# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""SSO/SAML Metadata loader for RAG pipelines."""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class SsoSamlLoader(BaseLoader):
    """Load SAML metadata XML files."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()

    @property
    def source_name(self) -> str:
        return "sso_saml"

    def authenticate(self) -> bool:
        return True

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        path = self.base_path / doc_id
        if not path.exists():
            return None

        try:
            content = path.read_text()
            root = ET.fromstring(content)

            entity_id = root.get("entityID")

            # Basic namespace handling
            ns = {"md": "urn:oasis:names:tc:SAML:2.0:metadata"}

            idps = root.findall(".//md:IDPSSODescriptor", ns)
            sps = root.findall(".//md:SPSSODescriptor", ns)

            metadata = {
                "entity_id": entity_id,
                "is_idp": len(idps) > 0,
                "is_sp": len(sps) > 0,
                "cert_count": len(
                    root.findall(
                        ".//ds:X509Certificate",
                        {"ds": "http://www.w3.org/2000/09/xmldsig#"},
                    )
                ),
            }

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading SAML metadata {path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        folder = self.base_path / folder_path
        docs = []
        pattern = "**/*.xml" if recursive else "*.xml"
        for p in folder.glob(pattern):
            if p.is_file():
                # Heuristic: check if it looks like SAML
                try:
                    content = p.read_text()[:500]
                    if "EntityDescriptor" in content:
                        doc = self.load_document(str(p.relative_to(self.base_path)))
                        if doc:
                            docs.append(doc)
                except Exception:
                    pass
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []
