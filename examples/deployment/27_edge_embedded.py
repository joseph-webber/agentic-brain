#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 27: Edge/Embedded Deployment
======================================

Minimal footprint for IoT, kiosks, and embedded devices.
Runs on Raspberry Pi, industrial PCs, and constrained hardware.

This deployment pattern is ideal for:
- Retail kiosks and self-service terminals
- Industrial IoT devices
- Point-of-sale (POS) systems
- Digital signage with voice interaction
- Warehouse handheld devices
- Vehicle infotainment systems

Architecture:
    ┌────────────────────────────────────────────────────────────────┐
    │                    EDGE DEPLOYMENT                             │
    │                                                                │
    │  ┌──────────────────────────────────────────────────────────┐ │
    │  │                  EDGE DEVICE                              │ │
    │  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │ │
    │  │  │ Tiny LLM   │  │  SQLite    │  │  Application       │ │ │
    │  │  │ (1-3B)     │  │  (Memory)  │  │  (Python/Rust)     │ │ │
    │  │  └────────────┘  └────────────┘  └────────────────────┘ │ │
    │  │       │               │                   │              │ │
    │  │       └───────────────┴───────────────────┘              │ │
    │  │                    Local Bus                              │ │
    │  └──────────────────────────┬───────────────────────────────┘ │
    │                             │                                  │
    │                    ┌────────┴────────┐                        │
    │                    │  WiFi/Ethernet  │                        │
    │                    │  (When Online)  │                        │
    │                    └────────┬────────┘                        │
    │                             │                                  │
    │  ┌──────────────────────────┴───────────────────────────────┐ │
    │  │                  CLOUD (Optional)                        │ │
    │  │  • Analytics upload (batched)                            │ │
    │  │  • Config updates                                        │ │
    │  │  • Model updates (OTA)                                   │ │
    │  └──────────────────────────────────────────────────────────┘ │
    └────────────────────────────────────────────────────────────────┘

Hardware Requirements:
    - Minimum: Raspberry Pi 4 (4GB RAM)
    - Recommended: Pi 5 (8GB) or Intel NUC
    - Storage: 8GB+ SD card or eMMC
    - Network: WiFi or Ethernet (for sync)

Supported Models (Tiny/Efficient):
    - llama3.2:1b (smallest, fastest)
    - llama3.2:3b (better quality)
    - phi-2 (Microsoft, 2.7B)
    - gemma:2b (Google)
    - qwen2:0.5b (fastest for Chinese)

Optimizations:
    - Quantized models (Q4_K_M or Q4_K_S)
    - Response caching for common queries
    - Batched sync to reduce network usage
    - Power-aware scheduling

Demo Scenario:
    Retail Kiosk / POS Assistant.
    Helps customers find products, check prices,
    and provides store information - works offline.

Usage:
    python examples/27_edge_embedded.py
    python examples/27_edge_embedded.py --demo
    python examples/27_edge_embedded.py --interactive
    python examples/27_edge_embedded.py --benchmark
    python examples/27_edge_embedded.py --kiosk-mode

Requirements:
    pip install agentic-brain
    ollama pull llama3.2:1b  # Smallest model
