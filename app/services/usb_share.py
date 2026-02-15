from __future__ import annotations

import asyncio
import os
import re
import shlex
import tempfile
from pathlib import Path
from typing import Optional

from ..config import settings
from .system_cmd import CommandRunner, RealCommandRunner
from .transaction import TransactionRunner, TransactionStep

SUPPORTED_FS = {'ext4', 'exfat'}
_PROVISION_LOCK = asyncio.Lock()


def _mkfs_cmd(device: str, fs_type: str) -> list[str]:
    if fs_type == 'ext4':
        return ['mkfs.ext4', '-F', device]
    if fs_type == 'exfat':
        return ['mkfs.exfat', '-f', device]
    raise ValueError('Only ext4 and exfat are supported for NAS usage')


async def _fstype_for_device(device: str, runner: CommandRunner) -> Optional[str]:
    result = await runner.run(['blkid', '-s', 'TYPE', '-o', 'value', device])
    if result.exit_code == 0 and result.stdout:
        return result.stdout.strip().lower()

    result_ls = await runner.run(['lsblk', '-dn', '-o', 'FSTYPE', device])
    if result_ls.exit_code == 0 and result_ls.stdout:
        fs = result_ls.stdout.strip().lower()
        if fs:
            return fs

    return None


async def _uuid_for_device(device: str, runner: CommandRunner) -> Optional[str]:
    result = await runner.run(['blkid', '-s', 'UUID', '-o', 'value', device])
    if result.exit_code == 0 and result.stdout:
        return result.stdout.strip()
    return None


async def _transport_for_device(device: str, runner: CommandRunner) -> str:
    result = await runner.run(['lsblk', '-dn', '-o', 'TRAN', device])
    transport = result.stdout.strip().lower() if result.exit_code == 0 and result.stdout else ''
    if transport:
        return transport

    result_pk = await runner.run(['lsblk', '-no', 'PKNAME', device])
    parent = result_pk.stdout.strip()
    if result_pk.exit_code == 0 and parent:
        result_t = await runner.run(['lsblk', '-dn', '-o', 'TRAN', f'/dev/{parent}'])
        if result_t.exit_code == 0 and result_t.stdout:
            return result_t.stdout.strip().lower()

    return ''


async def _device_type(device: str, runner: CommandRunner) -> str:
    result = await runner.run(['lsblk', '-dn', '-o', 'TYPE', device])
    if result.exit_code == 0 and result.stdout:
        return result.stdout.strip().lower()
    return ''


async def _preflight_device(
    device: str,
    expected_transport: str,
    runner: CommandRunner,
) -> tuple[bool, str, dict]:
    result = await runner.run(['lsblk', '-dn', '-o', 'TYPE,TRAN,SIZE,MODEL', device])
    if result.exit_code != 0 or not result.stdout:
        return False, result.stderr or result.stdout or 'Device not found', {}

    parts = result.stdout.split(None, 3)
    dev_type = parts[0].strip().lower() if len(parts) > 0 else ''
    transport = parts[1].strip().lower() if len(parts) > 1 else ''
    size = parts[2].strip() if len(parts) > 2 else ''
    model = parts[3].strip() if len(parts) > 3 else ''

    if expected_transport == 'usb' and 'usb' not in transport:
        return False, 'Selected device is not USB storage', {'transport': transport, 'type': dev_type}
    if expected_transport == 'nvme' and transport != 'nvme':
        return False, 'Selected device is not NVMe storage', {'transport': transport, 'type': dev_type}

    result_root = await runner.run(['findmnt', '-nr', '-o', 'SOURCE', '/'])
    root_src = result_root.stdout.strip() if result_root.exit_code == 0 and result_root.stdout else ''
    os_disk = ''
    if root_src.startswith('/dev/'):
        result_pk = await runner.run(['lsblk', '-no', 'PKNAME', root_src])
        if result_pk.exit_code == 0 and result_pk.stdout.strip():
            os_disk = f"/dev/{result_pk.stdout.strip()}"

    if root_src and (device == root_src or device == os_disk):
        return False, 'Selected device is the OS disk/root device and cannot be provisioned', {
            'root_source': root_src,
            'os_disk': os_disk,
        }

    return True, '', {'transport': transport, 'type': dev_type, 'size': size, 'model': model}


async def _disk_has_partitions(device: str, runner: CommandRunner) -> bool:
    result = await runner.run(['lsblk', '-nr', '-o', 'TYPE', device])
    if result.exit_code != 0 or not result.stdout:
        return False
    types = [line.strip().lower() for line in result.stdout.splitlines() if line.strip()]
    return len(types) > 1 and types[0] == 'disk' and any(t == 'part' for t in types[1:])


