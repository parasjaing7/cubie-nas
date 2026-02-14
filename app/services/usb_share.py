from __future__ import annotations

import asyncio
import re
import shlex
from pathlib import Path
from typing import Optional

from ..config import settings
from .system_cmd import run_cmd

SUPPORTED_FS = {'ext4', 'exfat'}


def _mkfs_cmd(device: str, fs_type: str) -> list[str]:
    if fs_type == 'ext4':
        return ['mkfs.ext4', '-F', device]
    if fs_type == 'exfat':
        return ['mkfs.exfat', '-f', device]
    raise ValueError('Only ext4 and exfat are supported for NAS usage')


async def _fstype_for_device(device: str) -> Optional[str]:
    rc, out, _ = await run_cmd(['blkid', '-s', 'TYPE', '-o', 'value', device])
    if rc == 0 and out:
        return out.strip().lower()

    rc_ls, out_ls, _ = await run_cmd(['lsblk', '-dn', '-o', 'FSTYPE', device])
    if rc_ls == 0 and out_ls:
        fs = out_ls.strip().lower()
        if fs:
            return fs

    return None


async def _uuid_for_device(device: str) -> Optional[str]:
    rc, out, _ = await run_cmd(['blkid', '-s', 'UUID', '-o', 'value', device])
    if rc == 0 and out:
        return out.strip()
    return None


async def _transport_for_device(device: str) -> str:
    rc, out, _ = await run_cmd(['lsblk', '-dn', '-o', 'TRAN', device])
    transport = out.strip().lower() if rc == 0 and out else ''
    if transport:
        return transport

    rc_pk, out_pk, _ = await run_cmd(['lsblk', '-no', 'PKNAME', device])
    parent = out_pk.strip()
    if rc_pk == 0 and parent:
        rc_t, out_t, _ = await run_cmd(['lsblk', '-dn', '-o', 'TRAN', f'/dev/{parent}'])
        if rc_t == 0 and out_t:
            return out_t.strip().lower()

    return ''


async def _device_type(device: str) -> str:
    rc, out, _ = await run_cmd(['lsblk', '-dn', '-o', 'TYPE', device])
    if rc == 0 and out:
        return out.strip().lower()
    return ''


async def _disk_has_partitions(device: str) -> bool:
    rc, out, _ = await run_cmd(['lsblk', '-nr', '-o', 'TYPE', device])
    if rc != 0 or not out:
        return False
    types = [line.strip().lower() for line in out.splitlines() if line.strip()]
    return len(types) > 1 and types[0] == 'disk' and any(t == 'part' for t in types[1:])


async def _uid_gid_for_user(username: str) -> tuple[Optional[str], Optional[str]]:
    rc_u, out_u, _ = await run_cmd(['id', '-u', username])
    rc_g, out_g, _ = await run_cmd(['id', '-g', username])
    uid = out_u.strip() if rc_u == 0 and out_u else None
    gid = out_g.strip() if rc_g == 0 and out_g else None
    return uid, gid


async def _unmount_device_tree(device: str) -> tuple[bool, str]:
    rc, out, err = await run_cmd(['lsblk', '-nr', '-o', 'PATH,MOUNTPOINT', device])
    if rc != 0:
        return False, err or out or 'Failed to inspect mount tree'

    entries: list[tuple[str, str]] = []
    for line in out.splitlines():
        row = line.strip()
        if not row:
            continue
        parts = row.split(None, 1)
        path = parts[0]
        mountpoint = parts[1].strip() if len(parts) > 1 else ''
        entries.append((path, mountpoint))

    for path, mountpoint in sorted(entries, key=lambda x: len(x[0]), reverse=True):
        if not mountpoint:
            continue
        if mountpoint == '[SWAP]':
            rc_s, out_s, err_s = await run_cmd(['swapoff', path])
            if rc_s != 0:
                return False, err_s or out_s or f'Failed to swapoff {path}'
            continue
        rc_u, out_u, err_u = await run_cmd(['umount', path])
        if rc_u != 0:
            return False, err_u or out_u or f'Failed to unmount {path}'

    return True, ''


