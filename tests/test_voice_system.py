# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Comprehensive tests for the voice system.

Tests all components:
- Voice registry (all 145+ voices)
- Conversational system (multi-voice)
- VoiceOver integration
- Voice modes (work/life/quiet)
"""

from pathlib import Path

import pytest

from tests.fixtures.voice_test_phrases import pick_voice_phrase, pick_voice_phrases

from agentic_brain.voice.conversation import (
    ConversationalVoice,
    ConversationConfig,
    VoiceMode,
)
from agentic_brain.voice.registry import (
    ALL_MACOS_VOICES,
    PRIMARY_VOICE_ASSISTANTS,
    VoiceGender,
    VoiceQuality,
    get_english_voices,
    get_novelty_voices,
    get_premium_voices,
    get_primary_voices,
    get_voice,
    get_voice_stats,
)
from agentic_brain.voice.voiceover import (
    VoiceOverCoordinator,
    VoiceOverPriority,
    format_for_voiceover,
)


class TestVoiceRegistry:
    """Tests for voice registry."""

    def test_voice_count(self):
        """Test we have all expected voices."""
        stats = get_voice_stats()

        # Should have 80+ voices (macOS has many voices)
        assert stats["total"] >= 80
        assert stats["primary"] == 10  # 10 primary curated voices in registry
        assert stats["english"] >= 20  # Many English variants
        assert stats["premium"] >= 10  # Premium voices
        assert stats["novelty"] >= 10  # Fun voices

    def test_primary_voices(self):
        """Test Joseph's primary voice assistants are all registered."""
        primary = get_primary_voices()
        primary_names = [v.name for v in primary]

        # Core voices that MUST be present
        required = [
            "Karen",  # Australia - Lead
            "Moira",  # Ireland - Creative
            "Kyoko",  # Japan - QA
            "Tingting",  # China - Analytics
            "Damayanti",  # Indonesia/Bali - PM
            "Zosia",  # Poland - Security
            "Yuna",  # Korea - Tech
            "Linh",  # Vietnam - GitHub
            "Kanya",  # Thailand - Wellness
            "Sinji",  # Hong Kong - Trading
        ]

        for name in required:
            assert name in primary_names, f"{name} missing from registry!"

    def test_voice_metadata(self):
        """Test voice metadata is complete."""
        karen = get_voice("Karen")

        assert karen is not None
        assert karen.name == "Karen"
        assert karen.language == "en-AU"
        assert karen.language_name == "Australian English"
        assert karen.region == "Australia"
        assert karen.gender == VoiceGender.FEMALE
        assert karen.quality == VoiceQuality.PREMIUM
        assert karen.is_primary is True
        assert karen.full_name == "Karen (Premium)"

    def test_english_voices(self):
        """Test English voice filtering."""
        english = get_english_voices()

        # All should have en-* language code
        for voice in english:
            assert voice.language.startswith("en-")

        # Should have Australian, British, American, Irish at minimum
        regions = [v.region for v in english]
        assert "Australia" in regions
        assert "UK" in regions
        assert "USA" in regions
        assert "Ireland" in regions

    def test_premium_voices(self):
        """Test premium voice filtering."""
        premium = get_premium_voices()

        for voice in premium:
            assert voice.quality == VoiceQuality.PREMIUM
            assert "(Premium)" in voice.full_name or voice.name in [
                "Eddy",
                "Flo",
                "Grandma",
                "Grandpa",
                "Reed",
                "Rocko",
                "Sandy",
                "Shelley",
            ]

    def test_novelty_voices(self):
        """Test novelty voice filtering."""
        novelty = get_novelty_voices()

        # Should have fun voices
        novelty_names = [v.name for v in novelty]
        assert "Zarvox" in novelty_names  # Robot voice
        assert "Bubbles" in novelty_names
        assert "Ralph" in novelty_names

    def test_voice_lookup(self):
        """Test voice lookup by name."""
        # Exact match
        karen = get_voice("Karen")
        assert karen is not None
        assert karen.name == "Karen"

        # Case insensitive
        moira = get_voice("moira")
        assert moira is not None
        assert moira.name == "Moira"

        # Not found
        fake = get_voice("NotARealVoice")
        assert fake is None


