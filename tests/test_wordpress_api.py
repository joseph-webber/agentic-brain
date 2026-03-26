# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import asyncio
import base64

import httpx
import pytest
from pydantic import ValidationError

from agentic_brain.commerce.wordpress import (
    WordPressAPIError,
    WordPressClient,
    WordPressConfig,
    WPAuth,
)
from agentic_brain.rate_limiter import RateLimiter


def test_wordpress_config_validates_and_normalizes():
    config = WordPressConfig(
        base_url="https://example.com///",
        api_namespace="/wp-json/wp/v2/",
        username="editor",
        application_password="pass app word",
    )
    assert config.rest_base_url == "https://example.com/wp-json/wp/v2"
    assert "User-Agent" in config.headers()
    assert config.basic_auth() is not None

    with pytest.raises(ValidationError):
        WordPressConfig(base_url="example.com")

    with pytest.raises(ValidationError):
        WordPressConfig(
            base_url="https://example.com",
            oauth_client_id="client",
            oauth_token_url="https://example.com/oauth",
        )

    with pytest.raises(ValidationError):
        WordPressConfig(
            base_url="https://example.com",
            application_password="secret",
        )


@pytest.mark.asyncio
async def test_application_password_auth_adds_basic_header():
    config = WPAuth(
        base_url="https://example.com",
        username="editor",
        application_password="app-password",
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization", "")
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "slug": "demo",
                    "status": "publish",
                    "title": {"rendered": "Demo"},
                    "content": {"rendered": "<p>Demo</p>"},
                    "excerpt": {"rendered": "Demo"},
                }
            ],
        )

    transport = httpx.MockTransport(handler)
    limiter = RateLimiter(auto_save=False)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WordPressClient(
            config=config,
            client=http_client,
            rate_limiter=limiter,
        )
        await client.list_posts()

    assert captured["auth"].startswith("Basic ")
    decoded = base64.b64decode(captured["auth"].split(" ", 1)[1]).decode()
    assert decoded == "editor:app-password"


@pytest.mark.asyncio
async def test_jwt_token_refresh_on_unauthorized(monkeypatch):
    attempts = {"posts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jwt-token"):
            return httpx.Response(200, json={"token": "fresh-token"})
        if request.url.path.endswith("/posts"):
            attempts["posts"] += 1
            if attempts["posts"] == 1:
                return httpx.Response(401, json={"code": "rest_not_logged_in"})
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 42,
                        "slug": "secured",
                        "status": "publish",
                        "title": {"rendered": "Secured"},
                        "content": {"rendered": "<p>Secure</p>"},
                        "excerpt": {"rendered": "Secure"},
                    }
                ],
            )
        raise AssertionError(f"Unexpected URL {request.url}")

    transport = httpx.MockTransport(handler)
    config = WordPressConfig(
        base_url="https://example.com",
        username="editor",
        user_password="wp-password",
        jwt_token_endpoint="https://example.com/jwt-token",
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WordPressClient(
            config=config,
            client=http_client,
            rate_limiter=RateLimiter(auto_save=False),
        )
        result = await client.list_posts()

    assert result[0].slug == "secured"
    assert attempts["posts"] == 2


@pytest.mark.asyncio
async def test_oauth_token_flow(monkeypatch):
    calls = {"token": 0, "posts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            calls["token"] += 1
            return httpx.Response(
                200,
                json={"access_token": "oauth-token", "expires_in": 3600},
            )
        if request.url.path.endswith("/posts"):
            calls["posts"] += 1
            assert request.headers["authorization"] == "Bearer oauth-token"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 99,
                        "slug": "oauth",
                        "status": "publish",
                        "title": {"rendered": "OAuth"},
                        "content": {"rendered": "<p>OAuth</p>"},
                        "excerpt": {"rendered": "OAuth"},
                    }
                ],
            )
        raise AssertionError(f"Unexpected URL {request.url}")

    transport = httpx.MockTransport(handler)
    config = WordPressConfig(
        base_url="https://example.com",
        oauth_client_id="client",
        oauth_client_secret="secret",
        oauth_token_url="https://example.com/oauth/token",
        oauth_scope="content",
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WordPressClient(
            config=config,
            client=http_client,
            rate_limiter=RateLimiter(auto_save=False),
        )
        posts = await client.list_posts()

    assert posts[0].slug == "oauth"
    assert calls == {"token": 1, "posts": 1}


@pytest.mark.asyncio
async def test_retries_on_rate_limit(monkeypatch):
    attempts = 0

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("agentic_brain.commerce.wordpress.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"code": "too_many_requests"})
        return httpx.Response(
            200,
            json=[
                {
                    "id": 5,
                    "slug": "retried",
                    "status": "publish",
                    "title": {"rendered": "Retry"},
                    "content": {"rendered": "<p>Retry</p>"},
                    "excerpt": {"rendered": "Retry"},
                }
            ],
        )

    transport = httpx.MockTransport(handler)
    config = WPAuth(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WordPressClient(
            config=config,
            client=http_client,
            rate_limiter=RateLimiter(auto_save=False),
        )
        posts = await client.list_posts()

    assert posts[0].slug == "retried"
    assert attempts == 2


@pytest.mark.asyncio
async def test_custom_post_type_support():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": 1, "meta": {"field": "value"}}],
            )
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"id": 2, "meta": {"field": "created"}},
            )
        if request.method == "DELETE":
            return httpx.Response(200, json={"deleted": True})
        raise AssertionError(f"Unexpected method {request.method}")

    transport = httpx.MockTransport(handler)
    config = WPAuth(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WordPressClient(
            config=config,
            client=http_client,
            rate_limiter=RateLimiter(auto_save=False),
        )
        items = await client.list_custom_post_type("products")
        created = await client.create_custom_post_type_item(
            "products", {"title": "Product"}
        )
        deleted = await client.delete_custom_post_type_item("products", 2)

    assert items[0]["meta"]["field"] == "value"
    assert created["meta"]["field"] == "created"
    assert deleted["deleted"] is True


@pytest.mark.asyncio
async def test_media_upload_uses_multipart():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["content_type"] = request.headers.get("content-type", "")
        body = request.content.decode(errors="ignore")
        assert 'filename="hero.png"' in body
        assert "alt_text" in body
        return httpx.Response(
            200,
            json={
                "id": 77,
                "slug": "hero",
                "status": "inherit",
                "title": {"rendered": "Hero"},
                "media_type": "image",
                "mime_type": "image/png",
                "source_url": "https://example.com/hero.png",
            },
        )

    transport = httpx.MockTransport(handler)
    config = WPAuth(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WordPressClient(
            config=config,
            client=http_client,
            rate_limiter=RateLimiter(auto_save=False),
        )
        media = await client.upload_media(
            file_name="hero.png",
            content=b"<binary>",
            mime_type="image/png",
            metadata={"alt_text": "Hero image"},
        )

    assert "multipart/form-data" in observed["content_type"]
    assert media.slug == "hero"
