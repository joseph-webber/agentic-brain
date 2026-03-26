# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Chatbot Intelligence Module
===========================

Smart features for chatbots:
- ConversationSummarizer: Auto-compress long conversations
- IntentDetector: Detect user intent (action/question/chat/complaint)
- ClarificationGenerator: Smart follow-up questions
- ConfidenceScorer: Know when guessing vs certain
- MoodDetector: Detect user mood for tone adjustment
- PersonalityManager: Switch between personality profiles
- ResponseLengthController: Brief/normal/detailed responses
- BookmarkManager: Mark important moments for recall
- CorrectionLearner: Learn from user corrections
- SafetyChecker: Hallucination detection, action confirmation

All features are optional - use what you need.

Example:
    from agentic_brain.chat.intelligence import (
        IntentDetector, MoodDetector, PersonalityManager
    )

    intent_detector = IntentDetector()
    intent, confidence = intent_detector.detect_sync("Fix the login bug")
    # (Intent.ACTION, 0.9)

    mood_detector = MoodDetector()
    mood, confidence = mood_detector.detect("This is broken AGAIN!!!")
    # (Mood.FRUSTRATED, 0.95)
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Intent Detection
# =============================================================================


class Intent(Enum):
    """User intent categories."""

    ACTION = "action"  # User wants something done
    QUESTION = "question"  # User wants information
    CHAT = "chat"  # Casual conversation
    COMPLAINT = "complaint"  # User is frustrated
    CLARIFICATION = "clarification"  # User is clarifying
    CONFIRMATION = "confirmation"  # User confirming/denying


