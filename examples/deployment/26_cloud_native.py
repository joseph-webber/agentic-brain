#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 26: Cloud Native Deployment
=====================================

Pure cloud architecture for maximum scalability.
Designed for multi-device, multi-location deployments.

This deployment pattern is ideal for:
- Multi-location retail chains
- Distributed teams across regions
- Mobile-first applications
- Serverless/FaaS deployments
- Applications requiring real-time sync

Architecture:
    ┌────────────────────────────────────────────────────────────────────┐
    │                     CLOUD NATIVE ARCHITECTURE                      │
    │                                                                    │
    │  ┌─────────────────────────────────────────────────────────────┐  │
    │  │                    CLIENT LAYER                             │  │
    │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │  │
    │  │  │  Web App │  │ Mobile   │  │  Kiosk   │  │  Tablet  │   │  │
    │  │  │ (React)  │  │  (iOS)   │  │ (Chrome) │  │ (Android)│   │  │
    │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │  │
    │  └───────┴──────────────┴──────────────┴──────────────┴───────┘  │
    │                              │                                    │
    │                       ┌──────┴──────┐                            │
    │                       │  Firebase   │                            │
    │                       │  Realtime   │                            │
    │                       └──────┬──────┘                            │
    │                              │                                    │
    │  ┌─────────────────────────────────────────────────────────────┐  │
    │  │                    SERVICE LAYER                            │  │
    │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │  │
    │  │  │ Cloud LLM    │  │ Cloud Vector │  │   Cloud Storage  │  │  │
    │  │  │ (OpenAI/     │  │ (Pinecone/   │  │   (Firebase/     │  │  │
    │  │  │  Anthropic)  │  │  Weaviate)   │  │    S3/GCS)       │  │  │
    │  │  └──────────────┘  └──────────────┘  └──────────────────┘  │  │
    │  └─────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────────┘

Key Features:
- Real-time sync via Firebase/Firestore
- Multi-tenant support
- Horizontal scaling (serverless)
- No local dependencies
- Works on any device with a browser

Demo Scenario:
    Multi-location retail chain chat assistant.
    Customers at any store can get product info,
    check stock, find items - all synced in real-time.

Serverless Deployment Options:
- AWS Lambda + API Gateway
- Google Cloud Functions
- Azure Functions
- Vercel Edge Functions
- Cloudflare Workers

Usage:
    python examples/26_cloud_native.py
    python examples/26_cloud_native.py --demo
    python examples/26_cloud_native.py --interactive
    python examples/26_cloud_native.py --simulate-traffic

Requirements:
    pip install agentic-brain
    # Cloud API keys required:
    # OPENAI_API_KEY or ANTHROPIC_API_KEY
    # FIREBASE_CONFIG (optional, simulated if missing)
