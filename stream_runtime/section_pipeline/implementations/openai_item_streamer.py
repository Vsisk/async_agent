from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, Literal
from urllib.parse import urlparse

try:
    from openai import AsyncOpenAI
    _OPENAI_SDK_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AsyncOpenAI = Any  # type: ignore[assignment]
    _OPENAI_SDK_AVAILABLE = False

from stream_runtime.section_pipeline.abstractions.models import SectionContext


MessageBuilder = Callable[[SectionContext, str], list[dict[str, Any]]]


class OpenAISectionItemStreamer:
    """Streams pure JSONL item text from an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        model: str,
        message_builder: MessageBuilder,
        client: AsyncOpenAI | None = None,
        temperature: float | None = None,
        api_mode: Literal["auto", "responses", "chat_completions"] = "auto",
        response_format: dict[str, Any] | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> None:
        if client is None and not _OPENAI_SDK_AVAILABLE:
            raise ModuleNotFoundError(
                "openai package is required to instantiate OpenAISectionItemStreamer."
            )
        self._client = client or AsyncOpenAI()
        self._model = model
        self._message_builder = message_builder
        self._temperature = temperature
        self._api_mode = api_mode
        self._response_format = response_format
        self._extra_params = extra_params or {}

    async def stream_items(
        self,
        section_context: SectionContext,
        *,
        section_type: str,
    ) -> AsyncIterator[str]:
        messages = self._message_builder(section_context, section_type)
        mode = self._resolve_api_mode()
        if mode == "responses":
            async for chunk in self._stream_via_responses(messages):
                yield chunk
            return

        async for chunk in self._stream_via_chat_completions(messages):
            yield chunk

    async def _stream_via_responses(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "input": messages,
            **self._extra_params,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if self._response_format is not None:
            payload["text"] = {"format": self._response_format}

        async with self._client.responses.stream(**payload) as stream:
            async for event in stream:
                text = self._extract_response_text(event)
                if text:
                    yield text

    async def _stream_via_chat_completions(
        self,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            **self._extra_params,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if self._response_format is not None:
            payload["response_format"] = self._response_format

        stream = await self._client.chat.completions.create(**payload)
        async for chunk in stream:
            text = self._extract_chat_text(chunk)
            if text:
                yield text

    def _resolve_api_mode(self) -> Literal["responses", "chat_completions"]:
        if self._api_mode != "auto":
            return self._api_mode

        base_url = getattr(self._client, "base_url", None)
        if base_url is None:
            return "responses"

        hostname = (urlparse(str(base_url)).hostname or "").lower()
        if not hostname or hostname.endswith("openai.com"):
            return "responses"
        return "chat_completions"

    @staticmethod
    def _extract_response_text(event: Any) -> str:
        event_type = OpenAISectionItemStreamer._read_field(event, "type")
        if event_type != "response.output_text.delta":
            return ""
        return str(OpenAISectionItemStreamer._read_field(event, "delta") or "")

    @staticmethod
    def _extract_chat_text(chunk: Any) -> str:
        choices = OpenAISectionItemStreamer._read_field(chunk, "choices")
        if not choices:
            return ""

        delta = OpenAISectionItemStreamer._read_field(choices[0], "delta")
        if delta is None:
            return ""

        content = OpenAISectionItemStreamer._read_field(delta, "content")
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                part_type = OpenAISectionItemStreamer._read_field(part, "type")
                if part_type == "text":
                    text = OpenAISectionItemStreamer._read_field(part, "text")
                    if isinstance(text, str):
                        parts.append(text)
                        continue
                    nested = OpenAISectionItemStreamer._read_field(text, "value")
                    if nested is not None:
                        parts.append(str(nested))
            return "".join(parts)
        return ""

    @staticmethod
    def _read_field(value: Any, field: str) -> Any:
        if isinstance(value, dict):
            return value.get(field)
        return getattr(value, field, None)