class IntentDetector:
    """
    Detect user intent for smarter routing.

    Supports both LLM-based detection (async) and fast keyword-based
    detection (sync) for real-time applications.

    Example:
        detector = IntentDetector()

        # Fast sync detection (no LLM)
        intent, confidence = detector.detect_sync("Create a new user")
        # (Intent.ACTION, 0.85)

        # LLM-based detection (more accurate)
        intent, confidence = await detector.detect("Can you help me?")
        # (Intent.QUESTION, 0.92)
    """

    def __init__(self, llm_router: Optional[Any] = None):
        """
        Initialize intent detector.

        Args:
            llm_router: Optional LLM for advanced detection
        """
        self.llm_router = llm_router

        # Keyword-based fallback patterns
        self._action_keywords = [
            "do",
            "make",
            "create",
            "fix",
            "deploy",
            "run",
            "start",
            "stop",
            "build",
            "delete",
            "remove",
            "add",
            "update",
            "change",
            "set",
            "install",
            "configure",
            "enable",
            "disable",
            "restart",
            "reset",
        ]
        self._question_keywords = [
            "what",
            "how",
            "why",
            "when",
            "where",
            "who",
            "which",
            "can you",
            "could you",
            "is it",
            "are there",
            "does it",
            "will it",
            "should i",
            "do you know",
            "tell me",
        ]
        self._complaint_keywords = [
            "broken",
            "doesn't work",
            "not working",
            "failed",
            "error",
            "wrong",
            "bad",
            "terrible",
            "hate",
            "frustrated",
            "annoyed",
            "again",
            "still",
            "always",
            "never",
        ]
        self._confirmation_keywords = [
            "yes",
            "no",
            "correct",
            "right",
            "wrong",
            "exactly",
            "nope",
            "yep",
            "yeah",
            "nah",
            "sure",
            "ok",
            "okay",
            "confirm",
            "deny",
            "agree",
            "disagree",
            "true",
            "false",
        ]
        self._clarification_keywords = [
            "i mean",
            "what i meant",
            "to clarify",
            "specifically",
            "actually",
            "no, i",
            "not that",
            "the one",
            "i'm talking about",
            "let me explain",
            "to be clear",
        ]
        self._chat_keywords = [
            "hello",
            "hi",
            "hey",
            "thanks",
            "thank you",
            "bye",
            "goodbye",
            "how are you",
            "good morning",
            "good night",
            "cheers",
            "mate",
        ]

    async def detect(self, message: str) -> tuple[Intent, float]:
        """
        Detect intent using LLM if available, otherwise keyword-based.

        Args:
            message: User message

        Returns:
            Tuple of (Intent, confidence score 0.0-1.0)
        """
        if self.llm_router:
            try:
                return await self._detect_with_llm(message)
            except Exception as e:
                logger.warning(
                    f"LLM intent detection failed: {e}, falling back to keywords"
                )

        return self.detect_sync(message)

    async def _detect_with_llm(self, message: str) -> tuple[Intent, float]:
        """Detect intent using LLM."""
        prompt = f"""Classify this message into ONE category:
- ACTION: User wants something done (create, fix, deploy, run)
- QUESTION: User wants information (what, how, why, tell me)
- CHAT: Casual conversation (hello, thanks, how are you)
- COMPLAINT: User is frustrated (broken, doesn't work, hate)
- CLARIFICATION: User is clarifying something (I mean, specifically)
- CONFIRMATION: User confirming/denying (yes, no, correct)

Message: "{message}"

Reply with ONLY the category name (e.g., "ACTION")."""

        if hasattr(self.llm_router, "chat"):
            response = await self.llm_router.chat([{"role": "user", "content": prompt}])
        elif callable(self.llm_router):
            response = self.llm_router(prompt)
        else:
            return self.detect_sync(message)

        # Parse response
        response_upper = response.strip().upper()
        for intent in Intent:
            if intent.value.upper() in response_upper:
                return (intent, 0.9)

        return self.detect_sync(message)

    def detect_sync(self, message: str) -> tuple[Intent, float]:
        """
        Fast keyword-based intent detection (no LLM required).

        Args:
            message: User message

        Returns:
            Tuple of (Intent, confidence score 0.0-1.0)
        """
        lower = message.lower().strip()

        # Count keyword matches for each intent
        scores: dict[Intent, float] = dict.fromkeys(Intent, 0.0)

        # Check each category
        for keyword in self._action_keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lower):
                scores[Intent.ACTION] += 0.15

        for keyword in self._question_keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lower):
                scores[Intent.QUESTION] += 0.15

        for keyword in self._complaint_keywords:
            if keyword in lower:
                scores[Intent.COMPLAINT] += 0.2

        for keyword in self._confirmation_keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lower):
                scores[Intent.CONFIRMATION] += 0.2

        for keyword in self._clarification_keywords:
            if keyword in lower:
                scores[Intent.CLARIFICATION] += 0.25

        for keyword in self._chat_keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lower):
                scores[Intent.CHAT] += 0.2

        # Check for question marks (boost QUESTION)
        if "?" in message:
            scores[Intent.QUESTION] += 0.3

        # Check for exclamation marks with negative words (boost COMPLAINT)
        if "!" in message and any(kw in lower for kw in self._complaint_keywords):
            scores[Intent.COMPLAINT] += 0.2

        # Find highest scoring intent
        best_intent = max(scores, key=lambda k: scores[k])
        best_score = min(scores[best_intent], 1.0)

        # If no strong signal, default to CHAT
        if best_score < 0.1:
            return (Intent.CHAT, 0.5)

        return (best_intent, best_score)


# =============================================================================
# Mood Detection
# =============================================================================


class Mood(Enum):
    """User mood categories."""

    HAPPY = "happy"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    CONFUSED = "confused"
    URGENT = "urgent"


class MoodDetector:
    """
    Detect user mood to adjust response tone.

    Example:
        detector = MoodDetector()
        mood, confidence = detector.detect("This is broken AGAIN!!!")
        # (Mood.FRUSTRATED, 0.95)

        mood, confidence = detector.detect("Thanks so much! Perfect!")
        # (Mood.HAPPY, 0.85)
    """

    def __init__(self):
        """Initialize mood detector."""
        self._frustration_signals = [
            "!!!",
            "???",
            "come on",
            "ugh",
            "again",
            "still not",
            "broken",
            "doesn't work",
            "not working",
            "failed",
            "hate",
            "terrible",
            "seriously",
            "ridiculous",
            "unbelievable",
            "wtf",
            "damn",
        ]
        self._urgency_signals = [
            "asap",
            "urgent",
            "now",
            "quickly",
            "hurry",
            "emergency",
            "critical",
            "immediately",
            "right now",
            "deadline",
            "blocking",
            "production down",
            "fire",
            "crisis",
        ]
        self._happy_signals = [
            "thanks",
            "thank you",
            "awesome",
            "great",
            "perfect",
            "love it",
            "amazing",
            "excellent",
            "wonderful",
            "brilliant",
            "fantastic",
            "cheers",
            ":)",
            "😊",
            "👍",
            "❤️",
            "nice",
            "cool",
        ]
        self._confused_signals = [
            "confused",
            "don't understand",
            "what do you mean",
            "unclear",
            "huh",
            "???",
            "lost",
            "makes no sense",
            "not sure",
            "help me understand",
        ]

    def detect(
        self, message: str, history: Optional[list[dict]] = None
    ) -> tuple[Mood, float]:
        """
        Detect mood from message and optionally recent history.

        Args:
            message: Current message
            history: Optional recent message history

        Returns:
            Tuple of (Mood, confidence score 0.0-1.0)
        """
        lower = message.lower()
        scores: dict[Mood, float] = dict.fromkeys(Mood, 0.0)

        # Check frustration signals
        for signal in self._frustration_signals:
            if signal in lower or signal in message:
                scores[Mood.FRUSTRATED] += 0.2

        # Check urgency signals
        for signal in self._urgency_signals:
            if signal in lower:
                scores[Mood.URGENT] += 0.25

        # Check happy signals
        for signal in self._happy_signals:
            if signal in lower or signal in message:
                scores[Mood.HAPPY] += 0.2

        # Check confusion signals
        for signal in self._confused_signals:
            if signal in lower:
                scores[Mood.CONFUSED] += 0.2

        # Punctuation analysis
        exclaim_count = message.count("!")
        question_count = message.count("?")

        if exclaim_count >= 3:
            scores[Mood.FRUSTRATED] += 0.3
        elif exclaim_count >= 1 and any(s in lower for s in self._happy_signals):
            scores[Mood.HAPPY] += 0.1

        if question_count >= 3:
            scores[Mood.CONFUSED] += 0.2

        # CAPS analysis (frustration indicator)
        words = message.split()
        caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
        if caps_words >= 2:
            scores[Mood.FRUSTRATED] += 0.2

        # History analysis (escalating frustration)
        if history:
            recent_frustration = sum(
                1
                for msg in history[-5:]
                if any(
                    s in msg.get("content", "").lower()
                    for s in self._frustration_signals
                )
            )
            if recent_frustration >= 2:
                scores[Mood.FRUSTRATED] += 0.3

        # Find best mood
        best_mood = max(scores, key=lambda k: scores[k])
        best_score = min(scores[best_mood], 1.0)

        # Default to neutral if no strong signals
        if best_score < 0.1:
            return (Mood.NEUTRAL, 0.7)

        return (best_mood, best_score)


# =============================================================================
# Conversation Summarizer
# =============================================================================


class ConversationSummarizer:
    """
    Auto-summarize old messages to preserve context without losing key facts.

    Wraps UnifiedSummarizer for brain-core compatibility while maintaining
    the simple API for this module.

    Example:
        summarizer = ConversationSummarizer(llm_router=my_llm)

        if summarizer.should_summarize(messages):
            compressed = await summarizer.compress_history(messages)

        # For advanced features, access the unified summarizer
        topics = await summarizer.unified.extract_topics(messages)
    """

    def __init__(
        self,
        llm_router: Optional[Any] = None,
        max_tokens: int = 500,
        memory: Optional[Any] = None,
    ):
        """
        Initialize summarizer.

        Args:
            llm_router: LLM for generating summaries
            max_tokens: Max tokens for summary
            memory: Neo4j memory for storage (optional)
        """
        # Import here to avoid circular imports
        from ..memory.summarization import SummaryType, UnifiedSummarizer

        self._SummaryType = SummaryType
        self._unified = UnifiedSummarizer(
            llm_router=llm_router,
            memory=memory,
            max_summary_tokens=max_tokens,
        )
        self.llm_router = llm_router
        self.max_tokens = max_tokens

    @property
    def unified(self):
        """
        Access the underlying UnifiedSummarizer for advanced features.

        Example:
            >>> topics = await summarizer.unified.extract_topics(messages)
            >>> facts = await summarizer.unified.extract_key_facts(messages)
        """
        return self._unified

    async def summarize(self, messages: list[dict]) -> str:
        """
        Summarize a list of messages into a concise summary.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Concise summary string
        """
        if not messages:
            return ""

        summary = await self._unified._generate_summary(
            messages,
            self._SummaryType.REALTIME,
        )
        return summary.content

    async def compress_history(
        self,
        messages: list[dict],
        keep_recent: int = 5,
    ) -> list[dict]:
        """
        Compress old messages while keeping recent ones intact.

        Args:
            messages: Full message history
            keep_recent: Number of recent messages to keep unchanged

        Returns:
            Compressed message list with summary + recent messages
        """
        compressed, _ = await self._unified.compress_conversation(messages, keep_recent)
        return compressed

    def should_summarize(self, messages: list[dict], threshold: int = 20) -> bool:
        """
        Check if conversation needs summarization.

        Args:
            messages: Message list
            threshold: Trigger summarization if more than this many messages

        Returns:
            True if summarization recommended
        """
        return self._unified.should_compress_sync(messages, threshold)


