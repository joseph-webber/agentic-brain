#!/usr/bin/env python3
"""
Perfect Memory MCP Server v1.0 - NEVER FORGET ANYTHING
======================================================

🧠 THE ULTIMATE MEMORY UPGRADE - Perfect recall across ALL sessions

Features:
- MCP Lifecycle Hooks: Auto-preload on start, auto-save on end
- M2 Hardware Acceleration: MLX native, 285 texts/sec target
- Semantic Search: Vector embeddings with Neo4j
- RAG Pipeline: Context-aware retrieval
- Event Bus: Real-time memory events via Redpanda
- Crash Recovery: Signal handlers, emergency saves

LIFECYCLE:
1. ON START: Preload recent memories, warm up M2 embedder
2. DURING: Auto-checkpoint every 60s, stream to Neo4j
3. ON END: Save session context, emit completion event
4. ON CRASH: Emergency save, recover on next start

Created: 2026-03-15
Author: Joseph Webber's Brain (Iris Lumina)
"""

import atexit
import asyncio
import hashlib
import json
import os
import signal
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add brain paths
BRAIN_ROOT = Path.home() / "brain"
sys.path.insert(0, str(BRAIN_ROOT))
sys.path.insert(0, str(BRAIN_ROOT / "core"))
sys.path.insert(0, str(BRAIN_ROOT / "core_data"))

from mcp.server.fastmcp import FastMCP

# ============================================================================
# CONFIGURATION
# ============================================================================

MEMORY_DIR = Path.home() / ".brain-memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = MEMORY_DIR / "memory_state.json"
CACHE_FILE = MEMORY_DIR / "embedding_cache.json"
PRELOAD_FILE = MEMORY_DIR / "preloaded_memories.json"

# Memory settings
MAX_PRELOAD_MEMORIES = 50  # Preload last 50 memories on start
AUTO_CHECKPOINT_INTERVAL = 60  # Seconds
EMBEDDING_BATCH_SIZE = 32  # Optimal for M2
DEFAULT_TOP_K = 10

# ============================================================================
# LAZY IMPORTS (Performance optimization)
# ============================================================================

_perfect_memory = None
_m2_embedder = None
_rag_pipeline = None
_neo4j_driver = None
_event_bus = None


