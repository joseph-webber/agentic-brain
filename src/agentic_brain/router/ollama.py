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

"""
Ollama provider implementation.
"""


import json
import logging
import shutil
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Callable

import aiohttp

from agentic_brain.exceptions import (
    APIError,
    LLMProviderError,
    ModelNotFoundError,
)
from agentic_brain.exceptions import (
    TimeoutError as AgenticTimeoutError,
)

from .config import Provider, Response, RouterConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def check_ollama_available(host: str, pool: Any | None = None) -> bool:
    """Check if Ollama is running (async).

    Args:
        host: Ollama API host URL
        pool: Optional HTTP pool to use

    Returns:
        True if Ollama is running
    """
    try:
        # Check if ollama command exists first
        if not shutil.which("ollama"):
            logger.debug("Ollama command not found in PATH")
            return False

        # Try pooled request first
        if pool:
            try:
                response = await pool.get(f"{host}/api/tags", timeout=2)
                return response.ok
            except Exception as e:
                logger.debug(f"Ollama pool check failed, falling back to direct: {e}")

        # Fall back to direct request
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{host}/api/tags",
                timeout=aiohttp.ClientTimeout(total=2),
            ) as response,
        ):
            return response.status == 200
    except Exception as e:
        logger.debug(f"Ollama availability check failed: {e}")
        return False


def check_ollama_sync(host: str) -> bool:
    """Sync check for Ollama availability.

    Args:
        host: Ollama API host URL

    Returns:
        True if Ollama is running
    """
    try:
        if not shutil.which("ollama"):
            logger.debug("Ollama command not found in PATH")
            return False

        import urllib.error
        import urllib.request

        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        logger.debug(f"Ollama availability check failed: {e}")
        return False


async def chat_ollama(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
    is_available_fn: Callable[[], Any],
    post_fn: Callable[..., Any],
    track_tokens_fn: Callable[[int, str], None],
) -> Response:
    """Chat via Ollama (async).

    Uses HTTP connection pool when available for better performance
    (keep-alive, connection reuse, retries).

    Args:
        message: User message
        system: Optional system prompt
        model: Model name
        temperature: Temperature for generation
        config: Router configuration
        is_available_fn: Async function to check Ollama availability
        post_fn: Async function for POST requests
        track_tokens_fn: Function to track token usage

    Returns:
        LLM response

    Raises:
        ModelNotFoundError: Model not installed
        AgenticTimeoutError: Request timed out
        LLMProviderError: Connection or response error
    """
    if not await is_available_fn():
        raise LLMProviderError(
            "ollama", model, Exception("Ollama is not running. Try: ollama serve")
        )

    logger.debug(f"Ollama chat: model={model}, temperature={temperature}")

    payload = {
        "model": model,
        "messages": [],
        "stream": False,
        "options": {"temperature": temperature},
    }

    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": message})

    url = f"{config.ollama_host}/api/chat"

    try:
        status, result = await post_fn(url, payload, timeout=config.ollama_timeout)

        if status == 404:
            raise ModelNotFoundError(model, "ollama")

        if status != 200:
            raise APIError(url, status, str(result), None)

        if not isinstance(result, dict):
            raise LLMProviderError(
                "ollama",
                model,
                Exception(f"Unexpected response type: {type(result)}"),
            )

        tokens_used = result.get("eval_count", 0)
        logger.info(
            f"LLM response received: provider={Provider.OLLAMA.value}, tokens={tokens_used}"
        )

        # Track token usage
        track_tokens_fn(tokens_used, Provider.OLLAMA.value)

        return Response(
            content=result["message"]["content"],
            model=model,
            provider=Provider.OLLAMA,
            tokens_used=tokens_used,
        )
    except aiohttp.ClientError as e:
        raise LLMProviderError("ollama", model, e)
    except TimeoutError:
        raise AgenticTimeoutError("Ollama chat", config.timeout, None)
    except (KeyError, TypeError) as e:
        raise LLMProviderError(
            "ollama", model, Exception(f"Invalid response from Ollama: {e}")
        )


async def stream_ollama(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
    is_available_fn: Callable[[], Any],
) -> AsyncGenerator[str, None]:
    """Stream from Ollama.

    Args:
        message: User message
        system: Optional system prompt
        model: Model name
        temperature: Temperature for generation
        config: Router configuration
        is_available_fn: Async function to check Ollama availability

    Yields:
        Response tokens as they arrive
    """
    if not await is_available_fn():
        raise LLMProviderError(
            "ollama", model, Exception("Ollama is not running. Try: ollama serve")
        )

    payload = {
        "model": model,
        "messages": [],
        "stream": True,
        "options": {"temperature": temperature},
    }

    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": message})

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{config.ollama_host}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response,
    ):
        async for line in response.content:
            if line:
                try:
                    data = json.loads(line.decode())
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                except json.JSONDecodeError:
                    continue


async def list_models_async(host: str, is_available_fn: Callable[[], Any]) -> list[str]:
    """List available Ollama models (async).

    Args:
        host: Ollama API host URL
        is_available_fn: Async function to check availability

    Returns:
        List of model names
    """
    if not await is_available_fn():
        return []

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{host}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response,
        ):
            if response.status != 200:
                return []
            result = await response.json()

        return [m["name"] for m in result.get("models", [])]
    except Exception as e:
        logger.debug(f"Failed to fetch Ollama models: {e}")
        return []


def list_models_sync(host: str, is_available: bool) -> list[str]:
    """List available Ollama models (sync).

    Args:
        host: Ollama API host URL
        is_available: Whether Ollama is available

    Returns:
        List of model names
    """
    if not is_available:
        return []

    try:
        import urllib.request

        req = urllib.request.Request(f"{host}/api/tags", method="GET")

        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())

        return [m["name"] for m in result.get("models", [])]

    except Exception as e:
        logger.debug(f"Failed to fetch Ollama models: {e}")
        return []
