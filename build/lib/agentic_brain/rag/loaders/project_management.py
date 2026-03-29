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

"""Project management loaders for RAG pipelines.

Supports:
- Jira (issues, comments, attachments)
- Asana (tasks and projects)
- Linear (issues and cycles)
- Trello (boards and cards)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

# Check for Jira
try:
    from jira import JIRA

    JIRA_AVAILABLE = True
except ImportError:
    JIRA_AVAILABLE = False

# Check for Asana
try:
    import asana

    ASANA_AVAILABLE = True
except ImportError:
    ASANA_AVAILABLE = False

# Check for Linear
try:
    from linear import Client as LinearClient

    LINEAR_AVAILABLE = True
except ImportError:
    LINEAR_AVAILABLE = False


class JiraLoader(BaseLoader):
    """Load Jira issues, comments, and attachments.

    Example:
        loader = JiraLoader(
            server="https://jira.company.com",
            username="user@company.com",
            api_token="your-token"
        )
        docs = loader.load_folder("PROJECT-1")
    """

    def __init__(
        self,
        server: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        project_key: Optional[str] = None,
        url: Optional[str] = None,
        email: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """Initialize Jira loader.

        Args:
            server: Jira server URL
            username: Username or email
            api_token: API token
            project_key: Default project key
            url: Alias for server
            email: Alias for username
            token: Alias for api_token
        """
        if not JIRA_AVAILABLE:
            raise ImportError(
                "jira package is required. Install with: pip install jira"
            )

        self.server = server or url or os.environ.get("JIRA_SERVER", "")
        self.username = username or email or os.environ.get("JIRA_USERNAME", "")
        self.api_token = api_token or token or os.environ.get("JIRA_API_TOKEN", "")
        self.project_key = project_key or os.environ.get("JIRA_PROJECT_KEY", "")
        self._jira = None

    @property
    def source_name(self) -> str:
        return "JIRA"

    def authenticate(self) -> bool:
        """Connect to Jira."""
        try:
            from jira import JIRA

            self._jira = JIRA(
                server=self.server,
                basic_auth=(self.username, self.api_token),
            )
            logger.info(f"Connected to Jira at {self.server}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Jira: {e}")
            return False

    def close(self) -> None:
        """Close Jira connection."""
        if self._jira:
            self._jira.close()

    @with_rate_limit(requests_per_minute=30)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Jira issue.

        Args:
            doc_id: Issue key (e.g., "PROJECT-123")

        Returns:
            Loaded issue document
        """
        if not self._jira:
            return None

        try:
            issue = self._jira.issue(doc_id)

            content = self._format_issue(issue)

            return LoadedDocument(
                content=content,
                metadata={
                    "key": issue.key,
                    "summary": issue.fields.summary,
                    "status": str(issue.fields.status),
                    "priority": str(issue.fields.priority),
                    "assignee": (
                        str(issue.fields.assignee) if issue.fields.assignee else None
                    ),
                    "created": str(issue.fields.created),
                    "updated": str(issue.fields.updated),
                },
                source="jira",
                source_id=issue.key,
                filename=issue.key,
                mime_type="text/plain",
                created_at=datetime.fromisoformat(str(issue.fields.created)),
                modified_at=datetime.fromisoformat(str(issue.fields.updated)),
            )
        except Exception as e:
            logger.error(f"Error loading Jira issue {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all issues from a project.

        Args:
            folder_path: Project key
            recursive: Unused

        Returns:
            List of issue documents
        """
        if not self._jira:
            return []

        documents = []
        project_key = folder_path or self.project_key

        try:
            jql = f"project = {project_key} ORDER BY created DESC"
            issues = self._jira.search_issues(jql, maxResults=False)

            for issue in issues:
                content = self._format_issue(issue)

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        "key": issue.key,
                        "summary": issue.fields.summary,
                        "status": str(issue.fields.status),
                        "priority": str(issue.fields.priority),
                    },
                    source="jira",
                    source_id=issue.key,
                    filename=issue.key,
                    mime_type="text/plain",
                    created_at=datetime.fromisoformat(str(issue.fields.created)),
                    modified_at=datetime.fromisoformat(str(issue.fields.updated)),
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Jira issues from {project_key}")
        except Exception as e:
            logger.error(f"Error loading Jira project {project_key}: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Jira issues.

        Args:
            query: JQL query or text search
            max_results: Maximum results

        Returns:
            Matching issues
        """
        if not self._jira:
            return []

        documents = []
        try:
            # Try as JQL first, fall back to text search
            try:
                issues = self._jira.search_issues(query, maxResults=max_results)
            except Exception:
                jql = f'text ~ "{query}" ORDER BY updated DESC'
                issues = self._jira.search_issues(jql, maxResults=max_results)

            for issue in issues:
                content = self._format_issue(issue)

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        "key": issue.key,
                        "summary": issue.fields.summary,
                    },
                    source="jira",
                    source_id=issue.key,
                    filename=issue.key,
                    mime_type="text/plain",
                )
                documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching Jira: {e}")

        return documents

    @staticmethod
    def _format_issue(issue) -> str:
        """Format Jira issue as text."""
        lines = [
            f"# {issue.key}: {issue.fields.summary}",
            f"\nStatus: {issue.fields.status}",
            f"Priority: {issue.fields.priority}",
        ]

        if issue.fields.description:
            lines.append(f"\nDescription:\n{issue.fields.description}")

        if issue.fields.comment.comments:
            lines.append("\n## Comments")
            for comment in issue.fields.comment.comments:
                lines.append(f"\n{comment.author.displayName} ({comment.created}):")
                lines.append(comment.body)

        return "\n".join(lines)


