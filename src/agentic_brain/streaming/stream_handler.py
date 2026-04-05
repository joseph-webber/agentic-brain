# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

"""Streaming handler and provider adapters for Agentic Brain.

This module owns the streaming implementation used by the API, WebSocket layer,
and tests. It adds chunked response decoding so provider payloads can arrive in
partial TCP frames without breaking JSON parsing.
"""

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class StreamProvider(StrEnum):
    """Supported streaming providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class StreamToken:
    """A single token emitted by the streaming pipeline."""

    token: str
    finish_reason: str | None = None
    is_start: bool = False
    is_end: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "finish_reason": self.finish_reason,
            "is_start": self.is_start,
            "is_end": self.is_end,
            "metadata": self.metadata,
        }

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_dict())}\n\n"


async def iter_text_chunks(
    chunks: AsyncIterable[bytes | str],
) -> AsyncIterator[str]:
    """Normalize an async chunk source to text."""

    async for chunk in chunks:
        if chunk is None:
            continue
        if isinstance(chunk, bytes):
            yield chunk.decode("utf-8")
        else:
            yield str(chunk)


async def iter_chunked_lines(
    chunks: AsyncIterable[bytes | str],
) -> AsyncIterator[str]:
    """Yield newline-delimited text lines from arbitrarily chunked input."""

    buffer = ""
    async for text in iter_text_chunks(chunks):
        buffer += text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                yield line
    if buffer.strip():
        yield buffer.rstrip("\r")


async def iter_sse_payloads(
    chunks: AsyncIterable[bytes | str],
) -> AsyncIterator[str]:
    """Yield SSE `data:` payloads from chunked input."""

    buffer = ""
    event_lines: list[str] = []

    async for text in iter_text_chunks(chunks):
        buffer += text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if not line:
                if event_lines:
                    yield "\n".join(event_lines)
                    event_lines = []
                continue
            if line.startswith(":"):
                continue
            if line == "[DONE]":
                if event_lines:
                    yield "\n".join(event_lines)
                    event_lines = []
                yield "[DONE]"
                continue
            if line.startswith("data:"):
                payload = line[5:].lstrip()
                if payload == "[DONE]":
                    if event_lines:
                        yield "\n".join(event_lines)
                        event_lines = []
                    yield "[DONE]"
                    continue
                event_lines.append(payload)
                continue
            event_lines.append(line)

    if event_lines:
        yield "\n".join(event_lines)
    elif buffer.strip():
        tail = buffer.strip()
        if tail == "[DONE]":
            yield "[DONE]"
        else:
            yield tail


class StreamingResponse:
    """Unified streaming wrapper for provider responses and API consumers."""

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "llama3.1:8b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self.provider = StreamProvider(provider)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or "You are a helpful assistant."
        self.api_key = api_key
        self.api_base = api_base

        if self.provider == StreamProvider.OLLAMA:
            self.api_base = api_base or os.getenv(
                "OLLAMA_API_BASE", "http://localhost:11434"
            )
        elif self.provider == StreamProvider.OPENAI:
            self.api_base = api_base or "https://api.openai.com/v1"
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY required for OpenAI provider")
        elif self.provider == StreamProvider.ANTHROPIC:
            self.api_base = api_base or "https://api.anthropic.com/v1"
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY required for Anthropic provider")

    def _make_messages(
        self, message: str, history: list[dict[str, str]] | None
    ) -> list[dict[str, str]]:
        messages = list(history or [])
        messages.append({"role": "user", "content": message})
        return messages

    async def stream(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[StreamToken]:
        if self.provider == StreamProvider.OLLAMA:
            async for token in self._stream_ollama(message, conversation_history):
                yield token
        elif self.provider == StreamProvider.OPENAI:
            async for token in self._stream_openai(message, conversation_history):
                yield token
        else:
            async for token in self._stream_anthropic(message, conversation_history):
                yield token

    async def _stream_ollama(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[StreamToken]:
        url = f"{self.api_base}/api/chat"
        payload = {
            "model": self.model,
            "messages": self._make_messages(message, conversation_history),
            "stream": True,
            "temperature": self.temperature,
            "num_predict": self.max_tokens,
        }
        start_time = time.time()
        total_tokens = 0

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(
                        total=300, sock_read=30, sock_connect=10
                    ),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise RuntimeError(f"Ollama error {resp.status}: {error_text}")

                    is_first = True
                    async for line in iter_chunked_lines(resp.content):
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            logger.debug("Skipping malformed Ollama chunk: %s", line)
                            continue

                        token_text = data.get("message", {}).get("content", "")
                        done = bool(data.get("done"))
                        if token_text:
                            total_tokens += 1
                            yield StreamToken(
                                token=token_text,
                                is_start=is_first,
                                is_end=done,
                                finish_reason="stop" if done else None,
                                metadata={"provider": "ollama", "model": self.model},
                            )
                            is_first = False
                        elif done:
                            yield StreamToken(
                                token="",
                                is_start=is_first,
                                is_end=True,
                                finish_reason="stop",
                                metadata={"provider": "ollama", "model": self.model},
                            )
                            is_first = False
                    logger.info(
                        "Ollama stream complete: %s tokens in %.2fs",
                        total_tokens,
                        time.time() - start_time,
                    )
        except TimeoutError:
            yield StreamToken(
                token="",
                finish_reason="error",
                is_end=True,
                metadata={"error": "timeout"},
            )
        except Exception as exc:
            yield StreamToken(
                token="",
                finish_reason="error",
                is_end=True,
                metadata={"error": str(exc)},
            )

    async def _stream_openai(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[StreamToken]:
        url = f"{self.api_base}/chat/completions"
        messages = self._make_messages(message, conversation_history)
        if self.system_prompt:
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        attempt = 0
        max_retries = 3
        while attempt < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=None),
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            raise RuntimeError(
                                f"OpenAI error {resp.status}: {error_text}"
                            )

                        is_first = True
                        async for payload_text in iter_sse_payloads(resp.content):
                            if payload_text == "[DONE]":
                                yield StreamToken(
                                    token="",
                                    is_end=True,
                                    finish_reason="stop",
                                    metadata={
                                        "provider": "openai",
                                        "model": self.model,
                                    },
                                )
                                return

                            data = json.loads(payload_text)
                            choices = data.get("choices", [])
                            if not choices:
                                continue
                            choice = choices[0]
                            delta = choice.get("delta", {})
                            token_text = delta.get("content", "")
                            finish_reason = choice.get("finish_reason")
                            if token_text or finish_reason is not None:
                                yield StreamToken(
                                    token=token_text,
                                    is_start=is_first,
                                    is_end=finish_reason is not None,
                                    finish_reason=finish_reason,
                                    metadata={
                                        "provider": "openai",
                                        "model": self.model,
                                    },
                                )
                                is_first = False
                        return
            except (TimeoutError, aiohttp.ClientError) as exc:
                attempt += 1
                if attempt >= max_retries:
                    yield StreamToken(
                        token="",
                        finish_reason="error",
                        is_end=True,
                        metadata={
                            "error": (
                                str(exc)
                                if not isinstance(exc, asyncio.TimeoutError)
                                else "timeout"
                            )
                        },
                    )
                    return
            except Exception as exc:
                yield StreamToken(
                    token="",
                    finish_reason="error",
                    is_end=True,
                    metadata={"error": str(exc)},
                )
                return

    async def _stream_anthropic(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[StreamToken]:
        url = f"{self.api_base}/messages"
        messages = self._make_messages(message, conversation_history)
        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.system_prompt,
            "messages": messages,
            "stream": True,
        }

        attempt = 0
        max_retries = 3
        while attempt < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(
                            total=300, sock_read=30, sock_connect=10
                        ),
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            raise RuntimeError(
                                f"Anthropic error {resp.status}: {error_text}"
                            )

                        is_first = True
                        async for payload_text in iter_sse_payloads(resp.content):
                            if payload_text == "[DONE]":
                                break
                            chunk = json.loads(payload_text)
                            event_type = chunk.get("type", "")
                            if event_type == "content_block_delta":
                                text = chunk.get("delta", {}).get("text", "")
                                if text:
                                    yield StreamToken(
                                        token=text,
                                        is_start=is_first,
                                        is_end=False,
                                        metadata={
                                            "provider": "anthropic",
                                            "model": self.model,
                                        },
                                    )
                                    is_first = False
                            elif event_type == "message_stop":
                                yield StreamToken(
                                    token="",
                                    is_end=True,
                                    finish_reason="stop",
                                    metadata={
                                        "provider": "anthropic",
                                        "model": self.model,
                                    },
                                )
                                return
                        yield StreamToken(
                            token="",
                            is_end=True,
                            finish_reason="stop",
                            metadata={"provider": "anthropic", "model": self.model},
                        )
                        return
            except (TimeoutError, aiohttp.ClientError) as exc:
                attempt += 1
                if attempt >= max_retries:
                    yield StreamToken(
                        token="",
                        finish_reason="error",
                        is_end=True,
                        metadata={
                            "error": (
                                str(exc)
                                if not isinstance(exc, asyncio.TimeoutError)
                                else "timeout"
                            )
                        },
                    )
                    return
            except Exception as exc:
                yield StreamToken(
                    token="",
                    finish_reason="error",
                    is_end=True,
                    metadata={"error": str(exc)},
                )
                return

    async def stream_sse(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]:
        async for token in self.stream(message, conversation_history):
            yield token.to_sse()

    async def stream_websocket(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]:
        async for token in self.stream(message, conversation_history):
            yield json.dumps(token.to_dict())

    def as_fastapi_response(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
        *,
        headers: dict[str, str] | None = None,
        status_code: int = 200,
    ):
        from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

        response_headers = {
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
        }
        if headers:
            response_headers.update(headers)

        return FastAPIStreamingResponse(
            self.stream_sse(message, conversation_history),
            media_type="text/event-stream",
            status_code=status_code,
            headers=response_headers,
        )


__all__ = [
    "StreamProvider",
    "StreamToken",
    "StreamingResponse",
    "iter_chunked_lines",
    "iter_sse_payloads",
    "iter_text_chunks",
]
