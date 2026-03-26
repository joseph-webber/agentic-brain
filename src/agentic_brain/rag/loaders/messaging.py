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

"""Messaging platform loaders for RAG pipelines.

Supports:
- Discord (server messages)
- Telegram (chat history)
- Microsoft Teams (chat messages)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

# Check for Discord
try:
    import discord

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

# Check for Telegram
try:
    from telegram import Bot

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

# Check for Teams (via Microsoft Graph)
try:
    import requests

    TEAMS_AVAILABLE = True
except ImportError:
    TEAMS_AVAILABLE = False


class DiscordLoader(BaseLoader):
    """Load Discord messages from servers and channels.

    Example:
        loader = DiscordLoader(
            bot_token="your-token"
        )
        docs = loader.load_folder("channel-id")
    """

    def __init__(self, bot_token: Optional[str] = None):
        """Initialize Discord loader.

        Args:
            bot_token: Discord bot token
        """
        if not DISCORD_AVAILABLE:
            raise ImportError(
                "discord.py package is required. Install with: pip install discord.py"
            )

        self.bot_token = bot_token or os.environ.get("DISCORD_BOT_TOKEN", "")
        self._client = None

    def source_name(self) -> str:
        return "discord"

    def authenticate(self) -> bool:
        """Verify Discord credentials."""
        try:
            self._client = discord.Client(intents=discord.Intents.default())
            logger.info("Discord client initialized")
            return bool(self.bot_token)
        except Exception as e:
            logger.error(f"Failed to initialize Discord client: {e}")
            return False

    def close(self) -> None:
        """Close Discord client."""
        if self._client:
            try:
                # Would need event loop to close properly
                pass
            except Exception as e:
                logger.error(f"Error closing Discord client: {e}")

    @with_rate_limit(requests_per_minute=30)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Discord message.

        Args:
            doc_id: Message ID

        Returns:
            Loaded message document
        """
        # Discord requires async context, this is simplified
        logger.warning("Individual message loading requires async context")
        return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all messages from a Discord channel.

        Args:
            folder_path: Channel ID
            recursive: Unused (messages are not hierarchical)

        Returns:
            List of message documents
        """
        # This would require async event loop
        # Simplified implementation returns empty list
        logger.warning(
            "Discord message loading requires async context. "
            "Use a Discord bot with event loop."
        )
        return []

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Discord messages (requires async context).

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching messages
        """
        logger.warning("Search requires async context")
        return []

    @staticmethod
    def _format_message(message) -> str:
        """Format Discord message as text."""
        lines = [
            f"User: {message.author}",
            f"Time: {message.created_at}",
            f"\n{message.content}",
        ]

        if message.attachments:
            lines.append("\nAttachments:")
            for att in message.attachments:
                lines.append(f"  - {att.filename}")

        return "\n".join(lines)


