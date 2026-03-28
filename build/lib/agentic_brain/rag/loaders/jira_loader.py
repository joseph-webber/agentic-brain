# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""JIRA loader for RAG pipelines."""

import logging
from datetime import datetime
from typing import Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for atlassian-python-api
try:
    from atlassian import Jira

    JIRA_AVAILABLE = True
except ImportError:

    class Jira:  # type: ignore[no-redef]
        """Fallback Jira stub so tests can patch this attribute even offline."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "atlassian-python-api not installed. "
                "Run: pip install atlassian-python-api"
            )

    JIRA_AVAILABLE = False


class JiraLoader(BaseLoader):
    """Load tickets from Atlassian JIRA.

    Supports:
    - Loading single issue by Key
    - Loading JQL search results
    """

    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        token: Optional[str] = None,
        cloud: bool = True,
    ):
        """Initialize JIRA loader.

        Args:
            url: JIRA base URL
            username: Username (email for cloud)
            token: API token or password
            cloud: Whether using Atlassian Cloud (default True)
        """
        self._url = url
        self._username = username
        self._token = token
        self._cloud = cloud
        self._client = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "jira"

    def authenticate(self) -> bool:
        """Authenticate with JIRA API."""
        if not JIRA_AVAILABLE:
            raise ImportError(
                "atlassian-python-api not installed. "
                "Run: pip install atlassian-python-api"
            )

        try:
            self._client = Jira(
                url=self._url,
                username=self._username,
                password=self._token,
                cloud=self._cloud,
            )
            # Test connection (get server info or current user)
            # This might fail if permissions are tight, but usually works
            try:
                self._client.get_project_list()
            except Exception:
                pass  # Ignore project list failure, might just be restricted

            self._authenticated = True
            return True

        except Exception as e:
            logger.error(f"JIRA authentication failed: {e}")
            self._authenticated = False
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single issue by Key (e.g. 'PROJ-123')."""
        if not self._authenticated:
            self.authenticate()

        try:
            issue = self._client.issue(doc_id)

            fields = issue.get("fields", {})
            summary = fields.get("summary", "")
            description = fields.get("description", "") or ""

            # Format content
            content = f"Key: {doc_id}\nSummary: {summary}\nStatus: {fields.get('status', {}).get('name')}\n\nDescription:\n{description}"

            # Add comments
            comments = fields.get("comment", {}).get("comments", [])
            if comments:
                content += "\n\nComments:\n"
                for c in comments:
                    author = c.get("author", {}).get("displayName", "Unknown")
                    body = c.get("body", "")
                    content += f"--- {author} ---\n{body}\n\n"

            created = fields.get("created")
            updated = fields.get("updated")

            metadata = {
                "key": doc_id,
                "summary": summary,
                "project": fields.get("project", {}).get("key"),
                "issuetype": fields.get("issuetype", {}).get("name"),
                "priority": fields.get("priority", {}).get("name"),
                "assignee": fields.get("assignee", {}).get("displayName"),
                "reporter": fields.get("reporter", {}).get("displayName"),
            }

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"{doc_id}.txt",
                metadata=metadata,
                created_at=(
                    datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if created
                    else None
                ),
                modified_at=(
                    datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if updated
                    else None
                ),
            )
        except Exception as e:
            logger.error(f"Error loading JIRA issue {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load issues from a JQL query (treated as folder_path)."""
        # folder_path is interpreted as JQL here
        return self.search(folder_path)

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search using JQL."""
        if not self._authenticated:
            self.authenticate()

        documents = []
        try:
            results = self._client.jql(query, limit=max_results)
            issues = results.get("issues", [])

            for issue in issues:
                key = issue.get("key")
                if key:
                    doc = self.load_document(key)
                    if doc:
                        documents.append(doc)
        except Exception as e:
            logger.error(f"Error searching JIRA: {e}")

        return documents
