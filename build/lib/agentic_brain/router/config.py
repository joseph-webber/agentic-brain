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

"""
Router configuration and data structures.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Provider(Enum):
    """LLM providers."""

    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    TOGETHER = "together"
    GOOGLE = "google"
    XAI = "xai"


@dataclass
class Model:
    """Model configuration."""

    name: str
    provider: Provider
    context_length: int = 4096
    supports_tools: bool = False

    # Common models
    @staticmethod
    def llama3_8b() -> Model:
        return Model("llama3.1:8b", Provider.OLLAMA, 8192)

    @staticmethod
    def llama3_3b() -> Model:
        return Model("llama3.2:3b", Provider.OLLAMA, 4096)

    @staticmethod
    def gpt4o() -> Model:
        return Model("gpt-4o", Provider.OPENAI, 128000, True)

    @staticmethod
    def claude_sonnet() -> Model:
        return Model("claude-3-sonnet", Provider.ANTHROPIC, 200000, True)


@dataclass
class LLMConfig:
    """Configuration for a specific LLM instance."""

    provider: str
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    fallback: Optional[str] = None


@dataclass
class RouterConfig:
    """Router configuration."""

    models: Dict[str, LLMConfig] = field(default_factory=dict)
    default_provider: Provider = Provider.OLLAMA
    default_model: str = "llama3.1:8b"
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    timeout: int = 60  # Keep as default fallback
    max_retries: int = 3
    fallback_enabled: bool = True
    use_http_pool: bool = True  # Use HTTP connection pooling (recommended)
    priority_models: list[str] = field(
        default_factory=lambda: ["L2", "OP2", "CL2"]
    )  # Friendly alias chain
    model_aliases: dict[str, str] = field(default_factory=dict)
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 8.0
    cost_tracking_enabled: bool = True

    # Per-provider timeouts
    ollama_timeout: int = 120  # Local models can be slow on first load
    openai_timeout: int = 60
    azure_openai_timeout: int = 60
    anthropic_timeout: int = 90  # Claude can be slower
    openrouter_timeout: int = 60
    groq_timeout: int = 60
    together_timeout: int = 60
    google_timeout: int = 60
    xai_timeout: int = 60

    # API keys (loaded from env if not set)
    openai_key: str | None = None
    azure_openai_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str | None = None
    anthropic_key: str | None = None
    openrouter_key: str | None = None
    groq_key: str | None = None
    together_key: str | None = None
    google_key: str | None = None
    xai_key: str | None = None

    # Semantic prompt caching
    cache_enabled: bool = True  # Enable semantic prompt caching
    cache_ttl_seconds: int = 3600  # Cache TTL (1 hour default)
    cache_max_entries: int = 10000  # Max cached responses
    cache_backend: str = "memory"  # memory, sqlite, redis
    cache_normalize_whitespace: bool = True  # Normalize whitespace in keys
    cache_sqlite_path: str | None = None  # Path for SQLite backend
    cache_redis_url: str | None = None  # URL for Redis backend


@dataclass
class Message:
    """Chat message."""

    role: str  # system, user, assistant
    content: str


@dataclass
class Response:
    """LLM response."""

    content: str
    model: str
    provider: Provider
    tokens_used: int = 0
    finish_reason: str = "stop"
    cached: bool = False  # Whether response was served from cache
    cache_key: str | None = None  # Cache key if applicable
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