"""

import argparse
import asyncio
import json
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

# ══════════════════════════════════════════════════════════════════════════════
# MULTI-TENANT CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class TenantConfig:
    """Configuration for a retail chain tenant."""

    tenant_id: str
    name: str
    stores: list[str]
    primary_region: str
    llm_model: str = "gpt-4o-mini"
    max_concurrent_chats: int = 100
    features_enabled: list[str] = field(
        default_factory=lambda: ["product_search", "stock_check", "store_locator"]
    )


@dataclass
class CloudConfig:
    """Cloud-native deployment configuration."""

    # LLM Settings
    llm_provider: str = "openai"  # openai, anthropic, google
    llm_model: str = "gpt-4o-mini"
    llm_api_key: Optional[str] = None

    # Vector DB (for RAG)
    vector_provider: str = "pinecone"  # pinecone, weaviate, qdrant
    vector_api_key: Optional[str] = None
    vector_index: str = "retail-products"

    # Real-time Sync
    realtime_provider: str = "firebase"  # firebase, supabase, pusher
    firebase_project: Optional[str] = None

    # Storage
    storage_provider: str = "gcs"  # s3, gcs, azure_blob
    storage_bucket: str = "retail-chat-data"

    # Multi-tenant
    multi_tenant: bool = True
    tenant_isolation: str = "namespace"  # namespace, database, schema

    def validate(self) -> list[str]:
        """Validate cloud configuration."""
        issues = []

        # Check LLM API key
        if not self.llm_api_key and not os.environ.get("OPENAI_API_KEY"):
            issues.append("No LLM API key configured")

        return issues


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATED FIREBASE REALTIME
# ══════════════════════════════════════════════════════════════════════════════


class SimulatedFirebase:
    """
    Simulated Firebase Realtime Database.

    In production, replace with actual Firebase Admin SDK.
    This demonstrates the patterns without requiring credentials.
    """

    def __init__(self, project_id: str = "demo-retail"):
        self.project_id = project_id
        self.data: Dict[str, Any] = {
            "chats": {},
            "stores": {},
            "products": {},
            "analytics": {},
        }
        self.listeners: Dict[str, list] = {}
        self._init_sample_data()

    def _init_sample_data(self):
        """Initialize sample retail data."""
        # Stores
        self.data["stores"] = {
            "store_sydney": {
                "id": "store_sydney",
                "name": "Sydney CBD",
                "address": "123 George Street, Sydney NSW 2000",
                "timezone": "Australia/Sydney",
                "status": "open",
                "manager": "Sarah Chen",
            },
            "store_melbourne": {
                "id": "store_melbourne",
                "name": "Melbourne Central",
                "address": "456 Bourke Street, Melbourne VIC 3000",
                "timezone": "Australia/Melbourne",
                "status": "open",
                "manager": "James Wilson",
            },
            "store_brisbane": {
                "id": "store_brisbane",
                "name": "Brisbane City",
                "address": "789 Queen Street, Brisbane QLD 4000",
                "timezone": "Australia/Brisbane",
                "status": "open",
                "manager": "Emma Thompson",
            },
        }

        # Products
        self.data["products"] = {
            "KB-ERGO-PRO": {
                "sku": "KB-ERGO-PRO",
                "name": "Ergonomic Keyboard Pro",
                "price": 149.99,
                "category": "keyboards",
                "description": "Premium ergonomic keyboard with split design",
                "stock": {
                    "store_sydney": 25,
                    "store_melbourne": 18,
                    "store_brisbane": 12,
                },
            },
            "MS-WL-ERGO": {
                "sku": "MS-WL-ERGO",
                "name": "Wireless Ergonomic Mouse",
                "price": 79.99,
                "category": "mice",
                "description": "Vertical wireless mouse for comfort",
                "stock": {
                    "store_sydney": 45,
                    "store_melbourne": 30,
                    "store_brisbane": 22,
                },
            },
            "MON-27-4K": {
                "sku": "MON-27-4K",
                "name": "27-inch 4K Monitor",
                "price": 499.99,
                "category": "monitors",
                "description": "Ultra-sharp 4K display with USB-C",
                "stock": {
                    "store_sydney": 8,
                    "store_melbourne": 5,
                    "store_brisbane": 3,
                },
            },
            "MON-24-HD": {
                "sku": "MON-24-HD",
                "name": "24-inch HD Monitor",
                "price": 249.99,
                "category": "monitors",
                "description": "Budget-friendly HD monitor",
                "stock": {
                    "store_sydney": 35,
                    "store_melbourne": 28,
                    "store_brisbane": 20,
                },
            },
            "HUB-USB-7": {
                "sku": "HUB-USB-7",
                "name": "7-Port USB Hub",
                "price": 59.99,
                "category": "accessories",
                "description": "Powered USB 3.0 hub with 7 ports",
                "stock": {
                    "store_sydney": 60,
                    "store_melbourne": 45,
                    "store_brisbane": 38,
                },
            },
            "CBL-HDMI-2M": {
                "sku": "CBL-HDMI-2M",
                "name": "HDMI Cable 2m",
                "price": 19.99,
                "category": "cables",
                "description": "High-speed HDMI 2.1 cable",
                "stock": {
                    "store_sydney": 100,
                    "store_melbourne": 85,
                    "store_brisbane": 70,
                },
            },
            "CBL-USBC-1M": {
                "sku": "CBL-USBC-1M",
                "name": "USB-C Cable 1m",
                "price": 14.99,
                "category": "cables",
                "description": "USB-C to USB-C charging cable",
                "stock": {
                    "store_sydney": 120,
                    "store_melbourne": 95,
                    "store_brisbane": 80,
                },
            },
            "DP-USB-C": {
                "sku": "DP-USB-C",
                "name": "USB-C Docking Station",
                "price": 199.99,
                "category": "accessories",
                "description": "13-in-1 docking station",
                "stock": {
                    "store_sydney": 15,
                    "store_melbourne": 12,
                    "store_brisbane": 8,
                },
            },
        }

    async def get(self, path: str) -> Any:
        """Get data at path."""
        parts = path.strip("/").split("/")
        data = self.data

        for part in parts:
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                return None

        return data

    async def set(self, path: str, value: Any):
        """Set data at path."""
        parts = path.strip("/").split("/")
        data = self.data

        for part in parts[:-1]:
            if part not in data:
                data[part] = {}
            data = data[part]

        data[parts[-1]] = value

        # Notify listeners
        await self._notify_listeners(path, value)

    async def push(self, path: str, value: Any) -> str:
        """Push new item to list, returns key."""
        key = f"item_{uuid.uuid4().hex[:8]}"
        await self.set(f"{path}/{key}", value)
        return key

    async def _notify_listeners(self, path: str, value: Any):
        """Notify listeners of data change."""
        for listener_path, callbacks in self.listeners.items():
            if path.startswith(listener_path):
                for callback in callbacks:
                    await callback(path, value)

    def on(self, path: str, callback):
        """Register listener for path."""
        if path not in self.listeners:
            self.listeners[path] = []
        self.listeners[path].append(callback)


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATED CLOUD VECTOR DB
# ══════════════════════════════════════════════════════════════════════════════


class SimulatedVectorDB:
    """
    Simulated cloud vector database (Pinecone-like).

    In production, use actual Pinecone, Weaviate, or Qdrant.
    """

    def __init__(self, index_name: str = "retail-products"):
        self.index_name = index_name
        self.vectors: Dict[str, Dict] = {}
        self._init_product_vectors()

    def _init_product_vectors(self):
        """Initialize product vectors for demo."""
        # Simulated embeddings (in production, use actual embeddings)
        products = [
            ("KB-ERGO-PRO", "ergonomic keyboard split design typing comfort"),
            ("MS-WL-ERGO", "wireless mouse vertical ergonomic wrist comfort"),
            ("MON-27-4K", "monitor 4k display uhd sharp professional"),
            ("MON-24-HD", "monitor hd display budget affordable"),
            ("HUB-USB-7", "usb hub ports connect devices powered"),
            ("CBL-HDMI-2M", "hdmi cable video display connection"),
            ("CBL-USBC-1M", "usb c cable charging power data"),
            ("DP-USB-C", "docking station laptop hub ports"),
        ]

        for sku, keywords in products:
            self.vectors[sku] = {
                "id": sku,
                "keywords": keywords.split(),
                "metadata": {"sku": sku},
            }

    async def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        """Query vectors by similarity (simulated)."""
        query_words = query_text.lower().split()

        results = []
        for vec_id, vec_data in self.vectors.items():
            # Simulated similarity based on keyword overlap
            keywords = vec_data["keywords"]
            overlap = len(set(query_words) & set(keywords))

            if overlap > 0:
                results.append(
                    {
                        "id": vec_id,
                        "score": overlap / len(query_words),
                        "metadata": vec_data["metadata"],
                    }
                )

        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


# ══════════════════════════════════════════════════════════════════════════════
# RETAIL CHAT SESSION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ChatSession:
    """A customer chat session."""

    session_id: str
    store_id: str
    device_type: str  # web, mobile, kiosk
    started_at: str
    messages: list[dict] = field(default_factory=list)
    customer_name: Optional[str] = None
    current_intent: Optional[str] = None


class RetailChatManager:
    """
    Manages retail chat sessions across all stores.

    Real-time sync ensures all devices see same data.
    """

    def __init__(self, firebase: SimulatedFirebase, vector_db: SimulatedVectorDB):
        self.firebase = firebase
        self.vector_db = vector_db
        self.active_sessions: Dict[str, ChatSession] = {}

    async def create_session(
        self, store_id: str, device_type: str = "web"
    ) -> ChatSession:
        """Create new chat session."""
        session_id = f"chat_{uuid.uuid4().hex[:12]}"

        session = ChatSession(
            session_id=session_id,
            store_id=store_id,
            device_type=device_type,
            started_at=datetime.now().isoformat(),
        )

        self.active_sessions[session_id] = session

        # Sync to Firebase
        await self.firebase.set(
            f"chats/{store_id}/{session_id}",
            {
                "session_id": session_id,
                "store_id": store_id,
                "device_type": device_type,
                "started_at": session.started_at,
                "status": "active",
            },
        )

        return session

    async def send_message(
        self, session_id: str, message: str, role: str = "user"
    ) -> dict:
        """Send message and get response."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Add user message
        user_msg = {
            "role": role,
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
        session.messages.append(user_msg)

        # Generate response
        response = await self._generate_response(session, message)

        # Add assistant message
        assistant_msg = {
            "role": "assistant",
            "content": response["answer"],
            "timestamp": datetime.now().isoformat(),
            "products": response.get("products", []),
        }
        session.messages.append(assistant_msg)

        # Sync to Firebase
        await self.firebase.push(
            f"chats/{session.store_id}/{session_id}/messages", assistant_msg
        )

        return response

    async def _generate_response(self, session: ChatSession, message: str) -> dict:
        """Generate response using cloud LLM and RAG."""
        msg_lower = message.lower()
        store = await self.firebase.get(f"stores/{session.store_id}")

        # Product search
        if any(
            kw in msg_lower for kw in ["looking for", "need", "want", "find", "search"]
        ):
            # Vector search
            results = await self.vector_db.query(message, top_k=3)

            if results:
                products = []
                for result in results:
                    product = await self.firebase.get(f"products/{result['id']}")
                    if product:
                        stock = product["stock"].get(session.store_id, 0)
                        products.append(
                            {
                                "sku": product["sku"],
                                "name": product["name"],
                                "price": product["price"],
                                "stock": stock,
                                "available": stock > 0,
                            }
                        )

                return {
                    "answer": self._format_product_results(products, store),
                    "products": products,
                    "intent": "product_search",
                }

        # Stock check
        if any(
            kw in msg_lower for kw in ["stock", "available", "in stock", "have any"]
        ):
            results = await self.vector_db.query(message, top_k=1)

            if results:
                product = await self.firebase.get(f"products/{results[0]['id']}")
                if product:
                    stock = product["stock"].get(session.store_id, 0)
                    return {
                        "answer": f"**{product['name']}** at {store['name']}:\n\n"
                        f"• Stock: {stock} units\n"
                        f"• Price: ${product['price']:.2f}\n"
                        f"• {'✅ In stock!' if stock > 0 else '❌ Out of stock'}",
                        "products": [{"sku": product["sku"], "stock": stock}],
                        "intent": "stock_check",
                    }

        # Store info
        if any(
            kw in msg_lower for kw in ["store", "location", "address", "hours", "open"]
        ):
            return {
                "answer": f"**{store['name']}**\n\n"
                f"📍 {store['address']}\n"
                f"🕐 Status: {store['status'].title()}\n"
                f"👤 Manager: {store['manager']}",
                "intent": "store_info",
            }

        # Price question
        if any(kw in msg_lower for kw in ["price", "cost", "how much"]):
            results = await self.vector_db.query(message, top_k=1)

            if results:
                product = await self.firebase.get(f"products/{results[0]['id']}")
                if product:
                    return {
                        "answer": f"**{product['name']}** is ${product['price']:.2f}",
                        "products": [
                            {"sku": product["sku"], "price": product["price"]}
                        ],
                        "intent": "price_check",
                    }

        # Default welcome/help
        return {
            "answer": f"Welcome to {store['name']}! 👋\n\n"
            f"I can help you with:\n"
            f"• 🔍 Finding products\n"
            f"• 📦 Checking stock\n"
            f"• 💰 Price information\n"
            f"• 📍 Store details\n\n"
            f"What would you like to know?",
            "intent": "greeting",
        }

    def _format_product_results(self, products: list[dict], store: dict) -> str:
        """Format product search results."""
        if not products:
            return "I couldn't find any matching products. Try a different search term."

        lines = [f"Found {len(products)} products at {store['name']}:\n"]

        for p in products:
            status = "✅ In stock" if p["available"] else "❌ Out of stock"
            lines.append(
                f"• **{p['name']}** (SKU: {p['sku']})\n"
                f"  💰 ${p['price']:.2f} | 📦 {p['stock']} units | {status}"
            )

        return "\n".join(lines)

    async def get_analytics(self, store_id: str = None) -> dict:
        """Get chat analytics."""
        total_sessions = len(self.active_sessions)

        if store_id:
            sessions = [
                s for s in self.active_sessions.values() if s.store_id == store_id
            ]
        else:
            sessions = list(self.active_sessions.values())

        total_messages = sum(len(s.messages) for s in sessions)

        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "avg_messages_per_session": (
                total_messages / len(sessions) if sessions else 0
            ),
            "device_breakdown": self._get_device_breakdown(sessions),
        }

    def _get_device_breakdown(self, sessions: list[ChatSession]) -> dict:
        """Get breakdown by device type."""
        breakdown = {"web": 0, "mobile": 0, "kiosk": 0}
        for session in sessions:
            breakdown[session.device_type] = breakdown.get(session.device_type, 0) + 1
        return breakdown


