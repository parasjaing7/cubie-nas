from __future__ import annotations

import json

import psutil

from .system_cmd import RealCommandRunner

_runner = RealCommandRunner()


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