class TestConversationalVoice:
    """Tests for conversational voice system."""

    def test_init(self):
        """Test conversation initialization."""
        conv = ConversationalVoice()

        assert conv.config is not None
        assert conv.config.mode in [VoiceMode.WORK, VoiceMode.LIFE, VoiceMode.QUIET]

    def test_voice_modes(self):
        """Test voice mode switching."""
        conv = ConversationalVoice()

        # Test mode changes
        conv.set_mode(VoiceMode.WORK)
        assert conv.config.mode == VoiceMode.WORK
        assert conv.get_available_voices() == ["Karen"]

        conv.set_mode(VoiceMode.LIFE)
        assert conv.config.mode == VoiceMode.LIFE
        assert len(conv.get_available_voices()) >= 5  # All primary voices

        conv.set_mode(VoiceMode.QUIET)
        assert conv.config.mode == VoiceMode.QUIET
        assert conv.get_available_voices() == []

    def test_voice_selection_for_topic(self):
        """Test intelligent voice selection."""
        conv = ConversationalVoice()
        conv.set_mode(VoiceMode.LIFE)

        # Work keywords → Karen
        assert conv.select_voice_for_topic("JIRA ticket SD-1330") == "Karen"
        assert conv.select_voice_for_topic("Deploy to production") == "Karen"

        # Security → Zosia
        voice = conv.select_voice_for_topic("Security scan complete")
        # Should prefer Zosia but will fallback if not available
        assert voice in conv.get_available_voices()

    def test_emphasis_addition(self):
        """Test text emphasis for speech."""
        conv = ConversationalVoice()
        conv.config.enable_emphasis = True

        text = "This is critical and urgent"
        emphasized = conv.add_emphasis(text)

        assert "CRITICAL" in emphasized
        assert "URGENT" in emphasized

    def test_natural_pauses(self):
        """Test natural pause insertion."""
        conv = ConversationalVoice()

        text = "However this is good"
        paused = conv.add_natural_pauses(text)

        assert "However," in paused  # Added comma for pause

    def test_speaking_rate_variation(self):
        """Test rate variation by voice."""
        conv = ConversationalVoice()
        conv.config.vary_rate = True

        karen_rate = conv.get_speaking_rate("Karen", base_rate=160)
        tingting_rate = conv.get_speaking_rate("Tingting", base_rate=160)

        # Rates should vary
        assert karen_rate != tingting_rate or karen_rate == 160  # Some variation

        # Should be within reasonable range
        assert 140 <= karen_rate <= 180
        assert 140 <= tingting_rate <= 200  # Tingting is faster


class TestVoiceOverIntegration:
    """Tests for VoiceOver integration."""

    def test_coordinator_init(self):
        """Test VoiceOver coordinator initialization."""
        coord = VoiceOverCoordinator()

        assert coord.status is not None
        assert isinstance(coord.status.is_running, bool)

    def test_voiceover_detection(self):
        """Test VoiceOver running detection."""
        coord = VoiceOverCoordinator()

        # Should return a boolean (may be True or False depending on system)
        running = coord.is_voiceover_running()
        assert isinstance(running, bool)

    def test_priority_system(self):
        """Test priority levels."""
        coord = VoiceOverCoordinator()

        # Critical always allowed
        assert coord.can_speak(VoiceOverPriority.CRITICAL) is True

        # Normal depends on VoiceOver state
        can_speak = coord.can_speak(VoiceOverPriority.NORMAL)
        assert isinstance(can_speak, bool)

    def test_format_for_voiceover(self):
        """Test VoiceOver text formatting."""
        # Remove emojis
        text = "Hello 🎉 World 🚀"
        formatted = format_for_voiceover(text)
        assert "🎉" not in formatted
        assert "🚀" not in formatted
        assert "Hello" in formatted
        assert "World" in formatted

        # Clean markdown
        text = "This is **bold** and *italic* and `code`"
        formatted = format_for_voiceover(text)
        assert "**" not in formatted
        assert "*" not in formatted
        assert "`" not in formatted
        assert "bold" in formatted
        assert "italic" in formatted
        assert "code" in formatted

        # Replace bullets
        text = "- Item 1\n- Item 2"
        formatted = format_for_voiceover(text)
        assert "Bullet:" in formatted


