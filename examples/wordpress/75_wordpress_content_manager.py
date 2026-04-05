#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WordPress Content Manager - Agentic Brain Example #75

A comprehensive WordPress content management system that handles:
- Blog post creation, editing, and scheduling
- Category and tag management
- Featured image handling
- SEO metadata optimization
- Draft/publish workflow
- Content calendar management
- Multi-author support
- Revision history tracking

Perfect for electronics stores, tech blogs, or any content-heavy WordPress site.

Usage:
    python 75_wordpress_content_manager.py --demo
    python 75_wordpress_content_manager.py --url https://yoursite.com --user admin --password app_password
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class PostStatus(Enum):
    """WordPress post status options."""

    DRAFT = "draft"
    PENDING = "pending"
    PUBLISH = "publish"
    FUTURE = "future"
    PRIVATE = "private"
    TRASH = "trash"
    AUTO_DRAFT = "auto-draft"


class ContentType(Enum):
    """Content types for electronics store."""

    PRODUCT_REVIEW = "product_review"
    BUYING_GUIDE = "buying_guide"
    HOW_TO = "how_to"
    NEWS = "news"
    COMPARISON = "comparison"
    DEAL_ALERT = "deal_alert"
    TUTORIAL = "tutorial"
    ANNOUNCEMENT = "announcement"


class AuthorRole(Enum):
    """WordPress user roles."""

    ADMINISTRATOR = "administrator"
    EDITOR = "editor"
    AUTHOR = "author"
    CONTRIBUTOR = "contributor"
    SUBSCRIBER = "subscriber"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class SEOMetadata:
    """SEO metadata for a post."""

    title: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    focus_keyword: str = ""
    canonical_url: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    twitter_title: str = ""
    twitter_description: str = ""
    no_index: bool = False
    no_follow: bool = False

    def to_yoast_meta(self) -> Dict[str, Any]:
        """Convert to Yoast SEO meta format."""
        return {
            "_yoast_wpseo_title": self.title,
            "_yoast_wpseo_metadesc": self.description,
            "_yoast_wpseo_focuskw": self.focus_keyword,
            "_yoast_wpseo_canonical": self.canonical_url,
            "_yoast_wpseo_opengraph-title": self.og_title or self.title,
            "_yoast_wpseo_opengraph-description": self.og_description
            or self.description,
            "_yoast_wpseo_opengraph-image": self.og_image,
            "_yoast_wpseo_twitter-title": self.twitter_title or self.title,
            "_yoast_wpseo_twitter-description": self.twitter_description
            or self.description,
            "_yoast_wpseo_meta-robots-noindex": "1" if self.no_index else "",
            "_yoast_wpseo_meta-robots-nofollow": "1" if self.no_follow else "",
        }

    def to_rankmath_meta(self) -> Dict[str, Any]:
        """Convert to Rank Math SEO meta format."""
        return {
            "rank_math_title": self.title,
            "rank_math_description": self.description,
            "rank_math_focus_keyword": self.focus_keyword,
            "rank_math_canonical_url": self.canonical_url,
            "rank_math_facebook_title": self.og_title or self.title,
            "rank_math_facebook_description": self.og_description or self.description,
            "rank_math_facebook_image": self.og_image,
            "rank_math_twitter_title": self.twitter_title or self.title,
            "rank_math_twitter_description": self.twitter_description
            or self.description,
            "rank_math_robots": self._get_robots_meta(),
        }

    def _get_robots_meta(self) -> List[str]:
        """Generate robots meta directives."""
        robots = []
        if self.no_index:
            robots.append("noindex")
        if self.no_follow:
            robots.append("nofollow")
        return robots if robots else ["index", "follow"]


@dataclass
class FeaturedImage:
    """Featured image data."""

    id: Optional[int] = None
    url: str = ""
    alt_text: str = ""
    title: str = ""
    caption: str = ""
    width: int = 0
    height: int = 0
    file_path: str = ""

    def is_valid(self) -> bool:
        """Check if image data is valid."""
        return bool(self.id or self.url or self.file_path)


@dataclass
class Category:
    """WordPress category."""

    id: Optional[int] = None
    name: str = ""
    slug: str = ""
    description: str = ""
    parent_id: Optional[int] = None
    count: int = 0

    def generate_slug(self) -> str:
        """Generate slug from name."""
        if not self.slug:
            self.slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return self.slug


@dataclass
class Tag:
    """WordPress tag."""

    id: Optional[int] = None
    name: str = ""
    slug: str = ""
    description: str = ""
    count: int = 0

    def generate_slug(self) -> str:
        """Generate slug from name."""
        if not self.slug:
            self.slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return self.slug


@dataclass
class Author:
    """WordPress author/user."""

    id: Optional[int] = None
    username: str = ""
    email: str = ""
    display_name: str = ""
    role: AuthorRole = AuthorRole.AUTHOR
    bio: str = ""
    avatar_url: str = ""
    post_count: int = 0

    def get_author_box_html(self) -> str:
        """Generate author box HTML."""
        return f"""
        <div class="author-box">
            <img src="{self.avatar_url}" alt="{self.display_name}" class="author-avatar">
            <div class="author-info">
                <h4 class="author-name">{self.display_name}</h4>
                <p class="author-bio">{self.bio}</p>
            </div>
        </div>
        """


@dataclass
class Revision:
    """Post revision data."""

    id: int
    post_id: int
    author_id: int
    date: datetime
    title: str
    content: str
    excerpt: str
    modified_fields: List[str] = field(default_factory=list)

    def get_diff_summary(self, other: "Revision") -> Dict[str, Any]:
        """Get summary of changes between revisions."""
        changes = {}
        if self.title != other.title:
            changes["title"] = {"old": other.title, "new": self.title}
        if self.content != other.content:
            changes["content"] = {
                "old_length": len(other.content),
                "new_length": len(self.content),
                "changed": True,
            }
        if self.excerpt != other.excerpt:
            changes["excerpt"] = {"old": other.excerpt, "new": self.excerpt}
        return changes


