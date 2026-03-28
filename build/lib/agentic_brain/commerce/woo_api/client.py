# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Base WooCommerce REST API client.

The :class:`WooAPIClient` encapsulates authentication, pagination, and batch helpers
for every resource-specific module. It is intentionally async-first and exposes a
:py:meth:`run_sync` helper for ergonomic synchronous wrappers.

Example
-------
>>> from agentic_brain.commerce.woo_api import WooCommerceAPI
>>> woo = WooCommerceAPI("https://shop.example", "ck_123", "cs_456")
>>> products = woo.products.sync.list(search="Notebook")
>>> len(products)
3
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Mapping, MutableMapping, Sequence

import aiohttp

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_PER_PAGE = 100


class WooAPIError(RuntimeError):
    """Raised when the WooCommerce API returns a non-successful status code."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        url: str,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.url = url
        self.payload = payload


class WooAPIClient:
    """Async-first HTTP client for the WooCommerce REST API."""

    def __init__(
        self,
        base_url: str,
        consumer_key: str,
        consumer_secret: str,
        *,
        api_namespace: str = "wc",
        api_version: str = "v3",
        timeout: float = DEFAULT_TIMEOUT,
        verify_ssl: bool = True,
        user_agent: str = "AgenticBrainWooAPI/1.0",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        base_url = base_url.rstrip("/")
        if not base_url:
            raise ValueError("base_url must be provided")
        self.base_url = base_url
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.api_namespace = api_namespace.strip("/")
        self.api_version = api_version.strip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.user_agent = user_agent
        self._session = session
        self._connector: aiohttp.TCPConnector | None = None

    @property
    def api_root(self) -> str:
        """Return the fully qualified REST root."""

        return (
            f"{self.base_url}/wp-json/{self.api_namespace}/{self.api_version}".rstrip(
                "/"
            )
        )

    async def close(self) -> None:
        """Close the underlying :mod:`aiohttp` session."""

        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector and not self._connector.closed:
            self._connector.close()
        self._session = None
        self._connector = None

    def close_sync(self) -> None:
        """Synchronously close the HTTP session."""

        self.run_sync(self.close())

    def run_sync(self, awaitable: Awaitable[Any]) -> Any:
        """Run an awaitable in a fresh event loop.

        Sync wrappers call this utility so that synchronous contexts never have to
        manage asyncio plumbing.
        """

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        else:
            if loop.is_running():
                raise RuntimeError("Cannot call sync wrapper from a running event loop")
        return asyncio.run(awaitable)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        self._connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self._session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(self.consumer_key, self.consumer_secret),
            connector=self._connector,
            timeout=timeout,
            headers={"User-Agent": self.user_agent, "Content-Type": "application/json"},
        )
        return self._session

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return f"{self.api_root}/{endpoint}"

    @staticmethod
    def _clean_params(params: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        if not params:
            return None
        cleaned = {key: value for key, value in params.items() if value is not None}
        return cleaned or None

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        """Perform an HTTP request against the WooCommerce API."""

        session = await self._ensure_session()
        url = self._build_url(endpoint)
        async with session.request(
            method.upper(),
            url,
            params=self._clean_params(params),
            json=json_body,
        ) as response:
            payload = await self._parse_response(response)
            if response.status >= 400:
                message = (
                    payload.get("message")
                    if isinstance(payload, dict)
                    else str(payload)
                )
                raise WooAPIError(
                    message
                    or f"WooCommerce request failed with status {response.status}",
                    status=response.status,
                    url=url,
                    payload=payload,
                )
            return payload

    async def paginate(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Any]:
        """Retrieve all pages for a list endpoint."""

        collected: list[Any] = []
        page = 1
        per_page = per_page or DEFAULT_PER_PAGE
        while True:
            page_params: dict[str, Any] = {"page": page, "per_page": per_page}
            if params:
                page_params.update(params)
            page_data = await self.request("GET", endpoint, params=page_params)
            if not isinstance(page_data, list):
                LOGGER.debug(
                    "Received non-list payload for %s pagination; returning as-is",
                    endpoint,
                )
                return page_data  # type: ignore[return-value]
            collected.extend(page_data)
            if len(page_data) < per_page:
                break
            page += 1
            if max_pages is not None and page > max_pages:
                break
        return collected

    async def batch(
        self,
        endpoint: str,
        payload: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> Any:
        """Execute a WooCommerce batch endpoint."""

        if not payload:
            raise ValueError("batch payload must not be empty")
        filtered = {
            key: list(value)
            for key, value in payload.items()
            if value is not None and len(value) > 0
        }
        if not filtered:
            raise ValueError("batch payload must contain at least one set of records")
        return await self.request("POST", endpoint, json_body=filtered)

    @staticmethod
    async def _parse_response(response: aiohttp.ClientResponse) -> Any:
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            return await response.json(loads=json.loads)
        text = await response.text()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


class WooResourceAPI:
    """Base helper used by resource modules to provide sync wrappers."""

    def __init__(self, client: WooAPIClient) -> None:
        self.client = client
        self.sync = WooResourceSyncProxy(self)

    def _sync(self, awaitable: Awaitable[Any]) -> Any:
        return self.client.run_sync(awaitable)

    @staticmethod
    def _clean(mapping: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        if not mapping:
            return None
        cleaned = {k: v for k, v in mapping.items() if v is not None}
        return cleaned or None

    @staticmethod
    def _build_batch_payload(
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Sequence[Mapping[str, Any]]]:
        payload: dict[str, Sequence[Mapping[str, Any]]] = {}
        if create:
            payload["create"] = list(create)
        if update:
            payload["update"] = list(update)
        if delete:
            payload["delete"] = list(delete)
        if not payload:
            raise ValueError("At least one of create, update, delete must be provided")
        return payload


class WooResourceSyncProxy:
    """Proxy exposing synchronous wrappers for every coroutine on a resource."""

    def __init__(self, resource: WooResourceAPI) -> None:
        self._resource = resource

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._resource, name)
        if not callable(attribute):
            raise AttributeError(name)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = attribute(*args, **kwargs)
            if asyncio.iscoroutine(result):
                return self._resource._sync(result)
            return result

        return wrapper
