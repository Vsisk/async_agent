from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI


class OpenAIStreamChunkSource:
    """OpenAI-compatible chunk source that normalizes stream events into text chunks."""

    def __init__(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
        client: AsyncOpenAI | None = None,
        **extra_params: Any,
    ) -> None:
        self._client = client or AsyncOpenAI()
        self._model = model
        self._messages = messages
        self._temperature = temperature
        self._response_format = response_format
        self._extra_params = extra_params

    async def stream(self) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._messages,
            "stream": True,
            **self._extra_params,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if self._response_format is not None:
            payload["response_format"] = self._response_format

        stream = await self._client.chat.completions.create(**payload)

        async for chunk in stream:
            text = self._extract_text(chunk)
            if text:
                yield text

    @staticmethod
    def _extract_text(chunk: Any) -> str:
        choices = getattr(chunk, "choices", None)
        if not choices:
            return ""

        delta = getattr(choices[0], "delta", None)
        if delta is None:
            return ""

        content = getattr(delta, "content", None)
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        # Some providers may return mixed content parts.
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif hasattr(part, "text"):
                    parts.append(str(getattr(part, "text")))
            return "".join(parts)

        return ""
