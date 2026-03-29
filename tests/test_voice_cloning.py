from __future__ import annotations

import argparse
import shutil
import wave
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from agentic_brain.cli import create_parser
from agentic_brain.cli.voice_commands import voice_clone_command
from agentic_brain.voice.voice_cloning import VoiceCloner
from agentic_brain.voice.voice_library import VoiceLibrary, resolve_voice_storage_dir


def _create_test_wav(
    path: Path,
    *,
    duration_seconds: float = 1.0,
    sample_rate: int = 24_000,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(duration_seconds * sample_rate))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x10\x00" * frame_count)
    return path


class FakeF5TTS:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def infer(
        self,
        *,
        ref_file: str,
        ref_text: str,
        gen_text: str,
        file_wave: str,
        **_: object,
    ):
        self.calls.append(
            {
                "ref_file": ref_file,
                "ref_text": ref_text,
                "gen_text": gen_text,
                "file_wave": file_wave,
            }
        )
        _create_test_wav(Path(file_wave), duration_seconds=0.75)
        return [0], 24_000, None


@pytest.fixture
def voice_workspace():
    root = Path.cwd() / ".test-artifacts" / "voice-cloning" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def configured_env(monkeypatch, voice_workspace):
    clone_dir = voice_workspace / "voice-store"
    monkeypatch.setenv("AGENTIC_BRAIN_VOICE_CLONE_DIR", str(clone_dir))
    return clone_dir


class TestVoiceValidation:
    def test_resolve_storage_dir_uses_env(self, configured_env):
        assert resolve_voice_storage_dir() == configured_env

    def test_validate_missing_file(self, configured_env):
        cloner = VoiceCloner(base_dir=configured_env)
        result = cloner.validate_voice_quality(configured_env / "missing.wav")
        assert result.ok is False
        assert result.errors

    def test_validate_valid_wave(self, configured_env, voice_workspace):
        sample = _create_test_wav(voice_workspace / "sample.wav", duration_seconds=1.2)
        cloner = VoiceCloner(base_dir=configured_env)
        result = cloner.validate_voice_quality(sample)
        assert result.ok is True
        assert result.format == "wav"
        assert result.duration_seconds == pytest.approx(1.2, rel=0.01)

    def test_validate_warns_for_short_audio(self, configured_env, voice_workspace):
        sample = _create_test_wav(voice_workspace / "short.wav", duration_seconds=0.6)
        cloner = VoiceCloner(base_dir=configured_env)
        result = cloner.validate_voice_quality(sample)
        assert result.ok is True
        assert any("very short" in warning for warning in result.warnings)

    def test_validate_warns_for_long_audio(self, configured_env, voice_workspace):
        sample = _create_test_wav(voice_workspace / "long.wav", duration_seconds=12.5)
        cloner = VoiceCloner(base_dir=configured_env)
        result = cloner.validate_voice_quality(sample)
        assert result.ok is True
        assert any("12 seconds" in warning for warning in result.warnings)


