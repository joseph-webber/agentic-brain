# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Kokoro-82M neural TTS integration for the 14 ladies.

Design
------
- Karen stays on Apple ``say`` for fast, reliable system/navigation speech.
- The other ladies can use Kokoro neural voices for warm conversational speech.
- Native-language teaching prefers Kokoro where the official v1.0 model supports
  the language, and falls back to Apple voices where Kokoro does not.
- All playback is routed through ``VoiceSerializer`` so utterances never overlap.

Authoritative voice catalogue source:
https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md

Kokoro v1.0 officially ships voices for:
- American English (lang_code='a')
- British English (lang_code='b')
- Japanese (lang_code='j')
- Mandarin Chinese (lang_code='z')
- Spanish (lang_code='e')
- French (lang_code='f')
- Hindi (lang_code='h')
- Italian (lang_code='i')
- Brazilian Portuguese (lang_code='p')

Notably, Vietnamese, Korean, Thai, Indonesian, Polish, Irish Gaelic, and
Cantonese are not official Kokoro v1.0 languages. For those cases, this module
uses unique neural conversational voices and native-language fallback voices for
teaching mode.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import logging
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import numpy as np

from agentic_brain.voice.serializer import VoiceMessage, get_voice_serializer

logger = logging.getLogger(__name__)

KOKORO_REPO_ID = "hexgrad/Kokoro-82M"
KOKORO_SAMPLE_RATE = 24_000
KOKORO_VOICE_SOURCE = "https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md"

# Official Kokoro v1.0 voice IDs documented from VOICES.md.
OFFICIAL_KOKORO_VOICES: Dict[str, tuple[str, ...]] = {
    "en-us": (
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
    ),
    "en-gb": (
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
    ),
    "ja": (
        "jf_alpha",
        "jf_gongitsune",
        "jf_nezumi",
        "jf_tebukuro",
        "jm_kumo",
    ),
    "zh": (
        "zf_xiaobei",
        "zf_xiaoni",
        "zf_xiaoxiao",
        "zf_xiaoyi",
        "zm_yunjian",
        "zm_yunxi",
        "zm_yunxia",
        "zm_yunyang",
    ),
    "es": ("ef_dora", "em_alex", "em_santa"),
    "fr": ("ff_siwis",),
    "hi": ("hf_alpha", "hf_beta", "hm_omega", "hm_psi"),
    "it": ("if_sara", "im_nicola"),
    "pt-br": ("pf_dora", "pm_alex", "pm_santa"),
}

KOKORO_LANGUAGE_CODES = {
    "en": "a",
    "en-us": "a",
    "en-gb": "b",
    "ja": "j",
    "zh": "z",
    "es": "e",
    "fr": "f",
    "hi": "h",
    "it": "i",
    "pt-br": "p",
}

VOICE_PREFIX_LANGUAGE = {
    "a": "en-us",
    "b": "en-gb",
    "j": "ja",
    "z": "zh",
    "e": "es",
    "f": "fr",
    "h": "hi",
    "i": "it",
    "p": "pt-br",
}

LADY_LANGUAGES = {
    "Karen": "Australian English",
    "Kyoko": "Japanese",
    "Tingting": "Mandarin Chinese",
    "Linh": "Vietnamese",
    "Moira": "Irish English",
    "Yuna": "Korean",
    "Kanya": "Thai",
    "Dewi": "Indonesian",
    "Sari": "Javanese / Indonesian",
    "Wayan": "Balinese / Indonesian",
    "Zosia": "Polish",
    "Flo": "British English",
    "Shelley": "British English",
    "Alice": "Italian",
    "Sinji": "Cantonese",
}


@dataclass(frozen=True)
class LadyVoiceConfig:
    """Routing configuration for a lady voice."""

    engine: str
    voice: str
    language: str = "en-us"
    fallback_voice: str = "Samantha"
    native_engine: Optional[str] = None
    native_voice: Optional[str] = None
    native_language: Optional[str] = None
    notes: str = ""


