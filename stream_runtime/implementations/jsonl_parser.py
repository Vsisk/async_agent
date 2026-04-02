from __future__ import annotations

import json
from typing import Any

from stream_runtime.abstractions.models import ParseIssue


class JsonlIncrementalParser:
    """Incrementally parse JSONL content from arbitrary chunk boundaries."""

    def __init__(self) -> None:
        self._buffer = ""
        self._issues: list[ParseIssue] = []

    @property
    def issues(self) -> list[ParseIssue]:
        return self._issues

    def feed(self, chunk: str) -> list[Any]:
        self._buffer += chunk
        return self._drain_lines(include_tail=False)

    def flush(self) -> list[Any]:
        return self._drain_lines(include_tail=True)

    def _drain_lines(self, *, include_tail: bool) -> list[Any]:
        outputs: list[Any] = []

        while True:
            newline_idx = self._buffer.find("\n")
            if newline_idx < 0:
                break
            line = self._buffer[:newline_idx]
            self._buffer = self._buffer[newline_idx + 1 :]
            parsed = self._parse_line(line)
            if parsed is not None:
                outputs.append(parsed)

        if include_tail and self._buffer:
            line = self._buffer
            self._buffer = ""
            parsed = self._parse_line(line)
            if parsed is not None:
                outputs.append(parsed)

        return outputs

    def _parse_line(self, raw_line: str) -> Any | None:
        candidate = raw_line.strip()
        if not candidate:
            return None

        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            self._issues.append(ParseIssue(raw_line=raw_line, error_message=str(exc)))
            return None
