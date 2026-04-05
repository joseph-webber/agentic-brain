#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 14: Business Knowledge Brain

Demonstrates:
- Neo4j knowledge graph for business data
- Supplier/customer relationship tracking
- AI-assisted query interface
- Session continuity (remember last topic)
- Learning from interactions

This is a simplified business brain pattern used in real-world
automation projects. Perfect for:
- CRM-style relationship tracking
- Supplier management
- Customer context lookup
- Business knowledge capture

Requirements:
- Ollama running with llama3.1:8b
- Neo4j running (or use InMemoryStore fallback)

Author: agentic-brain
License: MIT
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Agentic Brain imports
from agentic_brain import Agent
from agentic_brain.memory import get_memory_backend
from agentic_brain.router import LLMRouter

# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS MODELS
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Supplier:
    """Represents a business supplier/vendor."""

    name: str
    short_name: str
    email_domain: str
    contact_email: str
    products: list[str] = field(default_factory=list)
    payment_terms: str = "Net 30"
    notes: str = ""


@dataclass
class Customer:
    """Represents a customer."""

    email: str
    name: str
    total_orders: int = 0
    total_spent: float = 0.0
    last_order_date: Optional[str] = None
    communication_style: str = "formal"  # formal, casual, terse


@dataclass
class Learning:
    """A piece of business knowledge learned over time."""

    topic: str
    content: str
    source: str  # "user", "email", "invoice", etc.
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS BRAIN
# ─────────────────────────────────────────────────────────────────────────────


class BusinessBrain:
    """AI-powered business knowledge brain.

    Stores and retrieves business knowledge using a knowledge graph,
    with AI assistance for natural language queries.
    """

    def __init__(self, model: str = "llama3.1:8b"):
        """Initialize the business brain."""
        self.model = model
        self.memory = get_memory_backend()  # Neo4j or InMemory
        self.router: Optional[LLMRouter] = None

        # In-memory caches (would be persisted in production)
        self.suppliers: dict[str, Supplier] = {}
        self.customers: dict[str, Customer] = {}
        self.learnings: list[Learning] = []

        # Session state
        self.last_topic: Optional[str] = None
        self.last_query_time: Optional[datetime] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.router = LLMRouter(
            providers=["ollama"],
            default_model=self.model,
        )
        await self.router.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.router:
            await self.router.__aexit__(exc_type, exc_val, exc_tb)

    # ─────────────────────────────────────────────────────────────────────
    # SUPPLIER MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def add_supplier(self, supplier: Supplier) -> None:
        """Add or update a supplier."""
        self.suppliers[supplier.short_name.lower()] = supplier
        print(f"✅ Added supplier: {supplier.name}")

    def get_supplier(self, name: str) -> Optional[Supplier]:
        """Get supplier by name (fuzzy match)."""
        name_lower = name.lower()

        # Exact match
        if name_lower in self.suppliers:
            return self.suppliers[name_lower]

        # Partial match
        for key, supplier in self.suppliers.items():
            if name_lower in key or name_lower in supplier.name.lower():
                return supplier

        return None

    def list_suppliers(self) -> list[Supplier]:
        """List all suppliers."""
        return list(self.suppliers.values())

    # ─────────────────────────────────────────────────────────────────────
    # CUSTOMER MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def add_customer(self, customer: Customer) -> None:
        """Add or update a customer."""
        self.customers[customer.email.lower()] = customer
        print(f"✅ Added customer: {customer.name}")

    def get_customer(self, email: str) -> Optional[Customer]:
        """Get customer by email."""
        return self.customers.get(email.lower())

    async def get_customer_context(self, email: str) -> str:
        """Get AI-summarized customer context for drafting replies.

        Args:
            email: Customer email address

        Returns:
            Context summary for AI-assisted reply drafting
        """
        customer = self.get_customer(email)

        if not customer:
            return f"No customer record found for {email}"

        # Build context
        context = f"""Customer: {customer.name}
Email: {customer.email}
Total Orders: {customer.total_orders}
Total Spent: ${customer.total_spent:.2f}
Last Order: {customer.last_order_date or 'Never'}
Communication Style: {customer.communication_style}
"""

        # Use AI to summarize and suggest approach
        prompt = f"""Based on this customer profile, provide a brief 2-3 sentence
summary of how to approach communication with them:

{context}

Be specific about tone and any special considerations."""

        summary = await self.router.complete(prompt)

        return f"{context}\n📝 AI Recommendation:\n{summary}"

    # ─────────────────────────────────────────────────────────────────────
    # LEARNING / MEMORY
    # ─────────────────────────────────────────────────────────────────────

    def remember(self, topic: str, content: str, source: str = "user") -> None:
        """Store a piece of business knowledge.

        Args:
            topic: Topic/category for the learning
            content: The actual knowledge to store
            source: Where this came from (user, email, etc.)
        """
        learning = Learning(topic=topic, content=content, source=source)
        self.learnings.append(learning)
        print(f"📝 Learned: [{topic}] {content[:50]}...")

    def recall(self, topic: Optional[str] = None) -> list[Learning]:
        """Recall learned knowledge.

        Args:
            topic: Optional topic filter

        Returns:
            List of relevant learnings
        """
        if topic is None:
            return self.learnings[-10:]  # Last 10

        topic_lower = topic.lower()
        return [l for l in self.learnings if topic_lower in l.topic.lower()]

    # ─────────────────────────────────────────────────────────────────────
    # AI QUERY INTERFACE
    # ─────────────────────────────────────────────────────────────────────

    async def query(self, question: str) -> str:
        """Ask the brain a natural language question.

        Args:
            question: Natural language question about the business

        Returns:
            AI-generated answer based on stored knowledge
        """
        # Track session state
        self.last_query_time = datetime.now()

        # Build context from stored knowledge
        context_parts = []

        # Add supplier info
        if self.suppliers:
            supplier_list = ", ".join(
                f"{s.name} ({s.short_name})" for s in self.suppliers.values()
            )
            context_parts.append(f"Suppliers: {supplier_list}")

        # Add customer info
        if self.customers:
            customer_list = ", ".join(
                f"{c.name} ({c.email})" for c in self.customers.values()
            )
            context_parts.append(f"Customers: {customer_list}")

        # Add recent learnings
        if self.learnings:
            learning_text = "\n".join(
                f"- [{l.topic}] {l.content}" for l in self.learnings[-5:]
            )
            context_parts.append(f"Recent learnings:\n{learning_text}")

        context = "\n\n".join(context_parts) or "No stored knowledge yet."

        # Build prompt
        prompt = f"""You are a business assistant with access to this knowledge:

{context}

Answer this question concisely and helpfully:
{question}

If you don't have enough information, say so clearly."""

        # Get AI response
        response = await self.router.complete(prompt)

        # Extract topic for session continuity
        self.last_topic = question[:50]

        return response

    # ─────────────────────────────────────────────────────────────────────
    # SESSION CONTINUITY
    # ─────────────────────────────────────────────────────────────────────

    def get_session_summary(self) -> str:
        """Get a summary for session startup.

        Returns:
            Summary of last session state for continuity
        """
        parts = []

        if self.last_topic:
            parts.append(f"📌 Last topic: {self.last_topic}")

        if self.last_query_time:
            parts.append(
                f"⏰ Last active: {self.last_query_time.strftime('%Y-%m-%d %H:%M')}"
            )

        parts.append(
            f"📊 Data: {len(self.suppliers)} suppliers, "
            f"{len(self.customers)} customers, "
            f"{len(self.learnings)} learnings"
        )

        return "\n".join(parts)

    def wrapup(self, summary: str, pending_tasks: list[str] = None) -> None:
        """Save session state before ending.

        Args:
            summary: Summary of what was accomplished
            pending_tasks: Optional list of pending tasks
        """
        self.remember(
            topic="session_wrapup",
            content=f"Session summary: {summary}. Pending: {pending_tasks or []}",
            source="session",
        )
        print(f"💾 Session saved: {summary}")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────


