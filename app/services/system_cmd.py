from __future__ import annotations

import asyncio
import shlex

from ..config import settings


async def run_cmd(cmd: list[str], timeout: int | None = None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    effective_timeout = timeout if timeout is not None else settings.command_timeout_sec
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=effective_timeout)
    except asyncio.TimeoutError:
        proc.kill()
        out, err = await proc.communicate()
        err_txt = (err.decode(errors='ignore').strip() if err else '')
        detail = f'Command timed out after {effective_timeout}s'
        return 124, out.decode(errors='ignore').strip(), f'{detail}. {err_txt}'.strip()

    return proc.returncode, out.decode(errors='ignore').strip(), err.decode(errors='ignore').strip()


def shell_preview(cmd: list[str]) -> str:
    return ' '.join(shlex.quote(v) for v in cmd)