LADY_VOICE_MAP: Dict[str, LadyVoiceConfig] = {
    "Karen": LadyVoiceConfig(
        engine="apple",
        voice="Karen (Premium)",
        language="en-au",
        fallback_voice="Karen (Premium)",
        native_engine="apple",
        native_voice="Karen (Premium)",
        native_language="en-au",
        notes="System/navigation voice stays on Apple for speed and reliability.",
    ),
    "Kyoko": LadyVoiceConfig(
        engine="kokoro",
        voice="jf_alpha",
        language="ja",
        fallback_voice="Kyoko",
        native_engine="kokoro",
        native_voice="jf_tebukuro",
        native_language="ja",
    ),
    "Tingting": LadyVoiceConfig(
        engine="kokoro",
        voice="zf_xiaoxiao",
        language="zh",
        fallback_voice="Tingting",
        native_engine="kokoro",
        native_voice="zf_xiaoyi",
        native_language="zh",
    ),
    "Linh": LadyVoiceConfig(
        engine="kokoro",
        voice="bf_alice",
        language="en-gb",
        fallback_voice="Linh",
        native_engine="apple",
        native_voice="Linh",
        native_language="vi",
        notes="Kokoro v1.0 has no official Vietnamese voice; Apple handles native phrases.",
    ),
    "Moira": LadyVoiceConfig(
        engine="kokoro",
        voice="af_heart",
        language="en-us",
        fallback_voice="Moira",
        native_engine="apple",
        native_voice="Moira",
        native_language="en-ie",
        notes="Kokoro has no dedicated Irish voice in v1.0.",
    ),
    "Yuna": LadyVoiceConfig(
        engine="kokoro",
        voice="af_bella",
        language="en-us",
        fallback_voice="Yuna",
        native_engine="apple",
        native_voice="Yuna",
        native_language="ko",
        notes="Kokoro v1.0 has no official Korean voice.",
    ),
    "Kanya": LadyVoiceConfig(
        engine="kokoro",
        voice="af_nicole",
        language="en-us",
        fallback_voice="Kanya",
        native_engine="apple",
        native_voice="Kanya",
        native_language="th",
        notes="Kokoro v1.0 has no official Thai voice.",
    ),
    "Dewi": LadyVoiceConfig(
        engine="kokoro",
        voice="bf_emma",
        language="en-gb",
        fallback_voice="Damayanti",
        native_engine="apple",
        native_voice="Damayanti",
        native_language="id",
        notes="Kokoro v1.0 has no official Indonesian voice.",
    ),
    "Sari": LadyVoiceConfig(
        engine="kokoro",
        voice="bf_isabella",
        language="en-gb",
        fallback_voice="Damayanti",
        native_engine="apple",
        native_voice="Damayanti",
        native_language="id",
        notes="Uses Indonesian fallback for native teaching until Kokoro adds Javanese/Indonesian.",
    ),
    "Wayan": LadyVoiceConfig(
        engine="kokoro",
        voice="af_sarah",
        language="en-us",
        fallback_voice="Damayanti",
        native_engine="apple",
        native_voice="Damayanti",
        native_language="id",
        notes="Uses Indonesian fallback for native teaching until Kokoro adds Balinese/Indonesian.",
    ),
    "Zosia": LadyVoiceConfig(
        engine="kokoro",
        voice="af_aoede",
        language="en-us",
        fallback_voice="Zosia",
        native_engine="apple",
        native_voice="Zosia",
        native_language="pl",
        notes="Kokoro v1.0 has no official Polish voice.",
    ),
    "Flo": LadyVoiceConfig(
        engine="kokoro",
        voice="ff_siwis",
        language="fr",
        fallback_voice="Amelie",
        native_engine="apple",
        native_voice="Amelie",
        native_language="fr",
        notes="French neural voice gives Flo a clearly distinct timbre.",
    ),
    "Shelley": LadyVoiceConfig(
        engine="kokoro",
        voice="bf_lily",
        language="en-gb",
        fallback_voice="Shelley",
        native_engine="apple",
        native_voice="Shelley",
        native_language="en-gb",
    ),
    "Alice": LadyVoiceConfig(
        engine="kokoro",
        voice="if_sara",
        language="it",
        fallback_voice="Alice",
        native_engine="kokoro",
        native_voice="if_sara",
        native_language="it",
    ),
    "Sinji": LadyVoiceConfig(
        engine="kokoro",
        voice="zf_xiaobei",
        language="zh",
        fallback_voice="Sinji",
        native_engine="apple",
        native_voice="Sinji",
        native_language="zh-hk",
        notes="Conversational Kokoro voice uses Mandarin; native teaching falls back to Cantonese Apple voice.",
    ),
}