# =============================================================================
# Clarification Generator
# =============================================================================


class ClarificationGenerator:
    """
    Generate smart follow-up questions when user is ambiguous.

    Example:
        generator = ClarificationGenerator(llm_router=my_llm)

        if await generator.needs_clarification("Update the thing"):
            questions = await generator.generate_questions("Update the thing")
            # ["Which item would you like to update?", "What changes should I make?"]
    """

    def __init__(self, llm_router: Optional[Any] = None):
        """Initialize generator."""
        self.llm_router = llm_router

        # Ambiguity indicators
        self._ambiguous_words = [
            "it",
            "that",
            "this",
            "thing",
            "stuff",
            "something",
            "the one",
            "the other",
            "some",
            "maybe",
            "probably",
        ]

    async def needs_clarification(
        self, message: str, context: Optional[list[dict]] = None
    ) -> bool:
        """
        Check if message is ambiguous and needs clarification.

        Args:
            message: User message
            context: Conversation context

        Returns:
            True if clarification needed
        """
        lower = message.lower()

        # Check for ambiguous references
        has_ambiguous = any(word in lower for word in self._ambiguous_words)

        # Very short messages are often ambiguous
        is_short = len(message.split()) < 4

        # Missing key info (what, where, how)
        has_action = any(
            word in lower for word in ["do", "make", "create", "fix", "update"]
        )
        missing_target = has_action and not any(
            word in lower for word in ["the", "my", "our", "a", "an"]
        )

        return has_ambiguous or (is_short and has_action) or missing_target

    async def generate_questions(
        self, message: str, context: Optional[list[dict]] = None, max_questions: int = 3
    ) -> list[str]:
        """
        Generate clarifying questions.

        Args:
            message: Ambiguous message
            context: Conversation context
            max_questions: Maximum questions to generate

        Returns:
            List of clarifying questions
        """
        if self.llm_router:
            return await self._generate_with_llm(message, context, max_questions)

        return self._generate_simple(message)

    async def _generate_with_llm(
        self, message: str, context: Optional[list[dict]], max_questions: int
    ) -> list[str]:
        """Generate questions using LLM."""
        context_str = ""
        if context:
            context_str = "\n".join(
                [
                    f"{m.get('role', 'user')}: {m.get('content', '')}"
                    for m in context[-5:]
                ]
            )

        prompt = f"""The user said something ambiguous. Generate {max_questions} clarifying questions.

Context:
{context_str}

User message: "{message}"

Generate {max_questions} short, specific questions to understand what the user needs.
Format: One question per line, no numbering."""

        try:
            if hasattr(self.llm_router, "chat"):
                response = await self.llm_router.chat(
                    [{"role": "user", "content": prompt}]
                )
            elif callable(self.llm_router):
                response = self.llm_router(prompt)
                if hasattr(response, "__await__"):
                    response = await response
            else:
                return self._generate_simple(message)

            # Parse response
            questions = [q.strip() for q in response.strip().split("\n") if q.strip()]
            return questions[:max_questions]

        except Exception as e:
            logger.warning(f"LLM question generation failed: {e}")
            return self._generate_simple(message)

    def _generate_simple(self, message: str) -> list[str]:
        """Generate simple rule-based questions."""
        questions = []
        lower = message.lower()

        if "it" in lower or "that" in lower or "this" in lower:
            questions.append("Could you specify what you're referring to?")

        if any(word in lower for word in ["update", "change", "modify"]):
            questions.append("What specific changes would you like to make?")

        if any(word in lower for word in ["fix", "broken", "error"]):
            questions.append("What error or issue are you experiencing?")

        if not questions:
            questions.append("Could you provide more details about what you need?")

        return questions[:3]


# =============================================================================
# Confidence Scorer
# =============================================================================