# ══════════════════════════════════════════════════════════════════════════════
# SERVERLESS-READY HANDLER
# ══════════════════════════════════════════════════════════════════════════════


class ServerlessHandler:
    """
    Serverless function handler.

    Stateless design - each request is independent.
    State stored in Firebase/cloud services.

    Deploy to:
    - AWS Lambda
    - Google Cloud Functions
    - Azure Functions
    - Vercel Edge Functions
    """

    def __init__(self):
        self.firebase = SimulatedFirebase()
        self.vector_db = SimulatedVectorDB()
        self.chat_manager = RetailChatManager(self.firebase, self.vector_db)

    async def handle(self, event: dict) -> dict:
        """
        Handle incoming request.

        Expected event format:
        {
            "action": "chat|create_session|analytics",
            "store_id": "store_sydney",
            "session_id": "chat_xxx" (for chat),
            "message": "..." (for chat),
        }
        """
        action = event.get("action", "chat")

        if action == "create_session":
            store_id = event.get("store_id", "store_sydney")
            device = event.get("device_type", "web")
            session = await self.chat_manager.create_session(store_id, device)
            return {
                "status": "success",
                "session_id": session.session_id,
                "store": store_id,
            }

        elif action == "chat":
            session_id = event.get("session_id")
            message = event.get("message", "")

            if not session_id:
                return {"status": "error", "message": "session_id required"}

            response = await self.chat_manager.send_message(session_id, message)
            return {
                "status": "success",
                **response,
            }

        elif action == "analytics":
            store_id = event.get("store_id")
            analytics = await self.chat_manager.get_analytics(store_id)
            return {
                "status": "success",
                **analytics,
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}


# ══════════════════════════════════════════════════════════════════════════════
# TRAFFIC SIMULATOR
# ══════════════════════════════════════════════════════════════════════════════


async def simulate_traffic(handler: ServerlessHandler, duration_seconds: int = 30):
    """Simulate multi-location retail traffic."""
    print("🔄 Simulating multi-location traffic...")
    print("-" * 40)

    stores = ["store_sydney", "store_melbourne", "store_brisbane"]
    devices = ["web", "mobile", "kiosk"]

    sample_queries = [
        "Looking for a keyboard",
        "Do you have any monitors in stock?",
        "What's the price of the USB hub?",
        "Where is your store located?",
        "I need a USB-C cable",
        "Looking for ergonomic mouse",
        "What monitors do you have?",
        "Do you have 4K displays?",
    ]

    sessions = {}
    requests = 0
    start_time = datetime.now()

    while (datetime.now() - start_time).seconds < duration_seconds:
        # Random store and device
        store = random.choice(stores)
        device = random.choice(devices)

        # Create or reuse session
        session_key = f"{store}_{device}"

        if session_key not in sessions or random.random() > 0.7:
            # New session
            result = await handler.handle(
                {
                    "action": "create_session",
                    "store_id": store,
                    "device_type": device,
                }
            )
            sessions[session_key] = result["session_id"]
            requests += 1
            print(f"📱 New session: {store} ({device})")

        # Send message
        query = random.choice(sample_queries)
        result = await handler.handle(
            {
                "action": "chat",
                "session_id": sessions[session_key],
                "message": query,
            }
        )
        requests += 1

        if result.get("status") == "success":
            intent = result.get("intent", "unknown")
            print(f"💬 {store}: {query[:30]}... → {intent}")

        await asyncio.sleep(random.uniform(0.5, 2.0))

    # Get final analytics
    analytics = await handler.handle({"action": "analytics"})

    print()
    print("📊 SIMULATION RESULTS")
    print("-" * 40)
    print(f"  Duration: {duration_seconds} seconds")
    print(f"  Total requests: {requests}")
    print(f"  Requests/sec: {requests / duration_seconds:.1f}")
    print(f"  Sessions created: {analytics['total_sessions']}")
    print(f"  Messages exchanged: {analytics['total_messages']}")
    print(f"  Device breakdown: {analytics['device_breakdown']}")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def run_demo():
    """Run demonstration of cloud-native deployment."""
    print("=" * 70)
    print("☁️ CLOUD NATIVE DEPLOYMENT")
    print("   Multi-Location Retail Chat")
    print("=" * 70)
    print()

    # Initialize handler
    handler = ServerlessHandler()

    # Show architecture
    print("📐 ARCHITECTURE")
    print("-" * 40)
    print("  LLM: Cloud (OpenAI/Anthropic)")
    print("  Vector DB: Pinecone (simulated)")
    print("  Realtime: Firebase (simulated)")
    print("  Storage: GCS (simulated)")
    print()

    # List stores
    print("🏪 STORES")
    print("-" * 40)
    stores = await handler.firebase.get("stores")
    for store_id, store in stores.items():
        print(f"  • {store['name']} ({store_id})")
        print(f"    📍 {store['address']}")
    print()

    # List products
    print("📦 PRODUCTS")
    print("-" * 40)
    products = await handler.firebase.get("products")
    for sku, product in list(products.items())[:5]:
        print(f"  • {product['name']} - ${product['price']:.2f}")
    print(f"  ... and {len(products) - 5} more")
    print()

    # Demo chat session
    print("💬 DEMO CHAT SESSION")
    print("-" * 40)

    # Create session
    result = await handler.handle(
        {
            "action": "create_session",
            "store_id": "store_sydney",
            "device_type": "web",
        }
    )
    session_id = result["session_id"]
    print(f"  Created session: {session_id}")
    print()

    # Demo queries
    queries = [
        "Hi there!",
        "I'm looking for a keyboard",
        "What monitors do you have?",
        "Is the 27-inch 4K monitor in stock?",
        "Where is your store located?",
    ]

    for query in queries:
        print(f"👤 Customer: {query}")
        response = await handler.handle(
            {
                "action": "chat",
                "session_id": session_id,
                "message": query,
            }
        )
        print(f"🤖 Assistant: {response['answer']}")
        print()

    # Show analytics
    print("📊 ANALYTICS")
    print("-" * 40)
    analytics = await handler.handle({"action": "analytics"})
    print(f"  Sessions: {analytics['total_sessions']}")
    print(f"  Messages: {analytics['total_messages']}")


async def run_interactive():
    """Run interactive retail chat."""
    print("=" * 70)
    print("☁️ CLOUD NATIVE RETAIL CHAT - INTERACTIVE")
    print("=" * 70)
    print()

    handler = ServerlessHandler()

    # Show stores
    stores = await handler.firebase.get("stores")
    print("Available stores:")
    for i, (store_id, store) in enumerate(stores.items(), 1):
        print(f"  {i}. {store['name']}")

    # Select store
    store_ids = list(stores.keys())
    store_choice = input("\nSelect store (1-3) or press Enter for Sydney: ").strip()

    if store_choice.isdigit() and 1 <= int(store_choice) <= len(store_ids):
        store_id = store_ids[int(store_choice) - 1]
    else:
        store_id = "store_sydney"

    # Create session
    result = await handler.handle(
        {
            "action": "create_session",
            "store_id": store_id,
            "device_type": "web",
        }
    )
    session_id = result["session_id"]

    store = stores[store_id]
    print(f"\n🏪 Connected to: {store['name']}")
    print("Commands: 'quit', 'analytics', 'products'\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("Thanks for shopping with us! 👋")
                break

            if user_input.lower() == "analytics":
                analytics = await handler.handle(
                    {
                        "action": "analytics",
                        "store_id": store_id,
                    }
                )
                print(f"\n📊 Analytics: {json.dumps(analytics, indent=2)}\n")
                continue

            if user_input.lower() == "products":
                products = await handler.firebase.get("products")
                print("\n📦 Products:")
                for sku, p in products.items():
                    stock = p["stock"].get(store_id, 0)
                    print(f"  • {p['name']} (${p['price']:.2f}) - {stock} in stock")
                print()
                continue

            response = await handler.handle(
                {
                    "action": "chat",
                    "session_id": session_id,
                    "message": user_input,
                }
            )

            print(f"\n🤖 {response['answer']}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloud Native Deployment Example")
    parser.add_argument("--demo", action="store_true", help="Run demonstration mode")
    parser.add_argument(
        "--interactive", action="store_true", help="Run interactive mode"
    )
    parser.add_argument(
        "--simulate-traffic",
        action="store_true",
        help="Simulate multi-location traffic",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Traffic simulation duration in seconds",
    )

    args = parser.parse_args()

    if args.simulate_traffic:
        handler = ServerlessHandler()
        asyncio.run(simulate_traffic(handler, args.duration))
    elif args.interactive:
        asyncio.run(run_interactive())
    else:
        asyncio.run(run_demo())
