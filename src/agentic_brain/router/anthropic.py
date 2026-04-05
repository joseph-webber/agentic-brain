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
Anthropic provider implementation.
"""


import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any, Callable

import aiohttp

from agentic_brain.exceptions import (
    APIError,
    ConfigurationError,
    LLMProviderError,
    RateLimitError,
)
from agentic_brain.exceptions import (
    TimeoutError as AgenticTimeoutError,
)

from .config import Provider, Response, RouterConfig

logger = logging.getLogger(__name__)


def get_api_key(config: RouterConfig) -> str:
    """Get Anthropic API key from config or environment.

    Args:
        config: Router configuration

    Returns:
        API key

    Raises:
        ConfigurationError: API key not configured
    """
    api_key = config.anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "ANTHROPIC_API_KEY",
            "valid Anthropic API key from https://console.anthropic.com/account/keys",
        )
    return api_key


async def chat_anthropic(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
    post_fn: Callable[..., Any],
    track_tokens_fn: Callable[[int, str], None],
) -> Response:
    """Chat via Anthropic (async).

    Uses HTTP connection pool when available for better performance.

    Args:
        message: User message
        system: Optional system prompt
        model: Model name
        temperature: Temperature for generation
        config: Router configuration
        post_fn: Async function for POST requests
        track_tokens_fn: Function to track token usage

    Returns:
        LLM response

    Raises:
        ConfigurationError: API key not configured
        APIError: API call failed
    """
    api_key = get_api_key(config)

    logger.debug(f"Anthropic chat: model={model}, temperature={temperature}")

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": message}],
        "temperature": temperature,
    }

    if system:
        payload["system"] = system

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    try:
        status, result = await post_fn(
            url, payload, headers, timeout=config.anthropic_timeout
        )

        if status == 429:
            raise RateLimitError(limit=50000, window="minute", retry_after=60)

        if status != 200:
            raise APIError(url, status, str(result), None)

        if not isinstance(result, dict):
            raise LLMProviderError(
                "anthropic",
                model,
                Exception(f"Unexpected response type: {type(result)}"),
            )

        tokens_used = result.get("usage", {}).get("input_tokens", 0) + result.get(
            "usage", {}
        ).get("output_tokens", 0)
        logger.info(
            f"LLM response received: provider={Provider.ANTHROPIC.value}, tokens={tokens_used}"
        )

        # Track token usage
        track_tokens_fn(tokens_used, Provider.ANTHROPIC.value)

        return Response(
            content=result["content"][0]["text"],
            model=model,
            provider=Provider.ANTHROPIC,
            tokens_used=tokens_used,
        )
    except aiohttp.ClientError as e:
        raise LLMProviderError("anthropic", model, e)
    except TimeoutError:
        raise AgenticTimeoutError("Anthropic chat", config.timeout, None)
    except (KeyError, TypeError) as e:
        raise LLMProviderError(
            "anthropic",
            model,
            Exception(f"Invalid response from Anthropic: {e}"),
        )


async def stream_anthropic(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
) -> AsyncGenerator[str, None]:
    """Stream from Anthropic.

    Args:
        message: User message
        system: Optional system prompt
        model: Model name
        temperature: Temperature for generation
        config: Router configuration

    Yields:
        Response tokens as they arrive
    """
    api_key = get_api_key(config)

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": message}],
        "temperature": temperature,
        "stream": True,
    }

    if system:
        payload["system"] = system

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response,
    ):
        async for line in response.content:
            line_str = line.decode().strip()
            if line_str.startswith("data: "):
                try:
                    data = json.loads(line_str[6:])
                    if data.get("type") == "content_block_delta":
                        delta = data.get("delta", {})
                        if "text" in delta:
                            yield delta["text"]
                except json.JSONDecodeError:
                    continue
