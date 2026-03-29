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
Tests for Chat Intelligence Module
==================================

Tests for conversation intelligence features:
- IntentDetector
- MoodDetector
- ConversationSummarizer
- ClarificationGenerator
- ConfidenceScorer
- PersonalityManager
- ResponseLengthController
- BookmarkManager
- CorrectionLearner
- SafetyChecker
"""

from datetime import UTC, datetime, timezone

import pytest

from agentic_brain.chat.intelligence import (
    # Bookmarks
    BookmarkManager,
    # Clarification
    ClarificationGenerator,
    # Scoring
    ConfidenceScorer,
    # Summarization
    ConversationSummarizer,
    # Learning
    Correction,
    CorrectionLearner,
    # Enums
    Intent,
    # Detectors
    IntentDetector,
    Mood,
    MoodDetector,
    PersonalityManager,
    # Personality
    PersonalityProfile,
    # Response control
    ResponseLengthController,
    # Safety
    SafetyChecker,
)

# =============================================================================
# Intent Detector Tests
# =============================================================================


class TestIntentDetector:
    """Tests for IntentDetector."""

    def test_detect_action_intent(self):
        """Test detection of action intent."""
        detector = IntentDetector()

        action_messages = [
            "Create a new user account",
            "Fix the login bug",
            "Deploy to production",
            "Run the tests",
            "Delete the old files",
        ]

        for msg in action_messages:
            intent, confidence = detector.detect_sync(msg)
            assert intent == Intent.ACTION, f"Expected ACTION for '{msg}'"
            assert confidence > 0.1

    def test_detect_question_intent(self):
        """Test detection of question intent."""
        detector = IntentDetector()

        question_messages = [
            "What is the status?",
            "How do I configure this?",
            "Why did the test fail?",
            "Can you help me?",
            "Where is the config file?",
        ]

        for msg in question_messages:
            intent, confidence = detector.detect_sync(msg)
            assert intent == Intent.QUESTION, f"Expected QUESTION for '{msg}'"
            assert confidence > 0.1

    def test_detect_complaint_intent(self):
        """Test detection of complaint intent."""
        detector = IntentDetector()

        complaint_messages = [
            "This is broken again!",
            "It still doesn't work",
            "The system always fails",
        ]

        for msg in complaint_messages:
            intent, confidence = detector.detect_sync(msg)
            assert intent == Intent.COMPLAINT, f"Expected COMPLAINT for '{msg}'"
            assert confidence > 0.1

    def test_detect_confirmation_intent(self):
        """Test detection of confirmation intent."""
        detector = IntentDetector()

        confirmation_messages = [
            "Yes, that's correct",
            "Correct, exactly right",
            "Nope, wrong",
        ]

        for msg in confirmation_messages:
            intent, confidence = detector.detect_sync(msg)
            assert intent == Intent.CONFIRMATION, f"Expected CONFIRMATION for '{msg}'"

    def test_detect_chat_intent(self):
        """Test detection of casual chat intent."""
        detector = IntentDetector()

        chat_messages = [
            "Hello!",
            "Thanks for your help",
            "Good morning",
        ]

        for msg in chat_messages:
            intent, confidence = detector.detect_sync(msg)
            assert intent == Intent.CHAT, f"Expected CHAT for '{msg}'"

    def test_question_mark_boosts_question(self):
        """Test that question marks boost question confidence."""
        detector = IntentDetector()

        intent, conf = detector.detect_sync("What?")
        assert intent == Intent.QUESTION
        assert conf > 0.3  # Question mark should boost


# =============================================================================
# Mood Detector Tests
# =============================================================================


class TestMoodDetector:
    """Tests for MoodDetector."""

    def test_detect_frustrated_mood(self):
        """Test detection of frustrated mood."""
        detector = MoodDetector()

        frustrated_messages = [
            "This is broken AGAIN!!!",
            "Ugh, come on, this doesn't work",
            "It STILL doesn't work!!!",
        ]

        for msg in frustrated_messages:
            mood, confidence = detector.detect(msg)
            assert mood == Mood.FRUSTRATED, f"Expected FRUSTRATED for '{msg}'"
            assert confidence > 0.1

    def test_detect_urgent_mood(self):
        """Test detection of urgent mood."""
        detector = MoodDetector()

        urgent_messages = [
            "This is urgent, need help ASAP",
            "Emergency! Production is down",
            "Need this fixed NOW",
        ]

        for msg in urgent_messages:
            mood, confidence = detector.detect(msg)
            assert mood == Mood.URGENT, f"Expected URGENT for '{msg}'"
            assert confidence > 0.2

    def test_detect_happy_mood(self):
        """Test detection of happy mood."""
        detector = MoodDetector()

        happy_messages = [
            "Thanks so much! This is perfect!",
            "Awesome work, love it!",
            "Great, thanks! :)",
        ]

        for msg in happy_messages:
            mood, confidence = detector.detect(msg)
            assert mood == Mood.HAPPY, f"Expected HAPPY for '{msg}'"

    def test_detect_confused_mood(self):
        """Test detection of confused mood."""
        detector = MoodDetector()

        confused_messages = [
            "I'm confused, what do you mean?",
            "This makes no sense, help me understand",
            "Huh??? I don't get it",
        ]

        for msg in confused_messages:
            mood, confidence = detector.detect(msg)
            assert mood == Mood.CONFUSED, f"Expected CONFUSED for '{msg}'"

    def test_detect_neutral_mood(self):
        """Test detection of neutral mood."""
        detector = MoodDetector()

        mood, confidence = detector.detect("Please update the file")
        assert mood == Mood.NEUTRAL

    def test_caps_increases_frustration(self):
        """Test that ALL CAPS increases frustration score."""
        detector = MoodDetector()

        mood1, conf1 = detector.detect("this is broken")
        mood2, conf2 = detector.detect("THIS IS BROKEN")

        assert conf2 > conf1 or mood2 == Mood.FRUSTRATED


# =============================================================================
# Confidence Scorer Tests
# =============================================================================


class TestConfidenceScorer:
    """Tests for ConfidenceScorer."""

    def test_high_confidence_with_sources(self):
        """Test that having sources increases confidence."""
        scorer = ConfidenceScorer()

        response = "According to the documentation, the answer is X."
        score_with = scorer.score(response, has_sources=True)
        score_without = scorer.score(response, has_sources=False)

        assert score_with > score_without

    def test_low_confidence_with_hedging(self):
        """Test that hedging language reduces confidence."""
        scorer = ConfidenceScorer()

        confident = "The answer is 42."
        hedging = "I think the answer might be 42, but I'm not sure."

        score_confident = scorer.score(confident)
        score_hedging = scorer.score(hedging)

        assert score_confident > score_hedging

    def test_certainty_phrases_boost_confidence(self):
        """Test that certainty phrases boost confidence."""
        scorer = ConfidenceScorer()

        certain = "The answer is definitely 42. This is confirmed."
        normal = "The answer is 42."

        score_certain = scorer.score(certain)
        score_normal = scorer.score(normal)

        assert score_certain > score_normal

    def test_should_ask_for_help(self):
        """Test the help threshold check."""
        scorer = ConfidenceScorer()

        assert scorer.should_ask_for_help(0.3, threshold=0.5) is True
        assert scorer.should_ask_for_help(0.7, threshold=0.5) is False

    def test_score_range(self):
        """Test that scores are in valid range."""
        scorer = ConfidenceScorer()

        test_responses = [
            "I think maybe it could be something.",
            "Definitely, certainly, absolutely yes!",
            "The answer is 42.",
        ]

        for response in test_responses:
            score = scorer.score(response)
            assert 0.0 <= score <= 1.0


# =============================================================================
# Personality Manager Tests
# =============================================================================


class TestPersonalityManager:
    """Tests for PersonalityManager."""

    def test_default_profiles_exist(self):
        """Test that default profiles are available."""
        manager = PersonalityManager()

        assert "professional" in manager.list_profiles()
        assert "friendly" in manager.list_profiles()
        assert "technical" in manager.list_profiles()
        assert "brief" in manager.list_profiles()

    def test_get_default_profile(self):
        """Test getting the default profile."""
        manager = PersonalityManager()

        profile = manager.get_profile()
        assert profile.name == "professional"
        assert profile.formality > 0.5

    def test_switch_personality(self):
        """Test switching personalities."""
        manager = PersonalityManager()

        manager.switch("friendly")
        profile = manager.get_profile()

        assert profile.name == "friendly"
        assert profile.emoji_usage is True
        assert profile.formality < 0.5

    def test_switch_to_invalid_personality(self):
        """Test switching to non-existent personality keeps current."""
        manager = PersonalityManager()

        manager.switch("nonexistent")
        profile = manager.get_profile()

        assert profile.name == "professional"

    def test_add_custom_profile(self):
        """Test adding a custom personality profile."""
        manager = PersonalityManager()

        custom = PersonalityProfile(
            name="pirate",
            tone="casual",
            verbosity="normal",
            emoji_usage=True,
            formality=0.1,
            system_prompt_additions="Speak like a pirate. Arr!",
        )

        manager.add_profile(custom)
        manager.switch("pirate")

        assert manager.get_profile().name == "pirate"
        assert "pirate" in manager.list_profiles()


# =============================================================================
# Response Length Controller Tests
# =============================================================================


class TestResponseLengthController:
    """Tests for ResponseLengthController."""

    def test_detect_brief_preference(self):
        """Test detection of brief preference."""
        controller = ResponseLengthController()

        brief_messages = [
            "Give me a brief summary",
            "TLDR please",
            "Just tell me quickly",
        ]

        for msg in brief_messages:
            pref = controller.detect_preference(msg)
            assert pref == "brief", f"Expected 'brief' for '{msg}'"

    def test_detect_detailed_preference(self):
        """Test detection of detailed preference."""
        controller = ResponseLengthController()

        detailed_messages = [
            "Explain in detail",
            "Tell me more about this",
            "I need all the details",
        ]

        for msg in detailed_messages:
            pref = controller.detect_preference(msg)
            assert pref == "detailed", f"Expected 'detailed' for '{msg}'"

    def test_detect_normal_preference(self):
        """Test detection of normal preference."""
        controller = ResponseLengthController()

        pref = controller.detect_preference("What is the status?")
        assert pref == "normal"

    def test_token_limits(self):
        """Test token limits for each preference."""
        controller = ResponseLengthController()

        assert controller.get_max_tokens("brief") == 100
        assert controller.get_max_tokens("normal") == 500
        assert controller.get_max_tokens("detailed") == 2000

    def test_truncate_response(self):
        """Test response truncation."""
        controller = ResponseLengthController()

        long_response = "This is a sentence. " * 100
        truncated = controller.truncate_response(long_response, "brief")

        assert len(truncated) < len(long_response)


# =============================================================================
# Bookmark Manager Tests
# =============================================================================


class TestBookmarkManager:
    """Tests for BookmarkManager."""

    @pytest.mark.asyncio
    async def test_add_bookmark(self):
        """Test adding a bookmark."""
        manager = BookmarkManager()

        bookmark = await manager.add(
            label="API Decision",
            content="We decided to use REST not GraphQL",
            tags=["architecture", "api"],
        )

        assert bookmark.label == "API Decision"
        assert "architecture" in bookmark.tags
        assert bookmark.id is not None

    @pytest.mark.asyncio
    async def test_find_bookmark(self):
        """Test finding bookmarks."""
        manager = BookmarkManager()

        await manager.add("API Decision", "REST not GraphQL", ["api"])
        await manager.add("Database Choice", "PostgreSQL selected", ["database"])

        results = await manager.find("API")

        assert len(results) == 1
        assert results[0].label == "API Decision"

    @pytest.mark.asyncio
    async def test_recall_bookmark(self):
        """Test recalling specific bookmark."""
        manager = BookmarkManager()

        await manager.add("Important Meeting", "Discussed roadmap", ["meeting"])

        recalled = await manager.recall("Important")

        assert recalled is not None
        assert recalled.label == "Important Meeting"

    @pytest.mark.asyncio
    async def test_list_all_bookmarks(self):
        """Test listing all bookmarks."""
        manager = BookmarkManager()

        await manager.add("Bookmark 1", "Content 1")
        await manager.add("Bookmark 2", "Content 2")

        all_bookmarks = manager.list_all()

        assert len(all_bookmarks) == 2

    @pytest.mark.asyncio
    async def test_delete_bookmark(self):
        """Test deleting a bookmark."""
        manager = BookmarkManager()

        bookmark = await manager.add("To Delete", "Will be deleted")

        assert manager.delete(bookmark.id) is True
        assert len(manager.list_all()) == 0


# =============================================================================
# Correction Learner Tests
# =============================================================================


class TestCorrectionLearner:
    """Tests for CorrectionLearner."""

    @pytest.mark.asyncio
    async def test_record_correction(self):
        """Test recording a correction."""
        learner = CorrectionLearner()

        correction = await learner.record_correction(
            original="The meeting is at 3pm",
            correction="Actually it's at 2pm",
            context="schedule discussion",
        )

        assert correction.original_response == "The meeting is at 3pm"
        assert correction.correction == "Actually it's at 2pm"
        assert correction.id is not None

    @pytest.mark.asyncio
    async def test_check_past_corrections(self):
        """Test checking for past corrections."""
        learner = CorrectionLearner()

        await learner.record_correction(
            original="The meeting is at 3pm",
            correction="It's at 2pm",
            context="meeting time",
        )

        relevant = await learner.check_past_corrections("meeting")

        assert len(relevant) == 1
        assert "3pm" in relevant[0].original_response

    def test_apply_corrections(self):
        """Test applying corrections to response."""
        learner = CorrectionLearner()

        # Add a correction manually
        learner.corrections.append(
            Correction(
                id="test",
                original_response="3pm",
                correction="2pm",
                context="time",
                created_at=datetime.now(UTC),
            )
        )

        response = "The meeting is at 3pm"
        corrected = learner.apply_corrections(response)

        assert "2pm" in corrected


# =============================================================================
# Safety Checker Tests
# =============================================================================


class TestSafetyChecker:
    """Tests for SafetyChecker."""

    def test_needs_confirmation_dangerous_action(self):
        """Test that dangerous actions need confirmation."""
        checker = SafetyChecker()

        dangerous = [
            "delete all users",
            "drop database production",
            "wipe all data",
            "destroy everything",
        ]

        for action in dangerous:
            assert checker.needs_confirmation(action), f"Expected True for '{action}'"

    def test_safe_actions_no_confirmation(self):
        """Test that safe actions don't need confirmation."""
        checker = SafetyChecker()

        safe = [
            "read user profile",
            "list all items",
            "create new document",
        ]

        for action in safe:
            assert not checker.needs_confirmation(
                action
            ), f"Expected False for '{action}'"

    def test_hallucination_detection_no_sources(self):
        """Test hallucination detection without sources."""
        checker = SafetyChecker()

        # Specific claims without sources are risky
        risky = "The meeting was at exactly 3:47pm on 2024-01-15. Attendance was 87%."
        risk = checker.detect_potential_hallucination(risky)

        assert risk > 0.3  # Should have elevated risk

    def test_hallucination_detection_with_sources(self):
        """Test hallucination detection with sources."""
        checker = SafetyChecker()

        response = "The value is 42."

        risk_without = checker.detect_potential_hallucination(response, sources=None)
        risk_with = checker.detect_potential_hallucination(response, sources=["doc.md"])

        assert risk_with < risk_without

    def test_rate_limit_check_ok(self):
        """Test rate limit check when OK."""
        checker = SafetyChecker()

        is_ok, message = checker.check_rate_limit(50, 100)

        assert is_ok is True
        assert "50/100" in message

    def test_rate_limit_check_warning(self):
        """Test rate limit check when approaching limit."""
        checker = SafetyChecker()

        is_ok, message = checker.check_rate_limit(85, 100)

        assert is_ok is True
        assert "Warning" in message

    def test_rate_limit_check_exceeded(self):
        """Test rate limit check when exceeded."""
        checker = SafetyChecker()

        is_ok, message = checker.check_rate_limit(105, 100)

        assert is_ok is False
        assert "exceeded" in message


