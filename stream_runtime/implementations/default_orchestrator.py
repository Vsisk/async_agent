from __future__ import annotations

import inspect
from typing import Any

from stream_runtime.abstractions.aggregator import ResultAggregator
from stream_runtime.abstractions.errors import AggregationError, SourceStreamError
from stream_runtime.abstractions.executor import ObjectExecutor
from stream_runtime.abstractions.models import OrchestrationReport
from stream_runtime.abstractions.parser import IncrementalObjectParser
from stream_runtime.abstractions.scheduler import DynamicTaskScheduler
from stream_runtime.abstractions.source import StreamChunkSource


class DefaultStreamOrchestrator:
    """Default pipeline orchestrator for stream -> parse -> schedule -> aggregate."""

    def __init__(
        self,
        *,
        source: StreamChunkSource,
        parser: IncrementalObjectParser,
        scheduler: DynamicTaskScheduler,
        executor: ObjectExecutor,
        aggregator: ResultAggregator,
        fail_fast: bool = False,
    ) -> None:
        self._source = source
        self._parser = parser
        self._scheduler = scheduler
        self._executor = executor
        self._aggregator = aggregator
        self._fail_fast = fail_fast

    async def run(self) -> tuple[Any, OrchestrationReport]:
        source_error: BaseException | None = None
        flush_error: BaseException | None = None

        try:
            async for chunk in self._source.stream():
                objects = self._parser.feed(chunk)
                for obj in objects:
                    await self._scheduler.add_task(self._executor(obj), input_object=obj)

                    if self._fail_fast and self._scheduler.outcomes:
                        latest = self._scheduler.outcomes[-1]
                        if not latest.success:
                            raise RuntimeError("fail-fast: task failure detected")
        except BaseException as exc:
            source_error = SourceStreamError(str(exc))

        try:
            remaining = self._parser.flush()
            for obj in remaining:
                await self._scheduler.add_task(self._executor(obj), input_object=obj)
        except BaseException as exc:
            flush_error = exc

        outcomes = await self._scheduler.close_and_wait()
        report = OrchestrationReport(
            task_outcomes=outcomes,
            parse_issues=self._parser.issues,
            source_error=source_error,
            parser_flush_error=flush_error,
        )

        try:
            aggregated = self._aggregator(outcomes)
            if inspect.isawaitable(aggregated):
                aggregated = await aggregated
        except BaseException as exc:
            raise AggregationError(str(exc)) from exc

        return aggregated, report
