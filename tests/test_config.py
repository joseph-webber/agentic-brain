# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for JHipster-style configuration management."""

import os
from unittest.mock import patch

import pytest

from agentic_brain.config import (
    CacheSettings,
    Environment,
    LLMSettings,
    Neo4jSettings,
    ObservabilitySettings,
    SecuritySettings,
    Settings,
    get_settings,
)


class TestEnvironment:
    """Tests for Environment enum."""

    def test_environment_values(self):
        """Test all environment values exist."""
        assert Environment.DEV.value == "dev"
        assert Environment.STAGING.value == "staging"
        assert Environment.PROD.value == "prod"
        assert Environment.TEST.value == "test"


class TestNeo4jSettings:
    """Tests for Neo4j configuration."""

    def test_default_values(self):
        """Test Neo4j defaults."""
        settings = Neo4jSettings()
        assert settings.uri == "bolt://localhost:7687"
        assert settings.user == "neo4j"
        assert settings.database == "neo4j"
        assert settings.max_connection_pool_size == 50

    @patch.dict(os.environ, {"NEO4J_URI": "bolt://custom:7687"})
    def test_env_override(self):
        """Test environment variable override."""
        settings = Neo4jSettings()
        assert settings.uri == "bolt://custom:7687"


class TestLLMSettings:
    """Tests for LLM configuration."""

    def test_default_values(self):
        """Test LLM defaults."""
        settings = LLMSettings()
        assert settings.default_provider == "ollama"
        assert settings.default_model == "llama3.2:3b"
        assert settings.timeout == 60
        assert settings.max_retries == 3

    def test_api_keys_optional(self):
        """Test API keys are optional."""
        settings = LLMSettings()
        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None


class TestSecuritySettings:
    """Tests for security configuration."""

    def test_default_values(self):
        """Test security defaults."""
        settings = SecuritySettings()
        assert settings.jwt_algorithm == "HS512"
        assert settings.jwt_expiration_hours == 24
        assert settings.password_min_length == 12
        assert settings.rate_limit_requests == 100


class TestObservabilitySettings:
    """Tests for observability configuration."""

    def test_default_values(self):
        """Test observability defaults."""
        settings = ObservabilitySettings()
        assert settings.enable_tracing is True
        assert settings.enable_metrics is True
        assert settings.log_level == "INFO"
        assert settings.service_name == "agentic-brain"


class TestCacheSettings:
    """Tests for cache configuration."""

    def test_default_values(self):
        """Test cache defaults."""
        settings = CacheSettings()
        assert settings.backend == "memory"
        assert settings.default_ttl == 3600
        assert settings.semantic_cache_enabled is False


class TestSettings:
    """Tests for main Settings class."""

    def test_default_environment(self):
        """Test default environment is dev."""
        settings = Settings()
        assert settings.environment == Environment.DEV
        assert settings.is_dev is True
        assert settings.is_prod is False

    def test_nested_settings(self):
        """Test nested settings are created."""
        settings = Settings()
        assert isinstance(settings.neo4j, Neo4jSettings)
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.security, SecuritySettings)

    def test_environment_validation(self):
        """Test environment string validation."""
        settings = Settings(environment="prod")
        assert settings.environment == Environment.PROD
        assert settings.is_prod is True

    def test_invalid_environment_defaults_to_dev(self):
        """Test invalid environment defaults to dev."""
        settings = Settings(environment="invalid")
        assert settings.environment == Environment.DEV

    @patch.dict(os.environ, {"ENVIRONMENT": "staging"})
    def test_environment_from_env_var(self):
        """Test environment from environment variable."""
        # Clear cache to reload settings
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.environment == Environment.STAGING
        get_settings.cache_clear()  # Clean up


class TestGetSettings:
    """Tests for get_settings function."""

    def test_settings_cached(self):
        """Test settings are cached."""
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()

    def test_returns_settings_instance(self):
        """Test returns Settings instance."""
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)
        get_settings.cache_clear()