@dataclass
class BlogPost:
    """Complete blog post data structure."""

    id: Optional[int] = None
    title: str = ""
    slug: str = ""
    content: str = ""
    excerpt: str = ""
    status: PostStatus = PostStatus.DRAFT
    content_type: ContentType = ContentType.NEWS
    author: Optional[Author] = None
    categories: List[Category] = field(default_factory=list)
    tags: List[Tag] = field(default_factory=list)
    featured_image: Optional[FeaturedImage] = None
    seo: Optional[SEOMetadata] = None
    publish_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    created_date: Optional[datetime] = None
    comment_status: str = "open"
    ping_status: str = "open"
    format: str = "standard"
    sticky: bool = False
    template: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    revisions: List[Revision] = field(default_factory=list)

    def generate_slug(self) -> str:
        """Generate URL slug from title."""
        if not self.slug:
            self.slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return self.slug

    def generate_excerpt(self, max_length: int = 155) -> str:
        """Generate excerpt from content."""
        if self.excerpt:
            return self.excerpt

        # Strip HTML and get plain text
        plain_text = re.sub(r"<[^>]+>", "", self.content)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

        if len(plain_text) <= max_length:
            return plain_text

        # Truncate at word boundary
        truncated = plain_text[:max_length].rsplit(" ", 1)[0]
        return truncated + "..."

    def word_count(self) -> int:
        """Get word count of content."""
        plain_text = re.sub(r"<[^>]+>", "", self.content)
        words = plain_text.split()
        return len(words)

    def reading_time(self, words_per_minute: int = 200) -> int:
        """Calculate estimated reading time in minutes."""
        count = self.word_count()
        return max(1, round(count / words_per_minute))

    def to_wp_api_format(self) -> Dict[str, Any]:
        """Convert to WordPress REST API format."""
        data = {
            "title": self.title,
            "slug": self.generate_slug(),
            "content": self.content,
            "excerpt": self.excerpt or self.generate_excerpt(),
            "status": self.status.value,
            "comment_status": self.comment_status,
            "ping_status": self.ping_status,
            "format": self.format,
            "sticky": self.sticky,
        }

        if self.author and self.author.id:
            data["author"] = self.author.id

        if self.categories:
            data["categories"] = [c.id for c in self.categories if c.id]

        if self.tags:
            data["tags"] = [t.id for t in self.tags if t.id]

        if self.featured_image and self.featured_image.id:
            data["featured_media"] = self.featured_image.id

        if self.publish_date and self.status == PostStatus.FUTURE:
            data["date"] = self.publish_date.isoformat()

        if self.template:
            data["template"] = self.template

        # Add custom fields as meta
        if self.custom_fields:
            data["meta"] = self.custom_fields

        return data


@dataclass
class CalendarEntry:
    """Content calendar entry."""

    post_id: Optional[int] = None
    title: str = ""
    content_type: ContentType = ContentType.NEWS
    scheduled_date: Optional[datetime] = None
    author: Optional[Author] = None
    status: PostStatus = PostStatus.DRAFT
    notes: str = ""
    priority: int = 1  # 1-5, 5 being highest
    dependencies: List[int] = field(default_factory=list)
    assigned_editor: Optional[Author] = None
    deadline: Optional[datetime] = None


# ============================================================================
# WORDPRESS API CLIENT
# ============================================================================