# =============================================================================
# Conversation Summarizer Tests
# =============================================================================


class TestConversationSummarizer:
    """Tests for ConversationSummarizer."""

    def test_should_summarize_threshold(self):
        """Test summarization threshold check."""
        summarizer = ConversationSummarizer()

        short_history = [{"role": "user", "content": "Hi"}] * 5
        long_history = [{"role": "user", "content": "Hi"}] * 25

        assert summarizer.should_summarize(short_history) is False
        assert summarizer.should_summarize(long_history) is True

    @pytest.mark.asyncio
    async def test_simple_summarize(self):
        """Test simple summarization without LLM."""
        summarizer = ConversationSummarizer()

        messages = [
            {"role": "user", "content": "Hello, I need help with deployment"},
            {"role": "assistant", "content": "Sure, what do you need?"},
            {"role": "user", "content": "How do I deploy to production?"},
        ]

        summary = await summarizer.summarize(messages)

        assert len(summary) > 0
        assert "deployment" in summary.lower() or "Started" in summary

    @pytest.mark.asyncio
    async def test_compress_history(self):
        """Test history compression."""
        summarizer = ConversationSummarizer()

        messages = [{"role": "user", "content": f"Message {i}"} for i in range(15)]

        compressed = await summarizer.compress_history(messages, keep_recent=5)

        # Should have 1 summary + 5 recent
        assert len(compressed) == 6
        assert compressed[0]["role"] == "system"
        assert "summary" in compressed[0]["content"].lower()


