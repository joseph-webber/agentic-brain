# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Structured configuration loading and validation for Agentic Brain."""

from __future__ import annotations

import os
import re
import tomllib
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from .profiles import (
    ConfigProfile,
    DevelopmentProfile,
    get_profile,
)


class Environment(StrEnum):
    """Compatibility environment enum used by legacy code and tests."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"
    TEST = "test"
    CUSTOM = "custom"


class ProviderName(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    TOGETHER = "together"
    GOOGLE = "google"
    OPENROUTER = "openrouter"
    XAI = "xai"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


class CacheBackend(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"
    SQLITE = "sqlite"
    NONE = "none"


class VoiceProvider(StrEnum):
    SYSTEM = "system"
    CARTESIA = "cartesia"
    ELEVENLABS = "elevenlabs"
    KOKORO = "kokoro"
    GTTS = "gtts"
    PYYTSSX3 = "pyttsx3"


class Neo4jSettings(BaseModel):
    """Neo4j connection settings."""

    model_config = ConfigDict(extra="forbid")

    uri: str = Field(default="bolt://localhost:7687", min_length=1)
    user: str = Field(default="neo4j", min_length=1)
    password: SecretStr = Field(
        default=SecretStr("change-me-in-production-use-a-strong-secret"),
    )
    database: str = Field(default="neo4j", min_length=1)
    max_connection_pool_size: int = Field(default=50, ge=1, le=1000)
    connection_timeout: int = Field(default=30, ge=1, le=300)
    connection_timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    encrypted: bool = False

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        if not value:
            raise ValueError("Neo4j URI cannot be blank")
        if not value.startswith(
            (
                "bolt://",
                "neo4j://",
                "bolt+s://",
                "neo4j+s://",
                "bolt+ssc://",
                "neo4j+ssc://",
            )
        ):
            raise ValueError("Neo4j URI must use bolt:// or neo4j://")
        return value

    @model_validator(mode="after")
    def reconcile_timeout_alias(self) -> Neo4jSettings:
        if self.connection_timeout_seconds is not None:
            self.connection_timeout = self.connection_timeout_seconds
        return self


class LLMSettings(BaseModel):
    """LLM provider configuration."""

    model_config = ConfigDict(extra="forbid")

    default_provider: ProviderName = ProviderName.OLLAMA
    default_model: str = Field(default="llama3.2:3b", min_length=1)
    timeout: int = Field(default=60, ge=1, le=600)
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    ollama_base_url: str | None = None
    openrouter_base_url: str | None = None
    openai_api_key: SecretStr | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str | None = None
    anthropic_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    together_api_key: SecretStr | None = None
    xai_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def reconcile_timeout_alias(self) -> LLMSettings:
        if self.timeout_seconds is not None:
            self.timeout = self.timeout_seconds
        return self


class VoiceSettings(BaseModel):
    """Accessibility and text-to-speech defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    provider: VoiceProvider = VoiceProvider.SYSTEM
    default_voice: str = Field(default="Karen", min_length=1)
    rate: int = Field(default=160, ge=50, le=250)
    volume: float = Field(default=0.8, ge=0.0, le=1.0)
    queue_enabled: bool = True


class SecuritySettings(BaseModel):
    """Security and authentication configuration."""

    model_config = ConfigDict(extra="forbid")

    jwt_secret: SecretStr = Field(
        default=SecretStr("change-me-in-production-use-a-strong-secret"),
    )
    jwt_algorithm: str = Field(default="HS512", min_length=3)
    jwt_expiration_hours: int = Field(default=24, ge=1, le=168)
    jwt_refresh_expiration_days: int = Field(default=7, ge=1, le=365)
    password_min_length: int = Field(default=12, ge=8, le=128)
    api_key_header: str = Field(default="X-API-Key", min_length=1)
    require_auth: bool = True
    cors_enabled: bool = True
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    rate_limit_requests: int = Field(default=100, ge=1, le=100000)
    rate_limit_requests_per_minute: int | None = Field(default=None, ge=1, le=100000)
    secrets_source: str = Field(default="environment", min_length=1)

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, values: list[str]) -> list[str]:
        return _validate_origins(values)

    @model_validator(mode="after")
    def reconcile_rate_limit_alias(self) -> SecuritySettings:
        if self.rate_limit_requests_per_minute is not None:
            self.rate_limit_requests = self.rate_limit_requests_per_minute
        return self


class ObservabilitySettings(BaseModel):
    """Logging and tracing configuration."""

    model_config = ConfigDict(extra="forbid")

    enable_tracing: bool = True
    enable_metrics: bool = True
    log_level: LogLevel = LogLevel.INFO
    log_format: LogFormat = LogFormat.JSON
    otlp_endpoint: str | None = None
    service_name: str = Field(default="agentic-brain", min_length=1)


class CacheSettings(BaseModel):
    """Cache configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: CacheBackend = CacheBackend.MEMORY
    redis_url: str = Field(default="redis://localhost:6379/0", min_length=1)
    default_ttl: int = Field(default=3600, ge=1, le=86400 * 365)
    max_size: int = Field(default=10000, ge=1, le=1_000_000)
    semantic_cache_enabled: bool = False
    semantic_similarity_threshold: float = Field(default=0.95, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_backend(self) -> CacheSettings:
        if self.backend == CacheBackend.REDIS and not self.redis_url:
            raise ValueError("redis_url is required when cache backend is redis")
        return self


class ServerSettings(BaseModel):
    """HTTP server configuration."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(default="0.0.0.0", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1, le=128)
    reload: bool = False
    docs_enabled: bool = True
    base_path: str = Field(default="/api", min_length=1)
    request_timeout_seconds: int = Field(default=60, ge=1, le=600)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        return _validate_origins(values)


class FeatureSettings(BaseModel):
    """Feature flags for major subsystems."""

    model_config = ConfigDict(extra="forbid")

    rag_enabled: bool = True
    voice_enabled: bool = True
    neo4j_enabled: bool = True
    api_enabled: bool = True
    observability_enabled: bool = True
    local_llm_enabled: bool = True


class Settings(BaseModel):
    """Fully validated application settings."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    profile: str = Field(default=DevelopmentProfile().name, min_length=1)
    app_name: str = Field(default="Agentic Brain", min_length=1)
    version: str = Field(default="3.1.1", min_length=1)
    debug: bool = False
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)

    @field_validator("profile")
    @classmethod
    def normalize_profile(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("profile cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_profile_rules(self) -> Settings:
        if self.profile in {"production", "prod"}:
            secret = self.security.jwt_secret.get_secret_value()
            if "change-me" in secret or len(secret) < 32:
                raise ValueError("production requires a strong JWT secret")
            if any(origin == "*" for origin in self.server.cors_origins):
                raise ValueError("production cannot allow wildcard server CORS origins")
            if any(origin == "*" for origin in self.security.allowed_origins):
                raise ValueError("production cannot allow wildcard security origins")
        return self

    @property
    def environment(self) -> Environment:
        return _profile_to_environment(self.profile)

    @property
    def is_dev(self) -> bool:
        return self.profile in {"development", "dev"}

    @property
    def is_prod(self) -> bool:
        return self.profile in {"production", "prod"}

    @property
    def is_test(self) -> bool:
        return self.profile in {"testing", "test"}

    @property
    def is_custom(self) -> bool:
        return self.environment is Environment.CUSTOM

    @property
    def api(self) -> ServerSettings:
        """Compatibility alias for existing code that expects an API section."""

        return self.server

    @classmethod
    def from_sources(
        cls,
        *,
        profile: ConfigProfile | str | None = None,
        config_file: str | Path | None = None,
        env_file: str | Path | None = None,
        base_path: str | Path | None = None,
    ) -> Settings:
        resolved_profile = get_profile(profile or _profile_from_env())
        data = resolved_profile.build()
        data = deep_merge(data, _load_config_file(config_file, base_path=base_path))
        data = deep_merge(
            data,
            _load_env_file(
                env_file, profile=resolved_profile.name, base_path=base_path
            ),
        )
        data = deep_merge(data, _load_environment_variables())
        data = _normalize_legacy_aliases(data)
        if profile is not None:
            data["profile"] = resolved_profile.name
        else:
            data.setdefault("profile", resolved_profile.name)
        return cls.model_validate(data)


ENVIRONMENT_KEYS = {
    "BRAIN_PROFILE",
    "ENVIRONMENT",
}

ENV_VAR_PATHS: dict[str, tuple[str, ...]] = {
    "APP_NAME": ("app_name",),
    "APP_VERSION": ("version",),
    "DEBUG": ("debug",),
    "PROFILE": ("profile",),
    "SERVER_HOST": ("server", "host"),
    "SERVER_PORT": ("server", "port"),
    "SERVER_WORKERS": ("server", "workers"),
    "SERVER_RELOAD": ("server", "reload"),
    "SERVER_DOCS_ENABLED": ("server", "docs_enabled"),
    "SERVER_BASE_PATH": ("server", "base_path"),
    "SERVER_REQUEST_TIMEOUT_SECONDS": ("server", "request_timeout_seconds"),
    "SERVER_CORS_ORIGINS": ("server", "cors_origins"),
    "API_HOST": ("server", "host"),
    "API_PORT": ("server", "port"),
    "API_BASE_PATH": ("server", "base_path"),
    "API_REQUEST_TIMEOUT": ("server", "request_timeout_seconds"),
    "API_REQUEST_TIMEOUT_SECONDS": ("server", "request_timeout_seconds"),
    "API_CORS_ORIGINS": ("server", "cors_origins"),
    "NEO4J_URI": ("neo4j", "uri"),
    "NEO4J_USER": ("neo4j", "user"),
    "NEO4J_PASSWORD": ("neo4j", "password"),
    "NEO4J_DATABASE": ("neo4j", "database"),
    "NEO4J_MAX_CONNECTION_POOL_SIZE": ("neo4j", "max_connection_pool_size"),
    "NEO4J_POOL_SIZE": ("neo4j", "max_connection_pool_size"),
    "NEO4J_CONNECTION_TIMEOUT": ("neo4j", "connection_timeout"),
    "NEO4J_POOL_TIMEOUT": ("neo4j", "connection_timeout"),
    "NEO4J_ENCRYPTED": ("neo4j", "encrypted"),
    "LLM_DEFAULT_PROVIDER": ("llm", "default_provider"),
    "LLM_DEFAULT_MODEL": ("llm", "default_model"),
    "LLM_TIMEOUT": ("llm", "timeout"),
    "LLM_TIMEOUT_SECONDS": ("llm", "timeout"),
    "LLM_MAX_RETRIES": ("llm", "max_retries"),
    "LLM_TEMPERATURE": ("llm", "temperature"),
    "OLLAMA_HOST": ("llm", "ollama_base_url"),
    "OPENROUTER_BASE_URL": ("llm", "openrouter_base_url"),
    "OPENAI_API_KEY": ("llm", "openai_api_key"),
    "AZURE_OPENAI_API_KEY": ("llm", "azure_openai_api_key"),
    "AZURE_OPENAI_ENDPOINT": ("llm", "azure_openai_endpoint"),
    "AZURE_OPENAI_DEPLOYMENT": ("llm", "azure_openai_deployment"),
    "AZURE_OPENAI_API_VERSION": ("llm", "azure_openai_api_version"),
    "ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),
    "GROQ_API_KEY": ("llm", "groq_api_key"),
    "GOOGLE_API_KEY": ("llm", "google_api_key"),
    "OPENROUTER_API_KEY": ("llm", "openrouter_api_key"),
    "TOGETHER_API_KEY": ("llm", "together_api_key"),
    "XAI_API_KEY": ("llm", "xai_api_key"),
    "VOICE_ENABLED": ("voice", "enabled"),
    "VOICE_PROVIDER": ("voice", "provider"),
    "VOICE_DEFAULT_VOICE": ("voice", "default_voice"),
    "VOICE_RATE": ("voice", "rate"),
    "VOICE_VOLUME": ("voice", "volume"),
    "VOICE_QUEUE_ENABLED": ("voice", "queue_enabled"),
    "SECURITY_JWT_SECRET": ("security", "jwt_secret"),
    "SECURITY_JWT_ALGORITHM": ("security", "jwt_algorithm"),
    "SECURITY_JWT_EXPIRATION_HOURS": ("security", "jwt_expiration_hours"),
    "SECURITY_JWT_REFRESH_EXPIRATION_DAYS": ("security", "jwt_refresh_expiration_days"),
    "SECURITY_PASSWORD_MIN_LENGTH": ("security", "password_min_length"),
    "SECURITY_API_KEY_HEADER": ("security", "api_key_header"),
    "SECURITY_REQUIRE_AUTH": ("security", "require_auth"),
    "SECURITY_CORS_ENABLED": ("security", "cors_enabled"),
    "SECURITY_ALLOWED_ORIGINS": ("security", "allowed_origins"),
    "SECURITY_RATE_LIMIT_REQUESTS": ("security", "rate_limit_requests"),
    "SECURITY_SECRETS_SOURCE": ("security", "secrets_source"),
    "CORS_ORIGINS": ("security", "allowed_origins"),
    "OBSERVABILITY_ENABLE_TRACING": ("observability", "enable_tracing"),
    "OBSERVABILITY_ENABLE_METRICS": ("observability", "enable_metrics"),
    "OBSERVABILITY_LOG_LEVEL": ("observability", "log_level"),
    "OBSERVABILITY_LOG_FORMAT": ("observability", "log_format"),
    "OBSERVABILITY_OTLP_ENDPOINT": ("observability", "otlp_endpoint"),
    "OBSERVABILITY_SERVICE_NAME": ("observability", "service_name"),
    "CACHE_BACKEND": ("cache", "backend"),
    "CACHE_REDIS_URL": ("cache", "redis_url"),
    "CACHE_DEFAULT_TTL": ("cache", "default_ttl"),
    "CACHE_MAX_SIZE": ("cache", "max_size"),
    "CACHE_SEMANTIC_CACHE_ENABLED": ("cache", "semantic_cache_enabled"),
    "CACHE_SEMANTIC_SIMILARITY_THRESHOLD": ("cache", "semantic_similarity_threshold"),
    "FEATURE_RAG_ENABLED": ("features", "rag_enabled"),
    "FEATURE_VOICE_ENABLED": ("features", "voice_enabled"),
    "FEATURE_NEO4J_ENABLED": ("features", "neo4j_enabled"),
    "FEATURE_API_ENABLED": ("features", "api_enabled"),
    "FEATURE_OBSERVABILITY_ENABLED": ("features", "observability_enabled"),
    "FEATURE_LOCAL_LLM_ENABLED": ("features", "local_llm_enabled"),
}


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge two mappings."""

    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, Mapping)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _profile_from_env() -> str:
    for key in ("BRAIN_PROFILE", "ENVIRONMENT", "PROFILE"):
        value = os.getenv(key)
        if value:
            return value
    return DevelopmentProfile().name


