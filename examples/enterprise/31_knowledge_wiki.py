#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 31: Corporate Knowledge Base / Wiki

An enterprise knowledge management system:
- Full-text search across documents
- Category browsing
- Related article suggestions
- Version history
- Contribution tracking

Key patterns demonstrated:
- Full-text search with relevance scoring
- Category hierarchy navigation
- Version control for content
- Collaborative editing workflows
- Related content recommendations

Usage:
    python examples/31_knowledge_wiki.py

Requirements:
    pip install agentic-brain
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import json
import random
import string
import re

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class ArticleStatus(Enum):
    """Article publication status."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentType(Enum):
    """Type of wiki content."""

    ARTICLE = "article"
    PROCEDURE = "procedure"
    FAQ = "faq"
    GLOSSARY = "glossary"
    TEMPLATE = "template"
    ANNOUNCEMENT = "announcement"


class UserRole(Enum):
    """Wiki user roles."""

    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    EDITOR = "editor"
    ADMIN = "admin"


@dataclass
class User:
    """Wiki user."""

    id: str
    email: str
    name: str
    department: str
    role: UserRole
    contributions: int = 0
    expertise_areas: list = field(default_factory=list)


@dataclass
class Category:
    """Article category."""

    id: str
    name: str
    description: str
    parent_id: str = ""
    icon: str = "📁"
    article_count: int = 0


@dataclass
class ArticleVersion:
    """Version of an article."""

    version: str
    content: str
    summary: str
    author_id: str
    created_at: datetime
    change_description: str = ""


@dataclass
class Article:
    """Wiki article."""

    id: str
    title: str
    slug: str
    content: str
    summary: str
    content_type: ContentType
    categories: list[str]
    tags: list[str]
    status: ArticleStatus
    author_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    views: int = 0
    helpful_votes: int = 0
    not_helpful_votes: int = 0
    version: str = "1.0"
    versions: list[ArticleVersion] = field(default_factory=list)
    related_articles: list[str] = field(default_factory=list)
    attachments: list = field(default_factory=list)


@dataclass
class SearchResult:
    """Search result with relevance scoring."""

    article: Article
    score: float
    highlights: list[str]


@dataclass
class Comment:
    """Article comment."""

    id: str
    article_id: str
    author_id: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    parent_id: str = ""  # For threaded comments


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class KnowledgeBaseService:
    """Enterprise knowledge base/wiki service."""

    def __init__(self):
        """Initialize with demo data."""
        self.users: dict[str, User] = {}
        self.categories: dict[str, Category] = {}
        self.articles: dict[str, Article] = {}
        self.comments: dict[str, Comment] = {}
        self.current_user: Optional[User] = None
        self._load_demo_data()

    def _generate_id(self, prefix: str = "ART") -> str:
        """Generate unique ID."""
        suffix = "".join(random.choices(string.digits + string.ascii_lowercase, k=8))
        return f"{prefix}-{suffix}"

    def _slugify(self, text: str) -> str:
        """Create URL-friendly slug from text."""
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        return slug[:50]

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo users
        users = [
            User(
                "U001",
                "john.writer@company.com",
                "John Writer",
                "Engineering",
                UserRole.CONTRIBUTOR,
                15,
                ["engineering", "devops"],
            ),
            User(
                "U002",
                "sarah.editor@company.com",
                "Sarah Editor",
                "Documentation",
                UserRole.EDITOR,
                42,
                ["all"],
            ),
            User(
                "U003",
                "mike.reader@company.com",
                "Mike Reader",
                "Sales",
                UserRole.VIEWER,
                0,
                [],
            ),
            User(
                "U004",
                "admin@company.com",
                "Wiki Admin",
                "IT",
                UserRole.ADMIN,
                100,
                ["all"],
            ),
        ]
        for user in users:
            self.users[user.id] = user

        # Categories (hierarchical)
        categories = [
            Category(
                "CAT-001",
                "Engineering",
                "Technical documentation and guides",
                "",
                "⚙️",
                5,
            ),
            Category(
                "CAT-002",
                "Development",
                "Software development practices",
                "CAT-001",
                "💻",
                3,
            ),
            Category(
                "CAT-003", "DevOps", "Infrastructure and deployment", "CAT-001", "🔧", 2
            ),
            Category(
                "CAT-004", "HR & People", "Human resources information", "", "👥", 3
            ),
            Category(
                "CAT-005", "Onboarding", "New employee resources", "CAT-004", "🎯", 2
            ),
            Category(
                "CAT-006",
                "Benefits",
                "Employee benefits information",
                "CAT-004",
                "🎁",
                1,
            ),
            Category(
                "CAT-007",
                "IT & Security",
                "IT policies and security guidelines",
                "",
                "🔒",
                4,
            ),
            Category("CAT-008", "Company", "General company information", "", "🏢", 2),
            Category(
                "CAT-009",
                "Policies",
                "Company policies and procedures",
                "CAT-008",
                "📋",
                2,
            ),
        ]
        for cat in categories:
            self.categories[cat.id] = cat

        # Demo articles
        articles = [
            Article(
                id="ART-001",
                title="Git Branching Strategy",
                slug="git-branching-strategy",
                content="""# Git Branching Strategy

## Overview
This document describes our standard Git branching strategy based on GitFlow.

## Branch Types

### Main Branches
- **main**: Production-ready code only
- **develop**: Integration branch for features

### Supporting Branches
- **feature/**: New features (branch from develop)
- **release/**: Release preparation (branch from develop)
- **hotfix/**: Production fixes (branch from main)

## Workflow

1. Create feature branch from develop
2. Develop and commit changes
3. Create pull request to develop
4. Code review and approval
5. Merge to develop
6. Release branch created for testing
7. Merge to main for deployment

## Naming Conventions

```
feature/JIRA-123-short-description
bugfix/JIRA-456-fix-login-issue
hotfix/JIRA-789-critical-security-fix
release/1.2.0
```

## Pull Request Requirements
- Minimum 1 approval required
- All CI checks must pass
- No merge conflicts
- Updated documentation if applicable""",
                summary="Standard Git branching strategy using GitFlow methodology",
                content_type=ContentType.PROCEDURE,
                categories=["CAT-002"],
                tags=["git", "branching", "workflow", "gitflow"],
                status=ArticleStatus.PUBLISHED,
                author_id="U001",
                views=523,
                helpful_votes=45,
                published_at=datetime.now() - timedelta(days=60),
            ),
            Article(
                id="ART-002",
                title="Code Review Guidelines",
                slug="code-review-guidelines",
                content="""# Code Review Guidelines

## Purpose
Code reviews ensure code quality, knowledge sharing, and mentorship.

## What to Look For

### Code Quality
- Follows coding standards and style guides
- No obvious bugs or logic errors
- Appropriate error handling
- No security vulnerabilities

### Design
- Follows SOLID principles
- Appropriate abstraction level
- No unnecessary complexity
- Good separation of concerns

### Testing
- Adequate test coverage
- Tests are meaningful and maintainable
- Edge cases considered

### Documentation
- Code is self-documenting where possible
- Complex logic is commented
- Public APIs are documented

## Review Process

1. **Author** creates PR with clear description
2. **Reviewer** reviews within 24 hours
3. **Author** addresses feedback
4. **Reviewer** approves or requests changes
5. **Author** merges after approval

## Giving Feedback

### Do:
- Be constructive and specific
- Explain the "why" behind suggestions
- Acknowledge good code
- Ask questions rather than make demands

### Don't:
- Be harsh or personal
- Nitpick on style (use linters)
- Block for minor issues
- Review when tired or frustrated""",
                summary="Best practices for conducting effective code reviews",
                content_type=ContentType.ARTICLE,
                categories=["CAT-002"],
                tags=["code review", "best practices", "quality"],
                status=ArticleStatus.PUBLISHED,
                author_id="U001",
                views=892,
                helpful_votes=78,
                published_at=datetime.now() - timedelta(days=45),
                related_articles=["ART-001"],
            ),
            Article(
                id="ART-003",
                title="New Employee Onboarding Checklist",
                slug="new-employee-onboarding",
                content="""# New Employee Onboarding Checklist

Welcome to the team! This checklist will help you get started.

## Day 1

### Before You Arrive
- [ ] Complete pre-hire paperwork
- [ ] Review employee handbook
- [ ] Set up direct deposit

### First Day
- [ ] Get building access badge
- [ ] Set up laptop and accounts
- [ ] Meet with your manager
- [ ] Tour the office
- [ ] Complete I-9 verification

## First Week

### IT Setup
- [ ] Email configuration
- [ ] Slack/Teams access
- [ ] VPN setup for remote work
- [ ] Development environment (if applicable)

### Learning
- [ ] Complete security awareness training
- [ ] Review department documentation
- [ ] Meet team members

## First Month

### Training
- [ ] Complete mandatory compliance training
- [ ] Review role-specific procedures
- [ ] Shadow experienced colleagues

### Goals
- [ ] Set 30-day goals with manager
- [ ] Schedule regular 1:1s
- [ ] Begin contributing to projects

## Resources

- IT Help Desk: help@company.com
- HR Questions: hr@company.com
- Your Manager: [See org chart]
- Buddy Program: Ask HR for assignment""",
                summary="Complete checklist for new employee onboarding",
                content_type=ContentType.PROCEDURE,
                categories=["CAT-005"],
                tags=["onboarding", "new hire", "checklist"],
                status=ArticleStatus.PUBLISHED,
                author_id="U002",
                views=1245,
                helpful_votes=156,
                published_at=datetime.now() - timedelta(days=120),
            ),
            Article(
                id="ART-004",
                title="VPN Setup Guide",
                slug="vpn-setup-guide",
                content="""# VPN Setup Guide

## Overview
This guide explains how to set up and use the company VPN for secure remote access.

## Prerequisites
- Company laptop or approved device
- VPN client installed (IT can assist)
- Network credentials

## Windows Setup

1. Open the VPN client application
2. Click "Add Connection"
3. Enter server: vpn.company.com
4. Enter your network credentials
5. Enable "Remember credentials" if on trusted device
6. Click "Connect"

## Mac Setup

1. Open System Preferences > Network
2. Click "+" to add VPN
3. Select "VPN" as interface type
4. Choose "IKEv2" as VPN type
5. Enter server address: vpn.company.com
6. Enter account name (your email)
7. Click "Authentication Settings"
8. Enter your password
9. Click "Connect"

## Troubleshooting

### "Authentication Failed"
- Verify username (full email address)
- Check password hasn't expired
- Ensure MFA token is current

### "Connection Timeout"
- Check internet connectivity
- Try different network
- Contact IT if issue persists

### Split Tunneling
VPN uses split tunneling - only company traffic goes through VPN.

## Security Notes
- Never share VPN credentials
- Disconnect when not in use
- Use on trusted networks only
- Report any suspicious activity""",
                summary="Step-by-step guide for setting up company VPN",
                content_type=ContentType.PROCEDURE,
                categories=["CAT-007"],
                tags=["vpn", "remote work", "security", "setup"],
                status=ArticleStatus.PUBLISHED,
                author_id="U004",
                views=2341,
                helpful_votes=198,
                published_at=datetime.now() - timedelta(days=90),
            ),
            Article(
                id="ART-005",
                title="Expense Reimbursement FAQ",
                slug="expense-reimbursement-faq",
                content="""# Expense Reimbursement FAQ

## General Questions

### Q: What expenses can I claim?
Business-related expenses including:
- Travel (flights, hotels, ground transportation)
- Meals during business travel
- Client entertainment (with approval)
- Professional development
- Office supplies for remote work

### Q: What's the submission deadline?
Submit expenses within 30 days of incurring them.

### Q: When will I be reimbursed?
Typically within 2 weeks of approval.

## Receipts

### Q: Do I need receipts for everything?
Receipts required for expenses over $25. Keep all receipts for audit purposes.

### Q: What if I lost a receipt?
Complete a Missing Receipt Form with expense details and manager signature.

## Travel

### Q: What's the meal per diem?
- Domestic: $75/day
- International: Varies by country (see policy)

### Q: Can I book my own flights?
Use the corporate booking tool for flights. Personal bookings need pre-approval.

### Q: Is Uber/Lyft allowed?
Yes, for business travel. Tips up to 20% are reimbursable.

## Approval Limits

| Amount | Approver |
|--------|----------|
| Up to $500 | Direct Manager |
| $500 - $2,000 | Department Head |
| Over $2,000 | VP Approval |

## Contact
- Expense Team: expenses@company.com
- Finance Questions: finance@company.com""",
                summary="Frequently asked questions about expense reimbursement",
                content_type=ContentType.FAQ,
                categories=["CAT-009"],
                tags=["expenses", "reimbursement", "faq", "finance"],
                status=ArticleStatus.PUBLISHED,
                author_id="U002",
                views=567,
                helpful_votes=34,
                published_at=datetime.now() - timedelta(days=30),
            ),
            Article(
                id="ART-006",
                title="CI/CD Pipeline Overview",
                slug="cicd-pipeline-overview",
                content="""# CI/CD Pipeline Overview

## Architecture

Our CI/CD pipeline uses GitHub Actions for continuous integration and ArgoCD for deployment.

## Pipeline Stages

### 1. Build
- Compile source code
- Run unit tests
- Generate code coverage report

### 2. Test
- Integration tests
- E2E tests (staging only)
- Security scanning

### 3. Package
- Build Docker image
- Push to container registry
- Generate SBOM

### 4. Deploy
- Development: Automatic on merge to develop
- Staging: Automatic on merge to release/*
- Production: Manual approval required

## Configuration

Pipeline configuration in `.github/workflows/`:
- `ci.yml`: Build and test
- `cd-dev.yml`: Deploy to dev
- `cd-staging.yml`: Deploy to staging
- `cd-prod.yml`: Deploy to production

## Monitoring

- Build status: GitHub Actions dashboard
- Deployment status: ArgoCD UI
- Application health: Grafana

## Rollback

Rollback procedure:
1. Go to ArgoCD
2. Select application
3. Click "History"
4. Select previous revision
5. Click "Rollback"

## Contact
DevOps Team: devops@company.com""",
                summary="Overview of the CI/CD pipeline architecture and processes",
                content_type=ContentType.ARTICLE,
                categories=["CAT-003"],
                tags=["cicd", "devops", "deployment", "github actions"],
                status=ArticleStatus.PUBLISHED,
                author_id="U001",
                views=445,
                helpful_votes=52,
                published_at=datetime.now() - timedelta(days=15),
                related_articles=["ART-001", "ART-002"],
            ),
            Article(
                id="ART-007",
                title="Password Policy",
                slug="password-policy",
                content="""# Password Policy

## Requirements

All passwords must meet these requirements:
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

## Expiration

- Regular users: 90 days
- Privileged accounts: 60 days
- Service accounts: 365 days (or certificate)

## Password Managers

Use a company-approved password manager:
- 1Password (recommended)
- LastPass
- Bitwarden

Never store passwords in plain text files or shared documents.

## Multi-Factor Authentication (MFA)

MFA is required for:
- All remote access
- Admin systems
- Financial systems
- Cloud consoles

## What to Do If Compromised

1. Change password immediately
2. Report to security@company.com
3. Check for unauthorized access
4. Enable additional MFA if available""",
                summary="Company password policy and security requirements",
                content_type=ContentType.ARTICLE,
                categories=["CAT-007"],
                tags=["security", "password", "policy", "mfa"],
                status=ArticleStatus.PUBLISHED,
                author_id="U004",
                views=1890,
                helpful_votes=87,
                published_at=datetime.now() - timedelta(days=180),
            ),
            Article(
                id="ART-008",
                title="Company Holiday Calendar 2024",
                slug="holiday-calendar-2024",
                content="""# Company Holiday Calendar 2024

## Observed Holidays

| Date | Day | Holiday |
|------|-----|---------|
| January 1 | Monday | New Year's Day |
| January 15 | Monday | Martin Luther King Jr. Day |
| February 19 | Monday | Presidents Day |
| May 27 | Monday | Memorial Day |
| July 4 | Thursday | Independence Day |
| September 2 | Monday | Labor Day |
| November 28 | Thursday | Thanksgiving |
| November 29 | Friday | Day After Thanksgiving |
| December 24 | Tuesday | Christmas Eve |
| December 25 | Wednesday | Christmas Day |

## Floating Holidays
Each employee receives 2 floating holidays per year.

## Office Closures
The office is closed on all observed holidays.

## Working on Holidays
If you must work on a holiday:
- Get manager approval
- Record as holiday worked
- Take comp time within 60 days

## International Offices
See regional calendars for local holidays.""",
                summary="2024 company holiday calendar and policies",
                content_type=ContentType.ANNOUNCEMENT,
                categories=["CAT-008"],
                tags=["holidays", "calendar", "2024"],
                status=ArticleStatus.PUBLISHED,
                author_id="U002",
                views=3245,
                helpful_votes=12,
                published_at=datetime.now() - timedelta(days=200),
            ),
        ]
        for article in articles:
            self.articles[article.id] = article

        # Set default user
        self.current_user = self.users["U003"]

    # ──────────────────────────────────────────────────────────────────────────
    # SEARCH
    # ──────────────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        category: str = None,
        content_type: str = None,
        limit: int = 10,
    ) -> dict:
        """Full-text search across articles."""
        if not query:
            return {"success": False, "error": "Search query required"}

        query_lower = query.lower()
        query_words = query_lower.split()
        results = []

        for article in self.articles.values():
            if article.status != ArticleStatus.PUBLISHED:
                continue

            # Category filter
            if category:
                if category not in article.categories:
                    continue

            # Content type filter
            if content_type:
                try:
                    ct = ContentType[content_type.upper()]
                    if article.content_type != ct:
                        continue
                except KeyError:
                    pass

            # Calculate relevance score
            score = 0.0
            highlights = []

            # Title match (highest weight)
            title_lower = article.title.lower()
            for word in query_words:
                if word in title_lower:
                    score += 20
                    highlights.append(f"Title: ...{article.title}...")

            # Tag match (high weight)
            for tag in article.tags:
                if any(word in tag.lower() for word in query_words):
                    score += 15
                    highlights.append(f"Tag: {tag}")

            # Summary match
            summary_lower = article.summary.lower()
            for word in query_words:
                if word in summary_lower:
                    score += 10

            # Content match
            content_lower = article.content.lower()
            for word in query_words:
                count = content_lower.count(word)
                if count > 0:
                    score += min(count * 2, 20)  # Cap at 20
                    # Extract highlight
                    idx = content_lower.find(word)
                    start = max(0, idx - 30)
                    end = min(len(article.content), idx + len(word) + 30)
                    snippet = article.content[start:end]
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(article.content):
                        snippet = snippet + "..."
                    if len(highlights) < 3:
                        highlights.append(snippet)

            # Boost by popularity
            score += min(article.views / 100, 5)  # Max 5 points from views
            score += article.helpful_votes * 0.1

            if score > 0:
                results.append(SearchResult(article, score, highlights[:3]))

        # Sort by relevance
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:limit]

        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": [
                {
                    "id": r.article.id,
                    "title": r.article.title,
                    "summary": r.article.summary,
                    "type": r.article.content_type.value,
                    "score": round(r.score, 1),
                    "highlights": r.highlights,
                    "views": r.article.views,
                    "helpful_votes": r.article.helpful_votes,
                }
                for r in results
            ],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # CATEGORIES
    # ──────────────────────────────────────────────────────────────────────────

    def list_categories(self, parent_id: str = None) -> dict:
        """List categories, optionally filtered by parent."""
        categories = list(self.categories.values())

        if parent_id:
            categories = [c for c in categories if c.parent_id == parent_id]
        else:
            # Root categories only
            categories = [c for c in categories if not c.parent_id]

        # Include subcategories count
        result_cats = []
        for cat in categories:
            subcats = len(
                [c for c in self.categories.values() if c.parent_id == cat.id]
            )
            result_cats.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description,
                    "icon": cat.icon,
                    "article_count": cat.article_count,
                    "subcategory_count": subcats,
                }
            )

        return {"success": True, "count": len(result_cats), "categories": result_cats}

    def get_category(self, category_id: str) -> dict:
        """Get category details with articles."""
        cat = self.categories.get(category_id)
        if not cat:
            return {"success": False, "error": f"Category {category_id} not found"}

        # Get articles in this category
        articles = [
            a
            for a in self.articles.values()
            if category_id in a.categories and a.status == ArticleStatus.PUBLISHED
        ]

        # Get subcategories
        subcats = [c for c in self.categories.values() if c.parent_id == category_id]

        # Get parent category
        parent = self.categories.get(cat.parent_id) if cat.parent_id else None

        return {
            "success": True,
            "category": {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "icon": cat.icon,
                "parent": {"id": parent.id, "name": parent.name} if parent else None,
                "subcategories": [
                    {"id": sc.id, "name": sc.name, "icon": sc.icon} for sc in subcats
                ],
                "articles": [
                    {
                        "id": a.id,
                        "title": a.title,
                        "summary": a.summary,
                        "views": a.views,
                    }
                    for a in sorted(articles, key=lambda x: x.views, reverse=True)[:10]
                ],
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # ARTICLES
    # ──────────────────────────────────────────────────────────────────────────

    def get_article(self, article_id: str) -> dict:
        """Get full article content."""
        article = self.articles.get(article_id)
        if not article:
            return {"success": False, "error": f"Article {article_id} not found"}

        if article.status != ArticleStatus.PUBLISHED:
            if self.current_user.role not in [UserRole.EDITOR, UserRole.ADMIN]:
                return {"success": False, "error": "Article not published"}

        # Increment view count
        article.views += 1

        # Get author info
        author = self.users.get(article.author_id)

        # Get category names
        cat_names = [
            self.categories[cid].name
            for cid in article.categories
            if cid in self.categories
        ]

        # Get related articles
        related = []
        for rel_id in article.related_articles:
            rel = self.articles.get(rel_id)
            if rel and rel.status == ArticleStatus.PUBLISHED:
                related.append({"id": rel.id, "title": rel.title})

        return {
            "success": True,
            "article": {
                "id": article.id,
                "title": article.title,
                "content": article.content,
                "summary": article.summary,
                "type": article.content_type.value,
                "categories": cat_names,
                "tags": article.tags,
                "author": author.name if author else "Unknown",
                "created_at": article.created_at.isoformat(),
                "updated_at": article.updated_at.isoformat(),
                "version": article.version,
                "views": article.views,
                "helpful_votes": article.helpful_votes,
                "related_articles": related,
            },
        }

    def create_article(
        self,
        title: str,
        content: str,
        summary: str,
        content_type: str,
        categories: list,
        tags: list,
        status: str = "draft",
    ) -> dict:
        """Create a new article."""
        if self.current_user.role not in [
            UserRole.CONTRIBUTOR,
            UserRole.EDITOR,
            UserRole.ADMIN,
        ]:
            return {
                "success": False,
                "error": "Permission denied - contributor role required",
            }

        try:
            ct = ContentType[content_type.upper()]
            stat = ArticleStatus[status.upper()]
        except KeyError as e:
            return {"success": False, "error": f"Invalid type: {e}"}

        article_id = self._generate_id()
        slug = self._slugify(title)

        article = Article(
            id=article_id,
            title=title,
            slug=slug,
            content=content,
            summary=summary,
            content_type=ct,
            categories=categories,
            tags=tags,
            status=stat,
            author_id=self.current_user.id,
        )

        if stat == ArticleStatus.PUBLISHED:
            article.published_at = datetime.now()

        self.articles[article_id] = article

        # Update user contributions
        self.current_user.contributions += 1

        # Update category article counts
        for cat_id in categories:
            if cat_id in self.categories:
                self.categories[cat_id].article_count += 1

        return {
            "success": True,
            "article_id": article_id,
            "slug": slug,
            "status": stat.value,
            "message": f"Article '{title}' created successfully",
        }

    def update_article(
        self,
        article_id: str,
        content: str = None,
        summary: str = None,
        tags: list = None,
        change_description: str = "",
    ) -> dict:
        """Update an article (creates new version)."""
        article = self.articles.get(article_id)
        if not article:
            return {"success": False, "error": f"Article {article_id} not found"}

        # Check permissions
        can_edit = (
            self.current_user.id == article.author_id
            or self.current_user.role in [UserRole.EDITOR, UserRole.ADMIN]
        )
        if not can_edit:
            return {"success": False, "error": "Permission denied"}

        # Save current version
        old_version = ArticleVersion(
            version=article.version,
            content=article.content,
            summary=article.summary,
            author_id=article.author_id,
            created_at=article.updated_at,
            change_description="Previous version",
        )
        article.versions.append(old_version)

        # Update fields
        if content:
            article.content = content
        if summary:
            article.summary = summary
        if tags:
            article.tags = tags

        # Increment version
        parts = article.version.split(".")
        article.version = f"{parts[0]}.{int(parts[1]) + 1}"
        article.updated_at = datetime.now()

        # Update user contributions
        self.current_user.contributions += 1

        return {
            "success": True,
            "article_id": article_id,
            "new_version": article.version,
            "message": f"Article updated to version {article.version}",
        }

    def get_article_history(self, article_id: str) -> dict:
        """Get version history for an article."""
        article = self.articles.get(article_id)
        if not article:
            return {"success": False, "error": f"Article {article_id} not found"}

        versions = [
            {
                "version": article.version,
                "author": (
                    self.users[article.author_id].name
                    if article.author_id in self.users
                    else "Unknown"
                ),
                "date": article.updated_at.isoformat(),
                "change": "Current version",
                "is_current": True,
            }
        ]

        for v in reversed(article.versions):
            versions.append(
                {
                    "version": v.version,
                    "author": (
                        self.users[v.author_id].name
                        if v.author_id in self.users
                        else "Unknown"
                    ),
                    "date": v.created_at.isoformat(),
                    "change": v.change_description,
                    "is_current": False,
                }
            )

        return {
            "success": True,
            "article_id": article_id,
            "title": article.title,
            "versions": versions,
        }

    def vote_helpful(self, article_id: str, helpful: bool = True) -> dict:
        """Vote on whether article was helpful."""
        article = self.articles.get(article_id)
        if not article:
            return {"success": False, "error": f"Article {article_id} not found"}

        if helpful:
            article.helpful_votes += 1
        else:
            article.not_helpful_votes += 1

        return {
            "success": True,
            "message": "Thank you for your feedback!",
            "helpful_votes": article.helpful_votes,
            "not_helpful_votes": article.not_helpful_votes,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # RELATED & POPULAR
    # ──────────────────────────────────────────────────────────────────────────

    def get_related_articles(self, article_id: str, limit: int = 5) -> dict:
        """Get articles related to the given article."""
        article = self.articles.get(article_id)
        if not article:
            return {"success": False, "error": f"Article {article_id} not found"}

        # Find related by shared tags and categories
        candidates = []
        for other in self.articles.values():
            if other.id == article_id or other.status != ArticleStatus.PUBLISHED:
                continue

            score = 0
            # Shared categories
            shared_cats = set(article.categories) & set(other.categories)
            score += len(shared_cats) * 10

            # Shared tags
            shared_tags = set(article.tags) & set(other.tags)
            score += len(shared_tags) * 5

            # Explicit related
            if other.id in article.related_articles:
                score += 20

            if score > 0:
                candidates.append((other, score))

        # Sort by relevance
        candidates.sort(key=lambda x: x[1], reverse=True)

        return {
            "success": True,
            "article_id": article_id,
            "related": [
                {
                    "id": a.id,
                    "title": a.title,
                    "summary": a.summary,
                    "relevance_score": score,
                }
                for a, score in candidates[:limit]
            ],
        }

    def get_popular_articles(self, limit: int = 10, days: int = 30) -> dict:
        """Get most popular articles."""
        cutoff = datetime.now() - timedelta(days=days)

        articles = [
            a
            for a in self.articles.values()
            if a.status == ArticleStatus.PUBLISHED and a.published_at >= cutoff
        ]

        # Sort by views
        articles.sort(key=lambda a: a.views, reverse=True)

        return {
            "success": True,
            "period_days": days,
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "views": a.views,
                    "helpful_votes": a.helpful_votes,
                    "type": a.content_type.value,
                }
                for a in articles[:limit]
            ],
        }

    def get_recent_articles(self, limit: int = 10) -> dict:
        """Get recently published/updated articles."""
        articles = [
            a for a in self.articles.values() if a.status == ArticleStatus.PUBLISHED
        ]

        articles.sort(key=lambda a: a.updated_at, reverse=True)

        return {
            "success": True,
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "summary": a.summary,
                    "updated_at": a.updated_at.isoformat(),
                    "author": (
                        self.users[a.author_id].name
                        if a.author_id in self.users
                        else "Unknown"
                    ),
                }
                for a in articles[:limit]
            ],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # CONTRIBUTORS
    # ──────────────────────────────────────────────────────────────────────────

    def get_top_contributors(self, limit: int = 10) -> dict:
        """Get top wiki contributors."""
        contributors = [u for u in self.users.values() if u.contributions > 0]
        contributors.sort(key=lambda u: u.contributions, reverse=True)

        return {
            "success": True,
            "contributors": [
                {
                    "name": u.name,
                    "department": u.department,
                    "contributions": u.contributions,
                    "expertise": u.expertise_areas,
                }
                for u in contributors[:limit]
            ],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # USER MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def switch_user(self, user_id: str) -> dict:
        """Switch current user context (for demo)."""
        user = self.users.get(user_id)
        if not user:
            return {"success": False, "error": f"User {user_id} not found"}

        self.current_user = user
        return {
            "success": True,
            "message": f"Switched to: {user.name}",
            "role": user.role.value,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Corporate Knowledge Base Assistant.

Your role is to:
1. Help users search for information in the knowledge base
2. Navigate categories and find relevant articles
3. Suggest related content
4. Help contributors create and update content

You have access to these tools:
- search: Full-text search across articles
- list_categories: Browse category hierarchy
- get_category: Get category with articles
- get_article: Read full article
- create_article: Create new article (contributors only)
- update_article: Update existing article
- get_article_history: View version history
- vote_helpful: Mark article as helpful
- get_related_articles: Find related content
- get_popular_articles: View trending articles
- get_recent_articles: View latest updates
- get_top_contributors: See top wiki contributors

Be helpful in finding information. Suggest related articles when relevant. For complex topics, recommend creating a support ticket if the wiki doesn't have the answer."""


# ══════════════════════════════════════════════════════════════════════════════
# AGENT TOOLS
# ══════════════════════════════════════════════════════════════════════════════


def create_wiki_tools(service: KnowledgeBaseService) -> list:
    """Create tool definitions for the wiki agent."""
    return [
        {
            "name": "search",
            "description": "Full-text search across wiki articles",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {
                        "type": "string",
                        "description": "Filter by category ID",
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Filter: article, procedure, faq, etc.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                    },
                },
                "required": ["query"],
            },
            "function": lambda query, category=None, content_type=None, limit=10: service.search(
                query, category, content_type, limit
            ),
        },
        {
            "name": "list_categories",
            "description": "List wiki categories",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {
                        "type": "string",
                        "description": "Parent category for subcategories",
                    }
                },
            },
            "function": lambda parent_id=None: service.list_categories(parent_id),
        },
        {
            "name": "get_category",
            "description": "Get category details with articles",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {"type": "string", "description": "Category ID"}
                },
                "required": ["category_id"],
            },
            "function": lambda category_id: service.get_category(category_id),
        },
        {
            "name": "get_article",
            "description": "Get full article content",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "Article ID"}
                },
                "required": ["article_id"],
            },
            "function": lambda article_id: service.get_article(article_id),
        },
        {
            "name": "get_article_history",
            "description": "Get version history for an article",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "Article ID"}
                },
                "required": ["article_id"],
            },
            "function": lambda article_id: service.get_article_history(article_id),
        },
        {
            "name": "vote_helpful",
            "description": "Mark article as helpful or not",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "Article ID"},
                    "helpful": {"type": "boolean", "description": "True if helpful"},
                },
                "required": ["article_id"],
            },
            "function": lambda article_id, helpful=True: service.vote_helpful(
                article_id, helpful
            ),
        },
        {
            "name": "get_related_articles",
            "description": "Get articles related to the given one",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "Article ID"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                "required": ["article_id"],
            },
            "function": lambda article_id, limit=5: service.get_related_articles(
                article_id, limit
            ),
        },
        {
            "name": "get_popular_articles",
            "description": "Get most viewed articles",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results"},
                    "days": {"type": "integer", "description": "Time period in days"},
                },
            },
            "function": lambda limit=10, days=30: service.get_popular_articles(
                limit, days
            ),
        },
        {
            "name": "get_recent_articles",
            "description": "Get recently updated articles",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results"}
                },
            },
            "function": lambda limit=10: service.get_recent_articles(limit),
        },
        {
            "name": "get_top_contributors",
            "description": "Get top wiki contributors",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results"}
                },
            },
            "function": lambda limit=10: service.get_top_contributors(limit),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# DEMO AND INTERACTIVE MODES
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate wiki capabilities."""
    print("=" * 70)
    print("CORPORATE KNOWLEDGE BASE - DEMO MODE")
    print("=" * 70)

    service = KnowledgeBaseService()

    # Categories
    print("\n📁 ROOT CATEGORIES")
    print("-" * 50)
    cats = service.list_categories()
    for cat in cats["categories"]:
        print(
            f"  {cat['icon']} {cat['name']} ({cat['article_count']} articles, {cat['subcategory_count']} subcategories)"
        )

    # Search
    print("\n🔍 SEARCH: 'git branching'")
    print("-" * 50)
    results = service.search("git branching")
    for r in results["results"]:
        print(f"  [{r['score']}] {r['title']}")
        print(f"       {r['summary'][:60]}...")

    # Get article
    print("\n📄 ARTICLE: Git Branching Strategy")
    print("-" * 50)
    article = service.get_article("ART-001")
    a = article["article"]
    print(f"Title: {a['title']}")
    print(f"Author: {a['author']}")
    print(f"Views: {a['views']}")
    print(f"Tags: {', '.join(a['tags'])}")
    print(f"\nContent preview:\n{a['content'][:300]}...")

    # Related articles
    print("\n🔗 RELATED ARTICLES")
    print("-" * 50)
    related = service.get_related_articles("ART-001")
    for r in related["related"]:
        print(f"  • {r['title']} (relevance: {r['relevance_score']})")

    # Popular articles
    print("\n🔥 POPULAR ARTICLES (Last 30 days)")
    print("-" * 50)
    popular = service.get_popular_articles(limit=5)
    for p in popular["articles"]:
        print(f"  {p['title']} - {p['views']} views")

    # Contributors
    print("\n🏆 TOP CONTRIBUTORS")
    print("-" * 50)
    contributors = service.get_top_contributors(limit=3)
    for c in contributors["contributors"]:
        print(f"  {c['name']} ({c['department']}) - {c['contributions']} contributions")

    # Category drill-down
    print("\n📂 CATEGORY: Engineering > Development")
    print("-" * 50)
    cat_detail = service.get_category("CAT-002")
    c = cat_detail["category"]
    print(f"Category: {c['name']}")
    print(f"Description: {c['description']}")
    print(f"Articles:")
    for art in c["articles"]:
        print(f"  • {art['title']}")

    print("\n" + "=" * 70)
    print("Demo complete! Run with --interactive for full chat mode.")
    print("=" * 70)


async def interactive():
    """Run interactive wiki chat."""
    print("=" * 70)
    print("CORPORATE KNOWLEDGE BASE ASSISTANT")
    print("=" * 70)
    print("\nWelcome! I can help you find information in our knowledge base.")
    print("  • Search for articles and procedures")
    print("  • Browse categories")
    print("  • Find related content")
    print("\nType 'quit' to exit, 'demo' for demo mode.\n")

    service = KnowledgeBaseService()
    tools = create_wiki_tools(service)

    try:
        from agentic_brain import Agent

        agent = Agent(system_prompt=SYSTEM_PROMPT, tools=tools, model="gpt-4")
        use_agent = True
    except ImportError:
        print("Note: agentic-brain not installed. Running in simple mode.\n")
        use_agent = False

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("\nGoodbye!")
                break

            if user_input.lower() == "demo":
                await demo()
                continue

            if user_input.lower().startswith("search "):
                query = user_input[7:]
                result = service.search(query)
                print(f"\n🤖 Assistant: Found {result['results_count']} results:")
                for r in result["results"][:5]:
                    print(f"  • {r['title']}")
                continue

            if use_agent:
                response = await agent.chat(user_input)
                print(f"\n🤖 Assistant: {response}")
            else:
                print("\n🤖 Assistant: I understand you're looking for information.")
                print("   Quick commands: 'search <query>', 'demo'")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(demo())


if __name__ == "__main__":
    main()
