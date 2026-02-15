from __future__ import annotations

from .system_cmd import RealCommandRunner

_runner = RealCommandRunner()

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
    result = await _runner.run(['systemctl', action, unit])
    return result.exit_code, result.stdout, result.stderr


async def service_status(name: str) -> dict:
    unit = SERVICE_MAP.get(name)
    if not unit:
        return {'service': name, 'enabled': False, 'active': False}

    result_e = await _runner.run(['systemctl', 'is-enabled', unit])
    result_a = await _runner.run(['systemctl', 'is-active', unit])
    return {
        'service': name,
        'unit': unit,
        'enabled': result_e.exit_code == 0 and result_e.stdout == 'enabled',
        'active': result_a.exit_code == 0 and result_a.stdout == 'active',
    }
