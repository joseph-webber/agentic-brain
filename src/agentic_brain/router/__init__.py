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

"""
LLM router with fallback chains (fully async).

Routes requests to appropriate LLM providers:
- Cloud (OpenRouter, OpenAI, Anthropic)
- Local (Ollama)
- Automatic fallback on failure

Example:
    >>> from agentic_brain.router import LLMRouter
    >>> router = LLMRouter()
    >>> response = await router.chat("Hello, how are you?")

This module provides backward-compatible imports for the router subpackage.
All public APIs are available directly from `agentic_brain.router`.

Import weight guide
-------------------
All provider modules are imported **eagerly** here so that
``from agentic_brain.router import LLMRouter`` resolves everything in one
shot.  The actual HTTP client libraries (``openai``, ``anthropic``,
``google-generativeai``, etc.) are **not** imported at module level — each
``chat_*`` / ``stream_*`` function imports its client lazily on first call.

The one exception is ``aiohttp`` which several providers import at the module
level for type annotations.  Install cost is ~5 ms on Apple Silicon.

If you only need a single provider, import it directly::

    from agentic_brain.router.openai import chat_openai
    from agentic_brain.router.ollama import chat_ollama
"""

# Re-export all public APIs for backward compatibility
# Provider implementations (for advanced usage)
from .anthropic import chat_anthropic, stream_anthropic
from .azure_openai import chat_azure_openai, stream_azure_openai
from .config import Message, Model, Provider, Response, RouterConfig
from .google import chat_google, stream_google
from .groq import chat_groq, stream_groq
from .ollama import (
    chat_ollama,
    check_ollama_available,
    check_ollama_sync,
    list_models_async,
    list_models_sync,
    stream_ollama,
)
from .openai import chat_openai, stream_openai
from .openrouter import chat_openrouter, stream_openrouter
from .provider_checker import (
    ProviderChecker,
    ProviderStatus,
    format_error_message,
    format_provider_status_report,
    get_setup_help,
)
from .smart_router import (
    PostureMode,
    SecurityPosture,
    SmartRouter,
    SmashMode,
    SmashResult,
)
from .together import chat_together, stream_together
from .xai import chat_xai, stream_xai

__all__ = [
    # Main classes
    "LLMRouter",
    "RouterConfig",
    "Provider",
    "Response",
    "Message",
    "Model",
    # Provider checker (new)
    "ProviderChecker",
    "ProviderStatus",
    "format_error_message",
    "format_provider_status_report",
    "get_setup_help",
    # Convenience functions
    "get_router",
    "chat_async",
    "chat",
    # Smart router
    "SmartRouter",
    "SmashMode",
    "SmashResult",
    "SecurityPosture",
    "PostureMode",
    # Ollama
    "chat_ollama",
    "stream_ollama",
    "check_ollama_available",
    "check_ollama_sync",
    "list_models_async",
    "list_models_sync",
    # OpenAI
    "chat_openai",
    "stream_openai",
    # Azure OpenAI
    "chat_azure_openai",
    "stream_azure_openai",
    # Anthropic
    "chat_anthropic",
    "stream_anthropic",
    # Google
    "chat_google",
    "stream_google",
    # Groq
    "chat_groq",
    "stream_groq",
    # OpenRouter
    "chat_openrouter",
    "stream_openrouter",
    # Together
    "chat_together",
    "stream_together",
    # xAI
    "chat_xai",
    "stream_xai",
]

# --- Lazy imports for .routing to break circular dependency ---------------
# routing.py imports agentic_brain.llm.router.LLMRouterCore, and llm/router.py
# imports agentic_brain.router.config which triggers this __init__.  Deferring
# the .routing import via __getattr__ (PEP 562) ensures llm/router.py is fully
# loaded before routing.py tries to read LLMRouterCore from it.
_ROUTING_ATTRS = {"LLMRouter", "chat", "chat_async", "get_router"}


def __getattr__(name: str):
    if name in _ROUTING_ATTRS:
        from .routing import LLMRouter, chat, chat_async, get_router

        _mapping = {
            "LLMRouter": LLMRouter,
            "chat": chat,
            "chat_async": chat_async,
            "get_router": get_router,
        }
        # Cache in module globals so __getattr__ is only called once per name
        for attr_name, attr_val in _mapping.items():
            globals()[attr_name] = attr_val
        return _mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