class WordPressAPIClient:
    """WordPress REST API client."""

    def __init__(self, site_url: str, username: str, password: str, timeout: int = 30):
        self.site_url = site_url.rstrip("/")
        self.api_url = f"{self.site_url}/wp-json/wp/v2"
        self.username = username
        self.password = password
        self.timeout = timeout
        self._auth_header = self._create_auth_header()

    def _create_auth_header(self) -> str:
        """Create Basic Auth header."""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make API request (simulated for demo)."""
        url = f"{self.api_url}/{endpoint}"
        logger.info(f"API {method} request to: {url}")

        # In real implementation, use aiohttp or httpx
        # For demo, return simulated response
        return {"success": True, "data": data or {}}

    async def get_posts(
        self,
        page: int = 1,
        per_page: int = 10,
        status: Optional[PostStatus] = None,
        categories: Optional[List[int]] = None,
        tags: Optional[List[int]] = None,
        author: Optional[int] = None,
        search: Optional[str] = None,
        order: str = "desc",
        orderby: str = "date",
    ) -> List[Dict]:
        """Get posts with filters."""
        params = {
            "page": page,
            "per_page": per_page,
            "order": order,
            "orderby": orderby,
        }

        if status:
            params["status"] = status.value
        if categories:
            params["categories"] = ",".join(map(str, categories))
        if tags:
            params["tags"] = ",".join(map(str, tags))
        if author:
            params["author"] = author
        if search:
            params["search"] = search

        return await self._request("GET", "posts", params=params)

    async def create_post(self, post: BlogPost) -> Dict:
        """Create a new post."""
        data = post.to_wp_api_format()
        return await self._request("POST", "posts", data=data)

    async def update_post(self, post_id: int, post: BlogPost) -> Dict:
        """Update an existing post."""
        data = post.to_wp_api_format()
        return await self._request("PUT", f"posts/{post_id}", data=data)

    async def delete_post(self, post_id: int, force: bool = False) -> Dict:
        """Delete a post."""
        params = {"force": force}
        return await self._request("DELETE", f"posts/{post_id}", params=params)

    async def get_categories(self, per_page: int = 100) -> List[Dict]:
        """Get all categories."""
        params = {"per_page": per_page}
        return await self._request("GET", "categories", params=params)

    async def create_category(self, category: Category) -> Dict:
        """Create a new category."""
        data = {
            "name": category.name,
            "slug": category.generate_slug(),
            "description": category.description,
        }
        if category.parent_id:
            data["parent"] = category.parent_id
        return await self._request("POST", "categories", data=data)

    async def get_tags(self, per_page: int = 100) -> List[Dict]:
        """Get all tags."""
        params = {"per_page": per_page}
        return await self._request("GET", "tags", params=params)

    async def create_tag(self, tag: Tag) -> Dict:
        """Create a new tag."""
        data = {
            "name": tag.name,
            "slug": tag.generate_slug(),
            "description": tag.description,
        }
        return await self._request("POST", "tags", data=data)

    async def upload_media(
        self, file_path: str, title: str = "", alt_text: str = "", caption: str = ""
    ) -> Dict:
        """Upload media file."""
        # In real implementation, read file and upload
        data = {
            "title": title,
            "alt_text": alt_text,
            "caption": caption,
            "source_url": file_path,
        }
        return await self._request("POST", "media", data=data)

    async def get_users(self, roles: Optional[List[str]] = None) -> List[Dict]:
        """Get users/authors."""
        params = {}
        if roles:
            params["roles"] = ",".join(roles)
        return await self._request("GET", "users", params=params)

    async def get_revisions(self, post_id: int) -> List[Dict]:
        """Get post revisions."""
        return await self._request("GET", f"posts/{post_id}/revisions")

    async def restore_revision(self, post_id: int, revision_id: int) -> Dict:
        """Restore a post revision."""
        return await self._request("POST", f"posts/{post_id}/revisions/{revision_id}")


# ============================================================================
# CONTENT MANAGER
# ============================================================================


class ContentManager:
    """Manages WordPress content operations."""

    def __init__(self, api_client: WordPressAPIClient):
        self.api = api_client
        self.categories_cache: Dict[int, Category] = {}
        self.tags_cache: Dict[int, Tag] = {}
        self.authors_cache: Dict[int, Author] = {}

    async def initialize(self):
        """Initialize caches."""
        await self._load_categories()
        await self._load_tags()
        await self._load_authors()

    async def _load_categories(self):
        """Load categories into cache."""
        logger.info("Loading categories...")
        # In real implementation, parse API response
        # Demo categories for electronics store
        demo_categories = [
            Category(id=1, name="Product Reviews", slug="product-reviews", count=45),
            Category(id=2, name="Buying Guides", slug="buying-guides", count=23),
            Category(id=3, name="How-To Tutorials", slug="how-to-tutorials", count=67),
            Category(id=4, name="Tech News", slug="tech-news", count=89),
            Category(id=5, name="Deals & Offers", slug="deals-offers", count=34),
            Category(
                id=6, name="Smartphones", slug="smartphones", parent_id=1, count=18
            ),
            Category(id=7, name="Laptops", slug="laptops", parent_id=1, count=15),
            Category(id=8, name="Audio", slug="audio", parent_id=1, count=12),
            Category(id=9, name="Smart Home", slug="smart-home", parent_id=1, count=9),
            Category(id=10, name="Gaming", slug="gaming", parent_id=1, count=21),
        ]
        for cat in demo_categories:
            self.categories_cache[cat.id] = cat

    async def _load_tags(self):
        """Load tags into cache."""
        logger.info("Loading tags...")
        demo_tags = [
            Tag(id=1, name="Wireless", slug="wireless", count=45),
            Tag(id=2, name="Bluetooth", slug="bluetooth", count=38),
            Tag(id=3, name="USB-C", slug="usb-c", count=29),
            Tag(id=4, name="4K", slug="4k", count=22),
            Tag(id=5, name="Budget", slug="budget", count=56),
            Tag(id=6, name="Premium", slug="premium", count=34),
            Tag(id=7, name="Best Seller", slug="best-seller", count=18),
            Tag(id=8, name="New Release", slug="new-release", count=27),
            Tag(id=9, name="Sale", slug="sale", count=43),
            Tag(id=10, name="Editor's Choice", slug="editors-choice", count=12),
        ]
        for tag in demo_tags:
            self.tags_cache[tag.id] = tag

    async def _load_authors(self):
        """Load authors into cache."""
        logger.info("Loading authors...")
        demo_authors = [
            Author(
                id=1,
                username="tech_editor",
                email="editor@example.com",
                display_name="Alex Chen",
                role=AuthorRole.EDITOR,
                bio="Senior tech editor with 10 years experience in consumer electronics.",
                post_count=156,
            ),
            Author(
                id=2,
                username="review_specialist",
                email="reviews@example.com",
                display_name="Sarah Johnson",
                role=AuthorRole.AUTHOR,
                bio="Product review specialist focusing on smartphones and wearables.",
                post_count=89,
            ),
            Author(
                id=3,
                username="deal_hunter",
                email="deals@example.com",
                display_name="Mike Torres",
                role=AuthorRole.AUTHOR,
                bio="Your guide to finding the best tech deals and discounts.",
                post_count=234,
            ),
            Author(
                id=4,
                username="smart_home_expert",
                email="smarthome@example.com",
                display_name="Emma Wilson",
                role=AuthorRole.CONTRIBUTOR,
                bio="Smart home enthusiast and automation specialist.",
                post_count=67,
            ),
        ]
        for author in demo_authors:
            self.authors_cache[author.id] = author

    def get_category_by_name(self, name: str) -> Optional[Category]:
        """Find category by name."""
        name_lower = name.lower()
        for cat in self.categories_cache.values():
            if cat.name.lower() == name_lower:
                return cat
        return None

    def get_tag_by_name(self, name: str) -> Optional[Tag]:
        """Find tag by name."""
        name_lower = name.lower()
        for tag in self.tags_cache.values():
            if tag.name.lower() == name_lower:
                return tag
        return None

    def suggest_categories(self, content_type: ContentType) -> List[Category]:
        """Suggest categories based on content type."""
        suggestions = {
            ContentType.PRODUCT_REVIEW: [1, 6, 7, 8, 9, 10],
            ContentType.BUYING_GUIDE: [2],
            ContentType.HOW_TO: [3],
            ContentType.NEWS: [4],
            ContentType.DEAL_ALERT: [5],
            ContentType.COMPARISON: [1, 2],
            ContentType.TUTORIAL: [3],
            ContentType.ANNOUNCEMENT: [4],
        }
        category_ids = suggestions.get(content_type, [])
        return [
            self.categories_cache[cid]
            for cid in category_ids
            if cid in self.categories_cache
        ]

    def suggest_tags(self, title: str, content: str) -> List[Tag]:
        """Suggest tags based on content analysis."""
        text = f"{title} {content}".lower()
        suggestions = []

        # Simple keyword matching (in production, use NLP)
        keyword_map = {
            "wireless": 1,
            "wifi": 1,
            "wi-fi": 1,
            "bluetooth": 2,
            "bt": 2,
            "usb-c": 3,
            "usbc": 3,
            "type-c": 3,
            "4k": 4,
            "ultra hd": 4,
            "uhd": 4,
            "budget": 5,
            "affordable": 5,
            "cheap": 5,
            "premium": 6,
            "high-end": 6,
            "flagship": 6,
            "best sell": 7,
            "popular": 7,
            "new": 8,
            "launch": 8,
            "release": 8,
            "sale": 9,
            "discount": 9,
            "deal": 9,
            "recommend": 10,
            "choice": 10,
        }

        for keyword, tag_id in keyword_map.items():
            if keyword in text and tag_id in self.tags_cache:
                tag = self.tags_cache[tag_id]
                if tag not in suggestions:
                    suggestions.append(tag)

        return suggestions[:5]  # Limit to 5 suggestions


# ============================================================================
# CONTENT CALENDAR
# ============================================================================


class ContentCalendar:
    """Manages content scheduling and calendar."""

    def __init__(self, content_manager: ContentManager):
        self.manager = content_manager
        self.entries: Dict[str, CalendarEntry] = {}

    def add_entry(self, entry: CalendarEntry) -> str:
        """Add calendar entry."""
        entry_id = hashlib.md5(
            f"{entry.title}{entry.scheduled_date}".encode()
        ).hexdigest()[:8]
        self.entries[entry_id] = entry
        return entry_id

    def get_entries_for_date(self, date: datetime) -> List[CalendarEntry]:
        """Get all entries for a specific date."""
        date_str = date.strftime("%Y-%m-%d")
        return [
            e
            for e in self.entries.values()
            if e.scheduled_date and e.scheduled_date.strftime("%Y-%m-%d") == date_str
        ]

    def get_entries_for_week(
        self, start_date: datetime
    ) -> Dict[str, List[CalendarEntry]]:
        """Get entries for a week."""
        week = {}
        for i in range(7):
            day = start_date + timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            week[day_str] = self.get_entries_for_date(day)
        return week

    def get_entries_for_month(
        self, year: int, month: int
    ) -> Dict[str, List[CalendarEntry]]:
        """Get entries for a month."""
        from calendar import monthrange

        days_in_month = monthrange(year, month)[1]
        month_entries = {}

        for day in range(1, days_in_month + 1):
            date = datetime(year, month, day)
            day_str = date.strftime("%Y-%m-%d")
            entries = self.get_entries_for_date(date)
            if entries:
                month_entries[day_str] = entries

        return month_entries

    def get_upcoming_deadlines(self, days: int = 7) -> List[CalendarEntry]:
        """Get entries with upcoming deadlines."""
        now = datetime.now()
        cutoff = now + timedelta(days=days)

        upcoming = [
            e
            for e in self.entries.values()
            if e.deadline and now <= e.deadline <= cutoff
        ]
        return sorted(upcoming, key=lambda x: x.deadline)

    def check_conflicts(self, entry: CalendarEntry) -> List[CalendarEntry]:
        """Check for scheduling conflicts."""
        if not entry.scheduled_date:
            return []

        same_day = self.get_entries_for_date(entry.scheduled_date)

        # Check for same author on same day
        conflicts = []
        for e in same_day:
            if e.author and entry.author and e.author.id == entry.author.id:
                conflicts.append(e)

        return conflicts

    def suggest_schedule_slot(
        self, content_type: ContentType, preferred_days: Optional[List[int]] = None
    ) -> datetime:
        """Suggest optimal publishing time."""
        # Best times by content type (simplified)
        optimal_hours = {
            ContentType.PRODUCT_REVIEW: 10,
            ContentType.BUYING_GUIDE: 14,
            ContentType.HOW_TO: 11,
            ContentType.NEWS: 8,
            ContentType.DEAL_ALERT: 9,
            ContentType.COMPARISON: 13,
            ContentType.TUTORIAL: 15,
            ContentType.ANNOUNCEMENT: 10,
        }

        hour = optimal_hours.get(content_type, 10)

        # Find next available slot
        date = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)

        if preferred_days:
            # Find next preferred day
            while date.weekday() not in preferred_days:
                date += timedelta(days=1)
        else:
            # Default: avoid weekends for business content
            while date.weekday() >= 5:  # Saturday or Sunday
                date += timedelta(days=1)

        # Make sure it's in the future
        if date <= datetime.now():
            date += timedelta(days=1)
            while date.weekday() >= 5:
                date += timedelta(days=1)

        return date

    def generate_calendar_view(self, year: int, month: int) -> str:
        """Generate text calendar view."""
        from calendar import month_name, monthcalendar

        entries = self.get_entries_for_month(year, month)
        cal = monthcalendar(year, month)

        lines = [f"\n{'=' * 60}"]
        lines.append(f"  {month_name[month]} {year}")
        lines.append("=" * 60)
        lines.append("  Mon   Tue   Wed   Thu   Fri   Sat   Sun")
        lines.append("-" * 60)

        for week in cal:
            week_line = ""
            for day in week:
                if day == 0:
                    week_line += "      "
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    count = len(entries.get(date_str, []))
                    if count > 0:
                        week_line += f"  {day:2d}* "
                    else:
                        week_line += f"  {day:2d}  "
            lines.append(week_line)

        lines.append("-" * 60)
        lines.append("* = Scheduled content")

        return "\n".join(lines)


# ============================================================================
# DRAFT/PUBLISH WORKFLOW
# ============================================================================


class WorkflowState(Enum):
    """Workflow states."""

    IDEA = "idea"
    DRAFTING = "drafting"
    REVIEW = "review"
    REVISION = "revision"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"


@dataclass
class WorkflowTask:
    """Workflow task assignment."""

    post_id: int
    state: WorkflowState
    assigned_to: Optional[Author] = None
    assigned_by: Optional[Author] = None
    due_date: Optional[datetime] = None
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class PublishingWorkflow:
    """Manages content publishing workflow."""

    def __init__(self, content_manager: ContentManager):
        self.manager = content_manager
        self.tasks: Dict[int, List[WorkflowTask]] = {}
        self.current_states: Dict[int, WorkflowState] = {}

    def start_workflow(self, post: BlogPost, author: Author) -> WorkflowTask:
        """Start workflow for a post."""
        task = WorkflowTask(
            post_id=post.id,
            state=WorkflowState.IDEA,
            assigned_to=author,
            assigned_by=author,
        )

        if post.id not in self.tasks:
            self.tasks[post.id] = []

        self.tasks[post.id].append(task)
        self.current_states[post.id] = WorkflowState.IDEA

        return task

    def transition(
        self,
        post_id: int,
        new_state: WorkflowState,
        assigned_to: Optional[Author] = None,
        notes: str = "",
    ) -> WorkflowTask:
        """Transition post to new workflow state."""
        current = self.current_states.get(post_id)

        # Validate transition
        valid_transitions = {
            WorkflowState.IDEA: [WorkflowState.DRAFTING],
            WorkflowState.DRAFTING: [WorkflowState.REVIEW],
            WorkflowState.REVIEW: [WorkflowState.REVISION, WorkflowState.APPROVED],
            WorkflowState.REVISION: [WorkflowState.REVIEW],
            WorkflowState.APPROVED: [WorkflowState.SCHEDULED, WorkflowState.PUBLISHED],
            WorkflowState.SCHEDULED: [WorkflowState.PUBLISHED],
            WorkflowState.PUBLISHED: [],
        }

        if current and new_state not in valid_transitions.get(current, []):
            raise ValueError(f"Invalid transition from {current} to {new_state}")

        # Complete current task
        if post_id in self.tasks and self.tasks[post_id]:
            current_task = self.tasks[post_id][-1]
            current_task.completed_at = datetime.now()

        # Create new task
        task = WorkflowTask(
            post_id=post_id,
            state=new_state,
            assigned_to=assigned_to,
            notes=notes,
        )

        self.tasks[post_id].append(task)
        self.current_states[post_id] = new_state

        return task

    def get_posts_by_state(self, state: WorkflowState) -> List[int]:
        """Get all posts in a specific state."""
        return [
            post_id
            for post_id, current_state in self.current_states.items()
            if current_state == state
        ]

    def get_workflow_history(self, post_id: int) -> List[WorkflowTask]:
        """Get workflow history for a post."""
        return self.tasks.get(post_id, [])

    def get_pending_reviews(self, reviewer: Author) -> List[int]:
        """Get posts pending review by specific reviewer."""
        pending = []
        for post_id, tasks in self.tasks.items():
            if tasks:
                current = tasks[-1]
                if (
                    current.state == WorkflowState.REVIEW
                    and current.assigned_to
                    and current.assigned_to.id == reviewer.id
                    and not current.completed_at
                ):
                    pending.append(post_id)
        return pending


# ============================================================================
# REVISION MANAGER
# ============================================================================


class RevisionManager:
    """Manages post revisions and history."""

    def __init__(self, api_client: WordPressAPIClient):
        self.api = api_client
        self.local_revisions: Dict[int, List[Revision]] = {}

    async def get_revisions(self, post_id: int) -> List[Revision]:
        """Get all revisions for a post."""
        # In real implementation, fetch from API
        return self.local_revisions.get(post_id, [])

    def create_local_revision(self, post: BlogPost, author: Author) -> Revision:
        """Create a local revision snapshot."""
        revisions = self.local_revisions.get(post.id, [])

        revision = Revision(
            id=len(revisions) + 1,
            post_id=post.id,
            author_id=author.id,
            date=datetime.now(),
            title=post.title,
            content=post.content,
            excerpt=post.excerpt,
        )

        if post.id not in self.local_revisions:
            self.local_revisions[post.id] = []

        self.local_revisions[post.id].append(revision)

        return revision

    def compare_revisions(
        self, post_id: int, revision_a: int, revision_b: int
    ) -> Dict[str, Any]:
        """Compare two revisions."""
        revisions = self.local_revisions.get(post_id, [])

        rev_a = next((r for r in revisions if r.id == revision_a), None)
        rev_b = next((r for r in revisions if r.id == revision_b), None)

        if not rev_a or not rev_b:
            return {"error": "Revision not found"}

        return rev_a.get_diff_summary(rev_b)

    async def restore_revision(self, post_id: int, revision_id: int) -> bool:
        """Restore a specific revision."""
        return await self.api.restore_revision(post_id, revision_id)

    def get_revision_stats(self, post_id: int) -> Dict[str, Any]:
        """Get revision statistics for a post."""
        revisions = self.local_revisions.get(post_id, [])

        if not revisions:
            return {"count": 0}

        authors = {r.author_id for r in revisions}
        dates = [r.date for r in revisions]

        return {
            "count": len(revisions),
            "unique_authors": len(authors),
            "first_revision": min(dates).isoformat() if dates else None,
            "last_revision": max(dates).isoformat() if dates else None,
            "avg_content_length": sum(len(r.content) for r in revisions)
            // len(revisions),
        }


# ============================================================================
# FEATURED IMAGE MANAGER
# ============================================================================


class FeaturedImageManager:
    """Manages featured images."""

    def __init__(self, api_client: WordPressAPIClient):
        self.api = api_client

    def generate_alt_text(self, title: str, category: str = "") -> str:
        """Generate alt text for featured image."""
        alt_text = title
        if category:
            alt_text = f"{title} - {category}"
        return alt_text[:125]  # WordPress limit

    def suggest_image_dimensions(self, content_type: ContentType) -> Tuple[int, int]:
        """Suggest optimal image dimensions."""
        dimensions = {
            ContentType.PRODUCT_REVIEW: (1200, 628),
            ContentType.BUYING_GUIDE: (1200, 800),
            ContentType.HOW_TO: (1200, 675),
            ContentType.NEWS: (1200, 628),
            ContentType.DEAL_ALERT: (1200, 628),
            ContentType.COMPARISON: (1200, 800),
            ContentType.TUTORIAL: (1200, 675),
            ContentType.ANNOUNCEMENT: (1200, 628),
        }
        return dimensions.get(content_type, (1200, 628))

    async def upload_featured_image(
        self, file_path: str, post: BlogPost
    ) -> FeaturedImage:
        """Upload and configure featured image."""
        alt_text = self.generate_alt_text(
            post.title, post.categories[0].name if post.categories else ""
        )

        result = await self.api.upload_media(
            file_path=file_path,
            title=post.title,
            alt_text=alt_text,
            caption=f"Featured image for: {post.title}",
        )

        width, height = self.suggest_image_dimensions(post.content_type)

        return FeaturedImage(
            id=result.get("id"),
            url=result.get("source_url", ""),
            alt_text=alt_text,
            title=post.title,
            caption=f"Featured image for: {post.title}",
            width=width,
            height=height,
            file_path=file_path,
        )

    def validate_image(self, image: FeaturedImage) -> List[str]:
        """Validate featured image."""
        issues = []

        if not image.alt_text:
            issues.append("Missing alt text - required for accessibility and SEO")

        if len(image.alt_text) > 125:
            issues.append(f"Alt text too long ({len(image.alt_text)} chars, max 125)")

        if image.width < 1200:
            issues.append(f"Image width ({image.width}px) below recommended 1200px")

        if image.width > 0 and image.height > 0:
            ratio = image.width / image.height
            if ratio < 1.5 or ratio > 2.5:
                issues.append(
                    f"Unusual aspect ratio ({ratio:.2f}), recommended 1.91:1 for social"
                )

        return issues


# ============================================================================
# CONTENT TEMPLATES
# ============================================================================


class ContentTemplates:
    """Pre-built content templates for electronics store."""

    @staticmethod
    def product_review_template() -> str:
        """Product review template."""
        return """
