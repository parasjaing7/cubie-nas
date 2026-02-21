from __future__ import annotations

import json
import time
from pathlib import Path
from shutil import disk_usage

import psutil

from ..config import settings
from .system_cmd import RealCommandRunner

_runner = RealCommandRunner()
_DEVICE_CACHE: dict[str, object] = {'ts': 0.0, 'data': []}


def _size_to_gb(raw_size: int) -> float:
    return round(raw_size / (1024 ** 3), 1)


def _device_type(name: str, transport: str | None) -> str:
    low_name = (name or '').lower()
    low_transport = (transport or '').lower()
    if low_name.startswith('mmcblk'):
        return 'sd'
    if low_transport == 'usb':
        return 'usb'
    if low_transport == 'nvme' or low_name.startswith('nvme'):
        return 'nvme'
    return 'disk'


async def list_storage_devices() -> list[dict]:
    now = time.time()
    cached_ts = float(_DEVICE_CACHE.get('ts', 0.0))
    if now - cached_ts < 10.0:
        return list(_DEVICE_CACHE.get('data', []))

    result = await _runner.run(['lsblk', '-J', '-o', 'NAME,MOUNTPOINT,SIZE,TRAN,TYPE,LABEL,FSTYPE'])
    if result.exit_code != 0 or not result.stdout:
        return []

    try:
        parsed = json.loads(result.stdout)
    except Exception:
        return []
    out: list[dict] = []

    def walk(nodes: list[dict]):
        for node in nodes:
            mountpoint = node.get('mountpoint')
            if mountpoint:
                resolved = Path(mountpoint).resolve(strict=False)
                if resolved.exists() and resolved.is_dir():
                    usage = disk_usage(str(resolved))
                    total_gb = _size_to_gb(usage.total)
                    used_gb = _size_to_gb(usage.used)
                    free_gb = _size_to_gb(usage.free)
                    name = node.get('name') or ''
                    nas_root = Path(settings.nas_root).resolve(strict=False)
                    browse_path = None
                    if resolved == nas_root or nas_root in resolved.parents:
                        browse_path = str(resolved.relative_to(nas_root))
                    out.append(
                        {
                            'id': name,
                            'label': node.get('label') or name,
                            'type': _device_type(name, node.get('tran')),
                            'mountpoint': str(resolved),
                            'total_gb': total_gb,
                            'used_gb': used_gb,
                            'free_gb': free_gb,
                            'browse_path': browse_path,
                        }
                    )

            children = node.get('children') or []
            if children:
                walk(children)

    walk(parsed.get('blockdevices', []))
    _DEVICE_CACHE['ts'] = now
    _DEVICE_CACHE['data'] = out
    return out


async def list_drives() -> list[dict]:
    result = await _runner.run(['lsblk', '-J', '-o', 'NAME,KNAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,MODEL,TRAN'])
    if result.exit_code != 0 or not result.stdout:
        return []

    data = json.loads(result.stdout)
    drives: list[dict] = []

    def walk(devs: list[dict]):
        for dev in devs:
            if dev.get('type') in {'disk', 'part'}:
                mp = dev.get('mountpoint')
                used = free = None
                if mp:
                    try:
                        usage = psutil.disk_usage(mp)
                        used = usage.used
                        free = usage.free
                    except Exception:
                        pass
                drives.append(
                    {
                        'name': dev.get('name'),
                        'device': f"/dev/{dev.get('kname', dev.get('name'))}",
                        'fstype': dev.get('fstype'),
                        'size': dev.get('size'),
                        'mountpoint': mp,
                        'used_bytes': used,
                        'free_bytes': free,
                        'model': dev.get('model'),
                        'transport': dev.get('tran'),
                        'is_usb': (dev.get('tran') or '').lower() == 'usb',
                    }
                )
            children = dev.get('children') or []
            if children:
                walk(children)

    walk(data.get('blockdevices', []))
    return drives


async def smart_status(device: str) -> str:
    result = await _runner.run(['smartctl', '-H', device])
    if result.exit_code != 0:
        return f'unsupported ({result.stderr[:120]})' if result.stderr else 'unsupported'
    for line in result.stdout.splitlines():
        if 'SMART overall-health self-assessment test result' in line:
            return line.split(':', 1)[-1].strip()
        if 'SMART Health Status' in line:
            return line.split(':', 1)[-1].strip()
    return 'unknown'
