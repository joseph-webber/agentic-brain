"""Content moderation plugin for Agentic Brain."""

import logging
import re
from typing import Optional, List, Dict, Tuple
from agentic_brain.plugins.base import Plugin, PluginConfig

logger = logging.getLogger(__name__)


class ModerationPlugin(Plugin):
    """
    Content filtering and moderation plugin.

    Provides content filtering based on:
    - Keyword blacklists
    - Pattern matching (regex)
    - Message length limits
    - Rate limiting per user

    Configuration:
        enabled_filters: List of filters to enable (keyword, pattern, length, rate_limit)
        keywords: List of forbidden keywords
        patterns: List of forbidden regex patterns
        max_message_length: Maximum message length (default: 10000)
        rate_limit_messages: Max messages per minute per user (default: 60)
        action: What to do with filtered content: 'block', 'warn', 'log' (default: 'log')

    Example config (plugins.yaml):
        plugins:
          ModerationPlugin:
            enabled: true
            config:
              enabled_filters: [keyword, pattern, length, rate_limit]
              keywords: [badword1, badword2]
              patterns:
                - '(spam|evil)'
              max_message_length: 10000
              rate_limit_messages: 60
              action: log
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """Initialize moderation plugin."""
        if config is None:
            config = PluginConfig(
                name="ModerationPlugin",
                description="Content filtering and moderation",
            )
        super().__init__(config)

        # Parse config
        self.enabled_filters = self.config.config.get("enabled_filters", ["keyword", "pattern", "length"])
        self.keywords = self.config.config.get("keywords", [])
        self.patterns = self._compile_patterns(self.config.config.get("patterns", []))
        self.max_message_length = self.config.config.get("max_message_length", 10000)
        self.rate_limit_messages = self.config.config.get("rate_limit_messages", 60)
        self.rate_limit_window = self.config.config.get("rate_limit_window", 60)  # seconds
        self.action = self.config.config.get("action", "log")

        # Runtime state - track (count, window_start_time) per user for proper rate limiting
        self.user_message_count: Dict[str, Tuple[int, float]] = {}
        self.violations: Dict[str, int] = {}

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        logger.info(
            f"ModerationPlugin loaded: "
            f"keywords={len(self.keywords)}, "
            f"patterns={len(self.patterns)}, "
            f"filters={self.enabled_filters}"
        )

    def _compile_patterns(self, patterns: List[str]) -> List:
        """Compile regex patterns."""
        compiled = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except Exception as e:
                logger.error(f"Error compiling pattern {pattern}: {e}")
        return compiled

    def _check_keywords(self, message: str) -> Optional[str]:
        """Check message against keyword blacklist."""
        if "keyword" not in self.enabled_filters:
            return None

        message_lower = message.lower()
        for keyword in self.keywords:
            if keyword.lower() in message_lower:
                return f"Keyword filter triggered: {keyword}"

        return None

    def _check_patterns(self, message: str) -> Optional[str]:
        """Check message against regex patterns."""
        if "pattern" not in self.enabled_filters:
            return None

        for pattern in self.patterns:
            if pattern.search(message):
                return f"Pattern filter triggered: {pattern.pattern}"

        return None

    def _check_length(self, message: str) -> Optional[str]:
        """Check message length."""
        if "length" not in self.enabled_filters:
            return None

        if len(message) > self.max_message_length:
            return f"Message too long: {len(message)} > {self.max_message_length}"

        return None

    def _check_rate_limit(self, user_id: str) -> Optional[str]:
        """Check user rate limit with time-window based limiting."""
        if "rate_limit" not in self.enabled_filters:
            return None

        import time
        current_time = time.time()
        
        if user_id in self.user_message_count:
            count, window_start = self.user_message_count[user_id]
            
            # Check if window has expired - reset if so
            if current_time - window_start > self.rate_limit_window:
                self.user_message_count[user_id] = (1, current_time)
                return None
            
            # Check if limit exceeded
            if count >= self.rate_limit_messages:
                return f"Rate limit exceeded: {count} messages in {self.rate_limit_window}s"
            
            # Increment counter within window
            self.user_message_count[user_id] = (count + 1, window_start)
        else:
            # First message from this user
            self.user_message_count[user_id] = (1, current_time)

        return None

    def _handle_violation(self, user_id: str, violation: str) -> None:
        """Handle a moderation violation."""
        # Track violations
        self.violations[user_id] = self.violations.get(user_id, 0) + 1

        if self.action == "log":
            logger.warning(f"Moderation violation from {user_id}: {violation}")
        elif self.action == "warn":
            logger.warning(f"Moderation warning for {user_id}: {violation}")
        elif self.action == "block":
            logger.error(f"Moderation block for {user_id}: {violation}")

    def on_message(self, message: str, **kwargs) -> Optional[str]:
        """Check and filter message."""
        user_id = kwargs.get("user_id", "unknown")

        # Run all checks
        checks = [
            self._check_keywords(message),
            self._check_patterns(message),
            self._check_length(message),
            self._check_rate_limit(user_id),
        ]

        violations = [v for v in checks if v is not None]

        if violations:
            for violation in violations:
                self._handle_violation(user_id, violation)

            # Return message based on action
            if self.action == "block":
                return None  # Block message
            # For 'warn' and 'log', pass through unchanged

        return None

    def get_violations(self) -> Dict[str, int]:
        """Get violation statistics."""
        return dict(self.violations)

    def reset_violations(self) -> None:
        """Reset violation statistics."""
        self.violations.clear()
        self.user_message_count.clear()
        logger.info("Moderation violations and rate limits reset")

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        total_violations = sum(self.violations.values())
        logger.info(f"ModerationPlugin unloaded: total violations={total_violations}")