async def _uid_gid_for_user(username: str, runner: CommandRunner) -> tuple[Optional[str], Optional[str]]:
    result_u = await runner.run(['id', '-u', username])
    result_g = await runner.run(['id', '-g', username])
    uid = result_u.stdout.strip() if result_u.exit_code == 0 and result_u.stdout else None
    gid = result_g.stdout.strip() if result_g.exit_code == 0 and result_g.stdout else None
    return uid, gid


async def _unmount_device_tree(device: str, runner: CommandRunner) -> tuple[bool, str]:
    result = await runner.run(['lsblk', '-nr', '-o', 'PATH,MOUNTPOINT', device])
    if result.exit_code != 0:
        return False, result.stderr or result.stdout or 'Failed to inspect mount tree'

    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
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
            result_s = await runner.run(['swapoff', path])
            if result_s.exit_code != 0:
                return False, result_s.stderr or result_s.stdout or f'Failed to swapoff {path}'
            continue
        result_u = await runner.run(['umount', path])
        if result_u.exit_code != 0:
            return False, result_u.stderr or result_u.stdout or f'Failed to unmount {path}'

    return True, ''


def _partition_path_for_disk(device: str) -> str:
    # nvme0n1 -> nvme0n1p1, sda -> sda1
    return f'{device}p1' if device[-1].isdigit() else f'{device}1'


async def _repartition_single_partition(device: str, runner: CommandRunner) -> tuple[bool, str, Optional[str]]:
    ok, msg = await _unmount_device_tree(device, runner)
    if not ok:
        return False, msg, None

    result_w = await runner.run(['wipefs', '-a', device])
    if result_w.exit_code != 0:
        return False, result_w.stderr or result_w.stdout or 'Failed to wipe filesystem signatures', None

    script = "label: gpt\n,\n"
    cmd = f"set -euo pipefail; printf %s {shlex.quote(script)} | sfdisk --wipe always {shlex.quote(device)}"
    result_p = await runner.run(['bash', '-lc', cmd])
    if result_p.exit_code != 0:
        return False, result_p.stderr or result_p.stdout or 'Failed to create GPT single partition', None

    await runner.run(['partprobe', device])
    await runner.run(['udevadm', 'settle'])

    part = _partition_path_for_disk(device)
    for _ in range(30):
        if await _device_type(part, runner) == 'part':
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

    _atomic_write_text(fstab, '\n'.join(new_lines).rstrip() + '\n')


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
    _atomic_write_text(smb, '\n'.join(kept))


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _atomic_copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=str(target.parent))
    try:
        with source.open('rb') as src, os.fdopen(fd, 'wb') as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(tmp_path, target)
        dir_fd = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


async def _verify_mount(
    target_mount: str,
    expected_uuid: Optional[str],
    runner: CommandRunner,
) -> tuple[bool, str]:
    result_target = await runner.run(['findmnt', '-nr', '-o', 'TARGET', '--target', target_mount])
    mounted_target = result_target.stdout.strip() if result_target.exit_code == 0 and result_target.stdout else ''
    if mounted_target != target_mount:
        return False, 'Post-mount verification failed: mountpoint is not active'

    if expected_uuid:
        result_source = await runner.run(['findmnt', '-nr', '-o', 'SOURCE', '--target', target_mount])
        mount_source = result_source.stdout.strip() if result_source.exit_code == 0 and result_source.stdout else ''
        if not mount_source.startswith('/dev/'):
            return False, 'Post-mount verification failed: unable to determine mounted source device'
        mounted_uuid = await _uuid_for_device(mount_source, runner)
        if mounted_uuid != expected_uuid:
            return False, 'Post-mount verification failed: mounted device UUID mismatch'

    return True, ''


def _backup_file(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + '.cubie-nas.bak')
    _atomic_copy_file(path, backup)
    return backup


def _restore_file(path: Path, backup: Optional[Path]) -> None:
    if backup and backup.exists():
        _atomic_copy_file(backup, path)
        return
    if path.exists():
        path.unlink(missing_ok=True)


async def provision_usb_share(
    device: str,
    share_name: str,
    mountpoint: Optional[str],
    format_before_mount: bool,
    fs_type: Optional[str],
    wipe_repartition: bool = False,
    wipe_confirmation: Optional[str] = None,
    runner: CommandRunner | None = None,
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
        runner=runner,
    )


