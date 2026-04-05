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

"""Productivity and no-code platform loaders for RAG pipelines.

Supports:
- Airtable (collaborative database)
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for Airtable
try:
    from pyairtable import Api as AirtableApi

    AIRTABLE_AVAILABLE = True
except ImportError:
    AIRTABLE_AVAILABLE = False


class AirtableLoader(BaseLoader):
    """Document loader for Airtable bases and tables.

    Load records from Airtable spreadsheet databases.

    Features:
    - Load records from tables
    - Filter by formula
    - Support for linked records
    - Field formatting

    Requirements:
        pip install pyairtable

    Environment variables:
        AIRTABLE_API_KEY: API key

    Example:
        loader = AirtableLoader(api_key="xxx")
        loader.authenticate()
        docs = loader.load_table("base_id", "table_name")
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize Airtable loader.

        Args:
            api_key: Airtable API key
        """
        if not AIRTABLE_AVAILABLE:
            raise ImportError(
                "pyairtable is required for AirtableLoader. "
                "Install with: pip install pyairtable"
            )

        self._api_key = api_key or os.environ.get("AIRTABLE_API_KEY")
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "Airtable"

    def authenticate(self) -> bool:
        """Authenticate with Airtable API."""
        try:
            self._client = AirtableApi(self._api_key)
            self._authenticated = True
            logger.info("Airtable authentication successful")
            return True

        except Exception as e:
            logger.error(f"Airtable authentication failed: {e}")
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single record by ID.

        Args:
            doc_id: Record ID in format "base_id:table_name:record_id"

        Returns:
            LoadedDocument or None
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            parts = doc_id.split(":")
            if len(parts) != 3:
                raise ValueError("doc_id must be base_id:table_name:record_id")

            base_id, table_name, record_id = parts
            table = self._client.table(base_id, table_name)
            record = table.get(record_id)

            # Format fields as content
            content_parts = [f"# Record: {record_id}", ""]
            for field, value in record.get("fields", {}).items():
                content_parts.append(f"**{field}:** {value}")

            content = "\n".join(content_parts)

            return LoadedDocument(
                content=content,
                source="airtable",
                source_id=doc_id,
                filename=f"{record_id}.md",
                created_at=(
                    datetime.fromisoformat(record["createdTime"].replace("Z", "+00:00"))
                    if record.get("createdTime")
                    else None
                ),
                metadata={
                    "base_id": base_id,
                    "table": table_name,
                    "fields": list(record.get("fields", {}).keys()),
                },
            )

        except Exception as e:
            logger.error(f"Failed to load Airtable record {doc_id}: {e}")
            return None

    def load_record(self, record_id: str) -> Optional[LoadedDocument]:
        """Alias for load_document."""
        return self.load_document(record_id)

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load records from a table.

        Args:
            folder_path: "base_id:table_name" format
            recursive: Not used for Airtable

        Returns:
            List of LoadedDocument
        """
        parts = folder_path.split(":")
        if len(parts) != 2:
            logger.error("folder_path must be base_id:table_name")
            return []

        return self.load_table(parts[0], parts[1])

    def load_table(
        self,
        base_id: str,
        table_name: str,
        formula: Optional[str] = None,
        max_records: int = 100,
    ) -> list[LoadedDocument]:
        """Load records from an Airtable table.

        Args:
            base_id: Base ID
            table_name: Table name
            formula: Filter formula
            max_records: Maximum records to return

        Returns:
            List of LoadedDocument
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            table = self._client.table(base_id, table_name)

            kwargs = {"max_records": max_records}
            if formula:
                kwargs["formula"] = formula

            records = table.all(**kwargs)

            for record in records:
                doc = self.load_document(f"{base_id}:{table_name}:{record['id']}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load Airtable table: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search is not directly supported - use formula filter instead."""
        logger.warning(
            "Airtable doesn't support full-text search. Use load_table with formula."
        )
        return []

    async def load_async(self, doc_id: str) -> Optional[LoadedDocument]:
        """Async document loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.load_document, doc_id)

    async def load_folder_async(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Async folder loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.load_folder, folder_path, recursive
        )


# ============================================================================
# HUBSPOT LOADER
# ============================================================================

# Check for hubspot availability
try:
    from hubspot import HubSpot

    HUBSPOT_AVAILABLE = True
except ImportError:
    HUBSPOT_AVAILABLE = False


__all__ = [
    "AirtableLoader",
    "AIRTABLE_AVAILABLE",
]
