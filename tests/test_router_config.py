# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
CI tests for the LLM router configuration, provider availability checks,
model alias mappings, and template definitions.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from agentic_brain.model_aliases import MODEL_ALIASES, resolve_alias
from agentic_brain.router import Provider, RouterConfig
from agentic_brain.router import provider_checker as provider_checker_module
from agentic_brain.router.provider_checker import ProviderChecker

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_FILES = sorted(TEMPLATE_DIR.glob("llm-*.env"))


def _load_env_template(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def test_router_config_defaults_are_sensible():
    """RouterConfig provides expected defaults for CI verification."""
    config = RouterConfig()

    assert config.default_provider == Provider.OLLAMA
    assert config.default_model == "llama3.1:8b"
    assert config.max_retries == 3
    assert config.fallback_enabled is True
    assert config.cache_enabled is True


def test_router_config_allows_custom_timeouts_without_side_effects():
    """Per-provider timeouts can be overridden without affecting other instances."""
    tuned = RouterConfig(ollama_timeout=30, openai_timeout=15, anthropic_timeout=240)
    default = RouterConfig()

    assert tuned.ollama_timeout == 30
    assert tuned.openai_timeout == 15
    assert tuned.anthropic_timeout == 240

    # Ensure defaults remain intact for new instances
    assert default.ollama_timeout == 120
    assert default.openai_timeout == 60
    assert default.anthropic_timeout == 90


def test_router_config_reads_ollama_host_from_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    """OLLAMA_HOST environment variable should be respected."""
    monkeypatch.setenv("OLLAMA_HOST", "http://router.test:1234")
    config = RouterConfig()
    assert config.ollama_host == "http://router.test:1234"


@pytest.mark.parametrize(
    ("alias", "expected_provider"),
    [
        ("L1", "ollama"),
        ("OP", "openai"),
        ("CL", "anthropic"),
        ("GR", "groq"),
    ],
)
def test_model_aliases_map_to_expected_providers(alias: str, expected_provider: str):
    """Model alias helpers should return accurate provider mappings."""
    resolved = resolve_alias(alias)
    assert resolved["provider"] == expected_provider
    assert resolved["model"]


def test_global_fallback_chain_uses_known_aliases():
    """Fallback chains must only reference aliases defined in MODEL_ALIASES."""
    from agentic_brain.model_aliases import FALLBACK_CHAIN

    assert FALLBACK_CHAIN, "Fallback chain should not be empty"
    for alias in FALLBACK_CHAIN:
        assert (
            alias in MODEL_ALIASES
        ), f"Fallback alias '{alias}' missing from MODEL_ALIASES"


def test_provider_checker_ollama_handles_installed_and_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    """ProviderChecker should differentiate between installed and missing Ollama."""

    # Scenario 1: Ollama binary missing
    monkeypatch.setattr(provider_checker_module.shutil, "which", lambda _: None)
    status = ProviderChecker.check_ollama()
    assert status.available is False
    assert "not found" in status.reason.lower()

    # Scenario 2: Ollama installed and responding
    class _DummyResponse:
        status = 200

    def fake_urlopen(*_args, **_kwargs):
        return _DummyResponse()

    monkeypatch.setattr(
        provider_checker_module.shutil, "which", lambda _: "/usr/bin/ollama"
    )
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    status = ProviderChecker.check_ollama()
    assert status.available is True


def test_provider_checker_openai_respects_environment(monkeypatch: pytest.MonkeyPatch):
    """OPENAI_API_KEY environment variable should drive availability."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    status = ProviderChecker.check_openai()
    assert status.available is False
    assert "not set" in status.reason.lower()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-value")
    status = ProviderChecker.check_openai()
    assert status.available is True


@pytest.mark.parametrize("template_file", TEMPLATE_FILES)
def test_llm_templates_reference_known_aliases(template_file: Path):
    """Each LLM template should reference aliases that exist in MODEL_ALIASES."""
    env_vars = _load_env_template(template_file)

    assert "DEFAULT_MODEL" in env_vars, f"{template_file.name} missing DEFAULT_MODEL"
    default_alias = env_vars["DEFAULT_MODEL"].strip().upper()
    assert (
        default_alias in MODEL_ALIASES
    ), f"Unknown alias '{default_alias}' in {template_file.name}"

    fallback_chain = env_vars.get("FALLBACK_CHAIN", "")
    assert fallback_chain, f"{template_file.name} missing FALLBACK_CHAIN"
    aliases = [
        alias.strip().upper() for alias in fallback_chain.split(",") if alias.strip()
    ]
    assert aliases, f"{template_file.name} has empty FALLBACK_CHAIN"

    for alias in aliases:
        assert (
            alias in MODEL_ALIASES
        ), f"Template {template_file.name} references unknown alias '{alias}'"