class KokoroEngine:
    """Lazy loader for Kokoro-82M inference."""

    def __init__(self, model_path: Optional[Path] = None):
        self._model_path = model_path or (Path.home() / ".cache" / "kokoro-82m")
        self._audio_dir = self._model_path / "rendered"
        self._loaded = False
        self._pipeline_cache: Dict[str, Any] = {}

    @property
    def model_path(self) -> Path:
        """Return the configured model cache path."""
        return self._model_path

    def is_available(self) -> bool:
        """Check if Kokoro is downloaded and the Python package is importable."""
        return (
            self._model_path.exists() and importlib.util.find_spec("kokoro") is not None
        )

    def load(self) -> None:
        """Ensure the model snapshot is present and ready for inference."""
        if self._loaded:
            return
        if not self._model_path.exists():
            self._download_model()
        # Import lazily so the rest of the voice stack still works without Kokoro.
        importlib.import_module("kokoro")
        self._loaded = True

    def synthesize(
        self,
        text: str,
        voice: str,
        language: str = "en-us",
        *,
        speed: float = 1.0,
    ) -> bytes:
        """Generate WAV bytes for the requested text and voice."""
        if not text.strip():
            raise ValueError("Text cannot be empty")
        if not self._loaded:
            self.load()

        normalized_speed = max(0.75, min(1.35, speed))
        pipeline = self._get_pipeline(self._resolve_lang_code(voice, language))
        segments: list[np.ndarray] = []

        generator = pipeline(text, voice=voice, speed=normalized_speed)
        for item in generator:
            audio = item[-1] if isinstance(item, tuple) else item
            segment = np.asarray(audio, dtype=np.float32).flatten()
            if segment.size:
                segments.append(segment)

        if not segments:
            raise RuntimeError(f"Kokoro returned no audio for voice {voice!r}")

        combined = np.concatenate(segments)
        return self._to_wav_bytes(combined)

    def render_to_path(
        self,
        text: str,
        voice: str,
        language: str = "en-us",
        *,
        speed: float = 1.0,
    ) -> Path:
        """Render speech to a deterministic cache file and return the path."""
        audio_bytes = self.synthesize(text, voice=voice, language=language, speed=speed)
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(
            f"{voice}|{language}|{speed}|{text}".encode()
        ).hexdigest()
        output_path = self._audio_dir / f"{digest}.wav"
        output_path.write_bytes(audio_bytes)
        return output_path

    def _get_pipeline(self, lang_code: str) -> Any:
        if lang_code in self._pipeline_cache:
            return self._pipeline_cache[lang_code]

        kokoro_module = importlib.import_module("kokoro")
        pipeline_class = kokoro_module.KPipeline
        pipeline = pipeline_class(lang_code=lang_code)
        self._pipeline_cache[lang_code] = pipeline
        return pipeline

    def _resolve_lang_code(self, voice: str, language: str) -> str:
        normalized_language = language.lower()
        if normalized_language in KOKORO_LANGUAGE_CODES:
            return KOKORO_LANGUAGE_CODES[normalized_language]

        prefix = voice.split("_", 1)[0][:1].lower()
        if prefix in VOICE_PREFIX_LANGUAGE:
            return KOKORO_LANGUAGE_CODES[VOICE_PREFIX_LANGUAGE[prefix]]

        raise ValueError(
            f"Unsupported Kokoro language {language!r} for voice {voice!r}"
        )

    def _download_model(self) -> None:
        """Download Kokoro-82M with huggingface_hub if needed."""
        hub = importlib.import_module("huggingface_hub")
        snapshot_download = hub.snapshot_download
        snapshot_download(
            repo_id=KOKORO_REPO_ID,
            local_dir=str(self._model_path),
            local_dir_use_symlinks=False,
        )

    @staticmethod
    def _to_wav_bytes(audio: np.ndarray) -> bytes:
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767).astype(np.int16)

        from io import BytesIO

        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(KOKORO_SAMPLE_RATE)
            wav_file.writeframes(pcm.tobytes())
        return buffer.getvalue()