<!-- wp:heading {"level":2} -->
<h2>Overview</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Product overview and first impressions]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Key Features</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul>
<li>[Feature 1]</li>
<li>[Feature 2]</li>
<li>[Feature 3]</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading {"level":2} -->
<h2>Design & Build Quality</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Description of design and build]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Performance</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Performance analysis and benchmarks]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Pros & Cons</h2>
<!-- /wp:heading -->

<!-- wp:columns -->
<div class="wp-block-columns">
<!-- wp:column -->
<div class="wp-block-column">
<h3>Pros</h3>
<ul>
<li>[Pro 1]</li>
<li>[Pro 2]</li>
<li>[Pro 3]</li>
</ul>
</div>
<!-- /wp:column -->
<!-- wp:column -->
<div class="wp-block-column">
<h3>Cons</h3>
<ul>
<li>[Con 1]</li>
<li>[Con 2]</li>
</ul>
</div>
<!-- /wp:column -->
</div>
<!-- /wp:columns -->

<!-- wp:heading {"level":2} -->
<h2>Verdict</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Final verdict and recommendation]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Rating</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><strong>Overall Score:</strong> [X]/10</p>
<!-- /wp:paragraph -->
"""

    @staticmethod
    def buying_guide_template() -> str:
        """Buying guide template."""
        return """