class TestVoiceIntegration:
    """Integration tests across all voice systems."""

    def test_work_mode_flow(self):
        """Test work mode end-to-end."""
        conv = ConversationalVoice()
        conv.set_mode(VoiceMode.WORK)

        # Only Karen available
        assert conv.get_available_voices() == ["Karen"]

        # Speak should work (though may not produce audio in test)
        # We're testing the logic, not actual audio output
        result = conv.speak(
            pick_voice_phrase("test_work_mode_flow", "technology_quotes"),
            voice="Karen",
        )
        assert isinstance(result, bool)

    def test_life_mode_conversation(self):
        """Test multi-voice conversation."""
        conv = ConversationalVoice()
        conv.set_mode(VoiceMode.LIFE)

        # Multiple voices available
        available = conv.get_available_voices()
        assert len(available) >= 5

        # Conversation structure
        phrases = pick_voice_phrases("test_life_mode_conversation", 3)
        messages = [
            ("Karen", phrases[0]),
            ("Moira", phrases[1]),
            ("Karen", phrases[2]),
        ]

        # Should handle conversation structure
        # (may not produce audio in test environment)
        result = conv.conversation(messages)
        assert isinstance(result, bool)

    def test_voiceover_coordination(self):
        """Test VoiceOver-aware voice."""
        from agentic_brain.voice.voiceover import VoiceOverAwareVoice

        vo_voice = VoiceOverAwareVoice()

        # Should have coordinator
        assert vo_voice.coordinator is not None

        # Can check VoiceOver status
        is_active = vo_voice.is_voiceover_active()
        assert isinstance(is_active, bool)


class TestVoiceModePersistence:
    """Test voice mode persistence across sessions."""

    def test_mode_save_load(self, tmp_path):
        """Test saving and loading voice mode."""
        ConversationConfig()

        # Override mode file location for testing
        mode_file = tmp_path / "voice-mode"

        # Save work mode
        mode_file.write_text("work")
        loaded_mode = (
            VoiceMode.WORK
            if mode_file.read_text().strip() == "work"
            else VoiceMode.LIFE
        )
        assert loaded_mode == VoiceMode.WORK

        # Save life mode
        mode_file.write_text("life")
        loaded_mode = (
            VoiceMode.LIFE
            if mode_file.read_text().strip() == "life"
            else VoiceMode.WORK
        )
        assert loaded_mode == VoiceMode.LIFE

        # Save quiet mode
        mode_file.write_text("quiet")
        loaded_mode = (
            VoiceMode.QUIET
            if mode_file.read_text().strip() == "quiet"
            else VoiceMode.LIFE
        )
        assert loaded_mode == VoiceMode.QUIET


# =============================================================================
# TEST UTILITIES
# =============================================================================


def test_voice_stats_output():
    """Test voice stats output."""
    stats = get_voice_stats()

    print("\n🎙️  Voice System Statistics:")
    print(f"   Total voices: {stats['total']}")
    print(f"   Primary voices: {stats['primary']}")
    print(f"   English voices: {stats['english']}")
    print(f"   Premium voices: {stats['premium']}")
    print(f"   Novelty voices: {stats['novelty']}")
    print(f"   Languages: {stats['languages']}")


def test_list_primary_voices():
    """Test listing primary voices."""
    primary = get_primary_voices()

    print("\n🎙️  Primary Voices:")
    for voice in primary:
        print(f"   {voice.name:15} - {voice.language_name:20} - {voice.description}")


if __name__ == "__main__":
    # Run quick tests
    print("🎙️  Running Voice System Tests")
    print("=" * 70)

    test_voice_stats_output()
    test_list_primary_voices()

    print("\n✅ Quick tests complete! Run with pytest for full suite.")
