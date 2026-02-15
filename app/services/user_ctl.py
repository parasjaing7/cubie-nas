from __future__ import annotations

import asyncio

from .system_cmd import RealCommandRunner

_runner = RealCommandRunner()


async def _chpasswd(username: str, password: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        'chpasswd',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(f'{username}:{password}'.encode())
    return proc.returncode, out.decode().strip(), err.decode().strip()


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
