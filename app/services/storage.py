from __future__ import annotations

import json

import psutil

from .system_cmd import run_cmd


async def list_drives() -> list[dict]:
    rc, out, _ = await run_cmd(['lsblk', '-J', '-o', 'NAME,KNAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,MODEL,TRAN'])
    if rc != 0 or not out:
        return []

    data = json.loads(out)
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
    rc, out, err = await run_cmd(['smartctl', '-H', device])
    if rc != 0:
        return f'unsupported ({err[:120]})' if err else 'unsupported'
    for line in out.splitlines():
        if 'SMART overall-health self-assessment test result' in line:
            return line.split(':', 1)[-1].strip()
        if 'SMART Health Status' in line:
            return line.split(':', 1)[-1].strip()
    return 'unknown'