<!-- wp:heading {"level":2} -->
<h2>Introduction</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Why this guide exists and who it's for]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>What to Consider</h2>
<!-- /wp:heading -->

<!-- wp:heading {"level":3} -->
<h3>Budget</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Budget considerations and price ranges]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3>Key Features to Look For</h3>
<!-- /wp:heading -->

<!-- wp:list -->
<ul>
<li>[Feature 1 and why it matters]</li>
<li>[Feature 2 and why it matters]</li>
<li>[Feature 3 and why it matters]</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading {"level":2} -->
<h2>Our Top Picks</h2>
<!-- /wp:heading -->

<!-- wp:heading {"level":3} -->
<h3>Best Overall: [Product Name]</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Why it's the best overall choice]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3>Best Budget: [Product Name]</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Why it's the best budget choice]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3>Best Premium: [Product Name]</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Why it's the best premium choice]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Comparison Table</h2>
<!-- /wp:heading -->

<!-- wp:table -->
<figure class="wp-block-table">
<table>
<thead>
<tr><th>Product</th><th>Price</th><th>Key Feature</th><th>Rating</th></tr>
</thead>
<tbody>
<tr><td>[Product 1]</td><td>[Price]</td><td>[Feature]</td><td>[Rating]</td></tr>
<tr><td>[Product 2]</td><td>[Price]</td><td>[Feature]</td><td>[Rating]</td></tr>
<tr><td>[Product 3]</td><td>[Price]</td><td>[Feature]</td><td>[Rating]</td></tr>
</tbody>
</table>
</figure>
<!-- /wp:table -->

<!-- wp:heading {"level":2} -->
<h2>Final Thoughts</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Summary and final recommendations]</p>
<!-- /wp:paragraph -->
"""

    @staticmethod
    def deal_alert_template() -> str:
        """Deal alert template."""
        return """
<!-- wp:heading {"level":2} -->
<h2>🔥 Deal Alert: [Product Name]</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {"className":"deal-price"} -->
<p class="deal-price"><strong>Was:</strong> <del>[Original Price]</del><br>
<strong>Now:</strong> <span class="sale-price">[Sale Price]</span><br>
<strong>Save:</strong> [Savings Amount] ([Percentage]% off)</p>
<!-- /wp:paragraph -->

<!-- wp:buttons -->
<div class="wp-block-buttons">
<!-- wp:button {"backgroundColor":"vivid-red"} -->
<div class="wp-block-button"><a class="wp-block-button__link has-vivid-red-background-color has-background" href="[Affiliate Link]">Get This Deal</a></div>
<!-- /wp:button -->
</div>
<!-- /wp:buttons -->

<!-- wp:heading {"level":3} -->
<h3>Why This Deal is Great</h3>
<!-- /wp:heading -->

<!-- wp:list -->
<ul>
<li>[Reason 1]</li>
<li>[Reason 2]</li>
<li>[Reason 3]</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading {"level":3} -->
<h3>Product Highlights</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Brief product description and key features]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3>Deal Details</h3>
<!-- /wp:heading -->

<!-- wp:list -->
<ul>
<li><strong>Retailer:</strong> [Store Name]</li>
<li><strong>Valid Until:</strong> [Expiry Date]</li>
<li><strong>Coupon Code:</strong> [Code if applicable]</li>
</ul>
<!-- /wp:list -->

