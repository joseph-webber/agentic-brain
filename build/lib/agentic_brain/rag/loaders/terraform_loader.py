# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Terraform loader for RAG pipelines."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class TerraformLoader(BaseLoader):
    """Load Terraform configuration files (.tf)."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()

    @property
    def source_name(self) -> str:
        return "terraform"

    def authenticate(self) -> bool:
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        path = self.base_path / doc_id
        if not path.exists():
            return None

        try:
            content = path.read_text()

            # Simple regex extraction for metadata
            resources = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', content)
            modules = re.findall(r'module\s+"([^"]+)"', content)
            variables = re.findall(r'variable\s+"([^"]+)"', content)

            metadata = {
                "resource_count": len(resources),
                "module_count": len(modules),
                "variable_count": len(variables),
                "resources": [f"{r[0]}.{r[1]}" for r in resources],
            }

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading Terraform file {path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        folder = self.base_path / folder_path
        docs = []
        pattern = "**/*.tf" if recursive else "*.tf"
        for p in folder.glob(pattern):
            if p.is_file():
                doc = self.load_document(str(p.relative_to(self.base_path)))
                if doc:
                    docs.append(doc)
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []
