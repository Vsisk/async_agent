from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class TaskOutcome:
    """Unified task execution outcome."""

    task_id: int
    input_object: Any
    success: bool
    result: Any | None = None
    error: BaseException | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


@dataclass(slots=True)
class ParseIssue:
    """Non-fatal parsing issue captured during incremental parsing."""

    raw_line: str
    error_message: str


@dataclass(slots=True)
class OrchestrationReport:
    """Report returned by orchestrator alongside aggregated result."""

    task_outcomes: list[TaskOutcome]
    parse_issues: list[ParseIssue] = field(default_factory=list)
    source_error: BaseException | None = None
    parser_flush_error: BaseException | None = None
