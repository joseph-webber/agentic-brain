"""Logging plugin for Agentic Brain."""

import logging
from typing import Optional
from datetime import datetime, timezone
from agentic_brain.plugins.base import Plugin, PluginConfig

logger = logging.getLogger(__name__)


class LoggingPlugin(Plugin):
    """
    Logs all messages and responses.

    Configuration:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_messages: Whether to log incoming messages (default: True)
        log_responses: Whether to log outgoing responses (default: True)
        log_timestamps: Whether to include timestamps (default: True)
        log_session_id: Whether to log session ID (default: True)

    Example config (plugins.yaml):
        plugins:
          LoggingPlugin:
            enabled: true
            config:
              log_level: DEBUG
              log_messages: true
              log_responses: true
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """Initialize logging plugin."""
        if config is None:
            config = PluginConfig(
                name="LoggingPlugin",
                description="Logs all messages and responses",
            )
        super().__init__(config)

        # Parse config
        self.log_level = self.config.config.get("log_level", "INFO")
        self.log_messages = self.config.config.get("log_messages", True)
        self.log_responses = self.config.config.get("log_responses", True)
        self.log_timestamps = self.config.config.get("log_timestamps", True)
        self.log_session_id = self.config.config.get("log_session_id", True)

        # Create logger
        self.plugin_logger = logging.getLogger(f"agentic_brain.plugins.{self.name}")
        self.plugin_logger.setLevel(self.log_level)

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        logger.info(f"LoggingPlugin loaded with level={self.log_level}")

    def on_message(self, message: str, **kwargs) -> Optional[str]:
        """Log incoming messages."""
        if not self.log_messages:
            return None

        log_parts = []

        if self.log_timestamps:
            log_parts.append(f"[{datetime.now(timezone.utc).isoformat()}]")

        if self.log_session_id and "session_id" in kwargs:
            log_parts.append(f"Session: {kwargs['session_id']}")

        if "user_id" in kwargs:
            log_parts.append(f"User: {kwargs['user_id']}")

        log_parts.append(f"Message: {message[:100]}..." if len(message) > 100 else f"Message: {message}")

        log_msg = " | ".join(log_parts)
        self.plugin_logger.info(log_msg)

        return None

    def on_response(self, response: str, **kwargs) -> Optional[str]:
        """Log outgoing responses."""
        if not self.log_responses:
            return None

        log_parts = []

        if self.log_timestamps:
            log_parts.append(f"[{datetime.now(timezone.utc).isoformat()}]")

        if self.log_session_id and "session_id" in kwargs:
            log_parts.append(f"Session: {kwargs['session_id']}")

        log_parts.append(f"Response: {response[:100]}..." if len(response) > 100 else f"Response: {response}")

        log_msg = " | ".join(log_parts)
        self.plugin_logger.info(log_msg)

        return None

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        logger.info("LoggingPlugin unloaded")
