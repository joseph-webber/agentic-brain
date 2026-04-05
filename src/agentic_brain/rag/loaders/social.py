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

"""Social platform loaders for RAG pipelines.

Supports:
- Slack
- Notion
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for Slack SDK
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

# Check for Notion SDK
try:
    from notion_client import Client as NotionClient

    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False


class SlackLoader(BaseLoader):
    """Load messages from Slack channels.

    Example:
        loader = SlackLoader(token="xoxb-your-token")
        docs = loader.load_channel("general", limit=100)
        docs = loader.search("project update")
    """

    def __init__(
        self,
        token: Optional[str] = None,
        include_replies: bool = True,
        max_messages: int = 1000,
    ):
        if not SLACK_AVAILABLE:
            raise ImportError("slack-sdk not installed. Run: pip install slack-sdk")

        self.token = token or os.environ.get("SLACK_BOT_TOKEN")
        self.include_replies = include_replies
        self.max_messages = max_messages
        self._client: Optional[WebClient] = None
        self._users: dict[str, str] = {}
        self._channels: dict[str, str] = {}

    @property
    def source_name(self) -> str:
        return "slack"

    def authenticate(self) -> bool:
        """Authenticate with Slack API."""
        try:
            self._client = WebClient(token=self.token)
            self._client.auth_test()
            self._load_users()
            self._load_channels()
            logger.info("Slack authentication successful")
            return True
        except SlackApiError as e:
            logger.error(f"Slack authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._client and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Slack")
        assert self._client is not None

    def _load_users(self):
        """Cache user info for name lookups."""
        try:
            response = self._client.users_list()
            for user in response.get("members", []):
                self._users[user["id"]] = user.get("profile", {}).get(
                    "real_name", user.get("name", "Unknown")
                )
        except SlackApiError:
            pass

    def _load_channels(self):
        """Cache channel info."""
        try:
            response = self._client.conversations_list(
                types="public_channel,private_channel"
            )
            for ch in response.get("channels", []):
                self._channels[ch["id"]] = ch["name"]
        except SlackApiError:
            pass

    def _get_username(self, user_id: str) -> str:
        return self._users.get(user_id, user_id)

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single message by channel:timestamp."""
        self._ensure_authenticated()
        try:
            channel_id, ts = doc_id.split(":", 1)
            response = self._client.conversations_history(
                channel=channel_id, latest=ts, inclusive=True, limit=1
            )
            messages = response.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            user = self._get_username(msg.get("user", ""))
            content = f"[{user}]: {msg.get('text', '')}"

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"slack_{channel_id}_{ts}.txt",
                created_at=datetime.fromtimestamp(float(ts)),
                metadata={
                    "channel": self._channels.get(channel_id, channel_id),
                    "user": user,
                    "timestamp": ts,
                },
            )
        except Exception as e:
            logger.error(f"Failed to load Slack message {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load messages from a channel."""
        return self.load_channel(folder_path)

    def load_channel(self, channel: str, limit: int = 100) -> list[LoadedDocument]:
        """Load messages from a Slack channel."""
        self._ensure_authenticated()
        docs = []

        try:
            # Get channel ID from name if needed
            channel_id = channel
            for cid, name in self._channels.items():
                if name == channel:
                    channel_id = cid
                    break

            response = self._client.conversations_history(
                channel=channel_id, limit=min(limit, self.max_messages)
            )

            for msg in response.get("messages", []):
                user = self._get_username(msg.get("user", ""))
                ts = msg.get("ts", "")
                content = f"[{user}]: {msg.get('text', '')}"

                # Include replies
                if self.include_replies and msg.get("reply_count", 0) > 0:
                    try:
                        replies = self._client.conversations_replies(
                            channel=channel_id, ts=ts
                        )
                        for reply in replies.get("messages", [])[1:]:
                            reply_user = self._get_username(reply.get("user", ""))
                            content += f"\n  [{reply_user}]: {reply.get('text', '')}"
                    except SlackApiError:
                        pass

                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{channel_id}:{ts}",
                        filename=f"slack_{channel}_{ts}.txt",
                        created_at=datetime.fromtimestamp(float(ts)) if ts else None,
                        metadata={
                            "channel": channel,
                            "user": user,
                            "timestamp": ts,
                        },
                    )
                )
        except SlackApiError as e:
            logger.error(f"Failed to load Slack channel {channel}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Slack messages."""
        self._ensure_authenticated()
        docs = []

        try:
            response = self._client.search_messages(query=query, count=max_results)

            for match in response.get("messages", {}).get("matches", []):
                channel = match.get("channel", {})
                channel_name = channel.get("name", channel.get("id", ""))
                user = self._get_username(match.get("user", ""))
                ts = match.get("ts", "")

                docs.append(
                    LoadedDocument(
                        content=f"[{user}]: {match.get('text', '')}",
                        source=self.source_name,
                        source_id=f"{channel.get('id')}:{ts}",
                        filename=f"slack_{channel_name}_{ts}.txt",
                        metadata={
                            "channel": channel_name,
                            "user": user,
                            "permalink": match.get("permalink", ""),
                        },
                    )
                )
        except SlackApiError as e:
            logger.error(f"Slack search failed: {e}")

        return docs


class NotionLoader(BaseLoader):
    """Load pages and databases from Notion.

    Example:
        loader = NotionLoader(token="secret_xxx")
        docs = loader.load_database("database_id")
        docs = loader.search("project docs")
    """

    def __init__(
        self,
        token: Optional[str] = None,
        max_block_depth: int = 3,
    ):
        if not NOTION_AVAILABLE:
            raise ImportError(
                "notion-client not installed. Run: pip install notion-client"
            )

        self.token = token or os.environ.get("NOTION_TOKEN")
        self.max_block_depth = max_block_depth
        self._client = None

    @property
    def source_name(self) -> str:
        return "notion"

    def authenticate(self) -> bool:
        """Authenticate with Notion API."""
        try:
            self._client = NotionClient(auth=self.token)
            self._client.users.me()
            logger.info("Notion authentication successful")
            return True
        except Exception as e:
            logger.error(f"Notion authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._client and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Notion")

    def _extract_text_from_block(self, block: dict) -> str:
        """Extract text content from a Notion block."""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        if "rich_text" in block_data:
            return "".join(
                t.get("plain_text", "") for t in block_data.get("rich_text", [])
            )
        elif "title" in block_data:
            return "".join(t.get("plain_text", "") for t in block_data.get("title", []))

        return ""

    def _get_page_content(self, page_id: str, depth: int = 0) -> str:
        """Get full page content including child blocks."""
        if depth >= self.max_block_depth:
            return ""

        content_parts = []

        try:
            blocks = self._client.blocks.children.list(block_id=page_id)

            for block in blocks.get("results", []):
                text = self._extract_text_from_block(block)
                if text:
                    content_parts.append(text)

                if block.get("has_children", False):
                    child_content = self._get_page_content(block["id"], depth + 1)
                    if child_content:
                        content_parts.append(child_content)
        except Exception as e:
            logger.debug(f"Failed to get page content: {e}")

        return "\n".join(content_parts)

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Notion page."""
        self._ensure_authenticated()

        try:
            page = self._client.pages.retrieve(page_id=doc_id)

            # Get title
            title = ""
            props = page.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    title = "".join(
                        t.get("plain_text", "") for t in prop.get("title", [])
                    )
                    break

            content = self._get_page_content(doc_id)

            return LoadedDocument(
                content=f"# {title}\n\n{content}" if title else content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"{title or 'Untitled'}.md",
                mime_type="text/markdown",
                created_at=(
                    datetime.fromisoformat(
                        page.get("created_time", "").replace("Z", "+00:00")
                    )
                    if page.get("created_time")
                    else None
                ),
                modified_at=(
                    datetime.fromisoformat(
                        page.get("last_edited_time", "").replace("Z", "+00:00")
                    )
                    if page.get("last_edited_time")
                    else None
                ),
                metadata={
                    "title": title,
                    "url": page.get("url", ""),
                },
            )
        except Exception as e:
            logger.error(f"Failed to load Notion page {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load pages from a database."""
        return self.load_database(folder_path)

    def load_database(
        self, database_id: str, filter: Optional[dict] = None
    ) -> list[LoadedDocument]:
        """Load all pages from a Notion database."""
        self._ensure_authenticated()
        docs = []

        try:
            query_params: dict[str, Any] = {"database_id": database_id}
            if filter:
                query_params["filter"] = filter

            response = self._client.databases.query(**query_params)

            for page in response.get("results", []):
                doc = self.load_document(page["id"])
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load Notion database {database_id}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Notion pages."""
        self._ensure_authenticated()
        docs = []

        try:
            response = self._client.search(query=query, page_size=min(max_results, 100))

            for result in response.get("results", []):
                if result.get("object") == "page":
                    doc = self.load_document(result["id"])
                    if doc:
                        docs.append(doc)
        except Exception as e:
            logger.error(f"Notion search failed: {e}")

        return docs


__all__ = [
    "SlackLoader",
    "NotionLoader",
]
