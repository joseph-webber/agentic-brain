# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Unified YAML-backed configuration for Agentic Brain.

The loader reads ``brain-config.yaml`` from the repository root by default and
applies environment variable overrides on top. Secrets are intentionally kept
out of YAML and should come from environment variables or external secret
stores.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar, cast, get_origin

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class UnifiedLLMSection(BaseModel):
    """Non-secret LLM runtime configuration."""

    model_config = ConfigDict(extra="forbid")

    default_provider: str = Field(default="ollama")
    default_model: str = Field(default="llama3.1:8b")
    timeout_seconds: int = Field(default=60, ge=1)
    max_retries: int = Field(default=3, ge=0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    ollama_base_url: str = Field(default="http://localhost:11434")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")


class VoiceSection(BaseModel):
    """Voice and accessibility defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    provider: str = "system"
    default_voice: str = "Karen"
    rate: int = Field(default=160, ge=50, le=250)
    volume: float = Field(default=0.8, ge=0.0, le=1.0)
    queue_enabled: bool = True


class Neo4jSection(BaseModel):
    """Neo4j connection settings excluding secrets."""

    model_config = ConfigDict(extra="forbid")

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    database: str = "neo4j"
    max_connection_pool_size: int = Field(default=50, ge=1)
    connection_timeout_seconds: int = Field(default=30, ge=1)


class APISection(BaseModel):
    """HTTP API defaults."""

    model_config = ConfigDict(extra="forbid")

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    base_path: str = "/api"
    request_timeout_seconds: int = Field(default=60, ge=1)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


class SecuritySection(BaseModel):
    """Security policy configuration without secrets."""

    model_config = ConfigDict(extra="forbid")

    require_auth: bool = True
    api_key_header: str = "X-API-Key"
    cors_enabled: bool = True
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    rate_limit_requests_per_minute: int = Field(default=100, ge=1)
    secrets_source: str = "environment"


class FeatureSection(BaseModel):
    """Feature flags for major subsystems."""

    model_config = ConfigDict(extra="forbid")

    rag_enabled: bool = True
    voice_enabled: bool = True
    neo4j_enabled: bool = True
    api_enabled: bool = True
    observability_enabled: bool = True
    local_llm_enabled: bool = True


class UnifiedConfig(BaseModel):
    """Full centralized application configuration."""

    model_config = ConfigDict(extra="forbid")

    llm: UnifiedLLMSection = Field(default_factory=UnifiedLLMSection)
    voice: VoiceSection = Field(default_factory=VoiceSection)
    neo4j: Neo4jSection = Field(default_factory=Neo4jSection)
    api: APISection = Field(default_factory=APISection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    features: FeatureSection = Field(default_factory=FeatureSection)


class ConfigLoader:
    """Load and validate the centralized YAML configuration."""

    ENV_CONFIG_PATH: ClassVar[str] = "BRAIN_CONFIG_PATH"
    ENV_OVERRIDES: ClassVar[dict[tuple[str, str], tuple[str, ...]]] = {
        ("llm", "default_provider"): ("LLM_DEFAULT_PROVIDER",),
        ("llm", "default_model"): ("LLM_DEFAULT_MODEL", "DEFAULT_MODEL"),
        ("llm", "timeout_seconds"): ("LLM_TIMEOUT", "LLM_TIMEOUT_SECONDS"),
        ("llm", "max_retries"): ("LLM_MAX_RETRIES",),
        ("llm", "temperature"): ("LLM_TEMPERATURE",),
        ("llm", "ollama_base_url"): ("OLLAMA_HOST", "LLM_OLLAMA_BASE_URL"),
        ("llm", "openrouter_base_url"): ("OPENROUTER_BASE_URL",),
        ("voice", "enabled"): ("VOICE_ENABLED",),
        ("voice", "provider"): ("VOICE_PROVIDER",),
        ("voice", "default_voice"): ("VOICE_DEFAULT_VOICE", "DEFAULT_VOICE"),
        ("voice", "rate"): ("VOICE_RATE",),
        ("voice", "volume"): ("VOICE_VOLUME",),
        ("voice", "queue_enabled"): ("VOICE_QUEUE_ENABLED",),
        ("neo4j", "uri"): ("NEO4J_URI",),
        ("neo4j", "user"): ("NEO4J_USER",),
        ("neo4j", "database"): ("NEO4J_DATABASE",),
        ("neo4j", "max_connection_pool_size"): (
            "NEO4J_POOL_SIZE",
            "NEO4J_MAX_CONNECTION_POOL_SIZE",
        ),
        ("neo4j", "connection_timeout_seconds"): (
            "NEO4J_POOL_TIMEOUT",
            "NEO4J_CONNECTION_TIMEOUT",
        ),
        ("api", "host"): ("API_HOST", "SERVER_HOST"),
        ("api", "port"): ("API_PORT", "SERVER_PORT"),
        ("api", "base_path"): ("API_BASE_PATH",),
        ("api", "request_timeout_seconds"): (
            "API_REQUEST_TIMEOUT",
            "API_REQUEST_TIMEOUT_SECONDS",
        ),
        ("api", "cors_origins"): ("API_CORS_ORIGINS", "CORS_ORIGINS"),
        ("security", "require_auth"): ("SECURITY_REQUIRE_AUTH",),
        ("security", "api_key_header"): ("SECURITY_API_KEY_HEADER",),
        ("security", "cors_enabled"): ("SECURITY_CORS_ENABLED",),
        ("security", "allowed_origins"): (
            "SECURITY_ALLOWED_ORIGINS",
            "CORS_ORIGINS",
        ),
        ("security", "rate_limit_requests_per_minute"): (
            "SECURITY_RATE_LIMIT_REQUESTS",
            "SECURITY_RATE_LIMIT_REQUESTS_PER_MINUTE",
        ),
        ("security", "secrets_source"): ("BRAIN_SECRETS_SOURCE",),
        ("features", "rag_enabled"): ("FEATURE_RAG_ENABLED",),
        ("features", "voice_enabled"): ("FEATURE_VOICE_ENABLED",),
        ("features", "neo4j_enabled"): ("FEATURE_NEO4J_ENABLED",),
        ("features", "api_enabled"): ("FEATURE_API_ENABLED",),
        ("features", "observability_enabled"): ("FEATURE_OBSERVABILITY_ENABLED",),
        ("features", "local_llm_enabled"): ("FEATURE_LOCAL_LLM_ENABLED",),
    }
    REQUIRED_FIELDS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("llm", "default_provider"),
        ("llm", "default_model"),
        ("voice", "default_voice"),
        ("neo4j", "uri"),
        ("neo4j", "user"),
        ("api", "host"),
        ("api", "port"),
        ("security", "api_key_header"),
        ("security", "secrets_source"),
    )

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = self._resolve_config_path(config_path)

    def load(self) -> UnifiedConfig:
        """Load configuration from YAML and environment variables."""

        raw_config = self._load_yaml()
        merged_config = self._apply_environment_overrides(raw_config)
        config = cast(UnifiedConfig, UnifiedConfig.model_validate(merged_config))
        self.validate_required_fields(config)
        return config

    def validate_required_fields(self, config: UnifiedConfig) -> None:
        """Raise ``ValueError`` when required public settings are blank."""

        missing_fields = [
            f"{section}.{field_name}"
            for section, field_name in self.REQUIRED_FIELDS
            if self._is_missing(getattr(getattr(config, section), field_name))
        ]
        if missing_fields:
            fields = ", ".join(missing_fields)
            raise ValueError(f"Missing required configuration values: {fields}")

    def _load_yaml(self) -> dict[str, Any]:
        """Read YAML config if present, otherwise return an empty config."""

        if not self.config_path.exists():
            return {}

        with self.config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}

        if not isinstance(loaded, dict):
            raise ValueError(
                f"Configuration file {self.config_path} must contain a top-level mapping."
            )
        return loaded

    def _apply_environment_overrides(
        self, raw_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Overlay environment variable values on top of YAML content."""

        merged: dict[str, Any] = {
            key: value.copy() if isinstance(value, dict) else value
            for key, value in raw_config.items()
        }

        for (section, field_name), env_names in self.ENV_OVERRIDES.items():
            env_value = self._get_env_value(env_names)
            if env_value is None:
                continue

            section_data = merged.setdefault(section, {})
            if not isinstance(section_data, dict):
                raise ValueError(f"Configuration section '{section}' must be a mapping.")

            section_model_annotation = UnifiedConfig.model_fields[section].annotation
            if not (
                isinstance(section_model_annotation, type)
                and issubclass(section_model_annotation, BaseModel)
            ):
                raise TypeError(
                    f"Configuration section '{section}' has an invalid schema definition."
                )

            section_model = cast(type[BaseModel], section_model_annotation)
            field_info = section_model.model_fields[field_name]
            coerced_value = self._coerce_env_value(field_info.annotation, env_value)
            section_data[field_name] = coerced_value

        return merged

    def _resolve_config_path(self, config_path: str | Path | None) -> Path:
        """Resolve the active config path."""

        if config_path is not None:
            return Path(config_path).expanduser().resolve()

        env_path = os.getenv(self.ENV_CONFIG_PATH)
        if env_path:
            return Path(env_path).expanduser().resolve()

        return Path(__file__).resolve().parents[3] / "brain-config.yaml"

    @staticmethod
    def _get_env_value(env_names: tuple[str, ...]) -> str | None:
        """Return the first non-empty environment value for a set of keys."""

        for env_name in env_names:
            value = os.getenv(env_name)
            if value is not None and value != "":
                return value
        return None

    @staticmethod
    def _coerce_env_value(annotation: Any, raw_value: str) -> Any:
        """Convert environment values into typed config data."""

        parsed: Any = raw_value
        if get_origin(annotation) is list:
            parsed = [item.strip() for item in raw_value.split(",") if item.strip()]
        elif raw_value.strip().startswith(("[", "{")):
            parsed = yaml.safe_load(raw_value)

        return TypeAdapter(annotation).validate_python(parsed)

    @staticmethod
    def _is_missing(value: Any) -> bool:
        """Return ``True`` when a config value should be treated as missing."""

        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, list):
            return len(value) == 0
        return False
