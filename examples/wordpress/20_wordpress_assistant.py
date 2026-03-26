#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 20: WordPress Content Management Assistant

A chatbot that helps manage WordPress content, posts, pages, and media.
Uses the WordPress REST API with Application Passwords authentication.

Use Cases:
- Content creators managing blog posts
- Marketing teams scheduling content
- Editors reviewing and publishing drafts
- Media managers organizing uploads

Requirements:
- WordPress 5.6+ (for Application Passwords)
- REST API enabled (default in modern WordPress)
- Application Password generated for API access
"""

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import aiohttp

# Simulated WordPress data for demo
DEMO_POSTS = [
    {
        "id": 101,
        "title": {"rendered": "Getting Started with Office Automation"},
        "status": "publish",
        "date": "2024-03-15T10:00:00",
        "categories": [5],
        "author": 1,
        "excerpt": {"rendered": "Learn how to automate your office workflows..."},
    },
    {
        "id": 102,
        "title": {"rendered": "Top 10 Ergonomic Keyboards for 2024"},
        "status": "publish",
        "date": "2024-03-14T14:30:00",
        "categories": [3],
        "author": 1,
        "excerpt": {"rendered": "Our review of the best ergonomic keyboards..."},
    },
    {
        "id": 103,
        "title": {"rendered": "Monitor Setup Guide: Dual vs Ultrawide"},
        "status": "draft",
        "date": "2024-03-16T09:00:00",
        "categories": [3],
        "author": 2,
        "excerpt": {"rendered": "Comparing dual monitor setups with ultrawide..."},
    },
    {
        "id": 104,
        "title": {"rendered": "USB-C Hub Buying Guide"},
        "status": "pending",
        "date": "2024-03-17T11:00:00",
        "categories": [4],
        "author": 1,
        "excerpt": {"rendered": "Everything you need to know about USB-C hubs..."},
    },
]

DEMO_CATEGORIES = [
    {"id": 3, "name": "Hardware Reviews", "count": 25},
    {"id": 4, "name": "Buying Guides", "count": 18},
    {"id": 5, "name": "Tutorials", "count": 32},
    {"id": 6, "name": "News", "count": 45},
]

DEMO_MEDIA = [
    {
        "id": 201,
        "title": {"rendered": "keyboard-hero.jpg"},
        "media_type": "image",
        "mime_type": "image/jpeg",
    },
    {
        "id": 202,
        "title": {"rendered": "monitor-comparison.png"},
        "media_type": "image",
        "mime_type": "image/png",
    },
    {
        "id": 203,
        "title": {"rendered": "usb-hub-diagram.svg"},
        "media_type": "image",
        "mime_type": "image/svg+xml",
    },
]


@dataclass
class WordPressConfig:
    """Configuration for WordPress API connection."""

    site_url: str = "https://demo-site.local"
    username: str = "editor"
    app_password: str = "xxxx xxxx xxxx xxxx"
    timeout: int = 30

    @property
    def auth_header(self) -> str:
        """Generate Basic Auth header value."""
        credentials = f"{self.username}:{self.app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"


@dataclass
class Post:
    """WordPress post representation."""

    id: int
    title: str
    status: str
    date: datetime
    categories: list[int] = field(default_factory=list)
    author: int = 1
    excerpt: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "Post":
        """Create Post from WordPress API response."""
        return cls(
            id=data["id"],
            title=data["title"]["rendered"],
            status=data["status"],
            date=datetime.fromisoformat(data["date"].replace("Z", "+00:00")),
            categories=data.get("categories", []),
            author=data.get("author", 1),
            excerpt=data.get("excerpt", {}).get("rendered", ""),
        )


class WordPressClient:
    """Async client for WordPress REST API."""

    def __init__(self, config: WordPressConfig, demo_mode: bool = True):
        self.config = config
        self.demo_mode = demo_mode
        self.base_url = f"{config.site_url}/wp-json/wp/v2"

    async def get_posts(
        self,
        status: str = "any",
        per_page: int = 10,
        category: Optional[int] = None,
    ) -> list[Post]:
        """Fetch posts from WordPress."""
        if self.demo_mode:
            posts = DEMO_POSTS
            if status != "any":
                posts = [p for p in posts if p["status"] == status]
            if category:
                posts = [p for p in posts if category in p["categories"]]
            return [Post.from_api(p) for p in posts[:per_page]]

        params = {"per_page": per_page, "status": status}
        if category:
            params["categories"] = category

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/posts",
                params=params,
                headers={"Authorization": self.config.auth_header},
            ) as response:
                data = await response.json()
                return [Post.from_api(p) for p in data]

    async def get_post(self, post_id: int) -> Optional[Post]:
        """Fetch a single post by ID."""
        if self.demo_mode:
            for p in DEMO_POSTS:
                if p["id"] == post_id:
                    return Post.from_api(p)
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/posts/{post_id}",
                headers={"Authorization": self.config.auth_header},
            ) as response:
                if response.status == 404:
                    return None
                data = await response.json()
                return Post.from_api(data)

    async def create_post(
        self,
        title: str,
        content: str,
        status: str = "draft",
        categories: Optional[list[int]] = None,
    ) -> dict:
        """Create a new post."""
        if self.demo_mode:
            new_id = max(p["id"] for p in DEMO_POSTS) + 1
            return {
                "success": True,
                "post_id": new_id,
                "title": title,
                "status": status,
                "message": f"Post '{title}' created as {status} (ID: {new_id})",
            }

        payload = {
            "title": title,
            "content": content,
            "status": status,
        }
        if categories:
            payload["categories"] = categories

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/posts",
                json=payload,
                headers={"Authorization": self.config.auth_header},
            ) as response:
                data = await response.json()
                return {"success": True, "post_id": data["id"], "data": data}

    async def update_post(self, post_id: int, updates: dict) -> dict:
        """Update an existing post."""
        if self.demo_mode:
            return {
                "success": True,
                "post_id": post_id,
                "updates": updates,
                "message": f"Post {post_id} updated successfully",
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/posts/{post_id}",
                json=updates,
                headers={"Authorization": self.config.auth_header},
            ) as response:
                data = await response.json()
                return {"success": True, "post_id": post_id, "data": data}

    async def get_categories(self) -> list[dict]:
        """Fetch all categories."""
        if self.demo_mode:
            return DEMO_CATEGORIES

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/categories",
                headers={"Authorization": self.config.auth_header},
            ) as response:
                return await response.json()

    async def get_media(self, per_page: int = 10) -> list[dict]:
        """Fetch media library items."""
        if self.demo_mode:
            return DEMO_MEDIA[:per_page]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/media",
                params={"per_page": per_page},
                headers={"Authorization": self.config.auth_header},
            ) as response:
                return await response.json()

    async def search_content(self, query: str) -> list[dict]:
        """Search across all content."""
        if self.demo_mode:
            query_lower = query.lower()
            results = []
            for p in DEMO_POSTS:
                if query_lower in p["title"]["rendered"].lower():
                    results.append(
                        {
                            "id": p["id"],
                            "title": p["title"]["rendered"],
                            "type": "post",
                            "status": p["status"],
                        }
                    )
            return results

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/search",
                params={"search": query},
                headers={"Authorization": self.config.auth_header},
            ) as response:
                return await response.json()


class WordPressAssistant:
    """
    AI assistant for WordPress content management.

    Capabilities:
    - List and search posts
    - Create and edit content
    - Manage categories
    - Handle media library
    - Schedule publications
    """

    def __init__(
        self, config: Optional[WordPressConfig] = None, demo_mode: bool = True
    ):
        self.config = config or WordPressConfig()
        self.client = WordPressClient(self.config, demo_mode=demo_mode)
        self.conversation_history: list[dict] = []

    async def process_message(self, user_message: str) -> str:
        """Process a user message and return a response."""
        message_lower = user_message.lower()

        # Store in history
        self.conversation_history.append(
            {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Route to appropriate handler
        if any(word in message_lower for word in ["list", "show", "posts", "articles"]):
            response = await self._handle_list_posts(message_lower)
        elif any(word in message_lower for word in ["draft", "drafts", "pending"]):
            response = await self._handle_drafts(message_lower)
        elif any(word in message_lower for word in ["create", "write", "new post"]):
            response = await self._handle_create_post(user_message)
        elif any(word in message_lower for word in ["publish", "schedule"]):
            response = await self._handle_publish(message_lower)
        elif any(word in message_lower for word in ["categor"]):
            response = await self._handle_categories()
        elif any(word in message_lower for word in ["media", "image", "upload"]):
            response = await self._handle_media()
        elif any(word in message_lower for word in ["search", "find"]):
            response = await self._handle_search(user_message)
        elif any(word in message_lower for word in ["help", "what can"]):
            response = self._get_help()
        else:
            response = await self._handle_general(user_message)

        # Store response
        self.conversation_history.append(
            {
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return response

    async def _handle_list_posts(self, message: str) -> str:
        """Handle requests to list posts."""
        # Determine status filter
        if "draft" in message:
            status = "draft"
        elif "pending" in message:
            status = "pending"
        elif "publish" in message:
            status = "publish"
        else:
            status = "any"

        posts = await self.client.get_posts(status=status)

        if not posts:
            return f"No posts found with status '{status}'."

        lines = [f"📝 **Posts ({status})**\n"]
        for post in posts:
            status_emoji = {"publish": "✅", "draft": "📝", "pending": "⏳"}.get(
                post.status, "❓"
            )
            lines.append(f"{status_emoji} [{post.id}] {post.title}")
            lines.append(
                f"   Status: {post.status} | Date: {post.date.strftime('%Y-%m-%d')}"
            )

        return "\n".join(lines)

    async def _handle_drafts(self, message: str) -> str:
        """Handle requests for draft posts."""
        drafts = await self.client.get_posts(status="draft")
        pending = await self.client.get_posts(status="pending")

        all_unpublished = drafts + pending

        if not all_unpublished:
            return "✅ No drafts or pending posts. All content is published!"

        lines = ["📋 **Unpublished Content**\n"]

        if drafts:
            lines.append("**Drafts:**")
            for post in drafts:
                lines.append(f"  📝 [{post.id}] {post.title}")

        if pending:
            lines.append("\n**Pending Review:**")
            for post in pending:
                lines.append(f"  ⏳ [{post.id}] {post.title}")

        lines.append(f"\nTotal: {len(drafts)} drafts, {len(pending)} pending review")
        return "\n".join(lines)

    async def _handle_create_post(self, message: str) -> str:
        """Handle post creation requests."""
        # In a real implementation, you'd parse the title/content from the message
        # or prompt for more details
        return """📝 **Create New Post**

