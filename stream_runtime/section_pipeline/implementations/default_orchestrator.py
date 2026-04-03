from __future__ import annotations

from dataclasses import replace

from stream_runtime.section_pipeline.abstractions.errors import (
    SectionClassificationError,
    SectionItemStreamError,
    StructuredAggregationError,
)
from stream_runtime.section_pipeline.abstractions.models import SectionContext, SectionPipelineReport, StructuredNode
from stream_runtime.section_pipeline.abstractions.protocols import (
    DynamicItemTaskScheduler,
    IncrementalItemParser,
    ItemProcessor,
    SectionClassifier,
    SectionItemStreamer,
    StructuredNodeAggregator,
)


class DefaultSectionPipelineOrchestrator:
    """Classify first, then stream items, process items concurrently, and aggregate once."""

    def __init__(
        self,
        *,
        classifier: SectionClassifier,
        item_streamer: SectionItemStreamer,
        item_parser: IncrementalItemParser,
        scheduler: DynamicItemTaskScheduler,
        item_processor: ItemProcessor,
        aggregator: StructuredNodeAggregator,
        fail_fast: bool = False,
    ) -> None:
        self._classifier = classifier
        self._item_streamer = item_streamer
        self._item_parser = item_parser
        self._scheduler = scheduler
        self._item_processor = item_processor
        self._aggregator = aggregator
        self._fail_fast = fail_fast
        self._last_report: SectionPipelineReport | None = None

    @property
    def last_report(self) -> SectionPipelineReport | None:
        return self._last_report

    async def run(self, section_context: SectionContext) -> StructuredNode:
        self._maybe_reset(self._item_parser)
        self._maybe_reset(self._scheduler)

        report = SectionPipelineReport(section_id=section_context.section_id)
        self._last_report = report

        try:
            section_type = await self._classifier.classify(section_context)
        except Exception as exc:
            report.fatal_error = str(exc)
            raise SectionClassificationError(str(exc)) from exc

        report.section_type = section_type
        runtime_context = replace(section_context, classification_result=section_type)

        try:
            async for chunk in self._item_streamer.stream_items(runtime_context, section_type=section_type):
                items = self._item_parser.feed(chunk)
                for item in items:
                    await self._scheduler.add_item_task(
                        item,
                        processor=self._item_processor,
                        section_context=runtime_context,
                    )
                if self._fail_fast and self._scheduler.fatal_error is not None:
                    raise self._scheduler.fatal_error

            for item in self._item_parser.flush():
                await self._scheduler.add_item_task(
                    item,
                    processor=self._item_processor,
                    section_context=runtime_context,
                )
        except Exception as exc:
            report.source_error = str(exc)
            if self._fail_fast:
                report.fatal_error = str(exc)
                raise SectionItemStreamError(str(exc)) from exc

        report.parser_issues = list(self._item_parser.issues)
        item_results = await self._scheduler.wait_all()
        report.item_results = list(item_results)

        if self._fail_fast and any(result.status == "failed" for result in item_results):
            first_error = next(result.error for result in item_results if result.status == "failed")
            report.fatal_error = first_error
            raise SectionItemStreamError(first_error or "fail-fast item failure")

        try:
            return await self._aggregator.aggregate(
                runtime_context,
                section_type=section_type,
                item_results=item_results,
            )
        except Exception as exc:
            report.fatal_error = str(exc)
            raise StructuredAggregationError(str(exc)) from exc

    @staticmethod
    def _maybe_reset(component: object) -> None:
        reset = getattr(component, "reset", None)
        if callable(reset):
            reset()
