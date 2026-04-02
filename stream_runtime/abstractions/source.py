from __future__ import annotations

from typing import AsyncIterator, Protocol


class StreamChunkSource(Protocol):
    """A source that asynchronously yields normalized text chunks."""

    def stream(self) -> AsyncIterator[str]:
        ...