def _profile_to_environment(profile: str) -> Environment:
    normalized = profile.strip().lower()
    if normalized in {"development", "dev"}:
        return Environment.DEV
    if normalized in {"staging", "stage"}:
        return Environment.STAGING
    if normalized in {"production", "prod"}:
        return Environment.PROD
    if normalized in {"testing", "test"}:
        return Environment.TEST
    return Environment.CUSTOM


def _load_config_file(
    config_file: str | Path | None,
    *,
    base_path: str | Path | None = None,
) -> dict[str, Any]:
    path = _resolve_config_file_path(config_file, base_path=base_path)
    if path is None or not path.exists():
        return {}
    if path.is_dir():
        raise ValueError(f"Configuration path {path} must be a file")

    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif suffix == ".toml":
        loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unsupported configuration file format: {path.suffix}")

    if not isinstance(loaded, dict):
        raise ValueError("Configuration file must contain a top-level mapping")
    return _normalize_legacy_aliases(loaded)


def _resolve_config_file_path(
    config_file: str | Path | None,
    *,
    base_path: str | Path | None = None,
) -> Path | None:
    if config_file is not None:
        return Path(config_file).expanduser().resolve()

    env_path = os.getenv("BRAIN_CONFIG_FILE") or os.getenv("BRAIN_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    search_roots: list[Path] = []
    if base_path is not None:
        search_roots.append(Path(base_path).expanduser().resolve())
    search_roots.append(Path.cwd())
    search_roots.append(Path(__file__).resolve().parents[3])

    for root in search_roots:
        for candidate in ("brain-config.yaml", "brain-config.yml", "brain-config.toml"):
            resolved = root / candidate
            if resolved.exists():
                return resolved
    return None


def _load_env_file(
    env_file: str | Path | None,
    *,
    profile: str,
    base_path: str | Path | None = None,
) -> dict[str, Any]:
    candidates: list[Path] = []
    if env_file is not None:
        candidates.append(Path(env_file).expanduser().resolve())
    else:
        explicit = os.getenv("BRAIN_ENV_FILE")
        if explicit:
            candidates.append(Path(explicit).expanduser().resolve())
        else:
            roots: list[Path] = []
            if base_path is not None:
                roots.append(Path(base_path).expanduser().resolve())
            roots.append(Path.cwd())
            roots.append(Path(__file__).resolve().parents[3])
            for root in roots:
                candidates.extend(
                    [
                        root / ".env",
                        root / f".env.{profile}",
                        root / f".env.{profile.lower()}",
                    ]
                )

    merged: dict[str, Any] = {}
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            merged = deep_merge(merged, _load_env_file_mapping(candidate))
    return merged


def _load_env_file_mapping(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        parsed = _parse_env_value(value)
        _apply_env_key(data, key, parsed)
    return data


def _load_environment_variables() -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, raw_value in os.environ.items():
        _apply_env_key(data, key, _parse_env_value(raw_value))
    return data


def _assign_env_value(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    _assign_path(target, tuple(dotted_path.split(".")), value)


def _apply_env_key(target: dict[str, Any], key: str, parsed: Any) -> None:
    if key in ENVIRONMENT_KEYS:
        _assign_env_value(target, "profile", parsed)
        return
    if key == "CORS_ORIGINS":
        if isinstance(parsed, str):
            parsed = [part.strip() for part in parsed.split(",") if part.strip()]
        _assign_env_value(target, "server.cors_origins", parsed)
        _assign_env_value(target, "security.allowed_origins", parsed)
        return
    if key not in ENV_VAR_PATHS:
        return
    if key.endswith("ORIGINS") and isinstance(parsed, str):
        parsed = [part.strip() for part in parsed.split(",") if part.strip()]
    _assign_path(target, ENV_VAR_PATHS[key], parsed)


def _assign_path(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for segment in path[:-1]:
        current = current.setdefault(segment, {})
        if not isinstance(current, dict):
            raise ValueError(f"Configuration section '{segment}' must be a mapping")
    current[path[-1]] = value


def _parse_env_value(raw_value: Any) -> Any:
    if not isinstance(raw_value, str):
        return raw_value
    value = raw_value.strip()
    if not value:
        return ""
    lower = value.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"none", "null"}:
        return None
    if value.startswith(("[", "{")):
        try:
            return yaml.safe_load(value)
        except Exception:
            return value
    if "," in value and "://" not in value and not value.startswith("http"):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if len(parts) > 1:
            return parts
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return _strip_wrapping_quotes(value)


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _strip_inline_comment(value: str) -> str:
    if not value:
        return value
    if value[0] in {"'", '"'}:
        return _strip_wrapping_quotes(value)
    if " #" in value:
        return value.split(" #", 1)[0].strip()
    return value.strip()


def _validate_origins(values: list[str]) -> list[str]:
    validated: list[str] = []
    for origin in values:
        if not origin:
            raise ValueError("Origin values cannot be blank")
        if origin == "*":
            validated.append(origin)
            continue
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/$.?#].*", origin):
            raise ValueError(f"Invalid origin: {origin}")
        validated.append(origin)
    return validated


def _normalize_legacy_aliases(data: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    if "api" in normalized and "server" not in normalized:
        normalized["server"] = normalized.pop("api")
    elif "api" in normalized:
        api_section = normalized.pop("api")
        if isinstance(api_section, Mapping) and isinstance(
            normalized.get("server"), Mapping
        ):
            normalized["server"] = deep_merge(normalized["server"], api_section)
        elif isinstance(api_section, Mapping):
            normalized["server"] = api_section
    if "environment" in normalized and "profile" not in normalized:
        normalized["profile"] = normalized.pop("environment")
    if "CORS_ORIGINS" in normalized:
        cors = normalized.pop("CORS_ORIGINS")
        if isinstance(cors, Mapping):
            cors = list(cors)
        elif isinstance(cors, str):
            cors = [cors]
        normalized.setdefault("server", {})
        normalized.setdefault("security", {})
        if isinstance(normalized["server"], Mapping):
            normalized["server"] = dict(normalized["server"])
            normalized["server"].setdefault("cors_origins", cors)
        if isinstance(normalized["security"], Mapping):
            normalized["security"] = dict(normalized["security"])
            normalized["security"].setdefault("allowed_origins", cors)
    return normalized


@lru_cache
def get_settings() -> Settings:
    """Return cached settings loaded from the active sources."""

    return Settings.from_sources()


settings = get_settings()


__all__ = [
    "Settings",
    "Environment",
    "ProviderName",
    "LogLevel",
    "LogFormat",
    "CacheBackend",
    "VoiceProvider",
    "Neo4jSettings",
    "LLMSettings",
    "VoiceSettings",
    "SecuritySettings",
    "ObservabilitySettings",
    "CacheSettings",
    "ServerSettings",
    "FeatureSettings",
    "get_settings",
    "settings",
    "deep_merge",
]
