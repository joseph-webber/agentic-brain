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
Chat Configuration
==================

Simple, sensible defaults that just work.
Override only what you need.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


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

    session_dir: Path = field(
        default_factory=lambda: Path.home() / ".agentic_brain" / "sessions"
    )
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
        return cls(persist_sessions=False, use_memory=False, max_history=20)

    @classmethod
    def business(cls) -> "ChatConfig":
        """Business config - customer isolation enabled."""
        return cls(
            customer_isolation=True,
            persist_sessions=True,
            use_memory=True,
            session_timeout=7200,  # 2 hours
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
