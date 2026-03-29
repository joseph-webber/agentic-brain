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

"""Core WordPress REST API v2 client."""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from agentic_brain.commerce.wordpress import (
    WordPressAPIError,
    WordPressClient,
    WordPressConfig,
)
from agentic_brain.rate_limiter import RateLimiter

WPAPIError = WordPressAPIError


class WPBaseEndpoint:
    """Shared helpers for WordPress REST API endpoint wrappers."""

    def __init__(self, client: WPAPIClient, resource: str) -> None:
        self.client = client
        self.resource = resource.strip("/")

    def _path(self, *parts: Any) -> str:
        segments = [self.resource]
        for part in parts:
            if part is None:
                continue
            segments.append(str(part).strip("/"))
        return "/".join(segments)

    def _params(self, params: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not params:
            return None
        return {key: value for key, value in params.items() if value is not None}


class WPAPIClient:
    """Async WordPress REST API client with full v2 coverage."""

    def __init__(
        self,
        config: WordPressConfig,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retries: int = 3,
        backoff_factor: float = 0.5,
        graphql_endpoint: str | None = None,
        acf_namespace: str = "acf/v3",
    ) -> None:
        self.config = config
        self.graphql_endpoint = graphql_endpoint or f"{config.base_url}/graphql"
        self.acf_namespace = acf_namespace.strip("/")
        self._client = WordPressClient(
            config,
            client=client,
            rate_limiter=rate_limiter,
            retries=retries,
            backoff_factor=backoff_factor,
        )

        from .blocks import BlocksAPI
        from .categories import CategoriesAPI, TagsAPI, TaxonomiesAPI
        from .comments import CommentsAPI
        from .custom_post_types import CustomPostTypesAPI
        from .media import MediaAPI
        from .menus import MenusAPI
        from .pages import PagesAPI
        from .plugins import PluginsAPI
        from .posts import PostsAPI
        from .search import SearchAPI
        from .settings import SettingsAPI
        from .themes import ThemesAPI
        from .users import UsersAPI

        self.posts = PostsAPI(self)
        self.pages = PagesAPI(self)
        self.media = MediaAPI(self)
        self.users = UsersAPI(self)
        self.comments = CommentsAPI(self)
        self.categories = CategoriesAPI(self)
        self.tags = TagsAPI(self)
        self.taxonomies = TaxonomiesAPI(self)
        self.blocks = BlocksAPI(self)
        self.menus = MenusAPI(self)
        self.settings = SettingsAPI(self)
        self.themes = ThemesAPI(self)
        self.plugins = PluginsAPI(self)
        self.search = SearchAPI(self)
        self.custom_post_types = CustomPostTypesAPI(self)

    async def __aenter__(self) -> WPAPIClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    def build_namespace_url(self, namespace: str, endpoint: str | None = None) -> str:
        base = f"{self.config.base_url}/wp-json/{namespace.strip('/')}"
        if endpoint:
            return f"{base}/{endpoint.lstrip('/')}"
        return base

    def acf_url(self, endpoint: str | None = None) -> str:
        return self.build_namespace_url(self.acf_namespace, endpoint)

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        headers: Mapping[str, str] | None = None,
        expect_json: bool = True,
    ) -> Any:
        return await self._client._request(
            method,
            endpoint,
            params=dict(params) if params else None,
            json=json_body,
            data=data,
            files=files,
            headers=dict(headers) if headers else None,
            expect_json=expect_json,
        )

    async def request_raw(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        response = await self.request(
            method,
            endpoint,
            params=params,
            json_body=json_body,
            data=data,
            files=files,
            headers=headers,
            expect_json=False,
        )
        if not isinstance(response, httpx.Response):
            raise WordPressAPIError("Expected raw response from WordPress")
        return response

    async def get(
        self, endpoint: str, *, params: Mapping[str, Any] | None = None
    ) -> Any:
        return await self.request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return await self.request(
            "POST",
            endpoint,
            params=params,
            json_body=json_body,
            data=data,
            files=files,
            headers=headers,
        )

    async def put(self, endpoint: str, *, json_body: Any | None = None) -> Any:
        return await self.request("PUT", endpoint, json_body=json_body)

    async def patch(self, endpoint: str, *, json_body: Any | None = None) -> Any:
        return await self.request("PATCH", endpoint, json_body=json_body)

    async def delete(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self.request("DELETE", endpoint, params=params)

    async def graphql_query(
        self,
        query: str,
        *,
        variables: Mapping[str, Any] | None = None,
        operation_name: str | None = None,
        endpoint: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = dict(variables)
        if operation_name is not None:
            payload["operationName"] = operation_name
        graphql_endpoint = endpoint or self.graphql_endpoint
        return await self.request(
            "POST",
            graphql_endpoint,
            json_body=payload,
            headers=headers,
        )

    async def close(self) -> None:
        await self._client.close()
