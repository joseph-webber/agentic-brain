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

"""Analytics plugin for Agentic Brain."""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from agentic_brain.plugins.base import Plugin, PluginConfig

logger = logging.getLogger(__name__)


class AnalyticsPlugin(Plugin):
    """
    Tracks usage statistics and analytics.

    Tracks:
    - Message count by session and user
    - Response time statistics
    - Token usage (if provided)
    - Error rates
    - Most common topics

    Configuration:
        track_messages: Whether to track messages (default: True)
        track_responses: Whether to track responses (default: True)
        track_errors: Whether to track errors (default: True)
        buffer_size: Size of analytics buffer before writing (default: 100)

    Example config (plugins.yaml):
        plugins:
          AnalyticsPlugin:
            enabled: true
            config:
              track_messages: true
              track_responses: true
              buffer_size: 100
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """Initialize analytics plugin."""
        if config is None:
            config = PluginConfig(
                name="AnalyticsPlugin",
                description="Tracks usage statistics and analytics",
            )
        super().__init__(config)

        # Parse config
        self.track_messages = self.config.config.get("track_messages", True)
        self.track_responses = self.config.config.get("track_responses", True)
        self.track_errors = self.config.config.get("track_errors", True)
        self.buffer_size = self.config.config.get("buffer_size", 100)

        # Statistics
        self.stats = {
            "message_count": 0,
            "response_count": 0,
            "error_count": 0,
            "total_message_length": 0,
            "total_response_length": 0,
            "sessions": defaultdict(int),
            "users": defaultdict(int),
            "timestamps": [],
        }

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        logger.info("AnalyticsPlugin loaded")

    def on_message(self, message: str, **kwargs) -> Optional[str]:
        """Track message statistics."""
        if not self.track_messages:
            return None

        self.stats["message_count"] += 1
        self.stats["total_message_length"] += len(message)

        if "session_id" in kwargs:
            self.stats["sessions"][kwargs["session_id"]] += 1

        if "user_id" in kwargs:
            self.stats["users"][kwargs["user_id"]] += 1

        # Track last message time instead of unbounded timestamps list (prevents memory leak)
        self.stats["last_message_time"] = datetime.now(timezone.utc).isoformat()

        # Log stats periodically
        if self.stats["message_count"] % self.buffer_size == 0:
            self._log_stats()

        return None

    def on_response(self, response: str, **kwargs) -> Optional[str]:
        """Track response statistics."""
        if not self.track_responses:
            return None

        self.stats["response_count"] += 1
        self.stats["total_response_length"] += len(response)

        return None

    def _log_stats(self) -> None:
        """Log current statistics."""
        avg_msg_len = (
            self.stats["total_message_length"] / self.stats["message_count"]
            if self.stats["message_count"] > 0
            else 0
        )
        avg_resp_len = (
            self.stats["total_response_length"] / self.stats["response_count"]
            if self.stats["response_count"] > 0
            else 0
        )

        logger.info(
            f"Analytics: messages={self.stats['message_count']}, "
            f"responses={self.stats['response_count']}, "
            f"avg_msg_len={avg_msg_len:.1f}, "
            f"avg_resp_len={avg_resp_len:.1f}, "
            f"unique_sessions={len(self.stats['sessions'])}, "
            f"unique_users={len(self.stats['users'])}"
        )

    def get_stats(self) -> dict:
        """Get current statistics."""
        return {
            "message_count": self.stats["message_count"],
            "response_count": self.stats["response_count"],
            "error_count": self.stats["error_count"],
            "avg_message_length": (
                self.stats["total_message_length"] / self.stats["message_count"]
                if self.stats["message_count"] > 0
                else 0
            ),
            "avg_response_length": (
                self.stats["total_response_length"] / self.stats["response_count"]
                if self.stats["response_count"] > 0
                else 0
            ),
            "unique_sessions": len(self.stats["sessions"]),
            "unique_users": len(self.stats["users"]),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            "message_count": 0,
            "response_count": 0,
            "error_count": 0,
            "total_message_length": 0,
            "total_response_length": 0,
            "sessions": defaultdict(int),
            "users": defaultdict(int),
            "timestamps": [],
        }
        logger.info("Analytics stats reset")

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        self._log_stats()
        logger.info("AnalyticsPlugin unloaded")