To create a post, I need:
1. **Title**: What should the post be called?
2. **Content**: The post body (can be HTML)
3. **Status**: draft, pending, or publish
4. **Category**: Which category? (use 'show categories' to see options)

Example command:
"Create draft post titled 'New Product Guide' in Hardware Reviews category"

Or provide the details and I'll create it for you!"""

    async def _handle_publish(self, message: str) -> str:
        """Handle publish/schedule requests."""
        # Extract post ID from message (simplified)
        import re

        id_match = re.search(r"\b(\d+)\b", message)

        if not id_match:
            drafts = await self.client.get_posts(status="draft")
            if drafts:
                lines = ["Which post would you like to publish?\n"]
                for post in drafts:
                    lines.append(f"  [{post.id}] {post.title}")
                return "\n".join(lines)
            return "No draft posts to publish. Create a new post first."

        post_id = int(id_match.group(1))
        post = await self.client.get_post(post_id)

        if not post:
            return f"Post {post_id} not found."

        if "schedule" in message:
            return f"""⏰ **Schedule Post {post_id}**

Post: {post.title}
Current status: {post.status}

When would you like to publish?
- "publish now" - Immediately
- "schedule for tomorrow 9am"
- "schedule for March 20 2024 at 2pm"
"""

        result = await self.client.update_post(post_id, {"status": "publish"})
        return f"✅ Published: {post.title}\n\nThe post is now live on your site!"

    async def _handle_categories(self) -> str:
        """Handle category listing."""
        categories = await self.client.get_categories()

        lines = ["📁 **Categories**\n"]
        for cat in categories:
            lines.append(f"  [{cat['id']}] {cat['name']} ({cat['count']} posts)")

        return "\n".join(lines)

    async def _handle_media(self) -> str:
        """Handle media library requests."""
        media = await self.client.get_media()

        lines = ["🖼️ **Media Library** (Recent)\n"]
        for item in media:
            emoji = "🖼️" if "image" in item["mime_type"] else "📄"
            lines.append(f"  {emoji} [{item['id']}] {item['title']['rendered']}")

        lines.append("\nUse 'upload image' to add new media.")
        return "\n".join(lines)

    async def _handle_search(self, message: str) -> str:
        """Handle content search."""
        # Extract search query
        query = message.lower().replace("search", "").replace("find", "").strip()

        if not query:
            return (
                "What would you like to search for? Example: 'search keyboard reviews'"
            )

        results = await self.client.search_content(query)

        if not results:
            return f"No results found for '{query}'."

        lines = [f"🔍 **Search Results for '{query}'**\n"]
        for item in results:
            status_emoji = {"publish": "✅", "draft": "📝", "pending": "⏳"}.get(
                item.get("status", ""), "📄"
            )
            lines.append(f"  {status_emoji} [{item['id']}] {item['title']}")

        return "\n".join(lines)

    async def _handle_general(self, message: str) -> str:
        """Handle general queries."""
        return f"""I'm not sure how to help with that. Here's what I can do:

{self._get_help()}

Please try one of these commands or ask for help!"""

    def _get_help(self) -> str:
        """Return help text."""
        return """📚 **WordPress Assistant Commands**

**Content Management:**
- "show posts" - List all posts
- "show drafts" - List unpublished content
- "create new post" - Start creating a post
- "publish post 123" - Publish a specific post
- "search [query]" - Find content

**Organization:**
- "show categories" - List all categories
- "show media" - Browse media library

**Examples:**
- "Show me all draft posts"
- "Search for keyboard"
- "Publish post 103"
- "Create new post about monitors"

Need help with something specific? Just ask!"""


async def demo():
    """Run an interactive demo of the WordPress assistant."""
    print("=" * 60)
    print("WordPress Content Management Assistant")
    print("=" * 60)
    print("\nRunning in DEMO MODE (no real WordPress connection)")
    print("Type 'quit' to exit, 'help' for commands\n")

    assistant = WordPressAssistant(demo_mode=True)

    # Demo queries
    demo_queries = [
        "show posts",
        "show drafts",
        "show categories",
        "search keyboard",
        "help",
    ]

    print("Running demo queries...\n")

    for query in demo_queries:
        print(f"👤 User: {query}")
        print("-" * 40)
        response = await assistant.process_message(query)
        print(f"🤖 Assistant:\n{response}")
        print("=" * 60)
        print()


async def interactive():
    """Run interactive mode."""
    print("=" * 60)
    print("WordPress Content Management Assistant")
    print("=" * 60)
    print("\nType 'quit' to exit, 'help' for commands\n")

    assistant = WordPressAssistant(demo_mode=True)

    while True:
        try:
            user_input = input("👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "bye"]:
                print("👋 Goodbye!")
                break

            response = await assistant.process_message(user_input)
            print(f"\n🤖 Assistant:\n{response}\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(demo())