"""

import asyncio
import os
import json
import time
import sqlite3
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any
from pathlib import Path
import argparse

# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE PROFILES
# ══════════════════════════════════════════════════════════════════════════════


class DeviceType(Enum):
    """Supported edge device types."""

    RASPBERRY_PI_4 = "rpi4"
    RASPBERRY_PI_5 = "rpi5"
    JETSON_NANO = "jetson_nano"
    INTEL_NUC = "intel_nuc"
    GENERIC_ARM = "arm"
    GENERIC_X86 = "x86"


@dataclass
class DeviceProfile:
    """Device hardware profile for optimization."""

    device_type: DeviceType
    ram_mb: int
    cpu_cores: int
    has_gpu: bool = False
    has_npu: bool = False
    recommended_model: str = "llama3.2:1b"
    max_batch_size: int = 1
    response_cache_size: int = 100


# Device-specific configurations
DEVICE_PROFILES = {
    DeviceType.RASPBERRY_PI_4: DeviceProfile(
        device_type=DeviceType.RASPBERRY_PI_4,
        ram_mb=4096,
        cpu_cores=4,
        recommended_model="llama3.2:1b",
        max_batch_size=1,
        response_cache_size=50,
    ),
    DeviceType.RASPBERRY_PI_5: DeviceProfile(
        device_type=DeviceType.RASPBERRY_PI_5,
        ram_mb=8192,
        cpu_cores=4,
        recommended_model="llama3.2:3b",
        max_batch_size=2,
        response_cache_size=100,
    ),
    DeviceType.JETSON_NANO: DeviceProfile(
        device_type=DeviceType.JETSON_NANO,
        ram_mb=4096,
        cpu_cores=4,
        has_gpu=True,
        recommended_model="llama3.2:1b",
        max_batch_size=4,
        response_cache_size=100,
    ),
    DeviceType.INTEL_NUC: DeviceProfile(
        device_type=DeviceType.INTEL_NUC,
        ram_mb=16384,
        cpu_cores=8,
        recommended_model="llama3.2:3b",
        max_batch_size=4,
        response_cache_size=200,
    ),
}


def detect_device() -> DeviceProfile:
    """Auto-detect device type and return profile."""
    import platform
    import subprocess

    machine = platform.machine().lower()

    # Try to detect Raspberry Pi
    try:
        with open("/proc/device-tree/model") as f:
            model = f.read()
            if "Raspberry Pi 5" in model:
                return DEVICE_PROFILES[DeviceType.RASPBERRY_PI_5]
            elif "Raspberry Pi 4" in model:
                return DEVICE_PROFILES[DeviceType.RASPBERRY_PI_4]
    except FileNotFoundError:
        pass

    # Try to detect Jetson
    try:
        result = subprocess.run(
            ["cat", "/etc/nv_tegra_release"], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return DEVICE_PROFILES[DeviceType.JETSON_NANO]
    except Exception:
        pass

    # Default based on architecture
    if "arm" in machine or "aarch64" in machine:
        return DeviceProfile(
            device_type=DeviceType.GENERIC_ARM,
            ram_mb=4096,
            cpu_cores=4,
            recommended_model="llama3.2:1b",
            max_batch_size=1,
            response_cache_size=50,
        )

    return DeviceProfile(
        device_type=DeviceType.GENERIC_X86,
        ram_mb=8192,
        cpu_cores=4,
        recommended_model="llama3.2:3b",
        max_batch_size=2,
        response_cache_size=100,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LIGHTWEIGHT STORAGE (SQLite)
# ══════════════════════════════════════════════════════════════════════════════


class EdgeStorage:
    """
    Lightweight SQLite storage for edge devices.

    Features:
    - In-memory option for fastest operation
    - File-based for persistence
    - Response caching for common queries
    - Batched sync support
    """

    def __init__(self, db_path: str = ":memory:", cache_size: int = 100):
        self.db_path = db_path
        self.cache_size = cache_size
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()
        self._init_sample_data()

    def _init_schema(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()

        # Products table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                description TEXT,
                stock INTEGER DEFAULT 0,
                location TEXT
            )
        """
        )

        # Response cache (for common queries)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS response_cache (
                query_hash TEXT PRIMARY KEY,
                query TEXT,
                response TEXT,
                created_at TEXT,
                hit_count INTEGER DEFAULT 0
            )
        """
        )

        # Analytics (for batched upload)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                data TEXT,
                timestamp TEXT,
                synced INTEGER DEFAULT 0
            )
        """
        )

        # Create indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_synced ON analytics(synced)"
        )

        self.conn.commit()

    def _init_sample_data(self):
        """Initialize with sample retail data."""
        products = [
            (
                "KB-STD-USB",
                "Standard USB Keyboard",
                29.99,
                "keyboards",
                "Basic USB keyboard with quiet keys",
                50,
                "A1-01",
            ),
            (
                "KB-ERGO-WL",
                "Ergonomic Wireless Keyboard",
                89.99,
                "keyboards",
                "Split design wireless keyboard",
                25,
                "A1-02",
            ),
            (
                "KB-MECH-RGB",
                "Mechanical RGB Keyboard",
                129.99,
                "keyboards",
                "Gaming keyboard with RGB lighting",
                15,
                "A1-03",
            ),
            (
                "MS-STD-USB",
                "Standard USB Mouse",
                19.99,
                "mice",
                "Basic optical mouse",
                75,
                "A2-01",
            ),
            (
                "MS-ERGO-WL",
                "Ergonomic Wireless Mouse",
                49.99,
                "mice",
                "Vertical wireless mouse",
                30,
                "A2-02",
            ),
            (
                "MS-GAMING",
                "Gaming Mouse RGB",
                69.99,
                "mice",
                "High DPI gaming mouse",
                20,
                "A2-03",
            ),
            (
                "MON-24-HD",
                "24-inch HD Monitor",
                199.99,
                "monitors",
                "1080p LED monitor",
                12,
                "B1-01",
            ),
            (
                "MON-27-4K",
                "27-inch 4K Monitor",
                449.99,
                "monitors",
                "4K UHD display with USB-C",
                8,
                "B1-02",
            ),
            (
                "MON-32-CRV",
                "32-inch Curved Monitor",
                399.99,
                "monitors",
                "Curved display for immersive viewing",
                5,
                "B1-03",
            ),
            (
                "HUB-USB4",
                "4-Port USB Hub",
                24.99,
                "accessories",
                "USB 3.0 hub",
                100,
                "C1-01",
            ),
            (
                "HUB-USB7",
                "7-Port USB Hub",
                49.99,
                "accessories",
                "Powered USB hub with 7 ports",
                60,
                "C1-02",
            ),
            (
                "CBL-HDMI",
                "HDMI Cable 2m",
                14.99,
                "cables",
                "High-speed HDMI cable",
                150,
                "C2-01",
            ),
            (
                "CBL-USBC",
                "USB-C Cable 1m",
                12.99,
                "cables",
                "USB-C charging cable",
                200,
                "C2-02",
            ),
            (
                "CBL-DP",
                "DisplayPort Cable",
                19.99,
                "cables",
                "DisplayPort 1.4 cable",
                80,
                "C2-03",
            ),
        ]

        cursor = self.conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO products 
            (sku, name, price, category, description, stock, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            products,
        )
        self.conn.commit()

    def search_products(self, query: str) -> list[dict]:
        """Search products by keyword."""
        cursor = self.conn.cursor()
        search_term = f"%{query}%"

        cursor.execute(
            """
            SELECT sku, name, price, category, stock, location
            FROM products
            WHERE name LIKE ? OR category LIKE ? OR description LIKE ?
            LIMIT 10
        """,
            (search_term, search_term, search_term),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "sku": row[0],
                    "name": row[1],
                    "price": row[2],
                    "category": row[3],
                    "stock": row[4],
                    "location": row[5],
                }
            )
        return results

    def get_product(self, sku: str) -> Optional[dict]:
        """Get product by SKU."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT sku, name, price, category, description, stock, location
            FROM products WHERE sku = ?
        """,
            (sku,),
        )

        row = cursor.fetchone()
        if row:
            return {
                "sku": row[0],
                "name": row[1],
                "price": row[2],
                "category": row[3],
                "description": row[4],
                "stock": row[5],
                "location": row[6],
            }
        return None

    def get_by_category(self, category: str) -> list[dict]:
        """Get all products in a category."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT sku, name, price, stock, location
            FROM products WHERE category = ?
        """,
            (category,),
        )

        return [
            {"sku": r[0], "name": r[1], "price": r[2], "stock": r[3], "location": r[4]}
            for r in cursor.fetchall()
        ]

    def cache_response(self, query: str, response: str):
        """Cache a response for future use."""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO response_cache
            (query_hash, query, response, created_at, hit_count)
            VALUES (?, ?, ?, ?, COALESCE(
                (SELECT hit_count FROM response_cache WHERE query_hash = ?), 0
            ))
        """,
            (query_hash, query, response, datetime.now().isoformat(), query_hash),
        )

        # Prune old entries if over limit
        cursor.execute(
            """
            DELETE FROM response_cache 
            WHERE query_hash NOT IN (
                SELECT query_hash FROM response_cache 
                ORDER BY hit_count DESC, created_at DESC 
                LIMIT ?
            )
        """,
            (self.cache_size,),
        )

        self.conn.commit()

    def get_cached_response(self, query: str) -> Optional[str]:
        """Get cached response if available."""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT response FROM response_cache WHERE query_hash = ?
        """,
            (query_hash,),
        )

        row = cursor.fetchone()
        if row:
            # Update hit count
            cursor.execute(
                """
                UPDATE response_cache 
                SET hit_count = hit_count + 1 
                WHERE query_hash = ?
            """,
                (query_hash,),
            )
            self.conn.commit()
            return row[0]
        return None

    def log_analytics(self, event_type: str, data: dict):
        """Log analytics event for batched sync."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO analytics (event_type, data, timestamp, synced)
            VALUES (?, ?, ?, 0)
        """,
            (event_type, json.dumps(data), datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_pending_analytics(self, limit: int = 100) -> list[dict]:
        """Get analytics events pending sync."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, event_type, data, timestamp
            FROM analytics WHERE synced = 0
            ORDER BY id LIMIT ?
        """,
            (limit,),
        )

        return [
            {
                "id": r[0],
                "event_type": r[1],
                "data": json.loads(r[2]),
                "timestamp": r[3],
            }
            for r in cursor.fetchall()
        ]

    def mark_analytics_synced(self, ids: list[int]):
        """Mark analytics as synced."""
        if not ids:
            return

        cursor = self.conn.cursor()
        placeholders = ",".join("?" * len(ids))
        cursor.execute(
            f"""
            UPDATE analytics SET synced = 1 WHERE id IN ({placeholders})
        """,
            ids,
        )
        self.conn.commit()

    def get_cache_stats(self) -> dict:
        """Get response cache statistics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*), SUM(hit_count) FROM response_cache")
        row = cursor.fetchone()

        return {
            "cached_responses": row[0] or 0,
            "total_hits": row[1] or 0,
            "cache_limit": self.cache_size,
        }


# ══════════════════════════════════════════════════════════════════════════════
# EDGE LLM WRAPPER
# ══════════════════════════════════════════════════════════════════════════════


class EdgeLLM:
    """
    Lightweight LLM wrapper for edge devices.

    Optimizations:
    - Response caching
    - Short context window
    - Streaming disabled (simpler)
    - Timeout protection
    """

    def __init__(
        self,
        model: str = "llama3.2:1b",
        timeout_seconds: int = 30,
        max_tokens: int = 256,
    ):
        self.model = model
        self.timeout = timeout_seconds
        self.max_tokens = max_tokens
        self.stats = {
            "queries": 0,
            "cache_hits": 0,
            "avg_latency_ms": 0,
        }

    async def generate(
        self, prompt: str, system: str = "", cached_response: Optional[str] = None
    ) -> str:
        """
        Generate response with edge optimizations.

        In production, calls Ollama API.
        This is simplified for demonstration.
        """
        start_time = time.time()
        self.stats["queries"] += 1

        # Use cache if available
        if cached_response:
            self.stats["cache_hits"] += 1
            return cached_response

        # Simulated LLM call (in production: call Ollama)
        # For demo, we return a simple response
        await asyncio.sleep(0.1)  # Simulate processing

        latency = (time.time() - start_time) * 1000
        self.stats["avg_latency_ms"] = (
            self.stats["avg_latency_ms"] * (self.stats["queries"] - 1) + latency
        ) / self.stats["queries"]

        return f"[LLM Response for: {prompt[:50]}...]"

    def get_stats(self) -> dict:
        """Get LLM statistics."""
        return {
            **self.stats,
            "cache_hit_rate": (
                self.stats["cache_hits"] / self.stats["queries"]
                if self.stats["queries"] > 0
                else 0
            ),
        }


# ══════════════════════════════════════════════════════════════════════════════
# KIOSK ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class KioskAssistant:
    """
    Kiosk/POS assistant optimized for edge deployment.

    Features:
    - Fast response via caching
    - Offline-first operation
    - Batched analytics upload
    - Simple, focused interactions
    """

    def __init__(
        self,
        storage: EdgeStorage,
        llm: EdgeLLM,
        device_profile: DeviceProfile,
        store_name: str = "Tech Store",
    ):
        self.storage = storage
        self.llm = llm
        self.profile = device_profile
        self.store_name = store_name
        self.session_start = datetime.now()
        self.queries_this_session = 0

    async def process_query(self, query: str) -> dict:
        """Process customer query."""
        self.queries_this_session += 1
        start_time = time.time()

        # Check cache first
        cached = self.storage.get_cached_response(query)
        if cached:
            response = json.loads(cached)
            response["from_cache"] = True
            self._log_query(query, response, cached=True)
            return response

        # Generate response
        response = await self._generate_response(query)
        response["from_cache"] = False

        # Cache the response
        self.storage.cache_response(query, json.dumps(response))

        # Log analytics
        latency_ms = (time.time() - start_time) * 1000
        response["latency_ms"] = round(latency_ms, 1)
        self._log_query(query, response, cached=False)

        return response

    async def _generate_response(self, query: str) -> dict:
        """Generate response for query."""
        q_lower = query.lower()

        # Product search
        if any(
            kw in q_lower
            for kw in ["looking for", "need", "want", "find", "search", "show me"]
        ):
            products = self.storage.search_products(query)

            if products:
                return {
                    "type": "product_list",
                    "message": self._format_products(products),
                    "products": products,
                }
            else:
                return {
                    "type": "no_results",
                    "message": "Sorry, I couldn't find products matching your search. "
                    "Try a different term or ask for help.",
                }

        # Price check
        if any(kw in q_lower for kw in ["price", "cost", "how much"]):
            products = self.storage.search_products(query)

            if products:
                p = products[0]
                return {
                    "type": "price",
                    "message": f"**{p['name']}** is **${p['price']:.2f}**\n\n"
                    f"📦 In stock: {p['stock']} units\n"
                    f"📍 Location: {p['location']}",
                    "product": p,
                }

        # Stock check
        if any(kw in q_lower for kw in ["stock", "available", "in stock", "have any"]):
            products = self.storage.search_products(query)

            if products:
                p = products[0]
                status = "✅ In stock" if p["stock"] > 0 else "❌ Out of stock"
                return {
                    "type": "stock",
                    "message": f"**{p['name']}**: {status}\n\n"
                    f"📦 Quantity: {p['stock']}\n"
                    f"📍 Find it at: {p['location']}",
                    "product": p,
                }

        # Location/where is
        if any(kw in q_lower for kw in ["where", "location", "find", "aisle"]):
            products = self.storage.search_products(query)

            if products:
                p = products[0]
                return {
                    "type": "location",
                    "message": f"**{p['name']}** is located at **{p['location']}**\n\n"
                    f"Head to Aisle {p['location'][0]}, "
                    f"Rack {p['location'][1]}, "
                    f"Shelf {p['location'][3:]}",
                    "product": p,
                }

        # Category listing
        categories = ["keyboards", "mice", "monitors", "accessories", "cables"]
        for cat in categories:
            if cat in q_lower or cat[:-1] in q_lower:  # "keyboard" or "keyboards"
                products = self.storage.get_by_category(cat)
                return {
                    "type": "category",
                    "message": f"**{cat.title()}** ({len(products)} items):\n\n"
                    + self._format_products(products),
                    "products": products,
                }

        # Default welcome
        return {
            "type": "welcome",
            "message": f"Welcome to **{self.store_name}**! 👋\n\n"
            f"I can help you:\n"
            f'• 🔍 Find products - "Show me keyboards"\n'
            f'• 💰 Check prices - "How much is the 4K monitor?"\n'
            f'• 📦 Check stock - "Is the USB hub available?"\n'
            f'• 📍 Find locations - "Where is the HDMI cable?"\n\n'
            f"What would you like to know?",
        }

    def _format_products(self, products: list[dict]) -> str:
        """Format product list for display."""
        if not products:
            return "No products found."

        lines = []
        for p in products[:5]:  # Limit to 5 for kiosk display
            status = "✅" if p["stock"] > 0 else "❌"
            lines.append(
                f"• **{p['name']}** - ${p['price']:.2f}\n"
                f"  {status} Stock: {p['stock']} | 📍 {p['location']}"
            )

        if len(products) > 5:
            lines.append(f"\n_...and {len(products) - 5} more_")

        return "\n".join(lines)

    def _log_query(self, query: str, response: dict, cached: bool):
        """Log query for analytics."""
        self.storage.log_analytics(
            "query",
            {
                "query": query[:100],
                "response_type": response.get("type"),
                "cached": cached,
                "session_query_num": self.queries_this_session,
            },
        )

    async def sync_analytics(self) -> dict:
        """Sync analytics to cloud (when online)."""
        pending = self.storage.get_pending_analytics(limit=100)

        if not pending:
            return {"synced": 0, "pending": 0}

        # Simulated cloud sync
        await asyncio.sleep(0.5)

        # Mark as synced
        ids = [e["id"] for e in pending]
        self.storage.mark_analytics_synced(ids)

        return {
            "synced": len(pending),
            "pending": len(self.storage.get_pending_analytics()),
        }

    def get_stats(self) -> dict:
        """Get kiosk statistics."""
        cache_stats = self.storage.get_cache_stats()
        llm_stats = self.llm.get_stats()

        return {
            "session_duration_minutes": (datetime.now() - self.session_start).seconds
            / 60,
            "queries_this_session": self.queries_this_session,
            "device": self.profile.device_type.value,
            "model": self.llm.model,
            "cache": cache_stats,
            "llm": llm_stats,
        }


# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ══════════════════════════════════════════════════════════════════════════════


async def run_benchmark(assistant: KioskAssistant, iterations: int = 50):
    """Run performance benchmark."""
    print("⏱️ PERFORMANCE BENCHMARK")
    print("-" * 40)

    test_queries = [
        "Show me keyboards",
        "How much is the 4K monitor?",
        "Is the USB hub in stock?",
        "Where can I find the HDMI cable?",
        "I need a mouse",
        "What monitors do you have?",
        "Price of ergonomic keyboard",
        "Show me all cables",
    ]

    # Warm up
    print("Warming up cache...")
    for q in test_queries:
        await assistant.process_query(q)

    # Benchmark cached queries
    print(f"\nBenchmarking {iterations} cached queries...")
    cached_times = []

    for i in range(iterations):
        query = test_queries[i % len(test_queries)]
        start = time.time()
        await assistant.process_query(query)
        cached_times.append((time.time() - start) * 1000)

    # Benchmark fresh queries
    print(f"Benchmarking {iterations} fresh queries...")

    # Clear cache
    assistant.storage.conn.execute("DELETE FROM response_cache")
    assistant.storage.conn.commit()

    fresh_times = []
    for i in range(iterations):
        query = test_queries[i % len(test_queries)]
        start = time.time()
        await assistant.process_query(query)
        fresh_times.append((time.time() - start) * 1000)

    # Results
    print("\n📊 RESULTS")
    print("-" * 40)
    print(f"  Cached queries:")
    print(f"    Average: {sum(cached_times)/len(cached_times):.2f} ms")
    print(f"    Min: {min(cached_times):.2f} ms")
    print(f"    Max: {max(cached_times):.2f} ms")
    print(f"    P95: {sorted(cached_times)[int(len(cached_times)*0.95)]:.2f} ms")

    print(f"\n  Fresh queries (no cache):")
    print(f"    Average: {sum(fresh_times)/len(fresh_times):.2f} ms")
    print(f"    Min: {min(fresh_times):.2f} ms")
    print(f"    Max: {max(fresh_times):.2f} ms")
    print(f"    P95: {sorted(fresh_times)[int(len(fresh_times)*0.95)]:.2f} ms")

    speedup = (sum(fresh_times) / len(fresh_times)) / (
        sum(cached_times) / len(cached_times)
    )
    print(f"\n  Cache speedup: {speedup:.1f}x faster")


# ══════════════════════════════════════════════════════════════════════════════
# KIOSK MODE
# ══════════════════════════════════════════════════════════════════════════════


async def run_kiosk_mode(assistant: KioskAssistant):
    """Run in fullscreen kiosk mode."""
    print("\033[2J\033[H")  # Clear screen

    print("=" * 60)
    print("   🖥️  SELF-SERVICE KIOSK")
    print(f"   {assistant.store_name}")
    print("=" * 60)
    print()
    print("Touch the screen or type your question below.")
    print("Examples: 'keyboards', 'price of monitor', 'where is USB hub'")
    print()
    print("-" * 60)

    idle_timeout = 60  # seconds
    last_activity = time.time()

    while True:
        try:
            # Show idle message after timeout
            if time.time() - last_activity > idle_timeout:
                print("\n💤 Tap screen to start...")

            user_input = input("\n🛒 You: ").strip()
            last_activity = time.time()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "admin"):
                print("\n[Kiosk mode ended]")
                break

            response = await assistant.process_query(user_input)

            # Large, clear display for kiosk
            print("\n" + "─" * 60)
            print(response["message"])
            print("─" * 60)

            if response.get("from_cache"):
                print("⚡ [instant response]")
            else:
                print(f"⏱️ [{response.get('latency_ms', 0):.0f}ms]")

        except KeyboardInterrupt:
            print("\n[Kiosk mode ended]")
            break


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def run_demo():
    """Run demonstration of edge deployment."""
    print("=" * 70)
    print("📱 EDGE/EMBEDDED DEPLOYMENT")
    print("   Retail Kiosk Assistant")
    print("=" * 70)
    print()

    # Detect device
    print("🔍 DEVICE DETECTION")
    print("-" * 40)
    profile = detect_device()
    print(f"  Device: {profile.device_type.value}")
    print(f"  RAM: {profile.ram_mb} MB")
    print(f"  CPU Cores: {profile.cpu_cores}")
    print(f"  GPU: {'Yes' if profile.has_gpu else 'No'}")
    print(f"  Recommended Model: {profile.recommended_model}")
    print(f"  Cache Size: {profile.response_cache_size} responses")
    print()

    # Initialize components
    storage = EdgeStorage(":memory:", cache_size=profile.response_cache_size)
    llm = EdgeLLM(model=profile.recommended_model)
    assistant = KioskAssistant(storage, llm, profile, store_name="Tech Store Demo")

    print("📦 INVENTORY")
    print("-" * 40)
    products = storage.search_products("")  # Get all
    categories = {}
    for p in products:
        cat = p["category"]
        categories[cat] = categories.get(cat, 0) + 1

    for cat, count in categories.items():
        print(f"  • {cat}: {count} items")
    print()

    # Demo queries
    print("💬 DEMO QUERIES")
    print("-" * 40)

    queries = [
        "Hello!",
        "Show me keyboards",
        "How much is the 4K monitor?",
        "Is the USB hub in stock?",
        "Where can I find HDMI cables?",
        "Show me keyboards",  # Repeat to show cache
    ]

    for query in queries:
        print(f"\n👤 Customer: {query}")
        response = await assistant.process_query(query)

        cache_indicator = "⚡ CACHED" if response.get("from_cache") else "🔄 Generated"
        print(f"   [{cache_indicator}]")
        print(f"🤖 {response['message']}")

    # Show statistics
    print("\n" + "=" * 40)
    print("📊 STATISTICS")
    print("=" * 40)
    stats = assistant.get_stats()
    print(f"  Queries: {stats['queries_this_session']}")
    print(f"  Cache entries: {stats['cache']['cached_responses']}")
    print(f"  Cache hits: {stats['cache']['total_hits']}")
    print(f"  Cache hit rate: {stats['llm']['cache_hit_rate']:.1%}")


async def run_interactive():
    """Run interactive kiosk assistant."""
    print("=" * 70)
    print("📱 EDGE KIOSK ASSISTANT - INTERACTIVE")
    print("=" * 70)
    print()

    profile = detect_device()
    storage = EdgeStorage(":memory:", cache_size=profile.response_cache_size)
    llm = EdgeLLM(model=profile.recommended_model)
    assistant = KioskAssistant(storage, llm, profile, store_name="Demo Store")

    print(f"Device: {profile.device_type.value} | Model: {llm.model}")
    print("Commands: 'quit', 'stats', 'sync', 'cache'\n")

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
                print(f"\n📊 Stats: {json.dumps(stats, indent=2)}\n")
                continue

            if user_input.lower() == "sync":
                result = await assistant.sync_analytics()
                print(f"\n🔄 Sync: {result}\n")
                continue

            if user_input.lower() == "cache":
                cache_stats = storage.get_cache_stats()
                print(f"\n💾 Cache: {json.dumps(cache_stats, indent=2)}\n")
                continue

            response = await assistant.process_query(user_input)
            cache_indicator = "⚡" if response.get("from_cache") else "🔄"
            print(f"\n{cache_indicator} {response['message']}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edge/Embedded Deployment Example")
    parser.add_argument("--demo", action="store_true", help="Run demonstration mode")
    parser.add_argument(
        "--interactive", action="store_true", help="Run interactive mode"
    )
    parser.add_argument(
        "--benchmark", action="store_true", help="Run performance benchmark"
    )
    parser.add_argument(
        "--kiosk-mode", action="store_true", help="Run in kiosk mode (fullscreen)"
    )
    parser.add_argument(
        "--iterations", type=int, default=50, help="Benchmark iterations"
    )

    args = parser.parse_args()

    if args.benchmark:
        profile = detect_device()
        storage = EdgeStorage(":memory:", cache_size=profile.response_cache_size)
        llm = EdgeLLM(model=profile.recommended_model)
        assistant = KioskAssistant(storage, llm, profile)
        asyncio.run(run_benchmark(assistant, args.iterations))
    elif args.kiosk_mode:
        profile = detect_device()
        storage = EdgeStorage(":memory:", cache_size=profile.response_cache_size)
        llm = EdgeLLM(model=profile.recommended_model)
        assistant = KioskAssistant(
            storage, llm, profile, store_name="Self-Service Kiosk"
        )
        asyncio.run(run_kiosk_mode(assistant))
    elif args.interactive:
        asyncio.run(run_interactive())
    else:
        asyncio.run(run_demo())
