# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for robot/novelty voice support in agentic-brain."""

import pytest

from agentic_brain.voice.queue import VoiceQueue, speak_system_message
from agentic_brain.voice.registry import ROBOT_VOICES


def test_robot_voices_registry_basic():
    """Robot voice presets should be defined with expected structure."""

    for key in ["zarvox", "trinoids", "ralph", "bad_news", "whisper"]:
        assert key in ROBOT_VOICES
        meta = ROBOT_VOICES[key]
        assert "name" in meta and isinstance(meta["name"], str)
        assert "type" in meta and isinstance(meta["type"], str)
        assert "gender" in meta and isinstance(meta["gender"], str)
        assert "description" in meta and isinstance(meta["description"], str)
        assert "use_for" in meta and isinstance(meta["use_for"], list)


@pytest.mark.asyncio
async def test_speak_system_message_voice_mapping(monkeypatch):
    """System messages should select appropriate robot/novelty voices."""

    last_call = {}

    def fake_speak(
        self,
        text,
        voice="Karen",
        rate=None,
        pause_after=1.5,
        speaker_id=None,
        importance=0,
    ):
        last_call["text"] = text
        last_call["voice"] = voice
        last_call["rate"] = rate
        last_call["pause_after"] = pause_after
        last_call["speaker_id"] = speaker_id
        last_call["importance"] = importance

        class DummyMsg:
            pass

        return DummyMsg()

    monkeypatch.setattr(VoiceQueue, "speak", fake_speak, raising=True)

    # Error → Bad News
    await speak_system_message("Error occurred", severity="error")
    assert last_call["voice"] == "Bad News"
    assert last_call["rate"] == 130
    assert last_call["speaker_id"] == "system:error"
    assert last_call["importance"] == 1

    # Warning → Zarvox
    await speak_system_message("Warning", severity="warning")
    assert last_call["voice"] == "Zarvox"
    assert last_call["speaker_id"] == "system:warning"

    # Success → Ralph
    await speak_system_message("All good", severity="success")
    assert last_call["voice"] == "Ralph"
    assert last_call["speaker_id"] == "system:success"

    # Info / default → Trinoids
    await speak_system_message("Info message", severity="info")
    assert last_call["voice"] == "Trinoids"
    assert last_call["speaker_id"] == "system:info"

    # Unknown severity falls back to Zarvox
    await speak_system_message("Unknown", severity="other")
    assert last_call["voice"] == "Zarvox"
    assert last_call["speaker_id"] == "system:other"
