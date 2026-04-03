from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal
from urllib.parse import urlparse

from openai import AsyncOpenAI


class OpenAIStreamChunkSource:
    """Stream text chunks from OpenAI Responses API with compatibility fallback."""

    def __init__(
        self,
        *,
        model: str,
        input: str | list[dict[str, Any]] | None = None,
        messages: list[dict[str, Any]] | None = None,
        instructions: str | None = None,
        temperature: float | None = None,
        text_format: dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        client: AsyncOpenAI | None = None,
        api_mode: Literal["auto", "responses", "chat_completions"] = "auto",
        **extra_params: Any,
    ) -> None:
        if input is not None and messages is not None:
            raise ValueError("Pass either input or messages, not both.")
        if text_format is not None and response_format is not None:
            raise ValueError("Pass either text_format or response_format, not both.")

        normalized_input = input if input is not None else messages
        if normalized_input is None:
            raise ValueError("Either input or messages must be provided.")

        self._client = client or AsyncOpenAI()
        self._model = model
        self._input = normalized_input
        self._messages = messages
        self._instructions = instructions
        self._temperature = temperature
        self._text_format = text_format if text_format is not None else response_format
        self._api_mode = api_mode
        self._extra_params = extra_params

    async def stream(self) -> AsyncIterator[str]:
        mode = self._resolve_api_mode()
        if mode == "responses":
            async for text in self._stream_via_responses():
                yield text
            return

        async for text in self._stream_via_chat_completions():
            yield text

    async def _stream_via_responses(self) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "input": self._input,
            **self._extra_params,
        }
        if self._instructions is not None:
            payload["instructions"] = self._instructions
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if self._text_format is not None:
            payload["text"] = {"format": self._text_format}

        async with self._client.responses.stream(**payload) as stream:
            async for event in stream:
                text = self._extract_response_text(event)
                if text:
                    yield text

    async def _stream_via_chat_completions(self) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._coerce_messages(),
            "stream": True,
            **self._extra_params,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if self._text_format is not None:
            payload["response_format"] = self._text_format

        stream = await self._client.chat.completions.create(**payload)
        async for chunk in stream:
            text = self._extract_chat_text(chunk)
            if text:
                yield text

    def _coerce_messages(self) -> list[dict[str, Any]]:
        if self._messages is not None:
            return self._messages

        if isinstance(self._input, str):
            messages: list[dict[str, Any]] = []
            if self._instructions is not None:
                messages.append({"role": "system", "content": self._instructions})
            messages.append({"role": "user", "content": self._input})
            return messages

        messages = list(self._input)
        if self._instructions is not None:
            return [{"role": "system", "content": self._instructions}, *messages]
        return messages

    def _resolve_api_mode(self) -> Literal["responses", "chat_completions"]:
        if self._api_mode != "auto":
            return self._api_mode
        if self._is_official_openai_base_url():
            return "responses"
        return "chat_completions"

    def _is_official_openai_base_url(self) -> bool:
        base_url = getattr(self._client, "base_url", None)
        if base_url is None:
            return True

        parsed = urlparse(str(base_url))
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return True
        return hostname.endswith("openai.com")

    @staticmethod
    def _extract_response_text(event: Any) -> str:
        event_type = OpenAIStreamChunkSource._read_field(event, "type")
        if event_type != "response.output_text.delta":
            return ""
        delta = OpenAIStreamChunkSource._read_field(event, "delta")
        return str(delta or "")

    @staticmethod
    def _extract_chat_text(chunk: Any) -> str:
        choices = OpenAIStreamChunkSource._read_field(chunk, "choices")
        if not choices:
            return ""

        delta = OpenAIStreamChunkSource._read_field(choices[0], "delta")
        if delta is None:
            return ""

        content = OpenAIStreamChunkSource._read_field(delta, "content")
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                part_type = OpenAIStreamChunkSource._read_field(part, "type")
                if part_type == "text":
                    text = OpenAIStreamChunkSource._read_field(part, "text")
                    if text is not None:
                        parts.append(str(text))
                        continue

                nested_text = OpenAIStreamChunkSource._read_field(
                    OpenAIStreamChunkSource._read_field(part, "text"),
                    "value",
                )
                if nested_text is not None:
                    parts.append(str(nested_text))
            return "".join(parts)

        return ""

    @staticmethod
    def _read_field(value: Any, field: str) -> Any:
        if isinstance(value, dict):
            return value.get(field)
        return getattr(value, field, None)
