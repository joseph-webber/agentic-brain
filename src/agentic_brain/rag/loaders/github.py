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

"""GitHub loader for RAG pipelines.

Supports:
- Repository code and documentation
- Issues and Pull Requests
- Search across GitHub
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for PyGithub
try:
    from github import Github, GithubException
    from github.ContentFile import ContentFile

    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False


class GitHubLoader(BaseLoader):
    """Load documents from GitHub repositories.

    Loads code, documentation, issues, PRs, and wikis for RAG.
    Perfect for building code-aware assistants.

    Authentication options:
        1. Personal Access Token (recommended)
        2. GitHub App installation token
        3. No auth (public repos only, rate limited)

    Example:
        loader = GitHubLoader(token="ghp_xxxxx")
        docs = loader.load_repository("owner/repo")
        issues = loader.load_issues("owner/repo", state="open")
        results = loader.search_code("def authenticate", language="python")
    """

    CODE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".sql",
        ".r",
        ".m",
        ".mm",
    }

    DOC_EXTENSIONS = {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".asciidoc",
        ".html",
        ".htm",
        ".xml",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".gitignore",
        ".dockerignore",
    }

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        include_code: bool = True,
        include_docs: bool = True,
        max_file_size: int = 1_000_000,
    ):
        if not PYGITHUB_AVAILABLE:
            raise ImportError(
                "PyGithub not available. Install with: pip install PyGithub"
            )

        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._base_url = base_url
        self._include_code = include_code
        self._include_docs = include_docs
        self._max_file_size = max_file_size
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "GitHub"

    def authenticate(self) -> bool:
        """Initialize GitHub client."""
        if self._authenticated and self._client is not None:
            return True

        try:
            github_kwargs = {"login_or_token": self._token}
            if self._base_url:
                github_kwargs["base_url"] = self._base_url

            self._client = Github(**github_kwargs)
        except Exception as e:
            logger.error(f"GitHub client initialization failed: {e}")
            self._client = None
            self._authenticated = False
            return False

        try:
            user = self._client.get_user()
            user_label = user.login if self._token else "anonymous"
            logger.info(f"GitHub authenticated as: {user_label}")
        except GithubException as e:
            logger.warning(
                "GitHub authentication degraded - proceeding with limited access: %s", e
            )
        except Exception as e:
            logger.warning(f"GitHub connection established but user lookup failed: {e}")

        self._authenticated = True
        return True

    def _ensure_authenticated(self) -> None:
        if not self._authenticated and not self.authenticate():
            raise RuntimeError("GitHub authentication required")

    def _should_include_file(self, path: str, size: int) -> bool:
        """Check if file should be included."""
        if size > self._max_file_size:
            return False

        ext = Path(path).suffix.lower()

        if self._include_code and ext in self.CODE_EXTENSIONS:
            return True
        if self._include_docs and ext in self.DOC_EXTENSIONS:
            return True

        filename = Path(path).name.lower()
        return filename in {
            "readme",
            "license",
            "changelog",
            "contributing",
            "makefile",
            "dockerfile",
        }

    def _content_to_document(
        self, content: "ContentFile", repo_name: str
    ) -> Optional[LoadedDocument]:
        """Convert GitHub ContentFile to LoadedDocument."""
        try:
            if content.type != "file":
                return None

            if not self._should_include_file(content.path, content.size):
                return None

            try:
                text_content = content.decoded_content.decode("utf-8")
            except UnicodeDecodeError:
                logger.debug(f"Skipping binary file: {content.path}")
                return None

            ext = Path(content.path).suffix.lower()
            mime_type = "text/plain"
            if ext in {".json"}:
                mime_type = "application/json"
            elif ext in {".md", ".markdown"}:
                mime_type = "text/markdown"
            elif ext in {".html", ".htm"}:
                mime_type = "text/html"
            elif ext in self.CODE_EXTENSIONS:
                mime_type = f"text/x-{ext[1:]}"

            return LoadedDocument(
                content=text_content,
                metadata={
                    "repository": repo_name,
                    "path": content.path,
                    "sha": content.sha,
                    "url": content.html_url,
                    "type": "code" if ext in self.CODE_EXTENSIONS else "documentation",
                },
                source="github",
                source_id=f"github:{repo_name}:{content.path}",
                filename=content.name,
                mime_type=mime_type,
                size_bytes=content.size,
            )

        except Exception as e:
            logger.error(f"Failed to convert GitHub content: {e}")
            return None

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single file from a repository."""
        self._ensure_authenticated()

        try:
            if ":" not in doc_id:
                raise ValueError(
                    f"Invalid doc_id format: {doc_id}. Use 'owner/repo:path/to/file'"
                )

            repo_name, file_path = doc_id.split(":", 1)
            repo = self._client.get_repo(repo_name)
            content = repo.get_contents(file_path)

            if isinstance(content, list):
                logger.warning(f"Path is a directory: {file_path}")
                return None

            return self._content_to_document(content, repo_name)

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load GitHub document: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load files from a repository folder."""
        self._ensure_authenticated()

        documents = []

        try:
            if ":" in folder_path:
                repo_name, path = folder_path.split(":", 1)
            else:
                repo_name = folder_path
                path = ""

            repo = self._client.get_repo(repo_name)

            def process_contents(contents, current_path=""):
                for content in contents:
                    if content.type == "file":
                        doc = self._content_to_document(content, repo_name)
                        if doc:
                            documents.append(doc)
                    elif content.type == "dir" and recursive:
                        try:
                            subcontents = repo.get_contents(content.path)
                            if isinstance(subcontents, list):
                                process_contents(subcontents, content.path)
                        except GithubException:
                            pass

            contents = repo.get_contents(path)
            if isinstance(contents, list):
                process_contents(contents, path)
            else:
                doc = self._content_to_document(contents, repo_name)
                if doc:
                    documents.append(doc)

            logger.info(f"Loaded {len(documents)} files from {repo_name}")
            return documents

        except Exception as e:
            logger.error(f"Failed to load GitHub folder: {e}")
            return []

    def load_repository(
        self,
        repo_name: str,
        branch: Optional[str] = None,
        paths: Optional[list[str]] = None,
    ) -> list[LoadedDocument]:
        """Load entire repository or specific paths."""
        self._ensure_authenticated()

        documents = []

        try:
            repo = self._client.get_repo(repo_name)

            if paths:
                for path in paths:
                    docs = self.load_folder(f"{repo_name}:{path}")
                    documents.extend(docs)
            else:
                documents = self.load_folder(repo_name)

            try:
                readme = repo.get_readme()
                readme_doc = self._content_to_document(readme, repo_name)
                if readme_doc and readme_doc.source_id not in [
                    d.source_id for d in documents
                ]:
                    documents.insert(0, readme_doc)
            except GithubException:
                pass

            return documents

        except Exception as e:
            logger.error(f"Failed to load repository: {e}")
            return []

    def load_issues(
        self,
        repo_name: str,
        state: str = "open",
        labels: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[LoadedDocument]:
        """Load issues from a repository."""
        self._ensure_authenticated()

        documents = []

        try:
            repo = self._client.get_repo(repo_name)
            issues = repo.get_issues(state=state, labels=labels or [])

            count = 0
            for issue in issues:
                if count >= limit:
                    break

                if issue.pull_request:
                    continue

                content_parts = [
                    f"# {issue.title}",
                    f"\n**State:** {issue.state}",
                    f"**Author:** {issue.user.login}",
                    f"**Created:** {issue.created_at}",
                ]

                if issue.labels:
                    content_parts.append(
                        f"**Labels:** {', '.join(l.name for l in issue.labels)}"
                    )

                if issue.body:
                    content_parts.append(f"\n## Description\n{issue.body}")

                comments = list(issue.get_comments()[:10])
                if comments:
                    content_parts.append("\n## Comments")
                    for comment in comments:
                        content_parts.append(
                            f"\n**{comment.user.login}** ({comment.created_at}):\n{comment.body}"
                        )

                doc = LoadedDocument(
                    content="\n".join(content_parts),
                    metadata={
                        "repository": repo_name,
                        "issue_number": issue.number,
                        "state": issue.state,
                        "author": issue.user.login,
                        "labels": [l.name for l in issue.labels],
                        "url": issue.html_url,
                        "comments_count": issue.comments,
                    },
                    source="github",
                    source_id=f"github:{repo_name}:issue:{issue.number}",
                    filename=f"Issue #{issue.number}: {issue.title}",
                    mime_type="text/markdown",
                    created_at=issue.created_at,
                    modified_at=issue.updated_at,
                )
                documents.append(doc)
                count += 1

            logger.info(f"Loaded {len(documents)} issues from {repo_name}")
            return documents

        except Exception as e:
            logger.error(f"Failed to load issues: {e}")
            return []

    def load_pull_requests(
        self, repo_name: str, state: str = "open", limit: int = 50
    ) -> list[LoadedDocument]:
        """Load pull requests from a repository."""
        self._ensure_authenticated()

        documents = []

        try:
            repo = self._client.get_repo(repo_name)
            prs = repo.get_pulls(state=state)

            count = 0
            for pr in prs:
                if count >= limit:
                    break

                content_parts = [
                    f"# PR #{pr.number}: {pr.title}",
                    f"\n**State:** {pr.state}",
                    f"**Author:** {pr.user.login}",
                    f"**Branch:** {pr.head.ref} → {pr.base.ref}",
                    f"**Created:** {pr.created_at}",
                ]

                if pr.body:
                    content_parts.append(f"\n## Description\n{pr.body}")

                try:
                    files = list(pr.get_files()[:20])
                    if files:
                        content_parts.append("\n## Changed Files")
                        for f in files:
                            content_parts.append(
                                f"- {f.filename} (+{f.additions}/-{f.deletions})"
                            )
                except GithubException:
                    pass

                doc = LoadedDocument(
                    content="\n".join(content_parts),
                    metadata={
                        "repository": repo_name,
                        "pr_number": pr.number,
                        "state": pr.state,
                        "author": pr.user.login,
                        "head_branch": pr.head.ref,
                        "base_branch": pr.base.ref,
                        "url": pr.html_url,
                        "mergeable": pr.mergeable,
                    },
                    source="github",
                    source_id=f"github:{repo_name}:pr:{pr.number}",
                    filename=f"PR #{pr.number}: {pr.title}",
                    mime_type="text/markdown",
                    created_at=pr.created_at,
                    modified_at=pr.updated_at,
                )
                documents.append(doc)
                count += 1

            logger.info(f"Loaded {len(documents)} PRs from {repo_name}")
            return documents

        except Exception as e:
            logger.error(f"Failed to load PRs: {e}")
            return []

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for code across GitHub."""
        self._ensure_authenticated()

        documents = []

        try:
            results = self._client.search_code(query)

            count = 0
            for result in results:
                if count >= max_results:
                    break

                try:
                    doc = self._content_to_document(result, result.repository.full_name)
                    if doc:
                        documents.append(doc)
                        count += 1
                except Exception:
                    continue

            logger.info(f"Found {len(documents)} results for '{query}'")
            return documents

        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return []

    def search_repositories(
        self, query: str, max_results: int = 10
    ) -> list[dict[str, Any]]:
        """Search for repositories."""
        self._ensure_authenticated()

        repos = []

        try:
            results = self._client.search_repositories(query)

            count = 0
            for repo in results:
                if count >= max_results:
                    break

                repos.append(
                    {
                        "full_name": repo.full_name,
                        "description": repo.description,
                        "stars": repo.stargazers_count,
                        "language": repo.language,
                        "url": repo.html_url,
                        "default_branch": repo.default_branch,
                    }
                )
                count += 1

            return repos

        except Exception as e:
            logger.error(f"Repository search failed: {e}")
            return []


__all__ = ["GitHubLoader"]
