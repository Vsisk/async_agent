from __future__ import annotations

from typing import Any, Awaitable, Protocol

from .models import TaskOutcome


class DynamicTaskScheduler(Protocol):
    """A scheduler that supports dynamic task addition while running."""

    async def add_task(self, coro: Awaitable[Any], *, input_object: Any) -> int:
        ...

    async def close_and_wait(self) -> list[TaskOutcome]:
        ...

    @property
    def outcomes(self) -> list[TaskOutcome]:
        ...
