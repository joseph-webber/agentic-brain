"""
Core Agent class for agentic-brain.

Combines memory, audio, and LLM routing into a cohesive agent.

Example:
    >>> from agentic_brain import Agent
    >>> agent = Agent(name="assistant")
    >>> response = agent.chat("Hello!")
    >>> print(response)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any
import logging

from .memory import Neo4jMemory, InMemoryStore, DataScope, Memory
from .audio import Audio, AudioConfig
from .router import LLMRouter, RouterConfig, Response, Provider

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent configuration."""
    name: str = "agent"
    system_prompt: Optional[str] = None
    
    # Memory
    neo4j_uri: Optional[str] = None
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    memory_scope: DataScope = DataScope.PRIVATE
    customer_id: Optional[str] = None
    
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
        system_prompt: Optional[str] = None,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        memory_scope: DataScope = DataScope.PRIVATE,
        customer_id: Optional[str] = None,
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
            self.audio = Audio(AudioConfig(
                default_voice=self.config.voice,
                default_rate=self.config.speech_rate,
            ))
        else:
            self.audio = None
    
    def _init_router(self) -> None:
        """Initialize LLM router."""
        self.router = LLMRouter(RouterConfig(
            default_provider=self.config.default_provider,
            default_model=self.config.default_model,
        ))
    
    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT
    
    def chat(
        self,
        message: str,
        remember: bool = True,
        speak: bool = False,
        scope: Optional[DataScope] = None,
    ) -> str:
        """
        Send message and get response.
        
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
        scope = scope or self.config.memory_scope
        
        # Add to history
        self._history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
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
        
        # Get LLM response
        try:
            response = self.router.chat(
                message=message,
                system=system,
                temperature=self.config.temperature,
            )
            answer = response.content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            answer = "I'm having trouble responding right now. Please try again."
        
        # Add to history
        self._history.append({
            "role": "assistant",
            "content": answer,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
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
        scope: Optional[DataScope] = None,
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
        scope: Optional[DataScope] = None,
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
    
    def __enter__(self) -> "Agent":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()
    
    def __repr__(self) -> str:
        return f"Agent(name='{self.config.name}', scope={self.config.memory_scope.value})"
