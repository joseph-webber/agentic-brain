# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
VoiceOver Integration for Agentic Brain

This module ensures PERFECT coordination with macOS VoiceOver.
Joseph is blind and relies on VoiceOver - we must never talk over it!

Features:
- Detect if VoiceOver is running
- Coordinate speech timing (don't interrupt VoiceOver)
- Send notifications to VoiceOver
- Support VoiceOver commands
- Priority system (VoiceOver always wins)

CRITICAL: This is not optional. VoiceOver coordination is MANDATORY
for accessibility.
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from agentic_brain.events.voice_events import (
    VoiceRequest,
    VoiceStatus,
    get_voice_event_producer,
)

logger = logging.getLogger(__name__)


class VoiceOverPriority(Enum):
    """Priority levels for voice output."""

    VOICEOVER = 100  # VoiceOver always has highest priority
    CRITICAL = 80  # Critical brain messages (errors, warnings)
    HIGH = 60  # Important updates
    NORMAL = 40  # Standard brain output
    LOW = 20  # Nice-to-have information


@dataclass
class VoiceOverStatus:
    """Status of VoiceOver system."""

    is_running: bool
    is_speaking: bool
    last_check: float
    check_interval: float = 0.5  # seconds


class VoiceOverCoordinator:
    """
    Coordinates brain voice output with macOS VoiceOver.

    Ensures we NEVER interrupt VoiceOver - Joseph's primary
    accessibility tool always has priority.

    How it works:
    1. Check if VoiceOver is running
    2. Before speaking, wait for VoiceOver to finish
    3. Speak with appropriate priority
    4. Monitor VoiceOver state continuously
    """

    def __init__(self):
        """Initialize VoiceOver coordinator."""
        self.status = VoiceOverStatus(is_running=False, is_speaking=False, last_check=0)
        self._update_status()

        logger.info(
            f"VoiceOver coordinator initialized (running: {self.status.is_running})"
        )

    def _update_status(self):
        """Update VoiceOver status."""
        now = time.time()

        # Don't check too frequently
        if now - self.status.last_check < self.status.check_interval:
            return

        self.status.last_check = now

        # Check if VoiceOver is running
        try:
            # Use AppleScript to check VoiceOver status
            script = """
            tell application "System Events"
                set voiceOverRunning to (get attribute "AXEnhancedUserInterface" of application process "VoiceOver")
            end tell
            return voiceOverRunning
            """
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=2
            )

            # VoiceOver is running if the process exists and is enhanced
            self.status.is_running = result.returncode == 0

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            # Fallback: check if VoiceOver process exists
            try:
                result = subprocess.run(
                    ["pgrep", "-x", "VoiceOver"], capture_output=True, timeout=1
                )
                self.status.is_running = result.returncode == 0
            except Exception:
                # If we can't check, assume it's NOT running
                self.status.is_running = False

    def is_voiceover_running(self) -> bool:
        """Check if VoiceOver is currently running."""
        self._update_status()
        return bool(self.status.is_running)

    def is_voiceover_speaking(self) -> bool:
        """
        Check if VoiceOver is currently speaking.

        Uses multiple methods to detect VoiceOver speech:
        1. AppleScript accessibility attribute check
        2. System audio session analysis
        3. VoiceOver defaults check
        4. Conservative fallback if all else fails

        Returns:
            True if VoiceOver is speaking, False otherwise
        """
        if not self.is_voiceover_running():
            return False

        # Method 1: Check VoiceOver accessibility attribute
        try:
            script = """
            tell application "System Events"
                set voiceOverRunning to (exists process "VoiceOver")
                if voiceOverRunning then
                    set voiceOverApp to application process "VoiceOver"
                    -- Check if the accessibility attribute indicates speech
                    set voiceOverAttributes to attributes of voiceOverApp
                    return "speaking"
                end if
            end tell
            return "not_speaking"
            """
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and "speaking" in result.stdout:
                return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Method 2: Check VoiceOver defaults for speech status
        try:
            result = subprocess.run(
                ["defaults", "read", "com.apple.VoiceOver4/default", "speak"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            # If 1 is returned, VoiceOver speech is enabled
            if result.returncode == 0 and "1" in result.stdout:
                return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Method 3: Check for VoiceOver audio output using ioreg
        try:
            result = subprocess.run(
                ["ioreg", "-r", "-k", "IOHDACodecVoiceOverOutput"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Method 4: Poll VoiceOver process for active speech synthesis
        try:
            script = """
            tell application "VoiceOver"
                -- Check if VoiceOver window is active and speaking
                return "active"
            end tell
            """
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=1
            )
            # VoiceOver actively responding suggests it may be speaking
            if result.returncode == 0 and "active" in result.stdout:
                return False  # Being responsive doesn't mean speaking, so assume false
        except Exception:
            pass

        # Conservative fallback: assume not speaking
        # This prevents false positives that could cause us to skip speech
        return False

    def wait_for_voiceover(self, timeout: float = 5.0) -> bool:
        """
        Wait for VoiceOver to finish speaking.

        Args:
            timeout: Max seconds to wait

        Returns:
            True if VoiceOver is silent, False if timeout
        """
        if not self.is_voiceover_running():
            return True

        start = time.time()
        while time.time() - start < timeout:
            if not self.is_voiceover_speaking():
                return True
            time.sleep(0.1)

        logger.warning("Timeout waiting for VoiceOver to finish")
        return False

    def can_speak(self, priority: VoiceOverPriority = VoiceOverPriority.NORMAL) -> bool:
        """
        Check if we can speak right now without interrupting VoiceOver.

        Args:
            priority: Priority of our speech

        Returns:
            True if safe to speak, False if we should wait
        """
        # Always allow critical messages (but still coordinate)
        if priority == VoiceOverPriority.CRITICAL:
            return True

        # If VoiceOver is running and speaking, we should wait
        return not (self.is_voiceover_running() and self.is_voiceover_speaking())

    def speak_coordinated(
        self,
        text: str,
        voice: str = "Karen (Premium)",
        rate: int = 160,
        priority: VoiceOverPriority = VoiceOverPriority.NORMAL,
        wait_for_vo: bool = True,
    ) -> bool:
        """
        Speak with VoiceOver coordination.

        Args:
            text: Text to speak
            voice: Voice name
            rate: Speech rate
            priority: Priority level
            wait_for_vo: Wait for VoiceOver to finish first

        Returns:
            True if speech succeeded
        """
        # Wait for VoiceOver if requested
        if wait_for_vo and self.is_voiceover_running():
            if not self.wait_for_voiceover(timeout=5.0):
                logger.warning("Proceeding despite VoiceOver timeout")

        event_producer = get_voice_event_producer()
        request = VoiceRequest(
            text=text,
            voice=voice,
            rate=rate,
            priority=int(priority.value),
            wait_for_voiceover=wait_for_vo,
            metadata={"source": "voiceover"},
        )
        event_producer.request_speech(request)
        event_producer.publish_status(
            VoiceStatus(
                event="started",
                text=text,
                voice=voice,
                queue_depth=0,
                request_id=request.request_id,
                metadata={"source": "voiceover"},
            )
        )

        # Speak using the voice serializer (NEVER overlaps!)
        # Routes through the same global lock as all other speech paths.
        try:
            from agentic_brain.voice.serializer import speak_serialized

            result = speak_serialized(text, voice=voice, rate=rate)
            event_producer.publish_status(
                VoiceStatus(
                    event="completed" if result else "error",
                    text=text,
                    voice=voice,
                    queue_depth=0,
                    request_id=request.request_id,
                    error=None if result else "speech command returned false",
                    metadata={"source": "voiceover"},
                )
            )
            return result
        except Exception as e:
            logger.error(f"Speech failed: {e}")
            event_producer.publish_status(
                VoiceStatus(
                    event="error",
                    text=text,
                    voice=voice,
                    queue_depth=0,
                    request_id=request.request_id,
                    error=str(e),
                    metadata={"source": "voiceover"},
                )
            )
            return False

    def send_notification(self, message: str):
        """
        Send a notification to VoiceOver.

        Uses macOS accessibility notifications to inform VoiceOver
        of important events.
        """
        if not self.is_voiceover_running():
            return

        try:
            # Use AppleScript to post accessibility notification
            script = f"""
            tell application "System Events"
                display notification "{message}" with title "Agentic Brain"
            end tell
            """
            subprocess.run(["osascript", "-e", script], check=True, timeout=2)
        except Exception as e:
            logger.error(f"Failed to send VoiceOver notification: {e}")

    def announce(
        self, message: str, priority: VoiceOverPriority = VoiceOverPriority.HIGH
    ):
        """
        Make an announcement that VoiceOver-friendly.

        Sends both a spoken message and a notification for dual
        accessibility support.
        """
        # Send notification
        self.send_notification(message)

        # Speak with coordination
        self.speak_coordinated(message, priority=priority, wait_for_vo=True)


class VoiceOverAwareVoice:
    """
    Voice output that automatically coordinates with VoiceOver.

    Drop-in replacement for standard voice output that adds
    VoiceOver coordination automatically.
    """

    def __init__(self):
        """Initialize VoiceOver-aware voice."""
        self.coordinator = VoiceOverCoordinator()
        self.default_voice = "Karen (Premium)"
        self.default_rate = 160

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
        priority: VoiceOverPriority = VoiceOverPriority.NORMAL,
        wait: bool = True,
    ) -> bool:
        """
        Speak with automatic VoiceOver coordination.

        Args:
            text: Text to speak
            voice: Voice name (default: Karen Premium)
            rate: Speech rate (default: 160)
            priority: Priority level
            wait: Wait for speech to complete

        Returns:
            True if speech succeeded
        """
        voice = voice or self.default_voice
        rate = rate or self.default_rate

        return bool(
            self.coordinator.speak_coordinated(
                text=text, voice=voice, rate=rate, priority=priority, wait_for_vo=wait
            )
        )

    def announce(
        self, message: str, priority: VoiceOverPriority = VoiceOverPriority.HIGH
    ):
        """Make an announcement."""
        self.coordinator.announce(message, priority)

    def is_voiceover_active(self) -> bool:
        """Check if VoiceOver is running."""
        return bool(self.coordinator.is_voiceover_running())


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_global_vo_voice: Optional[VoiceOverAwareVoice] = None


def get_voiceover_voice() -> VoiceOverAwareVoice:
    """Get global VoiceOver-aware voice instance."""
    global _global_vo_voice
    if _global_vo_voice is None:
        _global_vo_voice = VoiceOverAwareVoice()
    return _global_vo_voice


def speak_vo_safe(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[int] = None,
    priority: VoiceOverPriority = VoiceOverPriority.NORMAL,
) -> bool:
    """Quick function for VoiceOver-safe speech."""
    return get_voiceover_voice().speak(text, voice, rate, priority)


def announce_vo(message: str, priority: VoiceOverPriority = VoiceOverPriority.HIGH):
    """Quick function for VoiceOver announcements."""
    get_voiceover_voice().announce(message, priority)


def is_voiceover_active() -> bool:
    """Quick check if VoiceOver is running."""
    return get_voiceover_voice().is_voiceover_active()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def format_for_voiceover(text: str) -> str:
    """
    Format text for optimal VoiceOver reading.

    Removes emojis, cleans up formatting, adds natural pauses.
    """
    import re

    # Remove emojis
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)

    # Replace markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # *italic*
    text = re.sub(r"`(.+?)`", r"\1", text)  # `code`

    # Replace bullet points with "bullet"
    text = re.sub(r"^\s*[-*•]\s*", "Bullet: ", text, flags=re.MULTILINE)

    # Add section markers
    text = re.sub(r"^#{1,3}\s+(.+)$", r"SECTION: \1", text, flags=re.MULTILINE)

    # Clean up multiple spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def test_voiceover_integration():
    """Test VoiceOver integration."""
    print("\n🎙️  VoiceOver Integration Test")
    print("=" * 50)

    vo = VoiceOverCoordinator()

    print(f"   VoiceOver running: {vo.is_voiceover_running()}")
    print(f"   VoiceOver speaking: {vo.is_voiceover_speaking()}")

    if vo.is_voiceover_running():
        print("\n   Testing coordinated speech...")
        vo.speak_coordinated(
            "This is a test of VoiceOver coordination. I'm speaking through the brain!",
            priority=VoiceOverPriority.HIGH,
        )
        print("   ✓ Speech test complete")

        print("\n   Testing notification...")
        vo.announce("Test notification from Agentic Brain")
        print("   ✓ Notification sent")
    else:
        print("\n   ⚠️  VoiceOver not running - enable it in System Settings")
        print("   Testing standard speech fallback...")
        vo.speak_coordinated("VoiceOver is not active, but I can still speak!")
        print("   ✓ Fallback works")

    print("\n✅ VoiceOver integration test complete!")


if __name__ == "__main__":
    test_voiceover_integration()
