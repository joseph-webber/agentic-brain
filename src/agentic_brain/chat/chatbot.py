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

from __future__ import annotations

# Copyright 2024-2026 Agentic Brain Contributors
"""
Chatbot - The Star of the Show
==============================

A production-ready chatbot that:
- Remembers conversations (persists across restarts)
- Integrates with Neo4j memory for long-term knowledge
- Supports multi-user/customer isolation
- Works with any LLM (Ollama, OpenAI, Anthropic)
- Has hooks for lifecycle events
- Supports both sync and async operation

This is what makes agentic-brain worth using.

Quick Start:
    bot = Chatbot("assistant")
    response = bot.chat("Hello!")  # sync
    response = await bot.chat_async("Hello!")  # async
    print(response)

With Memory:
    memory = Neo4jMemory()
    bot = Chatbot("support", memory=memory)
    response = bot.chat("Remember my name is Joseph")
    # ...later, even after restart...
    response = bot.chat("What's my name?")  # "Your name is Joseph"
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable


from ..model_aliases import MODEL_ALIASES
from ..router import get_router
from .config import ChatConfig
from .session import Session, SessionManager

# Import intelligence features (optional, loaded on demand)
try:
    from .intelligence import (
        ConfidenceScorer,
        ConversationSummarizer,
        Intent,
        IntentDetector,
        Mood,
        MoodDetector,
        PersonalityManager,
        SafetyChecker,
    )

    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """
    A single chat message.

    Attributes:
        role: 'user', 'assistant', or 'system'
        content: The message text
        timestamp: When sent (ISO format)
        metadata: Additional data (tokens, model, etc.)
    """

    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMessage:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChatSession:
    """
    Active chat session with history.

    Lightweight wrapper for quick access to session data.
    """

    session_id: str
    user_id: str | None
    history: list[ChatMessage] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.history)

    @property
    def last_message(self) -> ChatMessage | None:
        return self.history[-1] if self.history else None


class Chatbot:
    """
    Production-ready chatbot with memory and persistence.

    Features:
    - Session persistence (survives restarts)
    - Neo4j memory integration (long-term knowledge)
    - Multi-user support with data isolation
    - Hooks for lifecycle events
    - Works with any LLM

    Basic Usage:
        bot = Chatbot("assistant")
        response = bot.chat("Hello!")

    With Memory:
        from agentic_brain import Neo4jMemory
        memory = Neo4jMemory()
        bot = Chatbot("support", memory=memory)

    Business Mode (Customer Isolation):
        bot = Chatbot("support", config=ChatConfig.business())
        bot.chat("Help me", user_id="customer_123")
        bot.chat("Help me", user_id="customer_456")  # Isolated

    With Hooks:
        def on_message(message):
            print(f"Got: {message}")

        bot = Chatbot("assistant", on_message=on_message)
    """

    def __init__(
        self,
        name: str,
        memory: Any | None = None,  # Neo4jMemory
        config: ChatConfig | None = None,
        llm: Any | None = None,  # LLMRouter or callable
        system_prompt: str | None = None,
        # Intelligence features (all optional)
        intelligence: bool = False,  # Enable intelligence features
        # Lifecycle hooks
        on_message: Callable[[ChatMessage | None, None]] = None,
        on_response: Callable[[ChatMessage | None, None]] = None,
        on_error: Callable[[Exception | None, None]] = None,
    ) -> None:
        """
        Initialize chatbot.

        Args:
            name: Bot name/identifier
            memory: Neo4jMemory instance for long-term storage
            config: ChatConfig or uses defaults
            llm: LLM provider (LLMRouter, callable, or None for default)
            system_prompt: Override system prompt
            intelligence: Enable intelligence features (intent, mood, safety)
            on_message: Hook called on user message
            on_response: Hook called on bot response
            on_error: Hook called on errors
        """
        self.name = name
        self.config = config or ChatConfig()
        self.memory = memory
        self.llm = llm

        # System prompt
        self.system_prompt = (
            system_prompt or self.config.system_prompt or self._default_system_prompt()
        )

        # Session management
        self.session_manager = (
            SessionManager(
                session_dir=self.config.session_dir,
                timeout_seconds=self.config.session_timeout,
            )
            if self.config.persist_sessions
            else None
        )

        # In-memory sessions (for non-persistent mode)
        self._sessions: dict[str, Session] = {}

        # Model switching state
        self._current_model: str = "L2"  # Default to local model L2
        self._auto_fallback_enabled: bool = True  # Auto-fallback on failure

        # Intelligence features (optional)
        self._intelligence_enabled = intelligence and INTELLIGENCE_AVAILABLE
        self._intent_detector: Any | None = None
        self._mood_detector: Any | None = None
        self._safety_checker: Any | None = None
        self._confidence_scorer: Any | None = None
        self._summarizer: Any | None = None
        self._personality_manager: Any | None = None

        if self._intelligence_enabled:
            self._init_intelligence()

        # Hooks
        self._on_message = on_message
        self._on_response = on_response
        self._on_error = on_error

        # Stats
        self.stats = {
            "messages_received": 0,
            "responses_sent": 0,
            "errors": 0,
            "sessions_created": 0,
        }

        logger.info(f"Chatbot '{name}' initialized")

    def _init_intelligence(self) -> None:
        """Initialize intelligence features."""
        if not INTELLIGENCE_AVAILABLE:
            logger.warning("Intelligence features not available")
            return

        self._intent_detector = IntentDetector(llm_router=self.llm)
        self._mood_detector = MoodDetector()
        self._safety_checker = SafetyChecker()
        self._confidence_scorer = ConfidenceScorer()
        self._summarizer = ConversationSummarizer(llm_router=self.llm)
        self._personality_manager = PersonalityManager()

        logger.info("Intelligence features initialized")

    def _default_system_prompt(self) -> str:
        """Generate default system prompt."""
        return f"""You are {self.name}, a helpful AI assistant.

