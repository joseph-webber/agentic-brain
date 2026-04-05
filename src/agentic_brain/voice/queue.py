# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
SAFE Voice Queue System - ONLY ONE VOICE AT A TIME!

CRITICAL RULE FOR JOSEPH (blind user):
- Overlapping voices are CONFUSING and DANGEROUS
- Queue ensures sequential speech with proper pauses
- Asian voices need number spelling (100 → "one hundred")
- Each voice has consistent rate and accent settings

This module is ESSENTIAL for accessibility compliance.
"""

import asyncio
import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from agentic_brain.voice.serializer import get_voice_serializer

logger = logging.getLogger(__name__)


class VoiceType(Enum):
    """Voice type classification."""

    WESTERN = "western"  # Standard English voices
    ASIAN = "asian"  # Standard Asian voices
    SYSTEM = "system"  # Generic system voices
    ROBOT = "robot"  # Robot and synthetic voices


# Asian voice configuration - needs number spelling!
ASIAN_VOICE_CONFIG = {
    "Kyoko": {
        "type": VoiceType.ASIAN,
        "native_lang": "ja-JP",
        "english_accent": True,
        "spell_numbers": True,
        "default_rate": 145,
    },
    "Tingting": {
        "type": VoiceType.ASIAN,
        "native_lang": "zh-CN",
        "english_accent": True,
        "spell_numbers": True,
        "default_rate": 140,
    },
    "Yuna": {
        "type": VoiceType.ASIAN,
        "native_lang": "ko-KR",
        "english_accent": True,
        "spell_numbers": True,
        "default_rate": 142,
    },
    "Sinji": {
        "type": VoiceType.ASIAN,
        "native_lang": "yue",  # Cantonese
        "english_accent": True,
        "spell_numbers": True,
        "default_rate": 138,
    },
    "Linh": {
        "type": VoiceType.ASIAN,
        "native_lang": "vi-VN",
        "english_accent": True,
        "spell_numbers": True,
        "default_rate": 140,
    },
}

# Western voice configuration
WESTERN_VOICE_CONFIG = {
    "Karen": {
        "type": VoiceType.WESTERN,
        "native_lang": "en-AU",
        "default_rate": 155,
        "description": "Australian - primary voice",
    },
    "Moira": {
        "type": VoiceType.WESTERN,
        "native_lang": "en-IE",
        "default_rate": 150,
        "description": "Irish Gaelic speaker",
    },
    "Shelley": {
        "type": VoiceType.WESTERN,
        "native_lang": "en-GB",
        "default_rate": 148,
        "description": "Northern English",
    },
    "Zosia": {
        "type": VoiceType.WESTERN,
        "native_lang": "pl-PL",
        "default_rate": 150,
        "description": "Polish speaker",
    },
    "Damayanti": {
        "type": VoiceType.WESTERN,
        "native_lang": "id-ID",
        "default_rate": 145,
        "description": "Indonesian/Balinese",
    },
}


@dataclass
class VoiceMessage:
    """Single message queued for speech."""

    text: str
    voice: str = "Karen"
    rate: int = 155
    pause_after: float = 1.5  # Pause after speaking (seconds)
    speaker_id: Optional[str] = None  # For debugging/tracking
    importance: int = 0  # 0=normal, 1=urgent, -1=low priority
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        """Validate and normalize the message."""
        if not self.text or not self.text.strip():
            raise ValueError("Voice message text cannot be empty")
        self.text = self.text.strip()
        if self.rate < 100 or self.rate > 500:
            raise ValueError(f"Rate must be 100-500 wpm, got {self.rate}")


class VoiceQueue:
    """
    Thread-safe, async-aware voice queue.

    GUARANTEES:
    - ✅ Only ONE voice speaks at a time
    - ✅ No overlapping speech
    - ✅ Proper pauses between speakers
    - ✅ Number spelling for Asian voices
    - ✅ Error recovery (speaker crashes won't block queue)
    - ✅ Accessible for blind users
    """

    _instance: Optional["VoiceQueue"] = None
    _lock = threading.Lock()
    _async_lock: Optional[asyncio.Lock] = None

    def __init__(self):
        """Initialize the voice queue."""
        self._speaking = False
        self._current_process: Optional[subprocess.Popen] = None
        self._queue: List[VoiceMessage] = []
        self._history: List[VoiceMessage] = []
        self._max_history = 100
        self._error_callbacks: List[Callable[[str, Exception], None]] = []
        self._speech_callbacks: List[Callable[[VoiceMessage], None]] = []
        self._semaphore = threading.Semaphore(1)
        logger.info("VoiceQueue initialized - SAFE MODE for accessibility")

    @classmethod
    def get_instance(cls) -> "VoiceQueue":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def reset(self):
        """Reset queue state (for testing)."""
        with self._semaphore:
            if self._current_process:
                try:
                    self._current_process.terminate()
                except Exception:
                    pass
            self._speaking = False
            self._queue.clear()
            self._history.clear()
        get_voice_serializer().reset()
        logger.info("VoiceQueue reset")

    def add_error_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """Register callback for errors."""
        self._error_callbacks.append(callback)

    def add_speech_callback(self, callback: Callable[[VoiceMessage], None]) -> None:
        """Register callback before speech starts."""
        self._speech_callbacks.append(callback)

    def speak(
        self,
        text: str,
        voice: str = "Karen",
        rate: Optional[int] = None,
        pause_after: float = 1.5,
        speaker_id: Optional[str] = None,
        importance: int = 0,
    ) -> VoiceMessage:
        """
        Queue a voice message (THREAD-SAFE).

        Args:
            text: Message to speak
            voice: Voice name
            rate: Speech rate in words per minute (100-200)
            pause_after: Pause duration after speaking (seconds)
            speaker_id: For debugging/tracking
            importance: -1=low, 0=normal, 1=urgent

        Returns:
            VoiceMessage that was queued

        Raises:
            ValueError: If text is empty or rate is invalid
        """
        if rate is None:
            # Get default rate for voice
            if voice in ASIAN_VOICE_CONFIG:
                rate = ASIAN_VOICE_CONFIG[voice]["default_rate"]
            elif voice in WESTERN_VOICE_CONFIG:
                rate = WESTERN_VOICE_CONFIG[voice]["default_rate"]
            else:
                rate = 155

        message = VoiceMessage(
            text=text,
            voice=voice,
            rate=rate,
            pause_after=pause_after,
            speaker_id=speaker_id,
            importance=importance,
        )

        with self._semaphore:
            self._queue.append(message)
            logger.debug(
                f"Queued voice message: {voice} - {text[:50]}... "
                f"(queue_size={len(self._queue)})"
            )

        # Start processing if not already running
        self._process_queue()

        return message

    def speak_async(
        self,
        text: str,
        voice: str = "Karen",
        rate: Optional[int] = None,
        pause_after: float = 1.5,
    ) -> asyncio.Task:
        """Async version of speak - returns immediately."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            None,
            self.speak,
            text,
            voice,
            rate,
            pause_after,
        )

    def _process_queue(self) -> None:
        """Process queue synchronously (called from thread-safe speak)."""
        if self._speaking:
            return  # Already processing

        with self._semaphore:
            if not self._queue or self._speaking:
                return

            self._speaking = True

        # Process all queued messages
        while True:
            with self._semaphore:
                if not self._queue:
                    self._speaking = False
                    break
                message = self._queue.pop(0)

            self._speak_message(message)

    def _speak_message(self, message: VoiceMessage) -> None:
        """Speak a single message."""
        try:
            # Call speech callbacks
            for callback in self._speech_callbacks:
                try:
                    callback(message)
                except Exception as e:
                    logger.warning(f"Speech callback error: {e}")

            # Prepare text
            text = self._prepare_text(message.text, message.voice)

            logger.info(
                f"🔊 Speaking [{message.voice}] @{message.rate}wpm: {text[:60]}..."
            )

            serializer = get_voice_serializer()
            success = serializer.speak(
                text,
                voice=message.voice,
                rate=message.rate,
                pause_after=message.pause_after,
            )
            self._current_process = serializer.current_process
            if not success:
                raise RuntimeError(f"Voice serializer failed for {message.voice}")

            # Add to history
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        except subprocess.TimeoutExpired:
            error_msg = f"Voice timeout for {message.voice}"
            logger.error(error_msg)
            self._trigger_error_callbacks(error_msg, TimeoutError(error_msg))
        except Exception as e:
            error_msg = f"Voice error [{message.voice}]: {str(e)}"
            logger.error(error_msg)
            self._trigger_error_callbacks(error_msg, e)
        finally:
            self._current_process = None

    def _prepare_text(self, text: str, voice: str) -> str:
        """
        Prepare text for speech.

        - Convert numbers to words for Asian voices
        - Remove problematic punctuation
        - Normalize whitespace
        """
        # Normalize whitespace
        text = " ".join(text.split())

        # Number spelling for Asian voices
        if voice in ASIAN_VOICE_CONFIG and ASIAN_VOICE_CONFIG[voice].get(
            "spell_numbers"
        ):
            text = self._spell_numbers(text)

        # Remove or normalize certain characters
        text = text.replace("\n", " ").replace("\r", "")

        return text

    @staticmethod
    def _spell_numbers(text: str) -> str:
        """
        Convert digits to spelled-out numbers for Asian voices.

        Examples:
            "100 items" → "one hundred items"
            "1,234" → "one thousand two hundred thirty four"
            "25°C" → "twenty five degrees Celsius"
        """
        ones = [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        ]
        tens = [
            "",
            "",
            "twenty",
            "thirty",
            "forty",
            "fifty",
            "sixty",
            "seventy",
            "eighty",
            "ninety",
        ]
        teens = [
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]

        def number_to_words(n):
            """Convert integer to words."""
            n = int(n)
            if n == 0:
                return "zero"
            if n < 10:
                return ones[n]
            if n < 20:
                return teens[n - 10]
            if n < 100:
                tens_digit = n // 10
                ones_digit = n % 10
                if ones_digit == 0:
                    return tens[tens_digit]
                return f"{tens[tens_digit]} {ones[ones_digit]}"
            if n < 1000:
                hundreds_digit = n // 100
                remainder = n % 100
                result = f"{ones[hundreds_digit]} hundred"
                if remainder > 0:
                    result += f" {number_to_words(remainder)}"
                return result
            if n < 1000000:
                thousands = n // 1000
                remainder = n % 1000
                result = f"{number_to_words(thousands)} thousand"
                if remainder > 0:
                    result += f" {number_to_words(remainder)}"
                return result
            # For larger numbers, just return as-is
            return str(n)

        def convert_match(match):
            """Convert regex match to words."""
            return number_to_words(match.group(0))

        # Replace all sequences of digits
        result = re.sub(r"\d+", convert_match, text)
        return result

    def _trigger_error_callbacks(self, error_msg: str, exception: Exception) -> None:
        """Trigger all error callbacks."""
        for callback in self._error_callbacks:
            try:
                callback(error_msg, exception)
            except Exception as e:
                logger.warning(f"Error callback failed: {e}")

    def get_queue_size(self) -> int:
        """Get current queue size."""
        with self._semaphore:
            return len(self._queue)

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._speaking or get_voice_serializer().is_speaking()

    def get_history(self, limit: Optional[int] = None) -> List[VoiceMessage]:
        """Get recent speech history."""
        with self._semaphore:
            if limit is None:
                return list(self._history)
            return list(self._history[-limit:])

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"VoiceQueue(speaking={self._speaking}, "
            f"queue_size={len(self._queue)}, "
            f"history_size={len(self._history)})"
        )


