# SPDX-License-Identifier: Apache-2.0
#
# Tests for stereo panning of voice personas.

from pathlib import Path
from types import SimpleNamespace

from agentic_brain.audio.stereo_pan import (
    LADY_PAN_POSITIONS,
    PannedAudio,
    StereoPanner,
    get_pan_position,
    resolve_lady_name,
)
from agentic_brain.voice.serializer import VoiceMessage, get_voice_serializer


def _repo_test_cache() -> Path:
    return Path(__file__).resolve().parent / ".cache_stereo_pan"


def test_resolve_lady_name_handles_aliases():
    assert resolve_lady_name("Ting-Ting") == "Tingting"
    assert resolve_lady_name("Karen (Premium)") == "Karen"
    assert resolve_lady_name("Amelie") == "Flo"


def test_get_pan_position_returns_expected_values():
    assert get_pan_position("Karen") == 0.0
    assert get_pan_position("Zosia") == LADY_PAN_POSITIONS["Zosia"]
    assert get_pan_position("unknown voice") == 0.0


def test_pan_audio_builds_expected_sox_command(monkeypatch):
    scratch_dir = _repo_test_cache()
    panner = StereoPanner(
        sox_path=Path("/opt/homebrew/bin/sox"),
        temp_dir=scratch_dir,
    )
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append((cmd, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("agentic_brain.audio.stereo_pan.subprocess.run", fake_run)

    output = panner.pan_audio(Path("voice.aiff"), "Zosia")

    assert output.parent == scratch_dir
    command, kwargs = commands[0]
    assert command[:4] == [
        "/opt/homebrew/bin/sox",
        "voice.aiff",
        str(output),
        "remix",
    ]
    assert command[4:] == ["1v0.88", "1v0.12"]
    assert kwargs["check"] is True


def test_render_panned_speech_generates_say_then_sox(monkeypatch):
    scratch_dir = _repo_test_cache()
    panner = StereoPanner(
        sox_path=Path("/opt/homebrew/bin/sox"),
        temp_dir=scratch_dir,
    )
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        if "-o" in cmd:
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"mono")
        elif len(cmd) >= 3 and cmd[0] == "/opt/homebrew/bin/sox":
            Path(cmd[2]).write_bytes(b"stereo")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("agentic_brain.audio.stereo_pan.subprocess.run", fake_run)

    panned_audio = panner.render_panned_speech(
        text="Hello Joseph",
        lady="Karen",
        voice="Karen (Premium)",
        rate=160,
    )

    assert commands[0][:6] == ["say", "-v", "Karen (Premium)", "-r", "160", "-o"]
    assert commands[1][:4] == [
        "/opt/homebrew/bin/sox",
        commands[0][6],
        str(panned_audio.path),
        "remix",
    ]
    assert panned_audio.lady == "Karen"
    assert panned_audio.pan == 0.0
    assert panned_audio.path.exists()
    panner.cleanup_audio(panned_audio.path)


def test_serializer_uses_stereo_pan_when_enabled(monkeypatch):
    from agentic_brain.voice.serializer import VoiceSerializer

    serializer = VoiceSerializer()
    serializer._audit_enabled = False
    calls = {}

    class FakePanner:
        def is_available(self):
            return True

        def render_panned_speech(self, text, lady, voice, rate):
            calls["render"] = (text, lady, voice, rate)
            return PannedAudio(
                path=Path(
                    "/Users/joe/brain/agentic-brain/tests/fixtures/panned_voice.aiff"
                ),
                lady=lady,
                pan=0.4,
            )

        def cleanup_audio(self, path):
            calls["cleanup"] = path

    class FakeProcess:
        def wait(self):
            return 0

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        calls["popen"] = cmd
        return FakeProcess()

    monkeypatch.setattr(
        "agentic_brain.voice.serializer.shutil.which", lambda _: "/usr/bin/say"
    )
    monkeypatch.setattr(
        "agentic_brain.voice.serializer.stereo_pan_enabled", lambda: True
    )
    monkeypatch.setattr(
        "agentic_brain.voice.serializer.get_stereo_panner",
        lambda: FakePanner(),
    )
    monkeypatch.setattr("agentic_brain.voice.serializer.subprocess.Popen", fake_popen)

    result = serializer._speak_with_say(
        VoiceMessage(text="Hello", voice="Karen", lady="Karen", rate=155)
    )

    assert result is True
    assert calls["render"] == ("Hello", "Karen", "Karen", 155)
    assert calls["popen"] == [
        "afplay",
        "/Users/joe/brain/agentic-brain/tests/fixtures/panned_voice.aiff",
    ]
    assert calls["cleanup"] == Path(
        "/Users/joe/brain/agentic-brain/tests/fixtures/panned_voice.aiff"
    )


def test_serializer_falls_back_to_say_when_pan_disabled(monkeypatch):
    serializer = get_voice_serializer()
    serializer._audit_enabled = False
    commands = []

    class FakeProcess:
        def wait(self):
            return 0

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess()

    monkeypatch.setattr(
        "agentic_brain.voice.serializer.shutil.which", lambda _: "/usr/bin/say"
    )
    monkeypatch.setattr(
        "agentic_brain.voice.serializer.stereo_pan_enabled", lambda: False
    )
    monkeypatch.setattr("agentic_brain.voice.serializer.subprocess.Popen", fake_popen)

    result = serializer._speak_with_say(
        VoiceMessage(text="Fallback", voice="Karen", rate=150)
    )

    assert result is True
    assert commands == [["say", "-v", "Karen", "-r", "150", "Fallback"]]
