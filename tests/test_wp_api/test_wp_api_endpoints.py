# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

import httpx
import pytest

from agentic_brain.commerce.wordpress import WordPressConfig
from agentic_brain.commerce.wp_api import WPAPIClient


@pytest.mark.asyncio
async def test_posts_and_pages_endpoints():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = (
            request.url.query.decode()
            if isinstance(request.url.query, bytes)
            else request.url.query
        )
        calls.append((request.method, request.url.path, query))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    config = WordPressConfig(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WPAPIClient(config, client=http_client)
        await client.posts.list()
        await client.posts.get(1)
        await client.posts.list_revisions(1)
        await client.posts.get_revision(1, 2)
        await client.posts.list_autosaves(1)
        await client.posts.create({"title": "Hello"})
        await client.posts.update(1, {"title": "Updated"})
        await client.posts.delete(1, force=True)
        await client.pages.list()
        await client.pages.get(3)
        await client.pages.set_featured_media(3, 99)

    assert ("GET", "/wp-json/wp/v2/posts", "") in calls
    assert ("GET", "/wp-json/wp/v2/posts/1", "") in calls
    assert ("GET", "/wp-json/wp/v2/posts/1/revisions", "") in calls
    assert ("GET", "/wp-json/wp/v2/posts/1/revisions/2", "") in calls
    assert ("GET", "/wp-json/wp/v2/posts/1/autosaves", "") in calls
    assert ("POST", "/wp-json/wp/v2/posts", "") in calls
    assert ("POST", "/wp-json/wp/v2/posts/1", "") in calls
    assert ("DELETE", "/wp-json/wp/v2/posts/1", "force=true") in calls
    assert ("GET", "/wp-json/wp/v2/pages", "") in calls
    assert ("GET", "/wp-json/wp/v2/pages/3", "") in calls


@pytest.mark.asyncio
async def test_media_upload_and_sizes():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            (
                request.method,
                request.url.path,
                request.headers.get("content-disposition"),
            )
        )
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"media_details": {"sizes": {"full": {"file": "hero.jpg"}}}},
            )
        return httpx.Response(200, json={"id": 1})

    transport = httpx.MockTransport(handler)
    config = WordPressConfig(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WPAPIClient(config, client=http_client)
        await client.media.upload(
            file_name="hero.jpg",
            content=b"data",
            mime_type="image/jpeg",
            metadata={"title": "Hero"},
        )
        sizes = await client.media.get_sizes(1)

    assert sizes["full"]["file"] == "hero.jpg"
    assert ("POST", "/wp-json/wp/v2/media", 'attachment; filename="hero.jpg"') in calls


@pytest.mark.asyncio
async def test_users_comments_and_taxonomies():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = (
            request.url.query.decode()
            if isinstance(request.url.query, bytes)
            else request.url.query
        )
        calls.append((request.method, request.url.path, query))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    config = WordPressConfig(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WPAPIClient(config, client=http_client)
        await client.users.list()
        await client.users.me()
        await client.users.update_roles(5, ["editor"])
        await client.comments.approve(12)
        await client.comments.spam(15)
        await client.categories.list()
        await client.tags.create({"name": "release"})
        await client.taxonomies.list_taxonomies()
        await client.taxonomies.create_term("genres", {"name": "Sci-Fi"})

    assert ("GET", "/wp-json/wp/v2/users", "") in calls
    assert ("GET", "/wp-json/wp/v2/users/me", "") in calls
    assert ("POST", "/wp-json/wp/v2/users/5", "") in calls
    assert ("POST", "/wp-json/wp/v2/comments/12", "") in calls
    assert ("POST", "/wp-json/wp/v2/comments/15", "") in calls
    assert ("GET", "/wp-json/wp/v2/categories", "") in calls
    assert ("POST", "/wp-json/wp/v2/tags", "") in calls
    assert ("GET", "/wp-json/wp/v2/taxonomies", "") in calls
    assert ("POST", "/wp-json/wp/v2/genres", "") in calls


@pytest.mark.asyncio
async def test_blocks_menus_settings_themes_plugins_search_custom_types():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = (
            request.url.query.decode()
            if isinstance(request.url.query, bytes)
            else request.url.query
        )
        calls.append((request.method, request.url.path, query))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    config = WordPressConfig(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WPAPIClient(config, client=http_client)
        await client.blocks.list_block_types()
        await client.blocks.list_block_patterns()
        await client.blocks.search_block_directory(search="gallery")
        await client.menus.list_menus()
        await client.menus.list_menu_items(menu_id=7)
        await client.settings.get_settings()
        await client.themes.list()
        await client.themes.activate("twentytwenty")
        await client.plugins.list()
        await client.plugins.activate("akismet/akismet")
        await client.search.search("headless", type="post")
        await client.custom_post_types.list_types()
        await client.custom_post_types.create_item("products", {"title": "New"})

    assert ("GET", "/wp-json/wp/v2/block-types", "") in calls
    assert ("GET", "/wp-json/wp/v2/block-patterns/patterns", "") in calls
    assert ("GET", "/wp-json/wp/v2/block-directory/search", "search=gallery") in calls
    assert ("GET", "/wp-json/wp/v2/menus", "") in calls
    assert ("GET", "/wp-json/wp/v2/menu-items", "menus=7") in calls
    assert ("GET", "/wp-json/wp/v2/settings", "") in calls
    assert ("GET", "/wp-json/wp/v2/themes", "") in calls
    assert ("POST", "/wp-json/wp/v2/themes/twentytwenty", "") in calls
    assert ("GET", "/wp-json/wp/v2/plugins", "") in calls
    assert ("POST", "/wp-json/wp/v2/plugins/akismet/akismet", "") in calls
    assert ("GET", "/wp-json/wp/v2/search", "search=headless&type=post") in calls
    assert ("GET", "/wp-json/wp/v2/types", "") in calls
    assert ("POST", "/wp-json/wp/v2/products", "") in calls
