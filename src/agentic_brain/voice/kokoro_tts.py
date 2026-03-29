# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
KokoroVoice – High-level Kokoro-82M neural TTS for the 14 ladies.

Wraps ``kokoro-onnx`` (ONNX runtime, 20-50× realtime on M2) with
automatic fallback to the base ``kokoro`` package, then to Apple
``say``.  Installation is **optional** — the rest of the brain
continues working when Kokoro is absent.

Usage::

    from agentic_brain.voice.kokoro_tts import KokoroVoice

    voice = KokoroVoice()          # lazy – no model loaded yet
    audio = voice.synthesize("Hello Joseph", "Karen")
    voice.synthesize_to_file("こんにちは", "Kyoko", Path("out.wav"))

Every lady maps to a distinct Kokoro voice ID that matches her
personality, accent, and origin language.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import subprocess
import time
import wave
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

KOKORO_SAMPLE_RATE = 24_000

# ── Lady → Kokoro voice mapping ─────────────────────────────────────
#
# Each lady gets a unique voice that matches her personality and origin.
# Voice IDs are from the official Kokoro-82M VOICES.md catalogue.
# Prefix convention: af_=American female, bf_=British female,
# jf_=Japanese female, zf_=Chinese female, ff_=French female,
# if_=Italian female.

LADY_VOICES: Dict[str, Dict[str, str]] = {
    "Karen": {
        "voice_id": "af_heart",
        "lang_code": "a",
        "description": "Warm Australian lead — confident, direct",
    },
    "Kyoko": {
        "voice_id": "jf_alpha",
        "lang_code": "j",
        "description": "Japanese quality analyst — precise, gentle",
    },
    "Tingting": {
        "voice_id": "zf_xiaoxiao",
        "lang_code": "z",
        "description": "Chinese analytics — fast, solution-focused",
    },
    "Yuna": {
        "voice_id": "af_bella",
        "lang_code": "a",
        "description": "Korean tech — bright, encouraging",
    },
    "Linh": {
        "voice_id": "bf_alice",
        "lang_code": "b",
        "description": "Vietnamese Adelaide guide — warm, helpful",
    },
    "Kanya": {
        "voice_id": "af_nicole",
        "lang_code": "a",
        "description": "Thai wellness — calm, caring",
    },
    "Dewi": {
        "voice_id": "bf_emma",
        "lang_code": "b",
        "description": "Indonesian Jakarta — modern, upbeat",
    },
    "Sari": {
        "voice_id": "bf_isabella",
        "lang_code": "b",
        "description": "Javanese culture — thoughtful, measured",
    },
    "Wayan": {
        "voice_id": "af_sarah",
        "lang_code": "a",
        "description": "Balinese spiritual — serene, reflective",
    },
    "Moira": {
        "voice_id": "af_aoede",
        "lang_code": "a",
        "description": "Irish creative — warm, lyrical",
    },
    "Alice": {
        "voice_id": "if_sara",
        "lang_code": "i",
        "description": "Italian food & culture — expressive, musical",
    },
    "Zosia": {
        "voice_id": "af_nova",
        "lang_code": "a",
        "description": "Polish security — crisp, authoritative",
    },
    "Flo": {
        "voice_id": "ff_siwis",
        "lang_code": "f",
        "description": "French code review — refined, precise",
    },
    "Shelley": {
        "voice_id": "bf_lily",
        "lang_code": "b",
        "description": "British deployment — friendly, dependable",
    },
}

# Apple say fallback voices per lady
_APPLE_FALLBACKS: Dict[str, str] = {
    "Karen": "Karen (Premium)",
    "Kyoko": "Kyoko",
    "Tingting": "Tingting",
    "Yuna": "Yuna",
    "Linh": "Linh",
    "Kanya": "Kanya",
    "Dewi": "Damayanti",
    "Sari": "Damayanti",
    "Wayan": "Damayanti",
    "Moira": "Moira",
    "Alice": "Alice",
    "Zosia": "Zosia",
    "Flo": "Amelie",
    "Shelley": "Shelley",
}