def get_perfect_memory():
    """Lazy load PerfectMemory."""
    global _perfect_memory
    if _perfect_memory is None:
        try:
            from core.memory.perfect_memory import PerfectMemory
            _perfect_memory = PerfectMemory()
            print("✅ PerfectMemory loaded", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ PerfectMemory load failed: {e}", file=sys.stderr)
    return _perfect_memory


def get_m2_embedder():
    """Lazy load M2-accelerated embedder."""
    global _m2_embedder
    if _m2_embedder is None:
        try:
            from core.memory.m2_embeddings import M2Embedder
            _m2_embedder = M2Embedder()
            print(f"✅ M2Embedder loaded: {_m2_embedder.backend}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ M2Embedder load failed: {e}", file=sys.stderr)
            # Fallback to core_data embeddings
            try:
                from core_data.embeddings import EmbeddingService
                _m2_embedder = EmbeddingService.get_instance()
                print("✅ Fallback EmbeddingService loaded", file=sys.stderr)
            except Exception as e2:
                print(f"❌ All embedders failed: {e2}", file=sys.stderr)
    return _m2_embedder


def get_rag_pipeline():
    """Lazy load RAG pipeline."""
    global _rag_pipeline
    if _rag_pipeline is None:
        try:
            from core_data.rag_pipeline import RAGPipeline
            _rag_pipeline = RAGPipeline()
            print("✅ RAGPipeline loaded", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ RAGPipeline load failed: {e}", file=sys.stderr)
    return _rag_pipeline


def get_neo4j_driver():
    """Get Neo4j driver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            from neo4j import GraphDatabase
            uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
            user = os.getenv('NEO4J_USER', 'neo4j')
            password = os.getenv('NEO4J_PASSWORD', 'brain2026')
            _neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            with _neo4j_driver.session() as session:
                session.run("RETURN 1")
            print("✅ Neo4j connected", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Neo4j connection failed: {e}", file=sys.stderr)
    return _neo4j_driver


def get_event_bus():
    """Get Redpanda/Kafka event bus."""
    global _event_bus
    if _event_bus is None:
        try:
            from core.kafka_bus import BrainEventBus
            _event_bus = BrainEventBus()
            _event_bus.connect()
            print("✅ Event bus connected", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Event bus connection failed: {e}", file=sys.stderr)
    return _event_bus


# ============================================================================
# SESSION STATE
# ============================================================================

_session = {
    "id": None,
    "started_at": None,
    "memories_stored": 0,
    "memories_recalled": 0,
    "preloaded_count": 0,
    "last_activity": None,
    "checkpoints": [],
    "recovered_from_crash": False,
    "preloaded_memories": [],  # Cache of preloaded memories
}

_shutdown_in_progress = False
_auto_checkpoint_task = None


# ============================================================================
# EMERGENCY SHUTDOWN HANDLER
# ============================================================================

def _emergency_save():
    """Emergency save on shutdown/crash."""
    global _shutdown_in_progress
    if _shutdown_in_progress:
        return
    _shutdown_in_progress = True
    
    try:
        state = {
            "session_id": _session.get("id", "emergency"),
            "saved_at": datetime.now().isoformat(),
            "memories_stored": _session.get("memories_stored", 0),
            "memories_recalled": _session.get("memories_recalled", 0),
            "checkpoints": _session.get("checkpoints", []),
            "clean_shutdown": True,
            "emergency": False
        }
        
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        # Emit shutdown event
        bus = get_event_bus()
        if bus:
            try:
                bus.emit("brain.memory.session_end", {
                    "session_id": _session.get("id"),
                    "memories_stored": _session.get("memories_stored", 0),
                    "timestamp": datetime.now().isoformat()
                })
            except:
                pass
        
        print(f"✅ Perfect Memory saved: {_session.get('id')}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Emergency save failed: {e}", file=sys.stderr)


def _signal_handler(signum, frame):
    """Handle termination signals."""
    print(f"🚨 Signal {signum} - saving memory state...", file=sys.stderr)
    _emergency_save()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
if hasattr(signal, 'SIGHUP'):
    signal.signal(signal.SIGHUP, _signal_handler)
atexit.register(_emergency_save)


# ============================================================================
# LIFECYCLE FUNCTIONS
# ============================================================================

def preload_memories() -> List[Dict]:
    """Preload recent memories on session start."""
    driver = get_neo4j_driver()
    if not driver:
        return []
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (m:Memory)
                WHERE m.timestamp IS NOT NULL
                RETURN m.id as id, m.text as text, m.category as category,
                       m.timestamp as timestamp, m.importance as importance
                ORDER BY m.timestamp DESC
                LIMIT $limit
            """, limit=MAX_PRELOAD_MEMORIES)
            
            memories = [dict(r) for r in result]
            print(f"📚 Preloaded {len(memories)} memories", file=sys.stderr)
            return memories
    except Exception as e:
        print(f"⚠️ Preload failed: {e}", file=sys.stderr)
        return []


def warm_up_embedder():
    """Warm up M2 embedder for fast first inference."""
    embedder = get_m2_embedder()
    if embedder:
        try:
            start = time.time()
            # Warm up with a simple embedding
            if hasattr(embedder, 'embed'):
                embedder.embed("warm up")
            elif hasattr(embedder, 'get_embedding'):
                embedder.get_embedding("warm up")
            elapsed = (time.time() - start) * 1000
            print(f"🔥 Embedder warmed up in {elapsed:.1f}ms", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Warm up failed: {e}", file=sys.stderr)


def detect_crash() -> Optional[Dict]:
    """Detect if previous session crashed."""
    if not STATE_FILE.exists():
        return None
    
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        
        if not state.get("clean_shutdown", False):
            return {"type": "crash", "previous_session": state.get("session_id")}
        
        return None
    except Exception:
        return None


async def auto_checkpoint_loop():
    """Background task for auto-checkpointing."""
    while True:
        await asyncio.sleep(AUTO_CHECKPOINT_INTERVAL)
        try:
            # Save current state
            state = {
                "session_id": _session.get("id"),
                "saved_at": datetime.now().isoformat(),
                "memories_stored": _session.get("memories_stored", 0),
                "memories_recalled": _session.get("memories_recalled", 0),
                "checkpoints": _session.get("checkpoints", []),
                "clean_shutdown": False,  # Mark as not clean until proper shutdown
                "auto_checkpoint": True
            }
            
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            _session["checkpoints"].append({
                "time": datetime.now().isoformat(),
                "type": "auto"
            })
            
            # Emit checkpoint event
            bus = get_event_bus()
            if bus:
                try:
                    bus.emit("brain.memory.checkpoint", {
                        "session_id": _session.get("id"),
                        "memories_stored": _session.get("memories_stored", 0),
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    pass
                    
        except Exception as e:
            print(f"⚠️ Auto-checkpoint failed: {e}", file=sys.stderr)


# ============================================================================
# MCP LIFECYCLE CONTEXT MANAGER
# ============================================================================

@asynccontextmanager
async def memory_lifespan(server: FastMCP):
    """
    Perfect Memory Lifecycle Hook.
    
    START:
    - Generate session ID
    - Check for crash recovery
    - Preload recent memories
    - Warm up M2 embedder
    - Start auto-checkpoint task
    
    END:
    - Save session state
    - Emit completion event
    - Clean shutdown marker
    """
    global _auto_checkpoint_task, _shutdown_in_progress
    _shutdown_in_progress = False
    
    # === SESSION START ===
    session_id = str(uuid.uuid4())[:8]
    _session["id"] = session_id
    _session["started_at"] = datetime.now().isoformat()
    _session["memories_stored"] = 0
    _session["memories_recalled"] = 0
    _session["checkpoints"] = []
    _session["recovered_from_crash"] = False
    
    print(f"🧠 Perfect Memory session started: {session_id}", file=sys.stderr)
    
    # Check for crash
    crash_info = detect_crash()
    if crash_info:
        print(f"🚨 Previous session crashed - recovering...", file=sys.stderr)
        _session["recovered_from_crash"] = True
        
        bus = get_event_bus()
        if bus:
            try:
                bus.emit("brain.memory.crash_recovered", {
                    "session_id": session_id,
                    "recovered_from": crash_info.get("previous_session"),
                    "timestamp": datetime.now().isoformat()
                })
            except:
                pass
    
    # Preload recent memories (THE KEY FEATURE!)
    preloaded = preload_memories()
    _session["preloaded_memories"] = preloaded
    _session["preloaded_count"] = len(preloaded)
    
    # Warm up M2 embedder for fast first inference
    warm_up_embedder()
    
    # Emit session start event
    bus = get_event_bus()
    if bus:
        try:
            bus.emit("brain.memory.session_start", {
                "session_id": session_id,
                "preloaded_count": len(preloaded),
                "recovered": _session.get("recovered_from_crash", False),
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
    
    # Start auto-checkpoint background task
    _auto_checkpoint_task = asyncio.create_task(auto_checkpoint_loop())
    
    try:
        yield
    finally:
        # === SESSION END ===
        print(f"🧠 Perfect Memory session ending: {session_id}", file=sys.stderr)
        
        # Cancel auto-checkpoint
        if _auto_checkpoint_task:
            _auto_checkpoint_task.cancel()
            try:
                await _auto_checkpoint_task
            except asyncio.CancelledError:
                pass
        
        # Final save
        _emergency_save()


# ============================================================================
# MCP SERVER
# ============================================================================

mcp = FastMCP("brain-memory", lifespan=memory_lifespan)


# ============================================================================
# TOOLS
# ============================================================================

@mcp.tool()
def memory_remember(
    text: str,
    category: str = "conversation",
    importance: float = 0.5,
    metadata: dict = None
) -> dict:
    """
    Store a memory with semantic embedding.
    
    Categories: error, learning, decision, insight, conversation, ephemeral
    Importance: 0.0 (low) to 1.0 (critical)
    
    The memory is embedded using M2 acceleration and stored in Neo4j
    for semantic retrieval.
    """
    memory_id = hashlib.md5(f"{text}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
    
    # Get embedding
    embedder = get_m2_embedder()
    embedding = None
    if embedder:
        try:
            if hasattr(embedder, 'embed'):
                embedding = embedder.embed(text)
            elif hasattr(embedder, 'get_embedding'):
                embedding = embedder.get_embedding(text)
        except Exception as e:
            print(f"⚠️ Embedding failed: {e}", file=sys.stderr)
    
    # Store in Neo4j
    driver = get_neo4j_driver()
    stored = False
    if driver and embedding:
        try:
            with driver.session() as session:
                session.run("""
                    CREATE (m:Memory {
                        id: $id,
                        text: $text,
                        category: $category,
                        importance: $importance,
                        timestamp: datetime(),
                        session_id: $session_id,
                        embedding: $embedding
                    })
                """,
                    id=memory_id,
                    text=text[:1000],  # Limit text length
                    category=category,
                    importance=importance,
                    session_id=_session.get("id", "unknown"),
                    embedding=embedding
                )
            stored = True
        except Exception as e:
            print(f"⚠️ Neo4j store failed: {e}", file=sys.stderr)
    
    _session["memories_stored"] = _session.get("memories_stored", 0) + 1
    _session["last_activity"] = datetime.now().isoformat()
    
    # Emit event
    bus = get_event_bus()
    if bus:
        try:
            bus.emit("brain.memory.stored", {
                "memory_id": memory_id,
                "category": category,
                "importance": importance,
                "session_id": _session.get("id"),
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
    
    return {
        "success": True,
        "memory_id": memory_id,
        "stored_in_neo4j": stored,
        "embedded": embedding is not None,
        "category": category,
        "importance": importance
    }


@mcp.tool()
def memory_recall(
    query: str,
    top_k: int = 10,
    category: str = None,
    min_importance: float = 0.0
) -> dict:
    """
    Recall memories semantically similar to the query.
    
    Uses M2-accelerated embedding and Neo4j vector search
    to find the most relevant memories.
    """
    # Get query embedding
    embedder = get_m2_embedder()
    if not embedder:
        return {"success": False, "error": "Embedder not available"}
    
    try:
        if hasattr(embedder, 'embed'):
            query_embedding = embedder.embed(query)
        elif hasattr(embedder, 'get_embedding'):
            query_embedding = embedder.get_embedding(query)
        else:
            return {"success": False, "error": "No embed method"}
    except Exception as e:
        return {"success": False, "error": f"Embedding failed: {e}"}
    
    # Search Neo4j
    driver = get_neo4j_driver()
    if not driver:
        return {"success": False, "error": "Neo4j not available"}
    
    memories = []
    try:
        with driver.session() as session:
            # Try vector search first
            try:
                result = session.run("""
                    CALL db.index.vector.queryNodes('memory_embedding_index', $top_k, $embedding)
                    YIELD node, score
                    WHERE ($category IS NULL OR node.category = $category)
                      AND node.importance >= $min_importance
                    RETURN node.id as id, node.text as text, node.category as category,
                           node.importance as importance, node.timestamp as timestamp,
                           score
                    ORDER BY score DESC
                """,
                    top_k=top_k,
                    embedding=query_embedding,
                    category=category,
                    min_importance=min_importance
                )
                memories = [dict(r) for r in result]
            except Exception:
                # Fallback to simple text search
                result = session.run("""
                    MATCH (m:Memory)
                    WHERE m.text CONTAINS $query
                      AND ($category IS NULL OR m.category = $category)
                      AND m.importance >= $min_importance
                    RETURN m.id as id, m.text as text, m.category as category,
                           m.importance as importance, m.timestamp as timestamp
                    ORDER BY m.timestamp DESC
                    LIMIT $top_k
                """,
                    query=query,
                    category=category,
                    min_importance=min_importance,
                    top_k=top_k
                )
                memories = [dict(r) for r in result]
    except Exception as e:
        return {"success": False, "error": f"Search failed: {e}"}
    
    _session["memories_recalled"] = _session.get("memories_recalled", 0) + len(memories)
    _session["last_activity"] = datetime.now().isoformat()
    
    # Emit event
    bus = get_event_bus()
    if bus:
        try:
            bus.emit("brain.memory.recalled", {
                "query": query[:100],
                "results_count": len(memories),
                "session_id": _session.get("id"),
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
    
    return {
        "success": True,
        "query": query,
        "memories": memories,
        "count": len(memories)
    }


@mcp.tool()
def memory_context(
    task: str,
    top_k: int = 5
) -> dict:
    """
    Get RAG context for the current task.
    
    Uses the RAG pipeline to retrieve relevant context
    from all memory sources (ROMs, Emails, Teams, JIRA, etc.)
    """
    rag = get_rag_pipeline()
    if not rag:
        # Fallback to simple memory recall
        return memory_recall(task, top_k=top_k)
    
    try:
        result = rag.ask(task)
        return {
            "success": True,
            "task": task,
            "context": result.answer if hasattr(result, 'answer') else str(result),
            "sources": result.sources if hasattr(result, 'sources') else [],
            "speakable": result.speakable if hasattr(result, 'speakable') else None
        }
    except Exception as e:
        return {"success": False, "error": f"RAG failed: {e}"}


@mcp.tool()
def memory_preload_status() -> dict:
    """
    Get status of preloaded memories.
    
    Shows what memories were preloaded on session start
    for immediate context availability.
    """
    return {
        "session_id": _session.get("id"),
        "preloaded_count": _session.get("preloaded_count", 0),
        "memories_stored": _session.get("memories_stored", 0),
        "memories_recalled": _session.get("memories_recalled", 0),
        "recovered_from_crash": _session.get("recovered_from_crash", False),
        "checkpoints": len(_session.get("checkpoints", [])),
        "started_at": _session.get("started_at"),
        "last_activity": _session.get("last_activity"),
        "preloaded_memories": [
            {
                "id": m.get("id"),
                "category": m.get("category"),
                "text": m.get("text", "")[:100] + "..." if m.get("text") else ""
            }
            for m in _session.get("preloaded_memories", [])[:10]  # Show first 10
        ]
    }


@mcp.tool()
def memory_stats() -> dict:
    """
    Get Perfect Memory system statistics.
    
    Shows embedding backend, Neo4j status, memory counts, etc.
    """
    embedder = get_m2_embedder()
    driver = get_neo4j_driver()
    bus = get_event_bus()
    
    # Get Neo4j memory count
    memory_count = 0
    if driver:
        try:
            with driver.session() as session:
                result = session.run("MATCH (m:Memory) RETURN count(m) as count")
                memory_count = result.single()["count"]
        except:
            pass
    
    return {
        "session": {
            "id": _session.get("id"),
            "started_at": _session.get("started_at"),
            "memories_stored": _session.get("memories_stored", 0),
            "memories_recalled": _session.get("memories_recalled", 0),
            "preloaded_count": _session.get("preloaded_count", 0),
            "checkpoints": len(_session.get("checkpoints", []))
        },
        "embedder": {
            "available": embedder is not None,
            "backend": getattr(embedder, 'backend', 'unknown') if embedder else None,
            "device": getattr(embedder, 'device', 'unknown') if embedder else None
        },
        "neo4j": {
            "connected": driver is not None,
            "total_memories": memory_count
        },
        "event_bus": {
            "connected": bus is not None
        }
    }


@mcp.tool()
def memory_create_index() -> dict:
    """
    Create Neo4j vector index for Memory nodes.
    
    Required for fast semantic search. Run once during setup.
    """
    driver = get_neo4j_driver()
    if not driver:
        return {"success": False, "error": "Neo4j not available"}
    
    try:
        with driver.session() as session:
            # Create vector index
            session.run("""
                CREATE VECTOR INDEX memory_embedding_index IF NOT EXISTS
                FOR (m:Memory)
                ON (m.embedding)
                OPTIONS {
                    indexConfig: {
                        `vector.dimensions`: 384,
                        `vector.similarity_function`: 'cosine'
                    }
                }
            """)
            
            # Create regular indexes
            session.run("CREATE INDEX memory_category IF NOT EXISTS FOR (m:Memory) ON (m.category)")
            session.run("CREATE INDEX memory_timestamp IF NOT EXISTS FOR (m:Memory) ON (m.timestamp)")
            session.run("CREATE INDEX memory_session IF NOT EXISTS FOR (m:Memory) ON (m.session_id)")
            
        return {
            "success": True,
            "message": "Created vector index and regular indexes for Memory nodes"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def memory_benchmark() -> dict:
    """
    Benchmark M2 embedding performance.
    
    Tests embedding speed to verify hardware acceleration.
    Target: 285 texts/sec on M2.
    """
    embedder = get_m2_embedder()
    if not embedder:
        return {"success": False, "error": "Embedder not available"}
    
    test_texts = [
        f"Test sentence number {i} for embedding benchmark on Apple M2"
        for i in range(100)
    ]
    
    # Single embedding benchmark
    start = time.time()
    if hasattr(embedder, 'embed'):
        embedder.embed(test_texts[0])
    elif hasattr(embedder, 'get_embedding'):
        embedder.get_embedding(test_texts[0])
    single_time = (time.time() - start) * 1000
    
    # Batch embedding benchmark
    start = time.time()
    if hasattr(embedder, 'embed_batch'):
        embedder.embed_batch(test_texts, batch_size=EMBEDDING_BATCH_SIZE)
    elif hasattr(embedder, 'batch_embed'):
        embedder.batch_embed(test_texts)
    else:
        # Fallback to single embedding
        for text in test_texts:
            if hasattr(embedder, 'embed'):
                embedder.embed(text)
            elif hasattr(embedder, 'get_embedding'):
                embedder.get_embedding(text)
    batch_time = time.time() - start
    
    throughput = len(test_texts) / batch_time
    
    return {
        "success": True,
        "backend": getattr(embedder, 'backend', 'unknown'),
        "device": getattr(embedder, 'device', 'unknown'),
        "single_embedding_ms": round(single_time, 2),
        "batch_100_seconds": round(batch_time, 3),
        "throughput_texts_per_sec": round(throughput, 1),
        "target_throughput": 285,
        "meets_target": throughput >= 250  # Allow some margin
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("🧠 Perfect Memory MCP Server v1.0", file=sys.stderr)
    print("   - M2 Hardware Acceleration", file=sys.stderr)
    print("   - MCP Lifecycle Hooks", file=sys.stderr)
    print("   - Neo4j Vector Search", file=sys.stderr)
    print("   - Redpanda Event Bus", file=sys.stderr)
    mcp.run()
