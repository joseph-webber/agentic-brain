# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Ansible playbook loader for RAG pipelines."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class AnsibleLoader(BaseLoader):
    """Load Ansible playbooks (YAML)."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()

    @property
    def source_name(self) -> str:
        return "ansible"

    def authenticate(self) -> bool:
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        path = self.base_path / doc_id
        if not path.exists():
            return None

        try:
            content = path.read_text()
            data = yaml.safe_load(content)

            hosts = []
            tasks = []

            if isinstance(data, list):
                for play in data:
                    if isinstance(play, dict):
                        if "hosts" in play:
                            hosts.append(play["hosts"])
                        if "tasks" in play:
                            tasks.extend(
                                [t.get("name", "Unnamed task") for t in play["tasks"]]
                            )

            metadata = {"hosts": hosts, "task_count": len(tasks)}

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading Ansible playbook {path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        folder = self.base_path / folder_path
        docs = []
        pattern = "**/*.yml" if recursive else "*.yml"
        for p in folder.glob(pattern):
            if p.is_file():
                doc = self.load_document(str(p.relative_to(self.base_path)))
                if doc:
                    docs.append(doc)
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []
