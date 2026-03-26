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
Azure OpenAI provider implementation.
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


def get_azure_config(
    config: RouterConfig, model: str | None = None
) -> tuple[str, str, str, str]:
    """Get Azure OpenAI configuration from config or environment.

    Args:
        config: Router configuration
        model: Optional deployment name override (uses Azure deployment name)

    Returns:
        Tuple of (api_key, endpoint, deployment, api_version)

    Raises:
        ConfigurationError: Required configuration missing
    """
    api_key = config.azure_openai_key or os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = config.azure_openai_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment = (
        model
        or config.azure_openai_deployment
        or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    )
    api_version = (
        config.azure_openai_api_version
        or os.environ.get("AZURE_OPENAI_API_VERSION")
        or "2024-02-15-preview"
    )

    if not api_key:
        raise ConfigurationError(
            "AZURE_OPENAI_API_KEY",
            "Azure OpenAI API key",
            "your-azure-openai-key",
        )
    if not endpoint:
        raise ConfigurationError(
            "AZURE_OPENAI_ENDPOINT",
            "Azure OpenAI endpoint (https://<resource>.openai.azure.com)",
            "https://my-resource.openai.azure.com",
        )
    if not deployment:
        raise ConfigurationError(
            "AZURE_OPENAI_DEPLOYMENT",
            "Azure OpenAI deployment name",
            "gpt-4o",
        )

    return api_key, endpoint.rstrip("/"), deployment, api_version


async def chat_azure_openai(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
    post_fn: Callable[..., Any],
    track_tokens_fn: Callable[[int, str], None],
) -> Response:
    """Chat via Azure OpenAI (async).

    Uses HTTP connection pool when available for better performance.

    Args:
        message: User message
        system: Optional system prompt
        model: Deployment name (Azure uses deployments)
        temperature: Temperature for generation
        config: Router configuration
        post_fn: Async function for POST requests
        track_tokens_fn: Function to track token usage

    Returns:
        LLM response

    Raises:
        ConfigurationError: API key or endpoint not configured
        RateLimitError: Rate limit exceeded
        APIError: API call failed
    """
    api_key, endpoint, deployment, api_version = get_azure_config(config, model)

    logger.debug(
        "Azure OpenAI chat: deployment=%s, temperature=%s, api_version=%s",
        deployment,
        temperature,
        api_version,
    )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    payload = {
        "messages": messages,
        "temperature": temperature,
    }

    url = (
        f"{endpoint}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={api_version}"
    )
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    try:
        status, result = await post_fn(
            url, payload, headers, timeout=config.azure_openai_timeout
        )

        if status == 429:
            raise RateLimitError(limit=3500, window="minute", retry_after=60)

        if status != 200:
            raise APIError(url, status, str(result), None)

        if not isinstance(result, dict):
            raise LLMProviderError(
                "azure_openai",
                deployment,
                Exception(f"Unexpected response type: {type(result)}"),
            )

        tokens_used = result.get("usage", {}).get("total_tokens", 0)
        logger.info(
            "LLM response received: provider=%s, tokens=%s",
            Provider.AZURE_OPENAI.value,
            tokens_used,
        )

        # Track token usage
        track_tokens_fn(tokens_used, Provider.AZURE_OPENAI.value)

        choice = result["choices"][0]
        return Response(
            content=choice["message"]["content"],
            model=deployment,
            provider=Provider.AZURE_OPENAI,
            tokens_used=tokens_used,
            finish_reason=choice.get("finish_reason", "stop"),
        )
    except aiohttp.ClientError as e:
        raise LLMProviderError("azure_openai", deployment, e)
    except asyncio.TimeoutError:
        raise AgenticTimeoutError(
            "Azure OpenAI chat", config.azure_openai_timeout, None
        )
    except (KeyError, TypeError) as e:
        raise LLMProviderError(
            "azure_openai", deployment, Exception(f"Invalid response from Azure: {e}")
        )


async def stream_azure_openai(
    message: str,
    system: str | None,
    model: str,
    temperature: float,
    config: RouterConfig,
) -> AsyncGenerator[str, None]:
    """Stream from Azure OpenAI."""
    api_key, endpoint, deployment, api_version = get_azure_config(config, model)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    payload = {
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    url = (
        f"{endpoint}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={api_version}"
    )

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "api-key": api_key,
            },
            timeout=aiohttp.ClientTimeout(total=config.azure_openai_timeout),
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
