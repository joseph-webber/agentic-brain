# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""WordPress content discovery chatbot.

This module focuses on *read-only* content discovery:
- Find posts/pages about a topic
- Show "what's new" on the blog
- Navigate categories/tags conversationally
- Optionally search WooCommerce products (via WooCommerceAgent)

The intent parsing is deliberately lightweight (regex/rules) so it works without
an LLM, but can be wrapped by one.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Iterable

from agentic_brain.commerce.wordpress import WordPressClient, WPPage, WPPost

try:
    from agentic_brain.commerce.woocommerce import WooCommerceAgent
except Exception:  # pragma: no cover
    WooCommerceAgent = Any  # type: ignore[assignment]


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    text = html.unescape(value or "")
    text = _TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(slots=True)
class WPContentBotConfig:
    """Configuration for :class:`WPContentBot`."""

    max_results: int = 5
    include_pages: bool = True
    include_products: bool = True


class WPContentBot:
    """Conversational helper for discovering WordPress content."""

    def __init__(
        self,
        wp: WordPressClient,
        *,
        woo: WooCommerceAgent | None = None,
        config: WPContentBotConfig | None = None,
    ) -> None:
        self.wp = wp
        self.woo = woo
        self.config = config or WPContentBotConfig()

    async def handle(self, message: str) -> str | None:
        """Handle a user message.

        Returns:
            A response string if the message matches a supported intent, else
            ``None`` so a higher-level chatbot can continue.
        """

        text = (message or "").strip()
        lowered = text.lower()

        query = self._match_find_query(lowered)
        if query:
            return await self.find_content(query)

        if lowered in {
            "what's new on the blog?",
            "whats new on the blog?",
            "what's new on the blog",
            "whats new on the blog",
            "what is new on the blog",
            "new posts",
            "latest posts",
        }:
            return await self.whats_new()

        if re.fullmatch(r"(show|list) categories", lowered):
            return await self.list_categories()

        if re.fullmatch(r"(show|list) tags", lowered):
            return await self.list_tags()

        match = re.match(r"(?:browse|show|open) category (.+)", lowered)
        if match:
            return await self.browse_category(match.group(1).strip())

        match = re.match(r"(?:browse|show|open) tag (.+)", lowered)
        if match:
            return await self.browse_tag(match.group(1).strip())

        return None

    @staticmethod
    def _match_find_query(lowered_message: str) -> str | None:
        patterns = [
            r"find (?:articles|posts|pages) about (?P<q>.+)",
            r"search for (?P<q>.+)",
            r"find (?P<q>.+)",
        ]
        for pattern in patterns:
            match = re.match(pattern, lowered_message)
            if match:
                q = match.group("q").strip(" ?\t\n")
                return q or None
        return None

    async def find_content(self, query: str) -> str:
        posts = await self.wp.posts(search=query, per_page=self.config.max_results)
        pages: list[WPPage] = []
        if self.config.include_pages:
            pages = await self.wp.pages(search=query, per_page=self.config.max_results)

        products: list[dict[str, Any]] = []
        if self.config.include_products and self.woo is not None:
            try:
                products = await self.woo.search_products(query)
            except Exception:
                products = []

        return self._format_search_results(query, posts, pages, products)

    async def whats_new(self) -> str:
        posts = await self.wp.posts(
            per_page=self.config.max_results,
            orderby="date",
            order="desc",
            status="publish",
        )
        if not posts:
            return "I couldn't find any recent posts."

        lines = ["Newest blog posts:"]
        lines.extend(self._format_posts(posts))
        return "\n".join(lines)

    async def list_categories(self) -> str:
        categories = await self.wp.list_categories(
            per_page=20,
            orderby="count",
            order="desc",
        )
        if not categories:
            return "No categories found."

        lines = ["Top categories (say: browse category <name>):"]
        for cat in categories[:20]:
            name = _strip_html(cat.name)
            slug = cat.slug
            count = cat.count or 0
            lines.append(f"- {name} (slug: {slug}, posts: {count})")
        return "\n".join(lines)

    async def list_tags(self) -> str:
        tags = await self.wp.list_tags(
            per_page=20,
            orderby="count",
            order="desc",
        )
        if not tags:
            return "No tags found."

        lines = ["Top tags (say: browse tag <name>):"]
        for tag in tags[:20]:
            name = _strip_html(tag.name)
            slug = tag.slug
            count = tag.count or 0
            lines.append(f"- {name} (slug: {slug}, posts: {count})")
        return "\n".join(lines)

    async def browse_category(self, category_query: str) -> str:
        category_id = await self._resolve_term_id("categories", category_query)
        if category_id is None:
            return f"I couldn't find a category matching: {category_query}"

        posts = await self.wp.posts(
            categories=category_id,
            per_page=self.config.max_results,
            orderby="date",
            order="desc",
            status="publish",
        )
        if not posts:
            return "No posts found in that category."

        lines = [f"Posts in category '{category_query}':"]
        lines.extend(self._format_posts(posts))
        return "\n".join(lines)

    async def browse_tag(self, tag_query: str) -> str:
        tag_id = await self._resolve_term_id("tags", tag_query)
        if tag_id is None:
            return f"I couldn't find a tag matching: {tag_query}"

        posts = await self.wp.posts(
            tags=tag_id,
            per_page=self.config.max_results,
            orderby="date",
            order="desc",
            status="publish",
        )
        if not posts:
            return "No posts found for that tag."

        lines = [f"Posts tagged '{tag_query}':"]
        lines.extend(self._format_posts(posts))
        return "\n".join(lines)

    async def _resolve_term_id(self, endpoint: str, query: str) -> int | None:
        normalized = query.strip().lower()
        if endpoint == "categories":
            terms = await self.wp.list_categories(search=query, per_page=10)
        elif endpoint == "tags":
            terms = await self.wp.list_tags(search=query, per_page=10)
        else:
            return None

        if not terms:
            return None

        best = terms[0]
        for term in terms:
            if (
                term.name.strip().lower() == normalized
                or term.slug.strip().lower() == normalized
            ):
                return term.id
        return best.id

    def _format_search_results(
        self,
        query: str,
        posts: Iterable[WPPost],
        pages: Iterable[WPPage],
        products: Iterable[dict[str, Any]],
    ) -> str:
        lines: list[str] = [f"Search results for: {query}"]

        post_lines = self._format_posts(posts)
        if post_lines:
            lines.append("\nPosts:")
            lines.extend(post_lines)

        page_lines = self._format_pages(pages)
        if page_lines:
            lines.append("\nPages:")
            lines.extend(page_lines)

        product_lines = self._format_products(products)
        if product_lines:
            lines.append("\nProducts:")
            lines.extend(product_lines)

        if len(lines) == 1:
            return "I couldn't find anything matching that query."
        return "\n".join(lines)

    def _format_posts(self, posts: Iterable[WPPost]) -> list[str]:
        lines = []
        for post in list(posts)[: self.config.max_results]:
            title = _strip_html(post.title.rendered)
            url = post.link or ""
            lines.append(f"- {title}{f' — {url}' if url else ''}")
        return lines

    def _format_pages(self, pages: Iterable[WPPage]) -> list[str]:
        lines = []
        for page in list(pages)[: self.config.max_results]:
            title = _strip_html(page.title.rendered)
            url = page.link or ""
            lines.append(f"- {title}{f' — {url}' if url else ''}")
        return lines

    def _format_products(self, products: Iterable[dict[str, Any]]) -> list[str]:
        lines = []
        for product in list(products)[: self.config.max_results]:
            title = _strip_html(str(product.get("name", "")))
            url = str(product.get("permalink", ""))
            price = str(product.get("price", ""))
            suffix = []
            if price:
                suffix.append(f"price: {price}")
            if url:
                suffix.append(url)
            if title:
                lines.append(
                    f"- {title}{(' — ' + ' | '.join(suffix)) if suffix else ''}"
                )
        return lines


__all__ = ["WPContentBot", "WPContentBotConfig"]