class TestVoiceLibraryManagement:
    def test_clone_voice_persists_profile(self, configured_env, voice_workspace):
        sample = _create_test_wav(voice_workspace / "clone.wav")
        cloner = VoiceCloner(base_dir=configured_env)
        voice_id = cloner.clone_voice(sample, name="Custom Karen")
        profile = cloner.library.get_voice(voice_id)
        assert profile is not None
        assert profile.name == "Custom Karen"
        assert profile.reference_audio.exists()

    def test_clone_voice_uses_f5_backend_name_when_available(
        self,
        configured_env,
        voice_workspace,
    ):
        sample = _create_test_wav(voice_workspace / "clone.wav")
        cloner = VoiceCloner(base_dir=configured_env, backend_factory=FakeF5TTS)
        voice_id = cloner.clone_voice(sample, name="F5 Karen")
        profile = cloner.library.get_voice(voice_id)
        assert profile is not None
        assert profile.backend == "f5-tts"

    def test_list_voices_returns_sorted_profiles(self, configured_env, voice_workspace):
        library = VoiceLibrary(base_dir=configured_env)
        first = _create_test_wav(voice_workspace / "b.wav")
        second = _create_test_wav(voice_workspace / "a.wav")
        library.register_voice(source_audio=first, name="Zed")
        library.register_voice(source_audio=second, name="Alice")
        names = [profile.name for profile in library.list_voices()]
        assert names == ["Alice", "Zed"]

    def test_delete_voice_removes_profile(self, configured_env, voice_workspace):
        library = VoiceLibrary(base_dir=configured_env)
        sample = _create_test_wav(voice_workspace / "delete.wav")
        profile = library.register_voice(source_audio=sample, name="Delete Me")
        assert library.delete_voice(profile.voice_id) is True
        assert library.get_voice(profile.voice_id) is None

    def test_assign_voice_to_lady_updates_profile(
        self, configured_env, voice_workspace
    ):
        library = VoiceLibrary(base_dir=configured_env)
        sample = _create_test_wav(voice_workspace / "assign.wav")
        profile = library.register_voice(source_audio=sample, name="Assign Me")
        updated = library.assign_voice(profile.voice_id, "karen")
        assert updated.assigned_lady == "karen"
        assert updated.metadata["fallback_voice"] == "Karen (Premium)"

    def test_find_by_lady_filters_profiles(self, configured_env, voice_workspace):
        library = VoiceLibrary(base_dir=configured_env)
        one = _create_test_wav(voice_workspace / "one.wav")
        two = _create_test_wav(voice_workspace / "two.wav")
        profile_one = library.register_voice(
            source_audio=one, name="One", assigned_lady="karen"
        )
        library.register_voice(source_audio=two, name="Two", assigned_lady="moira")
        matches = library.find_by_lady("karen")
        assert [profile.voice_id for profile in matches] == [profile_one.voice_id]

    def test_export_voice_creates_zip_archive(self, configured_env, voice_workspace):
        library = VoiceLibrary(base_dir=configured_env)
        sample = _create_test_wav(voice_workspace / "export.wav")
        profile = library.register_voice(source_audio=sample, name="Export Me")
        archive = library.export_voice(profile.voice_id, voice_workspace / "voice.zip")
        assert archive.exists()
        with zipfile.ZipFile(archive, "r") as handle:
            assert "profile.json" in handle.namelist()

    def test_import_voice_restores_profile(self, configured_env, voice_workspace):
        source_library = VoiceLibrary(base_dir=voice_workspace / "source")
        sample = _create_test_wav(voice_workspace / "import.wav")
        profile = source_library.register_voice(source_audio=sample, name="Import Me")
        archive = source_library.export_voice(
            profile.voice_id, voice_workspace / "import.zip"
        )

        target_library = VoiceLibrary(base_dir=configured_env)
        imported = target_library.import_voice(archive)
        assert imported.name == "Import Me"
        assert imported.reference_audio.exists()
        assert imported.metadata["imported_from"].endswith("import.zip")


class TestVoiceSynthesis:
    def test_synthesize_with_f5_backend_writes_wav(
        self, configured_env, voice_workspace
    ):
        sample = _create_test_wav(voice_workspace / "ref.wav")
        fake_backend = FakeF5TTS()
        cloner = VoiceCloner(
            base_dir=configured_env, backend_factory=lambda: fake_backend
        )
        voice_id = cloner.clone_voice(
            sample, name="Synth Voice", reference_text="hello there"
        )
        output = cloner.synthesize_with_voice("Generated text", voice_id)
        assert output.exists()
        assert output.suffix == ".wav"
        assert fake_backend.calls[0]["ref_text"] == "hello there"

    def test_synthesize_with_voice_raises_for_unknown_id(self, configured_env):
        cloner = VoiceCloner(base_dir=configured_env)
        with pytest.raises(KeyError):
            cloner.synthesize_with_voice("Hello", "missing-voice")

    def test_synthesize_with_voice_uses_fallback_when_f5_unavailable(
        self,
        configured_env,
        voice_workspace,
        monkeypatch,
    ):
        sample = _create_test_wav(voice_workspace / "fallback.wav")
        cloner = VoiceCloner(base_dir=configured_env)
        voice_id = cloner.clone_voice(
            sample, name="Fallback Voice", assigned_lady="moira"
        )

        def fake_system_voice(text: str, voice_name: str, output_path: Path) -> Path:
            assert text == "Fallback text"
            assert voice_name == "Moira"
            return cloner._write_silence_wav(
                output_path.with_suffix(".wav"), duration_seconds=0.4
            )

        monkeypatch.setattr(cloner, "_synthesize_with_system_voice", fake_system_voice)
        output = cloner.synthesize_with_voice("Fallback text", voice_id)
        assert output.exists()
        assert output.suffix == ".wav"

    def test_synthesize_with_voice_rejects_blank_text(
        self, configured_env, voice_workspace
    ):
        sample = _create_test_wav(voice_workspace / "blank.wav")
        cloner = VoiceCloner(base_dir=configured_env)
        voice_id = cloner.clone_voice(sample, name="Blank")
        with pytest.raises(ValueError):
            cloner.synthesize_with_voice("   ", voice_id)


