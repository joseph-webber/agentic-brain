"""
Example custom plugin for Agentic Brain
========================================

This is an example showing how to create a custom plugin.
Copy this file and modify it for your needs.

To use:
1. Save as plugins/my_plugin.py
2. Manager will auto-discover it
3. Configure in plugins.yaml if needed
"""

import logging
from typing import Optional
from agentic_brain.plugins.base import Plugin, PluginConfig

logger = logging.getLogger(__name__)


class MyCustomPlugin(Plugin):
    """
    Example custom plugin that tracks conversation context.
    
    This plugin:
    - Tracks message history per session
    - Detects conversation topics
    - Provides conversation statistics
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """Initialize plugin."""
        if config is None:
            config = PluginConfig(
                name="MyCustomPlugin",
                description="Example custom plugin for context tracking",
                config={
                    "max_history": 100,
                    "track_topics": True,
                }
            )
        super().__init__(config)

        # Load configuration
        self.max_history = self.config.config.get("max_history", 100)
        self.track_topics = self.config.config.get("track_topics", True)

        # Plugin state
        self.session_history = {}
        self.topics = {}

    def on_load(self):
        """Called when plugin is loaded."""
        logger.info(
            f"Loading {self.name}: "
            f"max_history={self.max_history}, "
            f"track_topics={self.track_topics}"
        )

    def on_message(self, message: str, **kwargs) -> Optional[str]:
        """Process incoming message."""
        session_id = kwargs.get("session_id", "default")

        # Initialize session if needed
        if session_id not in self.session_history:
            self.session_history[session_id] = []
            self.topics[session_id] = []

        # Add to history
        self.session_history[session_id].append({
            "type": "message",
            "content": message,
            "user_id": kwargs.get("user_id", "unknown"),
        })

        # Keep history under max size
        if len(self.session_history[session_id]) > self.max_history:
            self.session_history[session_id] = self.session_history[session_id][-self.max_history:]

        # Detect topics if enabled
        if self.track_topics:
            self._detect_topics(message, session_id)

        # Don't modify message (return None)
        return None

    def on_response(self, response: str, **kwargs) -> Optional[str]:
        """Process outgoing response."""
        session_id = kwargs.get("session_id", "default")

        # Add response to history
        if session_id in self.session_history:
            self.session_history[session_id].append({
                "type": "response",
                "content": response,
            })

        # Don't modify response
        return None

    def _detect_topics(self, message: str, session_id: str) -> None:
        """Simple topic detection based on keywords."""
        keywords = {
            "weather": ["weather", "rain", "temperature", "sunny"],
            "sports": ["game", "score", "team", "player", "match"],
            "technology": ["code", "software", "python", "api", "database"],
            "health": ["health", "doctor", "medicine", "symptoms", "exercise"],
        }

        message_lower = message.lower()
        for topic, words in keywords.items():
            if any(word in message_lower for word in words):
                if topic not in self.topics[session_id]:
                    self.topics[session_id].append(topic)
                    logger.info(f"Detected topic '{topic}' in session {session_id}")

    def get_session_info(self, session_id: str) -> dict:
        """Get information about a session."""
        if session_id not in self.session_history:
            return {}

        return {
            "session_id": session_id,
            "message_count": len(self.session_history[session_id]),
            "topics": self.topics.get(session_id, []),
            "history": self.session_history[session_id],
        }

    def clear_session(self, session_id: str) -> None:
        """Clear session history."""
        if session_id in self.session_history:
            del self.session_history[session_id]
            del self.topics[session_id]
            logger.info(f"Cleared session {session_id}")

    def on_unload(self):
        """Called when plugin is unloaded."""
        session_count = len(self.session_history)
        logger.info(f"Unloading {self.name}: tracked {session_count} sessions")


# Alternative example: Translation Plugin

class SimpleTranslationPlugin(Plugin):
    """
    Example translation plugin.
    
    Simulates translating messages to a target language.
    In real use, would integrate with a translation API.
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """Initialize plugin."""
        if config is None:
            config = PluginConfig(
                name="SimpleTranslationPlugin",
                description="Example translation plugin",
                config={
                    "target_language": "es",  # Spanish
                    "enabled_for_users": ["user1", "user2"],
                }
            )
        super().__init__(config)

        self.target_language = self.config.config.get("target_language", "es")
        self.enabled_for_users = self.config.config.get("enabled_for_users", [])

    def on_message(self, message: str, **kwargs) -> Optional[str]:
        """Translate message for enabled users."""
        user_id = kwargs.get("user_id", "unknown")

        # Only translate for enabled users
        if self.enabled_for_users and user_id not in self.enabled_for_users:
            return None

        # In real implementation, call translation API
        translated = self._simulate_translate(message)
        logger.info(f"Translated message for user {user_id}")
        return translated

    def _simulate_translate(self, text: str) -> str:
        """Simulate translation (for demo only)."""
        # This is just a demo - in real use, call translation API
        # Example: Google Translate, AWS Translate, etc.
        return f"[Translated to {self.target_language}] {text}"

    def on_unload(self):
        """Called when plugin is unloaded."""
        logger.info(f"Unloading {self.name}")


if __name__ == "__main__":
    # Example usage
    from agentic_brain.plugins import PluginManager

    # Create manager
    manager = PluginManager()

    # Load custom plugin
    manager.load_plugin(MyCustomPlugin)

    # Simulate usage
    manager.trigger(
        "on_message",
        "What's the weather like?",
        session_id="session1",
        user_id="user1"
    )

    manager.trigger(
        "on_response",
        "The weather is sunny.",
        session_id="session1"
    )

    # Get session info
    plugin = manager.get_plugin("MyCustomPlugin")
    info = plugin.get_session_info("session1")
    print(f"Session info: {info}")

    # Cleanup
    manager.unload_all_plugins()
