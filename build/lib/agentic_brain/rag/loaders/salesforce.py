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

"""Salesforce loader for RAG pipelines.

SECURITY: Uses _validate_salesforce_object() to prevent injection attacks
in SOQL/SOSL queries.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument, _validate_salesforce_object

logger = logging.getLogger(__name__)

# Check for simple-salesforce
try:
    from simple_salesforce import Salesforce

    SALESFORCE_AVAILABLE = True
except ImportError:
    SALESFORCE_AVAILABLE = False


class SalesforceLoader(BaseLoader):
    """Document loader for Salesforce CRM.

    Load records from Salesforce objects.

    Features:
    - Load any Salesforce object
    - SOQL query support
    - Load attachments
    - Support for custom objects

    Requirements:
        pip install simple-salesforce

    SECURITY: Object names are validated with _validate_salesforce_object()
    to prevent SOQL/SOSL injection.

    Example:
        loader = SalesforceLoader(username="x", password="y", security_token="z")
        loader.authenticate()
        docs = loader.load_query("SELECT Id, Name FROM Account LIMIT 10")
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        security_token: Optional[str] = None,
        domain: Optional[str] = None,
        **kwargs,
    ):
        if not SALESFORCE_AVAILABLE:
            raise ImportError(
                "simple-salesforce is required for SalesforceLoader. "
                "Install with: pip install simple-salesforce"
            )

        self._username = username or os.environ.get("SALESFORCE_USERNAME")
        self._password = password or os.environ.get("SALESFORCE_PASSWORD")
        self._security_token = security_token or os.environ.get(
            "SALESFORCE_SECURITY_TOKEN"
        )
        self._domain = domain or os.environ.get("SALESFORCE_DOMAIN", "login")
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "salesforce"

    def authenticate(self) -> bool:
        """Authenticate with Salesforce API."""
        try:
            self._client = Salesforce(
                username=self._username,
                password=self._password,
                security_token=self._security_token,
                domain=self._domain,
            )

            self._authenticated = True
            logger.info("Salesforce authentication successful")
            return True

        except Exception as e:
            logger.error(f"Salesforce authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single record.

        Args:
            doc_id: Record ID in format "ObjectName:RecordId"
        """
        self._ensure_authenticated()

        try:
            obj_name, record_id = doc_id.split(":", 1)
            obj_name = _validate_salesforce_object(obj_name)
            obj = getattr(self._client, obj_name)
            record = obj.get(record_id)

            content_parts = [f"# {obj_name}: {record_id}", ""]
            for field, value in record.items():
                if value and field != "attributes":
                    content_parts.append(f"**{field}:** {value}")

            content = "\n".join(content_parts)

            return LoadedDocument(
                content=content,
                source="salesforce",
                source_id=doc_id,
                filename=f"{obj_name}_{record_id}.md",
                created_at=(
                    datetime.fromisoformat(record["CreatedDate"].replace("Z", "+00:00"))
                    if record.get("CreatedDate")
                    else None
                ),
                modified_at=(
                    datetime.fromisoformat(
                        record["LastModifiedDate"].replace("Z", "+00:00")
                    )
                    if record.get("LastModifiedDate")
                    else None
                ),
                metadata={
                    "object": obj_name,
                    "id": record_id,
                },
            )

        except Exception as e:
            logger.error(f"Failed to load Salesforce record {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load records from an object.

        Args:
            folder_path: Object name (Account, Contact, etc.)
        """
        obj_name = _validate_salesforce_object(folder_path)
        return self.load_query(f"SELECT Id FROM {obj_name} LIMIT 100")

    def load_query(self, soql: str) -> list[LoadedDocument]:
        """Load records matching a SOQL query."""
        self._ensure_authenticated()

        docs = []

        try:
            obj_name = soql.split("FROM")[1].split()[0].strip()
            obj_name = _validate_salesforce_object(obj_name)

            result = self._client.query(soql)

            for record in result.get("records", []):
                doc = self.load_document(f"{obj_name}:{record['Id']}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to execute Salesforce query: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search using SOSL."""
        self._ensure_authenticated()

        docs = []

        try:
            sosl = f"FIND {{{query}}} IN ALL FIELDS RETURNING Account(Id), Contact(Id), Lead(Id) LIMIT {max_results}"
            result = self._client.search(sosl)

            for record in result.get("searchRecords", []):
                obj_type = record["attributes"]["type"]
                doc = self.load_document(f"{obj_type}:{record['Id']}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Salesforce search failed: {e}")

        return docs


__all__ = ["SalesforceLoader"]