async def demo():
    """Demonstrate the business brain."""

    print("=" * 60)
    print("Business Knowledge Brain Example")
    print("=" * 60)

    async with BusinessBrain() as brain:
        # Step 1: Add some suppliers
        print("\n📦 Adding suppliers...")
        brain.add_supplier(
            Supplier(
                name="Innovative Music",
                short_name="Innovative",
                email_domain="halleonard.com.au",
                contact_email="orders@halleonard.com.au",
                products=["sheet music", "accessories"],
                payment_terms="Net 30",
            )
        )

        brain.add_supplier(
            Supplier(
                name="Ambertech Distribution",
                short_name="Ambertech",
                email_domain="ambertech.com.au",
                contact_email="sales@ambertech.com.au",
                products=["audio equipment", "cables"],
                payment_terms="Net 14",
            )
        )

        # Step 2: Add some customers
        print("\n👥 Adding customers...")
        brain.add_customer(
            Customer(
                email="john@example.com",
                name="John Smith",
                total_orders=5,
                total_spent=1234.56,
                last_order_date="2026-03-15",
                communication_style="casual",
            )
        )

        brain.add_customer(
            Customer(
                email="corporate@bigcompany.com",
                name="BigCorp Purchasing",
                total_orders=50,
                total_spent=45000.00,
                last_order_date="2026-03-20",
                communication_style="formal",
            )
        )

        # Step 3: Add some learnings
        print("\n📝 Adding business knowledge...")
        brain.remember(
            topic="Innovative payment",
            content="Innovative Music gives 2% discount for early payment",
            source="invoice",
        )
        brain.remember(
            topic="Ambertech shipping",
            content="Ambertech ships next day if ordered before 2pm",
            source="email",
        )
        brain.remember(
            topic="BigCorp contact",
            content="Always CC procurement@bigcompany.com on BigCorp orders",
            source="user",
        )

        # Step 4: Natural language queries
        print("\n🤖 AI Query Interface...")
        print("-" * 40)

        questions = [
            "Who are my suppliers?",
            "What do I know about Ambertech?",
            "How should I communicate with BigCorp?",
        ]

        for q in questions:
            print(f"\n❓ {q}")
            answer = await brain.query(q)
            print(f"💬 {answer}")

        # Step 5: Customer context
        print("\n\n📋 Getting customer context for reply...")
        print("-" * 40)
        context = await brain.get_customer_context("corporate@bigcompany.com")
        print(context)

        # Step 6: Session summary
        print("\n\n📊 Session Summary")
        print("-" * 40)
        print(brain.get_session_summary())

        # Step 7: Wrapup
        brain.wrapup(
            summary="Added suppliers and customers, tested queries",
            pending_tasks=["Follow up with Ambertech on delivery times"],
        )

    print("\n" + "=" * 60)
    print("✅ Business brain demo complete!")
    print("\nThis pattern can be extended for:")
    print("  • CRM integration")
    print("  • Email thread indexing")
    print("  • Invoice processing")
    print("  • Order tracking")
    print("  • Staff knowledge sharing")


if __name__ == "__main__":
    asyncio.run(demo())