def _partition_path_for_disk(device: str) -> str:
    # nvme0n1 -> nvme0n1p1, sda -> sda1
    return f'{device}p1' if device[-1].isdigit() else f'{device}1'


async def _repartition_single_partition(device: str) -> tuple[bool, str, Optional[str]]:
    ok, msg = await _unmount_device_tree(device)
    if not ok:
        return False, msg, None

    rc_w, out_w, err_w = await run_cmd(['wipefs', '-a', device])
    if rc_w != 0:
        return False, err_w or out_w or 'Failed to wipe filesystem signatures', None

    script = "label: gpt\n,\n"
    cmd = f"set -euo pipefail; printf %s {shlex.quote(script)} | sfdisk --wipe always {shlex.quote(device)}"
    rc_p, out_p, err_p = await run_cmd(['bash', '-lc', cmd])
    if rc_p != 0:
        return False, err_p or out_p or 'Failed to create GPT single partition', None

    await run_cmd(['partprobe', device])
    await run_cmd(['udevadm', 'settle'])

    part = _partition_path_for_disk(device)
    for _ in range(30):
        if await _device_type(part) == 'part':
            return True, '', part
        await asyncio.sleep(0.5)

    return False, f'Partition device did not appear after repartition: {part}', None


def _sanitize_share_name(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]', '', name)


def _upsert_fstab(device_ref: str, mountpoint: str, fs_type: str, mount_opts: str):
    fstab = Path('/etc/fstab')
    marker = '# cubie-nas'
    target = f'{device_ref} {mountpoint} {fs_type} {mount_opts} 0 2 {marker}'

    lines = []
    if fstab.exists():
        lines = fstab.read_text().splitlines()

    new_lines = []
    replaced = False
    for line in lines:
        if marker in line and f' {mountpoint} ' in f' {line} ':
            if not replaced:
                new_lines.append(target)
                replaced = True
            continue
        new_lines.append(line)

    if not replaced:
        new_lines.append(target)

    fstab.write_text('\n'.join(new_lines).rstrip() + '\n')


def _upsert_samba_share(share_name: str, mountpoint: str, nas_user: str):
    smb = Path('/etc/samba/smb.conf')
    if not smb.exists():
        raise RuntimeError('/etc/samba/smb.conf not found')

    begin = f'# cubie-nas-share:{share_name}:begin'
    end = f'# cubie-nas-share:{share_name}:end'

    block = [
        begin,
        f'[{share_name}]',
        f'   path = {mountpoint}',
        '   browseable = yes',
        '   writable = yes',
        '   read only = no',
        f'   valid users = {nas_user}',
        f'   force user = {nas_user}',
        f'   force group = {nas_user}',
        '   inherit permissions = yes',
        '   dos filemode = yes',
        '   map readonly = no',
        '   create mask = 0775',
        '   directory mask = 0775',
        end,
    ]

    lines = smb.read_text().splitlines()
    kept = []
    in_block = False
    for line in lines:
        if line.strip() == begin:
            in_block = True
            continue
        if line.strip() == end:
            in_block = False
            continue
        if not in_block:
            kept.append(line)

    if kept and kept[-1].strip() != '':
        kept.append('')
    kept.extend(block)
    kept.append('')
    smb.write_text('\n'.join(kept))


async def provision_usb_share(
    device: str,
    share_name: str,
    mountpoint: Optional[str],
    format_before_mount: bool,
    fs_type: Optional[str],
    wipe_repartition: bool = False,
    wipe_confirmation: Optional[str] = None,
) -> tuple[bool, str, dict]:
    return await provision_block_share(
        device=device,
        share_name=share_name,
        mountpoint=mountpoint,
        format_before_mount=format_before_mount,
        fs_type=fs_type,
        expected_transport='usb',
        label='USB',
        wipe_repartition=wipe_repartition,
        wipe_confirmation=wipe_confirmation,
    )


