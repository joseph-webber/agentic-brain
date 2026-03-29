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

"""LLM conversation history loaders for RAG pipelines.

Supports:
- Generic LLM conversation history
- OpenAI conversation exports
- Claude conversation exports
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class LLMConversationLoader(BaseLoader):
    """Load chat history from LLM interactions and conversations.

    Converts conversation turns into documents for context augmentation.

    Example:
        loader = LLMConversationLoader(
            conversations_dir="./chats"
        )
        docs = loader.load_folder("conversations")
    """

    def __init__(self, conversations_dir: Optional[str] = None):
        """Initialize LLM conversation loader.

        Args:
            conversations_dir: Directory containing conversation files
        """
        self.conversations_dir = conversations_dir or os.environ.get(
            "LLM_CONVERSATIONS_DIR", "./conversations"
        )

    @property
    def source_name(self) -> str:
        return "llm_conversations"

    def authenticate(self) -> bool:
        """Verify conversations directory exists."""
        if not os.path.isdir(self.conversations_dir):
            logger.warning(
                f"Conversations directory not found: {self.conversations_dir}"
            )
            return False
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID.

        Load a single conversation file for the given document identifier.

        Args:
            doc_id: Filename of conversation

        Returns:
            Loaded conversation document or None
        """
        # Fetch specific item by ID
        try:
            filepath = os.path.join(self.conversations_dir, doc_id)
            if not os.path.exists(filepath):
                return None

            with open(filepath, encoding="utf-8") as f:
                if filepath.endswith(".json"):
                    data = json.load(f)
                else:
                    data = {"content": f.read()}

            content = self._format_conversation(data)

            return LoadedDocument(
                content=content,
                metadata=self._extract_metadata(data),
                source="llm_conversations",
                source_id=doc_id,
                filename=doc_id,
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading conversation {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all conversation files from directory.

        Args:
            folder_path: Subdirectory within conversations_dir
            recursive: Whether to search subdirectories

        Returns:
            List of conversation documents
        """
        documents = []
        target_dir = os.path.join(self.conversations_dir, folder_path)

        try:
            if not os.path.isdir(target_dir):
                target_dir = self.conversations_dir

            for root, dirs, files in os.walk(target_dir):
                if not recursive:
                    dirs.clear()

                for filename in files:
                    if filename.endswith((".json", ".txt", ".md")):
                        filepath = os.path.join(root, filename)
                        doc = self.load_document(
                            os.path.relpath(filepath, self.conversations_dir)
                        )
                        if doc:
                            documents.append(doc)

            logger.info(f"Loaded {len(documents)} conversations from {target_dir}")
        except Exception as e:
            logger.error(f"Error loading conversations from {target_dir}: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search conversations by content.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            List of matching documents
        """
        documents = self.load_folder(".", recursive=True)
        matches = []

        for doc in documents:
            if query.lower() in doc.content.lower():
                matches.append(doc)
                if len(matches) >= max_results:
                    break

        return matches

    @staticmethod
    def _format_conversation(data: dict[str, Any]) -> str:
        """Format conversation data as readable text."""
        if isinstance(data, dict):
            if "messages" in data:
                # OpenAI/Claude format
                lines = []
                for msg in data["messages"]:
                    role = msg.get("role", "unknown").upper()
                    content = msg.get("content", "")
                    lines.append(f"{role}: {content}")
                return "\n\n".join(lines)
            elif "conversations" in data:
                # Nested conversations
                lines = []
                for conv in data["conversations"]:
                    lines.append(conv.get("content", str(conv)))
                return "\n\n".join(lines)
            elif "content" in data:
                return data["content"]
        return str(data)

    @staticmethod
    def _extract_metadata(data: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from conversation data."""
        metadata = {}

        if isinstance(data, dict):
            if "created_at" in data:
                metadata["created_at"] = str(data["created_at"])
            if "updated_at" in data:
                metadata["updated_at"] = str(data["updated_at"])
            if "title" in data:
                metadata["title"] = data["title"]
            if "model" in data:
                metadata["model"] = data["model"]
            if "messages" in data:
                metadata["message_count"] = len(data["messages"])

        return metadata


class OpenAIHistoryLoader(BaseLoader):
    """Load chat history from OpenAI conversation exports (JSON).

    OpenAI provides conversation export in JSON format with messages array.

    Example:
        loader = OpenAIHistoryLoader(
            export_dir="./openai_exports"
        )
        docs = loader.load_folder("chats")
    """

    def __init__(self, export_dir: Optional[str] = None):
        """Initialize OpenAI history loader.

        Args:
            export_dir: Directory containing OpenAI exports
        """
        self.export_dir = export_dir or os.environ.get(
            "OPENAI_EXPORT_DIR", "./openai_exports"
        )

    @property
    def source_name(self) -> str:
        return "openai_history"

    def authenticate(self) -> bool:
        """Verify export directory exists."""
        if not os.path.isdir(self.export_dir):
            logger.warning(f"Export directory not found: {self.export_dir}")
            return False
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID.

        Load a single OpenAI conversation JSON export.

        Args:
            doc_id: Filename of conversation

        Returns:
            Loaded conversation document
        """
        # Fetch specific item by ID
        try:
            filepath = os.path.join(self.export_dir, doc_id)
            if not os.path.exists(filepath):
                return None

            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            # OpenAI format typically has 'messages' array
            title = data.get("title", "Untitled")
            messages = data.get("messages", [])

            lines = [f"# Conversation: {title}\n"]
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "")

                if timestamp:
                    lines.append(f"[{timestamp}] {role}: {content}")
                else:
                    lines.append(f"{role}: {content}")

            content = "\n\n".join(lines)

            return LoadedDocument(
                content=content,
                metadata={
                    "title": title,
                    "message_count": len(messages),
                    "created_at": data.get("created_at"),
                    "model": data.get("model", "unknown"),
                },
                source="openai_history",
                source_id=doc_id,
                filename=doc_id,
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading OpenAI conversation {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all OpenAI JSON exports.

        Args:
            folder_path: Subdirectory
            recursive: Search subdirectories

        Returns:
            List of conversation documents
        """
        documents = []
        target_dir = os.path.join(self.export_dir, folder_path)

        try:
            if not os.path.isdir(target_dir):
                target_dir = self.export_dir

            for root, dirs, files in os.walk(target_dir):
                if not recursive:
                    dirs.clear()

                for filename in files:
                    if filename.endswith(".json"):
                        filepath = os.path.join(root, filename)
                        doc = self.load_document(
                            os.path.relpath(filepath, self.export_dir)
                        )
                        if doc:
                            documents.append(doc)

            logger.info(f"Loaded {len(documents)} OpenAI conversations")
        except Exception as e:
            logger.error(f"Error loading OpenAI exports: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search conversations by content.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching conversations
        """
        documents = self.load_folder(".", recursive=True)
        matches = []

        for doc in documents:
            if query.lower() in doc.content.lower():
                matches.append(doc)
                if len(matches) >= max_results:
                    break

        return matches


class ClaudeHistoryLoader(BaseLoader):
    """Load chat history from Claude conversation exports.

    Claude provides conversation exports in JSON format.

    Example:
        loader = ClaudeHistoryLoader(
            export_dir="./claude_exports"
        )
        docs = loader.load_folder("conversations")
    """

    def __init__(self, export_dir: Optional[str] = None):
        """Initialize Claude history loader.

        Args:
            export_dir: Directory containing Claude exports
        """
        self.export_dir = export_dir or os.environ.get(
            "CLAUDE_EXPORT_DIR", "./claude_exports"
        )

    @property
    def source_name(self) -> str:
        return "claude_history"

    def authenticate(self) -> bool:
        """Verify export directory exists."""
        if not os.path.isdir(self.export_dir):
            logger.warning(f"Export directory not found: {self.export_dir}")
            return False
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID.

        Load a single Claude conversation export.

        Args:
            doc_id: Filename of conversation

        Returns:
            Loaded conversation document
        """
        # Fetch specific item by ID
        try:
            filepath = os.path.join(self.export_dir, doc_id)
            if not os.path.exists(filepath):
                return None

            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            # Claude format
            title = data.get("title", "Untitled")
            messages = data.get("messages", [])
            if not messages and "conversations" in data:
                messages = data["conversations"]

            lines = [f"# Claude Conversation: {title}\n"]

            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown").upper()
                    content = msg.get("content", "")
                    lines.append(f"{role}: {content}")
                else:
                    lines.append(str(msg))

            content = "\n\n".join(lines)

            return LoadedDocument(
                content=content,
                metadata={
                    "title": title,
                    "message_count": len(messages),
                    "created_at": data.get("created_at"),
                    "model": data.get("model", "claude"),
                },
                source="claude_history",
                source_id=doc_id,
                filename=doc_id,
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading Claude conversation {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all Claude conversation exports.

        Args:
            folder_path: Subdirectory
            recursive: Search subdirectories

        Returns:
            List of conversation documents
        """
        documents = []
        target_dir = os.path.join(self.export_dir, folder_path)

        try:
            if not os.path.isdir(target_dir):
                target_dir = self.export_dir

            for root, dirs, files in os.walk(target_dir):
                if not recursive:
                    dirs.clear()

                for filename in files:
                    if filename.endswith(".json"):
                        filepath = os.path.join(root, filename)
                        doc = self.load_document(
                            os.path.relpath(filepath, self.export_dir)
                        )
                        if doc:
                            documents.append(doc)

            logger.info(f"Loaded {len(documents)} Claude conversations")
        except Exception as e:
            logger.error(f"Error loading Claude exports: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search conversations by content.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching conversations
        """
        documents = self.load_folder(".", recursive=True)
        matches = []

        for doc in documents:
            if query.lower() in doc.content.lower():
                matches.append(doc)
                if len(matches) >= max_results:
                    break

        return matches


__all__ = [
    "LLMConversationLoader",
    "OpenAIHistoryLoader",
    "ClaudeHistoryLoader",
]
