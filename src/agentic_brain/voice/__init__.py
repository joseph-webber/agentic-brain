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
from agentic_brain.voice.serializer import (
    VoiceSerializer,
    _legacy_speak,
    _warn_direct_say,
    audit_no_concurrent_say,
    get_voice_serializer,
    speak_serialized,
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
    rate: int = 155,
    *,
    pause_after: float | None = None,
    wait: bool = True,
) -> bool:
    """THE recommended way to produce voice output.

    Routes through the singleton ``VoiceSerializer``, which serializes
    all speech through a single worker thread.  **Never overlaps.**

    Args:
        text: What to say.
        voice: macOS voice name (Karen, Moira, Kyoko …).
        rate: Words per minute (100-200).
        pause_after: Seconds to pause after this utterance.
        wait: Block until the utterance finishes.

    Returns:
        True if the utterance was delivered successfully.
    """
    return get_voice_serializer().speak(
        text,
        voice=voice,
        rate=rate,
        pause_after=pause_after,
        wait=wait,
    )


def __getattr__(name: str):
    import agentic_brain.audio as _audio

    if hasattr(_audio, name):
        return getattr(_audio, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # ── PRIMARY ENTRY POINT (use this!) ──
    "speak_safe",
    # Config
    "VoiceConfig",
    "VoiceQuality",
    "LanguagePack",
    "LANGUAGE_PACKS",
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
    "audit_no_concurrent_say",
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
