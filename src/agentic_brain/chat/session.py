# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Session Management
==================

Handles session persistence so chatbots survive restarts.
Sessions are stored as JSON files - simple and portable.

Features:
- Auto-save on every message
- Crash recovery  
- Multi-user sessions
- Configurable cleanup
"""

import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """
    A chat session with history and metadata.
    
    Attributes:
        session_id: Unique identifier
        user_id: Optional user/customer identifier
        bot_name: Name of the chatbot
        messages: Conversation history
        metadata: Additional session data
        created_at: When session started
        updated_at: Last activity time
    """
    session_id: str
    user_id: Optional[str] = None
    bot_name: str = "assistant"
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def add_message(self, role: str, content: str, **kwargs) -> Dict[str, Any]:
        """Add a message to the session."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs
        }
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return message
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get message history, optionally limited."""
        if limit:
            return self.messages[-limit:]
        return self.messages
    
    def clear_history(self) -> None:
        """Clear message history."""
        self.messages = []
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        return cls(**data)


class SessionManager:
    """
    Manages multiple chat sessions with persistence.
    
    Usage:
        manager = SessionManager(Path("./sessions"))
        
        # Get or create session
        session = manager.get_session("user_123")
        session.add_message("user", "Hello!")
        manager.save_session(session)
        
        # Recover after restart
        session = manager.load_session("user_123")
    """
    
    def __init__(
        self,
        session_dir: Path,
        timeout_seconds: int = 3600,
        auto_cleanup: bool = True
    ) -> None:
        """
        Initialize session manager.
        
        Args:
            session_dir: Directory to store session files
            timeout_seconds: Session timeout (default: 1 hour)
            auto_cleanup: Remove expired sessions on startup
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timedelta(seconds=timeout_seconds)
        self.sessions: Dict[str, Session] = {}
        
        if auto_cleanup:
            self._cleanup_expired()
    
    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        # Hash the session ID for safe filenames
        safe_id = hashlib.sha256(session_id.encode()).hexdigest()[:16]
        return self.session_dir / f"session_{safe_id}.json"
    
    def _cleanup_expired(self) -> None:
        """Remove expired session files."""
        now = datetime.now(timezone.utc)
        cleaned = 0
        
        for file in self.session_dir.glob("session_*.json"):
            try:
                data = json.loads(file.read_text())
                updated_str = data.get("updated_at", "2000-01-01T00:00:00+00:00")
                updated = datetime.fromisoformat(updated_str)
                # Ensure timezone-aware for comparison
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if now - updated > self.timeout:
                    file.unlink()
                    cleaned += 1
            except (json.JSONDecodeError, ValueError, OSError) as e:
                # json.JSONDecodeError: invalid JSON
                # ValueError: invalid datetime format
                # OSError: file read/delete errors
                logger.warning(f"Error cleaning session {file}: {e}")
        
        if cleaned:
            logger.info(f"Cleaned up {cleaned} expired sessions")
    
    def get_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        bot_name: str = "assistant"
    ) -> Session:
        """
        Get or create a session.
        
        Args:
            session_id: Unique session identifier
            user_id: Optional user/customer ID
            bot_name: Name of the chatbot
            
        Returns:
            Session object (loaded or new)
        """
        # Check memory cache
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try to load from disk
        session = self.load_session(session_id)
        if session:
            self.sessions[session_id] = session
            return session
        
        # Create new session
        session = Session(
            session_id=session_id,
            user_id=user_id,
            bot_name=bot_name
        )
        self.sessions[session_id] = session
        return session
    
    def save_session(self, session: Session) -> bool:
        """
        Save session to disk.
        
        Args:
            session: Session to save
            
        Returns:
            True if saved successfully
        """
        try:
            path = self._session_path(session.session_id)
            path.write_text(json.dumps(session.to_dict(), indent=2))
            return True
        except (IOError, FileNotFoundError, PermissionError, json.JSONDecodeError, TypeError) as e:
            # IOError/OSError: write failures
            # FileNotFoundError: path doesn't exist
            # PermissionError: no write permission
            # TypeError: object not JSON serializable
            logger.error(f"Failed to save session: {e}", exc_info=True)
            return False
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """
        Load session from disk.
        
        Args:
            session_id: Session to load
            
        Returns:
            Session if found, None otherwise
        """
        try:
            path = self._session_path(session_id)
            if path.exists():
                data = json.loads(path.read_text())
                return Session.from_dict(data)
        except (IOError, FileNotFoundError, json.JSONDecodeError, ValueError, TypeError) as e:
            # IOError/OSError: read failures
            # FileNotFoundError: file doesn't exist
            # json.JSONDecodeError: invalid JSON
            # ValueError: invalid data
            # TypeError: data incompatible with Session
            logger.warning(f"Failed to load session {session_id}: {e}", exc_info=True)
        return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from memory and disk.
        
        Args:
            session_id: Session to delete
            
        Returns:
            True if deleted
        """
        # Remove from memory
        self.sessions.pop(session_id, None)
        
        # Remove from disk
        try:
            path = self._session_path(session_id)
            if path.exists():
                path.unlink()
            return True
        except (IOError, FileNotFoundError, PermissionError) as e:
            # IOError/OSError: delete failures
            # FileNotFoundError: file doesn't exist (OK to ignore)
            # PermissionError: no delete permission
            logger.error(f"Failed to delete session: {e}", exc_info=True)
            return False
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        sessions = list(self.sessions.keys())
        
        # Also check disk for sessions not in memory
        for file in self.session_dir.glob("session_*.json"):
            try:
                data = json.loads(file.read_text())
                sid = data.get("session_id")
                if sid and sid not in sessions:
                    sessions.append(sid)
            except (json.JSONDecodeError, ValueError, OSError):
                # json.JSONDecodeError: invalid JSON file
                # ValueError: invalid data
                # OSError: file read error
                # Skip malformed files silently
                pass
        
        return sessions
    
    def get_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self.list_sessions())
