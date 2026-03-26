# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""WordPress admin dashboard assistant.

This bot is designed to be paired with authenticated WordPress REST API access
(application passwords are recommended).

Supported intents:
- "Create a new draft post about ..."
- "Schedule post for tomorrow" (schedules the last created post)
- "Show me pending comments"
- "Update page X with Y" (find by search + update)

All REST calls go through :class:`WPAdminAPI` which uses the same auth model as
:class:`agentic_brain.commerce.wordpress.WordPressClient`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from agentic_brain.commerce.wordpress import WordPressClient


@dataclass(slots=True)
class WPAdminBotConfig:
    """Configuration for :class:`WPAdminBot`."""

    default_schedule_hour: int = 9
    max_comment_results: int = 10


class WPAdminAPI:
    """Authenticated helper for WordPress write operations.

    This wraps :class:`agentic_brain.commerce.wordpress.WordPressClient` so we
    reuse its auth, retries, and rate limiting.
    """

    def __init__(self, wp: WordPressClient) -> None:
        self.wp = wp

    async def create_post(
        self,
        *,
        title: str,
        content: str,
        status: str = "draft",
    ) -> dict[str, Any]:
        post = await self.wp.create_post(
            {"title": title, "content": content, "status": status}
        )
        return post.model_dump()

    async def update_post(self, post_id: int, **fields: Any) -> dict[str, Any]:
        post = await self.wp.update_post(post_id, dict(fields))
        return post.model_dump()

    async def list_comments(
        self,
        *,
        status: str = "hold",
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        comments = await self.wp.list_comments(
            status=status, per_page=per_page, order="desc"
        )
        return [comment.model_dump() for comment in comments]

    async def find_page(self, query: str) -> dict[str, Any] | None:
        pages = await self.wp.pages(search=query, per_page=5, orderby="relevance")
        if not pages:
            return None
        return pages[0].model_dump()

    async def update_page(self, page_id: int, *, content: str) -> dict[str, Any]:
        page = await self.wp.update_page(page_id, {"content": content})
        return page.model_dump()


class WPAdminBot:
    """Rule-based WordPress admin assistant."""

    def __init__(
        self,
        api: WPAdminAPI,
        *,
        config: WPAdminBotConfig | None = None,
    ) -> None:
        self.api = api
        self.config = config or WPAdminBotConfig()
        self._last_post_id_by_session: dict[str, int] = {}

    async def handle(self, message: str, *, session_id: str = "default") -> str | None:
        text = (message or "").strip()
        lowered = text.lower()

        match = re.match(r"create (?:a )?(?:new )?(?:draft )?post about (.+)", lowered)
        if match:
            topic = match.group(1).strip(" ?\t\n")
            return await self.create_draft_post(topic, session_id=session_id)

        if lowered in {
            "schedule post for tomorrow",
            "schedule it for tomorrow",
            "schedule for tomorrow",
        }:
            return await self.schedule_last_post_for_tomorrow(session_id=session_id)

        if lowered in {
            "show me pending comments",
            "pending comments",
            "show pending comments",
        }:
            return await self.show_pending_comments()

        match = re.match(
            r"update page (.+?) with (.+)", text, flags=re.IGNORECASE | re.DOTALL
        )
        if match:
            page_query = match.group(1).strip()
            new_content = match.group(2).strip()
            return await self.update_page(page_query, new_content)

        return None

    async def create_draft_post(self, topic: str, *, session_id: str) -> str:
        title = topic.strip().title()
        content = (
            f"<p><strong>Draft outline:</strong> {topic}</p>\n"
            "<ul>\n"
            "  <li>Intro</li>\n"
            "  <li>Main points</li>\n"
            "  <li>Call to action</li>\n"
            "</ul>\n"
        )
        post = await self.api.create_post(title=title, content=content, status="draft")
        post_id = int(post.get("id"))
        self._last_post_id_by_session[session_id] = post_id
        link = post.get("link") or ""
        return f"Created draft post #{post_id}: {title}{f' — {link}' if link else ''}"

    async def schedule_last_post_for_tomorrow(self, *, session_id: str) -> str:
        post_id = self._last_post_id_by_session.get(session_id)
        if not post_id:
            return "I don't know which post to schedule yet. Create a draft post first."

        now = datetime.now(UTC)
        target = (now + timedelta(days=1)).replace(
            hour=self.config.default_schedule_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        updated = await self.api.update_post(
            post_id,
            status="future",
            date_gmt=target.isoformat().replace("+00:00", "Z"),
        )
        link = updated.get("link") or ""
        return f"Scheduled post #{post_id} for {target.date().isoformat()} {self.config.default_schedule_hour:02d}:00 UTC{f' — {link}' if link else ''}"

    async def show_pending_comments(self) -> str:
        comments = await self.api.list_comments(
            status="hold",
            per_page=self.config.max_comment_results,
        )
        if not comments:
            return "No pending comments."

        lines = ["Pending comments:"]
        for comment in comments[: self.config.max_comment_results]:
            comment_id = comment.get("id")
            author = (comment.get("author_name") or "").strip() or "(unknown)"
            link = (comment.get("link") or "").strip()
            lines.append(
                f"- Comment #{comment_id} by {author}{f' — {link}' if link else ''}"
            )
        return "\n".join(lines)

    async def update_page(self, page_query: str, new_content: str) -> str:
        page = await self.api.find_page(page_query)
        if not page:
            return f"I couldn't find a page matching: {page_query}"

        page_id = int(page.get("id"))
        updated = await self.api.update_page(page_id, content=new_content)
        link = updated.get("link") or page.get("link") or ""
        return f"Updated page #{page_id}{f' — {link}' if link else ''}"


__all__ = ["WPAdminAPI", "WPAdminBot", "WPAdminBotConfig"]
