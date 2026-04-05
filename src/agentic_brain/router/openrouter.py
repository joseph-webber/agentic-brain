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
OpenRouter provider implementation.
"""


import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any, Callable

import aiohttp

from agentic_brain.exceptions import (
    APIError,
    LLMProviderError,
    RateLimitError,
)
from agentic_brain.exceptions import (
    TimeoutError as AgenticTimeoutError,
)

from .config import Provider, Response, RouterConfig

logger = logging.getLogger(__name__)


def get_api_key(config: RouterConfig) -> str | None:
    """Get OpenRouter API key from config or environment.

    Note: OpenRouter works without API key for free models.

    Args:
        config: Router configuration

    Returns:
        API key or None
    """
    return config.openrouter_key or os.environ.get("OPENROUTER_API_KEY")


async def chat_openrouter(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
    post_fn: Callable[..., Any],
    track_tokens_fn: Callable[[int, str], None],
) -> Response:
    """Chat via OpenRouter (async, free models available).

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
        APIError: API call failed
        RateLimitError: Rate limit exceeded
    """
    api_key = get_api_key(config)

    logger.debug(
        f"OpenRouter chat: model={model}, temperature={temperature}, "
        f"api_key={'configured' if api_key else 'not configured'}"
    )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        status, result = await post_fn(
            url, payload, headers, timeout=config.openrouter_timeout
        )

        if status == 429:
            raise RateLimitError(limit=10, window="minute", retry_after=60)

        if status != 200:
            raise APIError(url, status, str(result), None)

        if not isinstance(result, dict):
            raise LLMProviderError(
                "openrouter",
                model,
                Exception(f"Unexpected response type: {type(result)}"),
            )

        tokens_used = result.get("usage", {}).get("total_tokens", 0)
        logger.info(
            f"LLM response received: provider={Provider.OPENROUTER.value}, tokens={tokens_used}"
        )

        # Track token usage
        track_tokens_fn(tokens_used, Provider.OPENROUTER.value)

        choice = result["choices"][0]
        return Response(
            content=choice["message"]["content"],
            model=model,
            provider=Provider.OPENROUTER,
            tokens_used=tokens_used,
        )
    except aiohttp.ClientError as e:
        raise LLMProviderError("openrouter", model, e)
    except TimeoutError:
        raise AgenticTimeoutError("OpenRouter chat", config.timeout, None)
    except (KeyError, TypeError) as e:
        raise LLMProviderError(
            "openrouter",
            model,
            Exception(f"Invalid response from OpenRouter: {e}"),
        )


async def stream_openrouter(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
) -> AsyncGenerator[str, None]:
    """Stream from OpenRouter.

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

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response,
    ):
        async for line in response.content:
            line_str = line.decode().strip()
            if line_str.startswith("data: ") and line_str != "data: [DONE]":
                try:
                    data = json.loads(line_str[6:])
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
                except json.JSONDecodeError:
                    continue
