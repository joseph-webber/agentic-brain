from __future__ import annotations

from pathlib import Path

import pytest

import agentic_brain.config.profiles as config_profiles

from agentic_brain.config import (
    CustomProfile,
    DevelopmentProfile,
    ProductionProfile,
    Settings,
    get_settings,
)


def test_get_settings_caches_instances():
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()

    assert first is second


def test_environment_properties_for_testing_profile():
    settings = Settings.from_sources(
        profile=config_profiles.TestingProfile(),
        env_file=Path("/nonexistent/env-file"),
    )

    assert settings.profile == "testing"
    assert settings.environment.value == "test"
    assert settings.is_test is True
    assert settings.is_dev is False


def test_custom_profile_sets_custom_environment():
    profile = CustomProfile(
        name="eu-ops",
        defaults={
            "app_name": "EU Ops Brain",
            "server": {"port": 9010},
            "cache": {"backend": "sqlite"},
        },
    )

    settings = Settings.from_sources(
        profile=profile,
        config_file=Path("/nonexistent/config-file.yaml"),
        env_file=Path("/nonexistent/env-file"),
    )

    assert settings.profile == "eu-ops"
    assert settings.is_custom is True
    assert settings.app_name == "EU Ops Brain"
    assert settings.server.port == 9010
    assert settings.cache.backend.value == "sqlite"


def test_production_profile_rejects_weak_secret():
    with pytest.raises(ValueError, match="production requires a strong JWT secret"):
        Settings.from_sources(
            profile=ProductionProfile(),
            env_file=Path("/nonexistent/env-file"),
        )


def test_production_profile_loads_when_secret_is_strong(tmp_path: Path):
    config_file = tmp_path / "brain-config.yaml"
    config_file.write_text(
        """
security:
  jwt_secret: super-long-production-secret-value-1234567890
  allowed_origins: []
server:
  cors_origins: []
""",
        encoding="utf-8",
    )

    settings = Settings.from_sources(
        profile=ProductionProfile(),
        config_file=config_file,
        env_file=Path("/nonexistent/env-file"),
    )

    assert settings.is_prod is True
    assert settings.security.jwt_secret.get_secret_value().startswith(
        "super-long-production-secret-value"
    )


def test_production_profile_rejects_wildcard_origins(tmp_path: Path):
    config_file = tmp_path / "brain-config.yaml"
    config_file.write_text(
        """
security:
  jwt_secret: super-long-production-secret-value-1234567890
  allowed_origins:
    - "*"
server:
  cors_origins:
    - "*"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="wildcard"):
        Settings.from_sources(
            profile=ProductionProfile(),
            config_file=config_file,
            env_file=Path("/nonexistent/env-file"),
        )


def test_development_profile_defaults_apply():
    settings = Settings.from_sources(
        profile=DevelopmentProfile(),
        env_file=Path("/nonexistent/env-file"),
    )

    assert settings.profile == "development"
    assert settings.is_dev is True
    assert settings.server.reload is True


def test_get_settings_respects_environment_profile(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BRAIN_PROFILE", "testing")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.profile == "testing"
    assert settings.is_test is True


def test_api_alias_returns_server_model():
    settings = Settings.from_sources(env_file=Path("/nonexistent/env-file"))

    assert settings.api is settings.server
