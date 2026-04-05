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

"""Enterprise system loaders for RAG pipelines.

Supports:
- SAP
- Workday
- ServiceNow
- Dynamics 365
"""

import json
import logging
import os
from typing import Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class SAPLoader(BaseLoader):
    """Load documents from SAP systems via RFC or OData.

    Connects to SAP ERP/S4HANA for document extraction.

    Example:
        loader = SAPLoader(
            host="sap.example.com",
            system_number="00",
            client="100",
            user="SAPUSER",
            password="secret"
        )
        docs = loader.load_folder("BKPF")  # Accounting documents
    """

    def __init__(
        self,
        host: str,
        system_number: str = "00",
        client: str = "100",
        user: Optional[str] = None,
        password: Optional[str] = None,
        odata_url: Optional[str] = None,
    ):
        self.host = host
        self.system_number = system_number
        self.client = client
        self.user = user or os.environ.get("SAP_USER")
        self.password = password or os.environ.get("SAP_PASSWORD")
        self.odata_url = odata_url
        self._connection = None
        self._session = None

    @property
    def source_name(self) -> str:
        return "sap"

    def authenticate(self) -> bool:
        """Connect to SAP system."""
        try:
            try:
                from pyrfc import Connection

                self._connection = Connection(
                    ashost=self.host,
                    sysnr=self.system_number,
                    client=self.client,
                    user=self.user,
                    passwd=self.password,
                )
                logger.info("SAP RFC connection successful")
                return True
            except ImportError:
                pass

            if self.odata_url:
                import requests

                self._session = requests.Session()
                self._session.auth = (self.user, self.password)
                resp = self._session.get(f"{self.odata_url}/$metadata")
                resp.raise_for_status()
                logger.info("SAP OData connection successful")
                return True

            raise ImportError(
                "pyrfc not installed and no OData URL provided. "
                "Run: pip install pyrfc or provide odata_url"
            )
        except Exception as e:
            logger.error(f"SAP connection failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._connection and not self._session and not self.authenticate():
            raise RuntimeError("Failed to connect to SAP")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single SAP document."""
        self._ensure_authenticated()
        try:
            if self._connection:
                result = self._connection.call(
                    "RFC_READ_TABLE",
                    QUERY_TABLE=doc_id.split("/")[0],
                    DELIMITER="|",
                    OPTIONS=[{"TEXT": f"KEY = '{doc_id}'"}],
                )
                content = "\n".join([row["WA"] for row in result.get("DATA", [])])
            else:
                resp = self._session.get(f"{self.odata_url}/{doc_id}")
                resp.raise_for_status()
                content = json.dumps(resp.json(), indent=2)

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=doc_id,
                metadata={"system": self.host, "client": self.client},
            )
        except Exception as e:
            logger.error(f"Failed to load SAP document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load documents from a SAP table/entity set."""
        self._ensure_authenticated()
        docs = []
        table = folder_path

        try:
            if self._connection:
                result = self._connection.call(
                    "RFC_READ_TABLE",
                    QUERY_TABLE=table,
                    DELIMITER="|",
                    ROWCOUNT=1000,
                )
                for i, row in enumerate(result.get("DATA", [])):
                    docs.append(
                        LoadedDocument(
                            content=row["WA"],
                            source=self.source_name,
                            source_id=f"{table}/{i}",
                            filename=f"{table}_{i}",
                            metadata={"table": table},
                        )
                    )
            else:
                resp = self._session.get(f"{self.odata_url}/{table}")
                resp.raise_for_status()
                data = resp.json().get("d", {}).get("results", [])
                for i, item in enumerate(data):
                    docs.append(
                        LoadedDocument(
                            content=json.dumps(item, indent=2),
                            source=self.source_name,
                            source_id=f"{table}/{i}",
                            filename=f"{table}_{i}",
                            metadata={"entity_set": table, **item},
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to load SAP table {table}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search SAP documents."""
        self._ensure_authenticated()
        if self._session and self.odata_url:
            try:
                resp = self._session.get(
                    f"{self.odata_url}/$search",
                    params={"$search": query, "$top": max_results},
                )
                resp.raise_for_status()
                docs = []
                for i, item in enumerate(resp.json().get("d", {}).get("results", [])):
                    docs.append(
                        LoadedDocument(
                            content=json.dumps(item, indent=2),
                            source=self.source_name,
                            source_id=f"search/{i}",
                            filename=f"search_{i}",
                            metadata=item,
                        )
                    )
                return docs
            except Exception as e:
                logger.error(f"SAP search failed: {e}")
        return []


class WorkdayLoader(BaseLoader):
    """Load documents from Workday HCM via REST API.

    Example:
        loader = WorkdayLoader(
            tenant_url="https://company.workday.com",
            client_id="xxx",
            client_secret="yyy"
        )
        docs = loader.load_folder("workers")
    """

    def __init__(
        self,
        tenant_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        self.tenant_url = tenant_url or os.environ.get("WORKDAY_TENANT_URL")
        self.client_id = client_id or os.environ.get("WORKDAY_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("WORKDAY_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.environ.get("WORKDAY_REFRESH_TOKEN")
        self._session = None
        self._access_token = None

    @property
    def source_name(self) -> str:
        return "workday"

    def authenticate(self) -> bool:
        """Authenticate with Workday API."""
        try:
            import requests

            self._session = requests.Session()

            # OAuth token refresh
            response = self._session.post(
                f"{self.tenant_url}/oauth2/v2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
            self._session.headers["Authorization"] = f"Bearer {self._access_token}"

            logger.info("Workday authentication successful")
            return True
        except Exception as e:
            logger.error(f"Workday authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Workday")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Workday resource."""
        self._ensure_authenticated()
        try:
            resp = self._session.get(f"{self.tenant_url}/api/v1/{doc_id}")
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{doc_id.replace('/', '_')}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load Workday document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load Workday resources by type."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(f"{self.tenant_url}/api/v1/{folder_path}")
            resp.raise_for_status()
            data = resp.json().get("data", resp.json())

            if isinstance(data, list):
                for i, item in enumerate(data):
                    docs.append(
                        LoadedDocument(
                            content=json.dumps(item, indent=2),
                            source=self.source_name,
                            source_id=f"{folder_path}/{i}",
                            filename=f"{folder_path}_{i}.json",
                            metadata=item,
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to load Workday {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Workday (workers)."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                f"{self.tenant_url}/api/v1/workers",
                params={"search": query, "limit": max_results},
            )
            resp.raise_for_status()

            for i, item in enumerate(resp.json().get("data", [])):
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2),
                        source=self.source_name,
                        source_id=f"worker/{item.get('id', i)}",
                        filename=f"worker_{item.get('id', i)}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"Workday search failed: {e}")

        return docs


class ServiceNowLoader(BaseLoader):
    """Load documents from ServiceNow via REST API.

    Example:
        loader = ServiceNowLoader(
            instance="company.service-now.com",
            username="admin",
            password="secret"
        )
        docs = loader.load_folder("incident")
    """

    def __init__(
        self,
        instance: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.instance = instance or os.environ.get("SERVICENOW_INSTANCE")
        self.username = username or os.environ.get("SERVICENOW_USERNAME")
        self.password = password or os.environ.get("SERVICENOW_PASSWORD")
        self._session = None

    @property
    def source_name(self) -> str:
        return "servicenow"

    def authenticate(self) -> bool:
        """Authenticate with ServiceNow."""
        try:
            import requests

            self._session = requests.Session()
            self._session.auth = (self.username, self.password)
            self._session.headers["Accept"] = "application/json"

            resp = self._session.get(
                f"https://{self.instance}/api/now/table/sys_user?sysparm_limit=1"
            )
            resp.raise_for_status()

            logger.info("ServiceNow authentication successful")
            return True
        except Exception as e:
            logger.error(f"ServiceNow authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with ServiceNow")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single ServiceNow record."""
        self._ensure_authenticated()
        try:
            table, sys_id = doc_id.split(":", 1)
            resp = self._session.get(
                f"https://{self.instance}/api/now/table/{table}/{sys_id}"
            )
            resp.raise_for_status()
            record = resp.json().get("result", {})

            return LoadedDocument(
                content=json.dumps(record, indent=2),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{table}_{sys_id}.json",
                metadata={"table": table, "sys_id": sys_id},
            )
        except Exception as e:
            logger.error(f"Failed to load ServiceNow record {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load records from a ServiceNow table."""
        self._ensure_authenticated()
        docs = []
        table = folder_path

        try:
            resp = self._session.get(
                f"https://{self.instance}/api/now/table/{table}",
                params={"sysparm_limit": 100},
            )
            resp.raise_for_status()

            for record in resp.json().get("result", []):
                sys_id = record.get("sys_id", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(record, indent=2),
                        source=self.source_name,
                        source_id=f"{table}:{sys_id}",
                        filename=f"{table}_{sys_id}.json",
                        metadata={"table": table, "sys_id": sys_id},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load ServiceNow table {table}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search ServiceNow incidents."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                f"https://{self.instance}/api/now/table/incident",
                params={
                    "sysparm_query": f"short_descriptionLIKE{query}",
                    "sysparm_limit": max_results,
                },
            )
            resp.raise_for_status()

            for record in resp.json().get("result", []):
                sys_id = record.get("sys_id", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(record, indent=2),
                        source=self.source_name,
                        source_id=f"incident:{sys_id}",
                        filename=f"incident_{sys_id}.json",
                        metadata=record,
                    )
                )
        except Exception as e:
            logger.error(f"ServiceNow search failed: {e}")

        return docs


class Dynamics365Loader(BaseLoader):
    """Load documents from Microsoft Dynamics 365 via Dataverse API.

    Example:
        loader = Dynamics365Loader(
            tenant_id="xxx",
            client_id="yyy",
            client_secret="zzz",
            environment_url="https://company.crm.dynamics.com"
        )
        docs = loader.load_folder("accounts")
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        environment_url: Optional[str] = None,
    ):
        self.tenant_id = tenant_id or os.environ.get("DYNAMICS_TENANT_ID")
        self.client_id = client_id or os.environ.get("DYNAMICS_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("DYNAMICS_CLIENT_SECRET")
        self.environment_url = environment_url or os.environ.get(
            "DYNAMICS_ENVIRONMENT_URL"
        )
        self._session = None
        self._access_token = None

    @property
    def source_name(self) -> str:
        return "dynamics365"

    def authenticate(self) -> bool:
        """Authenticate with Dynamics 365."""
        try:
            import requests

            self._session = requests.Session()

            response = self._session.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": f"{self.environment_url}/.default",
                },
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
            self._session.headers["Authorization"] = f"Bearer {self._access_token}"
            self._session.headers["OData-MaxVersion"] = "4.0"
            self._session.headers["OData-Version"] = "4.0"

            logger.info("Dynamics 365 authentication successful")
            return True
        except Exception as e:
            logger.error(f"Dynamics 365 authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Dynamics 365")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Dynamics 365 record."""
        self._ensure_authenticated()
        try:
            entity, record_id = doc_id.split(":", 1)
            resp = self._session.get(
                f"{self.environment_url}/api/data/v9.2/{entity}({record_id})"
            )
            resp.raise_for_status()
            record = resp.json()

            return LoadedDocument(
                content=json.dumps(record, indent=2),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{entity}_{record_id}.json",
                metadata={"entity": entity, "id": record_id},
            )
        except Exception as e:
            logger.error(f"Failed to load Dynamics 365 record {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load records from a Dynamics 365 entity."""
        self._ensure_authenticated()
        docs = []
        entity = folder_path

        try:
            resp = self._session.get(
                f"{self.environment_url}/api/data/v9.2/{entity}",
                params={"$top": 100},
            )
            resp.raise_for_status()

            for record in resp.json().get("value", []):
                record_id = record.get(f"{entity.rstrip('s')}id", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(record, indent=2),
                        source=self.source_name,
                        source_id=f"{entity}:{record_id}",
                        filename=f"{entity}_{record_id}.json",
                        metadata={"entity": entity, "id": record_id},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load Dynamics 365 entity {entity}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Dynamics 365 accounts."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                f"{self.environment_url}/api/data/v9.2/accounts",
                params={
                    "$filter": f"contains(name,'{query}')",
                    "$top": max_results,
                },
            )
            resp.raise_for_status()

            for record in resp.json().get("value", []):
                record_id = record.get("accountid", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(record, indent=2),
                        source=self.source_name,
                        source_id=f"accounts:{record_id}",
                        filename=f"account_{record_id}.json",
                        metadata=record,
                    )
                )
        except Exception as e:
            logger.error(f"Dynamics 365 search failed: {e}")

        return docs


__all__ = [
    "SAPLoader",
    "WorkdayLoader",
    "ServiceNowLoader",
    "Dynamics365Loader",
]
