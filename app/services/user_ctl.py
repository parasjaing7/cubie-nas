from __future__ import annotations

from .system_cmd import RealCommandRunner

_runner = RealCommandRunner()


async def _chpasswd(username: str, password: str) -> tuple[int, str, str]:
    result = await _runner.run(['chpasswd'], input_text=f'{username}:{password}\n')
    return result.exit_code, result.stdout, result.stderr


async def create_system_user(username: str, password: str) -> tuple[int, str, str]:
    result = await _runner.run(['useradd', '-m', username])
    if result.exit_code != 0 and 'already exists' not in result.stderr.lower():
        return result.exit_code, result.stdout, result.stderr
    return await _chpasswd(username, password)


async def set_system_password(username: str, password: str) -> tuple[int, str, str]:
    return await _chpasswd(username, password)


async def active_sessions() -> list[dict]:
    result = await _runner.run(['who'])
    if result.exit_code != 0:
        return []

    sessions = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            sessions.append({'user': parts[0], 'tty': parts[1], 'date': f'{parts[2]} {parts[3]}', 'origin': parts[4]})
    return sessions
