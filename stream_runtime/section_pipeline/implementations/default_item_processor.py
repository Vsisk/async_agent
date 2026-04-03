from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from stream_runtime.section_pipeline.abstractions.models import ItemProcessResult, SectionContext, SectionItem


ParseItemContentFn = Callable[[SectionItem, SectionContext], Awaitable[Any] | Any]
GenerateDescriptionFn = Callable[[SectionItem, Any, SectionContext], Awaitable[str] | str]


class DefaultItemProcessor:
    """Default item processor with replaceable parse and description steps."""

    def __init__(
        self,
        *,
        parse_item_content: ParseItemContentFn,
        generate_item_description: GenerateDescriptionFn,
    ) -> None:
        self._parse_item_content = parse_item_content
        self._generate_item_description = generate_item_description

    async def process(
        self,
        item: SectionItem,
        *,
        section_context: SectionContext,
    ) -> ItemProcessResult:
        result = ItemProcessResult(
            item=item,
            status="pending",
            started_at=datetime.now(timezone.utc),
        )

        try:
            parsed_content = self._parse_item_content(item, section_context)
            if inspect.isawaitable(parsed_content):
                parsed_content = await parsed_content

            description = self._generate_item_description(item, parsed_content, section_context)
            if inspect.isawaitable(description):
                description = await description

            result.parsed_content = parsed_content
            result.description = str(description)
            result.status = "success"
        except asyncio.CancelledError:
            result.status = "cancelled"
            result.error = "item processing cancelled"
            raise
        except Exception as exc:
            result.status = "failed"
            result.error = str(exc)
        finally:
            result.finished_at = datetime.now(timezone.utc)

        return result
