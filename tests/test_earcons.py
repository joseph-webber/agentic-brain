# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scipy.io import wavfile

import agentic_brain.audio as audio_module
from agentic_brain.audio import Audio, AudioConfig
from agentic_brain.audio.earcons import (
    DEFAULT_EARCON_VOLUME,
    DEFAULT_SPEECH_VOLUME,
    EARCON_ALIASES,
    EARCONS,
    MAX_DURATION_SECONDS,
    SAMPLE_RATE,
    SOUND_DIR,
    Earcon,
    EarconPlayer,
    canonical_earcon_name,
    ensure_earcons_exist,
    get_earcon_config,
)
from agentic_brain.audio.sound_themes import (
    DEFAULT_SOUND_THEME,
    SOUND_THEMES,
    get_sound_theme,
    list_sound_themes,
)
from agentic_brain.cli import create_parser
from agentic_brain.cli.audio_commands import audio_earcon_command

REQUIRED_EARCONS = {
    "success",
    "error",
    "waiting",
    "mode_switch",
    "attention_needed",
    "speech_start",
    "speech_end",
    "agent_deployed",
    "agent_completed",
    "system_ready",
}


class TestEarconMetadata:
    def test_required_earcons_exist(self):
        assert set(EARCONS) == REQUIRED_EARCONS

    def test_all_required_earcons_are_short(self):
        assert all(
            config.duration_seconds < MAX_DURATION_SECONDS
            for config in EARCONS.values()
        )

    def test_default_earcon_volume_is_quieter_than_speech(self):
        assert DEFAULT_EARCON_VOLUME < DEFAULT_SPEECH_VOLUME

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("task_done", "success"),
            ("thinking", "waiting"),
            ("notification", "attention_needed"),
            ("utterance_start", "speech_start"),
            ("queue_empty", "agent_completed"),
        ],
    )
    def test_aliases_resolve_to_canonical_names(self, alias, expected):
        assert canonical_earcon_name(alias) == expected

    def test_alias_map_contains_backwards_compatible_names(self):
        assert "task_done" in EARCON_ALIASES
        assert "thinking" in EARCON_ALIASES
        assert "new_message" in EARCON_ALIASES

    def test_unknown_earcon_raises_value_error(self):
        with pytest.raises(ValueError):
            canonical_earcon_name("not-real")


class TestSoundThemes:
    def test_theme_registry_contains_required_themes(self):
        assert set(SOUND_THEMES) == {"minimal", "expressive", "silent"}

    def test_default_theme_is_minimal(self):
        assert DEFAULT_SOUND_THEME == "minimal"

    def test_minimal_theme_is_quieter_than_expressive(self):
        assert get_sound_theme("minimal").apply(
            DEFAULT_EARCON_VOLUME
        ) < get_sound_theme("expressive").apply(DEFAULT_EARCON_VOLUME)

    def test_silent_theme_disables_playback(self):
        silent = get_sound_theme("silent")
        assert silent.enabled is False
        assert silent.apply(DEFAULT_EARCON_VOLUME) == 0.0

    def test_list_sound_themes_returns_expected_names(self):
        assert list_sound_themes() == ("expressive", "minimal", "silent")

    def test_unknown_sound_theme_raises_value_error(self):
        with pytest.raises(ValueError):
            get_sound_theme("party")


class TestEarconGeneration:
    @pytest.mark.parametrize("name", sorted(REQUIRED_EARCONS))
    def test_generator_creates_mono_audio(self, name):
        signal = EARCONS[name].generator()
        assert signal.ndim == 1
        assert signal.size > 0
        assert float(signal.max()) <= 1.0
        assert float(signal.min()) >= -1.0

    @pytest.mark.parametrize("name", sorted(REQUIRED_EARCONS))
    def test_generator_duration_is_under_half_second(self, name):
        signal = EARCONS[name].generator()
        assert signal.size / SAMPLE_RATE < MAX_DURATION_SECONDS

    def test_ensure_earcons_exist_writes_all_required_files(self):
        generated = ensure_earcons_exist(force=True)
        assert set(generated) == REQUIRED_EARCONS

    @pytest.mark.parametrize("name", sorted(REQUIRED_EARCONS))
    def test_generated_files_exist_and_match_sample_rate(self, name):
        generated = ensure_earcons_exist(force=True)
        sample_rate, data = wavfile.read(generated[name])
        assert sample_rate == SAMPLE_RATE
        assert data.ndim == 1

    @pytest.mark.parametrize("name", sorted(REQUIRED_EARCONS))
    def test_generated_files_are_short(self, name):
        generated = ensure_earcons_exist(force=True)
        _, data = wavfile.read(generated[name])
        assert len(data) / SAMPLE_RATE < MAX_DURATION_SECONDS

    def test_packaged_sound_directory_exists(self):
        ensure_earcons_exist(SOUND_DIR, force=True)
        assert SOUND_DIR.exists()