class HybridVoiceRouter:
    """Route lady voices to Apple or Kokoro while preserving serialization."""

    def __init__(self, kokoro: Optional[KokoroEngine] = None):
        self._kokoro = kokoro or KokoroEngine()

    def speak(
        self,
        text: str,
        lady: str = "Karen",
        rate: int = 155,
        *,
        wait: bool = True,
        use_native_voice: bool = False,
    ) -> bool:
        """Speak with the selected lady using the correct engine."""
        config = LADY_VOICE_MAP.get(lady, LADY_VOICE_MAP["Karen"])
        serializer = get_voice_serializer()
        message = VoiceMessage(text=text, voice=lady, rate=rate)
        return serializer.run_serialized(
            message,
            executor=lambda queued_message: self._speak_serialized(
                queued_message,
                config,
                use_native_voice=use_native_voice,
            ),
            wait=wait,
        )

    async def speak_async(
        self,
        text: str,
        lady: str = "Karen",
        rate: int = 155,
        *,
        wait: bool = True,
        use_native_voice: bool = False,
    ) -> bool:
        """Async variant of :meth:`speak` for event-loop friendly playback."""
        config = LADY_VOICE_MAP.get(lady, LADY_VOICE_MAP["Karen"])
        serializer = get_voice_serializer()
        message = VoiceMessage(text=text, voice=lady, rate=rate)
        return await serializer.run_serialized_async(
            message,
            executor=lambda queued_message: asyncio.run(
                self._speak_serialized_async(
                    queued_message,
                    config,
                    use_native_voice=use_native_voice,
                )
            ),
            wait=wait,
        )

    def teach_phrase(self, english: str, native: str, lady: str) -> bool:
        """Teach a phrase using Karen for guidance and the lady for pronunciation."""
        language_name = LADY_LANGUAGES.get(lady, "that language")
        steps = (
            self.speak(f"In {language_name}, you say:", lady="Karen"),
            self.speak(native, lady=lady, use_native_voice=True),
            self.speak(f"Which means: {english}", lady="Karen"),
        )
        return all(steps)

    def _speak_serialized(
        self,
        message: VoiceMessage,
        config: LadyVoiceConfig,
        *,
        use_native_voice: bool,
    ) -> bool:
        engine, voice_name, language, fallback = self._resolve_route(
            config,
            use_native_voice=use_native_voice,
        )

        if engine == "apple":
            return self._speak_with_apple(message.text, voice_name, message.rate)

        try:
            speed = max(0.75, min(1.35, message.rate / 155.0))
            audio_path = self._kokoro.render_to_path(
                message.text,
                voice=voice_name,
                language=language,
                speed=speed,
            )
            return self._play_audio(audio_path)
        except Exception as exc:
            logger.warning(
                "Kokoro speak failed for %s via %s (%s). Falling back to Apple %s.",
                message.voice,
                voice_name,
                exc,
                fallback,
            )
            return self._speak_with_apple(message.text, fallback, message.rate)

    async def _speak_serialized_async(
        self,
        message: VoiceMessage,
        config: LadyVoiceConfig,
        *,
        use_native_voice: bool,
    ) -> bool:
        engine, voice_name, language, fallback = self._resolve_route(
            config,
            use_native_voice=use_native_voice,
        )

        if engine == "apple":
            return await self._speak_with_apple_async(
                message.text, voice_name, message.rate
            )

        try:
            speed = max(0.75, min(1.35, message.rate / 155.0))
            audio_path = await asyncio.to_thread(
                self._kokoro.render_to_path,
                message.text,
                voice=voice_name,
                language=language,
                speed=speed,
            )
            return await self._play_audio_async(audio_path)
        except Exception as exc:
            logger.warning(
                "Kokoro speak failed for %s via %s (%s). Falling back to Apple %s.",
                message.voice,
                voice_name,
                exc,
                fallback,
            )
            return await self._speak_with_apple_async(
                message.text, fallback, message.rate
            )

    @staticmethod
    def _resolve_route(
        config: LadyVoiceConfig,
        *,
        use_native_voice: bool,
    ) -> tuple[str, str, str, str]:
        if use_native_voice:
            native_engine = config.native_engine or config.engine
            native_voice = config.native_voice or config.voice
            native_language = config.native_language or config.language
            return native_engine, native_voice, native_language, config.fallback_voice
        return config.engine, config.voice, config.language, config.fallback_voice

    @staticmethod
    def _speak_with_apple(text: str, voice: str, rate: int) -> bool:
        if shutil.which("say") is None:
            logger.warning("macOS 'say' command not available")
            return False
        completed = subprocess.run(
            ["say", "-v", voice, "-r", str(rate), text],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return completed.returncode == 0

    @staticmethod
    async def _speak_with_apple_async(text: str, voice: str, rate: int) -> bool:
        if shutil.which("say") is None:
            logger.warning("macOS 'say' command not available")
            return False
        process = await asyncio.create_subprocess_exec(
            "say",
            "-v",
            voice,
            "-r",
            str(rate),
            text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await process.wait() == 0

    @staticmethod
    def _play_audio(audio_path: Path) -> bool:
        if shutil.which("afplay") is None:
            logger.warning("afplay not available for Kokoro playback")
            return False
        completed = subprocess.run(
            ["afplay", str(audio_path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return completed.returncode == 0

    @staticmethod
    async def _play_audio_async(audio_path: Path) -> bool:
        if shutil.which("afplay") is None:
            logger.warning("afplay not available for Kokoro playback")
            return False
        process = await asyncio.create_subprocess_exec(
            "afplay",
            str(audio_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await process.wait() == 0


def get_official_kokoro_voice_ids(
    language: Optional[str] = None,
) -> Mapping[str, Iterable[str]]:
    """Return the official Kokoro v1.0 voice catalogue or a single language entry."""
    if language is None:
        return OFFICIAL_KOKORO_VOICES
    normalized = language.lower()
    return {normalized: OFFICIAL_KOKORO_VOICES.get(normalized, ())}
