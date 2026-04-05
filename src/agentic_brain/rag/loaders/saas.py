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

"""SaaS platform loaders for RAG pipelines.

Supports:
- Shopify (e-commerce)
- Stripe (payments)
- PayPal (payments)
- Afterpay (BNPL)
- Braintree (payments)
- WooCommerce (e-commerce)
- BigCommerce (e-commerce)
- Magento (e-commerce)
"""

import json
import logging
import os
from typing import Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class ShopifyLoader(BaseLoader):
    """Load data from Shopify store.

    Example:
        loader = ShopifyLoader(
            shop_name="mystore",
            api_key="xxx",
            api_password="yyy"
        )
        docs = loader.load_folder("products")
    """

    def __init__(
        self,
        shop_name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_password: Optional[str] = None,
        api_version: str = "2024-01",
    ):
        self.shop_name = shop_name or os.environ.get("SHOPIFY_SHOP_NAME")
        self.api_key = api_key or os.environ.get("SHOPIFY_API_KEY")
        self.api_password = api_password or os.environ.get("SHOPIFY_API_PASSWORD")
        self.api_version = api_version
        self._session = None

    @property
    def source_name(self) -> str:
        return "shopify"

    def authenticate(self) -> bool:
        """Initialize Shopify API session."""
        try:
            import requests

            self._session = requests.Session()
            self._session.auth = (self.api_key, self.api_password)
            self._session.headers["Content-Type"] = "application/json"

            # Test connection
            resp = self._session.get(self._api_url("shop.json"))
            resp.raise_for_status()

            logger.info("Shopify authentication successful")
            return True
        except Exception as e:
            logger.error(f"Shopify authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Shopify")

    def _api_url(self, endpoint: str) -> str:
        return f"https://{self.shop_name}.myshopify.com/admin/api/{self.api_version}/{endpoint}"

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Shopify resource."""
        self._ensure_authenticated()
        try:
            resource_type, resource_id = doc_id.split("/", 1)
            resp = self._session.get(
                self._api_url(f"{resource_type}/{resource_id}.json")
            )
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{resource_type}_{resource_id}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load Shopify document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load Shopify resources by type."""
        self._ensure_authenticated()
        docs = []
        resource = folder_path.lower()

        resource_map = {
            "products": "products",
            "orders": "orders",
            "customers": "customers",
            "collections": "custom_collections",
        }

        endpoint = resource_map.get(resource, resource)

        try:
            resp = self._session.get(self._api_url(f"{endpoint}.json"))
            resp.raise_for_status()
            data = resp.json()

            items = data.get(endpoint, data.get(resource, []))

            for item in items:
                item_id = item.get("id", "")
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"{resource}/{item_id}",
                        filename=f"{resource}_{item_id}.json",
                        metadata={"type": resource, "id": str(item_id)},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load Shopify {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Shopify products."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                self._api_url("products.json"),
                params={"title": query, "limit": max_results},
            )
            resp.raise_for_status()

            for item in resp.json().get("products", []):
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"products/{item['id']}",
                        filename=f"product_{item['id']}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"Shopify search failed: {e}")

        return docs


class StripeLoader(BaseLoader):
    """Load data from Stripe.

    Example:
        loader = StripeLoader(api_key="sk_xxx")
        docs = loader.load_folder("charges")
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("STRIPE_SECRET_KEY")
        self._session = None

    @property
    def source_name(self) -> str:
        return "stripe"

    def authenticate(self) -> bool:
        """Initialize Stripe API."""
        try:
            import requests

            self._session = requests.Session()
            self._session.auth = (self.api_key, "")
            self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"

            # Test connection
            resp = self._session.get("https://api.stripe.com/v1/balance")
            resp.raise_for_status()

            logger.info("Stripe authentication successful")
            return True
        except Exception as e:
            logger.error(f"Stripe authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Stripe")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Stripe object."""
        self._ensure_authenticated()
        try:
            resource_type, resource_id = doc_id.split("/", 1)
            resp = self._session.get(
                f"https://api.stripe.com/v1/{resource_type}/{resource_id}"
            )
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{resource_type}_{resource_id}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load Stripe document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load Stripe objects by type."""
        self._ensure_authenticated()
        docs = []
        resource = folder_path.lower()

        try:
            resp = self._session.get(
                f"https://api.stripe.com/v1/{resource}",
                params={"limit": 100},
            )
            resp.raise_for_status()

            for item in resp.json().get("data", []):
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"{resource}/{item['id']}",
                        filename=f"{resource}_{item['id']}.json",
                        metadata={"type": resource, "id": item["id"]},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load Stripe {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Stripe doesn't support text search."""
        return []


