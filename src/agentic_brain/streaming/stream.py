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

"""
Core streaming response implementation.

Supports:
- Ollama (local)
- OpenAI (cloud)
- Anthropic (cloud)

Token-by-token streaming for instant UX.
"""

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class StreamProvider(StrEnum):
    """Supported streaming providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class StreamToken:
    """A single token from the stream."""

    token: str
    """The actual token text"""

    finish_reason: Optional[str] = None
    """Reason stream ended: 'length', 'stop', 'error', or None if continuing"""

    is_start: bool = False
    """True for first token (helps frontend detect start)"""

    is_end: bool = False
    """True for last token (helps frontend detect end)"""

    metadata: dict[str, Any] = None
    """Additional metadata (model, timing, etc)"""

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "token": self.token,
            "finish_reason": self.finish_reason,
            "is_start": self.is_start,
            "is_end": self.is_end,
            "metadata": self.metadata,
        }

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format.

        Format:
            data: {"token": "hello", "is_start": false}\n\n
        """
        return f"data: {json.dumps(self.to_dict())}\n\n"


class StreamingResponse:
    """
    Unified streaming interface for multiple LLM providers.

    Makes responses feel instant with token-by-token streaming.

    Example:
        streamer = StreamingResponse(
            provider="ollama",
            model="llama3.1:8b",
            temperature=0.7,
        )
        async for token in streamer.stream("What is AI?"):
            print(token.token, end="", flush=True)
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "llama3.1:8b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """Initialize streaming response.

        Args:
            provider: "ollama", "openai", or "anthropic"
            model: Model name (e.g., "llama3.1:8b", "gpt-4", "claude-3-sonnet")
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            system_prompt: System message for the model
            api_key: API key for cloud providers (optional, uses env var)
            api_base: Custom API base URL (optional)
        """
        self.provider = StreamProvider(provider)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or "You are a helpful assistant."
        self.api_key = api_key
        self.api_base = api_base

        # Set up provider-specific defaults
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

    async def stream(
        self,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> AsyncIterator[StreamToken]:
        """
        Stream tokens for a single message.

        Args:
            message: User message
            conversation_history: Previous messages for context

        Yields:
            StreamToken: Individual tokens as they arrive

        Example:
            async for token in streamer.stream("Hello"):
                print(token.token, end="", flush=True)
        """
        msg_preview = message[:50] + "..." if len(message) > 50 else message
        logger.debug(
            f"Starting {self.provider.value} stream for message: {msg_preview}"
        )

        if self.provider == StreamProvider.OLLAMA:
            async for token in self._stream_ollama(message, conversation_history):
                yield token
        elif self.provider == StreamProvider.OPENAI:
            async for token in self._stream_openai(message, conversation_history):
                yield token
        elif self.provider == StreamProvider.ANTHROPIC:
            async for token in self._stream_anthropic(message, conversation_history):
                yield token

    async def _stream_ollama(
        self,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> AsyncIterator[StreamToken]:
        """Stream from Ollama (local)."""
        url = f"{self.api_base}/api/chat"

        messages = conversation_history or []
        messages.append({"role": "user", "content": message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
            "num_predict": self.max_tokens,
        }

        start_time = time.time()
        total_tokens = 0

        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(
                        total=300, sock_read=30, sock_connect=10
                    ),
                )

                async with resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Failed to connect to ollama: HTTP {resp.status}")
                        raise Exception(f"Ollama error {resp.status}: {error_text}")

                    logger.debug("Connected to ollama API")
                    is_first = True
                    async for line in resp.content:
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                            token_text = data.get("message", {}).get("content", "")

                            if token_text:
                                logger.debug(f"Received token: {token_text[:20]}...")
                                total_tokens += 1
                                yield StreamToken(
                                    token=token_text,
                                    is_start=is_first,
                                    is_end=data.get("done", False),
                                    finish_reason="stop" if data.get("done") else None,
                                    metadata={
                                        "provider": "ollama",
                                        "model": self.model,
                                    },
                                )
                                is_first = False
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse ollama response: {str(e)}")
                            continue

                    duration = time.time() - start_time
                    logger.info(
                        f"Stream complete: {total_tokens} tokens in {duration:.2f}s"
                    )
        except TimeoutError:
            logger.error("Stream timeout after 300s")
            yield StreamToken(
                token="", finish_reason="error", metadata={"error": "timeout"}
            )
        except Exception as e:
            logger.error(f"Failed to connect to ollama: {str(e)}")
            yield StreamToken(
                token="", finish_reason="error", metadata={"error": str(e)}
            )

    async def _stream_openai(
        self,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> AsyncIterator[StreamToken]:
        """Stream from OpenAI API."""
        url = f"{self.api_base}/chat/completions"

        messages = conversation_history or []
        if self.system_prompt:
            messages = [{"role": "system", "content": self.system_prompt}] + messages
        messages.append({"role": "user", "content": message})

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

        start_time = time.time()
        total_tokens = 0
        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=None),
                    ) as resp:
                        elapsed = time.time() - start_time
                        if elapsed > 10:
                            logger.warning(f"Slow response from openai: {elapsed:.2f}s")

                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(
                                f"Failed to connect to openai: HTTP {resp.status}"
                            )
                            raise Exception(f"OpenAI error {resp.status}: {error_text}")

                        logger.debug("Connected to openai API")
                        is_first = True
                        async for line in resp.content:
                            line = line.decode("utf-8").strip()
                            if not line or line == "data: [DONE]":
                                continue

                            if line.startswith("data: "):
                                line = line[6:]

                            try:
                                data = json.loads(line)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    token_text = delta.get("content", "")
                                    finish_reason = choices[0].get("finish_reason")

                                    if token_text or finish_reason:
                                        if token_text:
                                            logger.debug(
                                                f"Received token: {token_text[:20]}..."
                                            )
                                            total_tokens += 1
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
                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Failed to parse openai response: {str(e)}"
                                )
                                continue

                        duration = time.time() - start_time
                        logger.info(
                            f"Stream complete: {total_tokens} tokens in {duration:.2f}s"
                        )
                        break
            except (TimeoutError, aiohttp.ClientError) as e:
                attempt += 1
                if attempt < max_retries:
                    logger.warning(
                        f"Retrying openai stream, attempt {attempt}/{max_retries}"
                    )
                else:
                    if isinstance(e, asyncio.TimeoutError):
                        logger.error("Stream timeout after 300s")
                    else:
                        logger.error(f"Failed to connect to openai: {str(e)}")
                    yield StreamToken(
                        token="",
                        finish_reason="error",
                        metadata={
                            "error": (
                                str(e)
                                if not isinstance(e, asyncio.TimeoutError)
                                else "timeout"
                            )
                        },
                    )
                    break
            except Exception as e:
                logger.error(f"Failed to connect to openai: {str(e)}")
                yield StreamToken(
                    token="", finish_reason="error", metadata={"error": str(e)}
                )
                break

    async def _stream_anthropic(
        self,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> AsyncIterator[StreamToken]:
        """Stream from Anthropic Claude API."""
        url = f"{self.api_base}/messages"

        messages = conversation_history or []
        messages.append({"role": "user", "content": message})

        headers = {
            "x-api-key": self.api_key,
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

        start_time = time.time()
        total_tokens = 0
        max_retries = 3
        attempt = 0

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
                        elapsed = time.time() - start_time
                        if elapsed > 10:
                            logger.warning(
                                f"Slow response from anthropic: {elapsed:.2f}s"
                            )

                        if resp.status != 200:
                            logger.error(
                                f"Failed to connect to anthropic: HTTP {resp.status}"
                            )

                        logger.debug("Connected to anthropic API")
                        is_first = True
                        async for line in resp.content:
                            line = line.decode("utf-8").strip()
                            if not line or not line.startswith("data:"):
                                continue

                            data = line[5:].strip()
                            if data == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data)
                                event_type = chunk.get("type", "")

                                if event_type == "content_block_delta":
                                    delta = chunk.get("delta", {})
                                    text = delta.get("text", "")
                                    if text:
                                        logger.debug(f"Received token: {text[:20]}...")
                                        total_tokens += 1
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
                                        is_start=False,
                                        is_end=True,
                                        finish_reason="stop",
                                        metadata={
                                            "provider": "anthropic",
                                            "model": self.model,
                                        },
                                    )
                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Failed to parse anthropic response: {str(e)}"
                                )
                                continue

                        duration = time.time() - start_time
                        logger.info(
                            f"Stream complete: {total_tokens} tokens in {duration:.2f}s"
                        )
                        break
            except (TimeoutError, aiohttp.ClientError) as e:
                attempt += 1
                if attempt < max_retries:
                    logger.warning(
                        f"Retrying anthropic stream, attempt {attempt}/{max_retries}"
                    )
                else:
                    if isinstance(e, asyncio.TimeoutError):
                        logger.error("Stream timeout after 300s")
                    else:
                        logger.error(f"Failed to connect to anthropic: {str(e)}")
                    yield StreamToken(
                        token="",
                        finish_reason="error",
                        metadata={
                            "error": (
                                str(e)
                                if not isinstance(e, asyncio.TimeoutError)
                                else "timeout"
                            )
                        },
                    )
                    break
            except Exception as e:
                logger.error(f"Failed to connect to anthropic: {str(e)}")
                yield StreamToken(
                    token="", finish_reason="error", metadata={"error": str(e)}
                )
                break

    async def stream_sse(
        self,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream as Server-Sent Events (SSE).

        Use with FastAPI:
            from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

            @app.get("/chat/stream")
            async def stream_chat(message: str):
                streamer = StreamingResponse(provider="ollama")
                return FastAPIStreamingResponse(
                    streamer.stream_sse(message),
                    media_type="text/event-stream"
                )

        Args:
            message: User message
            conversation_history: Previous messages

        Yields:
            str: SSE formatted strings
        """
        try:
            async for token in self.stream(message, conversation_history):
                yield token.to_sse()
        except Exception as e:
            logger.error(f"Error in SSE stream: {str(e)}")
            error_token = StreamToken(
                token="", finish_reason="error", metadata={"error": str(e)}
            )
            yield error_token.to_sse()

    async def stream_websocket(
        self,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream for WebSocket consumption.

        Use with FastAPI:
            @app.websocket("/ws/chat")
            async def websocket_chat(websocket: WebSocket):
                await websocket.accept()
                streamer = StreamingResponse(provider="ollama")
                try:
                    async for token in streamer.stream_websocket(message):
                        await websocket.send_text(token)
                finally:
                    await websocket.close()

        Args:
            message: User message
            conversation_history: Previous messages

        Yields:
            str: JSON formatted token strings
        """
        try:
            async for token in self.stream(message, conversation_history):
                yield json.dumps(token.to_dict())
        except Exception as e:
            logger.error(f"Error in WebSocket stream: {str(e)}")
            error_token = StreamToken(
                token="", finish_reason="error", metadata={"error": str(e)}
            )
            yield json.dumps(error_token.to_dict())
