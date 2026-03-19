# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber

"""Lifecycle hooks system for agentic-brain.

This module provides a hooks management system for firing and registering
lifecycle events throughout the agentic-brain lifecycle.
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    """Context data passed to hook handlers."""

    event_type: str
    timestamp: datetime
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class HooksManager:
    """Manages lifecycle hooks for agentic-brain.

    Handles loading hooks from JSON configuration, registering programmatic handlers,
    and firing hooks at key lifecycle events.

    Built-in hook events:
    - on_session_start: Fired when a session begins
    - on_session_end: Fired when a session ends
    - on_message: Fired when a message is received
    - on_response: Fired when a response is generated
    - on_error: Fired when an error occurs
    """

    # Built-in hook event types
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"
    ON_MESSAGE = "on_message"
    ON_RESPONSE = "on_response"
    ON_ERROR = "on_error"

    BUILT_IN_HOOKS = {
        ON_SESSION_START,
        ON_SESSION_END,
        ON_MESSAGE,
        ON_RESPONSE,
        ON_ERROR,
    }

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the hooks manager.

        Args:
            config_path: Path to hooks.json configuration file.
                If None, uses default location at project root.
        """
        self.config_path = config_path or Path(__file__).parent.parent.parent.parent / "hooks.json"
        self._handlers: Dict[str, List[Callable]] = {
            hook: [] for hook in self.BUILT_IN_HOOKS
        }
        self._settings: Dict[str, Any] = {
            "timezone": "UTC",
            "capture_tools": True,
        }

        if self.config_path.exists():
            self._load_config()
        else:
            logger.debug(
                f"Hooks configuration not found at {self.config_path}, "
                "using defaults"
            )

    def _load_config(self) -> None:
        """Load hooks configuration from JSON file."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            # Validate version
            version = config.get("version", "1.0")
            if version != "1.0":
                logger.warning(f"Unknown hooks config version: {version}")

            # Load settings
            if "settings" in config:
                self._settings.update(config["settings"])

            # Load hook handlers (for future extensibility)
            # Currently, programmatic registration is the primary method
            logger.debug(f"Hooks configuration loaded from {self.config_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in hooks configuration: {e}")
        except Exception as e:
            logger.error(f"Error loading hooks configuration: {e}")

    def register(
        self, event_type: str, handler: Callable[[HookContext], None]
    ) -> None:
        """Register a handler for a hook event.

        Args:
            event_type: Name of the hook event (e.g., 'on_session_start')
            handler: Callable that accepts HookContext as parameter

        Raises:
            ValueError: If event_type is not a registered hook
        """
        if event_type not in self.BUILT_IN_HOOKS:
            logger.warning(
                f"Registering handler for unknown hook type: {event_type}. "
                f"Known hooks: {', '.join(sorted(self.BUILT_IN_HOOKS))}"
            )
            # Allow custom hooks to be registered
            if event_type not in self._handlers:
                self._handlers[event_type] = []

        if not callable(handler):
            raise ValueError(f"Handler must be callable, got {type(handler)}")

        self._handlers[event_type].append(handler)
        logger.debug(f"Registered handler for {event_type}: {handler.__name__}")

    def unregister(
        self, event_type: str, handler: Callable[[HookContext], None]
    ) -> bool:
        """Unregister a handler for a hook event.

        Args:
            event_type: Name of the hook event
            handler: The handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        if event_type not in self._handlers:
            return False

        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Unregistered handler for {event_type}: {handler.__name__}")
            return True

        return False

    def fire(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Fire a hook event, calling all registered handlers.

        Args:
            event_type: Name of the hook event to fire
            data: Optional data to pass to handlers

        Returns:
            None (handlers are called for side effects)
        """
        if event_type not in self._handlers:
            logger.warning(f"Attempt to fire unknown hook: {event_type}")
            return

        context = HookContext(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            data=data or {},
        )

        handlers = self._handlers[event_type]
        if not handlers:
            logger.debug(f"No handlers registered for {event_type}")
            return

        for handler in handlers:
            try:
                handler(context)
            except Exception as e:
                logger.error(
                    f"Error in hook handler {handler.__name__} for {event_type}: {e}",
                    exc_info=True,
                )

    def on_session_start(self, session_id: str, **kwargs) -> None:
        """Fire on_session_start hook.

        Args:
            session_id: Unique session identifier
            **kwargs: Additional session data
        """
        self.fire(
            self.ON_SESSION_START,
            {"session_id": session_id, **kwargs},
        )

    def on_session_end(self, session_id: str, **kwargs) -> None:
        """Fire on_session_end hook.

        Args:
            session_id: Unique session identifier
            **kwargs: Additional session data (e.g., duration, message_count)
        """
        self.fire(
            self.ON_SESSION_END,
            {"session_id": session_id, **kwargs},
        )

    def on_message(self, session_id: str, message: str, **kwargs) -> None:
        """Fire on_message hook.

        Args:
            session_id: Unique session identifier
            message: The message content
            **kwargs: Additional message metadata (e.g., role, source)
        """
        self.fire(
            self.ON_MESSAGE,
            {"session_id": session_id, "message": message, **kwargs},
        )

    def on_response(self, session_id: str, response: str, **kwargs) -> None:
        """Fire on_response hook.

        Args:
            session_id: Unique session identifier
            response: The response content
            **kwargs: Additional response metadata (e.g., model, latency)
        """
        self.fire(
            self.ON_RESPONSE,
            {"session_id": session_id, "response": response, **kwargs},
        )

    def on_error(
        self, session_id: str, error: Exception, **kwargs
    ) -> None:
        """Fire on_error hook.

        Args:
            session_id: Unique session identifier
            error: The exception that occurred
            **kwargs: Additional error context (e.g., context, stack_trace)
        """
        self.fire(
            self.ON_ERROR,
            {
                "session_id": session_id,
                "error": str(error),
                "error_type": type(error).__name__,
                **kwargs,
            },
        )

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        self._settings[key] = value

    def get_handlers(self, event_type: str) -> List[Callable]:
        """Get list of handlers for an event type.

        Args:
            event_type: Name of the hook event

        Returns:
            List of registered handlers
        """
        return self._handlers.get(event_type, []).copy()

    def clear_handlers(self, event_type: Optional[str] = None) -> None:
        """Clear handlers for an event type or all handlers.

        Args:
            event_type: Specific event to clear, or None to clear all
        """
        if event_type is None:
            logger.debug("Clearing all hook handlers")
            for key in self._handlers:
                self._handlers[key] = []
        else:
            logger.debug(f"Clearing handlers for {event_type}")
            if event_type in self._handlers:
                self._handlers[event_type] = []
