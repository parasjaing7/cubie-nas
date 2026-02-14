from __future__ import annotations

import asyncio

from .system_cmd import run_cmd


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
    rc, out, err = await run_cmd(['useradd', '-m', username])
    if rc != 0 and 'already exists' not in err.lower():
        return rc, out, err
    return await _chpasswd(username, password)


async def set_system_password(username: str, password: str) -> tuple[int, str, str]:
    return await _chpasswd(username, password)


async def active_sessions() -> list[dict]:
    rc, out, _ = await run_cmd(['who'])
    if rc != 0:
        return []

    sessions = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            sessions.append({'user': parts[0], 'tty': parts[1], 'date': f'{parts[2]} {parts[3]}', 'origin': parts[4]})
    return sessions
