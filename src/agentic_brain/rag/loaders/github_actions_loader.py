# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""GitHub Actions workflow loader for RAG pipelines."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class GitHubActionsLoader(BaseLoader):
    """Load GitHub Actions workflows."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()

    @property
    def source_name(self) -> str:
        return "github_actions"

    def authenticate(self) -> bool:
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        path = self.base_path / doc_id
        if not path.exists():
            return None

        try:
            content = path.read_text()
            data = yaml.safe_load(content)

            name = data.get("name", path.stem)
            on_events = []
            if "on" in data:
                if isinstance(data["on"], list):
                    on_events = data["on"]
                elif isinstance(data["on"], dict):
                    on_events = list(data["on"].keys())
                elif isinstance(data["on"], str):
                    on_events = [data["on"]]

            jobs = list(data.get("jobs", {}).keys())

            metadata = {"workflow_name": name, "triggers": on_events, "jobs": jobs}

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading GitHub workflow {path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        folder = self.base_path / folder_path
        docs = []
        # Typically in .github/workflows/*.yml
        pattern = "**/*.yml" if recursive else "*.yml"
        for p in folder.glob(pattern):
            if p.is_file() and ".github/workflows" in str(p):
                doc = self.load_document(str(p.relative_to(self.base_path)))
                if doc:
                    docs.append(doc)
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []
