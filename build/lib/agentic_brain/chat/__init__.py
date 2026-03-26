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
Agentic Brain Chat Module
=========================

Production-ready chatbot with:
- Session persistence (survives restarts)
- Neo4j memory integration
- Conversation threading
- Multi-user support with data isolation
- Simple, clean API
- Intelligence features (intent detection, mood, personality, safety)

Quick Start:
    from agentic_brain.chat import Chatbot

    bot = Chatbot("assistant")
    response = bot.chat("Hello!")
    print(response)

With Memory:
    from agentic_brain import Neo4jMemory
    from agentic_brain.chat import Chatbot

    memory = Neo4jMemory()
    bot = Chatbot("support", memory=memory)

    # Bot remembers across sessions
    bot.chat("My order number is 12345")
    # Later...
    bot.chat("What was my order number?")  # Knows it's 12345

Multi-User (Business):
    bot = Chatbot("support", memory=memory)

    # Each customer isolated
    bot.chat("I need help", user_id="customer_1")
    bot.chat("I need help", user_id="customer_2")  # Different context

Intelligence Features:
    from agentic_brain.chat import IntentDetector, MoodDetector, Intent, Mood

    intent_detector = IntentDetector()
    intent, confidence = intent_detector.detect_sync("Fix the bug")
    # (Intent.ACTION, 0.85)

    mood_detector = MoodDetector()
    mood, confidence = mood_detector.detect("This is broken AGAIN!!!")
    # (Mood.FRUSTRATED, 0.95)
"""

from .chatbot import Chatbot, ChatMessage, ChatSession
from .config import ChatConfig
from .intelligence import (
    # Bookmarks
    Bookmark,
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
from .session import Session, SessionManager

__all__ = [
    # Core chat
    "Chatbot",
    "ChatMessage",
    "ChatSession",
    "SessionManager",
    "Session",
    "ChatConfig",
    # Intelligence - Enums
    "Intent",
    "Mood",
    # Intelligence - Detectors
    "IntentDetector",
    "MoodDetector",
    # Intelligence - Summarization
    "ConversationSummarizer",
    # Intelligence - Clarification
    "ClarificationGenerator",
    # Intelligence - Scoring
    "ConfidenceScorer",
    # Intelligence - Personality
    "PersonalityProfile",
    "PersonalityManager",
    # Intelligence - Response control
    "ResponseLengthController",
    # Intelligence - Bookmarks
    "Bookmark",
    "BookmarkManager",
    # Intelligence - Learning
    "Correction",
    "CorrectionLearner",
    # Intelligence - Safety
    "SafetyChecker",
]