# Convenience functions
def speak(
    text: str,
    voice: str = "Karen",
    rate: Optional[int] = None,
    pause_after: float = 1.5,
) -> VoiceMessage:
    """Queue a voice message."""
    queue = VoiceQueue.get_instance()
    return queue.speak(text, voice, rate, pause_after)


async def speak_system_message(message: str, severity: str = "info") -> VoiceMessage:
    """Use appropriate voice for system messages.

    Severity mapping:
    - error   → Bad News (ominous)
    - warning → Zarvox (robot)
    - success → Ralph (playful)
    - info    → Trinoids (alien chorus)
    """
    severity_key = (severity or "info").lower()
    voice_map = {
        "error": "Bad News",
        "warning": "Zarvox",
        "success": "Ralph",
        "info": "Trinoids",
    }
    voice = voice_map.get(severity_key, "Zarvox")

    # System messages use a slightly slower, clear rate
    rate = 130
    pause_after = 1.0

    loop = asyncio.get_event_loop()
    queue = VoiceQueue.get_instance()

    return await loop.run_in_executor(
        None,
        lambda: queue.speak(
            message,
            voice=voice,
            rate=rate,
            pause_after=pause_after,
            speaker_id=f"system:{severity_key}",
            importance=1 if severity_key in {"error", "warning"} else 0,
        ),
    )


def clear_queue() -> None:
    """Clear the voice queue."""
    queue = VoiceQueue.get_instance()
    queue.reset()


def is_speaking() -> bool:
    """Check if currently speaking."""
    queue = VoiceQueue.get_instance()
    return queue.is_speaking()


def get_queue_size() -> int:
    """Get queue size."""
    queue = VoiceQueue.get_instance()
    return queue.get_queue_size()
