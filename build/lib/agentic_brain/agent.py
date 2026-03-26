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

from __future__ import annotations

# SPDX-License-Identifier: GPL-3.0-or-later
"""
Core Agent class for agentic-brain.

Combines memory, audio, and LLM routing into a cohesive agent.

Example:
    >>> from agentic_brain import Agent
    >>> agent = Agent(name="assistant")
    >>> response = agent.chat("Hello!")  # sync
    >>> response = await agent.chat_async("Hello!")  # async
    >>> print(response)
"""


import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .audio import Audio, AudioConfig
from .memory import DataScope, InMemoryStore, Memory, Neo4jMemory
from .router import LLMRouter, Provider, RouterConfig

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent configuration."""

    name: str = "agent"
    system_prompt: str | None = None

    # Memory
    neo4j_uri: str | None = None
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    memory_scope: DataScope = DataScope.PRIVATE
    customer_id: str | None = None

    # Audio
    audio_enabled: bool = True
    voice: str = "Karen"
    speech_rate: int = 175

    # LLM
    default_provider: Provider = Provider.OLLAMA
    default_model: str = "llama3.1:8b"
    temperature: float = 0.7


class Agent:
    """
    Intelligent agent with memory, voice, and LLM capabilities.

    Features:
    - Persistent memory (Neo4j or in-memory fallback)
    - Cross-platform voice output
    - LLM routing with fallback
    - Data scope isolation

    Example:
        >>> # Basic agent
        >>> agent = Agent(name="helper")
        >>> response = agent.chat("What can you help with?")
        >>>
        >>> # Agent with Neo4j memory
        >>> agent = Agent(
        ...     name="assistant",
        ...     neo4j_uri="bolt://localhost:7687",
        ...     neo4j_password="password"
        ... )
        >>>
        >>> # Customer-scoped agent (B2B isolation)
        >>> agent = Agent(
        ...     name="support",
        ...     memory_scope=DataScope.CUSTOMER,
        ...     customer_id="acme-corp"
        ... )
    """

    DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant.
Be concise and accurate. If you don't know something, say so."""

    def __init__(
        self,
        name: str = "agent",
        system_prompt: str | None = None,
        neo4j_uri: str | None = None,
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        memory_scope: DataScope = DataScope.PRIVATE,
        customer_id: str | None = None,
        audio_enabled: bool = True,
        voice: str = "Karen",
        **kwargs,
    ):
        """
        Initialize agent.

        Args:
            name: Agent name (for logging)
            system_prompt: Custom system prompt
            neo4j_uri: Neo4j connection URI (None for in-memory)
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            memory_scope: Default data scope
            customer_id: Customer ID for CUSTOMER scope
            audio_enabled: Enable voice output
            voice: Default voice name
        """
        self.config = AgentConfig(
            name=name,
            system_prompt=system_prompt,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            memory_scope=memory_scope,
            customer_id=customer_id,
            audio_enabled=audio_enabled,
            voice=voice,
        )

        # Initialize components
        self._init_memory()
        self._init_audio()
        self._init_router()

        # Conversation history (current session)
        self._history: list[dict] = []

        logger.info(f"Agent '{name}' initialized")

    def _init_memory(self) -> None:
        """Initialize memory backend."""
        if self.config.neo4j_uri:
            try:
                self.memory = Neo4jMemory(
                    uri=self.config.neo4j_uri,
                    user=self.config.neo4j_user,
                    password=self.config.neo4j_password,
                )
                self.memory.connect()
                logger.info("Neo4j memory connected")
            except Exception as e:
                logger.warning(f"Neo4j unavailable, using in-memory: {e}")
                self.memory = InMemoryStore()
        else:
            self.memory = InMemoryStore()
            logger.info("Using in-memory storage")

    def _init_audio(self) -> None:
        """Initialize audio engine."""
        if self.config.audio_enabled:
            self.audio = Audio(
                AudioConfig(
                    default_voice=self.config.voice,
                    default_rate=self.config.speech_rate,
                )
            )
        else:
            self.audio = None

    def _init_router(self) -> None:
        """Initialize LLM router and warn if no providers available."""
        from .router import ProviderChecker

        self.router = LLMRouter(
            RouterConfig(
                default_provider=self.config.default_provider,
                default_model=self.config.default_model,
            )
        )

        # Check if any providers are available (warn if not)
        if not ProviderChecker.has_any_provider():
            logger.warning(
                "No LLM providers configured. Run 'agentic check' for setup instructions."
            )

    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def chat(
        self,
        message: str,
        remember: bool = True,
        speak: bool = False,
        scope: DataScope | None = None,
    ) -> str:
        """
        Send message and get response (sync).

        Args:
            message: User message
            remember: Store in memory
            speak: Speak response aloud
            scope: Override memory scope

        Returns:
            Agent response text

        Example:
            >>> response = agent.chat("Hello!")
            >>> response = agent.chat("Remember this", remember=True)
            >>> response = agent.chat("Tell me", speak=True)
        """
        return asyncio.run(self.chat_async(message, remember, speak, scope))

    async def chat_async(
        self,
        message: str,
        remember: bool = True,
        speak: bool = False,
        scope: DataScope | None = None,
    ) -> str:
        """
        Send message and get response (async).

        Args:
            message: User message
            remember: Store in memory
            speak: Speak response aloud
            scope: Override memory scope

        Returns:
            Agent response text

        Example:
            >>> response = await agent.chat_async("Hello!")
            >>> response = await agent.chat_async("Remember this", remember=True)
        """
        scope = scope or self.config.memory_scope

        # Add to history
        self._history.append(
            {
                "role": "user",
                "content": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Store user message in memory
        if remember:
            self.memory.store(
                content=f"User: {message}",
                scope=scope,
                customer_id=self.config.customer_id,
            )

        # Get relevant context from memory
        context = self._get_context(message, scope)

        # Build system prompt with context
        system = self.system_prompt
        if context:
            system += f"\n\nRelevant context:\n{context}"

        # Get LLM response (async)
        try:
            response = await self.router.chat(
                message=message,
                system=system,
                temperature=self.config.temperature,
            )
            answer = response.content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            answer = "I'm having trouble responding right now. Please try again."

        # Add to history
        self._history.append(
            {
                "role": "assistant",
                "content": answer,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Store response in memory
        if remember:
            self.memory.store(
                content=f"Assistant: {answer}",
                scope=scope,
                customer_id=self.config.customer_id,
            )

        # Speak if requested
        if speak and self.audio:
            self.audio.speak(answer)

        return answer

    def _get_context(self, query: str, scope: DataScope) -> str:
        """Get relevant context from memory."""
        try:
            memories = self.memory.search(
                query=query,
                scope=scope,
                customer_id=self.config.customer_id,
                limit=5,
            )

            if not memories:
                return ""

            context_parts = []
            for mem in memories:
                context_parts.append(f"- {mem.content}")

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"Context retrieval failed: {e}")
            return ""

    def remember(
        self,
        content: str,
        scope: DataScope | None = None,
    ) -> Memory:
        """
        Store something in memory.

        Args:
            content: Content to remember
            scope: Data scope (default: agent's scope)

        Returns:
            Created Memory object

        Example:
            >>> agent.remember("User prefers morning meetings")
            >>> agent.remember("Client API key: xxx", scope=DataScope.PRIVATE)
        """
        scope = scope or self.config.memory_scope
        return self.memory.store(
            content=content,
            scope=scope,
            customer_id=self.config.customer_id,
        )

    def recall(
        self,
        query: str,
        scope: DataScope | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        """
        Search memories.

        Args:
            query: Search query
            scope: Data scope to search
            limit: Max results

        Returns:
            List of matching memories

        Example:
            >>> memories = agent.recall("meetings")
            >>> for m in memories:
            ...     print(m.content)
        """
        scope = scope or self.config.memory_scope
        return self.memory.search(
            query=query,
            scope=scope,
            customer_id=self.config.customer_id,
            limit=limit,
        )

    def speak(self, text: str) -> bool:
        """
        Speak text aloud.

        Args:
            text: Text to speak

        Returns:
            True if spoken successfully
        """
        if self.audio:
            return self.audio.speak(text)
        return False

    def announce(self, message: str, sound: str = "notification") -> bool:
        """
        Play sound and speak message.

        Args:
            message: Message to announce
            sound: Sound to play first

        Returns:
            True if successful
        """
        if self.audio:
            return self.audio.announce(message, sound=sound)
        return False

    @property
    def history(self) -> list[dict]:
        """Get conversation history."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    def close(self) -> None:
        """Clean up resources."""
        if hasattr(self.memory, "close"):
            self.memory.close()
        logger.info(f"Agent '{self.config.name}' closed")

    def __enter__(self) -> Agent:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"Agent(name='{self.config.name}', scope={self.config.memory_scope.value})"
        )
