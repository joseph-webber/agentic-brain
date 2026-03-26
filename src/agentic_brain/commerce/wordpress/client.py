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

"""Async WordPress REST API client with full CMS coverage."""

from __future__ import annotations

import logging
import time
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from agentic_brain.rate_limiter import ProviderLimits, RateLimiter

from . import asyncio

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="WPModel")


class WordPressAPIError(RuntimeError):
    """Raised when the WordPress REST API returns an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class WPModel(BaseModel):
    """Base model for WordPress payload parsing."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class WPRenderedText(WPModel):
    """Rendered HTML/text wrapper returned by the WordPress REST API."""

    rendered: str = Field(default="", description="Rendered HTML/text content")


class WPPost(WPModel):
    """WordPress post response model."""

    id: int = Field(..., ge=0)
    slug: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    link: str | None = Field(default=None)
    title: WPRenderedText = Field(default_factory=WPRenderedText)
    content: WPRenderedText = Field(default_factory=WPRenderedText)
    excerpt: WPRenderedText = Field(default_factory=WPRenderedText)


class WPPage(WPModel):
    """WordPress page response model."""

    id: int = Field(..., ge=0)
    slug: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    link: str | None = Field(default=None)
    title: WPRenderedText = Field(default_factory=WPRenderedText)
    content: WPRenderedText = Field(default_factory=WPRenderedText)
    excerpt: WPRenderedText = Field(default_factory=WPRenderedText)


class WPMedia(WPModel):
    """WordPress media response model."""

    id: int = Field(..., ge=0)
    slug: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    link: str | None = Field(default=None)
    title: WPRenderedText = Field(default_factory=WPRenderedText)
    media_type: str | None = Field(default=None)
    mime_type: str | None = Field(default=None)
    source_url: str = Field(..., min_length=1)


class WPTerm(WPModel):
    """Shared structure for categories and tags."""

    id: int = Field(..., ge=0)
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    description: str | None = None
    count: int | None = None


class WPCategory(WPTerm):
    """WordPress category term."""

    parent: int | None = None


class WPTag(WPTerm):
    """WordPress tag term."""


class WPUser(WPModel):
    """WordPress user representation."""

    id: int = Field(..., ge=0)
    name: str = Field(..., min_length=1)
    slug: str | None = None
    email: str | None = None
    roles: list[str] = Field(default_factory=list)
    url: str | None = None


class WPComment(WPModel):
    """WordPress comment representation."""

    id: int = Field(..., ge=0)
    post: int = Field(..., ge=0)
    status: str = Field(..., min_length=1)
    author_name: str | None = None
    content: WPRenderedText = Field(default_factory=WPRenderedText)


class WordPressConfig(WPModel):
    """Connection, authentication, and rate-limit settings for WordPress.

    Notes:
        Legacy callers used ``url`` and ``password`` field names. Those are
        supported as aliases for ``base_url`` and ``application_password``.
    """

    base_url: str = Field(
        ...,
        alias="url",
        min_length=1,
        description="WordPress site base URL",
    )
    api_namespace: str = Field(
        default="wp-json/wp/v2", min_length=1, description="WordPress REST namespace"
    )
    username: str | None = Field(default=None, description="WordPress username")
    application_password: SecretStr | None = Field(
        default=None,
        alias="password",
        description="WordPress application password",
    )
    user_password: SecretStr | None = Field(
        default=None, description="Account password for JWT token fetch"
    )
    jwt_token: SecretStr | None = Field(
        default=None, description="Pre-generated JWT token"
    )
    jwt_token_endpoint: str | None = Field(
        default=None, description="Endpoint to exchange username/password for JWT"
    )
    oauth_client_id: str | None = Field(
        default=None, description="OAuth2 client identifier"
    )
    oauth_client_secret: SecretStr | None = Field(
        default=None, description="OAuth2 client secret"
    )
    oauth_token_url: str | None = Field(
        default=None, description="OAuth2 token endpoint"
    )
    oauth_scope: str | None = Field(default=None, description="OAuth scope request")
    timeout: float = Field(default=30.0, gt=0, le=120, description="Request timeout")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificates")
    user_agent: str = Field(
        default="agentic-brain/wordpress-client",
        min_length=3,
        description="User-Agent header sent to WordPress",
    )
    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_per_hour: int = Field(default=2000, ge=1)
    rate_limit_per_day: int = Field(default=10000, ge=1)
    cooldown_seconds: int = Field(default=60, ge=1)

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return normalized

    @field_validator("api_namespace", mode="before")
    @classmethod
    def normalize_namespace(cls, value: str) -> str:
        return value.strip().strip("/")

    @field_validator("jwt_token_endpoint", "oauth_token_url")
    @classmethod
    def normalize_endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_credentials(self) -> WordPressConfig:
        if self.application_password and not self.username:
            raise ValueError("username is required when application_password is set")

        if self.jwt_token_endpoint and not (self.username and self.user_password):
            raise ValueError(
                "username and user_password are required for JWT token exchange"
            )

        oauth_fields = [
            self.oauth_client_id,
            self.oauth_client_secret,
            self.oauth_token_url,
        ]
        if any(oauth_fields) and not all(oauth_fields):
            raise ValueError(
                "oauth_client_id, oauth_client_secret, and oauth_token_url "
                "must be provided together"
            )
        return self

    @property
    def rest_base_url(self) -> str:
        """Return the base URL for the configured REST namespace."""
        return f"{self.base_url}/{self.api_namespace}"

    def headers(self) -> dict[str, str]:
        """Default headers for each request."""
        return {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

    def basic_auth(self) -> httpx.Auth | None:
        """Return httpx basic auth when application-password auth is configured."""
        if self.username and self.application_password:
            return httpx.BasicAuth(
                username=self.username,
                password=self.application_password.get_secret_value(),
            )
        return None


# Backwards compatible alias
WPAuth = WordPressConfig


class WordPressClient:
    """Async WordPress REST client with posts, pages, media, taxonomy, and users."""

    def __init__(
        self,
        config: WordPressConfig,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None
        self.retries = max(1, retries)
        self.backoff_factor = max(0.1, backoff_factor)
        self._token_lock = asyncio.Lock()
        self._basic_auth = config.basic_auth()
        self._jwt_token = (
            config.jwt_token.get_secret_value() if config.jwt_token else None
        )
        self._oauth_token: str | None = None
        self._oauth_token_expiry: float = 0.0

        self.rate_limiter = rate_limiter or RateLimiter(auto_save=False)
        provider_name = f"wordpress:{urlparse(self.config.base_url).netloc}"
        self.provider_name = provider_name
        limits = ProviderLimits(
            name=provider_name,
            requests_per_minute=config.rate_limit_per_minute,
            requests_per_hour=config.rate_limit_per_hour,
            requests_per_day=config.rate_limit_per_day,
            cooldown_seconds=config.cooldown_seconds,
        )
        self.rate_limiter.add_provider(limits)

    async def __aenter__(self) -> WordPressClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.config.rest_base_url}/{endpoint}"

    async def _build_headers(
        self, extra_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        headers = dict(self.config.headers())
        bearer = await self._get_bearer_token()
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def _get_bearer_token(self) -> str | None:
        if self._oauth_token and time.time() < self._oauth_token_expiry - 30:
            return self._oauth_token
        if self._jwt_token:
            return self._jwt_token
        if self.config.oauth_token_url:
            await self._refresh_oauth_token()
            return self._oauth_token
        if self.config.jwt_token_endpoint:
            await self._refresh_jwt_token()
            return self._jwt_token
        return None

    async def _refresh_jwt_token(self, force: bool = False) -> None:
        if not self.config.jwt_token_endpoint or not (
            self.config.username and self.config.user_password
        ):
            return

        async with self._token_lock:
            if self._jwt_token and not force:
                return

            client = await self._get_client()
            payload = {
                "username": self.config.username,
                "password": self.config.user_password.get_secret_value(),
            }
            response = await client.post(
                self.config.jwt_token_endpoint,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self.config.user_agent,
                },
                auth=None,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise WordPressAPIError(
                    "Failed to obtain JWT token",
                    status_code=exc.response.status_code,
                    payload=exc.response.text,
                ) from exc
            data = response.json()
            token = data.get("token")
            if not token:
                raise WordPressAPIError(
                    "JWT token endpoint did not return token",
                    status_code=response.status_code,
                    payload=data,
                )
            self._jwt_token = token

    async def _refresh_oauth_token(self) -> None:
        if not (
            self.config.oauth_token_url
            and self.config.oauth_client_id
            and self.config.oauth_client_secret
        ):
            return

        async with self._token_lock:
            if self._oauth_token and time.time() < self._oauth_token_expiry - 30:
                return

            client = await self._get_client()
            data = {"grant_type": "client_credentials"}
            if self.config.oauth_scope:
                data["scope"] = self.config.oauth_scope
            auth = httpx.BasicAuth(
                self.config.oauth_client_id,
                self.config.oauth_client_secret.get_secret_value(),
            )
            response = await client.post(
                self.config.oauth_token_url,
                data=data,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self.config.user_agent,
                },
                auth=auth,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise WordPressAPIError(
                    "Failed to obtain OAuth token",
                    status_code=exc.response.status_code,
                    payload=exc.response.text,
                ) from exc

            payload = response.json()
            token = payload.get("access_token")
            if not token:
                raise WordPressAPIError(
                    "OAuth token endpoint did not return access_token",
                    status_code=response.status_code,
                    payload=payload,
                )
            expires_in = int(payload.get("expires_in", 3600))
            self._oauth_token = token
            self._oauth_token_expiry = time.time() + expires_in

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        headers: dict[str, str] | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = self._build_url(endpoint)
        attempt = 0
        last_error: Exception | None = None

        while attempt < self.retries:
            attempt += 1
            await self.rate_limiter.wait_for_capacity(self.provider_name)
            start = time.perf_counter()
            try:
                client = await self._get_client()
                request_headers = await self._build_headers(headers)
                auth = None if "Authorization" in request_headers else self._basic_auth
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    headers=request_headers,
                    auth=auth,
                    timeout=self.config.timeout,
                )

                if response.status_code == 401 and await self._handle_unauthorized():
                    continue

                if response.status_code == 429:
                    self.rate_limiter.record_rate_limit(self.provider_name)
                    await asyncio.sleep(self.backoff_factor * attempt)
                    continue

                if response.status_code >= 500:
                    last_error = WordPressAPIError(
                        f"WordPress server error ({response.status_code})",
                        status_code=response.status_code,
                        payload=response.text,
                    )
                    await asyncio.sleep(self.backoff_factor * attempt)
                    continue

                response.raise_for_status()
                elapsed_ms = (time.perf_counter() - start) * 1000
                self.rate_limiter.record_success(
                    self.provider_name, response_time_ms=elapsed_ms
                )
                if not expect_json:
                    return response
                if not response.content:
                    return None
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return response.text
            except httpx.RequestError as exc:
                last_error = exc
                await asyncio.sleep(self.backoff_factor * attempt)
            except httpx.HTTPStatusError as exc:
                raise WordPressAPIError(
                    f"WordPress request failed: {exc.response.text}",
                    status_code=exc.response.status_code,
                    payload=exc.response.text,
                ) from exc

        raise WordPressAPIError(
            f"WordPress request failed after {self.retries} attempts",
            payload=str(last_error),
        )

    async def _handle_unauthorized(self) -> bool:
        refreshed = False
        if self.config.oauth_token_url:
            await self._refresh_oauth_token()
            refreshed = True
        if self.config.jwt_token_endpoint:
            await self._refresh_jwt_token(force=True)
            refreshed = True
        return refreshed

    async def _get_many(
        self, endpoint: str, model: type[T], params: dict[str, Any] | None = None
    ) -> list[T]:
        payload = await self._request("GET", endpoint, params=params or None)
        adapter = TypeAdapter(list[model])
        return adapter.validate_python(payload)

    async def _get_one(self, endpoint: str, model: type[T]) -> T:
        payload = await self._request("GET", endpoint)
        return model.model_validate(payload)

    async def _mutate(
        self,
        endpoint: str,
        *,
        method: str,
        payload: dict[str, Any] | None = None,
        model: type[T] | None = None,
        data: dict[str, Any] | None = None,
        files: Any | None = None,
    ) -> T | dict[str, Any]:
        body = await self._request(
            method,
            endpoint,
            json=payload,
            data=data,
            files=files,
        )
        if model is None:
            return body
        return model.model_validate(body)

    # --- Posts -----------------------------------------------------------------
    async def list_posts(self, **params: Any) -> list[WPPost]:
        return await self._get_many("posts", WPPost, params=params or None)

    async def get_post(self, post_id: int) -> WPPost:
        return await self._get_one(f"posts/{post_id}", WPPost)

    async def create_post(self, data: dict[str, Any]) -> WPPost:
        return await self._mutate("posts", method="POST", payload=data, model=WPPost)

    async def update_post(self, post_id: int, data: dict[str, Any]) -> WPPost:
        return await self._mutate(
            f"posts/{post_id}", method="POST", payload=data, model=WPPost
        )

    async def delete_post(self, post_id: int, *, force: bool = False) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"posts/{post_id}",
            params={"force": str(force).lower()},
        )

    # Backwards-compatible aliases
    async def posts(self, **params: Any) -> list[WPPost]:
        return await self.list_posts(**params)

    async def post(self, post_id: int) -> WPPost:
        return await self.get_post(post_id)

    # --- Pages -----------------------------------------------------------------
    async def list_pages(self, **params: Any) -> list[WPPage]:
        return await self._get_many("pages", WPPage, params=params or None)

    async def get_page(self, page_id: int) -> WPPage:
        return await self._get_one(f"pages/{page_id}", WPPage)

    async def create_page(self, data: dict[str, Any]) -> WPPage:
        return await self._mutate("pages", method="POST", payload=data, model=WPPage)

    async def update_page(self, page_id: int, data: dict[str, Any]) -> WPPage:
        return await self._mutate(
            f"pages/{page_id}", method="POST", payload=data, model=WPPage
        )

    async def delete_page(self, page_id: int, *, force: bool = False) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"pages/{page_id}",
            params={"force": str(force).lower()},
        )

    async def pages(self, **params: Any) -> list[WPPage]:
        return await self.list_pages(**params)

    async def page(self, page_id: int) -> WPPage:
        return await self.get_page(page_id)

    # --- Media -----------------------------------------------------------------
    async def list_media(self, **params: Any) -> list[WPMedia]:
        return await self._get_many("media", WPMedia, params=params or None)

    async def get_media_item(self, media_id: int) -> WPMedia:
        return await self._get_one(f"media/{media_id}", WPMedia)

    async def upload_media(
        self,
        *,
        file_name: str,
        content: bytes,
        mime_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> WPMedia:
        files = {"file": (file_name, content, mime_type)}
        return await self._mutate(
            "media",
            method="POST",
            model=WPMedia,
            data=metadata or {},
            files=files,
        )

    async def delete_media(
        self, media_id: int, *, force: bool = False
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"media/{media_id}",
            params={"force": str(force).lower()},
        )

    async def media(self, **params: Any) -> list[WPMedia]:
        return await self.list_media(**params)

    async def media_item(self, media_id: int) -> WPMedia:
        return await self.get_media_item(media_id)

    # --- Categories & Tags -----------------------------------------------------
    async def list_categories(self, **params: Any) -> list[WPCategory]:
        return await self._get_many("categories", WPCategory, params=params or None)

    async def create_category(self, data: dict[str, Any]) -> WPCategory:
        return await self._mutate(
            "categories", method="POST", payload=data, model=WPCategory
        )

    async def list_tags(self, **params: Any) -> list[WPTag]:
        return await self._get_many("tags", WPTag, params=params or None)

    async def create_tag(self, data: dict[str, Any]) -> WPTag:
        return await self._mutate("tags", method="POST", payload=data, model=WPTag)

    # --- Users -----------------------------------------------------------------
    async def list_users(self, **params: Any) -> list[WPUser]:
        return await self._get_many("users", WPUser, params=params or None)

    async def create_user(self, data: dict[str, Any]) -> WPUser:
        return await self._mutate("users", method="POST", payload=data, model=WPUser)

    async def update_user(self, user_id: int, data: dict[str, Any]) -> WPUser:
        return await self._mutate(
            f"users/{user_id}", method="POST", payload=data, model=WPUser
        )

    # --- Comments --------------------------------------------------------------
    async def list_comments(self, **params: Any) -> list[WPComment]:
        return await self._get_many("comments", WPComment, params=params or None)

    async def update_comment_status(self, comment_id: int, status: str) -> WPComment:
        return await self._mutate(
            f"comments/{comment_id}",
            method="POST",
            payload={"status": status},
            model=WPComment,
        )

    async def delete_comment(
        self, comment_id: int, *, force: bool = False
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"comments/{comment_id}",
            params={"force": str(force).lower()},
        )

    # --- Custom Post Types -----------------------------------------------------
    async def list_custom_post_type(
        self, post_type: str, **params: Any
    ) -> list[dict[str, Any]]:
        return await self._request("GET", post_type, params=params or None)

    async def get_custom_post_type_item(
        self, post_type: str, item_id: int
    ) -> dict[str, Any]:
        return await self._request("GET", f"{post_type}/{item_id}")

    async def create_custom_post_type_item(
        self, post_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request("POST", post_type, json=data)

    async def update_custom_post_type_item(
        self, post_type: str, item_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request("POST", f"{post_type}/{item_id}", json=data)

    async def delete_custom_post_type_item(
        self, post_type: str, item_id: int, *, force: bool = False
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"{post_type}/{item_id}",
            params={"force": str(force).lower()},
        )


__all__ = [
    "WordPressAPIError",
    "WordPressClient",
    "WordPressConfig",
    "WPCategory",
    "WPMedia",
    "WPPage",
    "WPPost",
    "WPRenderedText",
    "WPTag",
    "WPUser",
    "WPComment",
    "WPAuth",
]
