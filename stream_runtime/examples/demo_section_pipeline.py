from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stream_runtime.section_pipeline import (
    AsyncioItemTaskScheduler,
    DefaultItemProcessor,
    DefaultSectionPipelineOrchestrator,
    DefaultStructuredNodeAggregator,
    JsonlItemParser,
    SectionContext,
)


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}")


class DemoSectionClassifier:
    async def classify(self, section_context: SectionContext) -> str:
        log(f"SectionClassification start: section_id={section_context.section_id}")
        await asyncio.sleep(0.15)
        section_type = "fee_table"
        log(f"SectionClassification done: section_type={section_type}")
        return section_type


class DemoSectionItemStreamer:
    def __init__(self) -> None:
        self._jsonl_lines = [
            {
                "item_id": "item-1",
                "item_type": "fee",
                "raw_content": "挂号费 20 元",
                "order": 1,
                "metadata": {"currency": "CNY"},
            },
            {
                "item_id": "item-2",
                "item_type": "fee",
                "raw_content": "检查费 80 元",
                "order": 2,
                "metadata": {"currency": "CNY"},
            },
            {
                "item_id": "item-3",
                "item_type": "fee",
                "raw_content": "药品费 128 元",
                "order": 3,
                "metadata": {"currency": "CNY"},
            },
        ]

    async def stream_items(self, section_context: SectionContext, *, section_type: str):
        log(f"SectionItemStreamingExtraction start: section_type={section_type}")
        payload = "\n".join(json.dumps(line, ensure_ascii=False) for line in self._jsonl_lines) + "\n"

        chunk_sizes = [18, 11, 27, 9, 33, 1000]
        cursor = 0
        for chunk_size in chunk_sizes:
            if cursor >= len(payload):
                break
            next_cursor = min(len(payload), cursor + chunk_size)
            chunk = payload[cursor:next_cursor]
            cursor = next_cursor
            await asyncio.sleep(0.12)
            log(f"Streamer emitted chunk: {chunk!r}")
            yield chunk
        log("SectionItemStreamingExtraction done")


async def parse_item_content(item: Any, context: SectionContext) -> dict[str, Any]:
    log(f"ItemAsyncProcessing parse start: item_id={item.item_id}")
    await asyncio.sleep(0.35 if item.order == 1 else 0.2)
    parsed = {
        "tokens": item.raw_content.split(),
        "normalized_text": item.raw_content.replace(" ", ""),
        "section_type": context.classification_result,
    }
    log(f"ItemAsyncProcessing parse done: item_id={item.item_id}")
    return parsed


async def generate_item_description(item: Any, parsed_result: dict[str, Any], context: SectionContext) -> str:
    log(f"ItemAsyncProcessing describe start: item_id={item.item_id}")
    await asyncio.sleep(0.25 if item.order == 2 else 0.15)
    description = (
        f"{context.classification_result} item {item.item_id}: "
        f"{parsed_result['normalized_text']}"
    )
    log(f"ItemAsyncProcessing describe done: item_id={item.item_id}")
    return description


async def main() -> None:
    section_context = SectionContext(
        section_id="section-001",
        image_path="mock://invoice-page-1-section-001.png",
        page_no=1,
        metadata={"document_type": "medical_invoice"},
    )

    pipeline = DefaultSectionPipelineOrchestrator(
        classifier=DemoSectionClassifier(),
        item_streamer=DemoSectionItemStreamer(),
        item_parser=JsonlItemParser(),
        scheduler=AsyncioItemTaskScheduler(max_concurrency=3),
        item_processor=DefaultItemProcessor(
            parse_item_content=parse_item_content,
            generate_item_description=generate_item_description,
        ),
        aggregator=DefaultStructuredNodeAggregator(),
    )

    structured_node = await pipeline.run(section_context)

    log("StructuredNodeAggregation done")
    print("\nFinal structured node:")
    print(json.dumps(_to_jsonable(structured_node), ensure_ascii=False, indent=2))


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(val) for key, val in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(val) for key, val in value.items()}
    return value


if __name__ == "__main__":
    asyncio.run(main())
