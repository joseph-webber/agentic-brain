# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agentic_brain.commerce.chatbot import (
    WordPressChatWidgetConfig,
    WordPressHookConfig,
    WPAdminBot,
    WPAdminBotConfig,
    WPContentBot,
    WPContentBotConfig,
    generate_wp_hooks_plugin,
    generate_wp_widget_plugin,
)
from agentic_brain.commerce.wordpress import WPCategory, WPPost, WPTag


class FakeWP:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def posts(self, **params):
        self.calls.append(("posts", params))
        if params.get("search"):
            return [
                WPPost.model_validate(
                    {
                        "id": 1,
                        "slug": "cats",
                        "status": "publish",
                        "link": "https://example.com/cats",
                        "title": {"rendered": "All About Cats"},
                        "content": {"rendered": ""},
                        "excerpt": {"rendered": ""},
                    }
                )
            ]
        return [
            WPPost.model_validate(
                {
                    "id": 2,
                    "slug": "new",
                    "status": "publish",
                    "link": "https://example.com/new",
                    "title": {"rendered": "Newest"},
                    "content": {"rendered": ""},
                    "excerpt": {"rendered": ""},
                }
            )
        ]

    async def pages(self, **params):
        self.calls.append(("pages", params))
        return []

    async def list_categories(self, **params):
        self.calls.append(("categories", params))
        return [
            WPCategory.model_validate(
                {"id": 10, "name": "News", "slug": "news", "count": 3}
            )
        ]

    async def list_tags(self, **params):
        self.calls.append(("tags", params))
        return [
            WPTag.model_validate({"id": 20, "name": "AI", "slug": "ai", "count": 4})
        ]


class FakeWoo:
    async def search_products(self, query: str):
        return [
            {
                "name": "Cat Toy",
                "permalink": "https://shop.example.com/cat-toy",
                "price": "9.99",
            }
        ]


@pytest.mark.asyncio
async def test_wp_content_bot_search_posts_pages_products():
    wp = FakeWP()
    woo = FakeWoo()
    bot = WPContentBot(wp, woo=woo, config=WPContentBotConfig(max_results=3))

    resp = await bot.handle("Find articles about cats")
    assert resp and "Search results for: cats" in resp
    assert "All About Cats" in resp
    assert "Cat Toy" in resp


@pytest.mark.asyncio
async def test_wp_content_bot_whats_new():
    wp = FakeWP()
    bot = WPContentBot(
        wp, config=WPContentBotConfig(max_results=1, include_products=False)
    )
    resp = await bot.handle("What's new on the blog?")
    assert resp and "Newest blog posts" in resp
    assert "Newest" in resp


@pytest.mark.asyncio
async def test_wp_content_bot_categories_tags():
    wp = FakeWP()
    bot = WPContentBot(wp)

    cats = await bot.handle("list categories")
    assert cats and "Top categories" in cats and "News" in cats

    tags = await bot.handle("list tags")
    assert tags and "Top tags" in tags and "AI" in tags


@dataclass
class FakeAdminAPI:
    last_update_fields: dict | None = None

    async def create_post(self, *, title: str, content: str, status: str = "draft"):
        return {"id": 101, "link": "https://example.com/wp-admin/post.php?post=101"}

    async def update_post(self, post_id: int, **fields):
        self.last_update_fields = {"post_id": post_id, **fields}
        return {"id": post_id, "link": "https://example.com/?p=101"}

    async def list_comments(self, *, status: str = "hold", per_page: int = 10):
        return [
            {"id": 501, "author_name": "Alice", "link": "https://example.com/?c=501"}
        ]

    async def find_page(self, query: str):
        return {"id": 77, "link": "https://example.com/page"}

    async def update_page(self, page_id: int, *, content: str):
        return {"id": page_id, "link": "https://example.com/page"}


@pytest.mark.asyncio
async def test_wp_admin_bot_create_and_schedule():
    api = FakeAdminAPI()
    bot = WPAdminBot(api, config=WPAdminBotConfig(default_schedule_hour=9))

    created = await bot.handle("Create a new draft post about test", session_id="s1")
    assert created and "Created draft post" in created and "#101" in created

    scheduled = await bot.handle("Schedule post for tomorrow", session_id="s1")
    assert scheduled and "Scheduled post #101" in scheduled
    assert api.last_update_fields and api.last_update_fields["status"] == "future"


@pytest.mark.asyncio
async def test_wp_admin_bot_pending_comments_and_update_page():
    api = FakeAdminAPI()
    bot = WPAdminBot(api)

    comments = await bot.handle("Show me pending comments")
    assert comments and "Pending comments" in comments and "Comment #501" in comments

    updated = await bot.handle("Update page About with <p>Hi</p>")
    assert updated and "Updated page #77" in updated


def test_wp_widget_generation_contains_accessible_markup():
    cfg = WordPressChatWidgetConfig(api_url="https://example.com/api/chat")
    files = generate_wp_widget_plugin(cfg)
    assert f"{cfg.plugin_slug}.php" in files
    assert "assets/chat-widget.js" in files
    assert "aria-label" in files["assets/chat-widget.js"]
    assert "@media" in files["assets/chat-widget.css"]


def test_wp_hooks_generation_includes_wp_and_woo_hooks():
    cfg = WordPressHookConfig(webhook_url="https://example.com/webhooks/wordpress")
    files = generate_wp_hooks_plugin(cfg)
    php = files[f"{cfg.plugin_slug}.php"]
    assert "save_post" in php
    assert "woocommerce_new_order" in php
    assert cfg.webhook_url in php
