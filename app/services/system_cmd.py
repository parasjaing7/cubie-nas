from __future__ import annotations

import asyncio
import shlex
import time
from dataclasses import dataclass
from subprocess import Process
from typing import Protocol

from ..config import settings


@dataclass(frozen=True)
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = 0
    delay_seconds: float = 0.0
    retry_on_exit_codes: tuple[int, ...] = (124,)


class CommandRunner(Protocol):
    async def run(
        self,
        cmd: list[str],
        timeout: int | None = None,
        retry: RetryPolicy | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        ...


class RealCommandRunner:
    async def run(
        self,
        cmd: list[str],
        timeout: int | None = None,
        retry: RetryPolicy | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        policy = retry or RetryPolicy()
        last_result: CommandResult | None = None
        attempts = max(policy.retries, 0) + 1

        for attempt in range(attempts):
            result = await _run_once(cmd, timeout, input_text=input_text)
            last_result = result
            if result.success:
                return result
            if result.exit_code not in policy.retry_on_exit_codes:
                return result
            if attempt < attempts - 1 and policy.delay_seconds > 0:
                await asyncio.sleep(policy.delay_seconds)

        return last_result or CommandResult(False, '', 'Command not executed', 1, 0.0)


class MockCommandRunner:
    def __init__(self, default: CommandResult | None = None):
        self.default = default or CommandResult(True, '', '', 0, 0.0)
        self.calls: list[dict] = []
        self._queue: list[CommandResult] = []

    def queue_result(self, result: CommandResult) -> None:
        self._queue.append(result)

    async def run(
        self,
        cmd: list[str],
        timeout: int | None = None,
        retry: RetryPolicy | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        self.calls.append({'cmd': cmd, 'timeout': timeout, 'retry': retry, 'input_text': input_text})
        if self._queue:
            return self._queue.pop(0)
        return self.default


async def _run_once(cmd: list[str], timeout: int | None = None, input_text: str | None = None) -> CommandResult:
    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    effective_timeout = timeout if timeout is not None else settings.command_timeout_sec
    stdin_data = input_text.encode() if input_text is not None else None
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin_data), timeout=effective_timeout)
    except asyncio.TimeoutError:
        proc.kill()
        out, err = await proc.communicate()
        err_txt = (err.decode(errors='ignore').strip() if err else '')
        detail = f'Command timed out after {effective_timeout}s'
        stdout = out.decode(errors='ignore').strip()
        stderr = f'{detail}. {err_txt}'.strip()
        return CommandResult(False, stdout, stderr, 124, time.monotonic() - start)

    stdout = out.decode(errors='ignore').strip()
    stderr = err.decode(errors='ignore').strip()
    exit_code = proc.returncode
    return CommandResult(exit_code == 0, stdout, stderr, exit_code, time.monotonic() - start)


async def run_cmd(cmd: list[str], timeout: int | None = None) -> tuple[int, str, str]:
    result = await RealCommandRunner().run(cmd, timeout=timeout)
    return result.exit_code, result.stdout, result.stderr


def shell_preview(cmd: list[str]) -> str:
    return ' '.join(shlex.quote(v) for v in cmd)


async def spawn_bash_pty(slave_fd: int):
    return await asyncio.create_subprocess_exec(
        '/bin/bash',
        '-i',
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        start_new_session=True,
    )


async def spawn_stream_process(cmd: list[str]):
    return await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
