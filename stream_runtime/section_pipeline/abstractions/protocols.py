from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from .models import (
    ItemProcessResult,
    ParserIssue,
    SectionContext,
    SectionItem,
    SectionPipelineReport,
    StructuredNode,
)


class SectionClassifier(Protocol):
    async def classify(self, section_context: SectionContext) -> str:
        ...


class SectionItemStreamer(Protocol):
    async def stream_items(
        self,
        section_context: SectionContext,
        *,
        section_type: str,
    ) -> AsyncIterator[str]:
        ...


class IncrementalItemParser(Protocol):
    @property
    def issues(self) -> list[ParserIssue]:
        ...

    def feed(self, chunk: str) -> list[SectionItem]:
        ...

    def flush(self) -> list[SectionItem]:
        ...


class ItemProcessor(Protocol):
    async def process(
        self,
        item: SectionItem,
        *,
        section_context: SectionContext,
    ) -> ItemProcessResult:
        ...


class DynamicItemTaskScheduler(Protocol):
    @property
    def results(self) -> list[ItemProcessResult]:
        ...

    @property
    def fatal_error(self) -> BaseException | None:
        ...

    async def add_item_task(
        self,
        item: SectionItem,
        *,
        processor: ItemProcessor,
        section_context: SectionContext,
    ) -> int:
        ...

    async def wait_all(self) -> list[ItemProcessResult]:
        ...


class StructuredNodeAggregator(Protocol):
    async def aggregate(
        self,
        section_context: SectionContext,
        *,
        section_type: str,
        item_results: list[ItemProcessResult],
    ) -> StructuredNode:
        ...


class SectionPipelineOrchestrator(Protocol):
    @property
    def last_report(self) -> SectionPipelineReport | None:
        ...

    async def run(self, section_context: SectionContext) -> StructuredNode:
        ...
