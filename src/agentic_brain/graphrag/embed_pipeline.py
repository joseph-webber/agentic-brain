#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Embedding Pipeline — Text → Vector Embeddings

Generates embeddings for Session summaries and stores them in Neo4j.
Uses Ollama nomic-embed-text (768-dim) with OpenAI fallback.

Adapted from Arraz's P23-brain-graphrag/embed_pipeline.py.

Usage:
    python -m agentic_brain.graphrag.embed_pipeline
    python -m agentic_brain.graphrag.embed_pipeline --dry-run
    python -m agentic_brain.graphrag.embed_pipeline --force
"""

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
from enum import Enum
from typing import Optional

# Neo4j config
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "Brain2026")

# Ollama config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = "nomic-embed-text"
OLLAMA_DIM = 768

# OpenAI fallback
OPENAI_MODEL = "text-embedding-3-small"
OPENAI_DIM = 1536

# Vector index
INDEX_NAME = "session_text_embeddings"


class EmbeddingProvider(Enum):
    """Embedding provider types."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    NONE = "none"


def embed_ollama(text: str) -> Optional[list[float]]:
    """Generate embedding using Ollama."""
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("embedding")
    except Exception:
        return None


def _get_openai_key() -> Optional[str]:
    """Get OpenAI API key from keychain or environment."""
    # Try macOS keychain first
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                "agentic-brain",
                "-a",
                "openai-api-key",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback to environment
    return os.environ.get("OPENAI_API_KEY")


def embed_openai(text: str) -> Optional[list[float]]:
    """Generate embedding using OpenAI API."""
    key = _get_openai_key()
    if not key:
        return None

    payload = json.dumps({"input": text, "model": OPENAI_MODEL}).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["data"][0]["embedding"]
    except Exception:
        return None


def embed_text(text: str) -> tuple[Optional[list[float]], EmbeddingProvider]:
    """
    Generate embedding for text.

    Returns:
        Tuple of (embedding, provider_used)
    """
    # Try Ollama first (local, fast, free)
    vec = embed_ollama(text)
    if vec:
        return vec, EmbeddingProvider.OLLAMA

    # Fall back to OpenAI
    vec = embed_openai(text)
    if vec:
        return vec, EmbeddingProvider.OPENAI

    return None, EmbeddingProvider.NONE


def detect_ollama_model() -> bool:
    """Check if required Ollama model is available."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m["name"].split(":")[0] for m in data.get("models", [])]
            return OLLAMA_MODEL in models or OLLAMA_MODEL.split(":")[0] in models
    except Exception:
        return False


def _get_driver():
    """Get Neo4j driver."""
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    return driver


def _fetch_sessions(driver, force: bool = False) -> list[dict]:
    """Fetch sessions that need embedding."""
    query = """
        MATCH (s:Session)
        WHERE s.summary IS NOT NULL AND s.summary <> ''
    """
    if not force:
        query += " AND s.embedding IS NULL"
    query += " RETURN s.id AS id, s.summary AS summary"

    with driver.session() as session:
        return [dict(r) for r in session.run(query)]


def _write_embedding(driver, session_id: str, embedding: list[float]):
    """Store embedding on session node."""
    with driver.session() as session:
        session.run(
            "MATCH (s:Session {id: $id}) SET s.embedding = $emb",
            id=session_id,
            emb=embedding,
        )


def _ensure_vector_index(driver, dim: int):
    """Create vector index if not exists."""
    query = f"""
        CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS
        FOR (s:Session) ON (s.embedding)
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {dim},
                `vector.similarity_function`: 'cosine'
            }}
        }}
    """
    with driver.session() as session:
        try:
            session.run(query)
            print(f"  Vector index '{INDEX_NAME}' ensured (dim={dim}, cosine).")
        except Exception as e:
            print(f"  WARNING: Could not create vector index: {e}")


def embed_sessions(
    dry_run: bool = False, force: bool = False, session_id: Optional[str] = None
):
    """
    Embed session summaries into Neo4j.

    Args:
        dry_run: Show what would happen without writing
        force: Re-embed all sessions, even those already embedded
        session_id: Embed a single session only
    """
    driver = _get_driver()

    try:
        if session_id:
            sessions = _fetch_sessions(driver, force=True)
            sessions = [s for s in sessions if s["id"] == session_id]
        else:
            sessions = _fetch_sessions(driver, force=force)

        has_ollama = detect_ollama_model()

        print(f"Sessions to embed: {len(sessions)}")
        print(
            f"  Ollama {OLLAMA_MODEL}: {'available' if has_ollama else 'NOT available — will fall back to OpenAI'}"
        )

        if not has_ollama:
            print(
                f"  TIP: Run `ollama pull {OLLAMA_MODEL}` to enable local embeddings."
            )

        if dry_run:
            print("\nDRY RUN — no writes will occur.")
            return

        embedded = 0
        errors = 0
        provider_counts: dict[str, int] = {}
        dim_used = None

        for sess in sessions:
            sid = sess["id"]
            summary = sess["summary"]

            vec, provider = embed_text(summary)
            if vec is None:
                print(f"  ERROR: could not embed session {sid}")
                errors += 1
                continue

            if dim_used is None:
                dim_used = len(vec)

            _write_embedding(driver, sid, vec)
            provider_counts[provider.value] = provider_counts.get(provider.value, 0) + 1
            embedded += 1

            if embedded % 10 == 0:
                print(f"  Progress: {embedded}/{len(sessions)} embedded...")

        print("\nDone.")
        print(f"  Embedded: {embedded}")
        print(f"  Errors: {errors}")
        for prov, cnt in provider_counts.items():
            print(f"  Provider '{prov}': {cnt} embeddings")

        if embedded > 0 and dim_used:
            _ensure_vector_index(driver, dim_used)

    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(description="Embed Session summaries into Neo4j.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would happen without writing."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed all sessions, even those already embedded.",
    )
    parser.add_argument(
        "--session-id", metavar="ID", help="Embed a single session only."
    )
    args = parser.parse_args()

    embed_sessions(dry_run=args.dry_run, force=args.force, session_id=args.session_id)


if __name__ == "__main__":
    main()