class TelegramLoader(BaseLoader):
    """Load Telegram chat history.

    Example:
        loader = TelegramLoader(
            bot_token="your-token"
        )
        docs = loader.load_folder("chat-id")
    """

    def __init__(self, bot_token: Optional[str] = None):
        """Initialize Telegram loader.

        Args:
            bot_token: Telegram bot token
        """
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot package is required. "
                "Install with: pip install python-telegram-bot"
            )

        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._bot = None

    def source_name(self) -> str:
        return "telegram"

    def authenticate(self) -> bool:
        """Initialize Telegram bot."""
        try:
            self._bot = Bot(token=self.bot_token)
            logger.info("Telegram bot initialized")
            return bool(self.bot_token)
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            return False

    @with_rate_limit(requests_per_minute=30)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Telegram message.

        Args:
            doc_id: Message ID

        Returns:
            Loaded message document
        """
        # Telegram API doesn't support direct message lookup
        logger.warning("Individual message lookup not supported by Telegram API")
        return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load chat history from Telegram.

        Args:
            folder_path: Chat ID
            recursive: Unused

        Returns:
            List of message documents
        """
        # Telegram requires async context for message history
        logger.warning(
            "Telegram message loading requires async context. "
            "Consider using a backup/export file instead."
        )
        return []

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Telegram messages.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching messages
        """
        logger.warning("Search requires async context")
        return []

    @staticmethod
    def _format_message(message) -> str:
        """Format Telegram message as text."""
        lines = [
            f"User: {message.from_user.first_name}",
            f"Time: {message.date}",
            f"\n{message.text or '[No text content]'}",
        ]

        if message.photo:
            lines.append("\nPhoto attached")
        if message.document:
            lines.append(f"\nDocument: {message.document.file_name}")

        return "\n".join(lines)


class TeamsLoader(BaseLoader):
    """Load Microsoft Teams messages and conversations.

    Note: Different from M365Loader. This loads Teams-specific messages.

    Example:
        loader = TeamsLoader(
            tenant_id="your-tenant-id",
            client_id="your-client-id",
            client_secret="your-secret"
        )
        docs = loader.load_folder("team-id")
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Initialize Teams loader.

        Args:
            tenant_id: Azure tenant ID
            client_id: Azure application ID
            client_secret: Azure application secret
        """
        self.tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID", "")
        self.client_id = client_id or os.environ.get("AZURE_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("AZURE_CLIENT_SECRET", "")
        self._access_token = None
        self._session = None

    def source_name(self) -> str:
        return "teams"

    def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph API."""
        if not TEAMS_AVAILABLE:
            logger.error("requests library required")
            return False

        try:
            import requests

            url = (
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            )
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }

            resp = requests.post(url, data=data, timeout=10)
            resp.raise_for_status()

            token_data = resp.json()
            self._access_token = token_data.get("access_token")

            self._session = requests.Session()
            self._session.headers.update(
                {"Authorization": f"Bearer {self._access_token}"}
            )

            logger.info("Authenticated with Microsoft Graph API")
            return True
        except Exception as e:
            logger.error(f"Failed to authenticate with Teams: {e}")
            return False

    def close(self) -> None:
        """Close Teams session."""
        if self._session:
            self._session.close()

    @with_rate_limit(requests_per_minute=30)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Teams message.

        Args:
            doc_id: Message ID

        Returns:
            Loaded message document
        """
        if not self._session:
            return None

        try:
            # This would require knowing the channel/team context
            # Simplified implementation
            logger.warning("Individual message loading requires channel context")
            return None
        except Exception as e:
            logger.error(f"Error loading Teams message: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all messages from a Teams channel.

        Args:
            folder_path: Channel ID (format: "team-id/channel-id")
            recursive: Whether to load from sub-channels

        Returns:
            List of message documents
        """
        if not self._session:
            return []

        documents = []
        try:
            # Parse team-id and channel-id
            parts = folder_path.split("/")
            if len(parts) != 2:
                logger.error("folder_path should be 'team-id/channel-id'")
                return []

            team_id, channel_id = parts

            # Get messages from channel
            url = (
                f"https://graph.microsoft.com/v1.0/teams/{team_id}/"
                f"channels/{channel_id}/messages"
            )

            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()

            messages = resp.json().get("value", [])

            for msg in messages:
                content = self._format_message(msg)

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        "id": msg.get("id"),
                        "from": msg.get("from", {}).get("user", {}).get("displayName"),
                        "created_at": msg.get("createdDateTime"),
                    },
                    source="teams",
                    source_id=msg.get("id"),
                    filename=f"message_{msg.get('id')}",
                    mime_type="text/plain",
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Teams messages")
        except Exception as e:
            logger.error(f"Error loading Teams channel: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Teams messages (limited by API).

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching messages
        """
        if not self._session:
            return []

        documents = []
        try:
            # Microsoft Graph doesn't have built-in message search
            # Would need to search through all teams/channels
            logger.warning("Full-text search not supported by Teams API")
        except Exception as e:
            logger.error(f"Error searching Teams: {e}")

        return documents

    @staticmethod
    def _format_message(msg: dict[str, Any]) -> str:
        """Format Teams message as text."""
        sender = msg.get("from", {}).get("user", {}).get("displayName", "Unknown")
        timestamp = msg.get("createdDateTime", "")
        content = msg.get("body", {}).get("content", "")

        lines = [
            f"User: {sender}",
            f"Time: {timestamp}",
            f"\n{content}",
        ]

        if msg.get("attachments"):
            lines.append("\nAttachments:")
            for att in msg["attachments"]:
                lines.append(f"  - {att.get('name', 'attachment')}")

        return "\n".join(lines)


__all__ = [
    "DiscordLoader",
    "TelegramLoader",
    "TeamsLoader",
    "DISCORD_AVAILABLE",
    "TELEGRAM_AVAILABLE",
    "TEAMS_AVAILABLE",
]
