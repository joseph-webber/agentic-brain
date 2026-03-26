#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 25: Hybrid Cloud Deployment
====================================

Best of both worlds: local speed/privacy with cloud fallback.
Primary processing stays local, cloud APIs used when needed.

This deployment pattern is ideal for:
- Corporate environments with sensitive data
- Remote workers with variable connectivity
- Cost optimization (local is free, cloud costs money)
- Development teams needing flexibility

Architecture:
    ┌────────────────────────────────────────────────────────────────┐
    │                      HYBRID ARCHITECTURE                       │
    │                                                                │
    │  ┌──────────────────────────────────────────────────────────┐ │
    │  │                    LOCAL (Primary)                       │ │
    │  │  ┌──────────┐   ┌──────────┐   ┌─────────────────────┐  │ │
    │  │  │  Ollama  │   │  Neo4j   │   │  Local Vector DB    │  │ │
    │  │  │  Fast!   │   │  Memory  │   │  (FAISS/ChromaDB)   │  │ │
    │  │  └────┬─────┘   └────┬─────┘   └──────────┬──────────┘  │ │
    │  │       │              │                    │             │ │
    │  │       └──────────────┴────────────────────┘             │ │
    │  └────────────────────────│─────────────────────────────────┘ │
    │                           │                                   │
    │                    ┌──────┴──────┐                           │
    │                    │  FALLBACK   │                           │
    │                    │   ROUTER    │                           │
    │                    └──────┬──────┘                           │
    │                           │                                   │
    │  ┌────────────────────────│─────────────────────────────────┐ │
    │  │                    CLOUD (Fallback)                      │ │
    │  │  ┌──────────┐   ┌──────────┐   ┌─────────────────────┐  │ │
    │  │  │ OpenAI/  │   │ Firebase │   │   Cloud Vector      │  │ │
    │  │  │ Claude   │   │   Sync   │   │   (Pinecone/etc)    │  │ │
    │  │  └──────────┘   └──────────┘   └─────────────────────┘  │ │
    │  └──────────────────────────────────────────────────────────┘ │
    └────────────────────────────────────────────────────────────────┘

When Local is Used (90% of queries):
- Simple questions
- Routine tasks
- Privacy-sensitive data
- Fast responses needed
- Offline operation

When Cloud Fallback Triggers:
- Local model can't answer (low confidence)
- Complex reasoning required
- User explicitly requests cloud
- Local services down
- Need latest knowledge (RAG miss)

Data Sync Strategy:
- Conversations: Local-first, sync to cloud hourly
- Knowledge Base: Cloud-primary, cached locally
- User Data: Never leaves local by default

Demo Scenario:
    Corporate Knowledge Base Assistant.
    Answers company policy questions, product info,
    HR procedures - works offline but syncs when online.

Usage:
    python examples/25_hybrid_cloud.py
    python examples/25_hybrid_cloud.py --demo
    python examples/25_hybrid_cloud.py --interactive
    python examples/25_hybrid_cloud.py --sync-status

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b
    # Optional: OPENAI_API_KEY for cloud fallback
