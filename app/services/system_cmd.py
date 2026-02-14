from __future__ import annotations

import asyncio
import shlex


async def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode, out.decode().strip(), err.decode().strip()


def shell_preview(cmd: list[str]) -> str:
    return ' '.join(shlex.quote(v) for v in cmd)
