from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .system_cmd import run_cmd


def _mkfs_cmd(device: str, fs_type: str) -> list[str]:
    mapping = {
        'ext4': ['mkfs.ext4', '-F', device],
        'xfs': ['mkfs.xfs', '-f', device],
        'vfat': ['mkfs.vfat', device],
        'exfat': ['mkfs.exfat', device],
        'ntfs': ['mkfs.ntfs', '-F', device],
    }
    return mapping[fs_type]


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


def _upsert_samba_share(share_name: str, mountpoint: str):
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
        '   read only = no',
        '   guest ok = yes',
        '   force user = nobody',
        '   create mask = 0664',
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

    if format_before_mount and not fs_type:
        return False, 'fs_type is required when format_before_mount=true', {}

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
        rc_f, out_f, err_f = await run_cmd(_mkfs_cmd(device, fs_type or 'ext4'))
        if rc_f != 0:
            return False, err_f or out_f or 'Format failed', {'is_usb': is_usb}

    detected_fs = await _fstype_for_device(device)
    if not detected_fs:
        return False, 'Could not detect filesystem. Format first or use supported filesystem.', {'is_usb': is_usb}

    Path(target_mount).mkdir(parents=True, exist_ok=True)

    rc_m, out_m, err_m = await run_cmd(['mount', device, target_mount])
    if rc_m != 0:
        return False, err_m or out_m or 'Mount failed', {'is_usb': is_usb}

    rc_c, out_c, err_c = await run_cmd(['chmod', '0777', target_mount])
    if rc_c != 0:
        return False, err_c or out_c or 'Permission update failed', {'is_usb': is_usb}

    uuid = await _uuid_for_device(device)
    device_ref = f'UUID={uuid}' if uuid else device
    _upsert_fstab(device_ref, target_mount, detected_fs)

    _upsert_samba_share(name, target_mount)

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
            'filesystem': detected_fs,
            'is_usb': is_usb,
        },
    )