<!-- wp:paragraph {"className":"deal-disclaimer"} -->
<p class="deal-disclaimer"><em>Prices and availability subject to change. We may earn a commission from purchases.</em></p>
<!-- /wp:paragraph -->
"""

    @staticmethod
    def comparison_template() -> str:
        """Product comparison template."""
        return """
<!-- wp:heading {"level":2} -->
<h2>[Product A] vs [Product B]: Which Should You Buy?</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Introduction explaining the comparison]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Quick Comparison</h2>
<!-- /wp:heading -->

<!-- wp:table -->
<figure class="wp-block-table">
<table>
<thead>
<tr><th>Specification</th><th>[Product A]</th><th>[Product B]</th></tr>
</thead>
<tbody>
<tr><td>Price</td><td>[Price A]</td><td>[Price B]</td></tr>
<tr><td>[Spec 1]</td><td>[Value A]</td><td>[Value B]</td></tr>
<tr><td>[Spec 2]</td><td>[Value A]</td><td>[Value B]</td></tr>
<tr><td>[Spec 3]</td><td>[Value A]</td><td>[Value B]</td></tr>
</tbody>
</table>
</figure>
<!-- /wp:table -->

<!-- wp:heading {"level":2} -->
<h2>Design Comparison</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Compare design elements]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Performance Comparison</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Compare performance metrics]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Features Comparison</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Compare features]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Value for Money</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Compare value proposition]</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>The Verdict</h2>
<!-- /wp:heading -->

<!-- wp:columns -->
<div class="wp-block-columns">
<!-- wp:column -->
<div class="wp-block-column">
<h3>Choose [Product A] If:</h3>
<ul>
<li>[Reason 1]</li>
<li>[Reason 2]</li>
</ul>
</div>
<!-- /wp:column -->
<!-- wp:column -->
<div class="wp-block-column">
<h3>Choose [Product B] If:</h3>
<ul>
<li>[Reason 1]</li>
<li>[Reason 2]</li>
</ul>
</div>
<!-- /wp:column -->
</div>
<!-- /wp:columns -->
"""

    @classmethod
    def get_template(cls, content_type: ContentType) -> str:
        """Get template for content type."""
        templates = {
            ContentType.PRODUCT_REVIEW: cls.product_review_template,
            ContentType.BUYING_GUIDE: cls.buying_guide_template,
            ContentType.DEAL_ALERT: cls.deal_alert_template,
            ContentType.COMPARISON: cls.comparison_template,
        }

        template_func = templates.get(content_type)
        if template_func:
            return template_func()

        # Default template
        return """
