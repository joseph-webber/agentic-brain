# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Chat Configuration
==================

Simple, sensible defaults that just work.
Override only what you need.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class ChatConfig:
    """
    Configuration for Chatbot instances.
    
    Sensible defaults - override only what you need:
    
        config = ChatConfig()  # Works out of the box
        
        config = ChatConfig(
            max_history=50,
            persist_sessions=True
        )
    """
    
    # Session settings
    max_history: int = 100
    """Maximum messages to keep in memory per session."""
    
    persist_sessions: bool = True
    """Save sessions to disk for recovery after restart."""
    
    session_timeout: int = 3600
    """Session timeout in seconds (default: 1 hour)."""
    
    session_dir: Path = field(default_factory=lambda: Path.home() / ".agentic_brain" / "sessions")
    """Directory to store session files."""
    
    # Memory settings
    use_memory: bool = True
    """Store important facts in Neo4j memory."""
    
    memory_threshold: float = 0.7
    """Confidence threshold for storing memories (0-1)."""
    
    # LLM settings
    model: str = "llama3.1:8b"
    """Default LLM model (Ollama format)."""
    
    temperature: float = 0.7
    """LLM temperature for responses."""
    
    max_tokens: int = 1024
    """Maximum tokens in response."""
    
    system_prompt: Optional[str] = None
    """Custom system prompt. If None, uses default."""
    
    # Business settings
    customer_isolation: bool = False
    """Enable per-customer data isolation (B2B mode)."""
    
    # Hooks
    hooks_file: Optional[Path] = None
    """Path to hooks.json for lifecycle events."""
    
    def __post_init__(self):
        """Ensure directories exist."""
        if self.persist_sessions:
            self.session_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def minimal(cls) -> "ChatConfig":
        """Minimal config - no persistence, no memory."""
        return cls(
            persist_sessions=False,
            use_memory=False,
            max_history=20
        )
    
    @classmethod
    def business(cls) -> "ChatConfig":
        """Business config - customer isolation enabled."""
        return cls(
            customer_isolation=True,
            persist_sessions=True,
            use_memory=True,
            session_timeout=7200  # 2 hours
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
