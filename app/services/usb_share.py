from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..config import settings
from .system_cmd import run_cmd


def _mkfs_cmd(device: str, fs_type: str) -> list[str]:
    if fs_type != 'ext4':
        raise ValueError('Only ext4 is supported for NAS usage')
    return ['mkfs.ext4', '-F', device]


async def _fstype_for_device(device: str) -> Optional[str]:
    rc, out, _ = await run_cmd(['blkid', '-s', 'TYPE', '-o', 'value', device])
    if rc == 0 and out:
        return out.strip()
    return None


async def _uuid_for_device(device: str) -> Optional[str]:
    rc, out, _ = await run_cmd(['blkid', '-s', 'UUID', '-o', 'value', device])
    if rc == 0 and out:
        return out.strip()
    return None


def _sanitize_share_name(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]', '', name)


def _upsert_fstab(device_ref: str, mountpoint: str, fs_type: str):
    fstab = Path('/etc/fstab')
    marker = '# cubie-nas'
    target = f'{device_ref} {mountpoint} {fs_type} defaults,nofail,x-systemd.device-timeout=5 0 2 {marker}'

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
) -> tuple[bool, str, dict]:
    if not device.startswith('/dev/'):
        return False, 'Invalid device path', {}

    name = _sanitize_share_name(share_name)
    if len(name) < 2:
        return False, 'Invalid share name', {}

    target_mount = mountpoint or f'/srv/nas/{name}'
    if not target_mount.startswith('/srv/nas/'):
        return False, 'Mountpoint must be under /srv/nas', {}

    if fs_type and fs_type != 'ext4':
        return False, 'Only EXT4 formatted drives are supported for NAS usage.', {}

    if format_before_mount and (fs_type or 'ext4') != 'ext4':
        return False, 'Only EXT4 formatted drives are supported for NAS usage.', {}

    rc, out, _ = await run_cmd(['lsblk', '-no', 'TRAN', device])
    transport = out.strip().lower() if rc == 0 else ''
    is_usb = 'usb' in transport

    rc, out, _ = await run_cmd(['findmnt', '-nr', '-o', 'TARGET', device])
    current_mount = out.strip() if rc == 0 and out else None
    if current_mount:
        rc_u, out_u, err_u = await run_cmd(['umount', device])
        if rc_u != 0:
            return False, err_u or out_u or 'Failed to unmount device', {'is_usb': is_usb}

    if format_before_mount:
        try:
            cmd = _mkfs_cmd(device, fs_type or 'ext4')
        except ValueError as exc:
            return False, str(exc), {'is_usb': is_usb}
        rc_f, out_f, err_f = await run_cmd(cmd)
        if rc_f != 0:
            return False, err_f or out_f or 'Format failed', {'is_usb': is_usb}

    detected_fs = await _fstype_for_device(device)
    if detected_fs != 'ext4':
        return False, 'Only EXT4 formatted drives are supported for NAS usage.', {'is_usb': is_usb, 'filesystem': detected_fs}

    Path(target_mount).mkdir(parents=True, exist_ok=True)

    uuid = await _uuid_for_device(device)
    mount_ref = f'UUID={uuid}' if uuid else device

    rc_m, out_m, err_m = await run_cmd(['mount', '-t', 'ext4', mount_ref, target_mount])
    if rc_m != 0:
        return False, err_m or out_m or 'Mount failed', {'is_usb': is_usb}

    nas_user = settings.nas_owner_user
    rc_chown, out_chown, err_chown = await run_cmd(['chown', '-R', f'{nas_user}:{nas_user}', target_mount])
    if rc_chown != 0:
        await run_cmd(['umount', target_mount])
        return False, err_chown or out_chown or 'Ownership update failed', {'is_usb': is_usb}

    rc_chmod, out_chmod, err_chmod = await run_cmd(['chmod', '-R', '0775', target_mount])
    if rc_chmod != 0:
        await run_cmd(['umount', target_mount])
        return False, err_chmod or out_chmod or 'Permission update failed', {'is_usb': is_usb}

    device_ref = f'UUID={uuid}' if uuid else device
    _upsert_fstab(device_ref, target_mount, 'ext4')

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
        f'USB share {name} mounted at {target_mount} and published via SMB',
        {
            'share_name': name,
            'mountpoint': target_mount,
            'device': device,
            'filesystem': 'ext4',
            'is_usb': is_usb,
            'nas_user': nas_user,
        },
    )