def kokoro_available() -> bool:
    """Check if any Kokoro backend is importable (no model load)."""
    try:
        import importlib.util

        if importlib.util.find_spec("kokoro_onnx") is not None:
            return True
        if importlib.util.find_spec("kokoro") is not None:
            return True
    except Exception:
        pass
    return False


def detect_m2_acceleration() -> Dict[str, Any]:
    """Detect Apple Silicon M-series chip and available acceleration.

    Returns a dict with keys: ``is_apple_silicon``, ``chip_name``,
    ``has_ane`` (Apple Neural Engine), ``has_mps`` (Metal Performance
    Shaders), ``onnx_providers`` (ordered list for ONNX Runtime).
    """
    result: Dict[str, Any] = {
        "is_apple_silicon": False,
        "chip_name": "unknown",
        "has_ane": False,
        "has_mps": False,
        "onnx_providers": ["CPUExecutionProvider"],
    }

    if platform.system() != "Darwin" or platform.machine() not in ("arm64", "aarch64"):
        return result

    result["is_apple_silicon"] = True

    try:
        chip = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        result["chip_name"] = chip.stdout.strip() or "Apple Silicon"
    except Exception:
        result["chip_name"] = "Apple Silicon"

    result["has_ane"] = True

    try:
        import importlib.util

        if importlib.util.find_spec("torch") is not None:
            import torch

            result["has_mps"] = (
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            )
    except Exception:
        pass

    try:
        import importlib.util

        if importlib.util.find_spec("onnxruntime") is not None:
            import onnxruntime as ort

            available = ort.get_available_providers()
            providers = []
            if "CoreMLExecutionProvider" in available:
                providers.append("CoreMLExecutionProvider")
            providers.append("CPUExecutionProvider")
            result["onnx_providers"] = providers
    except Exception:
        pass

    return result


