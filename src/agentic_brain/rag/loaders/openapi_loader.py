# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""OpenAPI/Swagger loader for RAG pipelines."""

import json
import logging
from pathlib import Path
from typing import Optional

import yaml

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class OpenAPILoader(BaseLoader):
    """Load OpenAPI/Swagger specifications (JSON or YAML)."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()

    @property
    def source_name(self) -> str:
        return "openapi"

    def authenticate(self) -> bool:
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        path = self.base_path / doc_id
        if not path.exists():
            return None

        try:
            content = path.read_text()
            if path.suffix in [".json"]:
                data = json.loads(content)
            else:
                data = yaml.safe_load(content)

            title = data.get("info", {}).get("title", "Unknown API")
            version = data.get("info", {}).get("version", "unknown")
            paths = list(data.get("paths", {}).keys())

            metadata = {
                "title": title,
                "version": version,
                "endpoint_count": len(paths),
                "endpoints": paths[:10],  # First 10
            }

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading OpenAPI spec {path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        folder = self.base_path / folder_path
        docs = []
        for ext in ["*.json", "*.yaml", "*.yml"]:
            pattern = f"**/{ext}" if recursive else ext
            for p in folder.glob(pattern):
                if p.is_file():
                    # Simple heuristic: check if it looks like OpenAPI
                    try:
                        content = p.read_text()[:500]
                        if "openapi" in content or "swagger" in content:
                            doc = self.load_document(str(p.relative_to(self.base_path)))
                            if doc:
                                docs.append(doc)
                    except Exception:
                        pass
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []
