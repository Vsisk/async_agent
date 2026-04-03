from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from stream_runtime.section_pipeline.abstractions.models import (
    ItemProcessResult,
    SectionContext,
    StructuredNode,
)


AggregateStrategy = Callable[
    [SectionContext, str, list[ItemProcessResult]],
    Awaitable[StructuredNode | dict[str, Any]] | StructuredNode | dict[str, Any],
]


class DefaultStructuredNodeAggregator:
    """Builds a structured node after all item tasks have converged."""

    def __init__(self, *, aggregate_strategy: AggregateStrategy | None = None) -> None:
        self._aggregate_strategy = aggregate_strategy

    async def aggregate(
        self,
        section_context: SectionContext,
        *,
        section_type: str,
        item_results: list[ItemProcessResult],
    ) -> StructuredNode:
        ordered_results = sorted(item_results, key=lambda result: result.item.order)

        if self._aggregate_strategy is not None:
            candidate = self._aggregate_strategy(section_context, section_type, ordered_results)
            if inspect.isawaitable(candidate):
                candidate = await candidate
            if isinstance(candidate, StructuredNode):
                return candidate
            if isinstance(candidate, dict):
                return StructuredNode(**candidate)
            raise TypeError("aggregate_strategy must return StructuredNode or dict")

        success_results = [result for result in ordered_results if result.status == "success"]
        failed_results = [result for result in ordered_results if result.status != "success"]

        children = [
            {
                "item_id": result.item.item_id,
                "item_type": result.item.item_type,
                "order": result.item.order,
                "raw_content": result.item.raw_content,
                "parsed_content": result.parsed_content,
                "description": result.description,
                "status": result.status,
                "error": result.error,
            }
            for result in ordered_results
        ]

        return StructuredNode(
            section_id=section_context.section_id,
            section_type=section_type,
            node_type=f"{section_type}_node",
            children=children,
            fields={
                "successful_item_count": len(success_results),
                "failed_item_count": len(failed_results),
            },
            item_results=ordered_results,
            metadata={
                "page_no": section_context.page_no,
                "classification_result": section_context.classification_result,
                "upstream_metadata": dict(section_context.metadata),
            },
        )
