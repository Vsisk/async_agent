from __future__ import annotations

import json
from typing import Any, Callable

from stream_runtime.section_pipeline.abstractions.models import ParserIssue, SectionItem


SectionItemFactory = Callable[[dict[str, Any]], SectionItem]


def default_section_item_factory(payload: dict[str, Any]) -> SectionItem:
    metadata = payload.get("metadata")
    if metadata is None or not isinstance(metadata, dict):
        metadata = {}

    bbox_value = payload.get("bbox")
    bbox = tuple(bbox_value) if isinstance(bbox_value, (list, tuple)) and len(bbox_value) == 4 else None

    return SectionItem(
        item_id=str(payload.get("item_id", payload.get("id", ""))),
        item_type=str(payload.get("item_type", "unknown")),
        raw_content=str(payload.get("raw_content", payload.get("content", ""))),
        bbox=bbox,
        order=int(payload.get("order", 0)),
        metadata=metadata,
    )


class JsonlItemParser:
    """Incrementally parses JSONL section items from arbitrarily split chunks."""

    def __init__(self, *, item_factory: SectionItemFactory | None = None) -> None:
        self._buffer = ""
        self._issues: list[ParserIssue] = []
        self._item_factory = item_factory or default_section_item_factory

    @property
    def issues(self) -> list[ParserIssue]:
        return self._issues

    def reset(self) -> None:
        self._buffer = ""
        self._issues.clear()

    def feed(self, chunk: str) -> list[SectionItem]:
        self._buffer += chunk
        return self._drain_lines(include_tail=False)

    def flush(self) -> list[SectionItem]:
        return self._drain_lines(include_tail=True)

    def _drain_lines(self, *, include_tail: bool) -> list[SectionItem]:
        items: list[SectionItem] = []

        while True:
            newline_index = self._buffer.find("\n")
            if newline_index < 0:
                break

            raw_line = self._buffer[:newline_index]
            self._buffer = self._buffer[newline_index + 1 :]
            item = self._parse_line(raw_line)
            if item is not None:
                items.append(item)

        if include_tail and self._buffer.strip():
            raw_line = self._buffer
            self._buffer = ""
            item = self._parse_line(raw_line)
            if item is not None:
                items.append(item)

        return items

    def _parse_line(self, raw_line: str) -> SectionItem | None:
        candidate = raw_line.strip()
        if not candidate:
            return None

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            self._issues.append(ParserIssue(raw_line=raw_line, error_message=str(exc)))
            return None

        if not isinstance(payload, dict):
            self._issues.append(
                ParserIssue(
                    raw_line=raw_line,
                    error_message="Each JSONL line must decode to a JSON object.",
                )
            )
            return None

        try:
            return self._item_factory(payload)
        except Exception as exc:
            self._issues.append(ParserIssue(raw_line=raw_line, error_message=str(exc)))
            return None
