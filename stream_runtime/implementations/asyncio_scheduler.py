from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable

from stream_runtime.abstractions.errors import SchedulerClosedError
from stream_runtime.abstractions.models import TaskOutcome


class AsyncioDynamicTaskScheduler:
    """Dynamic scheduler using asyncio tasks and semaphore for concurrency control."""

    def __init__(self, max_concurrency: int = 8) -> None:
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be greater than 0")

        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: set[asyncio.Task[None]] = set()
        self._outcomes: list[TaskOutcome] = []
        self._closed = False
        self._counter = 0
        self._lock = asyncio.Lock()

    @property
    def outcomes(self) -> list[TaskOutcome]:
        return self._outcomes

    async def add_task(self, coro: Awaitable[Any], *, input_object: Any) -> int:
        async with self._lock:
            if self._closed:
                raise SchedulerClosedError("scheduler is already closed")
            self._counter += 1
            task_id = self._counter

            task = asyncio.create_task(self._run_task(task_id, input_object, coro))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        return task_id

    async def close_and_wait(self) -> list[TaskOutcome]:
        async with self._lock:
            self._closed = True

        while self._tasks:
            snapshot = tuple(self._tasks)
            if not snapshot:
                break
            await asyncio.gather(*snapshot, return_exceptions=True)

        return self._outcomes

    async def _run_task(self, task_id: int, input_object: Any, coro: Awaitable[Any]) -> None:
        started_at = datetime.now(timezone.utc)
        async with self._semaphore:
            try:
                result = await coro
                outcome = TaskOutcome(
                    task_id=task_id,
                    input_object=input_object,
                    success=True,
                    result=result,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )
            except BaseException as exc:  # capture task-level errors without crashing scheduler
                outcome = TaskOutcome(
                    task_id=task_id,
                    input_object=input_object,
                    success=False,
                    error=exc,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )

        self._outcomes.append(outcome)
