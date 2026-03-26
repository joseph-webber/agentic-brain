# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""End-to-end integration tests for critical agentic-brain subsystems."""

from __future__ import annotations

import asyncio
import importlib
import shutil
from pathlib import Path

import pytest

import agentic_brain.voice.config as voice_config
from agentic_brain.cli import main as cli_main
from agentic_brain.voice.queue import VoiceQueue, get_queue_size
from agentic_brain.voice.regional import RegionalVoice
from agentic_brain.voice.resilient import ResilientVoice


@pytest.mark.integration
def test_voice_actually_works():
    """Queue a real voice message and ensure resilient fallback can speak."""
    if shutil.which("say") is None:
        pytest.skip("macOS 'say' command is required for this voice integration test")

    queue = VoiceQueue.get_instance()
    queue.reset()

    message = queue.speak(
        "Integration voice test for Joseph.",
        voice="Karen",
        rate=150,
        pause_after=0.05,
    )

    assert message.voice == "Karen"
    assert message.text.startswith("Integration voice test")

    history = queue.get_history()
    assert history, "voice history should include the spoken message"
    assert history[-1].voice == "Karen"
    assert get_queue_size() == 0

    result = asyncio.run(
        ResilientVoice.speak(
            "Voice fallback integration verification.", voice="Karen", rate=150
        )
    )
    assert result is True

    stats = ResilientVoice.get_stats()
    assert stats, "voice stats should be populated after speaking"
    assert any(entry["success"] or entry["failure"] for entry in stats.values())


@pytest.mark.integration
def test_regional_profiles_persist_and_regionalize(tmp_path: Path):
    """Ensure Adelaide regional profile customisations persist to disk."""
    config_dir = tmp_path / "regional"
    rv = RegionalVoice(config_dir=str(config_dir))

    region_file = config_dir / "location.json"
    assert region_file.exists()
    assert "Adelaide" in rv.region_name

    localized = rv.regionalize(
        "This is a great day and thank you for visiting our beach."
    )
    assert localized != "This is a great day and thank you for visiting our beach."
    assert "heaps" in localized.lower() or "cheers" in localized.lower()

    greeting = rv.get_greeting()
    assert greeting

    rv.add_expression("sunset", "golden Glenelg sunset")
    updated = rv.regionalize("The sunset is great in Adelaide.")
    assert "golden glenelg sunset" in updated.lower()

    rv.add_local_knowledge("coffee", "Flat whites and Farmers Union Iced Coffee")
    knowledge = rv.get_local_knowledge("coffee")
    assert knowledge
    assert "flat white" in knowledge.lower()


@pytest.mark.integration
def test_config_loading_honors_environment(monkeypatch: pytest.MonkeyPatch):
    """VoiceConfig should read values from environment variables."""
    monkeypatch.setenv("AGENTIC_BRAIN_VOICE", "Moira")
    monkeypatch.setenv("AGENTIC_BRAIN_LANGUAGE", "en-IE")
    monkeypatch.setenv("AGENTIC_BRAIN_RATE", "148")
    monkeypatch.setenv("AGENTIC_BRAIN_PITCH", "1.25")
    monkeypatch.setenv("AGENTIC_BRAIN_VOLUME", "0.6")
    monkeypatch.setenv("AGENTIC_BRAIN_VOICE_PROVIDER", "cloud")
    monkeypatch.setenv("AGENTIC_BRAIN_VOICE_ENABLED", "false")
    monkeypatch.setenv("AGENTIC_BRAIN_VOICE_QUALITY", "standard")

    config_module = importlib.reload(voice_config)
    config = config_module.VoiceConfig()

    assert config.voice_name == "Moira"
    assert config.language == "en-IE"
    assert config.rate == 148
    assert config.pitch == 1.25
    assert config.volume == 0.6
    assert config.provider == "cloud"
    assert config.enabled is False
    assert config.quality == config_module.VoiceQuality.STANDARD


@pytest.mark.integration
def test_cli_version_command_executes(capsys: pytest.CaptureFixture[str]):
    """Run the real CLI entrypoint and ensure it reports version info."""
    exit_code = cli_main(["version"])
    assert exit_code == 0

    captured = capsys.readouterr().out
    assert "Agentic Brain" in captured
    assert "Version:" in captured