class AsanaLoader(BaseLoader):
    """Load Asana tasks and projects.

    Example:
        loader = AsanaLoader(
            personal_access_token="your-token"
        )
        docs = loader.load_folder("project-id")
    """

    def __init__(self, personal_access_token: Optional[str] = None):
        """Initialize Asana loader.

        Args:
            personal_access_token: Asana personal access token
        """
        if not ASANA_AVAILABLE:
            raise ImportError(
                "asana package is required. Install with: pip install asana"
            )

        self.token = personal_access_token or os.environ.get("ASANA_TOKEN", "")
        self._client = None

    def source_name(self) -> str:
        return "asana"

    def authenticate(self) -> bool:
        """Connect to Asana API."""
        try:
            self._client = asana.Client.access_token(self.token)
            logger.info("Connected to Asana")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Asana: {e}")
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Asana task.

        Args:
            doc_id: Task ID

        Returns:
            Loaded task document
        """
        if not self._client:
            return None

        try:
            task = self._client.tasks.find_by_id(doc_id)

            content = self._format_task(task)

            return LoadedDocument(
                content=content,
                metadata={
                    "id": task.get("id"),
                    "name": task.get("name"),
                    "completed": task.get("completed"),
                },
                source="asana",
                source_id=task.get("id"),
                filename=task.get("name", "task"),
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading Asana task {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all tasks from a project.

        Args:
            folder_path: Project ID
            recursive: Unused

        Returns:
            List of task documents
        """
        if not self._client:
            return []

        documents = []
        try:
            tasks = self._client.tasks.find_by_project(folder_path)

            for task in tasks:
                content = self._format_task(task)

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        "id": task.get("id"),
                        "name": task.get("name"),
                    },
                    source="asana",
                    source_id=task.get("id"),
                    filename=task.get("name", "task"),
                    mime_type="text/plain",
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Asana tasks")
        except Exception as e:
            logger.error(f"Error loading Asana project: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Asana tasks.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching tasks
        """
        if not self._client:
            return []

        documents = []
        try:
            tasks = self._client.tasks.find_all({"opt_fields": "name,notes"})

            for task in tasks:
                name = task.get("name", "")
                notes = task.get("notes", "")

                if query.lower() in name.lower() or query.lower() in notes.lower():
                    content = self._format_task(task)

                    doc = LoadedDocument(
                        content=content,
                        metadata={"id": task.get("id"), "name": name},
                        source="asana",
                        source_id=task.get("id"),
                        filename=name,
                        mime_type="text/plain",
                    )
                    documents.append(doc)

                    if len(documents) >= max_results:
                        break

        except Exception as e:
            logger.error(f"Error searching Asana: {e}")

        return documents

    @staticmethod
    def _format_task(task: dict[str, Any]) -> str:
        """Format Asana task as text."""
        lines = [f"# {task.get('name', 'Untitled')}"]

        if task.get("notes"):
            lines.append(f"\nNotes:\n{task['notes']}")

        if task.get("assignee"):
            lines.append(f"\nAssignee: {task['assignee'].get('name', 'Unassigned')}")

        if task.get("due_on"):
            lines.append(f"Due: {task['due_on']}")

        lines.append(f"\nCompleted: {'Yes' if task.get('completed') else 'No'}")

        return "\n".join(lines)


class LinearLoader(BaseLoader):
    """Load Linear issues and cycles.

    Example:
        loader = LinearLoader(api_key="your-api-key")
        docs = loader.load_folder("project-key")
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Linear loader.

        Args:
            api_key: Linear API key
        """
        if not LINEAR_AVAILABLE:
            raise ImportError(
                "linear package is required. Install with: pip install linear"
            )

        self.api_key = api_key or os.environ.get("LINEAR_API_KEY", "")
        self._client = None

    def source_name(self) -> str:
        return "linear"

    def authenticate(self) -> bool:
        """Connect to Linear API."""
        try:
            self._client = LinearClient(api_key=self.api_key)
            logger.info("Connected to Linear")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Linear: {e}")
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Linear issue.

        Args:
            doc_id: Issue ID or key

        Returns:
            Loaded issue document
        """
        if not self._client:
            return None

        try:
            # Try to get issue by ID or key
            issue = self._client.issue(doc_id)

            content = self._format_issue(issue)

            return LoadedDocument(
                content=content,
                metadata={
                    "id": getattr(issue, "id", ""),
                    "identifier": getattr(issue, "identifier", ""),
                    "title": getattr(issue, "title", ""),
                    "state": str(getattr(issue, "state", "")),
                },
                source="linear",
                source_id=doc_id,
                filename=getattr(issue, "identifier", doc_id),
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading Linear issue {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all issues.

        Args:
            folder_path: Project key or unused
            recursive: Unused

        Returns:
            List of issue documents
        """
        if not self._client:
            return []

        documents = []
        try:
            # Get all issues
            issues = self._client.issues()

            for issue in issues:
                content = self._format_issue(issue)

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        "id": getattr(issue, "id", ""),
                        "identifier": getattr(issue, "identifier", ""),
                        "title": getattr(issue, "title", ""),
                    },
                    source="linear",
                    source_id=getattr(issue, "id", ""),
                    filename=getattr(issue, "identifier", "issue"),
                    mime_type="text/plain",
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Linear issues")
        except Exception as e:
            logger.error(f"Error loading Linear issues: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Linear issues.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching issues
        """
        if not self._client:
            return []

        documents = []
        try:
            issues = self._client.issues(filter={"search": query})

            for issue in issues:
                if len(documents) >= max_results:
                    break

                content = self._format_issue(issue)

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        "id": getattr(issue, "id", ""),
                        "identifier": getattr(issue, "identifier", ""),
                        "title": getattr(issue, "title", ""),
                    },
                    source="linear",
                    source_id=getattr(issue, "id", ""),
                    filename=getattr(issue, "identifier", "issue"),
                    mime_type="text/plain",
                )
                documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching Linear: {e}")

        return documents

    @staticmethod
    def _format_issue(issue) -> str:
        """Format Linear issue as text."""
        identifier = getattr(issue, "identifier", "?")
        title = getattr(issue, "title", "Untitled")
        description = getattr(issue, "description", "")
        state = getattr(issue, "state", "Unknown")

        lines = [f"# {identifier}: {title}"]
        lines.append(f"\nState: {state}")

        if description:
            lines.append(f"\nDescription:\n{description}")

        return "\n".join(lines)


class TrelloLoader(BaseLoader):
    """Load Trello boards and cards.

    Example:
        loader = TrelloLoader(
            api_key="your-key",
            api_token="your-token"
        )
        docs = loader.load_folder("board-id")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """Initialize Trello loader.

        Args:
            api_key: Trello API key
            api_token: Trello API token
        """
        self.api_key = api_key or os.environ.get("TRELLO_API_KEY", "")
        self.api_token = api_token or os.environ.get("TRELLO_API_TOKEN", "")

        # For requests
        try:
            import requests

            self._requests = requests
        except ImportError:
            self._requests = None

    def source_name(self) -> str:
        return "trello"

    def authenticate(self) -> bool:
        """Verify Trello credentials."""
        if not self._requests:
            logger.error("requests library required for Trello")
            return False

        try:
            url = "https://api.trello.com/1/members/me"
            resp = self._requests.get(
                url,
                params={"key": self.api_key, "token": self.api_token},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Connected to Trello")
            return True
        except Exception as e:
            logger.error(f"Failed to authenticate with Trello: {e}")
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Trello card.

        Args:
            doc_id: Card ID

        Returns:
            Loaded card document
        """
        if not self._requests:
            return None

        try:
            url = f"https://api.trello.com/1/cards/{doc_id}"
            resp = self._requests.get(
                url,
                params={"key": self.api_key, "token": self.api_token},
                timeout=10,
            )
            resp.raise_for_status()

            card = resp.json()
            content = self._format_card(card)

            return LoadedDocument(
                content=content,
                metadata={
                    "id": card.get("id"),
                    "name": card.get("name"),
                    "status": "closed" if card.get("closed") else "open",
                },
                source="trello",
                source_id=card.get("id"),
                filename=card.get("name", "card"),
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading Trello card {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all cards from a Trello board.

        Args:
            folder_path: Board ID
            recursive: Unused

        Returns:
            List of card documents
        """
        if not self._requests:
            return []

        documents = []
        try:
            url = f"https://api.trello.com/1/boards/{folder_path}/cards"
            resp = self._requests.get(
                url,
                params={"key": self.api_key, "token": self.api_token},
                timeout=10,
            )
            resp.raise_for_status()

            cards = resp.json()
            for card in cards:
                content = self._format_card(card)

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        "id": card.get("id"),
                        "name": card.get("name"),
                    },
                    source="trello",
                    source_id=card.get("id"),
                    filename=card.get("name", "card"),
                    mime_type="text/plain",
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Trello cards")
        except Exception as e:
            logger.error(f"Error loading Trello board: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Trello cards.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching cards
        """
        if not self._requests:
            return []

        documents = []
        try:
            # Would need to search across boards/lists
            # For now, return empty (requires more complex implementation)
            logger.warning("Trello search not fully implemented")
        except Exception as e:
            logger.error(f"Error searching Trello: {e}")

        return documents

    @staticmethod
    def _format_card(card: dict[str, Any]) -> str:
        """Format Trello card as text."""
        lines = [f"# {card.get('name', 'Untitled')}"]

        if card.get("desc"):
            lines.append(f"\nDescription:\n{card['desc']}")

        if card.get("labels"):
            labels = ", ".join(l.get("name", "") for l in card["labels"])
            lines.append(f"\nLabels: {labels}")

        lines.append(f"\nStatus: {'Closed' if card.get('closed') else 'Open'}")

        return "\n".join(lines)


__all__ = [
    "JiraLoader",
    "AsanaLoader",
    "LinearLoader",
    "TrelloLoader",
    "JIRA_AVAILABLE",
    "ASANA_AVAILABLE",
    "LINEAR_AVAILABLE",
]
