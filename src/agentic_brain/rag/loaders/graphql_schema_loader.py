# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""GraphQL Schema loader for RAG pipelines."""

import logging
import re
from pathlib import Path
from typing import Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class GraphQLSchemaLoader(BaseLoader):
    """Load GraphQL schema definitions (.graphql)."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()

    @property
    def source_name(self) -> str:
        return "graphql"

    def authenticate(self) -> bool:
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        path = self.base_path / doc_id
        if not path.exists():
            return None

        try:
            content = path.read_text()

            types = re.findall(r"type\s+(\w+)", content)
            inputs = re.findall(r"input\s+(\w+)", content)
            enums = re.findall(r"enum\s+(\w+)", content)

            metadata = {
                "types": types,
                "inputs": inputs,
                "enums": enums,
                "type_count": len(types),
            }

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading GraphQL schema {path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        folder = self.base_path / folder_path
        docs = []
        pattern = "**/*.graphql" if recursive else "*.graphql"
        for p in folder.glob(pattern):
            if p.is_file():
                doc = self.load_document(str(p.relative_to(self.base_path)))
                if doc:
                    docs.append(doc)
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []
