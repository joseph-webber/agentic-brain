# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_brain.config.settings import (
    CacheBackend,
    CacheSettings,
    LLMSettings,
    LogFormat,
    LogLevel,
    Neo4jSettings,
    ObservabilitySettings,
    ProviderName,
    SecuritySettings,
    ServerSettings,
    Settings,
    VoiceProvider,
    VoiceSettings,
)


def test_neo4j_settings_defaults():
    settings = Neo4jSettings()

    assert settings.uri == "bolt://localhost:7687"
    assert settings.user == "neo4j"
    assert settings.database == "neo4j"


def test_neo4j_settings_rejects_bad_uri():
    with pytest.raises(ValidationError):
        Neo4jSettings(uri="http://localhost:7687")


def test_llm_settings_defaults():
    settings = LLMSettings()

    assert settings.default_provider == ProviderName.OLLAMA
    assert settings.default_model == "llama3.2:3b"
    assert settings.max_retries == 3


def test_llm_settings_rejects_negative_retries():
    with pytest.raises(ValidationError):
        LLMSettings(max_retries=-1)


def test_voice_settings_defaults():
    settings = VoiceSettings()

    assert settings.provider == VoiceProvider.SYSTEM
    assert settings.rate == 160
    assert settings.volume == 0.8


def test_voice_settings_rejects_out_of_range_rate():
    with pytest.raises(ValidationError):
        VoiceSettings(rate=10)


def test_security_settings_accepts_valid_origins():
    settings = SecuritySettings(allowed_origins=["https://example.com"])

    assert settings.allowed_origins == ["https://example.com"]


def test_security_settings_rejects_invalid_origins():
    with pytest.raises(ValidationError):
        SecuritySettings(allowed_origins=["not-a-url"])


def test_observability_settings_defaults():
    settings = ObservabilitySettings()

    assert settings.log_level == LogLevel.INFO
    assert settings.log_format == LogFormat.JSON


def test_cache_settings_defaults():
    settings = CacheSettings()

    assert settings.backend == CacheBackend.MEMORY
    assert settings.semantic_similarity_threshold == 0.95


def test_cache_settings_rejects_invalid_threshold():
    with pytest.raises(ValidationError):
        CacheSettings(semantic_similarity_threshold=1.5)


def test_server_settings_defaults():
    settings = ServerSettings()

    assert settings.port == 8000
    assert settings.base_path == "/api"


def test_server_settings_rejects_invalid_port():
    with pytest.raises(ValidationError):
        ServerSettings(port=70000)


def test_settings_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Settings.model_validate({"unexpected": True})


def test_settings_validation_supports_production_secret_rules():
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "profile": "production",
                "security": {
                    "jwt_secret": "change-me-in-production-use-a-strong-secret"
                },
            }
        )