async def provision_nvme_share(
    device: str,
    share_name: str,
    mountpoint: Optional[str],
    format_before_mount: bool,
    fs_type: Optional[str],
    wipe_repartition: bool = False,
    wipe_confirmation: Optional[str] = None,
) -> tuple[bool, str, dict]:
    return await provision_block_share(
        device=device,
        share_name=share_name,
        mountpoint=mountpoint,
        format_before_mount=format_before_mount,
        fs_type=fs_type,
        expected_transport='nvme',
        label='NVMe',
        wipe_repartition=wipe_repartition,
        wipe_confirmation=wipe_confirmation,
    )


async def provision_block_share(
    device: str,
    share_name: str,
    mountpoint: Optional[str],
    format_before_mount: bool,
    fs_type: Optional[str],
    expected_transport: str,
    label: str,
    wipe_repartition: bool,
    wipe_confirmation: Optional[str],
) -> tuple[bool, str, dict]:
    if not device.startswith('/dev/'):
        return False, 'Invalid device path', {}

    name = _sanitize_share_name(share_name)
    if len(name) < 2:
        return False, 'Invalid share name', {}

    target_mount = mountpoint or f'/srv/nas/{name}'
    if not target_mount.startswith('/srv/nas/'):
        return False, 'Mountpoint must be under /srv/nas', {}

    if fs_type and fs_type not in SUPPORTED_FS:
        return False, 'Only EXT4 and exFAT formatted drives are supported for NAS usage.', {}

    if format_before_mount and (fs_type or 'ext4') not in SUPPORTED_FS:
        return False, 'Only EXT4 and exFAT formatted drives are supported for NAS usage.', {}

    transport = await _transport_for_device(device)
    is_usb = 'usb' in transport
    if expected_transport == 'usb' and 'usb' not in transport:
        return False, f'Selected device is not {label} storage', {'transport': transport}
    if expected_transport == 'nvme' and transport != 'nvme':
        return False, f'Selected device is not {label} storage', {'transport': transport}

    original_device = device
    working_device = device
    dev_type = await _device_type(device)

    if wipe_repartition:
        if dev_type != 'disk':
            return False, 'Wipe + single partition requires selecting a whole disk device (for example: /dev/nvme0n1).', {'type': dev_type}
        expected = f'WIPE {device}'
        if (wipe_confirmation or '').strip() != expected:
            return False, f'Confirmation text mismatch. Type exactly: {expected}', {}

        ok_r, msg_r, new_part = await _repartition_single_partition(device)
        if not ok_r or not new_part:
            return False, msg_r or 'Failed to wipe and repartition device', {}

        working_device = new_part
        format_before_mount = True
        fs_type = fs_type or 'ext4'
    elif expected_transport == 'nvme' and dev_type == 'disk' and await _disk_has_partitions(device):
        return (
            False,
            'Selected NVMe disk has partitions. Choose a partition (example: /dev/nvme0n1p2) or enable wipe + single partition.',
            {'transport': transport, 'type': dev_type},
        )

    rc, out, _ = await run_cmd(['findmnt', '-nr', '-o', 'TARGET', working_device])
    current_mount = out.strip() if rc == 0 and out else None
    if current_mount:
        rc_u, out_u, err_u = await run_cmd(['umount', working_device])
        if rc_u != 0:
            return False, err_u or out_u or 'Failed to unmount device', {'is_usb': is_usb}

    if format_before_mount:
        try:
            cmd = _mkfs_cmd(working_device, fs_type or 'ext4')
        except ValueError as exc:
            return False, str(exc), {'is_usb': is_usb}
        rc_f, out_f, err_f = await run_cmd(cmd)
        if rc_f != 0:
            return False, err_f or out_f or 'Format failed', {'is_usb': is_usb}

    detected_fs = await _fstype_for_device(working_device)
    if detected_fs not in SUPPORTED_FS:
        if not format_before_mount:
            return (
                False,
                f'{label} device must be ext4 or exfat. Enable "Format before mount" to convert it, or pre-format it as ext4/exfat.',
                {'is_usb': is_usb, 'filesystem': detected_fs},
            )
        return False, 'Formatting to ext4/exfat did not succeed.', {'is_usb': is_usb, 'filesystem': detected_fs}

    nas_user = getattr(settings, 'nas_owner_user', 'radxa')

    Path(target_mount).mkdir(parents=True, exist_ok=True)

    # Keep mountpoint writable by NAS user even before/after the block device mount.
    rc_mp_chown, out_mp_chown, err_mp_chown = await run_cmd(['chown', f'{nas_user}:{nas_user}', target_mount])
    if rc_mp_chown != 0:
        return False, err_mp_chown or out_mp_chown or 'Mountpoint ownership update failed', {'is_usb': is_usb}
    rc_mp_chmod, out_mp_chmod, err_mp_chmod = await run_cmd(['chmod', '0775', target_mount])
    if rc_mp_chmod != 0:
        return False, err_mp_chmod or out_mp_chmod or 'Mountpoint permission update failed', {'is_usb': is_usb}

    uuid = await _uuid_for_device(working_device)
    mount_ref = f'UUID={uuid}' if uuid else working_device

    mount_opts = 'defaults,rw,nofail,x-systemd.device-timeout=5'
    mount_cmd = ['mount', '-t', detected_fs]

    if detected_fs == 'exfat':
        uid, gid = await _uid_gid_for_user(nas_user)
        exfat_opts = 'rw,umask=0002'
        if uid and gid:
            exfat_opts = f'rw,uid={uid},gid={gid},umask=0002'
        mount_cmd.extend(['-o', exfat_opts])
        mount_opts = f'defaults,nofail,{exfat_opts},x-systemd.device-timeout=5'

    mount_cmd.extend([mount_ref, target_mount])
    rc_m, out_m, err_m = await run_cmd(mount_cmd)
    if rc_m != 0:
        return False, err_m or out_m or 'Mount failed', {'is_usb': is_usb}

    if detected_fs != 'exfat':
        rc_chown, out_chown, err_chown = await run_cmd(['chown', '-R', f'{nas_user}:{nas_user}', target_mount])
        if rc_chown != 0:
            await run_cmd(['umount', target_mount])
            return False, err_chown or out_chown or 'Ownership update failed', {'is_usb': is_usb}

        rc_chmod, out_chmod, err_chmod = await run_cmd(['chmod', '-R', '0775', target_mount])
        if rc_chmod != 0:
            await run_cmd(['umount', target_mount])
            return False, err_chmod or out_chmod or 'Permission update failed', {'is_usb': is_usb}

    device_ref = f'UUID={uuid}' if uuid else working_device
    _upsert_fstab(device_ref, target_mount, detected_fs, mount_opts)

    _upsert_samba_share(name, target_mount, nas_user)

    rc_t, out_t, err_t = await run_cmd(['testparm', '-s'])
    if rc_t != 0:
        return False, err_t or out_t or 'Samba config test failed', {'is_usb': is_usb}

    for cmd in [
        ['systemctl', 'enable', 'smbd'],
        ['systemctl', 'restart', 'smbd'],
    ]:
        rc_s, out_s, err_s = await run_cmd(cmd)
        if rc_s != 0:
            return False, err_s or out_s or 'Failed to apply SMB service changes', {'is_usb': is_usb}

    return (
        True,
        f'{label} share {name} mounted at {target_mount} and published via SMB',
        {
            'share_name': name,
            'mountpoint': target_mount,
            'device': working_device,
            'requested_device': original_device,
            'filesystem': detected_fs,
            'is_usb': is_usb,
            'transport': transport,
            'nas_user': nas_user,
            'wipe_repartition': wipe_repartition,
        },
    )
