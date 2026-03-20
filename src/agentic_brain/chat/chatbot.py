# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Chatbot - The Star of the Show
==============================

A production-ready chatbot that:
- Remembers conversations (persists across restarts)
- Integrates with Neo4j memory for long-term knowledge
- Supports multi-user/customer isolation
- Works with any LLM (Ollama, OpenAI, Anthropic)
- Has hooks for lifecycle events

This is what makes agentic-brain worth using.

Quick Start:
    bot = Chatbot("assistant")
    response = bot.chat("Hello!")
    print(response)

With Memory:
    memory = Neo4jMemory()
    bot = Chatbot("support", memory=memory)
    response = bot.chat("Remember my name is Joseph")
    # ...later, even after restart...
    response = bot.chat("What's my name?")  # "Your name is Joseph"
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Union
from dataclasses import dataclass, field

from .config import ChatConfig
from .session import Session, SessionManager

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
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {})
        )


@dataclass
class ChatSession:
    """
    Active chat session with history.
    
    Lightweight wrapper for quick access to session data.
    """
    session_id: str
    user_id: Optional[str]
    history: List[ChatMessage] = field(default_factory=list)
    
    @property
    def message_count(self) -> int:
        return len(self.history)
    
    @property
    def last_message(self) -> Optional[ChatMessage]:
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
        memory: Optional[Any] = None,  # Neo4jMemory
        config: Optional[ChatConfig] = None,
        llm: Optional[Any] = None,  # LLMRouter or callable
        system_prompt: Optional[str] = None,
        # Lifecycle hooks
        on_message: Optional[Callable[[ChatMessage], None]] = None,
        on_response: Optional[Callable[[ChatMessage], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Initialize chatbot.
        
        Args:
            name: Bot name/identifier
            memory: Neo4jMemory instance for long-term storage
            config: ChatConfig or uses defaults
            llm: LLM provider (LLMRouter, callable, or None for default)
            system_prompt: Override system prompt
            on_message: Hook called on user message
            on_response: Hook called on bot response
            on_error: Hook called on errors
        """
        self.name = name
        self.config = config or ChatConfig()
        self.memory = memory
        self.llm = llm
        
        # System prompt
        self.system_prompt = system_prompt or self.config.system_prompt or self._default_system_prompt()
        
        # Session management
        self.session_manager = SessionManager(
            session_dir=self.config.session_dir,
            timeout_seconds=self.config.session_timeout
        ) if self.config.persist_sessions else None
        
        # In-memory sessions (for non-persistent mode)
        self._sessions: Dict[str, Session] = {}
        
        # Hooks
        self._on_message = on_message
        self._on_response = on_response
        self._on_error = on_error
        
        # Stats
        self.stats = {
            "messages_received": 0,
            "responses_sent": 0,
            "errors": 0,
            "sessions_created": 0
        }
        
        logger.info(f"Chatbot '{name}' initialized")
    
    def _default_system_prompt(self) -> str:
        """Generate default system prompt."""
        return f"""You are {self.name}, a helpful AI assistant.

Guidelines:
- Be helpful, accurate, and concise
- Ask clarifying questions when needed
- Remember context from the conversation
- If you don't know something, say so

Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"""
    
    def _get_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Session:
        """Get or create a session."""
        # Generate session ID if not provided
        if not session_id:
            if user_id:
                session_id = f"user_{user_id}"
            else:
                session_id = f"default_{self.name}"
        
        # Use session manager if available
        if self.session_manager:
            return self.session_manager.get_session(
                session_id=session_id,
                user_id=user_id,
                bot_name=self.name
            )
        
        # Otherwise use in-memory
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(
                session_id=session_id,
                user_id=user_id,
                bot_name=self.name
            )
            self.stats["sessions_created"] += 1
        
        return self._sessions[session_id]
    
    def _save_session(self, session: Session) -> None:
        """Save session if persistence enabled."""
        if self.session_manager:
            self.session_manager.save_session(session)
    
    def _build_messages(
        self,
        session: Session,
        user_message: str
    ) -> List[Dict[str, str]]:
        """Build message list for LLM."""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add history
        history = session.get_history(self.config.max_history)
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM to generate response."""
        # If custom LLM provided
        if self.llm:
            if callable(self.llm):
                return self.llm(messages)
            elif hasattr(self.llm, 'chat'):
                return self.llm.chat(messages)
            elif hasattr(self.llm, 'generate'):
                return self.llm.generate(messages)
        
        # Default: try Ollama
        try:
            import requests
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens
                    }
                },
                timeout=60
            )
            if response.ok:
                return response.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.warning(f"Ollama failed: {e}")
        
        # Fallback message
        return "I'm currently unable to process your request. Please try again."
    
    def _store_memory(self, session: Session, message: str, response: str) -> None:
        """Store important information in long-term memory."""
        if not self.memory or not self.config.use_memory:
            return
        
        try:
            # Simple heuristic: store if message contains "remember" or is factual
            store_indicators = [
                "remember", "my name is", "i am", "i work at",
                "my email", "my phone", "my address",
                "i like", "i prefer", "i need"
            ]
            
            lower_msg = message.lower()
            should_store = any(ind in lower_msg for ind in store_indicators)
            
            if should_store:
                self.memory.store(
                    content=f"User said: {message}",
                    metadata={
                        "session_id": session.session_id,
                        "user_id": session.user_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": "user_fact"
                    }
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
                limit=5
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
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send a message and get a response.
        
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
        try:
            # Get/create session
            session = self._get_session(session_id, user_id)
            logger.info(f"Chat started: session={session.session_id}, user={user_id}")
            logger.debug(f"Processing message: length={len(message)}")
            
            # Create message object
            user_msg = ChatMessage(
                role="user",
                content=message,
                metadata=metadata or {}
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
            
            # Get response
            response_text = self._call_llm(messages)
            
            # Create response message
            response_msg = ChatMessage(
                role="assistant",
                content=response_text,
                metadata={"model": self.config.model}
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
            
            logger.info(f"Chat completed: session={session.session_id}, response_length={len(response_text)}")
            return response_text
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Chat error: session={session_id}, error={type(e).__name__}: {str(e)}", exc_info=True)
            
            if self._on_error:
                self._on_error(e)
            
            return f"I encountered an error: {str(e)}"
    
    def get_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
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
            history=[ChatMessage.from_dict(m) for m in session.messages]
        )
    
    def clear_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """Clear session history."""
        session = self._get_session(session_id, user_id)
        session.clear_history()
        self._save_session(session)
    
    def set_system_prompt(self, prompt: str) -> None:
        """Update system prompt."""
        self.system_prompt = prompt
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chatbot statistics."""
        return {
            **self.stats,
            "name": self.name,
            "model": self.config.model,
            "memory_enabled": self.memory is not None,
            "persistence_enabled": self.session_manager is not None
        }
    
    def __repr__(self) -> str:
        return f"Chatbot(name='{self.name}', model='{self.config.model}')"