Guidelines:
- Be helpful, accurate, and concise
- Ask clarifying questions when needed
- Remember context from the conversation
- If you don't know something, say so

Current time: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"""

    def _get_session(
        self, session_id: str | None = None, user_id: str | None = None
    ) -> Session:
        """Get or create a session."""
        # Generate session ID if not provided
        if not session_id:
            session_id = f"user_{user_id}" if user_id else f"default_{self.name}"

        # Use session manager if available
        if self.session_manager:
            return self.session_manager.get_session(
                session_id=session_id, user_id=user_id, bot_name=self.name
            )

        # Otherwise use in-memory
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(
                session_id=session_id, user_id=user_id, bot_name=self.name
            )
            self.stats["sessions_created"] += 1

        return self._sessions[session_id]

    def _save_session(self, session: Session) -> None:
        """Save session if persistence enabled."""
        if self.session_manager:
            self.session_manager.save_session(session)

    def _build_messages(
        self, session: Session, user_message: str
    ) -> list[dict[str, str]]:
        """Build message list for LLM."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add history
        history = session.get_history(self.config.max_history)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        return messages

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Call the LLM to generate response (sync)."""
        return asyncio.run(self._call_llm_async(messages))

    async def _call_llm_async(self, messages: list[dict[str, str]]) -> str:
        """Call the LLM to generate response (async)."""
        # If custom LLM provided
        if self.llm:
            # Prefer explicit chat/generate methods over bare callables so that
            # router-like objects (with .chat) behave as expected in tests.
            if hasattr(self.llm, "chat"):
                result = self.llm.chat(messages=messages)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            if hasattr(self.llm, "generate"):
                result = self.llm.generate(messages)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            if callable(self.llm):
                result = self.llm(messages)
                if asyncio.iscoroutine(result):
                    return await result
                return result

        # Default: use LLMRouter with its built-in fallback chain
        try:
            router = get_router()
            # LLMRouter.chat expects a single message string; we join the
            # structured history into a compact transcript while preserving
            # roles for routing heuristics.
            transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
            return await router.chat(
                message=transcript,
                model=self.config.model,
                temperature=self.config.temperature,
            )
        except RuntimeError as e:
            # Handle LLMRouter errors with helpful context
            logger.error(f"LLM Router error: {e}")
            # The error message from LLMRouter already includes the helpful setup guide
            return str(e)
        except Exception as e:
            # Generic error handling
            logger.error(f"Unexpected error in chat: {e}", exc_info=True)
            return (
                "I encountered an unexpected error while processing your request. "
                "Please try again or contact support if the issue persists."
            )

    def _store_memory(self, session: Session, message: str, response: str) -> None:
        """Store important information in long-term memory."""
        if not self.memory or not self.config.use_memory:
            return

        try:
            # Simple heuristic: store if message contains "remember" or is factual
            store_indicators = [
                "remember",
                "my name is",
                "i am",
                "i work at",
                "my email",
                "my phone",
                "my address",
                "i like",
                "i prefer",
                "i need",
            ]

            lower_msg = message.lower()
            should_store = any(ind in lower_msg for ind in store_indicators)

            if should_store:
                self.memory.store(
                    content=f"User said: {message}",
                    metadata={
                        "session_id": session.session_id,
                        "user_id": session.user_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "type": "user_fact",
                    },
                )
                logger.debug(f"Stored memory: {message[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to store memory: {e}")

    def _retrieve_context(self, session: Session, message: str) -> str:
        """Retrieve relevant context from memory."""
        if not self.memory or not self.config.use_memory:
            return ""

        try:
            # Query memory for relevant facts
            results = self.memory.search(
                query=message,
                user_id=session.user_id if self.config.customer_isolation else None,
                limit=5,
            )

            if results:
                context = "\n".join([r.get("content", "") for r in results])
                return f"\n\nRelevant context from memory:\n{context}"
        except Exception as e:
            logger.warning(f"Failed to retrieve context: {e}")

        return ""

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any | None] = None,
    ) -> str:
        """
        Send a message and get a response (sync).

        Args:
            message: User's message
            session_id: Optional session identifier
            user_id: Optional user/customer ID
            metadata: Additional metadata to store

        Returns:
            Bot's response text

        Example:
            response = bot.chat("What's the weather?")
            response = bot.chat("Help me", user_id="customer_123")
        """
        return asyncio.run(self.chat_async(message, session_id, user_id, metadata))

    async def chat_async(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any | None] = None,
    ) -> str:
        """
        Send a message and get a response (async).

        Args:
            message: User's message
            session_id: Optional session identifier
            user_id: Optional user/customer ID
            metadata: Additional metadata to store

        Returns:
            Bot's response text

        Example:
            response = await bot.chat_async("What's the weather?")
            response = await bot.chat_async("Help me", user_id="customer_123")
        """
        try:
            # Get/create session
            session = self._get_session(session_id, user_id)
            logger.info(f"Chat started: session={session.session_id}, user={user_id}")
            logger.debug(f"Processing message: length={len(message)}")

            # Check for slash commands first
            command_response = self._handle_slash_command(message)
            if command_response:
                return command_response

            # Create message object
            user_msg = ChatMessage(
                role="user", content=message, metadata=metadata or {}
            )

            # Fire hook
            if self._on_message:
                self._on_message(user_msg)

            # Add to session
            session.add_message("user", message, **(metadata or {}))
            self.stats["messages_received"] += 1

            # Retrieve memory context
            context = self._retrieve_context(session, message)

            # Build messages for LLM
            messages = self._build_messages(session, message + context)

            # Get response (async)
            response_text = await self._call_llm_async(messages)

            # Create response message
            response_msg = ChatMessage(
                role="assistant",
                content=response_text,
                metadata={"model": self.config.model},
            )

            # Fire hook
            if self._on_response:
                self._on_response(response_msg)

            # Add to session
            session.add_message("assistant", response_text)
            self.stats["responses_sent"] += 1

            # Save session
            self._save_session(session)

            # Store in memory if appropriate
            self._store_memory(session, message, response_text)

            logger.info(
                f"Chat completed: session={session.session_id}, response_length={len(response_text)}"
            )
            return response_text

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(
                f"Chat error: session={session_id}, error={type(e).__name__}: {str(e)}",
                exc_info=True,
            )

            if self._on_error:
                self._on_error(e)

            return f"I encountered an error: {str(e)}"

    def get_session(
        self, session_id: str | None = None, user_id: str | None = None
    ) -> ChatSession:
        """
        Get session info.

        Args:
            session_id: Session identifier
            user_id: User identifier

        Returns:
            ChatSession with history
        """
        session = self._get_session(session_id, user_id)
        return ChatSession(
            session_id=session.session_id,
            user_id=session.user_id,
            history=[ChatMessage.from_dict(m) for m in session.messages],
        )

    def clear_session(
        self, session_id: str | None = None, user_id: str | None = None
    ) -> None:
        """Clear session history."""
        session = self._get_session(session_id, user_id)
        session.clear_history()
        self._save_session(session)

    def set_system_prompt(self, prompt: str) -> None:
        """Update system prompt."""
        self.system_prompt = prompt

    def get_stats(self) -> dict[str, Any]:
        """Get chatbot statistics."""
        return {
            **self.stats,
            "name": self.name,
            "model": self.config.model,
            "memory_enabled": self.memory is not None,
            "persistence_enabled": self.session_manager is not None,
            "intelligence_enabled": self._intelligence_enabled,
        }

    # =========================================================================
    # Model Switching Commands
    # =========================================================================

    def _handle_slash_command(self, message: str) -> str | None:
        """
        Handle slash commands for model switching and control.

        Returns:
            Response string if command was handled, None otherwise.
        """
        message = message.strip()
        if not message.startswith("/"):
            return None

        # Parse command (case-insensitive)
        parts = message.split(None, 1)
        command = parts[0].lower()
        parts[1] if len(parts) > 1 else ""

        # Route to appropriate handler
        if command in ["/models", "/help"]:
            return self._cmd_show_models()
        elif command in ["/current"]:
            return self._cmd_show_current()
        elif command in ["/fallback"]:
            return self._cmd_toggle_fallback()
        elif command.startswith("/l"):
            return self._cmd_switch_local(command)
        elif command.startswith("/cl"):
            return self._cmd_switch_claude(command)
        elif command.startswith("/op"):
            return self._cmd_switch_openai(command)
        elif command.startswith("/go"):
            return self._cmd_switch_gemini(command)
        elif command.startswith("/gr"):
            return self._cmd_switch_groq(command)

        # Unknown command
        return f"❌ Unknown command: {command}\n\nType /help for available commands."

    def _cmd_show_models(self) -> str:
        """Show all available models with descriptions."""
        lines = [
            "🤖 AVAILABLE MODELS",
            "=" * 70,
            "",
            "LOCAL (FREE, no internet - always available):",
            "  /L1  llama3.2:3b       ⚡⚡  Fast",
            "  /L2  llama3.1:8b       ⚡    Quality",
            "  /L3  mistral:7b        ⚡    Alternative",
            "  /L4  nomic-embed       ⚡⚡⚡ Embeddings only",
            "",
            "CLAUDE (Anthropic - best reasoning):",
            "  /CL  claude-sonnet-4   ⚡⚡  Best ($$$)",
            "  /CL2 claude-haiku      ⚡⚡⚡ Cheap ($)",
            "  /CL3 claude-opus       ⚡    Premium ($$$$)",
            "",
            "OPENAI (best for coding):",
            "  /OP  gpt-4o            ⚡⚡  Best ($$$)",
            "  /OP2 gpt-4o-mini       ⚡⚡⚡ Cheap ($)",
            "  /OP3 o1                🐢    Reasoning ($$$$)",
            "",
            "GEMINI (Google - good free tier):",
            "  /GO  gemini-2.5-flash  ⚡⚡⚡ Fast (FREE)",
            "  /GO2 gemini-2.5-pro    ⚡⚡  Quality ($$)",
            "",
            "GROQ (fastest cloud - FREE):",
            "  /GR  llama-3.3-70b     ⚡⚡⚡⚡ Blazing (FREE)",
            "  /GR2 mixtral-8x7b      ⚡⚡⚡ Alternative (FREE)",
            "",
            "CONTROL COMMANDS:",
            "  /current         Show current model",
            "  /fallback        Toggle auto-fallback on failure",
            "",
            "=" * 70,
            f"Current: {self._current_model} | Auto-fallback: {'✓ ON' if self._auto_fallback_enabled else '✗ OFF'}",
        ]
        return "\n".join(lines)

    def _cmd_show_current(self) -> str:
        """Show current model info."""
        try:
            config = MODEL_ALIASES[self._current_model]
            lines = [
                f"📌 Current Model: {self._current_model}",
                f"   Provider: {config['provider']}",
                f"   Model: {config['model']}",
                f"   Description: {config['description']}",
                f"   Speed: {config['speed']}",
                f"   Cost: {config['cost']}",
                f"   Auto-fallback: {'✓ ON' if self._auto_fallback_enabled else '✗ OFF'}",
            ]
            if "fallback" in config:
                lines.append(f"   Fallback to: {config['fallback']}")
            return "\n".join(lines)
        except KeyError:
            return f"❌ Invalid current model: {self._current_model}"

    def _cmd_toggle_fallback(self) -> str:
        """Toggle auto-fallback on/off."""
        self._auto_fallback_enabled = not self._auto_fallback_enabled
        status = "✓ ENABLED" if self._auto_fallback_enabled else "✗ DISABLED"
        return f"Auto-fallback: {status}\n\nWhen enabled, chatbot automatically falls back to alternate models on failure."

    def _cmd_switch_local(self, command: str) -> str:
        """Switch to local model (L1, L2, L3, L4)."""
        model_code = command[1:].upper()  # e.g., /l1 -> L1

        if model_code not in MODEL_ALIASES:
            return f"❌ Unknown local model: {command}\n\nValid: /L1, /L2, /L3, /L4"

        config = MODEL_ALIASES[model_code]

        # Check if it's chat-capable
        if not config.get("chat_capable", True):
            return f"❌ {model_code} is for embeddings only, not chat."

        return self._perform_switch(model_code, config)

    def _cmd_switch_claude(self, command: str) -> str:
        """Switch to Claude model (CL, CL1, CL2, CL3)."""
        model_code = command[1:].upper()  # e.g., /cl -> CL

        # Handle /cl as /cl (alias for /CL)
        if model_code == "L" or model_code == "L1":
            model_code = "CL"
        elif model_code == "L2":
            model_code = "CL2"
        elif model_code == "L3":
            model_code = "CL3"

        if model_code not in MODEL_ALIASES:
            return f"❌ Unknown Claude model: {command}\n\nValid: /CL, /CL2, /CL3"

        config = MODEL_ALIASES[model_code]
        return self._perform_switch(model_code, config)

    def _cmd_switch_openai(self, command: str) -> str:
        """Switch to OpenAI model (OP, OP1, OP2, OP3)."""
        model_code = command[1:].upper()  # e.g., /op -> OP

        # Handle /op as /OP (alias for OP)
        if model_code == "P" or model_code == "P1":
            model_code = "OP"
        elif model_code == "P2":
            model_code = "OP2"
        elif model_code == "P3":
            model_code = "OP3"

        if model_code not in MODEL_ALIASES:
            return f"❌ Unknown OpenAI model: {command}\n\nValid: /OP, /OP2, /OP3"

        config = MODEL_ALIASES[model_code]
        return self._perform_switch(model_code, config)

    def _cmd_switch_gemini(self, command: str) -> str:
        """Switch to Gemini model (GO, GO1, GO2)."""
        model_code = command[1:].upper()  # e.g., /go -> GO

        # Handle /go as /GO (alias for GO)
        if model_code == "O" or model_code == "O1":
            model_code = "GO"
        elif model_code == "O2":
            model_code = "GO2"

        if model_code not in MODEL_ALIASES:
            return f"❌ Unknown Gemini model: {command}\n\nValid: /GO, /GO2"

        config = MODEL_ALIASES[model_code]
        return self._perform_switch(model_code, config)

    def _cmd_switch_groq(self, command: str) -> str:
        """Switch to Groq model (GR, GR1, GR2)."""
        model_code = command[1:].upper()  # e.g., /gr -> GR

        # Handle /gr as /GR (alias for GR)
        if model_code == "R" or model_code == "R1":
            model_code = "GR"
        elif model_code == "R2":
            model_code = "GR2"

        if model_code not in MODEL_ALIASES:
            return f"❌ Unknown Groq model: {command}\n\nValid: /GR, /GR2"

        config = MODEL_ALIASES[model_code]
        return self._perform_switch(model_code, config)

    def _perform_switch(self, model_code: str, config: dict[str, Any]) -> str:
        """Perform the actual model switch and return confirmation."""
        self._current_model = model_code

        # Update the config model
        self.config.model = config["model"]

        # Build feedback message
        emoji_map = {
            "ollama": "🖥️",
            "anthropic": "🧠",
            "openai": "🔵",
            "google": "🔶",
            "groq": "⚡",
        }
        emoji = emoji_map.get(config["provider"], "🤖")

        lines = [
            f"✅ Switched to {model_code}",
            f"   {emoji} {config['description']}",
            f"   Model: {config['model']}",
            f"   Cost: {config['cost']}",
            f"   Speed: {config['speed']}",
        ]

        return "\n".join(lines)

    # =========================================================================
    # Intelligence Features (optional)
    # =========================================================================

    def detect_intent(self, message: str) -> tuple:
        """
        Detect user intent (sync, keyword-based).

        Args:
            message: User message

        Returns:
            Tuple of (Intent, confidence)

        Example:
            intent, conf = bot.detect_intent("Fix the login bug")
            # (Intent.ACTION, 0.85)
        """
        if not self._intent_detector:
            return (None, 0.0)
        return self._intent_detector.detect_sync(message)

    async def detect_intent_async(self, message: str) -> tuple:
        """
        Detect user intent (async, LLM-based if available).

        Args:
            message: User message

        Returns:
            Tuple of (Intent, confidence)
        """
        if not self._intent_detector:
            return (None, 0.0)
        return await self._intent_detector.detect(message)

    def get_mood(self, message: str, history: list[dict | None] = None) -> tuple:
        """
        Detect user mood.

        Args:
            message: User message
            history: Optional conversation history

        Returns:
            Tuple of (Mood, confidence)

        Example:
            mood, conf = bot.get_mood("This is broken AGAIN!!!")
            # (Mood.FRUSTRATED, 0.95)
        """
        if not self._mood_detector:
            return (None, 0.0)
        return self._mood_detector.detect(message, history)

    def switch_personality(self, name: str) -> Any | None:
        """
        Switch to a different personality profile.

        Args:
            name: Profile name (professional, friendly, technical, brief)

        Returns:
            Active PersonalityProfile or None

        Example:
            profile = bot.switch_personality("friendly")
        """
        if not self._personality_manager:
            return None

        profile = self._personality_manager.switch(name)

        # Update system prompt if personality has additions
        if profile.system_prompt_additions:
            self.system_prompt = (
                self._default_system_prompt() + "\n\n" + profile.system_prompt_additions
            )

        return profile

    def get_personality(self, name: str | None = None) -> Any | None:
        """
        Get a personality profile.

        Args:
            name: Profile name, or None for current

        Returns:
            PersonalityProfile or None
        """
        if not self._personality_manager:
            return None
        return self._personality_manager.get_profile(name)

    def score_confidence(self, response: str, has_sources: bool = False) -> float:
        """
        Score confidence of a response.

        Args:
            response: Response text
            has_sources: Whether response cites sources

        Returns:
            Confidence score 0.0-1.0
        """
        if not self._confidence_scorer:
            return 0.5
        return self._confidence_scorer.score(response, has_sources)

    def needs_safety_confirmation(self, action: str) -> bool:
        """
        Check if action needs safety confirmation.

        Args:
            action: Action description

        Returns:
            True if confirmation required

        Example:
            if bot.needs_safety_confirmation("delete all users"):
                # Ask for confirmation
        """
        if not self._safety_checker:
            return False
        return self._safety_checker.needs_confirmation(action)

    def detect_hallucination_risk(
        self, response: str, sources: list | None = None
    ) -> float:
        """
        Score hallucination risk of a response.

        Args:
            response: Response text
            sources: Optional sources/citations

        Returns:
            Risk score 0.0 (safe) to 1.0 (risky)
        """
        if not self._safety_checker:
            return 0.0
        return self._safety_checker.detect_potential_hallucination(response, sources)

    async def summarize_history(
        self, session_id: str | None = None, user_id: str | None = None
    ) -> str:
        """
        Summarize conversation history.

        Args:
            session_id: Session identifier
            user_id: User identifier

        Returns:
            Summary string
        """
        if not self._summarizer:
            return ""

        session = self._get_session(session_id, user_id)
        messages = [
            {"role": m["role"], "content": m["content"]} for m in session.messages
        ]
        return await self._summarizer.summarize(messages)

    def __repr__(self) -> str:
        return f"Chatbot(name='{self.name}', model='{self.config.model}')"