async def provision_nvme_share(
    device: str,
    share_name: str,
    mountpoint: Optional[str],
    format_before_mount: bool,
    fs_type: Optional[str],
    wipe_repartition: bool = False,
    wipe_confirmation: Optional[str] = None,
    runner: CommandRunner | None = None,
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
        runner=runner,
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
    runner: CommandRunner | None,
) -> tuple[bool, str, dict]:
    if _PROVISION_LOCK.locked():
        return False, 'Another provisioning operation is already in progress', {}

    async with _PROVISION_LOCK:
        return await _provision_block_share_impl(
            device=device,
            share_name=share_name,
            mountpoint=mountpoint,
            format_before_mount=format_before_mount,
            fs_type=fs_type,
            expected_transport=expected_transport,
            label=label,
            wipe_repartition=wipe_repartition,
            wipe_confirmation=wipe_confirmation,
            runner=runner,
        )


async def _provision_block_share_impl(
    device: str,
    share_name: str,
    mountpoint: Optional[str],
    format_before_mount: bool,
    fs_type: Optional[str],
    expected_transport: str,
    label: str,
    wipe_repartition: bool,
    wipe_confirmation: Optional[str],
    runner: CommandRunner | None,
) -> tuple[bool, str, dict]:
    runner = runner or RealCommandRunner()
    if not device.startswith('/dev/'):
        return False, 'Invalid device path', {}

    name = _sanitize_share_name(share_name)
    if len(name) < 2:
        return False, 'Invalid share name', {}

    target_mount = mountpoint or f'/srv/nas/{name}'
    target_mount_path = Path(target_mount)
    target_mount_resolved = target_mount_path.resolve(strict=False)
    nas_root = Path('/srv/nas').resolve(strict=False)
    if nas_root not in [target_mount_resolved, *target_mount_resolved.parents]:
        return False, 'Mountpoint must be under /srv/nas', {}

    if fs_type and fs_type not in SUPPORTED_FS:
        return False, 'Only EXT4 and exFAT formatted drives are supported for NAS usage.', {}

    if format_before_mount and (fs_type or 'ext4') not in SUPPORTED_FS:
        return False, 'Only EXT4 and exFAT formatted drives are supported for NAS usage.', {}

    ok_pre, msg_pre, meta = await _preflight_device(device, expected_transport, runner)
    if not ok_pre:
        return False, msg_pre, meta

    transport = meta.get('transport', '')
    is_usb = 'usb' in transport
    size = meta.get('size', '')
    model = meta.get('model', '')

    original_device = device
    working_device = device
    dev_type = await _device_type(device, runner)

    if wipe_repartition:
        if dev_type != 'disk':
            return False, 'Wipe + single partition requires selecting a whole disk device (for example: /dev/nvme0n1).', {'type': dev_type}
        expected = f'WIPE {device} ({model} {size})'.strip()
        if (wipe_confirmation or '').strip() != expected:
            return False, f'Confirmation text mismatch. Type exactly: {expected}', {
                'device': device,
                'model': model,
                'size': size,
            }

        ok_r, msg_r, new_part = await _repartition_single_partition(device, runner)
        if not ok_r or not new_part:
            return False, msg_r or 'Failed to wipe and repartition device', {}

        working_device = new_part
        format_before_mount = True
        fs_type = fs_type or 'ext4'
    elif expected_transport == 'nvme' and dev_type == 'disk' and await _disk_has_partitions(device, runner):
        return (
            False,
            'Selected NVMe disk has partitions. Choose a partition (example: /dev/nvme0n1p2) or enable wipe + single partition.',
            {'transport': transport, 'type': dev_type},
        )

    result_find = await runner.run(['findmnt', '-nr', '-o', 'TARGET', working_device])
    current_mount = result_find.stdout.strip() if result_find.exit_code == 0 and result_find.stdout else None
    if current_mount:
        result_u = await runner.run(['umount', working_device])
        if result_u.exit_code != 0:
            return False, result_u.stderr or result_u.stdout or 'Failed to unmount device', {'is_usb': is_usb}

    if format_before_mount:
        try:
            cmd = _mkfs_cmd(working_device, fs_type or 'ext4')
        except ValueError as exc:
            return False, str(exc), {'is_usb': is_usb}
        result_f = await runner.run(cmd)
        if result_f.exit_code != 0:
            return False, result_f.stderr or result_f.stdout or 'Format failed', {'is_usb': is_usb}

    detected_fs = await _fstype_for_device(working_device, runner)
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
    result_mp_chown = await runner.run(['chown', f'{nas_user}:{nas_user}', target_mount])
    if result_mp_chown.exit_code != 0:
        return False, result_mp_chown.stderr or result_mp_chown.stdout or 'Mountpoint ownership update failed', {'is_usb': is_usb}
    result_mp_chmod = await runner.run(['chmod', '0775', target_mount])
    if result_mp_chmod.exit_code != 0:
        return False, result_mp_chmod.stderr or result_mp_chmod.stdout or 'Mountpoint permission update failed', {'is_usb': is_usb}

    uuid = await _uuid_for_device(working_device, runner)
    mount_ref = f'UUID={uuid}' if uuid else working_device

    mount_opts = 'defaults,rw,nofail,x-systemd.device-timeout=5'
    mount_cmd = ['mount', '-t', detected_fs]

    if detected_fs == 'exfat':
        uid, gid = await _uid_gid_for_user(nas_user, runner)
        exfat_opts = 'rw,umask=0002'
        if uid and gid:
            exfat_opts = f'rw,uid={uid},gid={gid},umask=0002'
        mount_cmd.extend(['-o', exfat_opts])
        mount_opts = f'defaults,nofail,{exfat_opts},x-systemd.device-timeout=5'

    mount_cmd.extend([mount_ref, target_mount])

    async def _run_mount() -> tuple[bool, str]:
        result = await runner.run(mount_cmd)
        if result.exit_code != 0:
            return False, result.stderr or result.stdout or 'Mount failed'
        return True, ''

    async def _run_verify_mount() -> tuple[bool, str]:
        ok_v, msg_v = await _verify_mount(target_mount, uuid, runner)
        return ok_v, msg_v

    async def _run_chown() -> tuple[bool, str]:
        result = await runner.run(['chown', '-R', f'{nas_user}:{nas_user}', target_mount])
        if result.exit_code != 0:
            return False, result.stderr or result.stdout or 'Ownership update failed'
        return True, ''

    async def _run_chmod() -> tuple[bool, str]:
        result = await runner.run(['chmod', '-R', '0775', target_mount])
        if result.exit_code != 0:
            return False, result.stderr or result.stdout or 'Permission update failed'
        return True, ''

    async def _rollback_mount() -> None:
        await runner.run(['umount', target_mount])

    fstab_path = Path('/etc/fstab')
    smb_path = Path('/etc/samba/smb.conf')
    fstab_backup: list[Optional[Path]] = [None]
    smb_backup: list[Optional[Path]] = [None]

    async def _run_fstab_update() -> tuple[bool, str]:
        fstab_backup[0] = _backup_file(fstab_path)
        _upsert_fstab(device_ref, target_mount, detected_fs, mount_opts)
        return True, ''

    async def _rollback_fstab() -> None:
        _restore_file(fstab_path, fstab_backup[0])

    async def _run_smb_update() -> tuple[bool, str]:
        smb_backup[0] = _backup_file(smb_path)
        _upsert_samba_share(name, target_mount, nas_user)
        return True, ''

    async def _rollback_smb() -> None:
        _restore_file(smb_path, smb_backup[0])

    async def _run_testparm() -> tuple[bool, str]:
        result = await runner.run(['testparm', '-s'])
        if result.exit_code != 0:
            return False, result.stderr or result.stdout or 'Samba config test failed'
        return True, ''

    async def _run_systemctl(cmd: list[str]) -> tuple[bool, str]:
        result = await runner.run(cmd)
        if result.exit_code != 0:
            return False, result.stderr or result.stdout or 'Failed to apply SMB service changes'
        return True, ''

    txn = TransactionRunner()
    device_ref = f'UUID={uuid}' if uuid else working_device
    txn.add_step(TransactionStep(name='mount', action=_run_mount, rollback=_rollback_mount))
    txn.add_step(TransactionStep(name='verify_mount', action=_run_verify_mount, rollback=_rollback_mount))
    if detected_fs != 'exfat':
        txn.add_step(TransactionStep(name='chown', action=_run_chown))
        txn.add_step(TransactionStep(name='chmod', action=_run_chmod))
    txn.add_step(TransactionStep(name='fstab', action=_run_fstab_update, rollback=_rollback_fstab))
    txn.add_step(TransactionStep(name='smb', action=_run_smb_update, rollback=_rollback_smb))
    txn.add_step(TransactionStep(name='testparm', action=_run_testparm))
    txn.add_step(TransactionStep(name='smbd_enable', action=lambda: _run_systemctl(['systemctl', 'enable', 'smbd'])))
    txn.add_step(TransactionStep(name='smbd_restart', action=lambda: _run_systemctl(['systemctl', 'restart', 'smbd'])))

    ok, message = await txn.execute()
    if not ok:
        return False, message, {'is_usb': is_usb}

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