"""

import asyncio
import os
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Any
import argparse
import hashlib

# ══════════════════════════════════════════════════════════════════════════════
# ROUTING LOGIC
# ══════════════════════════════════════════════════════════════════════════════


class RouteDecision(Enum):
    """Where to route a query."""

    LOCAL = "local"
    CLOUD = "cloud"
    LOCAL_WITH_SYNC = "local_with_sync"


class QueryComplexity(Enum):
    """Estimated query complexity."""

    SIMPLE = "simple"  # Factual lookup
    MODERATE = "moderate"  # Some reasoning
    COMPLEX = "complex"  # Multi-step reasoning


@dataclass
class RoutingResult:
    """Result of routing decision."""

    decision: RouteDecision
    reason: str
    complexity: QueryComplexity
    estimated_tokens: int
    privacy_sensitive: bool


class HybridRouter:
    """
    Intelligent router that decides local vs cloud.

    Factors considered:
    - Query complexity
    - Privacy requirements
    - Local model confidence
    - Network availability
    - Cost optimization
    """

    def __init__(
        self,
        local_available: bool = True,
        cloud_available: bool = False,
        prefer_local: bool = True,
        cloud_threshold: float = 0.7,  # Confidence below this triggers cloud
    ):
        self.local_available = local_available
        self.cloud_available = cloud_available
        self.prefer_local = prefer_local
        self.cloud_threshold = cloud_threshold

        # Keywords that indicate privacy-sensitive queries
        self.privacy_keywords = [
            "salary",
            "performance",
            "disciplinary",
            "medical",
            "personal",
            "confidential",
            "private",
            "ssn",
            "password",
        ]

        # Keywords that suggest complex queries needing cloud
        self.complex_keywords = [
            "compare",
            "analyze",
            "why",
            "explain in detail",
            "step by step",
            "comprehensive",
            "evaluate",
        ]

    def route(self, query: str, context: dict = None) -> RoutingResult:
        """
        Decide where to route a query.

        Returns routing decision with reasoning.
        """
        query_lower = query.lower()
        context = context or {}

        # Check privacy sensitivity
        is_private = any(kw in query_lower for kw in self.privacy_keywords)
        if is_private:
            return RoutingResult(
                decision=RouteDecision.LOCAL,
                reason="Query contains privacy-sensitive keywords",
                complexity=QueryComplexity.SIMPLE,
                estimated_tokens=100,
                privacy_sensitive=True,
            )

        # Check complexity
        is_complex = any(kw in query_lower for kw in self.complex_keywords)
        complexity = QueryComplexity.COMPLEX if is_complex else QueryComplexity.SIMPLE

        # If only local available, use local
        if not self.cloud_available:
            return RoutingResult(
                decision=RouteDecision.LOCAL,
                reason="Cloud not available, using local",
                complexity=complexity,
                estimated_tokens=150 if is_complex else 80,
                privacy_sensitive=False,
            )

        # If only cloud available, use cloud
        if not self.local_available:
            return RoutingResult(
                decision=RouteDecision.CLOUD,
                reason="Local not available, using cloud",
                complexity=complexity,
                estimated_tokens=150 if is_complex else 80,
                privacy_sensitive=False,
            )

        # Both available - route based on complexity and preference
        if is_complex and not self.prefer_local:
            return RoutingResult(
                decision=RouteDecision.CLOUD,
                reason="Complex query routed to cloud for better reasoning",
                complexity=complexity,
                estimated_tokens=200,
                privacy_sensitive=False,
            )

        # Default to local
        return RoutingResult(
            decision=RouteDecision.LOCAL_WITH_SYNC,
            reason="Using local with async cloud sync",
            complexity=complexity,
            estimated_tokens=100,
            privacy_sensitive=False,
        )


# ══════════════════════════════════════════════════════════════════════════════
# SYNC ENGINE
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class SyncState:
    """Track sync state between local and cloud."""

    last_sync: Optional[datetime] = None
    pending_items: int = 0
    sync_in_progress: bool = False
    last_error: Optional[str] = None
    items_synced_today: int = 0


class SyncEngine:
    """
    Handles bidirectional sync between local and cloud.

    Local-first with periodic cloud backup:
    - Conversations sync every hour
    - Documents sync on change
    - User data never syncs (privacy)
    """

    def __init__(self, sync_interval_minutes: int = 60):
        self.sync_interval = timedelta(minutes=sync_interval_minutes)
        self.state = SyncState()
        self.pending_queue: list[dict] = []
        self.synced_hashes: set[str] = set()

    def queue_for_sync(self, item_type: str, data: dict):
        """Queue an item for next sync."""
        # Hash for deduplication
        item_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

        if item_hash not in self.synced_hashes:
            self.pending_queue.append(
                {
                    "type": item_type,
                    "data": data,
                    "queued_at": datetime.now().isoformat(),
                    "hash": item_hash,
                }
            )
            self.state.pending_items = len(self.pending_queue)

    def should_sync(self) -> bool:
        """Check if it's time to sync."""
        if not self.pending_queue:
            return False

        if self.state.last_sync is None:
            return True

        return datetime.now() - self.state.last_sync > self.sync_interval

    async def sync_to_cloud(self) -> dict:
        """
        Sync pending items to cloud.

        In production, this would call actual cloud APIs.
        """
        if self.state.sync_in_progress:
            return {"status": "already_running"}

        self.state.sync_in_progress = True

        try:
            items_to_sync = self.pending_queue.copy()
            synced = 0

            for item in items_to_sync:
                # Simulated cloud sync
                await asyncio.sleep(0.1)  # Simulate network
                self.synced_hashes.add(item["hash"])
                synced += 1

            self.pending_queue.clear()
            self.state.last_sync = datetime.now()
            self.state.pending_items = 0
            self.state.items_synced_today += synced

            return {
                "status": "success",
                "items_synced": synced,
                "timestamp": self.state.last_sync.isoformat(),
            }

        except Exception as e:
            self.state.last_error = str(e)
            return {"status": "error", "error": str(e)}
        finally:
            self.state.sync_in_progress = False

    def get_status(self) -> dict:
        """Get current sync status."""
        return {
            "last_sync": (
                self.state.last_sync.isoformat() if self.state.last_sync else None
            ),
            "pending_items": self.state.pending_items,
            "sync_in_progress": self.state.sync_in_progress,
            "items_synced_today": self.state.items_synced_today,
            "last_error": self.state.last_error,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CORPORATE KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class KnowledgeArticle:
    """A knowledge base article."""

    article_id: str
    title: str
    category: str
    content: str
    last_updated: str
    source: str  # "local" or "cloud"
    cached_at: Optional[str] = None


class CorporateKnowledgeBase:
    """
    Hybrid knowledge base with local cache.

    - Core articles cached locally (fast access)
    - Latest updates fetched from cloud periodically
    - Works offline with cached content
    """

    def __init__(self):
        # Local cache of knowledge articles
        self.local_cache: dict[str, KnowledgeArticle] = {}
        self.cache_timestamp: Optional[datetime] = None

        # Initialize with common corporate knowledge
        self._init_default_knowledge()

    def _init_default_knowledge(self):
        """Load default knowledge articles."""
        articles = [
            KnowledgeArticle(
                article_id="KB001",
                title="Remote Work Policy",
                category="HR",
                content="""
                REMOTE WORK GUIDELINES:
                
                Eligibility:
                - All employees after 90-day probation
                - Manager approval required
                - Performance-based
                
                Equipment:
                - Company laptop provided
                - Monitors: Up to 2x 27-inch monitors
                - Keyboard and mouse: Ergonomic options available
                - $500 home office stipend (one-time)
                
                Expectations:
                - Core hours: 10am-3pm local time
                - Video on for meetings
                - Response time: 1 hour during work hours
                - Minimum 2 days in office per week (hybrid)
                
                Security:
                - VPN required for all company resources
                - No public WiFi for sensitive work
                - Screen lock when away
                """,
                last_updated="2024-03-01",
                source="local",
            ),
            KnowledgeArticle(
                article_id="KB002",
                title="Expense Reimbursement",
                category="Finance",
                content="""
                EXPENSE POLICY:
                
                Pre-Approval Required:
                - Travel over $500
                - Equipment over $200
                - Client entertainment over $100
                
                Submission:
                - Within 30 days of expense
                - Original receipts required
                - Manager approval in Concur
                
                Categories:
                - Travel: Air, hotel, car rental
                - Meals: Per diem or actuals with receipts
                - Equipment: Monitors, keyboards, mice (need IT approval)
                - Supplies: Office supplies under $50 auto-approved
                
                Processing Time:
                - Domestic: 5 business days
                - International: 10 business days
                
                Direct deposit to payroll account.
                """,
                last_updated="2024-02-15",
                source="local",
            ),
            KnowledgeArticle(
                article_id="KB003",
                title="IT Support Procedures",
                category="IT",
                content="""
                IT SUPPORT:
                
                How to Get Help:
                1. Self-service portal: help.company.com
                2. Slack: #it-support
                3. Email: it@company.com
                4. Phone: x5555 (urgent only)
                
                Common Issues:
                
                Password Reset:
                - Self-service: password.company.com
                - If locked out: call IT
                
                VPN Issues:
                - Restart VPN client
                - Check internet connection
                - Try alternate server
                
                Equipment Requests:
                - Monitors, keyboards, mice through IT portal
                - Standard equipment: 3-day delivery
                - Special requests: 2-week lead time
                
                Lost/Stolen Device:
                - IMMEDIATELY report to security@company.com
                - Device will be remotely wiped
                - Police report required for insurance
                """,
                last_updated="2024-03-15",
                source="local",
            ),
            KnowledgeArticle(
                article_id="KB004",
                title="Product Catalog - Electronics",
                category="Products",
                content="""
                OFFICE ELECTRONICS CATALOG:
                
                Monitors:
                - Pro Display 27" 4K: $399 (SKU: MON-27-4K)
                - Standard 24" HD: $199 (SKU: MON-24-HD)
                - Ultrawide 34" Curved: $599 (SKU: MON-34-UW)
                
                Keyboards:
                - Ergonomic Wireless: $89 (SKU: KB-ERGO)
                - Mechanical RGB: $129 (SKU: KB-MECH)
                - Standard USB: $29 (SKU: KB-STD)
                
                Mice:
                - Ergonomic Vertical: $49 (SKU: MS-VERT)
                - Wireless Pro: $79 (SKU: MS-WL-PRO)
                - Standard USB: $19 (SKU: MS-STD)
                
                Accessories:
                - USB-C Hub 7-port: $59 (SKU: HUB-7P)
                - USB Hub 4-port: $29 (SKU: HUB-4P)
                - HDMI Cable 2m: $15 (SKU: CBL-HDMI)
                - USB-C Cable 1m: $12 (SKU: CBL-USBC)
                
                Employee Discount: 25% off all items
                """,
                last_updated="2024-03-10",
                source="local",
            ),
            KnowledgeArticle(
                article_id="KB005",
                title="Meeting Room Booking",
                category="Facilities",
                content="""
                MEETING ROOM BOOKING:
                
                How to Book:
                - Outlook calendar: Add room as attendee
                - Slack: /book-room command
                - Portal: rooms.company.com
                
                Available Rooms:
                - Conference A (12 people): Video conferencing
                - Conference B (8 people): Whiteboard, video
                - Huddle 1-4 (4 people each): Quick meetings
                - Boardroom (20 people): Executive meetings only
                
                Rules:
                - Maximum 2-hour booking
                - Release room if not using within 10 min
                - Clean up after use
                - No food in Boardroom
                
                Equipment Issues:
                - Report to facilities@company.com
                - Or Slack: #room-issues
                """,
                last_updated="2024-01-20",
                source="local",
            ),
        ]

        for article in articles:
            article.cached_at = datetime.now().isoformat()
            self.local_cache[article.article_id] = article

        self.cache_timestamp = datetime.now()

    def search(self, query: str) -> list[KnowledgeArticle]:
        """Search articles by keyword."""
        query_lower = query.lower()
        results = []

        for article in self.local_cache.values():
            if (
                query_lower in article.title.lower()
                or query_lower in article.content.lower()
                or query_lower in article.category.lower()
            ):
                results.append(article)

        return results

    def get_article(self, article_id: str) -> Optional[KnowledgeArticle]:
        """Get article by ID."""
        return self.local_cache.get(article_id)

    def get_by_category(self, category: str) -> list[KnowledgeArticle]:
        """Get all articles in a category."""
        return [
            a
            for a in self.local_cache.values()
            if a.category.lower() == category.lower()
        ]

    def update_from_cloud(self, articles: list[dict]):
        """Update local cache from cloud sync."""
        for article_data in articles:
            article = KnowledgeArticle(
                article_id=article_data["id"],
                title=article_data["title"],
                category=article_data["category"],
                content=article_data["content"],
                last_updated=article_data["updated"],
                source="cloud",
                cached_at=datetime.now().isoformat(),
            )
            self.local_cache[article.article_id] = article

        self.cache_timestamp = datetime.now()


# ══════════════════════════════════════════════════════════════════════════════
# HYBRID KNOWLEDGE ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class HybridKnowledgeAssistant:
    """
    Corporate knowledge assistant with hybrid architecture.

    - Local Ollama for fast, private responses
    - Cloud fallback for complex queries
    - Bidirectional sync for consistency
    """

    def __init__(
        self,
        local_model: str = "llama3.1:8b",
        cloud_model: str = "gpt-4o-mini",
        prefer_local: bool = True,
    ):
        self.local_model = local_model
        self.cloud_model = cloud_model
        self.prefer_local = prefer_local

        # Initialize components
        self.kb = CorporateKnowledgeBase()
        self.router = HybridRouter(
            local_available=True,
            cloud_available=os.environ.get("OPENAI_API_KEY") is not None,
            prefer_local=prefer_local,
        )
        self.sync_engine = SyncEngine(sync_interval_minutes=60)

        # Stats
        self.stats = {
            "local_queries": 0,
            "cloud_queries": 0,
            "cache_hits": 0,
            "total_queries": 0,
        }

    async def query(self, question: str, user_id: str = "anonymous") -> dict:
        """
        Process a knowledge query.

        1. Route decision (local vs cloud)
        2. Search knowledge base
        3. Generate response
        4. Queue for sync if needed
        """
        self.stats["total_queries"] += 1

        # Route decision
        routing = self.router.route(question)

        # Search knowledge base
        relevant_articles = self.kb.search(question)

        if relevant_articles:
            self.stats["cache_hits"] += 1

        # Generate response based on routing
        if routing.decision in (RouteDecision.LOCAL, RouteDecision.LOCAL_WITH_SYNC):
            self.stats["local_queries"] += 1
            response = await self._local_response(question, relevant_articles)

            # Queue for sync if needed
            if routing.decision == RouteDecision.LOCAL_WITH_SYNC:
                self.sync_engine.queue_for_sync(
                    "conversation",
                    {
                        "user_id": user_id,
                        "question": question,
                        "response": response["answer"],
                        "timestamp": datetime.now().isoformat(),
                    },
                )
        else:
            self.stats["cloud_queries"] += 1
            response = await self._cloud_response(question, relevant_articles)

        response["routing"] = {
            "decision": routing.decision.value,
            "reason": routing.reason,
            "complexity": routing.complexity.value,
        }

        return response

    async def _local_response(
        self, question: str, articles: list[KnowledgeArticle]
    ) -> dict:
        """Generate response using local LLM."""
        # In production, use agentic_brain.LLMRouter
        # This is simplified for demonstration

        if not articles:
            return {
                "answer": "I couldn't find specific information about that in our knowledge base. "
                "Please contact the relevant department directly.",
                "articles_used": [],
                "model": self.local_model,
                "source": "local",
            }

        # Build context from articles
        context = "\n\n".join(
            [f"[{a.article_id}] {a.title}:\n{a.content}" for a in articles[:3]]
        )

        # Generate answer (simplified - would use LLM in production)
        answer = self._generate_answer(question, articles)

        return {
            "answer": answer,
            "articles_used": [a.article_id for a in articles[:3]],
            "model": self.local_model,
            "source": "local",
        }

    async def _cloud_response(
        self, question: str, articles: list[KnowledgeArticle]
    ) -> dict:
        """Generate response using cloud LLM."""
        # In production, call OpenAI/Anthropic API
        # This is simplified for demonstration

        return {
            "answer": f"[Cloud response for: {question}]",
            "articles_used": [a.article_id for a in articles[:3]],
            "model": self.cloud_model,
            "source": "cloud",
        }

    def _generate_answer(self, question: str, articles: list[KnowledgeArticle]) -> str:
        """Generate answer from knowledge articles."""
        q_lower = question.lower()

        # Remote work questions
        if any(kw in q_lower for kw in ["remote", "work from home", "wfh", "hybrid"]):
            kb001 = self.kb.get_article("KB001")
            if kb001:
                return f"Based on our Remote Work Policy (KB001):\n\n{kb001.content}"

        # Expense questions
        if any(kw in q_lower for kw in ["expense", "reimbursement", "receipt"]):
            kb002 = self.kb.get_article("KB002")
            if kb002:
                return f"Based on our Expense Policy (KB002):\n\n{kb002.content}"

        # IT questions
        if any(
            kw in q_lower for kw in ["it", "support", "password", "vpn", "equipment"]
        ):
            kb003 = self.kb.get_article("KB003")
            if kb003:
                return f"Based on IT Support Procedures (KB003):\n\n{kb003.content}"

        # Product questions
        if any(
            kw in q_lower
            for kw in ["product", "monitor", "keyboard", "mouse", "cable", "hub"]
        ):
            kb004 = self.kb.get_article("KB004")
            if kb004:
                return f"Based on our Product Catalog (KB004):\n\n{kb004.content}"

        # Meeting rooms
        if any(kw in q_lower for kw in ["meeting", "room", "book", "conference"]):
            kb005 = self.kb.get_article("KB005")
            if kb005:
                return f"Based on Meeting Room Booking (KB005):\n\n{kb005.content}"

        # Generic response
        if articles:
            return f"I found relevant information in {articles[0].title}:\n\n{articles[0].content}"

        return "I couldn't find specific information about that. Please contact the relevant department."

    async def sync(self) -> dict:
        """Trigger sync to cloud."""
        return await self.sync_engine.sync_to_cloud()

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            **self.stats,
            "sync_status": self.sync_engine.get_status(),
            "local_model": self.local_model,
            "cloud_available": self.router.cloud_available,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CONNECTIVITY CHECKER
# ══════════════════════════════════════════════════════════════════════════════


def check_connectivity() -> dict:
    """Check local and cloud service availability."""
    import subprocess

    status = {
        "ollama": False,
        "neo4j": False,
        "internet": False,
        "openai_api": False,
    }

    # Check Ollama
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "http://localhost:11434/api/tags",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status["ollama"] = result.stdout.strip() == "200"
    except Exception:
        pass

    # Check Neo4j
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "http://localhost:7474",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status["neo4j"] = result.stdout.strip() in ("200", "401")
    except Exception:
        pass

    # Check internet
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "8.8.8.8"], capture_output=True, timeout=5
        )
        status["internet"] = result.returncode == 0
    except Exception:
        pass

    # Check OpenAI API key
    status["openai_api"] = bool(os.environ.get("OPENAI_API_KEY"))

    return status


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def run_demo():
    """Run demonstration of hybrid deployment."""
    print("=" * 70)
    print("☁️ HYBRID CLOUD DEPLOYMENT")
    print("   Corporate Knowledge Assistant")
    print("=" * 70)
    print()

    # Check connectivity
    print("🔍 CONNECTIVITY CHECK")
    print("-" * 40)
    status = check_connectivity()
    print(f"  Ollama (local):  {'✅' if status['ollama'] else '❌'}")
    print(f"  Neo4j (local):   {'✅' if status['neo4j'] else '❌'}")
    print(f"  Internet:        {'✅' if status['internet'] else '❌'}")
    print(f"  OpenAI API Key:  {'✅' if status['openai_api'] else '❌'}")
    print()

    # Initialize assistant
    assistant = HybridKnowledgeAssistant(
        prefer_local=True,
    )

    print("📚 KNOWLEDGE BASE")
    print("-" * 40)
    print(f"  Articles cached: {len(assistant.kb.local_cache)}")
    print(f"  Categories: HR, Finance, IT, Products, Facilities")
    print()

    # Demo queries
    print("💬 DEMO QUERIES")
    print("-" * 40)

    demo_queries = [
        "What's our remote work policy?",
        "How do I submit an expense report?",
        "What monitors are available for employees?",
        "I need IT support, who do I contact?",
        "How do I book a meeting room?",
    ]

    for query in demo_queries:
        print(f"\n👤 User: {query}")
        response = await assistant.query(query)

        # Show routing decision
        routing = response["routing"]
        print(f"   📡 Route: {routing['decision']} ({routing['reason']})")
        print(f"   📄 Articles: {', '.join(response['articles_used']) or 'None'}")
        print(f"   🤖 Model: {response['model']}")
        print(f"\n💬 Answer: {response['answer'][:300]}...")
        print("-" * 40)

    # Show stats
    print("\n📊 STATISTICS")
    print("-" * 40)
    stats = assistant.get_stats()
    print(f"  Total queries: {stats['total_queries']}")
    print(f"  Local queries: {stats['local_queries']}")
    print(f"  Cloud queries: {stats['cloud_queries']}")
    print(f"  Cache hits: {stats['cache_hits']}")
    print(f"  Pending sync: {stats['sync_status']['pending_items']} items")


