# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scipy.io import wavfile

import agentic_brain.audio as audio_module
from agentic_brain.audio import Audio, AudioConfig
from agentic_brain.audio.earcons import (
    DEFAULT_EARCON_VOLUME,
    EARCON_DIR,
    EARCON_GENERATORS,
    MAX_DURATION_SECONDS,
    SAMPLE_RATE,
    EarconPlayer,
    ensure_earcons_exist,
)


class TestEarconGeneration:
    @pytest.mark.parametrize(
        ("name", "generator"),
        sorted(EARCON_GENERATORS.items()),
    )
    def test_generators_create_short_normalized_audio(self, name, generator):
        signal = generator()

        assert signal.ndim == 1, name
        assert signal.size > 0, name
        assert signal.size <= int(SAMPLE_RATE * MAX_DURATION_SECONDS), name
        assert float(signal.max()) <= 1.0, name
        assert float(signal.min()) >= -1.0, name

    def test_ensure_earcons_exist_writes_expected_files(self):
        generated = ensure_earcons_exist(force=True)

        assert set(generated) == set(EARCON_GENERATORS)
        for path in generated.values():
            assert path.exists()
            sample_rate, data = wavfile.read(path)
            assert sample_rate == SAMPLE_RATE
            assert data.ndim == 1
            assert (len(data) / SAMPLE_RATE) <= MAX_DURATION_SECONDS


class TestEarconPlayer:
    @patch("agentic_brain.audio.earcons.subprocess.run")
    @patch("agentic_brain.audio.earcons.shutil.which")
    @patch("agentic_brain.audio.earcons.platform.system")
    def test_play_blocking_uses_afplay(self, mock_system, mock_which, mock_run):
        mock_system.return_value = "Darwin"
        mock_which.return_value = "/usr/bin/afplay"
        mock_run.return_value = MagicMock(returncode=0)

        player = EarconPlayer(volume=DEFAULT_EARCON_VOLUME)
        result = player.play("task_started", blocking=True)

        assert result is True
        command = mock_run.call_args.args[0]
        assert command[:3] == ["afplay", "-v", "0.30"]
        assert Path(command[3]).name == "task_started.wav"

    @patch("agentic_brain.audio.earcons.threading.Thread")
    def test_play_non_blocking_starts_daemon_thread(self, mock_thread):
        player = EarconPlayer()
        thread = MagicMock()
        mock_thread.return_value = thread

        result = player.play("task_done")

        assert result is True
        mock_thread.assert_called_once()
        _, kwargs = mock_thread.call_args
        assert kwargs["daemon"] is True
        assert kwargs["name"] == "earcon-task_done"
        thread.start.assert_called_once()

    def test_unknown_earcon_raises_value_error(self):
        player = EarconPlayer()
        with pytest.raises(ValueError):
            player.play("not-real", blocking=True)


class TestAudioIntegration:
    def test_audio_earcon_respects_config(self):
        audio = Audio(AudioConfig(earcons_enabled=False))
        assert audio.earcon("task_started") is False

    def test_audio_earcon_delegates_to_player(self):
        audio = Audio()
        audio._earcon_player = MagicMock()
        audio._earcon_player.play.return_value = True

        result = audio.earcon("attention_needed", blocking=True)

        assert result is True
        audio._earcon_player.play.assert_called_once_with(
            "attention_needed",
            blocking=True,
        )

    def test_module_level_earcon_uses_default_audio(self):
        audio_module._default_audio = Audio()
        audio_module._default_audio._earcon_player = MagicMock()
        audio_module._default_audio._earcon_player.play.return_value = True

        result = audio_module.earcon("new_message")

        assert result is True
        audio_module._default_audio._earcon_player.play.assert_called_once_with(
            "new_message",
            blocking=False,
        )


def test_packaged_earcon_directory_exists():
    ensure_earcons_exist(EARCON_DIR, force=True)
    assert EARCON_DIR.exists()
