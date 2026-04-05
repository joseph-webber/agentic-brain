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
OpenAI provider implementation.
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
    """Get OpenAI API key from config or environment.

    Args:
        config: Router configuration

    Returns:
        API key

    Raises:
        ConfigurationError: API key not configured
    """
    api_key = config.openai_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY",
            "valid OpenAI API key from https://platform.openai.com/account/api-keys",
            "sk-...",
        )
    return api_key


async def chat_openai(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
    post_fn: Callable[..., Any],
    track_tokens_fn: Callable[[int, str], None],
) -> Response:
    """Chat via OpenAI (async).

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
        RateLimitError: Rate limit exceeded
        APIError: API call failed
    """
    api_key = get_api_key(config)

    logger.debug(f"OpenAI chat: model={model}, temperature={temperature}")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        status, result = await post_fn(
            url, payload, headers, timeout=config.openai_timeout
        )

        if status == 429:
            raise RateLimitError(limit=3500, window="minute", retry_after=60)

        if status != 200:
            raise APIError(url, status, str(result), None)

        if not isinstance(result, dict):
            raise LLMProviderError(
                "openai",
                model,
                Exception(f"Unexpected response type: {type(result)}"),
            )

        tokens_used = result.get("usage", {}).get("total_tokens", 0)
        logger.info(
            f"LLM response received: provider={Provider.OPENAI.value}, tokens={tokens_used}"
        )

        # Track token usage
        track_tokens_fn(tokens_used, Provider.OPENAI.value)

        choice = result["choices"][0]
        return Response(
            content=choice["message"]["content"],
            model=model,
            provider=Provider.OPENAI,
            tokens_used=tokens_used,
            finish_reason=choice.get("finish_reason", "stop"),
        )
    except aiohttp.ClientError as e:
        raise LLMProviderError("openai", model, e)
    except TimeoutError:
        raise AgenticTimeoutError("OpenAI chat", config.timeout, None)
    except (KeyError, TypeError) as e:
        raise LLMProviderError(
            "openai", model, Exception(f"Invalid response from OpenAI: {e}")
        )


async def stream_openai(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
) -> AsyncGenerator[str, None]:
    """Stream from OpenAI.

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

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
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
