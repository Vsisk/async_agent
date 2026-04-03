from __future__ import annotations

from typing import Any, Protocol

from .models import ParseIssue


class IncrementalObjectParser(Protocol):
    """Consumes chunks incrementally and yields complete objects when available."""

    @property
    def issues(self) -> list[ParseIssue]:
        ...

    def feed(self, chunk: str) -> list[Any]:
        ...

    def flush(self) -> list[Any]:
        ...
