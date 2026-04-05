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

"""Australian business software loaders for RAG pipelines.

Supports:
- MYOB (AccountRight, Essentials)
- Xero
- Deputy
- Employment Hero
"""

import json
import logging
import os
from typing import Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class MYOBLoader(BaseLoader):
    """Load documents from MYOB accounting software.

    Supports both MYOB AccountRight and Essentials APIs.

    Environment variables:
        MYOB_CLIENT_ID: OAuth client ID
        MYOB_CLIENT_SECRET: OAuth client secret
        MYOB_REFRESH_TOKEN: OAuth refresh token
        MYOB_COMPANY_FILE_ID: Company file ID (AccountRight)

    Example:
        loader = MYOBLoader(client_id="xxx", client_secret="yyy")
        loader.authenticate()
        docs = loader.load_folder("invoices")
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        company_file_id: Optional[str] = None,
        api_version: str = "v2",
    ):
        self.client_id = client_id or os.environ.get("MYOB_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("MYOB_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.environ.get("MYOB_REFRESH_TOKEN")
        self.company_file_id = company_file_id or os.environ.get("MYOB_COMPANY_FILE_ID")
        self.api_version = api_version
        self._session = None
        self._access_token = None

    @property
    def source_name(self) -> str:
        return "myob"

    def authenticate(self) -> bool:
        """Authenticate with MYOB API."""
        try:
            import requests

            self._session = requests.Session()

            # OAuth token refresh
            response = self._session.post(
                "https://secure.myob.com/oauth2/v1/authorize",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
            self._session.headers["Authorization"] = f"Bearer {self._access_token}"
            self._session.headers["x-myobapi-key"] = self.client_id
            self._session.headers["Accept"] = "application/json"

            logger.info("MYOB authentication successful")
            return True
        except Exception as e:
            logger.error(f"MYOB authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with MYOB")

    def _api_url(self, endpoint: str) -> str:
        base = f"https://api.myob.com/accountright/{self.api_version}"
        if self.company_file_id:
            return f"{base}/{self.company_file_id}/{endpoint}"
        return f"{base}/{endpoint}"

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single MYOB record."""
        self._ensure_authenticated()
        try:
            resp = self._session.get(self._api_url(doc_id))
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{doc_id.replace('/', '_')}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load MYOB document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load MYOB records by type.

        Supported types: invoices, contacts, accounts, items
        """
        self._ensure_authenticated()
        docs = []
        folder_lower = folder_path.lower()

        endpoint_map = {
            "invoices": "Sale/Invoice",
            "contacts": "Contact",
            "accounts": "GeneralLedger/Account",
            "items": "Inventory/Item",
            "customers": "Contact/Customer",
            "suppliers": "Contact/Supplier",
        }

        endpoint = endpoint_map.get(folder_lower, folder_path)

        try:
            resp = self._session.get(self._api_url(endpoint))
            resp.raise_for_status()
            items = resp.json().get("Items", resp.json())

            if isinstance(items, list):
                for item in items:
                    uid = item.get("UID", "")
                    docs.append(
                        LoadedDocument(
                            content=json.dumps(item, indent=2, default=str),
                            source=self.source_name,
                            source_id=f"{endpoint}/{uid}",
                            filename=f"{folder_lower}_{uid}.json",
                            metadata={"type": folder_lower, "uid": uid},
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to load MYOB {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search MYOB contacts."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                self._api_url("Contact"),
                params={"$filter": f"contains(Name,'{query}')", "$top": max_results},
            )
            resp.raise_for_status()

            for item in resp.json().get("Items", []):
                uid = item.get("UID", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"Contact/{uid}",
                        filename=f"contact_{uid}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"MYOB search failed: {e}")

        return docs


class XeroLoader(BaseLoader):
    """Load documents from Xero accounting software.

    Environment variables:
        XERO_CLIENT_ID: OAuth2 client ID
        XERO_CLIENT_SECRET: OAuth2 client secret
        XERO_TENANT_ID: Tenant/Organisation ID

    Example:
        loader = XeroLoader(client_id="xxx", client_secret="yyy")
        loader.authenticate()
        docs = loader.load_folder("invoices")
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        self.client_id = client_id or os.environ.get("XERO_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("XERO_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.environ.get("XERO_REFRESH_TOKEN")
        self.tenant_id = tenant_id or os.environ.get("XERO_TENANT_ID")
        self._session = None
        self._access_token = None

    @property
    def source_name(self) -> str:
        return "xero"

    def authenticate(self) -> bool:
        """Authenticate with Xero API."""
        try:
            import requests

            self._session = requests.Session()

            response = self._session.post(
                "https://identity.xero.com/connect/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "refresh_token": self.refresh_token,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                auth=(self.client_id, self.client_secret),
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
            self._session.headers["Authorization"] = f"Bearer {self._access_token}"
            self._session.headers["xero-tenant-id"] = self.tenant_id
            self._session.headers["Accept"] = "application/json"

            logger.info("Xero authentication successful")
            return True
        except Exception as e:
            logger.error(f"Xero authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Xero")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Xero record."""
        self._ensure_authenticated()
        try:
            endpoint, item_id = doc_id.rsplit("/", 1)
            resp = self._session.get(
                f"https://api.xero.com/api.xro/2.0/{endpoint}/{item_id}"
            )
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{doc_id.replace('/', '_')}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load Xero document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load Xero records by type."""
        self._ensure_authenticated()
        docs = []
        folder_lower = folder_path.lower()

        endpoint_map = {
            "invoices": "Invoices",
            "contacts": "Contacts",
            "accounts": "Accounts",
            "items": "Items",
            "payments": "Payments",
            "bills": 'Invoices?where=Type="ACCPAY"',
        }

        endpoint = endpoint_map.get(folder_lower, folder_path)

        try:
            resp = self._session.get(f"https://api.xero.com/api.xro/2.0/{endpoint}")
            resp.raise_for_status()
            data = resp.json()

            # Xero returns data with type-specific keys
            for key, items in data.items():
                if isinstance(items, list):
                    for item in items:
                        item_id = item.get(f"{key[:-1]}ID", item.get("ContactID", ""))
                        docs.append(
                            LoadedDocument(
                                content=json.dumps(item, indent=2, default=str),
                                source=self.source_name,
                                source_id=f"{folder_lower}/{item_id}",
                                filename=f"{folder_lower}_{item_id}.json",
                                metadata={"type": folder_lower, "id": item_id},
                            )
                        )
                    break
        except Exception as e:
            logger.error(f"Failed to load Xero {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Xero contacts."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                "https://api.xero.com/api.xro/2.0/Contacts",
                params={"where": f'Name.Contains("{query}")'},
            )
            resp.raise_for_status()

            contacts = resp.json().get("Contacts", [])
            for contact in contacts[:max_results]:
                contact_id = contact.get("ContactID", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(contact, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"contacts/{contact_id}",
                        filename=f"contact_{contact_id}.json",
                        metadata=contact,
                    )
                )
        except Exception as e:
            logger.error(f"Xero search failed: {e}")

        return docs


class DeputyLoader(BaseLoader):
    """Load documents from Deputy workforce management.

    Environment variables:
        DEPUTY_ACCESS_TOKEN: OAuth2 access token
        DEPUTY_SUBDOMAIN: Your Deputy subdomain

    Example:
        loader = DeputyLoader(access_token="xxx", subdomain="company")
        docs = loader.load_folder("employees")
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        subdomain: Optional[str] = None,
    ):
        self.access_token = access_token or os.environ.get("DEPUTY_ACCESS_TOKEN")
        self.subdomain = subdomain or os.environ.get("DEPUTY_SUBDOMAIN")
        self._session = None

    @property
    def source_name(self) -> str:
        return "deputy"

    def authenticate(self) -> bool:
        """Setup Deputy API session."""
        try:
            import requests

            self._session = requests.Session()
            self._session.headers["Authorization"] = f"Bearer {self.access_token}"
            self._session.headers["Content-Type"] = "application/json"

            # Test connection
            resp = self._session.get(self._api_url("me"))
            resp.raise_for_status()

            logger.info("Deputy authentication successful")
            return True
        except Exception as e:
            logger.error(f"Deputy authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Deputy")

    def _api_url(self, endpoint: str) -> str:
        return f"https://{self.subdomain}.deputy.com/api/v1/{endpoint}"

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Deputy record."""
        self._ensure_authenticated()
        try:
            resp = self._session.get(self._api_url(doc_id))
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{doc_id.replace('/', '_')}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load Deputy document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load Deputy records by type."""
        self._ensure_authenticated()
        docs = []
        folder_lower = folder_path.lower()

        endpoint_map = {
            "employees": "resource/Employee/QUERY",
            "timesheets": "resource/Timesheet/QUERY",
            "rosters": "resource/Roster/QUERY",
            "leave": "resource/Leave/QUERY",
        }

        endpoint = endpoint_map.get(folder_lower, f"resource/{folder_path}/QUERY")

        try:
            resp = self._session.post(
                self._api_url(endpoint),
                json={"search": {"s1": {"field": "Id", "type": ">", "data": 0}}},
            )
            resp.raise_for_status()
            items = resp.json()

            if isinstance(items, list):
                for item in items:
                    item_id = item.get("Id", "")
                    docs.append(
                        LoadedDocument(
                            content=json.dumps(item, indent=2, default=str),
                            source=self.source_name,
                            source_id=f"{folder_lower}/{item_id}",
                            filename=f"{folder_lower}_{item_id}.json",
                            metadata={"type": folder_lower, "id": str(item_id)},
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to load Deputy {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Deputy employees."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.post(
                self._api_url("resource/Employee/QUERY"),
                json={
                    "search": {
                        "s1": {
                            "field": "DisplayName",
                            "type": "lk",
                            "data": f"%{query}%",
                        }
                    }
                },
            )
            resp.raise_for_status()

            for item in resp.json()[:max_results]:
                item_id = item.get("Id", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"employees/{item_id}",
                        filename=f"employee_{item_id}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"Deputy search failed: {e}")

        return docs


class EmploymentHeroLoader(BaseLoader):
    """Load documents from Employment Hero HR/Payroll.

    Environment variables:
        EMPLOYMENT_HERO_API_KEY: API key
        EMPLOYMENT_HERO_ORGANISATION_ID: Organisation ID

    Example:
        loader = EmploymentHeroLoader(api_key="xxx", organisation_id="yyy")
        docs = loader.load_folder("employees")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        organisation_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("EMPLOYMENT_HERO_API_KEY")
        self.organisation_id = organisation_id or os.environ.get(
            "EMPLOYMENT_HERO_ORGANISATION_ID"
        )
        self._session = None

    @property
    def source_name(self) -> str:
        return "employment_hero"

    def authenticate(self) -> bool:
        """Setup Employment Hero API session."""
        try:
            import requests

            self._session = requests.Session()
            self._session.headers["Authorization"] = f"Bearer {self.api_key}"
            self._session.headers["Accept"] = "application/json"

            # Test connection
            resp = self._session.get(self._api_url("organisations"))
            resp.raise_for_status()

            logger.info("Employment Hero authentication successful")
            return True
        except Exception as e:
            logger.error(f"Employment Hero authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Employment Hero")

    def _api_url(self, endpoint: str) -> str:
        base = "https://api.employmenthero.com/api/v1"
        if self.organisation_id and endpoint not in ["organisations"]:
            return f"{base}/organisations/{self.organisation_id}/{endpoint}"
        return f"{base}/{endpoint}"

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Employment Hero record."""
        self._ensure_authenticated()
        try:
            resp = self._session.get(self._api_url(doc_id))
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{doc_id.replace('/', '_')}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load Employment Hero document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load Employment Hero records by type."""
        self._ensure_authenticated()
        docs = []
        folder_lower = folder_path.lower()

        endpoint_map = {
            "employees": "employees",
            "leave": "leave_requests",
            "timesheets": "timesheets",
            "payslips": "pay_runs",
        }

        endpoint = endpoint_map.get(folder_lower, folder_path)

        try:
            resp = self._session.get(self._api_url(endpoint))
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data", data) if isinstance(data, dict) else data

            if isinstance(items, list):
                for item in items:
                    item_id = item.get("id", "")
                    docs.append(
                        LoadedDocument(
                            content=json.dumps(item, indent=2, default=str),
                            source=self.source_name,
                            source_id=f"{folder_lower}/{item_id}",
                            filename=f"{folder_lower}_{item_id}.json",
                            metadata={"type": folder_lower, "id": str(item_id)},
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to load Employment Hero {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Employment Hero employees."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                self._api_url("employees"), params={"filter[name]": query}
            )
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data", data) if isinstance(data, dict) else data

            for item in items[:max_results]:
                item_id = item.get("id", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"employees/{item_id}",
                        filename=f"employee_{item_id}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"Employment Hero search failed: {e}")

        return docs


__all__ = [
    "MYOBLoader",
    "XeroLoader",
    "DeputyLoader",
    "EmploymentHeroLoader",
]
