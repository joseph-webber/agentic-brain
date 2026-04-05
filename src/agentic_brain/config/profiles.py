
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Profile definitions for Agentic Brain configuration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ProfileName(StrEnum):
    """Canonical profile names."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"
    STAGING = "staging"
    CUSTOM = "custom"


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = deepcopy(value)
    return merged


@dataclass(frozen=True, slots=True)
class ConfigProfile:
    """Base profile definition."""

    name: str
    description: str
    defaults: Mapping[str, Any] = field(default_factory=dict)

    def build(self, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return the profile defaults merged with optional overrides."""

        base = deepcopy(dict(self.defaults))
        if overrides:
            return _deep_merge(base, overrides)
        return base


class DevelopmentProfile(ConfigProfile):
    def __init__(self) -> None:
        super().__init__(
            name=ProfileName.DEVELOPMENT.value,
            description="Local development with reloads, debug logging, and permissive CORS.",
            defaults={
                "profile": ProfileName.DEVELOPMENT.value,
                "app_name": "Agentic Brain",
                "version": "3.1.1",
                "debug": True,
                "server": {
                    "reload": True,
                    "workers": 1,
                    "docs_enabled": True,
                    "cors_origins": ["http://localhost:3000"],
                },
                "llm": {
                    "default_provider": "ollama",
                },
                "observability": {
                    "enable_tracing": True,
                    "enable_metrics": True,
                    "log_level": "DEBUG",
                    "log_format": "text",
                },
                "cache": {
                    "backend": "memory",
                },
                "security": {
                    "cors_enabled": True,
                    "allowed_origins": ["http://localhost:3000"],
                    "rate_limit_requests": 100,
                },
                "features": {
                    "rag_enabled": True,
                    "voice_enabled": True,
                    "neo4j_enabled": True,
                    "api_enabled": True,
                    "observability_enabled": True,
                    "local_llm_enabled": True,
                },
            },
        )


class StagingProfile(ConfigProfile):
    def __init__(self) -> None:
        super().__init__(
            name=ProfileName.STAGING.value,
            description="Staging-like validation with production-ish defaults.",
            defaults={
                "profile": ProfileName.STAGING.value,
                "app_name": "Agentic Brain",
                "version": "3.1.1",
                "debug": False,
                "server": {
                    "reload": False,
                    "workers": 2,
                    "docs_enabled": True,
                    "cors_origins": ["http://localhost:3000"],
                },
                "observability": {
                    "enable_tracing": True,
                    "enable_metrics": True,
                    "log_level": "INFO",
                    "log_format": "json",
                },
                "cache": {
                    "backend": "redis",
                },
                "security": {
                    "cors_enabled": True,
                    "allowed_origins": ["http://localhost:3000"],
                    "rate_limit_requests": 100,
                },
            },
        )


class ProductionProfile(ConfigProfile):
    def __init__(self) -> None:
        super().__init__(
            name=ProfileName.PRODUCTION.value,
            description="Hardened production defaults with JSON logs and Redis cache.",
            defaults={
                "profile": ProfileName.PRODUCTION.value,
                "app_name": "Agentic Brain",
                "version": "3.1.1",
                "debug": False,
                "server": {
                    "reload": False,
                    "workers": 4,
                    "docs_enabled": False,
                    "cors_origins": [],
                },
                "llm": {
                    "default_provider": "ollama",
                },
                "observability": {
                    "enable_tracing": True,
                    "enable_metrics": True,
                    "log_level": "WARNING",
                    "log_format": "json",
                },
                "cache": {
                    "backend": "redis",
                },
                "security": {
                    "cors_enabled": True,
                    "allowed_origins": [],
                    "rate_limit_requests": 100,
                },
                "features": {
                    "rag_enabled": True,
                    "voice_enabled": True,
                    "neo4j_enabled": True,
                    "api_enabled": True,
                    "observability_enabled": True,
                    "local_llm_enabled": True,
                },
            },
        )


class TestingProfile(ConfigProfile):
    def __init__(self) -> None:
        super().__init__(
            name=ProfileName.TESTING.value,
            description="Fast deterministic settings for automated test runs.",
            defaults={
                "profile": ProfileName.TESTING.value,
                "app_name": "Agentic Brain",
                "version": "3.1.1",
                "debug": True,
                "server": {
                    "reload": False,
                    "workers": 1,
                    "docs_enabled": True,
                    "cors_origins": ["http://localhost:3000"],
                },
                "neo4j": {
                    "database": "test",
                },
                "observability": {
                    "enable_tracing": False,
                    "enable_metrics": False,
                    "log_level": "DEBUG",
                    "log_format": "text",
                },
                "cache": {
                    "backend": "memory",
                },
                "security": {
                    "cors_enabled": True,
                    "allowed_origins": ["http://localhost:3000"],
                    "rate_limit_requests": 10,
                },
                "features": {
                    "rag_enabled": True,
                    "voice_enabled": False,
                    "neo4j_enabled": True,
                    "api_enabled": True,
                    "observability_enabled": False,
                    "local_llm_enabled": True,
                },
            },
        )


@dataclass(frozen=True, slots=True)
class CustomProfile(ConfigProfile):
    """User-defined profile with arbitrary defaults."""

    name: str
    description: str = "Custom configuration profile"
    defaults: Mapping[str, Any] = field(default_factory=dict)


BUILTIN_PROFILES: tuple[ConfigProfile, ...] = (
    DevelopmentProfile(),
    StagingProfile(),
    ProductionProfile(),
    TestingProfile(),
)

PROFILE_ALIASES: dict[str, str] = {
    "dev": ProfileName.DEVELOPMENT.value,
    "development": ProfileName.DEVELOPMENT.value,
    "prod": ProfileName.PRODUCTION.value,
    "production": ProfileName.PRODUCTION.value,
    "test": ProfileName.TESTING.value,
    "testing": ProfileName.TESTING.value,
    "stage": ProfileName.STAGING.value,
    "staging": ProfileName.STAGING.value,
    "custom": ProfileName.CUSTOM.value,
}


def available_profiles() -> tuple[ConfigProfile, ...]:
    """Return the built-in profiles in priority order."""

    return BUILTIN_PROFILES


def get_profile(profile: ConfigProfile | str | None) -> ConfigProfile:
    """Resolve a profile object from a name or existing profile instance."""

    if profile is None:
        return DevelopmentProfile()
    if isinstance(profile, ConfigProfile):
        return profile

    normalized = profile.strip().lower()
    profile_name = PROFILE_ALIASES.get(normalized, normalized)
    if profile_name == ProfileName.DEVELOPMENT.value:
        return DevelopmentProfile()
    if profile_name == ProfileName.PRODUCTION.value:
        return ProductionProfile()
    if profile_name == ProfileName.TESTING.value:
        return TestingProfile()
    if profile_name == ProfileName.STAGING.value:
        return StagingProfile()
    return CustomProfile(name=profile_name or ProfileName.CUSTOM.value)