<!-- wp:paragraph -->
<p>[Your content here]</p>
<!-- /wp:paragraph -->
"""


# ============================================================================
# MAIN CONTENT MANAGER AGENT
# ============================================================================


class WordPressContentAgent:
    """Main WordPress content management agent."""

    def __init__(
        self,
        site_url: str = "",
        username: str = "",
        password: str = "",
        demo_mode: bool = False,
    ):
        self.demo_mode = demo_mode
        self.site_url = site_url

        if demo_mode:
            self.api = None
            self.content_manager = None
        else:
            self.api = WordPressAPIClient(site_url, username, password)
            self.content_manager = ContentManager(self.api)

        self.calendar = None
        self.workflow = None
        self.revision_manager = None
        self.image_manager = None
        self.templates = ContentTemplates()

    async def initialize(self):
        """Initialize all components."""
        if self.demo_mode:
            logger.info("Running in demo mode - using sample data")
            self._setup_demo_data()
        else:
            await self.content_manager.initialize()

        self.calendar = ContentCalendar(self.content_manager)
        self.workflow = PublishingWorkflow(self.content_manager)
        self.revision_manager = RevisionManager(self.api) if self.api else None
        self.image_manager = FeaturedImageManager(self.api) if self.api else None

    def _setup_demo_data(self):
        """Setup demo data for demonstration."""

        # Create mock content manager with demo data
        class MockAPI:
            site_url = "https://demo-electronics.com"
            api_url = f"{site_url}/wp-json/wp/v2"

        self.api = MockAPI()
        self.content_manager = ContentManager(self.api)

        # Manually populate caches
        asyncio.get_event_loop().run_until_complete(
            self.content_manager._load_categories()
        )
        asyncio.get_event_loop().run_until_complete(self.content_manager._load_tags())
        asyncio.get_event_loop().run_until_complete(
            self.content_manager._load_authors()
        )

    def create_post(
        self, title: str, content_type: ContentType, use_template: bool = True
    ) -> BlogPost:
        """Create a new post with template."""
        content = ""
        if use_template:
            content = self.templates.get_template(content_type)

        post = BlogPost(
            title=title,
            content=content,
            content_type=content_type,
            status=PostStatus.DRAFT,
            seo=SEOMetadata(title=title),
        )

        # Suggest categories
        if self.content_manager:
            post.categories = self.content_manager.suggest_categories(content_type)

        return post

    def generate_seo_metadata(self, post: BlogPost) -> SEOMetadata:
        """Generate SEO metadata for a post."""
        # Generate meta title (max 60 chars)
        title = post.title
        if len(title) > 57:
            title = title[:57] + "..."

        # Generate meta description
        description = post.generate_excerpt(155)

        # Suggest focus keyword
        words = post.title.lower().split()
        focus_keyword = " ".join(words[:3])  # First 3 words

        # Suggest keywords
        keywords = []
        if self.content_manager:
            suggested_tags = self.content_manager.suggest_tags(post.title, post.content)
            keywords = [t.name for t in suggested_tags]

        return SEOMetadata(
            title=f"{title} | Your Electronics Store",
            description=description,
            keywords=keywords,
            focus_keyword=focus_keyword,
            og_title=post.title,
            og_description=description,
        )

    def schedule_post(
        self, post: BlogPost, scheduled_date: Optional[datetime] = None
    ) -> CalendarEntry:
        """Schedule a post for publication."""
        if not scheduled_date:
            scheduled_date = self.calendar.suggest_schedule_slot(post.content_type)

        post.status = PostStatus.FUTURE
        post.publish_date = scheduled_date

        entry = CalendarEntry(
            post_id=post.id,
            title=post.title,
            content_type=post.content_type,
            scheduled_date=scheduled_date,
            author=post.author,
            status=post.status,
        )

        self.calendar.add_entry(entry)

        return entry

    def get_content_report(self) -> Dict[str, Any]:
        """Generate content status report."""
        report = {
            "total_categories": len(self.content_manager.categories_cache),
            "total_tags": len(self.content_manager.tags_cache),
            "total_authors": len(self.content_manager.authors_cache),
            "workflow_states": {},
            "upcoming_publications": [],
            "pending_reviews": [],
        }

        # Workflow state counts
        for state in WorkflowState:
            count = len(self.workflow.get_posts_by_state(state))
            if count > 0:
                report["workflow_states"][state.value] = count

        # Upcoming deadlines
        upcoming = self.calendar.get_upcoming_deadlines(7)
        report["upcoming_publications"] = [
            {
                "title": e.title,
                "date": e.deadline.isoformat() if e.deadline else None,
                "author": e.author.display_name if e.author else "Unassigned",
            }
            for e in upcoming[:5]
        ]

        return report

    def demo_run(self):
        """Run demonstration of content management features."""
        print("\n" + "=" * 70)
        print("  WordPress Content Manager - Demo Mode")
        print("  Electronics Store Blog Management System")
        print("=" * 70)

        # Demo 1: Create a product review
        print("\n📝 Creating a new product review...")
        post = self.create_post(
            "Best Wireless Earbuds Under $100 in 2024", ContentType.PRODUCT_REVIEW
        )
        print(f"   Title: {post.title}")
        print(f"   Type: {post.content_type.value}")
        print(f"   Status: {post.status.value}")

        # Demo 2: Generate SEO metadata
        print("\n🔍 Generating SEO metadata...")
        seo = self.generate_seo_metadata(post)
        post.seo = seo
        print(f"   Meta Title: {seo.title}")
        print(f"   Focus Keyword: {seo.focus_keyword}")
        print(f"   Keywords: {', '.join(seo.keywords[:3])}")

        # Demo 3: Category suggestions
        print("\n📁 Suggested categories:")
        for cat in post.categories[:3]:
            print(f"   - {cat.name} ({cat.count} posts)")

        # Demo 4: Tag suggestions
        print("\n🏷️  Suggested tags:")
        if self.content_manager:
            tags = self.content_manager.suggest_tags(post.title, post.content)
            for tag in tags[:5]:
                print(f"   - {tag.name}")

        # Demo 5: Content calendar
        print("\n📅 Content Calendar Preview:")
        now = datetime.now()
        print(self.calendar.generate_calendar_view(now.year, now.month))

        # Demo 6: Schedule the post
        print("\n⏰ Scheduling post...")
        entry = self.schedule_post(post)
        print(f"   Scheduled for: {entry.scheduled_date}")

        # Demo 7: Workflow demonstration
        print("\n🔄 Starting publishing workflow...")
        author = Author(id=1, display_name="Alex Chen", role=AuthorRole.EDITOR)
        post.id = 1
        post.author = author

        task = self.workflow.start_workflow(post, author)
        print(f"   Current state: {task.state.value}")

        task = self.workflow.transition(post.id, WorkflowState.DRAFTING)
        print(f"   Transitioned to: {task.state.value}")

        task = self.workflow.transition(post.id, WorkflowState.REVIEW)
        print(f"   Transitioned to: {task.state.value}")

        # Demo 8: Authors list
        print("\n👥 Available Authors:")
        for author in list(self.content_manager.authors_cache.values())[:3]:
            print(
                f"   - {author.display_name} ({author.role.value}) - {author.post_count} posts"
            )

        # Demo 9: Content report
        print("\n📊 Content Status Report:")
        report = self.get_content_report()
        print(f"   Categories: {report['total_categories']}")
        print(f"   Tags: {report['total_tags']}")
        print(f"   Authors: {report['total_authors']}")

        # Demo 10: Template preview
        print("\n📋 Available Content Templates:")
        for ct in [
            ContentType.PRODUCT_REVIEW,
            ContentType.BUYING_GUIDE,
            ContentType.DEAL_ALERT,
            ContentType.COMPARISON,
        ]:
            template = self.templates.get_template(ct)
            line_count = len(template.strip().split("\n"))
            print(f"   - {ct.value}: {line_count} lines")

        print("\n" + "=" * 70)
        print("  Demo Complete! Ready to manage your electronics store content.")
        print("=" * 70 + "\n")


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WordPress Content Manager for Electronics Store"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Run in demo mode with sample data"
    )
    parser.add_argument("--url", type=str, help="WordPress site URL")
    parser.add_argument("--user", type=str, help="WordPress username")
    parser.add_argument("--password", type=str, help="WordPress application password")
    parser.add_argument("--create", type=str, help="Create new post with given title")
    parser.add_argument(
        "--type",
        type=str,
        choices=[ct.value for ct in ContentType],
        default="news",
        help="Content type for new post",
    )
    parser.add_argument("--calendar", action="store_true", help="Show content calendar")
    parser.add_argument("--report", action="store_true", help="Generate content report")

    args = parser.parse_args()

    # Create agent
    demo_mode = args.demo or not all([args.url, args.user, args.password])

    agent = WordPressContentAgent(
        site_url=args.url or "",
        username=args.user or "",
        password=args.password or "",
        demo_mode=demo_mode,
    )

    # Initialize
    loop = asyncio.get_event_loop()
    loop.run_until_complete(agent.initialize())

    # Run actions
    if args.demo:
        agent.demo_run()
    elif args.create:
        content_type = ContentType(args.type)
        post = agent.create_post(args.create, content_type)
        print(f"Created post: {post.title}")
        print(f"Slug: {post.generate_slug()}")
    elif args.calendar:
        now = datetime.now()
        print(agent.calendar.generate_calendar_view(now.year, now.month))
    elif args.report:
        report = agent.get_content_report()
        print(json.dumps(report, indent=2))
    else:
        agent.demo_run()


if __name__ == "__main__":
    main()