class ConfidenceScorer:
    """
    Score response confidence - know when guessing vs certain.

    Example:
        scorer = ConfidenceScorer()

        confidence = scorer.score("I think the answer might be 42")
        # 0.4 (low - hedging language)

        confidence = scorer.score("The answer is 42, as documented in X")
        # 0.9 (high - has source)
    """

    def __init__(self):
        """Initialize scorer."""
        self.uncertainty_phrases = [
            "i think",
            "probably",
            "might be",
            "i'm not sure",
            "possibly",
            "it seems",
            "i believe",
            "maybe",
            "i guess",
            "perhaps",
            "could be",
            "not certain",
            "as far as i know",
            "i'm not 100%",
            "roughly",
            "approximately",
            "around",
            "more or less",
        ]
        self.certainty_phrases = [
            "definitely",
            "certainly",
            "absolutely",
            "always",
            "never",
            "exactly",
            "precisely",
            "confirmed",
            "verified",
            "documented",
            "according to",
        ]

    def score(self, response: str, has_sources: bool = False) -> float:
        """
        Score confidence of a response.

        Args:
            response: The response text
            has_sources: Whether response cites sources

        Returns:
            Confidence score 0.0 (guessing) to 1.0 (certain)
        """
        lower = response.lower()

        # Base score
        score = 0.6

        # Penalize uncertainty phrases
        uncertainty_count = sum(
            1 for phrase in self.uncertainty_phrases if phrase in lower
        )
        score -= uncertainty_count * 0.1

        # Reward certainty phrases
        certainty_count = sum(1 for phrase in self.certainty_phrases if phrase in lower)
        score += certainty_count * 0.08

        # Reward sources/citations
        if has_sources:
            score += 0.2

        # Check for specific numbers without context (potential hallucination)
        numbers = re.findall(r"\b\d{4,}\b", response)
        if numbers and not has_sources:
            score -= 0.1

        # Clamp to valid range
        return max(0.0, min(1.0, score))

    def should_ask_for_help(self, score: float, threshold: float = 0.5) -> bool:
        """
        Check if confidence is too low and should escalate.

        Args:
            score: Confidence score
            threshold: Below this, recommend asking for help

        Returns:
            True if should ask for help
        """
        return score < threshold


# =============================================================================
# Personality Manager
# =============================================================================


@dataclass
class PersonalityProfile:
    """
    Switchable personality profile.

    Attributes:
        name: Profile identifier
        tone: professional, casual, friendly, technical
        verbosity: brief, normal, detailed
        emoji_usage: Whether to use emojis
        formality: 0.0 casual to 1.0 formal
        system_prompt_additions: Extra system prompt text
    """

    name: str
    tone: str  # professional, casual, friendly, technical
    verbosity: str  # brief, normal, detailed
    emoji_usage: bool
    formality: float  # 0.0 casual to 1.0 formal
    system_prompt_additions: str = ""


class PersonalityManager:
    """
    Manage and switch between personality profiles.

    Example:
        manager = PersonalityManager()

        # Get current profile
        profile = manager.get_profile()

        # Switch to friendly mode
        manager.switch("friendly")
        profile = manager.get_profile()
        # profile.emoji_usage = True, profile.formality = 0.3
    """

    def __init__(self):
        """Initialize with default profiles."""
        self.profiles: dict[str, PersonalityProfile] = {
            "professional": PersonalityProfile(
                name="professional",
                tone="professional",
                verbosity="normal",
                emoji_usage=False,
                formality=0.8,
                system_prompt_additions="Maintain a professional tone. Be clear and direct.",
            ),
            "friendly": PersonalityProfile(
                name="friendly",
                tone="friendly",
                verbosity="normal",
                emoji_usage=True,
                formality=0.3,
                system_prompt_additions="Be warm and approachable. Use casual language and occasional emojis.",
            ),
            "technical": PersonalityProfile(
                name="technical",
                tone="technical",
                verbosity="detailed",
                emoji_usage=False,
                formality=0.7,
                system_prompt_additions="Be precise and technical. Include relevant details and explanations.",
            ),
            "brief": PersonalityProfile(
                name="brief",
                tone="professional",
                verbosity="brief",
                emoji_usage=False,
                formality=0.5,
                system_prompt_additions="Be extremely concise. Use bullet points when appropriate.",
            ),
        }
        self.current = "professional"

    def get_profile(self, name: Optional[str] = None) -> PersonalityProfile:
        """
        Get a personality profile.

        Args:
            name: Profile name, or None for current

        Returns:
            PersonalityProfile
        """
        profile_name = name or self.current
        return self.profiles.get(profile_name, self.profiles["professional"])

    def switch(self, name: str) -> PersonalityProfile:
        """
        Switch to a different personality.

        Args:
            name: Profile name

        Returns:
            The new active profile
        """
        if name in self.profiles:
            self.current = name
            logger.info(f"Personality switched to: {name}")
        else:
            logger.warning(f"Unknown personality: {name}, keeping {self.current}")

        return self.get_profile()

    def add_profile(self, profile: PersonalityProfile) -> None:
        """Add a custom personality profile."""
        self.profiles[profile.name] = profile

    def list_profiles(self) -> list[str]:
        """List available profile names."""
        return list(self.profiles.keys())


