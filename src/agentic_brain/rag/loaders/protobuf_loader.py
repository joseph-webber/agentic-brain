# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Protocol Buffer loader for RAG pipelines."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class ProtobufLoader(BaseLoader):
    """Load Protocol Buffer definitions (.proto)."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()

    @property
    def source_name(self) -> str:
        return "protobuf"

    def authenticate(self) -> bool:
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        path = self.base_path / doc_id
        if not path.exists():
            return None

        try:
            content = path.read_text()

            messages = re.findall(r"message\s+(\w+)", content)
            services = re.findall(r"service\s+(\w+)", content)
            rpcs = re.findall(r"rpc\s+(\w+)", content)
            package = re.search(r"package\s+([\w\.]+);", content)

            metadata = {
                "package": package.group(1) if package else None,
                "messages": messages,
                "services": services,
                "rpc_count": len(rpcs),
            }

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading Protobuf file {path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        folder = self.base_path / folder_path
        docs = []
        pattern = "**/*.proto" if recursive else "*.proto"
        for p in folder.glob(pattern):
            if p.is_file():
                doc = self.load_document(str(p.relative_to(self.base_path)))
                if doc:
                    docs.append(doc)
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []
