#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WordPress SEO Assistant - Agentic Brain Example #77

A comprehensive SEO assistant for WordPress/WooCommerce sites:
- On-page SEO analysis
- Keyword research helper
- Meta tag optimization
- Internal linking suggestions
- Image alt text generator
- Schema markup recommendations
- Sitemap management
- Search console integration patterns

Perfect for optimizing an electronics store for search engines.

Usage:
    python 77_wordpress_seo_assistant.py --demo
    python 77_wordpress_seo_assistant.py --analyze "https://example.com/product/wireless-earbuds"
"""

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class SEOScore(Enum):
    """SEO score levels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    NEEDS_WORK = "needs_work"
    POOR = "poor"
    CRITICAL = "critical"


class ContentType(Enum):
    """Content types for SEO analysis."""

    PRODUCT = "product"
    CATEGORY = "category"
    BLOG_POST = "blog_post"
    PAGE = "page"
    HOME = "home"
    LANDING = "landing"


class SchemaType(Enum):
    """Schema.org types."""

    PRODUCT = "Product"
    ORGANIZATION = "Organization"
    LOCAL_BUSINESS = "LocalBusiness"
    ARTICLE = "Article"
    BLOG_POSTING = "BlogPosting"
    FAQ_PAGE = "FAQPage"
    HOW_TO = "HowTo"
    REVIEW = "Review"
    BREADCRUMB_LIST = "BreadcrumbList"
    WEBSITE = "WebSite"
    OFFER = "Offer"
    AGGREGATE_RATING = "AggregateRating"


class KeywordDifficulty(Enum):
    """Keyword difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    VERY_HARD = "very_hard"


class SearchIntent(Enum):
    """Search intent types."""

    INFORMATIONAL = "informational"
    NAVIGATIONAL = "navigational"
    COMMERCIAL = "commercial"
    TRANSACTIONAL = "transactional"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class Keyword:
    """Keyword data."""

    keyword: str
    search_volume: int = 0
    difficulty: KeywordDifficulty = KeywordDifficulty.MEDIUM
    cpc: float = 0.0
    intent: SearchIntent = SearchIntent.INFORMATIONAL
    trend: str = "stable"  # growing, stable, declining
    related_keywords: List[str] = field(default_factory=list)
    long_tail_variants: List[str] = field(default_factory=list)

    def get_priority_score(self) -> float:
        """Calculate priority score based on volume and difficulty."""
        difficulty_weights = {
            KeywordDifficulty.EASY: 1.0,
            KeywordDifficulty.MEDIUM: 0.7,
            KeywordDifficulty.HARD: 0.4,
            KeywordDifficulty.VERY_HARD: 0.2,
        }

        volume_score = min(self.search_volume / 10000, 1.0)
        difficulty_score = difficulty_weights.get(self.difficulty, 0.5)

        return (volume_score * 0.6 + difficulty_score * 0.4) * 100


@dataclass
class MetaTags:
    """Meta tag data."""

    title: str = ""
    description: str = ""
    robots: str = "index, follow"
    canonical: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_type: str = "website"
    twitter_card: str = "summary_large_image"
    twitter_title: str = ""
    twitter_description: str = ""
    twitter_image: str = ""

    def validate(self) -> List[Dict[str, Any]]:
        """Validate meta tags and return issues."""
        issues = []

        # Title validation
        if not self.title:
            issues.append(
                {
                    "field": "title",
                    "severity": "critical",
                    "issue": "Missing meta title",
                    "recommendation": "Add a unique, keyword-rich title (50-60 characters)",
                }
            )
        elif len(self.title) < 30:
            issues.append(
                {
                    "field": "title",
                    "severity": "warning",
                    "issue": f"Title too short ({len(self.title)} chars)",
                    "recommendation": "Aim for 50-60 characters to maximize SERP visibility",
                }
            )
        elif len(self.title) > 60:
            issues.append(
                {
                    "field": "title",
                    "severity": "warning",
                    "issue": f"Title may be truncated ({len(self.title)} chars)",
                    "recommendation": "Keep title under 60 characters",
                }
            )

        # Description validation
        if not self.description:
            issues.append(
                {
                    "field": "description",
                    "severity": "critical",
                    "issue": "Missing meta description",
                    "recommendation": "Add a compelling description (120-155 characters)",
                }
            )
        elif len(self.description) < 100:
            issues.append(
                {
                    "field": "description",
                    "severity": "warning",
                    "issue": f"Description too short ({len(self.description)} chars)",
                    "recommendation": "Aim for 120-155 characters for optimal display",
                }
            )
        elif len(self.description) > 160:
            issues.append(
                {
                    "field": "description",
                    "severity": "warning",
                    "issue": f"Description may be truncated ({len(self.description)} chars)",
                    "recommendation": "Keep description under 160 characters",
                }
            )

        # Canonical validation
        if not self.canonical:
            issues.append(
                {
                    "field": "canonical",
                    "severity": "warning",
                    "issue": "Missing canonical URL",
                    "recommendation": "Add canonical URL to prevent duplicate content issues",
                }
            )

        # Open Graph validation
        if not self.og_image:
            issues.append(
                {
                    "field": "og_image",
                    "severity": "info",
                    "issue": "Missing Open Graph image",
                    "recommendation": "Add og:image for better social sharing (1200x630px)",
                }
            )

        return issues

    def to_html(self) -> str:
        """Generate HTML meta tags."""
        tags = []

        if self.title:
            tags.append(f"<title>{self.title}</title>")

        if self.description:
            tags.append(f'<meta name="description" content="{self.description}">')

        if self.robots:
            tags.append(f'<meta name="robots" content="{self.robots}">')

        if self.canonical:
            tags.append(f'<link rel="canonical" href="{self.canonical}">')

        # Open Graph
        if self.og_title:
            tags.append(f'<meta property="og:title" content="{self.og_title}">')
        if self.og_description:
            tags.append(
                f'<meta property="og:description" content="{self.og_description}">'
            )
        if self.og_image:
            tags.append(f'<meta property="og:image" content="{self.og_image}">')
        if self.og_type:
            tags.append(f'<meta property="og:type" content="{self.og_type}">')

        # Twitter
        if self.twitter_card:
            tags.append(f'<meta name="twitter:card" content="{self.twitter_card}">')
        if self.twitter_title:
            tags.append(f'<meta name="twitter:title" content="{self.twitter_title}">')
        if self.twitter_description:
            tags.append(
                f'<meta name="twitter:description" content="{self.twitter_description}">'
            )
        if self.twitter_image:
            tags.append(f'<meta name="twitter:image" content="{self.twitter_image}">')

        return "\n".join(tags)


@dataclass
class ImageSEO:
    """Image SEO data."""

    url: str
    alt_text: str = ""
    title: str = ""
    filename: str = ""
    width: int = 0
    height: int = 0
    file_size: int = 0  # bytes
    format: str = ""

    def validate(self) -> List[Dict[str, Any]]:
        """Validate image SEO."""
        issues = []

        if not self.alt_text:
            issues.append(
                {
                    "field": "alt_text",
                    "severity": "warning",
                    "issue": "Missing alt text",
                    "recommendation": "Add descriptive alt text for accessibility and SEO",
                }
            )
        elif len(self.alt_text) > 125:
            issues.append(
                {
                    "field": "alt_text",
                    "severity": "info",
                    "issue": f"Alt text too long ({len(self.alt_text)} chars)",
                    "recommendation": "Keep alt text under 125 characters",
                }
            )

        if self.file_size > 200000:  # 200KB
            size_kb = self.file_size / 1024
            issues.append(
                {
                    "field": "file_size",
                    "severity": "warning",
                    "issue": f"Large image file ({size_kb:.0f}KB)",
                    "recommendation": "Compress image to under 200KB for faster loading",
                }
            )

        if self.format.lower() not in ["webp", "avif"]:
            issues.append(
                {
                    "field": "format",
                    "severity": "info",
                    "issue": f"Using {self.format} format",
                    "recommendation": "Consider WebP or AVIF for better compression",
                }
            )

        return issues


@dataclass
class InternalLink:
    """Internal link data."""

    source_url: str
    target_url: str
    anchor_text: str
    context: str = ""  # surrounding text
    is_followed: bool = True
    position: str = "content"  # content, navigation, footer, sidebar

    def validate(self) -> List[Dict[str, Any]]:
        """Validate internal link."""
        issues = []

        if not self.anchor_text:
            issues.append(
                {
                    "severity": "warning",
                    "issue": "Empty anchor text",
                    "recommendation": "Use descriptive anchor text with relevant keywords",
                }
            )
        elif self.anchor_text.lower() in [
            "click here",
            "read more",
            "learn more",
            "here",
        ]:
            issues.append(
                {
                    "severity": "info",
                    "issue": f"Generic anchor text: '{self.anchor_text}'",
                    "recommendation": "Use descriptive, keyword-rich anchor text",
                }
            )

        return issues


@dataclass
class ContentAnalysis:
    """Content analysis results."""

    url: str
    title: str = ""
    word_count: int = 0
    heading_structure: Dict[str, int] = field(
        default_factory=dict
    )  # {"h1": 1, "h2": 3, ...}
    keyword_density: Dict[str, float] = field(default_factory=dict)
    readability_score: float = 0.0
    images: List[ImageSEO] = field(default_factory=list)
    internal_links: List[InternalLink] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    meta_tags: Optional[MetaTags] = None
    schema_markup: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 0.0

    def calculate_score(self) -> float:
        """Calculate overall SEO score."""
        score = 100.0

        # Penalize for issues
        for issue in self.issues:
            if issue.get("severity") == "critical":
                score -= 20
            elif issue.get("severity") == "warning":
                score -= 10
            elif issue.get("severity") == "info":
                score -= 3

        # Bonus for good practices
        if self.word_count >= 1000:
            score += 5
        if self.heading_structure.get("h1") == 1:
            score += 5
        if len(self.internal_links) >= 3:
            score += 5
        if self.schema_markup:
            score += 10

        self.score = max(0, min(100, score))
        return self.score

    def get_score_level(self) -> SEOScore:
        """Get score level."""
        if self.score >= 90:
            return SEOScore.EXCELLENT
        elif self.score >= 70:
            return SEOScore.GOOD
        elif self.score >= 50:
            return SEOScore.NEEDS_WORK
        elif self.score >= 30:
            return SEOScore.POOR
        else:
            return SEOScore.CRITICAL


@dataclass
class SchemaMarkup:
    """Schema.org markup data."""

    schema_type: SchemaType
    data: Dict[str, Any] = field(default_factory=dict)

    def to_json_ld(self) -> str:
        """Generate JSON-LD script."""
        schema = {
            "@context": "https://schema.org",
            "@type": self.schema_type.value,
            **self.data,
        }
        return f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'


@dataclass
class SitemapEntry:
    """Sitemap entry."""

    loc: str
    lastmod: Optional[datetime] = None
    changefreq: str = "weekly"
    priority: float = 0.5
    images: List[str] = field(default_factory=list)

    def to_xml(self) -> str:
        """Generate XML for sitemap entry."""
        xml = f"  <url>\n    <loc>{self.loc}</loc>\n"

        if self.lastmod:
            xml += f"    <lastmod>{self.lastmod.strftime('%Y-%m-%d')}</lastmod>\n"

        xml += f"    <changefreq>{self.changefreq}</changefreq>\n"
        xml += f"    <priority>{self.priority}</priority>\n"

        for image in self.images:
            xml += f"    <image:image>\n      <image:loc>{image}</image:loc>\n    </image:image>\n"

        xml += "  </url>"
        return xml


@dataclass
class SearchConsoleData:
    """Search Console data."""

    url: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0
    queries: List[Dict[str, Any]] = field(default_factory=list)

    def get_opportunities(self) -> List[Dict[str, Any]]:
        """Identify optimization opportunities."""
        opportunities = []

        # Low CTR but good position
        if self.position <= 10 and self.ctr < 0.05:
            opportunities.append(
                {
                    "type": "low_ctr",
                    "issue": f"Position {self.position:.1f} but only {self.ctr*100:.1f}% CTR",
                    "recommendation": "Improve meta title and description to increase click-through rate",
                }
            )

        # Good impressions but low clicks
        if self.impressions > 1000 and self.clicks < 50:
            opportunities.append(
                {
                    "type": "impressions_vs_clicks",
                    "issue": f"{self.impressions} impressions but only {self.clicks} clicks",
                    "recommendation": "Content is visible but not engaging - optimize snippets",
                }
            )

        # Position 11-20 (page 2)
        if 10 < self.position <= 20:
            opportunities.append(
                {
                    "type": "page_two",
                    "issue": f"Ranking on page 2 (position {self.position:.1f})",
                    "recommendation": "Focus on this page to push to page 1",
                }
            )

        return opportunities


# ============================================================================
# KEYWORD RESEARCH
# ============================================================================


class KeywordResearcher:
    """Keyword research and analysis."""

    # Electronics store keyword categories
    KEYWORD_CATEGORIES = {
        "smartphones": [
            "best smartphones 2024",
            "budget smartphones under $300",
            "flagship phones comparison",
            "5g phones australia",
            "iphone vs samsung",
            "android phones with best camera",
            "phones with longest battery life",
        ],
        "laptops": [
            "best laptops for students",
            "gaming laptops under $1500",
            "business laptops 2024",
            "macbook vs windows laptop",
            "laptops with best battery life",
            "lightweight laptops for travel",
            "2-in-1 convertible laptops",
        ],
        "audio": [
            "best wireless earbuds",
            "noise cancelling headphones",
            "bluetooth speakers outdoor",
            "gaming headset with mic",
            "true wireless earbuds under $100",
            "audiophile headphones",
            "soundbar for tv",
        ],
        "smart_home": [
            "smart home devices",
            "best smart speakers",
            "home security cameras",
            "smart doorbell reviews",
            "smart lighting systems",
            "robot vacuum cleaners",
            "smart thermostat australia",
        ],
        "gaming": [
            "gaming monitors 144hz",
            "mechanical keyboards",
            "gaming mouse wireless",
            "ps5 accessories",
            "gaming chair ergonomic",
            "streaming setup for beginners",
            "gaming desk setup",
        ],
    }

    # Intent modifiers
    INTENT_MODIFIERS = {
        SearchIntent.INFORMATIONAL: [
            "what is",
            "how to",
            "why",
            "guide",
            "tutorial",
            "tips",
            "best way to",
            "learn",
            "understand",
            "explained",
        ],
        SearchIntent.COMMERCIAL: [
            "best",
            "top",
            "review",
            "comparison",
            "vs",
            "alternative",
            "worth it",
            "should i buy",
            "pros and cons",
        ],
        SearchIntent.TRANSACTIONAL: [
            "buy",
            "price",
            "deal",
            "discount",
            "cheap",
            "sale",
            "coupon",
            "free shipping",
            "order",
            "purchase",
        ],
        SearchIntent.NAVIGATIONAL: [
            "brand name",
            "official",
            "login",
            "support",
            "contact",
        ],
    }

    @classmethod
    def get_keywords_for_category(cls, category: str) -> List[Keyword]:
        """Get keywords for a product category."""
        keywords = []

        base_keywords = cls.KEYWORD_CATEGORIES.get(category, [])

        for kw in base_keywords:
            keyword = Keyword(
                keyword=kw,
                search_volume=random.randint(1000, 50000),  # Demo values
                difficulty=random.choice(list(KeywordDifficulty)),
                cpc=round(random.uniform(0.5, 5.0), 2),
                intent=cls.detect_intent(kw),
            )
            keywords.append(keyword)

        return keywords

    @classmethod
    def detect_intent(cls, keyword: str) -> SearchIntent:
        """Detect search intent from keyword."""
        keyword_lower = keyword.lower()

        for intent, modifiers in cls.INTENT_MODIFIERS.items():
            for modifier in modifiers:
                if modifier in keyword_lower:
                    return intent

        return SearchIntent.INFORMATIONAL

    @classmethod
    def generate_long_tail_keywords(
        cls, seed_keyword: str, count: int = 10
    ) -> List[str]:
        """Generate long-tail keyword variations."""
        modifiers_prefix = [
            "best",
            "top",
            "cheap",
            "affordable",
            "premium",
            "professional",
            "wireless",
            "portable",
            "compact",
            "large",
            "small",
            "mini",
        ]

        modifiers_suffix = [
            "for beginners",
            "for professionals",
            "under $100",
            "under $500",
            "in 2024",
            "australia",
            "review",
            "comparison",
            "buying guide",
            "for home",
            "for office",
            "for gaming",
            "for travel",
        ]

        variations = []

        # Prefix variations
        for prefix in modifiers_prefix[: count // 2]:
            variations.append(f"{prefix} {seed_keyword}")

        # Suffix variations
        for suffix in modifiers_suffix[: count // 2]:
            variations.append(f"{seed_keyword} {suffix}")

        return variations[:count]

    @classmethod
    def analyze_keyword_gap(
        cls, target_keywords: List[str], ranking_keywords: List[str]
    ) -> Dict[str, List[str]]:
        """Analyze keyword gaps."""
        target_set = set(kw.lower() for kw in target_keywords)
        ranking_set = set(kw.lower() for kw in ranking_keywords)

        return {
            "missing": list(target_set - ranking_set),
            "ranking": list(ranking_set),
            "opportunity": [kw for kw in target_set if kw not in ranking_set],
        }

    @classmethod
    def suggest_keywords_for_product(
        cls, product_name: str, category: str = ""
    ) -> List[str]:
        """Suggest keywords for a product."""
        suggestions = []

        # Base product keywords
        suggestions.append(product_name.lower())
        suggestions.append(f"{product_name} review")
        suggestions.append(f"{product_name} price")
        suggestions.append(f"buy {product_name}")
        suggestions.append(f"{product_name} vs")

        # Category-based suggestions
        if category:
            suggestions.append(f"best {category}")
            suggestions.append(f"{category} comparison")
            suggestions.append(f"{category} buying guide")

        # Long-tail suggestions
        suggestions.extend(cls.generate_long_tail_keywords(product_name, 5))

        return suggestions


# ============================================================================
# ON-PAGE SEO ANALYZER
# ============================================================================


class OnPageSEOAnalyzer:
    """Analyzes on-page SEO factors."""

    @staticmethod
    def analyze_title(title: str, target_keyword: str = "") -> List[Dict[str, Any]]:
        """Analyze page title."""
        issues = []

        if not title:
            issues.append(
                {
                    "severity": "critical",
                    "issue": "Missing page title",
                    "recommendation": "Add a unique, descriptive title tag",
                }
            )
            return issues

        title_length = len(title)

        if title_length < 30:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"Title too short ({title_length} characters)",
                    "recommendation": "Aim for 50-60 characters to maximize SERP real estate",
                }
            )
        elif title_length > 60:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"Title may be truncated ({title_length} characters)",
                    "recommendation": "Keep title under 60 characters to avoid truncation",
                }
            )

        if target_keyword and target_keyword.lower() not in title.lower():
            issues.append(
                {
                    "severity": "warning",
                    "issue": "Target keyword not in title",
                    "recommendation": f"Include '{target_keyword}' in the title, preferably near the start",
                }
            )
        elif target_keyword and not title.lower().startswith(
            target_keyword.lower()[:20]
        ):
            issues.append(
                {
                    "severity": "info",
                    "issue": "Target keyword not at start of title",
                    "recommendation": "Place the target keyword near the beginning of the title",
                }
            )

        return issues

    @staticmethod
    def analyze_meta_description(
        description: str, target_keyword: str = ""
    ) -> List[Dict[str, Any]]:
        """Analyze meta description."""
        issues = []

        if not description:
            issues.append(
                {
                    "severity": "critical",
                    "issue": "Missing meta description",
                    "recommendation": "Add a compelling meta description (120-155 characters)",
                }
            )
            return issues

        desc_length = len(description)

        if desc_length < 100:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"Description too short ({desc_length} characters)",
                    "recommendation": "Aim for 120-155 characters for optimal display",
                }
            )
        elif desc_length > 160:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"Description may be truncated ({desc_length} characters)",
                    "recommendation": "Keep under 160 characters to avoid truncation",
                }
            )

        if target_keyword and target_keyword.lower() not in description.lower():
            issues.append(
                {
                    "severity": "info",
                    "issue": "Target keyword not in meta description",
                    "recommendation": f"Include '{target_keyword}' naturally in the description",
                }
            )

        # Check for call-to-action
        cta_words = ["buy", "shop", "get", "discover", "learn", "find", "explore"]
        has_cta = any(word in description.lower() for word in cta_words)
        if not has_cta:
            issues.append(
                {
                    "severity": "info",
                    "issue": "No clear call-to-action in description",
                    "recommendation": "Add action words like 'Shop', 'Discover', or 'Learn'",
                }
            )

        return issues

    @staticmethod
    def analyze_headings(
        headings: Dict[str, List[str]], target_keyword: str = ""
    ) -> List[Dict[str, Any]]:
        """Analyze heading structure."""
        issues = []

        h1_count = len(headings.get("h1", []))

        if h1_count == 0:
            issues.append(
                {
                    "severity": "critical",
                    "issue": "Missing H1 heading",
                    "recommendation": "Add exactly one H1 heading containing the main topic",
                }
            )
        elif h1_count > 1:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"Multiple H1 headings ({h1_count})",
                    "recommendation": "Use only one H1 heading per page",
                }
            )

        h2_count = len(headings.get("h2", []))
        if h2_count == 0:
            issues.append(
                {
                    "severity": "warning",
                    "issue": "No H2 headings",
                    "recommendation": "Add H2 subheadings to structure your content",
                }
            )

        # Check keyword in headings
        if target_keyword:
            keyword_lower = target_keyword.lower()
            h1_headings = headings.get("h1", [])

            if h1_headings and keyword_lower not in h1_headings[0].lower():
                issues.append(
                    {
                        "severity": "warning",
                        "issue": "Target keyword not in H1",
                        "recommendation": f"Include '{target_keyword}' in your H1 heading",
                    }
                )

        # Check heading hierarchy
        h1s = len(headings.get("h1", []))
        h2s = len(headings.get("h2", []))
        h3s = len(headings.get("h3", []))

        if h3s > 0 and h2s == 0:
            issues.append(
                {
                    "severity": "info",
                    "issue": "H3 headings without H2",
                    "recommendation": "Maintain proper heading hierarchy (H1 > H2 > H3)",
                }
            )

        return issues

    @staticmethod
    def analyze_content(
        content: str, target_keyword: str = "", min_words: int = 300
    ) -> Dict[str, Any]:
        """Analyze content quality."""
        # Clean HTML
        plain_text = re.sub(r"<[^>]+>", " ", content)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

        # Word count
        words = plain_text.split()
        word_count = len(words)

        issues = []

        if word_count < min_words:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"Thin content ({word_count} words)",
                    "recommendation": f"Aim for at least {min_words} words for better rankings",
                }
            )

        # Keyword density
        keyword_density = 0.0
        if target_keyword and word_count > 0:
            keyword_count = plain_text.lower().count(target_keyword.lower())
            keyword_density = (keyword_count / word_count) * 100

            if keyword_density == 0:
                issues.append(
                    {
                        "severity": "warning",
                        "issue": "Target keyword not found in content",
                        "recommendation": f"Include '{target_keyword}' naturally in your content",
                    }
                )
            elif keyword_density > 3:
                issues.append(
                    {
                        "severity": "warning",
                        "issue": f"Keyword stuffing detected ({keyword_density:.1f}%)",
                        "recommendation": "Reduce keyword density to 1-2% for natural reading",
                    }
                )
            elif keyword_density < 0.5:
                issues.append(
                    {
                        "severity": "info",
                        "issue": f"Low keyword density ({keyword_density:.1f}%)",
                        "recommendation": "Consider adding a few more keyword mentions (aim for 1-2%)",
                    }
                )

        # Readability (simplified Flesch-Kincaid)
        sentences = re.split(r"[.!?]+", plain_text)
        sentence_count = len([s for s in sentences if s.strip()])

        if sentence_count > 0 and word_count > 0:
            avg_sentence_length = word_count / sentence_count

            if avg_sentence_length > 25:
                issues.append(
                    {
                        "severity": "info",
                        "issue": f"Long average sentence length ({avg_sentence_length:.0f} words)",
                        "recommendation": "Shorter sentences (15-20 words) improve readability",
                    }
                )

        return {
            "word_count": word_count,
            "keyword_density": keyword_density,
            "sentence_count": sentence_count,
            "issues": issues,
        }

    @staticmethod
    def analyze_url(url: str, target_keyword: str = "") -> List[Dict[str, Any]]:
        """Analyze URL structure."""
        issues = []

        parsed = urlparse(url)
        path = parsed.path

        # Check URL length
        if len(path) > 100:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"URL path too long ({len(path)} characters)",
                    "recommendation": "Keep URLs short and descriptive (under 75 characters)",
                }
            )

        # Check for keyword
        if target_keyword:
            keyword_slug = target_keyword.lower().replace(" ", "-")
            if keyword_slug not in path.lower():
                issues.append(
                    {
                        "severity": "info",
                        "issue": "Target keyword not in URL",
                        "recommendation": f"Include '{keyword_slug}' in your URL slug",
                    }
                )

        # Check URL format
        if "_" in path:
            issues.append(
                {
                    "severity": "info",
                    "issue": "URL contains underscores",
                    "recommendation": "Use hyphens instead of underscores for word separation",
                }
            )

        if any(char.isupper() for char in path):
            issues.append(
                {
                    "severity": "info",
                    "issue": "URL contains uppercase letters",
                    "recommendation": "Use lowercase URLs for consistency",
                }
            )

        # Check for parameters
        if parsed.query:
            issues.append(
                {
                    "severity": "info",
                    "issue": "URL contains parameters",
                    "recommendation": "Keep URLs clean; use canonical tags if parameters are needed",
                }
            )

        return issues


# ============================================================================
# IMAGE ALT TEXT GENERATOR
# ============================================================================


class AltTextGenerator:
    """Generates SEO-friendly alt text for images."""

    @staticmethod
    def generate_product_alt(
        product_name: str, variant: str = "", angle: str = "", context: str = ""
    ) -> str:
        """Generate alt text for product images."""
        parts = [product_name]

        if variant:
            parts.append(variant)

        if angle:
            angle_descriptions = {
                "front": "front view",
                "back": "back view",
                "side": "side view",
                "top": "top view",
                "detail": "detail shot",
                "lifestyle": "in use",
            }
            parts.append(angle_descriptions.get(angle.lower(), angle))

        if context:
            parts.append(context)

        alt_text = " - ".join(parts)

        # Truncate if too long
        if len(alt_text) > 125:
            alt_text = alt_text[:122] + "..."

        return alt_text

    @staticmethod
    def generate_category_alt(category_name: str, image_type: str = "banner") -> str:
        """Generate alt text for category images."""
        if image_type == "banner":
            return (
                f"{category_name} collection - shop the latest {category_name.lower()}"
            )
        elif image_type == "icon":
            return f"{category_name} category icon"
        else:
            return f"Browse our {category_name.lower()} selection"

    @staticmethod
    def generate_blog_alt(
        topic: str, image_number: int = 1, description: str = ""
    ) -> str:
        """Generate alt text for blog images."""
        if description:
            return f"{topic} - {description}"
        else:
            return f"{topic} illustration {image_number}"

    @staticmethod
    def optimize_existing_alt(current_alt: str, context: str = "") -> str:
        """Optimize existing alt text."""
        if not current_alt:
            return context or "Image"

        # Remove generic patterns
        generic_patterns = [
            r"^IMG_\d+",
            r"^DSC_\d+",
            r"^image\d*$",
            r"^photo\d*$",
            r"^untitled$",
        ]

        for pattern in generic_patterns:
            if re.match(pattern, current_alt, re.IGNORECASE):
                return context or "Product image"

        # Add context if alt is too short
        if len(current_alt) < 10 and context:
            return f"{current_alt} - {context}"

        return current_alt

    @staticmethod
    def batch_generate_alts(
        images: List[Dict[str, str]], product_name: str
    ) -> List[Dict[str, str]]:
        """Generate alt text for multiple images."""
        results = []

        angles = ["front", "side", "back", "detail", "lifestyle"]

        for i, image in enumerate(images):
            angle = angles[i] if i < len(angles) else ""

            alt = AltTextGenerator.generate_product_alt(
                product_name=product_name,
                angle=angle,
            )

            results.append(
                {
                    "url": image.get("url", ""),
                    "original_alt": image.get("alt", ""),
                    "suggested_alt": alt,
                }
            )

        return results


# ============================================================================
# SCHEMA MARKUP GENERATOR
# ============================================================================


class SchemaGenerator:
    """Generates Schema.org structured data."""

    @staticmethod
    def generate_product_schema(
        name: str,
        description: str,
        sku: str,
        price: float,
        currency: str = "AUD",
        brand: str = "",
        image_urls: List[str] = None,
        rating: float = 0,
        review_count: int = 0,
        availability: str = "InStock",
        url: str = "",
    ) -> SchemaMarkup:
        """Generate Product schema."""
        data = {
            "name": name,
            "description": description,
            "sku": sku,
            "image": image_urls or [],
            "offers": {
                "@type": "Offer",
                "price": price,
                "priceCurrency": currency,
                "availability": f"https://schema.org/{availability}",
                "url": url,
            },
        }

        if brand:
            data["brand"] = {
                "@type": "Brand",
                "name": brand,
            }

        if rating > 0 and review_count > 0:
            data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": rating,
                "reviewCount": review_count,
            }

        return SchemaMarkup(schema_type=SchemaType.PRODUCT, data=data)

    @staticmethod
    def generate_organization_schema(
        name: str,
        url: str,
        logo: str,
        description: str = "",
        social_profiles: List[str] = None,
        contact_phone: str = "",
        contact_email: str = "",
    ) -> SchemaMarkup:
        """Generate Organization schema."""
        data = {
            "name": name,
            "url": url,
            "logo": logo,
        }

        if description:
            data["description"] = description

        if social_profiles:
            data["sameAs"] = social_profiles

        if contact_phone or contact_email:
            data["contactPoint"] = {
                "@type": "ContactPoint",
                "contactType": "customer service",
            }
            if contact_phone:
                data["contactPoint"]["telephone"] = contact_phone
            if contact_email:
                data["contactPoint"]["email"] = contact_email

        return SchemaMarkup(schema_type=SchemaType.ORGANIZATION, data=data)

    @staticmethod
    def generate_local_business_schema(
        name: str,
        address: Dict[str, str],
        phone: str,
        url: str,
        opening_hours: List[str] = None,
        geo: Dict[str, float] = None,
    ) -> SchemaMarkup:
        """Generate LocalBusiness schema."""
        data = {
            "name": name,
            "url": url,
            "telephone": phone,
            "address": {"@type": "PostalAddress", **address},
        }

        if opening_hours:
            data["openingHours"] = opening_hours

        if geo:
            data["geo"] = {"@type": "GeoCoordinates", **geo}

        return SchemaMarkup(schema_type=SchemaType.LOCAL_BUSINESS, data=data)

    @staticmethod
    def generate_article_schema(
        headline: str,
        description: str,
        author: str,
        published_date: datetime,
        modified_date: datetime = None,
        image: str = "",
        publisher_name: str = "",
        publisher_logo: str = "",
    ) -> SchemaMarkup:
        """Generate Article schema."""
        data = {
            "headline": headline,
            "description": description,
            "author": {
                "@type": "Person",
                "name": author,
            },
            "datePublished": published_date.isoformat(),
        }

        if modified_date:
            data["dateModified"] = modified_date.isoformat()

        if image:
            data["image"] = image

        if publisher_name:
            data["publisher"] = {
                "@type": "Organization",
                "name": publisher_name,
            }
            if publisher_logo:
                data["publisher"]["logo"] = {
                    "@type": "ImageObject",
                    "url": publisher_logo,
                }

        return SchemaMarkup(schema_type=SchemaType.ARTICLE, data=data)

    @staticmethod
    def generate_faq_schema(faqs: List[Dict[str, str]]) -> SchemaMarkup:
        """Generate FAQPage schema."""
        main_entity = []

        for faq in faqs:
            main_entity.append(
                {
                    "@type": "Question",
                    "name": faq.get("question", ""),
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq.get("answer", ""),
                    },
                }
            )

        data = {"mainEntity": main_entity}
        return SchemaMarkup(schema_type=SchemaType.FAQ_PAGE, data=data)

    @staticmethod
    def generate_breadcrumb_schema(breadcrumbs: List[Dict[str, str]]) -> SchemaMarkup:
        """Generate BreadcrumbList schema."""
        items = []

        for i, crumb in enumerate(breadcrumbs):
            items.append(
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "name": crumb.get("name", ""),
                    "item": crumb.get("url", ""),
                }
            )

        data = {"itemListElement": items}
        return SchemaMarkup(schema_type=SchemaType.BREADCRUMB_LIST, data=data)

    @staticmethod
    def generate_how_to_schema(
        name: str,
        description: str,
        steps: List[Dict[str, str]],
        total_time: str = "",
        tools: List[str] = None,
        supplies: List[str] = None,
    ) -> SchemaMarkup:
        """Generate HowTo schema."""
        data = {
            "name": name,
            "description": description,
            "step": [],
        }

        for i, step in enumerate(steps):
            data["step"].append(
                {
                    "@type": "HowToStep",
                    "position": i + 1,
                    "name": step.get("name", f"Step {i + 1}"),
                    "text": step.get("text", ""),
                    "image": step.get("image", ""),
                }
            )

        if total_time:
            data["totalTime"] = total_time

        if tools:
            data["tool"] = [{"@type": "HowToTool", "name": t} for t in tools]

        if supplies:
            data["supply"] = [{"@type": "HowToSupply", "name": s} for s in supplies]

        return SchemaMarkup(schema_type=SchemaType.HOW_TO, data=data)


# ============================================================================
# INTERNAL LINKING SUGGESTER
# ============================================================================


class InternalLinkingSuggester:
    """Suggests internal linking opportunities."""

    def __init__(self):
        self.pages: Dict[str, Dict[str, Any]] = {}
        self.existing_links: List[InternalLink] = []

    def add_page(
        self, url: str, title: str, keywords: List[str], content_type: ContentType
    ):
        """Add a page to the site structure."""
        self.pages[url] = {
            "title": title,
            "keywords": [kw.lower() for kw in keywords],
            "content_type": content_type,
            "inbound_links": 0,
            "outbound_links": 0,
        }

    def add_existing_link(self, link: InternalLink):
        """Add an existing internal link."""
        self.existing_links.append(link)

        if link.source_url in self.pages:
            self.pages[link.source_url]["outbound_links"] += 1
        if link.target_url in self.pages:
            self.pages[link.target_url]["inbound_links"] += 1

    def suggest_links_for_page(
        self, page_url: str, content: str, max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """Suggest internal links for a page."""
        suggestions = []
        content_lower = content.lower()

        # Find keyword matches
        for url, page_data in self.pages.items():
            if url == page_url:
                continue

            for keyword in page_data["keywords"]:
                if keyword in content_lower:
                    # Check if link already exists
                    existing = any(
                        l.source_url == page_url and l.target_url == url
                        for l in self.existing_links
                    )

                    if not existing:
                        suggestions.append(
                            {
                                "target_url": url,
                                "target_title": page_data["title"],
                                "anchor_text": keyword,
                                "reason": f"Keyword '{keyword}' found in content",
                                "priority": self._calculate_link_priority(url),
                            }
                        )

        # Sort by priority and limit
        suggestions.sort(key=lambda x: x["priority"], reverse=True)
        return suggestions[:max_suggestions]

    def _calculate_link_priority(self, url: str) -> float:
        """Calculate priority for linking to a page."""
        page_data = self.pages.get(url, {})

        # Lower inbound links = higher priority
        inbound = page_data.get("inbound_links", 0)
        priority = 10 - min(inbound, 9)

        # Boost products and categories
        if page_data.get("content_type") == ContentType.PRODUCT:
            priority += 2
        elif page_data.get("content_type") == ContentType.CATEGORY:
            priority += 1

        return priority

    def find_orphan_pages(self) -> List[str]:
        """Find pages with no inbound links."""
        orphans = []

        for url, page_data in self.pages.items():
            if page_data["inbound_links"] == 0:
                orphans.append(url)

        return orphans

    def get_link_distribution_report(self) -> Dict[str, Any]:
        """Generate link distribution report."""
        inbound_counts = [p["inbound_links"] for p in self.pages.values()]
        outbound_counts = [p["outbound_links"] for p in self.pages.values()]

        return {
            "total_pages": len(self.pages),
            "total_internal_links": len(self.existing_links),
            "orphan_pages": len(self.find_orphan_pages()),
            "avg_inbound_links": (
                sum(inbound_counts) / len(inbound_counts) if inbound_counts else 0
            ),
            "avg_outbound_links": (
                sum(outbound_counts) / len(outbound_counts) if outbound_counts else 0
            ),
            "max_inbound_links": max(inbound_counts) if inbound_counts else 0,
            "pages_with_low_links": sum(1 for c in inbound_counts if c < 3),
        }


# ============================================================================
# SITEMAP MANAGER
# ============================================================================


class SitemapManager:
    """Manages XML sitemaps."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.entries: List[SitemapEntry] = []

    def add_entry(
        self,
        path: str,
        lastmod: datetime = None,
        changefreq: str = "weekly",
        priority: float = 0.5,
        images: List[str] = None,
    ):
        """Add entry to sitemap."""
        entry = SitemapEntry(
            loc=urljoin(self.base_url, path),
            lastmod=lastmod,
            changefreq=changefreq,
            priority=priority,
            images=images or [],
        )
        self.entries.append(entry)

    def add_product(
        self, slug: str, lastmod: datetime = None, images: List[str] = None
    ):
        """Add product to sitemap with appropriate settings."""
        self.add_entry(
            path=f"/product/{slug}/",
            lastmod=lastmod,
            changefreq="daily",
            priority=0.8,
            images=images,
        )

    def add_category(self, slug: str, lastmod: datetime = None):
        """Add category to sitemap."""
        self.add_entry(
            path=f"/product-category/{slug}/",
            lastmod=lastmod,
            changefreq="daily",
            priority=0.7,
        )

    def add_blog_post(
        self, slug: str, lastmod: datetime = None, images: List[str] = None
    ):
        """Add blog post to sitemap."""
        self.add_entry(
            path=f"/blog/{slug}/",
            lastmod=lastmod,
            changefreq="monthly",
            priority=0.6,
            images=images,
        )

    def generate_sitemap(self) -> str:
        """Generate complete sitemap XML."""
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
        ]

        for entry in self.entries:
            xml_parts.append(entry.to_xml())

        xml_parts.append("</urlset>")

        return "\n".join(xml_parts)

    def generate_sitemap_index(self, sitemaps: List[Dict[str, Any]]) -> str:
        """Generate sitemap index XML."""
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        for sitemap in sitemaps:
            xml_parts.append("  <sitemap>")
            xml_parts.append(f"    <loc>{sitemap['loc']}</loc>")
            if sitemap.get("lastmod"):
                xml_parts.append(f"    <lastmod>{sitemap['lastmod']}</lastmod>")
            xml_parts.append("  </sitemap>")

        xml_parts.append("</sitemapindex>")

        return "\n".join(xml_parts)

    def validate_sitemap(self) -> List[Dict[str, Any]]:
        """Validate sitemap entries."""
        issues = []

        # Check for duplicates
        urls = [e.loc for e in self.entries]
        duplicates = set([u for u in urls if urls.count(u) > 1])

        for dup in duplicates:
            issues.append(
                {
                    "severity": "warning",
                    "issue": f"Duplicate URL in sitemap: {dup}",
                    "recommendation": "Remove duplicate entries",
                }
            )

        # Check priorities
        high_priority = [e for e in self.entries if e.priority > 0.9]
        if len(high_priority) > len(self.entries) * 0.1:
            issues.append(
                {
                    "severity": "info",
                    "issue": "Too many high-priority pages",
                    "recommendation": "Reserve priority > 0.9 for most important pages only",
                }
            )

        # Check for missing lastmod
        missing_lastmod = [e for e in self.entries if not e.lastmod]
        if missing_lastmod:
            issues.append(
                {
                    "severity": "info",
                    "issue": f"{len(missing_lastmod)} URLs missing lastmod",
                    "recommendation": "Add lastmod dates for better crawl efficiency",
                }
            )

        return issues


# ============================================================================
# SEARCH CONSOLE ANALYZER
# ============================================================================


class SearchConsoleAnalyzer:
    """Analyzes Search Console data patterns."""

    @staticmethod
    def analyze_performance(data: List[SearchConsoleData]) -> Dict[str, Any]:
        """Analyze overall performance."""
        if not data:
            return {"error": "No data available"}

        total_clicks = sum(d.clicks for d in data)
        total_impressions = sum(d.impressions for d in data)
        avg_ctr = (
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        )
        avg_position = sum(d.position for d in data) / len(data) if data else 0

        return {
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "average_ctr": round(avg_ctr, 2),
            "average_position": round(avg_position, 1),
            "pages_analyzed": len(data),
        }

    @staticmethod
    def find_quick_wins(data: List[SearchConsoleData]) -> List[Dict[str, Any]]:
        """Find quick win optimization opportunities."""
        quick_wins = []

        for page in data:
            # Pages on page 1 with low CTR
            if page.position <= 10 and page.ctr < 0.05 and page.impressions > 100:
                quick_wins.append(
                    {
                        "url": page.url,
                        "type": "low_ctr_page_one",
                        "current_ctr": f"{page.ctr*100:.1f}%",
                        "position": page.position,
                        "impressions": page.impressions,
                        "recommendation": "Improve meta title/description - you're visible but not getting clicks",
                        "potential_impact": "high",
                    }
                )

            # Pages close to page 1 (positions 11-20)
            if 10 < page.position <= 20 and page.impressions > 50:
                quick_wins.append(
                    {
                        "url": page.url,
                        "type": "almost_page_one",
                        "position": page.position,
                        "impressions": page.impressions,
                        "recommendation": "Small content improvements could push to page 1",
                        "potential_impact": "high",
                    }
                )

            # High impressions, low position
            if page.impressions > 500 and page.position > 20:
                quick_wins.append(
                    {
                        "url": page.url,
                        "type": "high_impressions_low_rank",
                        "position": page.position,
                        "impressions": page.impressions,
                        "recommendation": "Google shows this page often - focus on improving ranking",
                        "potential_impact": "medium",
                    }
                )

        # Sort by potential impact
        quick_wins.sort(
            key=lambda x: {"high": 3, "medium": 2, "low": 1}[x["potential_impact"]],
            reverse=True,
        )

        return quick_wins

    @staticmethod
    def identify_cannibalizing_pages(
        data: List[SearchConsoleData],
    ) -> List[Dict[str, Any]]:
        """Identify potential keyword cannibalization."""
        # Group by queries
        query_pages: Dict[str, List[str]] = {}

        for page in data:
            for query_data in page.queries:
                query = query_data.get("query", "").lower()
                if query not in query_pages:
                    query_pages[query] = []
                query_pages[query].append(page.url)

        # Find queries with multiple ranking pages
        cannibalization = []

        for query, pages in query_pages.items():
            unique_pages = list(set(pages))
            if len(unique_pages) > 1:
                cannibalization.append(
                    {
                        "query": query,
                        "pages": unique_pages,
                        "recommendation": "Consider consolidating content or differentiating focus",
                    }
                )

        return cannibalization

    @staticmethod
    def suggest_content_updates(data: List[SearchConsoleData]) -> List[Dict[str, Any]]:
        """Suggest content updates based on Search Console data."""
        suggestions = []

        for page in data:
            # Declining performance
            if page.clicks > 0:
                # This would need historical comparison in real implementation
                pass

            # Pages with queries but poor ranking
            relevant_queries = [
                q
                for q in page.queries
                if q.get("position", 100) > 20 and q.get("impressions", 0) > 100
            ]

            if relevant_queries:
                suggestions.append(
                    {
                        "url": page.url,
                        "action": "content_expansion",
                        "queries": [q["query"] for q in relevant_queries[:5]],
                        "recommendation": "Expand content to better target these related queries",
                    }
                )

        return suggestions


# ============================================================================
# MAIN SEO ASSISTANT AGENT
# ============================================================================


class WordPressSEOAssistant:
    """Main WordPress SEO assistant agent."""

    def __init__(self, site_url: str = "", demo_mode: bool = True):
        self.site_url = site_url
        self.demo_mode = demo_mode

        self.keyword_researcher = KeywordResearcher()
        self.on_page_analyzer = OnPageSEOAnalyzer()
        self.alt_text_generator = AltTextGenerator()
        self.schema_generator = SchemaGenerator()
        self.internal_linker = InternalLinkingSuggester()
        self.sitemap_manager = SitemapManager(site_url or "https://example.com")
        self.search_console = SearchConsoleAnalyzer()

    def analyze_page(
        self,
        url: str,
        title: str = "",
        meta_description: str = "",
        content: str = "",
        headings: Dict[str, List[str]] = None,
        target_keyword: str = "",
        images: List[Dict[str, str]] = None,
    ) -> ContentAnalysis:
        """Perform complete on-page SEO analysis."""
        issues = []

        # Title analysis
        title_issues = self.on_page_analyzer.analyze_title(title, target_keyword)
        issues.extend(title_issues)

        # Meta description analysis
        desc_issues = self.on_page_analyzer.analyze_meta_description(
            meta_description, target_keyword
        )
        issues.extend(desc_issues)

        # URL analysis
        url_issues = self.on_page_analyzer.analyze_url(url, target_keyword)
        issues.extend(url_issues)

        # Headings analysis
        if headings:
            heading_issues = self.on_page_analyzer.analyze_headings(
                headings, target_keyword
            )
            issues.extend(heading_issues)

        # Content analysis
        content_result = self.on_page_analyzer.analyze_content(content, target_keyword)
        issues.extend(content_result.get("issues", []))

        # Image analysis
        image_seo_list = []
        if images:
            for img in images:
                image_seo = ImageSEO(
                    url=img.get("url", ""),
                    alt_text=img.get("alt", ""),
                    filename=img.get("filename", ""),
                )
                image_issues = image_seo.validate()
                for issue in image_issues:
                    issue["image_url"] = img.get("url", "")
                    issues.append(issue)
                image_seo_list.append(image_seo)

        # Create meta tags object
        meta_tags = MetaTags(
            title=title,
            description=meta_description,
            canonical=url,
        )
        meta_issues = meta_tags.validate()
        # Don't add duplicate issues already caught

        # Create analysis result
        analysis = ContentAnalysis(
            url=url,
            title=title,
            word_count=content_result.get("word_count", 0),
            heading_structure={k: len(v) for k, v in (headings or {}).items()},
            keyword_density={target_keyword: content_result.get("keyword_density", 0)},
            images=image_seo_list,
            meta_tags=meta_tags,
            issues=issues,
        )

        analysis.calculate_score()
        return analysis

    def generate_product_schema(self, product: Dict[str, Any]) -> str:
        """Generate schema markup for a product."""
        schema = self.schema_generator.generate_product_schema(
            name=product.get("name", ""),
            description=product.get("description", ""),
            sku=product.get("sku", ""),
            price=product.get("price", 0),
            currency=product.get("currency", "AUD"),
            brand=product.get("brand", ""),
            image_urls=product.get("images", []),
            rating=product.get("rating", 0),
            review_count=product.get("review_count", 0),
            url=product.get("url", ""),
        )
        return schema.to_json_ld()

    def suggest_alt_texts(
        self, product_name: str, images: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Suggest alt texts for product images."""
        return self.alt_text_generator.batch_generate_alts(images, product_name)

    def get_keyword_suggestions(self, category: str) -> List[Keyword]:
        """Get keyword suggestions for a category."""
        return self.keyword_researcher.get_keywords_for_category(category)

    def generate_sitemap(self) -> str:
        """Generate XML sitemap."""
        return self.sitemap_manager.generate_sitemap()

    def demo_run(self):
        """Run demonstration of SEO features."""
        print("\n" + "=" * 70)
        print("  WordPress SEO Assistant - Demo Mode")
        print("  Electronics Store SEO Optimization")
        print("=" * 70)

        # Demo 1: On-Page Analysis
        print("\n📊 On-Page SEO Analysis:")
        print("-" * 50)

        analysis = self.analyze_page(
            url="https://example.com/product/wireless-earbuds-pro",
            title="Wireless Earbuds Pro - Best Audio Quality",
            meta_description="Shop our premium wireless earbuds with active noise cancellation.",
            content="""
                <h1>Wireless Earbuds Pro</h1>
                <p>Experience premium audio quality with our wireless earbuds. 
                Features include active noise cancellation, 30-hour battery life,
                and comfortable fit for all-day wear.</p>
                <h2>Key Features</h2>
                <p>Our wireless earbuds deliver exceptional sound quality.</p>
            """,
            headings={
                "h1": ["Wireless Earbuds Pro"],
                "h2": ["Key Features"],
            },
            target_keyword="wireless earbuds",
            images=[
                {"url": "/images/earbuds-1.jpg", "alt": ""},
                {"url": "/images/earbuds-2.jpg", "alt": "product image"},
            ],
        )

        print(f"   URL: {analysis.url}")
        print(
            f"   Score: {analysis.score:.0f}/100 ({analysis.get_score_level().value})"
        )
        print(f"   Word Count: {analysis.word_count}")
        print(f"   Issues Found: {len(analysis.issues)}")

        for issue in analysis.issues[:3]:
            severity = issue.get("severity", "info").upper()
            print(f"   [{severity}] {issue.get('issue', '')}")

        # Demo 2: Keyword Research
        print("\n🔑 Keyword Research:")
        print("-" * 50)

        keywords = self.get_keyword_suggestions("audio")
        for kw in keywords[:5]:
            print(f"   • {kw.keyword}")
            print(
                f"     Volume: {kw.search_volume:,} | Difficulty: {kw.difficulty.value}"
            )
            print(
                f"     Intent: {kw.intent.value} | Priority: {kw.get_priority_score():.0f}"
            )

        # Demo 3: Long-tail Keywords
        print("\n🔍 Long-Tail Keyword Suggestions:")
        print("-" * 50)

        long_tails = self.keyword_researcher.generate_long_tail_keywords(
            "wireless earbuds", count=6
        )
        for lt in long_tails:
            print(f"   • {lt}")

        # Demo 4: Alt Text Suggestions
        print("\n🖼️  Image Alt Text Suggestions:")
        print("-" * 50)

        alt_suggestions = self.suggest_alt_texts(
            "Wireless Earbuds Pro",
            [
                {"url": "/img1.jpg", "alt": ""},
                {"url": "/img2.jpg", "alt": "image"},
                {"url": "/img3.jpg", "alt": ""},
            ],
        )
        for suggestion in alt_suggestions:
            print(f"   Original: '{suggestion['original_alt'] or '(empty)'}'")
            print(f"   Suggested: '{suggestion['suggested_alt']}'")
            print()

        # Demo 5: Schema Markup
        print("📋 Schema Markup (Product):")
        print("-" * 50)

        schema_json = self.generate_product_schema(
            {
                "name": "Wireless Earbuds Pro",
                "description": "Premium wireless earbuds with ANC",
                "sku": "WEP-001",
                "price": 149.99,
                "brand": "TechAudio",
                "rating": 4.5,
                "review_count": 127,
                "url": "https://example.com/product/wireless-earbuds-pro",
            }
        )

        # Show first few lines
        lines = schema_json.split("\n")
        for line in lines[:8]:
            print(f"   {line}")
        print("   ...")

        # Demo 6: Meta Tag Optimization
        print("\n📝 Meta Tag Recommendations:")
        print("-" * 50)

        meta = MetaTags(
            title="Best Wireless Earbuds 2024 | Premium Audio | Your Store",
            description="Discover the best wireless earbuds for 2024. Premium sound quality, noise cancellation, and all-day comfort. Free shipping on orders over $50.",
        )

        print(f"   Title: {meta.title}")
        print(f"   Length: {len(meta.title)} chars (target: 50-60)")
        print(f"   Description: {meta.description[:50]}...")
        print(f"   Length: {len(meta.description)} chars (target: 120-155)")

        # Demo 7: Internal Linking
        print("\n🔗 Internal Linking Analysis:")
        print("-" * 50)

        # Add demo pages
        self.internal_linker.add_page(
            "/product/wireless-earbuds/",
            "Wireless Earbuds",
            ["wireless earbuds", "bluetooth earbuds"],
            ContentType.PRODUCT,
        )
        self.internal_linker.add_page(
            "/category/audio/",
            "Audio Products",
            ["audio", "headphones", "speakers"],
            ContentType.CATEGORY,
        )
        self.internal_linker.add_page(
            "/blog/best-earbuds-guide/",
            "Best Earbuds Buying Guide",
            ["earbuds guide", "how to choose earbuds"],
            ContentType.BLOG_POST,
        )

        suggestions = self.internal_linker.suggest_links_for_page(
            "/blog/wireless-audio-trends/",
            "The latest trends in wireless audio technology including earbuds and headphones...",
        )

        for sug in suggestions[:3]:
            print(f"   Link to: {sug['target_title']}")
            print(f"   Anchor: '{sug['anchor_text']}'")
            print(f"   Reason: {sug['reason']}")
            print()

        # Demo 8: Sitemap Generation
        print("🗺️  Sitemap Entries (Sample):")
        print("-" * 50)

        self.sitemap_manager.add_product("wireless-earbuds-pro", datetime.now())
        self.sitemap_manager.add_category("audio", datetime.now())
        self.sitemap_manager.add_blog_post("best-earbuds-2024", datetime.now())

        sitemap = self.generate_sitemap()
        sitemap_lines = sitemap.split("\n")
        for line in sitemap_lines[:10]:
            print(f"   {line}")
        print("   ...")

        # Demo 9: Search Console Insights
        print("\n📈 Search Console Analysis (Demo Data):")
        print("-" * 50)

        demo_sc_data = [
            SearchConsoleData(
                url="/product/wireless-earbuds/",
                clicks=150,
                impressions=5000,
                ctr=0.03,
                position=8.5,
            ),
            SearchConsoleData(
                url="/blog/earbuds-guide/",
                clicks=45,
                impressions=2000,
                ctr=0.0225,
                position=12.3,
            ),
        ]

        performance = self.search_console.analyze_performance(demo_sc_data)
        print(f"   Total Clicks: {performance['total_clicks']}")
        print(f"   Total Impressions: {performance['total_impressions']}")
        print(f"   Average CTR: {performance['average_ctr']}%")
        print(f"   Average Position: {performance['average_position']}")

        quick_wins = self.search_console.find_quick_wins(demo_sc_data)
        if quick_wins:
            print("\n   Quick Wins:")
            for win in quick_wins[:2]:
                print(f"   • {win['url']}")
                print(f"     {win['recommendation']}")

        # Demo 10: SEO Checklist
        print("\n✅ SEO Checklist for Electronics Store:")
        print("-" * 50)
        checklist = [
            "☑ Unique meta titles for each product (include brand + model)",
            "☑ Compelling meta descriptions with call-to-action",
            "☑ Product schema markup on all product pages",
            "☑ Optimized images with descriptive alt text",
            "☑ Internal links between related products",
            "☑ Category pages with helpful content",
            "☑ Blog content targeting buying guides",
            "☑ FAQ schema on relevant pages",
            "☑ Mobile-friendly design verified",
            "☑ XML sitemap submitted to Search Console",
        ]
        for item in checklist:
            print(f"   {item}")

        print("\n" + "=" * 70)
        print("  Demo Complete! Ready to optimize your electronics store.")
        print("=" * 70 + "\n")


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WordPress SEO Assistant for Electronics Store"
    )
    parser.add_argument("--demo", action="store_true", help="Run in demo mode")
    parser.add_argument("--analyze", type=str, help="URL to analyze")
    parser.add_argument("--keyword", type=str, help="Target keyword for analysis")
    parser.add_argument("--category", type=str, help="Get keywords for category")
    parser.add_argument(
        "--schema",
        type=str,
        choices=["product", "organization", "faq", "article"],
        help="Generate schema markup",
    )
    parser.add_argument("--sitemap", action="store_true", help="Generate sitemap")

    args = parser.parse_args()

    assistant = WordPressSEOAssistant(demo_mode=args.demo)

    if args.demo:
        assistant.demo_run()
    elif args.category:
        keywords = assistant.get_keyword_suggestions(args.category)
        print(f"\nKeywords for '{args.category}':")
        for kw in keywords:
            print(f"  • {kw.keyword} (vol: {kw.search_volume:,})")
    elif args.sitemap:
        print(assistant.generate_sitemap())
    else:
        assistant.demo_run()


if __name__ == "__main__":
    main()
