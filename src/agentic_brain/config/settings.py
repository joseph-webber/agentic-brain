# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
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
JHipster-style Pydantic Settings with Environment Profiles

This module provides configuration management similar to JHipster's Spring Profiles:
- Environment detection (dev, staging, prod)
- Nested configuration groups
- Environment variable override
- .env file loading by profile

Configuration hierarchy (highest priority first):
1. Environment variables
2. .env.{environment} file
3. .env file
4. Default values
"""

from __future__ import annotations

import os
from enum import Enum, StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Application environment profiles (like JHipster Spring Profiles)."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"
    TEST = "test"


class Neo4jSettings(BaseSettings):
    """Neo4j database configuration."""

    model_config = SettingsConfigDict(env_prefix="NEO4J_")

    uri: str = Field(
        default="bolt://localhost:7687", description="Neo4j connection URI"
    )
    user: str = Field(default="neo4j", description="Neo4j username")
    password: SecretStr = Field(default=SecretStr(""), description="Neo4j password")
    database: str = Field(default="neo4j", description="Database name")
    max_connection_pool_size: int = Field(
        default=50, description="Maximum connection pool size"
    )
    connection_timeout: int = Field(
        default=30, description="Connection timeout in seconds"
    )
    encrypted: bool = Field(default=False, description="Use TLS encryption")


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    default_provider: str = Field(default="ollama", description="Default LLM provider")
    default_model: str = Field(default="llama3.2:3b", description="Default model name")
    timeout: int = Field(default=60, description="Request timeout seconds")
    max_retries: int = Field(default=3, description="Max retry attempts")

    # Provider-specific API keys (loaded from env vars)
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    azure_openai_api_key: SecretStr | None = Field(
        default=None, alias="AZURE_OPENAI_API_KEY"
    )
    azure_openai_endpoint: str | None = Field(
        default=None, alias="AZURE_OPENAI_ENDPOINT"
    )
    azure_openai_deployment: str | None = Field(
        default=None, alias="AZURE_OPENAI_DEPLOYMENT"
    )
    azure_openai_api_version: str | None = Field(
        default=None, alias="AZURE_OPENAI_API_VERSION"
    )
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: SecretStr | None = Field(default=None, alias="GROQ_API_KEY")
    google_api_key: SecretStr | None = Field(default=None, alias="GOOGLE_API_KEY")
    openrouter_api_key: SecretStr | None = Field(
        default=None, alias="OPENROUTER_API_KEY"
    )
    together_api_key: SecretStr | None = Field(default=None, alias="TOGETHER_API_KEY")
    xai_api_key: SecretStr | None = Field(default=None, alias="XAI_API_KEY")


class SecuritySettings(BaseSettings):
    """Security and authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    jwt_secret: SecretStr = Field(
        default=SecretStr("change-me-in-production"), description="JWT signing secret"
    )
    jwt_algorithm: str = Field(default="HS512", description="JWT algorithm")
    jwt_expiration_hours: int = Field(
        default=24, description="JWT token expiration in hours"
    )
    jwt_refresh_expiration_days: int = Field(
        default=7, description="Refresh token expiration in days"
    )
    password_min_length: int = Field(default=12, description="Minimum password length")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    rate_limit_requests: int = Field(
        default=100, description="Rate limit requests per minute"
    )


class ObservabilitySettings(BaseSettings):
    """Observability and monitoring configuration."""

    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_")

    enable_tracing: bool = Field(
        default=True, description="Enable OpenTelemetry tracing"
    )
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    otlp_endpoint: str | None = Field(
        default=None, description="OpenTelemetry collector endpoint"
    )
    service_name: str = Field(
        default="agentic-brain", description="Service name for tracing"
    )


class CacheSettings(BaseSettings):
    """Caching configuration."""

    model_config = SettingsConfigDict(env_prefix="CACHE_")

    backend: str = Field(
        default="memory", description="Cache backend: memory, redis, or none"
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    default_ttl: int = Field(default=3600, description="Default TTL in seconds")
    max_size: int = Field(
        default=10000, description="Maximum cache entries (memory backend)"
    )
    semantic_cache_enabled: bool = Field(
        default=False, description="Enable semantic caching for LLM responses"
    )
    semantic_similarity_threshold: float = Field(
        default=0.95, description="Similarity threshold for cache hits"
    )


class ServerSettings(BaseSettings):
    """Server configuration."""

    model_config = SettingsConfigDict(env_prefix="SERVER_")

    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of workers")
    reload: bool = Field(default=False, description="Enable hot reload")
    docs_enabled: bool = Field(default=True, description="Enable OpenAPI docs")


class Settings(BaseSettings):
    """
    Main application settings with JHipster-style profiles.

    Environment is detected from:
    1. ENVIRONMENT env var
    2. Defaults to "dev"

    Configuration files loaded:
    1. .env (always)
    2. .env.{environment} (environment-specific)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application info
    app_name: str = Field(default="Agentic Brain", description="Application name")
    version: str = Field(default="2.11.0", description="Application version")
    environment: Environment = Field(
        default=Environment.DEV, description="Environment profile"
    )
    debug: bool = Field(default=False, description="Debug mode")

    # Nested configuration groups
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: Any) -> Environment:
        """Validate and convert environment string to enum."""
        if isinstance(v, Environment):
            return v
        if isinstance(v, str):
            v = v.lower()
            try:
                return Environment(v)
            except ValueError:
                # Default to dev for unknown environments
                return Environment.DEV
        return Environment.DEV

    @property
    def is_dev(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEV

    @property
    def is_prod(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PROD

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == Environment.TEST

    def get_env_file_path(self) -> Path | None:
        """Get environment-specific .env file path."""
        env_file = Path(f".env.{self.environment.value}")
        if env_file.exists():
            return env_file
        return None


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Settings are loaded once and cached. Use this function
    for dependency injection in FastAPI.

    Returns:
        Settings: Cached settings instance
    """
    # Detect environment
    env = os.getenv("ENVIRONMENT", "dev").lower()

    # Load environment-specific .env file if it exists
    env_file = f".env.{env}"
    if Path(env_file).exists():
        return Settings(_env_file=env_file)

    return Settings()


# Module-level settings instance for convenience
settings = get_settings()


# Profile-specific default overrides
PROFILE_DEFAULTS: dict[Environment, dict[str, Any]] = {
    Environment.DEV: {
        "debug": True,
        "server.reload": True,
        "observability.log_level": "DEBUG",
        "cache.backend": "memory",
    },
    Environment.STAGING: {
        "debug": False,
        "server.reload": False,
        "observability.log_level": "INFO",
        "cache.backend": "redis",
    },
    Environment.PROD: {
        "debug": False,
        "server.reload": False,
        "server.workers": 4,
        "observability.log_level": "WARNING",
        "observability.log_format": "json",
        "cache.backend": "redis",
        "security.cors_origins": [],  # Must be explicitly configured
    },
    Environment.TEST: {
        "debug": True,
        "observability.log_level": "DEBUG",
        "cache.backend": "memory",
        "neo4j.database": "test",
    },
}