class KokoroVoice:
    """High-level Kokoro-82M TTS with lazy init and graceful fallback.

    The model is NOT loaded until the first call to :meth:`synthesize`
    or :meth:`synthesize_to_file`, keeping MCP server startup instant.

    Backends tried in order:
    1. ``kokoro-onnx`` — fastest, uses ONNX Runtime + CoreML on M2
    2. ``kokoro`` (base) — PyTorch-based, still fast on Apple Silicon
    3. Apple ``say`` — zero-dependency macOS fallback
    """

    def __init__(
        self,
        *,
        cache_dir: Optional[Path] = None,
        enable_cache: bool = True,
    ) -> None:
        self._cache_dir = cache_dir or Path.home() / ".cache" / "kokoro-voice"
        self._enable_cache = enable_cache
        self._backend: Optional[str] = None
        self._onnx_engine: Any = None
        self._base_engine: Any = None
        self._initialized = False
        self._hw_info: Optional[Dict[str, Any]] = None

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def backend(self) -> Optional[str]:
        """Return the active backend name or None if not yet initialized."""
        return self._backend

    @property
    def hardware_info(self) -> Dict[str, Any]:
        if self._hw_info is None:
            self._hw_info = detect_m2_acceleration()
        return self._hw_info

    def _ensure_initialized(self) -> None:
        """Lazy-load the best available Kokoro backend."""
        if self._initialized:
            return

        if self._try_kokoro_onnx():
            self._backend = "kokoro-onnx"
            self._initialized = True
            logger.info("KokoroVoice: using kokoro-onnx backend")
            return

        if self._try_kokoro_base():
            self._backend = "kokoro-base"
            self._initialized = True
            logger.info("KokoroVoice: using kokoro (base) backend")
            return

        self._backend = "apple-say"
        self._initialized = True
        logger.info("KokoroVoice: Kokoro not installed, using Apple say fallback")

    def _try_kokoro_onnx(self) -> bool:
        """Attempt to initialize the kokoro-onnx backend."""
        try:
            from kokoro_onnx import Kokoro

            self._onnx_engine = Kokoro.from_pretrained(
                model_id="hexgrad/Kokoro-82M",
            )
            return True
        except Exception as exc:
            logger.debug("kokoro-onnx init failed: %s", exc)
            return False

    def _try_kokoro_base(self) -> bool:
        """Attempt to initialize the base kokoro package."""
        try:
            import kokoro  # noqa: F401

            self._base_engine = True
            return True
        except Exception as exc:
            logger.debug("kokoro base init failed: %s", exc)
            return False

    def _resolve_voice(self, lady_name: str) -> Dict[str, str]:
        """Look up voice config for a lady, defaulting to Karen."""
        return LADY_VOICES.get(lady_name, LADY_VOICES["Karen"])

    def synthesize(
        self,
        text: str,
        lady_name: str = "Karen",
        *,
        speed: float = 1.0,
    ) -> bytes:
        """Synthesize speech, returning WAV audio bytes.

        Args:
            text: Text to speak.
            lady_name: One of the 14 ladies.
            speed: Playback speed multiplier (0.75–1.35).

        Returns:
            WAV-format audio bytes.

        Raises:
            ValueError: If text is empty.
            RuntimeError: If all backends fail.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        self._ensure_initialized()

        voice_cfg = self._resolve_voice(lady_name)
        voice_id = voice_cfg["voice_id"]
        lang_code = voice_cfg["lang_code"]
        speed = max(0.75, min(1.35, speed))

        if self._enable_cache:
            cached = self._cache_lookup(text, voice_id, lang_code, speed)
            if cached is not None:
                return cached

        audio_bytes: Optional[bytes] = None

        if self._backend == "kokoro-onnx" and self._onnx_engine is not None:
            audio_bytes = self._synthesize_onnx(text, voice_id, lang_code, speed)

        if audio_bytes is None and self._backend == "kokoro-base":
            audio_bytes = self._synthesize_base(text, voice_id, lang_code, speed)

        if audio_bytes is None:
            audio_bytes = self._synthesize_apple_say(text, lady_name)

        if audio_bytes is None:
            raise RuntimeError(
                f"All TTS backends failed for lady={lady_name!r}, text={text[:50]!r}"
            )

        if self._enable_cache:
            self._cache_store(text, voice_id, lang_code, speed, audio_bytes)

        return audio_bytes

    def synthesize_to_file(
        self,
        text: str,
        lady_name: str = "Karen",
        path: Optional[Path] = None,
        *,
        speed: float = 1.0,
    ) -> Path:
        """Synthesize and save to a WAV file.

        Args:
            text: Text to speak.
            lady_name: One of the 14 ladies.
            path: Output path. Auto-generated under cache_dir if None.
            speed: Playback speed multiplier.

        Returns:
            Path to the saved WAV file.
        """
        audio_bytes = self.synthesize(text, lady_name, speed=speed)

        if path is None:
            voice_cfg = self._resolve_voice(lady_name)
            digest = hashlib.sha256(
                f"{voice_cfg['voice_id']}|{text}|{speed}".encode()
            ).hexdigest()[:16]
            out_dir = self._cache_dir / "rendered"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{lady_name.lower()}_{digest}.wav"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio_bytes)
        return path

    def get_voice_info(self, lady_name: str) -> Dict[str, str]:
        """Return the voice configuration for a lady."""
        return dict(self._resolve_voice(lady_name))

    def list_ladies(self) -> list[str]:
        """Return all configured lady names."""
        return list(LADY_VOICES.keys())

    # ── Backend implementations ──────────────────────────────────────

    def _synthesize_onnx(
        self,
        text: str,
        voice_id: str,
        lang_code: str,
        speed: float,
    ) -> Optional[bytes]:
        """Synthesize via kokoro-onnx ONNX runtime."""
        try:
            import numpy as np

            samples, sample_rate = self._onnx_engine.create(
                text,
                voice=voice_id,
                speed=speed,
                lang=lang_code,
            )
            audio = np.asarray(samples, dtype=np.float32).flatten()
            return _to_wav_bytes(audio, sample_rate)
        except Exception as exc:
            logger.warning("kokoro-onnx synthesis failed: %s", exc)
            return None

    def _synthesize_base(
        self,
        text: str,
        voice_id: str,
        lang_code: str,
        speed: float,
    ) -> Optional[bytes]:
        """Synthesize via base kokoro package (KPipeline)."""
        try:
            import numpy as np
            from kokoro import KPipeline

            pipeline = KPipeline(lang_code=lang_code)
            segments: list = []
            for item in pipeline(text, voice=voice_id, speed=speed):
                audio = item[-1] if isinstance(item, tuple) else item
                segment = np.asarray(audio, dtype=np.float32).flatten()
                if segment.size:
                    segments.append(segment)

            if not segments:
                return None

            combined = np.concatenate(segments)
            return _to_wav_bytes(combined, KOKORO_SAMPLE_RATE)
        except Exception as exc:
            logger.warning("kokoro base synthesis failed: %s", exc)
            return None

    def _synthesize_apple_say(
        self,
        text: str,
        lady_name: str,
    ) -> Optional[bytes]:
        """Fallback: use macOS say to generate AIFF, convert to WAV bytes."""
        import shutil

        if shutil.which("say") is None:
            return None

        apple_voice = _APPLE_FALLBACKS.get(lady_name, "Samantha")
        out_dir = self._cache_dir / "apple_fallback"
        out_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(f"{apple_voice}|{text}".encode()).hexdigest()[:16]
        aiff_path = out_dir / f"{digest}.aiff"

        try:
            result = subprocess.run(
                ["say", "-v", apple_voice, "-o", str(aiff_path), text],
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0 or not aiff_path.exists():
                return None
            return aiff_path.read_bytes()
        except Exception as exc:
            logger.warning("Apple say fallback failed: %s", exc)
            return None
        finally:
            if aiff_path.exists():
                try:
                    aiff_path.unlink()
                except OSError:
                    pass

    # ── Cache ────────────────────────────────────────────────────────

    def _cache_key(self, text: str, voice_id: str, lang_code: str, speed: float) -> str:
        raw = f"{voice_id}|{lang_code}|{speed:.2f}|{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / "phrase_cache" / f"{key}.wav"

    def _cache_lookup(
        self, text: str, voice_id: str, lang_code: str, speed: float
    ) -> Optional[bytes]:
        path = self._cache_path(self._cache_key(text, voice_id, lang_code, speed))
        if path.exists():
            logger.debug("Cache hit for voice=%s text=%s", voice_id, text[:30])
            return path.read_bytes()
        return None

    def _cache_store(
        self,
        text: str,
        voice_id: str,
        lang_code: str,
        speed: float,
        audio_bytes: bytes,
    ) -> None:
        path = self._cache_path(self._cache_key(text, voice_id, lang_code, speed))
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(audio_bytes)
        except OSError as exc:
            logger.warning("Failed to cache audio: %s", exc)

    def clear_cache(self) -> int:
        """Remove all cached audio files. Returns count of files removed."""
        cache_root = self._cache_dir / "phrase_cache"
        if not cache_root.exists():
            return 0
        count = 0
        for f in cache_root.glob("*.wav"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass
        return count


# ── Utility ──────────────────────────────────────────────────────────


def _to_wav_bytes(audio, sample_rate: int = KOKORO_SAMPLE_RATE) -> bytes:
    """Convert float32 audio array to WAV bytes."""
    import numpy as np

    audio = np.asarray(audio, dtype=np.float32).flatten()
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buffer.getvalue()
