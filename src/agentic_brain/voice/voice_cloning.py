# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import importlib
import logging
import platform
import subprocess
import wave
from array import array
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import time
from typing import Any, Callable

from agentic_brain.voice.voice_library import SYSTEM_VOICE_BY_LADY, VoiceLibrary

logger = logging.getLogger(__name__)

BackendFactory = Callable[[], Any]


@dataclass(slots=True)
class VoiceValidationResult:
    ok: bool
    format: str = "unknown"
    duration_seconds: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    sample_width_bytes: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert validation result to dictionary.
        
        Returns:
            Dictionary representation of validation results.
        """
        return asdict(self)


class VoiceCloner:
    """Voice cloning system using F5-TTS with fallback to system voices.
    
    Manages voice profiles, validates audio quality, and synthesizes speech
    using either F5-TTS neural voice cloning or system voice fallbacks.
    """
    
    def __init__(
        self,
        *,
        library: VoiceLibrary | None = None,
        base_dir: str | Path | None = None,
        backend_factory: BackendFactory | None = None,
        fallback_voice: str = "Karen (Premium)",
    ) -> None:
        """Initialize voice cloner.
        
        Args:
            library: Voice library instance.
            base_dir: Base directory for voice storage.
            backend_factory: Optional F5-TTS backend factory.
            fallback_voice: System voice to use when F5-TTS unavailable.
        """
        self.library = library or VoiceLibrary(base_dir=base_dir)
        self._backend_factory = backend_factory
        self._fallback_voice = fallback_voice
        self._engine: Any = None

    @property
    def is_f5_available(self) -> bool:
        """Check if F5-TTS backend is available.
        
        Returns:
            True if F5-TTS can be imported.
        """
        if self._backend_factory is not None:
            return True
        try:
            importlib.import_module("f5_tts.api")
        except Exception:
            return False
        return True

    def clone_voice(
        self,
        audio_sample_path: str | Path,
        *,
        name: str | None = None,
        reference_text: str = "",
        assigned_lady: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Clone a voice from audio sample.
        
        Validates audio quality and registers the voice profile.
        
        Args:
            audio_sample_path: Path to reference audio file.
            name: Display name for the voice.
            reference_text: Transcript of reference audio.
            assigned_lady: Lady identifier to assign to.
            metadata: Additional metadata.
            
        Returns:
            Generated voice_id.
            
        Raises:
            ValueError: If audio validation fails.
        """
        sample_path = Path(audio_sample_path).expanduser()
        validation = self.validate_voice_quality(sample_path)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors) or "Invalid reference audio")

        profile = self.library.register_voice(
            source_audio=sample_path,
            name=name or sample_path.stem,
            reference_text=reference_text,
            assigned_lady=assigned_lady,
            backend="f5-tts" if self.is_f5_available else "stored-reference",
            validation=validation.to_dict(),
            metadata=metadata or {},
        )
        return profile.voice_id

    def synthesize_with_voice(
        self,
        text: str,
        voice_id: str,
        *,
        output_path: str | Path | None = None,
    ) -> Path:
        """Synthesize speech using a cloned voice.
        
        Uses F5-TTS if available, falls back to system voices.
        
        Args:
            text: Text to synthesize.
            voice_id: Voice profile identifier.
            output_path: Optional output file path.
            
        Returns:
            Path to generated audio file.
            
        Raises:
            ValueError: If text is empty.
            KeyError: If voice_id not found.
        """
        if not text.strip():
            raise ValueError("Text is required for synthesis")

        profile = self.library.get_voice(voice_id)
        if profile is None:
            raise KeyError(voice_id)

        target_path = self._resolve_output_path(voice_id, output_path)
        if self.is_f5_available:
            try:
                return self._synthesize_with_f5(
                    text=text, profile=profile, output_path=target_path
                )
            except Exception as exc:
                logger.warning("F5-TTS synthesis failed for %s: %s", voice_id, exc)

        return self._synthesize_with_fallback(
            text=text,
            profile=profile,
            output_path=target_path,
        )

    def validate_voice_quality(self, audio_path: str | Path) -> VoiceValidationResult:
        """Validate reference audio quality for voice cloning.
        
        Checks duration, sample rate, channels, and signal presence.
        
        Args:
            audio_path: Path to audio file.
            
        Returns:
            VoiceValidationResult with validation details.
        """
        path = Path(audio_path).expanduser()
        if not path.exists():
            return VoiceValidationResult(
                ok=False, errors=[f"Audio sample not found: {path}"]
            )

        if path.stat().st_size == 0:
            return VoiceValidationResult(ok=False, errors=["Audio sample is empty"])

        suffix = path.suffix.lower()
        if suffix not in {".wav", ".wave"}:
            warnings = [
                "Could not fully inspect audio container; using file-level checks only"
            ]
            if path.stat().st_size < 1024:
                return VoiceValidationResult(
                    ok=False,
                    format=suffix.lstrip(".") or "unknown",
                    errors=["Audio sample is too small to be usable"],
                    warnings=warnings,
                )
            return VoiceValidationResult(
                ok=True,
                format=suffix.lstrip(".") or "unknown",
                warnings=warnings,
            )

        try:
            with wave.open(str(path), "rb") as handle:
                sample_rate = handle.getframerate()
                frames = handle.getnframes()
                channels = handle.getnchannels()
                sample_width = handle.getsampwidth()
                duration = frames / float(sample_rate) if sample_rate else 0.0
                preview = handle.readframes(min(frames, sample_rate))
        except wave.Error as exc:
            return VoiceValidationResult(ok=False, format="wav", errors=[str(exc)])

        warnings: list[str] = []
        errors: list[str] = []

        if duration < 0.3:
            errors.append("Reference audio is too short; use at least 0.3 seconds")
        elif duration < 1.0:
            warnings.append("Reference audio is very short; 3-12 seconds works best")

        if duration > 12.0:
            warnings.append(
                "Reference audio exceeds 12 seconds; F5-TTS usually clips long prompts"
            )

        if sample_rate < 16_000:
            warnings.append("Sample rate below 16 kHz may reduce clone quality")

        if channels > 2:
            warnings.append(
                "More than 2 channels detected; mono or stereo is preferred"
            )

        if sample_width not in {1, 2, 4}:
            warnings.append("Uncommon sample width detected")

        if preview and not self._has_signal(preview, sample_width):
            warnings.append("Audio appears almost silent")

        return VoiceValidationResult(
            ok=not errors,
            format="wav",
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            sample_width_bytes=sample_width,
            errors=errors,
            warnings=warnings,
        )

    def _has_signal(self, preview: bytes, sample_width: int) -> bool:
        """Check if audio preview contains actual signal.
        
        Args:
            preview: Audio bytes preview.
            sample_width: Sample width in bytes.
            
        Returns:
            True if audio has detectable signal above noise floor.
        """
        if sample_width == 1:
            data = array("B", preview)
            return any(abs(sample - 128) > 2 for sample in data[:4000])
        if sample_width == 2:
            data = array("h")
        elif sample_width == 4:
            data = array("i")
        else:
            return bool(preview)
        data.frombytes(preview[: min(len(preview), 16_000)])
        return any(abs(sample) > 32 for sample in data[:4000])

    def _resolve_output_path(
        self, voice_id: str, output_path: str | Path | None
    ) -> Path:
        """Resolve output path for synthesized audio.
        
        Args:
            voice_id: Voice identifier.
            output_path: Optional explicit output path.
            
        Returns:
            Resolved path in renders directory if not specified.
        """
        if output_path is not None:
            target = Path(output_path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            return target

        render_dir = self.library.voice_dir(voice_id) / "renders"
        render_dir.mkdir(parents=True, exist_ok=True)
        return render_dir / f"{int(time() * 1000)}.wav"

    def _get_engine(self) -> Any:
        """Get or create F5-TTS engine instance.
        
        Returns:
            F5-TTS engine instance.
        """
        if self._engine is not None:
            return self._engine

        if self._backend_factory is not None:
            self._engine = self._backend_factory()
            return self._engine

        module = importlib.import_module("f5_tts.api")
        self._engine = module.F5TTS()
        return self._engine

    def _synthesize_with_f5(
        self, *, text: str, profile: Any, output_path: Path
    ) -> Path:
        """Synthesize using F5-TTS neural voice cloning.
        
        Args:
            text: Text to synthesize.
            profile: Voice profile.
            output_path: Output file path.
            
        Returns:
            Path to generated audio file.
            
        Raises:
            RuntimeError: If generated audio fails validation.
        """
        final_path = (
            output_path
            if output_path.suffix.lower() == ".wav"
            else output_path.with_suffix(".wav")
        )
        final_path.parent.mkdir(parents=True, exist_ok=True)
        engine = self._get_engine()
        engine.infer(
            ref_file=str(profile.reference_audio),
            ref_text=profile.reference_text or "",
            gen_text=text,
            file_wave=str(final_path),
        )

        validation = self.validate_voice_quality(final_path)
        if not validation.ok:
            raise RuntimeError(
                "; ".join(validation.errors) or "Generated audio failed validation"
            )
        return final_path

    def _synthesize_with_fallback(
        self, *, text: str, profile: Any, output_path: Path
    ) -> Path:
        """Synthesize using system voice fallback.
        
        Args:
            text: Text to synthesize.
            profile: Voice profile.
            output_path: Output file path.
            
        Returns:
            Path to generated audio (or silence WAV on failure).
        """
        fallback_voice = profile.metadata.get("fallback_voice")
        if not fallback_voice and profile.assigned_lady:
            fallback_voice = SYSTEM_VOICE_BY_LADY.get(
                profile.assigned_lady, self._fallback_voice
            )
        fallback_voice = fallback_voice or self._fallback_voice

        try:
            if platform.system() == "Darwin":
                return self._synthesize_with_system_voice(
                    text, fallback_voice, output_path
                )
        except Exception as exc:
            logger.warning(
                "System voice fallback failed for %s: %s", profile.voice_id, exc
            )

        return self._write_silence_wav(
            output_path
            if output_path.suffix.lower() == ".wav"
            else output_path.with_suffix(".wav")
        )

    def _synthesize_with_system_voice(
        self,
        text: str,
        voice_name: str,
        output_path: Path,
    ) -> Path:
        """Synthesize using macOS system voice.
        
        Args:
            text: Text to synthesize.
            voice_name: System voice name.
            output_path: Output file path.
            
        Returns:
            Path to generated AIFF file.
            
        Raises:
            RuntimeError: If synthesis fails.
        """
        final_path = (
            output_path
            if output_path.suffix.lower() in {".aif", ".aiff"}
            else output_path.with_suffix(".aiff")
        )
        final_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["say", "-v", voice_name, "-o", str(final_path), text],
            check=True,
            capture_output=True,
            text=True,
        )
        if not final_path.exists():
            raise RuntimeError("System speech synthesis did not create an audio file")
        return final_path

    def _write_silence_wav(
        self,
        output_path: Path,
        *,
        duration_seconds: float = 0.5,
        sample_rate: int = 24_000,
    ) -> Path:
        """Write a silence WAV file as last-resort fallback.
        
        Args:
            output_path: Output file path.
            duration_seconds: Duration of silence.
            sample_rate: Audio sample rate.
            
        Returns:
            Path to generated silence WAV.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames = max(1, int(duration_seconds * sample_rate))
        with wave.open(str(output_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(b"\x00\x00" * frames)
        return output_path


__all__ = ["VoiceCloner", "VoiceValidationResult"]