class TestEarconPlayer:
    def test_path_for_uses_sound_directory(self):
        player = EarconPlayer()
        assert player.path_for("success") == SOUND_DIR / "success.wav"

    def test_path_for_accepts_alias(self):
        player = EarconPlayer()
        assert player.path_for("task_done") == SOUND_DIR / "success.wav"

    def test_effective_volume_uses_theme_and_gain(self):
        player = EarconPlayer(volume=0.3, theme="minimal")
        assert player.effective_volume_for("speech_start") < 0.3

    def test_set_theme_updates_effective_volume(self):
        player = EarconPlayer(volume=0.3, theme="minimal")
        quiet = player.effective_volume_for("success")
        player.set_theme("expressive")
        loud = player.effective_volume_for("success")
        assert loud > quiet

    def test_disable_and_enable_toggle_playback(self):
        player = EarconPlayer()
        player.disable()
        assert player.enabled is False
        player.enable()
        assert player.enabled is True

    @patch("agentic_brain.audio.earcons.subprocess.run")
    @patch("agentic_brain.audio.earcons.shutil.which")
    def test_play_blocking_uses_afplay_with_quiet_volume(self, mock_which, mock_run):
        mock_which.side_effect = lambda cmd: (
            "/usr/bin/afplay" if cmd == "afplay" else None
        )
        mock_run.return_value = MagicMock(returncode=0)
        player = EarconPlayer(volume=0.22, theme="minimal")

        result = player.play("success", blocking=True)

        assert result is True
        command = mock_run.call_args.args[0]
        assert command[0] == "afplay"
        assert float(command[2]) < DEFAULT_SPEECH_VOLUME
        assert Path(command[3]).name == "success.wav"

    @patch("agentic_brain.audio.earcons.threading.Thread")
    def test_play_async_creates_daemon_thread(self, mock_thread):
        thread = MagicMock()
        mock_thread.return_value = thread
        player = EarconPlayer()

        returned = player.play_async("agent_completed")

        assert returned is thread
        _, kwargs = mock_thread.call_args
        assert kwargs["daemon"] is True
        assert kwargs["name"] == "earcon-agent_completed"
        thread.start.assert_called_once()

    def test_play_returns_false_when_disabled(self):
        player = EarconPlayer(enabled=False)
        assert player.play("success", blocking=True) is False

    def test_silent_theme_returns_false(self):
        player = EarconPlayer(theme="silent")
        assert player.play("success", blocking=True) is False


class TestEarconObject:
    def test_earcon_play_delegates_to_player(self):
        player = MagicMock()
        player.play.return_value = True
        earcon = Earcon(name="success", player=player)

        assert earcon.play() is True
        player.play.assert_called_once_with("success", blocking=True)

    def test_earcon_play_async_delegates_to_player(self):
        player = MagicMock()
        thread = MagicMock()
        player.play_async.return_value = thread
        earcon = Earcon(name="waiting", player=player)

        assert earcon.play_async() is thread
        player.play_async.assert_called_once_with("waiting")

    def test_earcon_config_property_returns_metadata(self):
        earcon = Earcon(name="mode_switch", player=MagicMock())
        assert earcon.config == get_earcon_config("mode_switch")


class TestAudioIntegration:
    def test_audio_earcon_respects_disabled_config(self):
        audio = Audio(AudioConfig(earcons_enabled=False))
        assert audio.earcon("success") is False

    def test_audio_earcon_passes_theme_to_player(self):
        audio = Audio(AudioConfig(earcon_theme="expressive"))
        player = audio._get_earcon_player()
        assert player.theme.name == "expressive"

    def test_module_level_earcon_uses_default_audio(self):
        audio_module._default_audio = Audio()
        audio_module._default_audio._earcon_player = MagicMock()
        audio_module._default_audio._earcon_player.play.return_value = True

        result = audio_module.earcon("success")

        assert result is True
        audio_module._default_audio._earcon_player.play.assert_called_once_with(
            "success",
            blocking=False,
        )


class TestAudioCli:
    def test_cli_parser_accepts_audio_earcon_command(self):
        parser = create_parser()
        args = parser.parse_args(["audio", "earcon", "success"])
        assert args.command == "audio"
        assert args.audio_subcommand == "earcon"
        assert args.name == "success"

    @patch("agentic_brain.cli.audio_commands.EarconPlayer")
    def test_audio_earcon_command_plays_requested_earcon(self, mock_player_cls):
        mock_player = MagicMock()
        mock_player.play.return_value = True
        mock_player.effective_volume_for.return_value = 0.14
        mock_player_cls.return_value = mock_player
        args = create_parser().parse_args(["audio", "earcon", "success"])

        result = audio_earcon_command(args)

        assert result == 0
        mock_player.play.assert_called_once_with("success", blocking=True)

    def test_audio_earcon_list_command_succeeds(self, capsys):
        args = create_parser().parse_args(["audio", "earcon", "--list"])

        result = audio_earcon_command(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "success" in captured.out
        assert "system_ready" in captured.out