# =============================================================================
# Response Length Controller
# =============================================================================


class ResponseLengthController:
    """
    Control response length based on user preferences.

    Example:
        controller = ResponseLengthController()

        pref = controller.detect_preference("Give me a quick summary")
        # "brief"

        max_tokens = controller.get_max_tokens("brief")
        # 100
    """

    def __init__(self):
        """Initialize controller."""
        self._brief_keywords = [
            "brief",
            "short",
            "quick",
            "tldr",
            "summary",
            "briefly",
            "in short",
            "summarize",
            "concise",
            "just tell me",
        ]
        self._detailed_keywords = [
            "explain",
            "detail",
            "detailed",
            "elaborate",
            "more",
            "tell me about",
            "in depth",
            "thoroughly",
            "everything",
            "all the details",
            "comprehensive",
        ]

        self._token_limits = {"brief": 100, "normal": 500, "detailed": 2000}

    def detect_preference(self, message: str) -> str:
        """
        Detect length preference from message.

        Args:
            message: User message

        Returns:
            "brief", "normal", or "detailed"
        """
        lower = message.lower()

        if any(kw in lower for kw in self._brief_keywords):
            return "brief"

        if any(kw in lower for kw in self._detailed_keywords):
            return "detailed"

        return "normal"

    def get_max_tokens(self, preference: str) -> int:
        """
        Get token limit for preference.

        Args:
            preference: "brief", "normal", or "detailed"

        Returns:
            Maximum tokens
        """
        return self._token_limits.get(preference, 500)

    def truncate_response(self, response: str, preference: str) -> str:
        """
        Truncate response to fit preference.

        Args:
            response: Full response
            preference: Length preference

        Returns:
            Possibly truncated response
        """
        max_chars = self.get_max_tokens(preference) * 4  # ~4 chars per token

        if len(response) <= max_chars:
            return response

        # Find last sentence boundary
        truncated = response[:max_chars]
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")

        cut_point = max(last_period, last_newline)
        if cut_point > max_chars // 2:
            return truncated[: cut_point + 1] + "\n\n[Response truncated for brevity]"

        return truncated + "..."


# =============================================================================
# Bookmark Manager
# =============================================================================


@dataclass
class Bookmark:
    """
    A marked moment in conversation.

    Attributes:
        id: Unique identifier
        label: User-friendly label
        message_index: Position in conversation
        content: The marked content
        created_at: When created
        tags: Optional categorization tags
    """

    id: str
    label: str
    message_index: int
    content: str
    created_at: datetime
    tags: list[str] = field(default_factory=list)


