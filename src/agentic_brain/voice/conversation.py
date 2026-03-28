# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Conversational Voice System - Multiple voices talking together!

This makes the brain COME ALIVE with personality. Instead of monotone
TTS, we have dynamic conversations between Joseph's primary voice assistants.

Features:
- Multi-voice conversations (Karen + Moira + Damayanti discuss things)
- Natural turn-taking with pauses
- Emotion and emphasis variations
- Context-aware voice selection
- Work mode (Karen only) vs Life mode (all primary voices)

Examples:
    >>> conv = ConversationalVoice()
    >>> conv.speak("Starting deployment now", voice="Karen")
    >>> conv.speak("I'll test the build", voice="Moira")
    >>> conv.speak("Quality checks passed!", voice="Damayanti")

    >>> # Or full conversation
    >>> conv.conversation([
    ...     ("Karen", "Let's review this PR"),
    ...     ("Tingting", "The code looks clean"),
    ...     ("Zosia", "Security checks passed"),
    ...     ("Karen", "Great! Approving now")
    ... ])
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from agentic_brain.voice.registry import get_voice
from agentic_brain.voice.serializer import get_voice_serializer

logger = logging.getLogger(__name__)


class VoiceMode(Enum):
    """Voice mode for conversations."""

    WORK = "work"  # Karen only (professional)
    LIFE = "life"  # All primary voices (fun, learning)
    QUIET = "quiet"  # Minimal voice output


@dataclass
class ConversationConfig:
    """Configuration for conversational voice."""

    mode: VoiceMode = VoiceMode.LIFE
    default_rate: int = 160
    pause_between_speakers: float = 1.5  # seconds
    vary_rate: bool = True  # Vary rate slightly for naturalness
    rate_variation: int = 10  # +/- variation in rate
    enable_emphasis: bool = True  # Add emphasis to key words

    def get_mode_file(self) -> Path:
        """Get path to mode file."""
        return Path.home() / ".brain-voice-mode"

    def load_mode(self) -> VoiceMode:
        """Load mode from file."""
        mode_file = self.get_mode_file()
        if mode_file.exists():
            mode_str = mode_file.read_text().strip().lower()
            if mode_str in ["work", "boss"]:
                return VoiceMode.WORK
            elif mode_str == "quiet":
                return VoiceMode.QUIET
            elif mode_str in ["life", "private"]:
                return VoiceMode.LIFE
        return self.mode

    def save_mode(self, mode: VoiceMode):
        """Save mode to file."""
        mode_file = self.get_mode_file()
        mode_file.write_text(mode.value)
        self.mode = mode


