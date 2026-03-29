# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Voice module for Agentic Brain.

HARDENED SERIALIZED ARCHITECTURE (2026-03-29)
=============================================

This is the PRIMARY interface for text-to-speech in the brain.
**Joseph is blind** – overlapping voices are an accessibility catastrophe.

**THE ONLY SANCTIONED WAY TO SPEAK:**

.. code-block:: python

    from agentic_brain.voice import speak_safe

    speak_safe("Hello Joseph", voice="Karen", rate=155)

``speak_safe`` routes through the singleton ``VoiceSerializer``, which
guarantees:

* ✅ One voice at a time – a threading lock + worker queue
* ✅ Runtime overlap audit – ``pgrep`` detects rogue ``say`` processes
* ✅ Deprecation warnings – legacy callers are logged
* ✅ Proper inter-utterance pauses for auditory clarity

**DO NOT bypass the serializer.**  Any direct
``subprocess.Popen(["say", ...])`` call WILL overlap.

Provides:
- 145+ macOS voices including Joseph's primary voice assistants
- Queue management (no overlapping speech!)
- Cross-platform fallback (Windows/Linux)
- Voice testing and discovery
- Multilingual support (Language Packs)
- Voice Quality Tiers
"""

# Import config first (safe)
# Lazy import for audio to avoid circular dependency
# audio -> voice.config -> voice/__init__ -> audio
import typing

from agentic_brain.voice.config import (
    LANGUAGE_PACKS,
    LanguagePack,
    VoiceConfig,
    VoiceQuality,
)
from agentic_brain.voice.ptt import (
    PTTConfig,
    PTTState,
    PushToTalkController,
)
from agentic_brain.voice.emotions import (
    EMOTION_PARAMS,
    Emotion,
    EmotionDetector,
    EmotionResult,
    VoiceEmotion,
    VoiceEmotionDetector,
    apply_emotion,
    emotion_result_to_voice_emotion,
    emotion_to_voice_emotion,
)
from agentic_brain.voice.expression import ExpressionEngine

# Import voice queue (CRITICAL for accessibility!)
from agentic_brain.voice.queue import (
    ASIAN_VOICE_CONFIG,
    WESTERN_VOICE_CONFIG,
    VoiceMessage,
    VoiceQueue,
    VoiceType,
    clear_queue,
    get_queue_size,
    is_speaking,
    speak,
    speak_system_message,
)

# Import regional voice support
from agentic_brain.voice.regional import (
    RegionalVoice,
    get_available_regions,
    get_regional_voice,
)

# Import resilient voice system (NEVER FAILS - multiple fallbacks!)
from agentic_brain.voice.resilient import (
    ResilientVoice,
    SoundEffects,
    VoiceDaemon,
    get_daemon,
    get_voice_stats,
    play_sound,
    speak_via_daemon,
)
from agentic_brain.voice.resilient import (
    speak as resilient_speak,
)
from agentic_brain.voice.serializer import (
    VoiceSerializer,
    _legacy_speak,
    _warn_direct_say,
    audit_no_concurrent_say,
    get_voice_serializer,
    speak_serialized,
)

# Import adaptive speed profiles (grow with Joseph's proficiency!)
from agentic_brain.voice.speed_profiles import (
    CONTENT_SPEED_TIERS,
    PROFILE_RATES,
    TIER_DESCRIPTIONS,
    AdaptiveSpeedTracker,
    ContentSpeedResult,
    SpeedProfile,
    SpeedProfileManager,
    UserPreferenceManager,
    UserSpeedPreferences,
    get_adaptive_tracker,
    get_current_rate,
    get_preference_manager,
    get_speed_for_content,
    get_speed_manager,
)
from agentic_brain.voice.stream import (
    VoiceEventConsumer,
    VoiceEventProducer,
    get_voice_event_producer,
    speak_async,
)
from agentic_brain.voice.streaming_api import (
    StreamingAPIConfig,
    VoiceStreamingAPI,
)

# Import user regional preferences and learning
from agentic_brain.voice.user_regions import (
    UserRegionStorage,
    get_region_stats,
    get_user_region_storage,
    regionalize_text,
    set_user_region,
)

if typing.TYPE_CHECKING:
    from agentic_brain.audio import (
        MACOS_VOICES,
        Audio,
        AudioConfig,
        Platform,
        Voice,
        VoiceInfo,
        VoiceQueue,
        VoiceRegistry,
        announce,
        get_audio,
        get_queue,
        get_registry,
        list_voices,
        play_queue,
        queue_speak,
        sound,
        speak,
        test_voice,
    )


# ── THE ONE TRUE SPEAK FUNCTION ─────────────────────────────────────


def speak_safe(
    text: str,
    voice: str = "Karen",
    rate: int | None = None,
    *,
    pause_after: float | None = None,
    wait: bool = True,
) -> bool:
    """THE recommended way to produce voice output.

    Routes through the singleton ``VoiceSerializer``, which serializes
    all speech through a single worker thread.  **Never overlaps.**

    When *rate* is ``None`` the current adaptive speed profile is used
    (see :mod:`agentic_brain.voice.speed_profiles`).

    Args:
        text: What to say.
        voice: macOS voice name (Karen, Moira, Kyoko …).
        rate: Words per minute, or ``None`` for the active profile rate.
        pause_after: Seconds to pause after this utterance.
        wait: Block until the utterance finishes.

    Returns:
        True if the utterance was delivered successfully.
    """
    if rate is None:
        rate = get_current_rate()
    return get_voice_serializer().speak(
        text,
        voice=voice,
        rate=rate,
        pause_after=pause_after,
        wait=wait,
    )


def __getattr__(name: str):
    if name in _VOICE_EXPORTS:
        module_name, attr_name = _VOICE_EXPORTS[name]
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)

    import agentic_brain.audio as _audio

    if hasattr(_audio, name):
        return getattr(_audio, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # ── PRIMARY ENTRY POINT (use this!) ──
    "speak_safe",
    # Speed profiles (adaptive rate)
    "SpeedProfile",
    "SpeedProfileManager",
    "AdaptiveSpeedTracker",
    "PROFILE_RATES",
    "CONTENT_SPEED_TIERS",
    "TIER_DESCRIPTIONS",
    "UserSpeedPreferences",
    "UserPreferenceManager",
    "ContentSpeedResult",
    "get_speed_manager",
    "get_adaptive_tracker",
    "get_current_rate",
    "get_preference_manager",
    "get_speed_for_content",
    # Config
    "VoiceConfig",
    "VoiceQuality",
    "LanguagePack",
    "LANGUAGE_PACKS",
    # Push-to-talk controller
    "PTTConfig",
    "PTTState",
    "PushToTalkController",
    "VoiceEmotion",
    "Emotion",
    "EmotionResult",
    "VoiceEmotionDetector",
    "EmotionDetector",
    "ExpressionEngine",
    "EMOTION_PARAMS",
    "apply_emotion",
    "emotion_to_voice_emotion",
    "emotion_result_to_voice_emotion",
    # Queue system (CRITICAL for accessibility!)
    "VoiceQueue",
    "VoiceMessage",
    "VoiceType",
    "ASIAN_VOICE_CONFIG",
    "WESTERN_VOICE_CONFIG",
    "speak",
    "clear_queue",
    "is_speaking",
    "get_queue_size",
    "speak_system_message",
    # Serializer (core gating mechanism)
    "VoiceSerializer",
    "get_voice_serializer",
    "speak_serialized",
    "speak_async",
    "audit_no_concurrent_say",
    "VoiceEventProducer",
    "VoiceEventConsumer",
    "get_voice_event_producer",
    "StreamingAPIConfig",
    "VoiceStreamingAPI",
    # Resilient voice system (NEVER FAILS!)
    "ResilientVoice",
    "VoiceDaemon",
    "SoundEffects",
    "resilient_speak",
    "speak_via_daemon",
    "play_sound",
    "get_daemon",
    "get_voice_stats",
    # User regional preferences (LEARNS IN REALTIME!)
    "UserRegionStorage",
    "get_user_region_storage",
    "set_user_region",
    "regionalize_text",
    "get_region_stats",
    # Regional voice support
    "RegionalVoice",
    "get_regional_voice",
    "get_available_regions",
    # ── NEW: Integration Plan Components (2026-03-29) ──
    # Lazy-loaded to avoid blocking MCP startup.
    # Use: from agentic_brain.voice.earcons import EarconPlayer
    # Or:  EarconPlayer, get_fn = _lazy_earcons()
    "_lazy_earcons",
    "_lazy_redis_voice_queue",
    "_lazy_speech_rates",
    "_lazy_tts_router",
    "_lazy_kokoro",
    "_lazy_neural_router",
    # ── PHASE 2: New Integration Components ──
    "_lazy_watchdog",
    "_lazy_daemon_gate",
    "_lazy_live_mode",
    "_lazy_stream_consumer",
    "_lazy_unified",
    # ── PHASE 3: Conversation Memory ──
    "_lazy_phase3",
    "_lazy_conversation_memory",
    "_lazy_repeat_detector",
    "Phase3VoiceSystem",
    "get_phase3_voice_system",
    "KokoroVoice",
    "KokoroTTS",
    "NeuralVoiceRouter",
    "EarconPlayer",
    "ensure_earcons_exist",
    "ContentClassifier",
    "ConversationMemory",
    "RepeatDetector",
    "VoiceCloner",
    "VoiceLibrary",
    "QualityGate",
    "VoiceQualityAnalyzer",
    "EmotionDetector",
    "ExpressionEngine",
    # ── PHASE 4: GraphRAG Voice Memory ──
    "_lazy_voice_memory",
    "VoiceMemory",
    "VoiceUtterance",
    "VoiceConversation",
    "get_voice_memory",
    # ── PHASE 5: ML-based Wake Word Detection ──
    "_lazy_wake_word",
    "WakeWordDetector",
    "WakeWordConfig",
    "WakeWordResult",
    "get_wake_word_detector",
    "detect_wake_word",
    # Classes
    "Audio",
    "AudioConfig",
    "Platform",
    "Voice",
    "VoiceInfo",
    "VoiceRegistry",
    "MACOS_VOICES",
    # Factory functions
    "get_audio",
    "get_registry",
    "get_queue",
    # Quick functions
    "sound",
    "announce",
    "list_voices",
    "test_voice",
    "queue_speak",
    "play_queue",
]

# Redis voice summary
from .redis_summary import (
    RedisSummary,
    RedisVoiceSummary,
    get_redis_summary,
    speak_queue_status,
    speak_redis_summary,
)

# ── NEW COMPONENTS (Voice Integration Plan 2026-03-29) ──────────────
#
# Five improvements built by parallel agents, integrated here:
#   ① Redis Cross-Process Lock   → _speech_lock.py (already imported above)
#   ② Earcon Sound System        → earcons.py
#   ③ Redis Voice Queue          → redis_voice_queue.py
#   ④ Adaptive Speech Rates      → speech_rates.py
#   ⑤ Kokoro TTS / Hybrid Router → kokoro_tts.py, tts_router.py
#
# All imports are lazy to avoid blocking MCP server startup.


def _lazy_earcons():
    """Lazy import for earcon sound system."""
    from agentic_brain.audio import get_earcon_player
    from agentic_brain.audio.earcons import EarconPlayer

    return EarconPlayer, get_earcon_player


def _lazy_redis_voice_queue():
    """Lazy import for Redis-backed priority voice queue."""
    from agentic_brain.voice.redis_voice_queue import (
        RedisVoiceQueue,
        get_redis_voice_queue,
    )

    return RedisVoiceQueue, get_redis_voice_queue


def _lazy_speech_rates():
    """Lazy import for adaptive speech rate profiles."""
    from agentic_brain.voice.speech_rates import (
        SpeedProfile,
        SpeedProfileResolver,
        VoiceMode,
        get_speed_profile_resolver,
    )

    return SpeedProfile, SpeedProfileResolver, VoiceMode, get_speed_profile_resolver


def _lazy_tts_router():
    """Lazy import for hybrid TTS engine router."""
    from agentic_brain.voice.tts_router import (
        HybridTTSRouter,
        TTSEngine,
        get_tts_router,
    )

    return HybridTTSRouter, TTSEngine, get_tts_router


def _lazy_kokoro():
    """Lazy import for Kokoro neural TTS engine."""
    from agentic_brain.voice.kokoro_tts import KokoroVoice, kokoro_available

    return KokoroVoice, kokoro_available


def _lazy_neural_router():
    """Lazy import for neural voice router (Apple say ↔ Kokoro)."""
    from agentic_brain.voice.neural_router import NeuralVoiceRouter

    return NeuralVoiceRouter


# ── PHASE 2 COMPONENTS (Voice Improvements 2026-03-30) ──────────────
#
# Four improvements built by parallel agents, integrated here:
#   ① Worker Thread Watchdog    → watchdog.py (monitors & restarts worker)
#   ② Daemon Overlap Gate       → daemon_gate.py (PID-file single-instance)
#   ③ Live Voice Mode (Aria)    → live_mode.py (streaming LLM → speech)
#   ④ Redpanda Stream Consumer  → stream_consumer.py (event-driven speech)
#   ⑤ Unified Voice System      → unified.py (single entry point for all)
#
# All imports are lazy to avoid blocking MCP server startup.


def _lazy_watchdog():
    """Lazy import for the voice worker watchdog."""
    from agentic_brain.voice.watchdog import VoiceWatchdog

    return VoiceWatchdog


def _lazy_daemon_gate():
    """Lazy import for the daemon startup gate."""
    from agentic_brain.voice.daemon_gate import DaemonGate, get_daemon_gate

    return DaemonGate, get_daemon_gate


def _lazy_live_mode():
    """Lazy import for live voice mode (Project Aria)."""
    from agentic_brain.voice.live_mode import LiveVoiceMode, get_live_mode

    return LiveVoiceMode, get_live_mode


def _lazy_stream_consumer():
    """Lazy import for Redpanda voice stream consumer."""
    from agentic_brain.voice.stream_consumer import VoiceStreamConsumer

    return VoiceStreamConsumer


def _lazy_unified():
    """Lazy import for the unified voice system."""
    from agentic_brain.voice.unified import UnifiedVoiceSystem, get_unified

    return UnifiedVoiceSystem, get_unified


def _lazy_phase3():
    """Lazy import for the Phase 3 voice integration facade."""
    from agentic_brain.voice.phase3 import (
        Phase3VoiceSystem,
        get_phase3_voice_system,
    )

    return Phase3VoiceSystem, get_phase3_voice_system


def _lazy_conversation_memory():
    """Lazy import for conversation memory (voice history + search)."""
    from agentic_brain.voice.conversation_memory import (
        ConversationMemory,
        Utterance,
        get_conversation_memory,
    )

    return ConversationMemory, Utterance, get_conversation_memory


def _lazy_repeat_detector():
    """Lazy import for repeat/duplicate utterance detection."""
    from agentic_brain.voice.repeat_detector import (
        RepeatAction,
        RepeatDetector,
        get_repeat_detector,
    )

    return RepeatDetector, RepeatAction, get_repeat_detector


def _lazy_voice_memory():
    """Lazy import for GraphRAG voice memory (Neo4j-backed)."""
    from agentic_brain.voice.memory import (
        VoiceConversation,
        VoiceMemory,
        VoiceUtterance,
        get_voice_memory,
        reset_voice_memory,
    )

    return (
        VoiceMemory,
        VoiceUtterance,
        VoiceConversation,
        get_voice_memory,
        reset_voice_memory,
    )


def _lazy_wake_word():
    """Lazy import for ML-based wake word detection."""
    from agentic_brain.voice.wake_word import (
        WakeWordConfig,
        WakeWordDetector,
        WakeWordResult,
        detect_wake_word,
        get_wake_word_detector,
    )

    return (
        WakeWordDetector,
        WakeWordConfig,
        WakeWordResult,
        get_wake_word_detector,
        detect_wake_word,
    )


_VOICE_EXPORTS = {
    "KokoroVoice": ("agentic_brain.voice.kokoro_tts", "KokoroVoice"),
    "KokoroTTS": ("agentic_brain.voice.kokoro_tts", "KokoroVoice"),
    "NeuralVoiceRouter": ("agentic_brain.voice.neural_router", "NeuralVoiceRouter"),
    "EarconPlayer": ("agentic_brain.audio.earcons", "EarconPlayer"),
    "ensure_earcons_exist": ("agentic_brain.audio.earcons", "ensure_earcons_exist"),
    "ContentClassifier": (
        "agentic_brain.voice.content_classifier",
        "ContentClassifier",
    ),
    "ConversationMemory": (
        "agentic_brain.voice.conversation_memory",
        "ConversationMemory",
    ),
    "RepeatDetector": ("agentic_brain.voice.repeat_detector", "RepeatDetector"),
    "VoiceCloner": ("agentic_brain.voice.voice_cloning", "VoiceCloner"),
    "VoiceLibrary": ("agentic_brain.voice.voice_library", "VoiceLibrary"),
    "QualityGate": ("agentic_brain.voice.quality_gate", "QualityGate"),
    "VoiceQualityAnalyzer": (
        "agentic_brain.audio.quality_analyzer",
        "VoiceQualityAnalyzer",
    ),
    "EmotionDetector": ("agentic_brain.voice.emotions", "EmotionDetector"),
    "VoiceEmotionDetector": ("agentic_brain.voice.emotions", "VoiceEmotionDetector"),
    "Emotion": ("agentic_brain.voice.emotions", "Emotion"),
    "EmotionResult": ("agentic_brain.voice.emotions", "EmotionResult"),
    "ExpressionEngine": ("agentic_brain.voice.expression", "ExpressionEngine"),
    "Phase3VoiceSystem": ("agentic_brain.voice.phase3", "Phase3VoiceSystem"),
    "get_phase3_voice_system": (
        "agentic_brain.voice.phase3",
        "get_phase3_voice_system",
    ),
    # GraphRAG Voice Memory (Neo4j-backed)
    "VoiceMemory": ("agentic_brain.voice.memory", "VoiceMemory"),
    "VoiceUtterance": ("agentic_brain.voice.memory", "VoiceUtterance"),
    "VoiceConversation": ("agentic_brain.voice.memory", "VoiceConversation"),
    "get_voice_memory": ("agentic_brain.voice.memory", "get_voice_memory"),
    # Wake word detection (ML-based, fast 50-100ms)
    "WakeWordDetector": ("agentic_brain.voice.wake_word", "WakeWordDetector"),
    "WakeWordConfig": ("agentic_brain.voice.wake_word", "WakeWordConfig"),
    "WakeWordResult": ("agentic_brain.voice.wake_word", "WakeWordResult"),
    "get_wake_word_detector": ("agentic_brain.voice.wake_word", "get_wake_word_detector"),
    "detect_wake_word": ("agentic_brain.voice.wake_word", "detect_wake_word"),
}