class PayPalLoader(BaseLoader):
    """Load data from PayPal.

    Example:
        loader = PayPalLoader(client_id="xxx", client_secret="yyy")
        docs = loader.load_folder("transactions")
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        sandbox: bool = False,
    ):
        self.client_id = client_id or os.environ.get("PAYPAL_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("PAYPAL_CLIENT_SECRET")
        self.sandbox = sandbox
        self._session = None
        self._access_token = None

    @property
    def source_name(self) -> str:
        return "paypal"

    @property
    def _base_url(self) -> str:
        return (
            "https://api-m.sandbox.paypal.com"
            if self.sandbox
            else "https://api-m.paypal.com"
        )

    def authenticate(self) -> bool:
        """Authenticate with PayPal."""
        try:
            import requests

            self._session = requests.Session()

            # Get OAuth token
            resp = self._session.post(
                f"{self._base_url}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
            self._session.headers["Authorization"] = f"Bearer {self._access_token}"

            logger.info("PayPal authentication successful")
            return True
        except Exception as e:
            logger.error(f"PayPal authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with PayPal")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single PayPal resource."""
        self._ensure_authenticated()
        try:
            resp = self._session.get(f"{self._base_url}/v1/{doc_id}")
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
            logger.error(f"Failed to load PayPal document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load PayPal resources."""
        self._ensure_authenticated()
        docs = []
        resource = folder_path.lower()

        endpoint_map = {
            "transactions": "/v1/reporting/transactions",
            "payments": "/v2/payments/captures",
            "invoices": "/v2/invoicing/invoices",
        }

        endpoint = endpoint_map.get(resource, f"/v1/{resource}")

        try:
            resp = self._session.get(f"{self._base_url}{endpoint}")
            resp.raise_for_status()
            data = resp.json()

            items = (
                data.get("transaction_details", [])
                or data.get("items", [])
                or data.get("invoices", [])
            )

            for item in items:
                item_id = item.get("transaction_id", item.get("id", ""))
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"{resource}/{item_id}",
                        filename=f"{resource}_{item_id}.json",
                        metadata={"type": resource, "id": str(item_id)},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load PayPal {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """PayPal search not implemented."""
        return []


class AfterpayLoader(BaseLoader):
    """Load data from Afterpay/Clearpay."""

    def __init__(
        self,
        merchant_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        sandbox: bool = False,
    ):
        self.merchant_id = merchant_id or os.environ.get("AFTERPAY_MERCHANT_ID")
        self.secret_key = secret_key or os.environ.get("AFTERPAY_SECRET_KEY")
        self.sandbox = sandbox
        self._session = None

    @property
    def source_name(self) -> str:
        return "afterpay"

    @property
    def _base_url(self) -> str:
        return (
            "https://api.us-sandbox.afterpay.com"
            if self.sandbox
            else "https://api.us.afterpay.com"
        )

    def authenticate(self) -> bool:
        """Authenticate with Afterpay."""
        try:
            import requests

            self._session = requests.Session()
            self._session.auth = (self.merchant_id, self.secret_key)
            self._session.headers["Accept"] = "application/json"

            logger.info("Afterpay authentication configured")
            return True
        except Exception as e:
            logger.error(f"Afterpay authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Afterpay")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        self._ensure_authenticated()
        try:
            resp = self._session.get(f"{self._base_url}/v2/{doc_id}")
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
            logger.error(f"Failed to load Afterpay document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                f"{self._base_url}/v2/{folder_path}",
                params={"limit": 100},
            )
            resp.raise_for_status()

            for item in resp.json().get("results", []):
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"{folder_path}/{item.get('id', '')}",
                        filename=f"{folder_path}_{item.get('id', '')}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load Afterpay {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        return []


class WooCommerceLoader(BaseLoader):
    """Load data from WooCommerce store."""

    def __init__(
        self,
        store_url: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
    ):
        self.store_url = (store_url or os.environ.get("WOOCOMMERCE_URL", "")).rstrip(
            "/"
        )
        self.consumer_key = consumer_key or os.environ.get("WOOCOMMERCE_CONSUMER_KEY")
        self.consumer_secret = consumer_secret or os.environ.get(
            "WOOCOMMERCE_CONSUMER_SECRET"
        )
        self._session = None

    @property
    def source_name(self) -> str:
        return "woocommerce"

    def authenticate(self) -> bool:
        try:
            import requests

            self._session = requests.Session()
            self._session.auth = (self.consumer_key, self.consumer_secret)

            resp = self._session.get(f"{self.store_url}/wp-json/wc/v3/system_status")
            resp.raise_for_status()

            logger.info("WooCommerce authentication successful")
            return True
        except Exception as e:
            logger.error(f"WooCommerce authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with WooCommerce")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        self._ensure_authenticated()
        try:
            resource, resource_id = doc_id.split("/", 1)
            resp = self._session.get(
                f"{self.store_url}/wp-json/wc/v3/{resource}/{resource_id}"
            )
            resp.raise_for_status()
            data = resp.json()

            return LoadedDocument(
                content=json.dumps(data, indent=2, default=str),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{resource}_{resource_id}.json",
                metadata=data,
            )
        except Exception as e:
            logger.error(f"Failed to load WooCommerce document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                f"{self.store_url}/wp-json/wc/v3/{folder_path}",
                params={"per_page": 100},
            )
            resp.raise_for_status()

            for item in resp.json():
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"{folder_path}/{item.get('id', '')}",
                        filename=f"{folder_path}_{item.get('id', '')}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load WooCommerce {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(
                f"{self.store_url}/wp-json/wc/v3/products",
                params={"search": query, "per_page": max_results},
            )
            resp.raise_for_status()

            for item in resp.json():
                docs.append(
                    LoadedDocument(
                        content=json.dumps(item, indent=2, default=str),
                        source=self.source_name,
                        source_id=f"products/{item['id']}",
                        filename=f"product_{item['id']}.json",
                        metadata=item,
                    )
                )
        except Exception as e:
            logger.error(f"WooCommerce search failed: {e}")

        return docs


__all__ = [
    "ShopifyLoader",
    "StripeLoader",
    "PayPalLoader",
    "AfterpayLoader",
    "WooCommerceLoader",
]