class BookmarkManager:
    """
    Mark important moments in conversation for later recall.

    Example:
        manager = BookmarkManager()

        bookmark = await manager.add(
            label="API decision",
            content="We decided to use REST not GraphQL"
        )

        results = await manager.find("API")
        recalled = await manager.recall("API decision")
    """

    def __init__(self, memory: Optional[Any] = None):
        """
        Initialize manager.

        Args:
            memory: Optional Neo4j memory for persistence
        """
        self.memory = memory
        self.bookmarks: dict[str, Bookmark] = {}
        self._message_counter = 0

    async def add(
        self, label: str, content: str, tags: Optional[list[str]] = None
    ) -> Bookmark:
        """
        Add a bookmark.

        Args:
            label: Human-readable label
            content: Content to bookmark
            tags: Optional tags for categorization

        Returns:
            Created bookmark
        """
        bookmark_id = str(uuid.uuid4())[:8]
        bookmark = Bookmark(
            id=bookmark_id,
            label=label,
            message_index=self._message_counter,
            content=content,
            created_at=datetime.now(timezone.utc),
            tags=tags or [],
        )

        self.bookmarks[bookmark_id] = bookmark
        self._message_counter += 1

        # Persist to memory if available
        if self.memory:
            try:
                self.memory.store(
                    content=f"Bookmark [{label}]: {content}",
                    metadata={
                        "type": "bookmark",
                        "bookmark_id": bookmark_id,
                        "tags": tags or [],
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to persist bookmark: {e}")

        logger.info(f"Bookmark added: {label} ({bookmark_id})")
        return bookmark

    async def find(self, query: str) -> list[Bookmark]:
        """
        Find bookmarks by query.

        Args:
            query: Search query (matches label, content, tags)

        Returns:
            List of matching bookmarks
        """
        query_lower = query.lower()
        results = []

        for bookmark in self.bookmarks.values():
            if (
                query_lower in bookmark.label.lower()
                or query_lower in bookmark.content.lower()
                or any(query_lower in tag.lower() for tag in bookmark.tags)
            ):
                results.append(bookmark)

        return results

    async def recall(self, label: str) -> Optional[Bookmark]:
        """
        Recall a specific bookmark by label.

        Args:
            label: Exact or partial label

        Returns:
            Bookmark if found
        """
        label_lower = label.lower()

        for bookmark in self.bookmarks.values():
            if label_lower in bookmark.label.lower():
                return bookmark

        return None

    def list_all(self) -> list[Bookmark]:
        """List all bookmarks."""
        return list(self.bookmarks.values())

    def delete(self, bookmark_id: str) -> bool:
        """Delete a bookmark by ID."""
        if bookmark_id in self.bookmarks:
            del self.bookmarks[bookmark_id]
            return True
        return False


# =============================================================================
# Correction Learner
# =============================================================================


@dataclass
class Correction:
    """
    A user correction to learn from.

    Attributes:
        id: Unique identifier
        original_response: What we said wrong
        correction: What user said is right
        context: Surrounding context
        created_at: When recorded
    """

    id: str
    original_response: str
    correction: str
    context: str
    created_at: datetime


class CorrectionLearner:
    """
    Learn from user corrections to avoid repeating mistakes.

    Example:
        learner = CorrectionLearner()

        await learner.record_correction(
            original="The meeting is at 3pm",
            correction="Actually it's at 2pm",
            context="schedule discussion"
        )

        # Later, when generating response
        past = await learner.check_past_corrections("meeting time")
    """

    def __init__(self, memory: Optional[Any] = None):
        """
        Initialize learner.

        Args:
            memory: Optional Neo4j memory for persistence
        """
        self.memory = memory
        self.corrections: list[Correction] = []

    async def record_correction(
        self, original: str, correction: str, context: str
    ) -> Correction:
        """
        Record a correction.

        Args:
            original: Original (wrong) response
            correction: User's correction
            context: Conversation context

        Returns:
            Recorded correction
        """
        correction_obj = Correction(
            id=str(uuid.uuid4())[:8],
            original_response=original,
            correction=correction,
            context=context,
            created_at=datetime.now(timezone.utc),
        )

        self.corrections.append(correction_obj)

        # Persist to memory
        if self.memory:
            try:
                self.memory.store(
                    content=f"CORRECTION: Said '{original}' but should be '{correction}'",
                    metadata={"type": "correction", "context": context},
                )
            except Exception as e:
                logger.warning(f"Failed to persist correction: {e}")

        logger.info(f"Correction recorded: {original[:50]} -> {correction[:50]}")
        return correction_obj

    async def check_past_corrections(self, query: str) -> list[Correction]:
        """
        Check if there are relevant past corrections.

        Args:
            query: Current topic/query

        Returns:
            List of relevant past corrections
        """
        query_lower = query.lower()
        relevant = []

        for correction in self.corrections:
            if (
                query_lower in correction.original_response.lower()
                or query_lower in correction.correction.lower()
                or query_lower in correction.context.lower()
            ):
                relevant.append(correction)

        return relevant

    def apply_corrections(self, response: str) -> str:
        """
        Apply known corrections to a response.

        Args:
            response: Response to check

        Returns:
            Corrected response
        """
        corrected = response

        for correction in self.corrections:
            # Simple substring replacement
            if correction.original_response.lower() in corrected.lower():
                # Case-insensitive replacement
                pattern = re.compile(
                    re.escape(correction.original_response), re.IGNORECASE
                )
                corrected = pattern.sub(correction.correction, corrected)

        return corrected


# =============================================================================
# Safety Checker
# =============================================================================


class SafetyChecker:
    """
    Safety features: hallucination detection, action confirmation, rate limiting.

    Example:
        checker = SafetyChecker()

        needs_confirm = checker.needs_confirmation("delete all users")
        # True

        hallucination_risk = checker.detect_potential_hallucination(
            "The meeting was at exactly 3:47pm on Tuesday"
        )
        # 0.7 (high - very specific without source)
    """

    def __init__(self):
        """Initialize checker."""
        self._dangerous_actions = [
            "delete",
            "remove",
            "drop",
            "truncate",
            "destroy",
            "wipe",
            "purge",
            "erase",
            "kill",
            "terminate",
            "shutdown",
            "format",
        ]
        self._dangerous_targets = [
            "all",
            "everything",
            "database",
            "production",
            "server",
            "users",
            "data",
            "system",
            "account",
        ]
        self._rate_limit_warning_threshold = 0.8  # 80% of limit

    def needs_confirmation(self, action: str) -> bool:
        """
        Check if action needs user confirmation.

        Args:
            action: Action description

        Returns:
            True if confirmation required
        """
        lower = action.lower()

        # Check for dangerous action words
        has_dangerous_action = any(da in lower for da in self._dangerous_actions)

        # Check for dangerous targets
        has_dangerous_target = any(dt in lower for dt in self._dangerous_targets)

        # Require confirmation if dangerous action + dangerous target
        return has_dangerous_action and has_dangerous_target

    def detect_potential_hallucination(
        self, response: str, sources: Optional[list] = None
    ) -> float:
        """
        Score likelihood of hallucination (0.0 to 1.0).

        High risk indicators:
        - Very specific claims (exact numbers, dates, times)
        - No sources cited
        - Proper nouns not in context

        Args:
            response: Response to check
            sources: Optional sources/citations

        Returns:
            Hallucination risk score 0.0 (safe) to 1.0 (risky)
        """
        risk = 0.0

        # No sources = higher risk
        if not sources:
            risk += 0.3

        # Specific numbers without context = risky
        specific_numbers = re.findall(r"\b\d{4,}\b", response)
        if specific_numbers:
            risk += 0.15 * min(len(specific_numbers), 3)

        # Specific times/dates = risky without source
        time_patterns = re.findall(r"\b\d{1,2}:\d{2}\b", response)
        date_patterns = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", response)
        if (time_patterns or date_patterns) and not sources:
            risk += 0.2

        # Percentage claims = risky without source
        percentages = re.findall(r"\b\d+\.?\d*%\b", response)
        if percentages and not sources:
            risk += 0.15

        # Absolute statements = slightly risky
        absolutes = ["always", "never", "everyone", "no one", "all", "none"]
        if any(ab in response.lower() for ab in absolutes):
            risk += 0.1

        return min(risk, 1.0)

    def check_rate_limit(self, current: int, limit: int) -> tuple[bool, str]:
        """
        Check rate limit status, return warning if approaching.

        Args:
            current: Current usage count
            limit: Maximum allowed

        Returns:
            Tuple of (is_ok, message)
        """
        if limit <= 0:
            return (True, "No rate limit configured")

        ratio = current / limit

        if ratio >= 1.0:
            return (False, f"Rate limit exceeded ({current}/{limit})")
        elif ratio >= self._rate_limit_warning_threshold:
            remaining = limit - current
            return (
                True,
                f"Warning: {remaining} requests remaining ({current}/{limit})",
            )
        else:
            return (True, f"OK ({current}/{limit})")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "Intent",
    "Mood",
    # Detectors
    "IntentDetector",
    "MoodDetector",
    # Summarization
    "ConversationSummarizer",
    # Clarification
    "ClarificationGenerator",
    # Scoring
    "ConfidenceScorer",
    # Personality
    "PersonalityProfile",
    "PersonalityManager",
    # Response control
    "ResponseLengthController",
    # Bookmarks
    "Bookmark",
    "BookmarkManager",
    # Learning
    "Correction",
    "CorrectionLearner",
    # Safety
    "SafetyChecker",
]
