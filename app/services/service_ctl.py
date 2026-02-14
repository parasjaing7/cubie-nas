from __future__ import annotations

from .system_cmd import run_cmd

SERVICE_MAP = {
    'samba': 'smbd',
    'nfs': 'nfs-kernel-server',
    'ssh': 'ssh',
    'ftp': 'vsftpd',
}


async def service_action(name: str, action: str) -> tuple[int, str, str]:
    unit = SERVICE_MAP.get(name)
    if not unit:
        return 1, '', f'Unknown service {name}'
    return await run_cmd(['systemctl', action, unit])


async def service_status(name: str) -> dict:
    unit = SERVICE_MAP.get(name)
    if not unit:
        return {'service': name, 'enabled': False, 'active': False}

    rc_e, out_e, _ = await run_cmd(['systemctl', 'is-enabled', unit])
    rc_a, out_a, _ = await run_cmd(['systemctl', 'is-active', unit])
    return {
        'service': name,
        'unit': unit,
        'enabled': rc_e == 0 and out_e == 'enabled',
        'active': rc_a == 0 and out_a == 'active',
    }