# =============================================================================
# Clarification Generator Tests
# =============================================================================


class TestClarificationGenerator:
    """Tests for ClarificationGenerator."""

    @pytest.mark.asyncio
    async def test_needs_clarification_ambiguous(self):
        """Test detection of ambiguous messages."""
        generator = ClarificationGenerator()

        ambiguous = [
            "Update it",
            "Fix that thing",
            "Do something about this",
        ]

        for msg in ambiguous:
            needs = await generator.needs_clarification(msg)
            assert needs is True, f"Expected True for '{msg}'"

    @pytest.mark.asyncio
    async def test_needs_clarification_clear(self):
        """Test that clear messages don't need clarification."""
        generator = ClarificationGenerator()

        # Very explicit message with no ambiguous pronouns
        clear = "Update john@example.com email address to jane@example.com"
        needs = await generator.needs_clarification(clear)

        # This is clear enough - no pronouns like "it" or "that"
        assert needs is False

    @pytest.mark.asyncio
    async def test_generate_simple_questions(self):
        """Test simple question generation."""
        generator = ClarificationGenerator()

        questions = await generator.generate_questions("Update it")

        assert len(questions) > 0
        assert len(questions) <= 3


# =============================================================================
# Integration with Chatbot Tests
# =============================================================================


class TestChatbotIntelligence:
    """Tests for intelligence features integrated with Chatbot."""

    def test_chatbot_with_intelligence(self):
        """Test creating chatbot with intelligence enabled."""
        from agentic_brain.chat import Chatbot

        bot = Chatbot("test", intelligence=True)

        assert bot._intelligence_enabled is True
        assert bot._intent_detector is not None
        assert bot._mood_detector is not None

    def test_chatbot_detect_intent(self):
        """Test intent detection via chatbot."""
        from agentic_brain.chat import Chatbot

        bot = Chatbot("test", intelligence=True)

        intent, confidence = bot.detect_intent("Create a new user")

        assert intent == Intent.ACTION
        assert confidence > 0.1

    def test_chatbot_get_mood(self):
        """Test mood detection via chatbot."""
        from agentic_brain.chat import Chatbot

        bot = Chatbot("test", intelligence=True)

        mood, confidence = bot.get_mood("This is broken!!!")

        assert mood == Mood.FRUSTRATED

    def test_chatbot_switch_personality(self):
        """Test personality switching via chatbot."""
        from agentic_brain.chat import Chatbot

        bot = Chatbot("test", intelligence=True)

        profile = bot.switch_personality("friendly")

        assert profile is not None
        assert profile.name == "friendly"
        assert profile.emoji_usage is True

    def test_chatbot_safety_check(self):
        """Test safety check via chatbot."""
        from agentic_brain.chat import Chatbot

        bot = Chatbot("test", intelligence=True)

        needs = bot.needs_safety_confirmation("delete all production data")

        assert needs is True

    def test_chatbot_without_intelligence(self):
        """Test that chatbot works without intelligence."""
        from agentic_brain.chat import Chatbot

        bot = Chatbot("test", intelligence=False)

        assert bot._intelligence_enabled is False

        # These should return safe defaults
        intent, conf = bot.detect_intent("hello")
        assert intent is None

        mood, conf = bot.get_mood("hello")
        assert mood is None

        profile = bot.switch_personality("friendly")
        assert profile is None

    def test_chatbot_stats_includes_intelligence(self):
        """Test that stats includes intelligence status."""
        from agentic_brain.chat import Chatbot

        bot = Chatbot("test", intelligence=True)
        stats = bot.get_stats()

        assert "intelligence_enabled" in stats
        assert stats["intelligence_enabled"] is True
