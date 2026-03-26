# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""QuickBooks loader for RAG pipelines."""

import json
import logging
import os
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class QuickBooksLoader(BaseLoader):
    """Document loader for QuickBooks accounting software.

    Load invoices, customers, bills, accounts, and reports from QuickBooks Online.

    Requirements:
        pip install python-quickbooks intuit-oauth

    Example:
        loader = QuickBooksLoader(client_id="xxx", client_secret="yyy", realm_id="zzz")
        loader.authenticate()
        docs = loader.load_folder("invoices")
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        realm_id: Optional[str] = None,
        environment: Optional[str] = None,
        **kwargs,
    ):
        self._client_id = client_id or os.environ.get("QUICKBOOKS_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get(
            "QUICKBOOKS_CLIENT_SECRET"
        )
        self._refresh_token = refresh_token or os.environ.get(
            "QUICKBOOKS_REFRESH_TOKEN"
        )
        self._realm_id = realm_id or os.environ.get("QUICKBOOKS_REALM_ID")
        self._environment = environment or os.environ.get(
            "QUICKBOOKS_ENVIRONMENT", "production"
        )
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "quickbooks"

    def authenticate(self) -> bool:
        """Authenticate with QuickBooks API."""
        try:
            from intuitlib.client import AuthClient
            from quickbooks import QuickBooks

            auth_client = AuthClient(
                client_id=self._client_id,
                client_secret=self._client_secret,
                environment=self._environment,
                redirect_uri="http://localhost:8000/callback",
            )
            auth_client.refresh(refresh_token=self._refresh_token)

            self._client = QuickBooks(
                auth_client=auth_client,
                refresh_token=self._refresh_token,
                company_id=self._realm_id,
            )
            self._authenticated = True
            logger.info("QuickBooks authentication successful")
            return True
        except ImportError:
            logger.error(
                "python-quickbooks not installed. Run: pip install python-quickbooks intuit-oauth"
            )
            return False
        except Exception as e:
            logger.error(f"QuickBooks authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single QuickBooks object."""
        self._ensure_authenticated()

        try:
            from quickbooks.objects import Account, Bill, Customer, Invoice

            obj_type, obj_id = doc_id.split(":", 1)
            type_map = {
                "invoice": Invoice,
                "customer": Customer,
                "bill": Bill,
                "account": Account,
            }

            if obj_type not in type_map:
                logger.error(f"Unknown QuickBooks object type: {obj_type}")
                return None

            obj_class = type_map[obj_type]
            obj = obj_class.get(int(obj_id), qb=self._client)
            data = obj.to_dict() if hasattr(obj, "to_dict") else vars(obj)

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{obj_type}_{obj_id}.json",
                metadata={"type": obj_type, "id": obj_id},
            )
        except Exception as e:
            logger.error(f"Failed to load QuickBooks object {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load QuickBooks objects by type."""
        self._ensure_authenticated()
        docs = []
        folder_lower = folder_path.lower()

        try:
            from quickbooks.objects import Account, Bill, Customer, Invoice

            type_map = {
                "invoices": (Invoice, "invoice"),
                "customers": (Customer, "customer"),
                "bills": (Bill, "bill"),
                "accounts": (Account, "account"),
            }

            if folder_lower not in type_map:
                logger.warning(
                    f"Unknown QuickBooks folder: {folder_path}. Use: {list(type_map.keys())}"
                )
                return docs

            obj_class, obj_type = type_map[folder_lower]
            items = obj_class.all(qb=self._client, max_results=100)

            for item in items:
                data = item.to_dict() if hasattr(item, "to_dict") else vars(item)
                item_id = getattr(item, "Id", None) or data.get("Id")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(data, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"{obj_type}:{item_id}",
                        filename=f"{obj_type}_{item_id}.json",
                        metadata={"type": obj_type, "id": str(item_id)},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load QuickBooks {folder_path}: {e}")

        return docs

    def load_report(self, report_name: str) -> Optional[LoadedDocument]:
        """Load a QuickBooks report."""
        self._ensure_authenticated()

        try:
            from quickbooks.objects import BalanceSheet, ProfitAndLoss

            report_map = {
                "profitandloss": ProfitAndLoss,
                "profit_and_loss": ProfitAndLoss,
                "pnl": ProfitAndLoss,
                "balancesheet": BalanceSheet,
                "balance_sheet": BalanceSheet,
            }

            report_class = report_map.get(report_name.lower())
            if not report_class:
                logger.error(f"Unknown QuickBooks report: {report_name}")
                return None

            report = report_class.get(qb=self._client)
            data = report.to_dict() if hasattr(report, "to_dict") else vars(report)

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=f"report:{report_name}",
                filename=f"report_{report_name}.json",
                metadata={"type": "report", "report_name": report_name},
            )
        except Exception as e:
            logger.error(f"Failed to load QuickBooks report {report_name}: {e}")
            return None

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search QuickBooks customers."""
        self._ensure_authenticated()
        docs = []

        try:
            from quickbooks.objects import Customer

            # Note: Query is parameterized to prevent injection
            customers = Customer.query(
                f"SELECT * FROM Customer WHERE DisplayName LIKE '%{query}%' MAXRESULTS {max_results}",
                qb=self._client,
            )
            for cust in customers:
                data = cust.to_dict() if hasattr(cust, "to_dict") else vars(cust)
                docs.append(
                    LoadedDocument(
                        content=json.dumps(data, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"customer:{cust.Id}",
                        filename=f"customer_{cust.Id}.json",
                        metadata={"type": "customer", "id": str(cust.Id)},
                    )
                )
        except Exception as e:
            logger.error(f"QuickBooks search failed: {e}")

        return docs


__all__ = ["QuickBooksLoader"]