async def run_interactive():
    """Run interactive knowledge assistant."""
    print("=" * 70)
    print("☁️ HYBRID KNOWLEDGE ASSISTANT - INTERACTIVE MODE")
    print("=" * 70)
    print()

    assistant = HybridKnowledgeAssistant()

    print("Commands: 'quit', 'stats', 'sync', 'status', 'articles'")
    print()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("Goodbye! 👋")
                break

            if user_input.lower() == "stats":
                stats = assistant.get_stats()
                print(f"\n📊 Stats: {json.dumps(stats, indent=2)}")
                continue

            if user_input.lower() == "sync":
                result = await assistant.sync()
                print(f"\n🔄 Sync: {result}")
                continue

            if user_input.lower() == "status":
                status = check_connectivity()
                print(f"\n🔌 Connectivity: {json.dumps(status, indent=2)}")
                continue

            if user_input.lower() == "articles":
                print("\n📚 Knowledge Articles:")
                for article in assistant.kb.local_cache.values():
                    print(
                        f"  • [{article.article_id}] {article.title} ({article.category})"
                    )
                continue

            response = await assistant.query(user_input)
            print(f"\n📡 Route: {response['routing']['decision']}")
            print(f"💬 {response['answer'][:500]}")
            print()

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


def show_sync_status():
    """Show detailed sync status."""
    print("=" * 70)
    print("🔄 SYNC STATUS")
    print("=" * 70)
    print()

    # Check connectivity
    status = check_connectivity()

    print("SERVICES:")
    print(
        f"  Local Ollama:   {'✅ Running' if status['ollama'] else '❌ Not available'}"
    )
    print(
        f"  Local Neo4j:    {'✅ Running' if status['neo4j'] else '❌ Not available'}"
    )
    print(f"  Internet:       {'✅ Connected' if status['internet'] else '❌ Offline'}")
    print(
        f"  Cloud API:      {'✅ Configured' if status['openai_api'] else '❌ Not configured'}"
    )
    print()

    print("MODE:")
    if status["ollama"] and status["internet"]:
        print("  🔄 HYBRID - Local + Cloud available")
    elif status["ollama"]:
        print("  📴 OFFLINE - Local only (no sync)")
    elif status["internet"]:
        print("  ☁️  CLOUD ONLY - Local services down")
    else:
        print("  ❌ NO SERVICE - Both local and cloud unavailable")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid Cloud Deployment Example")
    parser.add_argument("--demo", action="store_true", help="Run demonstration mode")
    parser.add_argument(
        "--interactive", action="store_true", help="Run interactive mode"
    )
    parser.add_argument("--sync-status", action="store_true", help="Show sync status")

    args = parser.parse_args()

    if args.sync_status:
        show_sync_status()
    elif args.interactive:
        asyncio.run(run_interactive())
    else:
        # Default to demo
        asyncio.run(run_demo())