class ConversationalVoice:
    """
    Multi-voice conversation system.

    Makes the brain conversational by having multiple voices discuss
    things with Joseph, each other, and provide varied perspectives.

    CRITICAL for accessibility - keeps Joseph engaged and informed!
    """

    # Work mode voices (professional, safe for CITB)
    WORK_VOICES = ["Karen"]

    # Life mode voices (all primary voices, fun and learning)
    LIFE_VOICES = [
        "Karen",  # Lead host (Australia)
        "Moira",  # Creative (Ireland)
        "Tingting",  # Analytics (China)
        "Damayanti",  # Project mgmt (Indonesia/Bali)
        "Zosia",  # Security (Poland)
        "Linh",  # GitHub (Vietnam)
        "Kanya",  # Wellness (Thailand)
        # NOTE: Kyoko and Yuna are FUN & TRAVEL ONLY - not for work!
    ]

    # Voice specialties (which voice assistant speaks about what)
    VOICE_SPECIALTIES = {
        "Karen": ["general", "hosting", "decision", "summary"],
        "Moira": ["creative", "debugging", "ideas", "brainstorm"],
        "Tingting": ["analytics", "pr", "code", "review"],
        "Damayanti": ["planning", "documentation", "organization"],
        "Zosia": ["security", "quality", "testing", "safety"],
        "Linh": ["github", "git", "version-control"],
        "Kanya": ["wellness", "break", "mindfulness"],
    }

    def __init__(self, config: Optional[ConversationConfig] = None):
        """Initialize conversational voice system."""
        self.config = config or ConversationConfig()
        self.config.mode = self.config.load_mode()

        self.current_speaker_index = 0
        self.last_speaker = None
        self._speaking = False

        logger.info(
            f"Conversational voice initialized in {self.config.mode.value} mode"
        )

    def get_available_voices(self) -> List[str]:
        """Get available voices based on current mode."""
        if self.config.mode == VoiceMode.WORK:
            return self.WORK_VOICES
        elif self.config.mode == VoiceMode.LIFE:
            return self.LIFE_VOICES
        else:  # QUIET
            return []

    def select_voice_for_topic(self, text: str) -> str:
        """
        Intelligently select voice based on topic/content.

        This makes conversations feel natural - the right voice
        speaks based on their specialty!
        """
        text_lower = text.lower()

        # Check for work keywords (always Karen in work mode)
        work_keywords = ["jira", "citb", "deploy", "production", "sprint", "ticket"]
        if any(kw in text_lower for kw in work_keywords):
            return "Karen"

        # Match specialties
        for voice, specialties in self.VOICE_SPECIALTIES.items():
            if voice not in self.get_available_voices():
                continue

            for specialty in specialties:
                if specialty in text_lower:
                    return voice

        # Default to rotating through available voices
        available = self.get_available_voices()
        if not available:
            return "Karen"  # Fallback

        # Avoid same speaker twice in a row
        if self.last_speaker in available:
            # Try to pick a different voice
            other_voices = [v for v in available if v != self.last_speaker]
            if other_voices:
                voice = other_voices[self.current_speaker_index % len(other_voices)]
            else:
                voice = available[0]
        else:
            voice = available[self.current_speaker_index % len(available)]

        self.current_speaker_index += 1
        return voice

    def add_emphasis(self, text: str) -> str:
        """
        Add natural emphasis to text for better speech.

        Makes important words stand out by capitalizing them.
        macOS `say` command emphasizes CAPITALIZED words.
        """
        if not self.config.enable_emphasis:
            return text

        # Words to emphasize
        emphasis_patterns = [
            r"\b(critical|important|urgent|error|failed|success|completed|ready)\b",
            r"\b(warning|caution|attention|note|remember)\b",
            r"\b(never|always|must|should|cannot)\b",
        ]

        for pattern in emphasis_patterns:
            text = re.sub(
                pattern, lambda m: m.group(0).upper(), text, flags=re.IGNORECASE
            )

        return text

    def add_natural_pauses(self, text: str) -> str:
        """
        Add natural pauses for better speech rhythm.

        Uses commas to create pauses at natural break points.
        """
        # Add pause after transition words (case-insensitive)
        text = re.sub(
            r"\b(however|therefore|meanwhile|additionally)\b",
            r"\1,",
            text,
            flags=re.IGNORECASE,
        )

        # Add pause before "because" and "since"
        text = re.sub(r"\s+(because|since)\b", r", \1", text)

        return text

    def get_speaking_rate(self, voice: str, base_rate: Optional[int] = None) -> int:
        """
        Get speaking rate for voice with natural variation.

        Makes conversation more natural by varying speeds slightly.
        """
        base = base_rate or self.config.default_rate

        if not self.config.vary_rate:
            return base

        # Different base rates for different voice personalities
        voice_rate_adjustments = {
            "Karen": 0,  # Standard
            "Moira": -5,  # Slightly slower, warm
            "Tingting": +10,  # Faster, energetic
            "Damayanti": -5,  # Calm, measured
            "Zosia": 0,  # Standard
            "Linh": +5,  # Quick, efficient
            "Kanya": -10,  # Very calm, peaceful
        }

        adjustment = voice_rate_adjustments.get(voice, 0)

        # Add small random variation for naturalness
        # Use voice name as seed for consistent but varied rates per voice
        import hashlib
        import random

        # Create deterministic but varied rate using voice name + base
        seed = int(hashlib.md5(f"{voice}{base}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        variation = rng.randint(-self.config.rate_variation, self.config.rate_variation)

        return base + adjustment + variation

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
        wait: bool = True,
        pause_after: Optional[float] = None,
    ) -> bool:
        """
        Speak text with natural pacing and intonation.

        Args:
            text: Text to speak
            voice: Voice name (auto-selects if None)
            rate: Speech rate (uses config default if None)
            wait: Wait for speech to complete

        Returns:
            True if speech succeeded
        """
        if self.config.mode == VoiceMode.QUIET:
            logger.debug(f"QUIET mode: {text}")
            return False

        # Auto-select voice if not specified
        if voice is None:
            voice = self.select_voice_for_topic(text)

        # Validate voice is in available set
        available = self.get_available_voices()
        if voice not in available:
            voice = available[0] if available else "Karen"

        # Get voice metadata for full name
        voice_meta = get_voice(voice)
        full_voice_name = voice_meta.full_name if voice_meta else voice

        # Enhance text
        text = self.add_emphasis(text)
        text = self.add_natural_pauses(text)

        # Get natural rate
        speaking_rate = self.get_speaking_rate(voice, rate)

        success = get_voice_serializer().speak(
            text,
            voice=full_voice_name,
            rate=speaking_rate,
            pause_after=pause_after,
            wait=wait,
        )
        if success:
            self.last_speaker = voice
            logger.info(f"Spoke with {voice}: {text[:50]}...")
        return success

    async def speak_async(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
        pause_after: Optional[float] = None,
    ) -> bool:
        """Async version of speak."""
        if self.config.mode == VoiceMode.QUIET:
            return False

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.speak(
                text,
                voice,
                rate,
                wait=True,
                pause_after=pause_after,
            ),
        )

    def conversation(
        self, messages: List[Tuple[str, str]], pause_between: Optional[float] = None
    ) -> bool:
        """
        Have multiple voices converse sequentially.

        Args:
            messages: List of (voice, text) tuples
            pause_between: Seconds to pause between speakers

        Returns:
            True if all speeches succeeded

        Example:
            >>> conv.conversation([
            ...     ("Karen", "Let's review this code"),
            ...     ("Tingting", "I see some improvements we can make"),
            ...     ("Zosia", "Security looks good"),
            ...     ("Karen", "Great! Let's merge it")
            ... ])
        """
        if self.config.mode == VoiceMode.QUIET:
            return False

        pause = pause_between or self.config.pause_between_speakers
        available = self.get_available_voices()

        success = True
        for i, (voice, text) in enumerate(messages):
            # Validate voice
            if voice not in available:
                logger.warning(
                    f"Voice {voice} not available in {self.config.mode.value} mode"
                )
                voice = available[0] if available else "Karen"

            pause_after = pause if i < len(messages) - 1 else 0.0
            if not self.speak(text, voice=voice, pause_after=pause_after):
                success = False
                break

        return success

    async def conversation_async(
        self, messages: List[Tuple[str, str]], pause_between: Optional[float] = None
    ) -> bool:
        """Async version of conversation."""
        if self.config.mode == VoiceMode.QUIET:
            return False

        pause = pause_between or self.config.pause_between_speakers
        available = self.get_available_voices()

        for i, (voice, text) in enumerate(messages):
            # Validate voice
            if voice not in available:
                voice = available[0] if available else "Karen"

            pause_after = pause if i < len(messages) - 1 else 0.0
            await self.speak_async(text, voice=voice, pause_after=pause_after)

        return True

    def set_mode(self, mode: VoiceMode):
        """Change voice mode (work/life/quiet)."""
        old_mode = self.config.mode
        self.config.save_mode(mode)
        logger.info(f"Voice mode changed: {old_mode.value} → {mode.value}")

        # Announce the change
        if mode == VoiceMode.WORK:
            self.speak(
                "Switching to work mode. Professional Karen only.", voice="Karen"
            )
        elif mode == VoiceMode.LIFE:
            self.speak(
                "Switching to life mode. All primary voices active!", voice="Karen"
            )
        elif mode == VoiceMode.QUIET:
            # Don't speak in quiet mode!
            logger.info("Quiet mode activated")

    def demo(self):
        """Run a demo conversation showing off the system!"""
        print("\n🎙️  Conversational Voice System Demo")
        print("=" * 50)
        print(f"Mode: {self.config.mode.value}")
        print(f"Available voices: {', '.join(self.get_available_voices())}\n")

        if self.config.mode == VoiceMode.WORK:
            # Work mode demo (Karen only)
            self.conversation(
                [
                    ("Karen", "This is work mode. Professional and focused."),
                    ("Karen", "Only Karen speaks in work mode."),
                    ("Karen", "Perfect for CITB development and client calls."),
                ]
            )

        elif self.config.mode == VoiceMode.LIFE:
            # Life mode demo (all primary voices)
            self.conversation(
                [
                    (
                        "Karen",
                        "Welcome to conversational voice! Let me introduce the team.",
                    ),
                    (
                        "Moira",
                        "Hello! I'm Moira from Ireland. I handle creative tasks and debugging.",
                    ),
                    (
                        "Tingting",
                        "Hi! Tingting here from China. I do code reviews and analytics.",
                    ),
                    (
                        "Damayanti",
                        "Greetings! I'm Damayanti from Bali. Project management is my specialty.",
                    ),
                    (
                        "Zosia",
                        "Hello Joseph! Zosia from Poland. Security and quality assurance.",
                    ),
                    ("Linh", "Hi! Linh from Vietnam. I manage GitHub operations."),
                    (
                        "Kanya",
                        "Sawadee ka! Kanya from Thailand. Wellness and mindfulness.",
                    ),
                    (
                        "Karen",
                        "Together, we make the brain come alive with personality!",
                    ),
                ]
            )

        else:  # QUIET
            print("   [Quiet mode - no speech output]")

        print("\n✅ Demo complete!")


# =============================================================================
# QUICK FUNCTIONS
# =============================================================================

_global_conv: Optional[ConversationalVoice] = None


def get_conversation() -> ConversationalVoice:
    """Get global conversation instance."""
    global _global_conv
    if _global_conv is None:
        _global_conv = ConversationalVoice()
    return _global_conv


def speak(text: str, voice: Optional[str] = None, rate: Optional[int] = None) -> bool:
    """Quick speak function."""
    return get_conversation().speak(text, voice, rate)


def conversation(messages: List[Tuple[str, str]]) -> bool:
    """Quick conversation function."""
    return get_conversation().conversation(messages)


def set_mode(mode: VoiceMode):
    """Quick mode change function."""
    get_conversation().set_mode(mode)


def demo():
    """Quick demo function."""
    get_conversation().demo()


# Test if run directly
if __name__ == "__main__":
    demo()
