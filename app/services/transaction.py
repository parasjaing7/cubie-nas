from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(frozen=True)
class TransactionStep:
    name: str
    action: Callable[[], Awaitable[tuple[bool, str]]]
    rollback: Callable[[], Awaitable[None]] | None = None


class TransactionRunner:
    def __init__(self):
        self._steps: list[TransactionStep] = []

    def add_step(self, step: TransactionStep) -> None:
        self._steps.append(step)

    async def execute(self) -> tuple[bool, str]:
        completed: list[TransactionStep] = []
        for step in self._steps:
            ok, message = await step.action()
            if not ok:
                await self._rollback(completed)
                return False, message
            completed.append(step)
        return True, ''

    async def _rollback(self, completed: list[TransactionStep]) -> None:
        for step in reversed(completed):
            if not step.rollback:
                continue
            try:
                await step.rollback()
            except Exception:
                pass
