# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from agentic_brain.config import Settings


def test_load_settings_uses_development_profile_by_default(tmp_path: Path):
    settings = Settings.from_sources(
        base_path=tmp_path, env_file=tmp_path / "missing.env"
    )

    assert settings.profile == "development"
    assert settings.is_dev is True
    assert settings.server.reload is True


def test_load_settings_reads_yaml_config_file(tmp_path: Path):
    config_file = tmp_path / "brain-config.yaml"
    config_file.write_text(
        """
profile: development
app_name: YAML Brain
debug: false
server:
  port: 9001
  cors_origins:
    - https://example.com
llm:
  default_model: mistral
security:
  allowed_origins:
    - https://example.com
""",
        encoding="utf-8",
    )

    settings = Settings.from_sources(
        config_file=config_file,
        env_file=tmp_path / "missing.env",
    )

    assert settings.app_name == "YAML Brain"
    assert settings.server.port == 9001
    assert settings.llm.default_model == "mistral"
    assert settings.security.allowed_origins == ["https://example.com"]


def test_load_settings_reads_toml_config_file(tmp_path: Path):
    config_file = tmp_path / "brain-config.toml"
    config_file.write_text(
        """
profile = "testing"
app_name = "TOML Brain"
debug = true

[server]
port = 9100
reload = false
docs_enabled = true
cors_origins = ["https://toml.example"]

[neo4j]
database = "toml-test"
""",
        encoding="utf-8",
    )

    settings = Settings.from_sources(
        config_file=config_file,
        env_file=tmp_path / "missing.env",
    )

    assert settings.profile == "testing"
    assert settings.app_name == "TOML Brain"
    assert settings.server.port == 9100
    assert settings.neo4j.database == "toml-test"


def test_load_settings_normalizes_api_alias(tmp_path: Path):
    config_file = tmp_path / "brain-config.yaml"
    config_file.write_text(
        """
api:
  port: 8300
  base_path: /brain
  cors_origins:
    - https://api.example.com
""",
        encoding="utf-8",
    )

    settings = Settings.from_sources(
        config_file=config_file,
        env_file=tmp_path / "missing.env",
    )

    assert settings.server.port == 8300
    assert settings.server.base_path == "/brain"
    assert settings.server.cors_origins == ["https://api.example.com"]


def test_load_settings_reads_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
APP_NAME=Dotenv Brain
SERVER_PORT=9200
VOICE_RATE=170
CORS_ORIGINS=https://one.example,https://two.example
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings.from_sources(base_path=tmp_path, env_file=env_file)

    assert settings.app_name == "Dotenv Brain"
    assert settings.server.port == 9200
    assert settings.voice.rate == 170
    assert settings.security.allowed_origins == [
        "https://one.example",
        "https://two.example",
    ]


def test_profile_specific_dotenv_file_is_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    env_file = tmp_path / ".env.testing"
    env_file.write_text("VOICE_ENABLED=false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = Settings.from_sources(profile="testing", env_file=env_file)

    assert settings.profile == "testing"
    assert settings.voice.enabled is False


def test_environment_variables_override_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    env_file = tmp_path / ".env"
    env_file.write_text("SERVER_PORT=9000\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SERVER_PORT", "9300")

    settings = Settings.from_sources(
        base_path=tmp_path,
        env_file=tmp_path / "missing.env",
    )

    assert settings.server.port == 9300


def test_environment_variables_override_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_file = tmp_path / "brain-config.yaml"
    config_file.write_text("llm:\n  default_model: yaml-model\n", encoding="utf-8")
    monkeypatch.setenv("LLM_DEFAULT_MODEL", "env-model")

    settings = Settings.from_sources(
        config_file=config_file,
        env_file=tmp_path / "missing.env",
    )

    assert settings.llm.default_model == "env-model"


def test_comma_separated_origins_from_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://first.example,https://second.example",
    )

    settings = Settings.from_sources(env_file=Path("/nonexistent/env-file"))

    assert settings.server.cors_origins == [
        "https://first.example",
        "https://second.example",
    ]
    assert settings.security.allowed_origins == [
        "https://first.example",
        "https://second.example",
    ]


def test_missing_config_file_falls_back_to_defaults(tmp_path: Path):
    settings = Settings.from_sources(
        config_file=tmp_path / "missing.yaml",
        env_file=tmp_path / "missing.env",
    )

    assert settings.app_name == "Agentic Brain"
    assert settings.server.base_path == "/api"


def test_unsupported_config_file_extension_raises(tmp_path: Path):
    config_file = tmp_path / "brain-config.json"
    config_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported configuration file format"):
        Settings.from_sources(
            config_file=config_file, env_file=tmp_path / "missing.env"
        )
