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
from .routing import LLMRouter, chat, chat_async, get_router
from .smart_router import (
    SmartRouter,
    SmashMode,
    SmashResult,
    SecurityPosture,
    PostureMode,
    ludicrous_smash,
    cascade_smash,
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
    "ludicrous_smash",
    "cascade_smash",
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
