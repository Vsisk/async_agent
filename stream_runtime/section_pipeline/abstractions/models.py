from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


SectionBBox = tuple[float, float, float, float]
ItemStatus = Literal["pending", "success", "failed", "cancelled"]


@dataclass(slots=True)
class SectionContext:
    section_id: str
    section_image: bytes | None = None
    image_path: str | None = None
    section_bbox: SectionBBox | None = None
    page_no: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    classification_result: str | None = None


@dataclass(slots=True)
class SectionItem:
    item_id: str
    item_type: str
    raw_content: str
    bbox: SectionBBox | None = None
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParserIssue:
    raw_line: str
    error_message: str


@dataclass(slots=True)
class ItemProcessResult:
    item: SectionItem
    parsed_content: Any | None = None
    description: str | None = None
    status: ItemStatus = "pending"
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StructuredNode:
    section_id: str
    section_type: str
    node_type: str
    children: list[dict[str, Any]] = field(default_factory=list)
    fields: dict[str, Any] = field(default_factory=dict)
    item_results: list[ItemProcessResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SectionPipelineReport:
    section_id: str
    section_type: str | None = None
    parser_issues: list[ParserIssue] = field(default_factory=list)
    item_results: list[ItemProcessResult] = field(default_factory=list)
    source_error: str | None = None
    fatal_error: str | None = None
