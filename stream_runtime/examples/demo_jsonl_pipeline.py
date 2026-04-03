from __future__ import annotations

import asyncio
import os
from collections import Counter
from typing import Any

from stream_runtime.implementations.asyncio_scheduler import AsyncioDynamicTaskScheduler
from stream_runtime.implementations.default_orchestrator import DefaultStreamOrchestrator
from stream_runtime.implementations.jsonl_parser import JsonlIncrementalParser
from stream_runtime.implementations.openai_source import OpenAIStreamChunkSource


async def execute_one_object(obj: dict[str, Any]) -> dict[str, Any]:
    """Business logic injected by caller: execute one parsed JSON object."""
    await asyncio.sleep(0.2)  # simulate async downstream I/O
    text = str(obj.get("text", ""))
    return {
        "id": obj.get("id"),
        "length": len(text),
        "category": obj.get("category", "unknown"),
    }


def aggregate_results(outcomes: list[Any]) -> dict[str, Any]:
    """Business aggregator injected by caller."""
    success = [o for o in outcomes if o.success]
    failed = [o for o in outcomes if not o.success]

    category_counter = Counter()
    for item in success:
        if isinstance(item.result, dict):
            category_counter[item.result.get("category", "unknown")] += 1

    return {
        "total": len(outcomes),
        "success": len(success),
        "failed": len(failed),
        "category_counts": dict(category_counter),
    }


async def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Please set OPENAI_API_KEY before running this demo.")

    source = OpenAIStreamChunkSource(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        instructions=(
            "You must output JSONL only. "
            "Return exactly 5 lines. "
            "Each line is a JSON object with fields: id(int), text(str), category(str)."
        ),
        input="Generate sample records now.",
        temperature=0.1,
    )

    parser = JsonlIncrementalParser()
    scheduler = AsyncioDynamicTaskScheduler(max_concurrency=4)

    orchestrator = DefaultStreamOrchestrator(
        source=source,
        parser=parser,
        scheduler=scheduler,
        executor=execute_one_object,
        aggregator=aggregate_results,
        fail_fast=False,
    )

    final_result, report = await orchestrator.run()

    print("Final summary:", final_result)
    print("Task outcomes:", len(report.task_outcomes))
    print("Parse issues:", len(report.parse_issues))
    if report.source_error:
        print("Source error:", report.source_error)
    if report.parser_flush_error:
        print("Parser flush error:", report.parser_flush_error)


if __name__ == "__main__":
    asyncio.run(main())
