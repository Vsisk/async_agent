from __future__ import annotations

from typing import Any, Protocol

from .models import OrchestrationReport


class StreamOrchestrator(Protocol):
    """Coordinates source, parser, scheduler, executor and aggregator."""

    async def run(self) -> tuple[Any, OrchestrationReport]:
        ...