class TestVoiceCloneCLI:
    def test_parser_accepts_clone_command(self):
        parser = create_parser()
        args = parser.parse_args(
            ["voice", "clone", "sample.wav", "--name", "custom_karen"]
        )
        assert args.command == "voice"
        assert args.voice_subcommand == "clone"
        assert args.audio_file == "sample.wav"
        assert args.name == "custom_karen"

    def test_cli_clone_creates_voice(self, configured_env, voice_workspace, capsys):
        sample = _create_test_wav(voice_workspace / "cli-clone.wav")
        args = argparse.Namespace(
            audio_file=str(sample),
            name="CLI Clone",
            reference_text="",
            list=False,
            delete=None,
            assign=None,
            lady="karen",
        )
        result = voice_clone_command(args)
        output = capsys.readouterr().out
        assert result == 0
        assert "Voice clone created" in output

    def test_cli_clone_list_outputs_profiles(
        self, configured_env, voice_workspace, capsys
    ):
        sample = _create_test_wav(voice_workspace / "cli-list.wav")
        VoiceLibrary(base_dir=configured_env).register_voice(
            source_audio=sample,
            name="Listed Voice",
        )
        args = argparse.Namespace(
            audio_file=None,
            name=None,
            reference_text="",
            list=True,
            delete=None,
            assign=None,
            lady=None,
        )
        result = voice_clone_command(args)
        output = capsys.readouterr().out
        assert result == 0
        assert "Listed Voice" in output

    def test_cli_clone_delete_removes_voice(self, configured_env, voice_workspace):
        library = VoiceLibrary(base_dir=configured_env)
        sample = _create_test_wav(voice_workspace / "cli-delete.wav")
        profile = library.register_voice(source_audio=sample, name="Delete Voice")
        args = argparse.Namespace(
            audio_file=None,
            name=None,
            reference_text="",
            list=False,
            delete=profile.voice_id,
            assign=None,
            lady=None,
        )
        result = voice_clone_command(args)
        assert result == 0
        assert library.get_voice(profile.voice_id) is None

    def test_cli_clone_assign_updates_lady(
        self, configured_env, voice_workspace, capsys
    ):
        library = VoiceLibrary(base_dir=configured_env)
        sample = _create_test_wav(voice_workspace / "cli-assign.wav")
        profile = library.register_voice(source_audio=sample, name="Assign Voice")
        args = argparse.Namespace(
            audio_file=None,
            name=None,
            reference_text="",
            list=False,
            delete=None,
            assign=profile.voice_id,
            lady="karen",
        )
        result = voice_clone_command(args)
        output = capsys.readouterr().out
        updated = library.get_voice(profile.voice_id)
        assert result == 0
        assert "Assigned" in output
        assert updated is not None and updated.assigned_lady == "karen"

    def test_cli_clone_assign_requires_lady(
        self, configured_env, voice_workspace, capsys
    ):
        library = VoiceLibrary(base_dir=configured_env)
        sample = _create_test_wav(voice_workspace / "cli-assign-missing.wav")
        profile = library.register_voice(source_audio=sample, name="Assign Missing")
        args = argparse.Namespace(
            audio_file=None,
            name=None,
            reference_text="",
            list=False,
            delete=None,
            assign=profile.voice_id,
            lady=None,
        )
        result = voice_clone_command(args)
        output = capsys.readouterr().out
        assert result == 1
        assert "--lady is required" in output
