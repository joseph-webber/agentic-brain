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

"""
Voice module for Agentic Brain.

This is the PRIMARY interface for text-to-speech in the brain.
CRITICAL for accessibility - Joseph is blind and needs voice output!

Provides:
- 145+ macOS voices including Joseph's ladies
- Queue management (no overlapping speech!)
- Cross-platform fallback (Windows/Linux)
- Voice testing and discovery

Quick Start:
    >>> from agentic_brain.voice import speak
    >>> speak("Hello Joseph", voice="Karen (Premium)")

    >>> from agentic_brain.voice import list_voices, test_voice
    >>> voices = list_voices()
    >>> print(f"Found {len(voices)} voices!")
    >>> test_voice("Moira")

Queue Example (for sequential speech):
    >>> from agentic_brain.voice import queue_speak, play_queue
    >>> queue_speak("First message", voice="Karen (Premium)")
    >>> queue_speak("Second message", voice="Moira")
    >>> play_queue()  # No overlaps!

Available Voices (145+ on macOS):
- Ladies: Karen, Moira, Kyoko, Tingting, Damayanti, Zosia, Yuna, etc.
- English: Samantha, Daniel, Alex, Fred, Tessa, Rishi
- European: Alice (IT), Anna (DE), Amélie (FR), Milena (RU)
- Novelty: Zarvox, Ralph, Bells, Whisper, Boing, Trinoids
"""

# Re-export everything from audio module
from agentic_brain.audio import (
    # Classes
    Audio,
    AudioConfig,
    Platform,
    Voice,
    VoiceInfo,
    VoiceQueue,
    VoiceRegistry,
    MACOS_VOICES,
    # Factory functions
    get_audio,
    get_registry,
    get_queue,
    # Quick functions
    speak,
    sound,
    announce,
    list_voices,
    test_voice,
    queue_speak,
    play_queue,
)

__all__ = [
    # Classes
    "Audio",
    "AudioConfig",
    "Platform",
    "Voice",
    "VoiceInfo",
    "VoiceQueue",
    "VoiceRegistry",
    "MACOS_VOICES",
    # Factory functions
    "get_audio",
    "get_registry",
    "get_queue",
    # Quick functions
    "speak",
    "sound",
    "announce",
    "list_voices",
    "test_voice",
    "queue_speak",
    "play_queue",
]
