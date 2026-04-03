from __future__ import annotations

import asyncio

from stream_runtime.section_pipeline.abstractions.models import ItemProcessResult, SectionContext, SectionItem
from stream_runtime.section_pipeline.abstractions.protocols import ItemProcessor


class AsyncioItemTaskScheduler:
    """Dynamically schedules item-level processing with asyncio tasks."""

    def __init__(self, *, max_concurrency: int = 8, fail_fast: bool = False) -> None:
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be greater than 0")

        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: set[asyncio.Task[None]] = set()
        self._results: list[ItemProcessResult] = []
        self._closed = False
        self._counter = 0
        self._lock = asyncio.Lock()
        self._fail_fast = fail_fast
        self._fatal_error: BaseException | None = None

    @property
    def results(self) -> list[ItemProcessResult]:
        return self._results

    @property
    def fatal_error(self) -> BaseException | None:
        return self._fatal_error

    def reset(self) -> None:
        self._tasks = set()
        self._results = []
        self._closed = False
        self._counter = 0
        self._fatal_error = None

    async def add_item_task(
        self,
        item: SectionItem,
        *,
        processor: ItemProcessor,
        section_context: SectionContext,
    ) -> int:
        async with self._lock:
            if self._closed:
                raise RuntimeError("scheduler is already closed")
            if self._fatal_error is not None and self._fail_fast:
                raise RuntimeError("scheduler aborted due to fail-fast failure")

            self._counter += 1
            task_id = self._counter
            task = asyncio.create_task(
                self._run_one(
                    task_id=task_id,
                    item=item,
                    processor=processor,
                    section_context=section_context,
                )
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return task_id

    async def wait_all(self) -> list[ItemProcessResult]:
        async with self._lock:
            self._closed = True

        while self._tasks:
            snapshot = tuple(self._tasks)
            await asyncio.gather(*snapshot, return_exceptions=True)

        if self._fatal_error is not None and self._fail_fast:
            raise RuntimeError("fail-fast: item processing aborted") from self._fatal_error

        return list(self._results)

    async def _run_one(
        self,
        *,
        task_id: int,
        item: SectionItem,
        processor: ItemProcessor,
        section_context: SectionContext,
    ) -> None:
        async with self._semaphore:
            try:
                result = await processor.process(item, section_context=section_context)
            except asyncio.CancelledError:
                result = ItemProcessResult(
                    item=item,
                    status="cancelled",
                    error="item processing cancelled",
                )
                self._results.append(result)
                raise
            except Exception as exc:
                result = ItemProcessResult(
                    item=item,
                    status="failed",
                    error=str(exc),
                    metadata={"task_id": task_id},
                )
            else:
                result.metadata.setdefault("task_id", task_id)

            self._results.append(result)

            if result.status == "failed" and self._fail_fast and self._fatal_error is None:
                self._fatal_error = RuntimeError(f"item {item.item_id} failed: {result.error}")
                self._cancel_pending()

    def _cancel_pending(self) -> None:
        for task in tuple(self._tasks):
            if not task.done():
                task.cancel()
