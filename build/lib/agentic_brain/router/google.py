# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

# SPDX-License-Identifier: GPL-3.0-or-later
"""
Google AI Studio provider implementation - Gemini models FREE.
"""

import asyncio
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
    """Get Google API key from config or environment.

    Args:
        config: Router configuration

    Returns:
        API key

    Raises:
        ConfigurationError: API key not configured
    """
    api_key = config.google_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "GOOGLE_API_KEY",
            "valid Google API key from https://aistudio.google.com/apikey",
            "AIza...",
        )
    return api_key


async def chat_google(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
    post_fn: Callable[..., Any],
    track_tokens_fn: Callable[[int, str], None],
) -> Response:
    """Chat via Google Gemini (async).

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

    logger.debug(f"Google chat: model={model}, temperature={temperature}")

    messages = []
    if system:
        messages.append({"role": "user", "content": system})
    messages.append({"role": "user", "content": message})

    # Google Gemini API v1beta format
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": message}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
        },
    }

    # Prepare system instruction if provided
    if system:
        payload["systemInstruction"] = {
            "role": "user",
            "parts": [{"text": system}],
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
    }

    # Add API key as query parameter for Gemini API
    url_with_key = f"{url}?key={api_key}"

    try:
        status, result = await post_fn(
            url_with_key, payload, headers, timeout=config.google_timeout
        )

        if status == 429:
            raise RateLimitError(limit=60, window="minute", retry_after=60)

        if status != 200:
            raise APIError(url, status, str(result), None)

        if not isinstance(result, dict):
            raise LLMProviderError(
                "google",
                model,
                Exception(f"Unexpected response type: {type(result)}"),
            )

        # Google API doesn't return token count in free tier, so estimate
        tokens_used = 0
        logger.info(
            f"LLM response received: provider={Provider.GOOGLE.value}, tokens={tokens_used}"
        )

        # Track token usage
        track_tokens_fn(tokens_used, Provider.GOOGLE.value)

        # Parse Google Gemini response format
        candidates = result.get("candidates", [])
        if not candidates:
            raise LLMProviderError(
                "google",
                model,
                Exception("No candidates in response"),
            )

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise LLMProviderError(
                "google",
                model,
                Exception("No parts in response content"),
            )

        text_content = parts[0].get("text", "")

        return Response(
            content=text_content,
            model=model,
            provider=Provider.GOOGLE,
            tokens_used=tokens_used,
            finish_reason=candidates[0].get("finishReason", "STOP"),
        )
    except aiohttp.ClientError as e:
        raise LLMProviderError("google", model, e)
    except asyncio.TimeoutError:
        raise AgenticTimeoutError("Google chat", config.google_timeout, None)
    except (KeyError, TypeError) as e:
        raise LLMProviderError(
            "google", model, Exception(f"Invalid response from Google: {e}")
        )


async def stream_google(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
) -> AsyncGenerator[str, None]:
    """Stream from Google Gemini.

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
        "contents": [
            {
                "role": "user",
                "parts": [{"text": message}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
        },
    }

    # Prepare system instruction if provided
    if system:
        payload["systemInstruction"] = {
            "role": "user",
            "parts": [{"text": system}],
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
    url_with_key = f"{url}?key={api_key}"

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            url_with_key,
            json=payload,
            headers={
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=config.google_timeout),
        ) as response,
    ):
        async for line in response.content:
            line_str = line.decode().strip()
            if line_str:
                try:
                    data = json.loads(line_str)
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            yield parts[0]["text"]
                except json.JSONDecodeError:
                    continue
