# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
GraphRAG Synthesis Layer — Hybrid Retrieval with RRF Merge

Combines vector similarity search (ANN) with graph traversal to retrieve
relevant sessions, then synthesizes an answer using LLM.

Adapted from Arraz's P23-brain-graphrag/synthesis_layer.py.

Usage:
    python -m agentic_brain.graphrag.synthesis_layer "your question here"
    python -m agentic_brain.graphrag.synthesis_layer "your question" --top-k 10
    python -m agentic_brain.graphrag.synthesis_layer "your question" --no-synthesis

    # Or programmatically:
    from agentic_brain.graphrag import recall
    answer = recall("What work was done on the voice system?")
"""

import argparse
import json
import os
import urllib.request
from typing import Optional

# Neo4j config
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "Brain2026")

# Ollama config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# Vector indexes
TEXT_INDEX = "session_text_embeddings"
STRUCT_INDEX = "session_structural_embeddings"

# RRF parameter (higher = more weight to lower-ranked results)
RRF_K = 60

# Synthesis system prompt
SYNTHESIS_SYSTEM = (
    "You are an assistant with access to a personal knowledge brain. "
    "Answer the user's question concisely using only the provided session context. "
    "If the sessions don't contain enough information, say so honestly."
)


class GraphRAGSynthesis:
    """
    GraphRAG recall system.

    Combines:
    1. Vector similarity search (semantic)
    2. Graph traversal (structural)
    3. RRF merge (reciprocal rank fusion)
    4. LLM synthesis
    """

    def __init__(self, llm_ask_fn=None):
        """
        Initialize synthesis layer.

        Args:
            llm_ask_fn: Function to call LLM. Signature: (prompt, system=None) -> str
        """
        self._llm_ask = llm_ask_fn
        self._driver = None

    def _get_driver(self):
        """Get Neo4j driver."""
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            self._driver.verify_connectivity()
        return self._driver

    def _embed_question(self, text: str) -> Optional[list[float]]:
        """Generate embedding for question."""
        payload = json.dumps({"model": OLLAMA_EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data.get("embedding")
        except Exception as e:
            print(f"ERROR: Ollama embedding failed: {e}")
            return None

    def _ann_search(
        self, index: str, embedding: list[float], top_k: int
    ) -> list[tuple[str, int]]:
        """
        Perform ANN (Approximate Nearest Neighbor) search.

        Returns:
            List of (session_id, rank) tuples
        """
        driver = self._get_driver()
        try:
            with driver.session() as session:
                results = session.run(
                    """
                    CALL db.index.vector.queryNodes($index, $top_k, $embedding)
                    YIELD node, score
                    WHERE node:Session
                    RETURN node.id AS id, score
                    ORDER BY score DESC
                """,
                    index=index,
                    top_k=top_k,
                    embedding=embedding,
                ).data()
                return [(r["id"], rank + 1) for rank, r in enumerate(results)]
        except Exception as e:
            # Index may not exist
            print(f"  WARNING: ANN search on '{index}' failed: {e}")
            return []

    def _rrf_merge(
        self,
        text_results: list[tuple[str, int]],
        struct_results: list[tuple[str, int]],
        top_k: int,
        k: int = RRF_K,
    ) -> list[str]:
        """
        Reciprocal Rank Fusion — merge rankings from multiple sources.

        Returns:
            Top-k session IDs by combined RRF score
        """
        scores: dict[str, float] = {}

        for sid, rank in text_results:
            scores[sid] = scores.get(sid, 0.0) + 1.0 / (rank + k)

        for sid, rank in struct_results:
            scores[sid] = scores.get(sid, 0.0) + 1.0 / (rank + k)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [sid for sid, _ in ranked[:top_k]]

    def _fetch_session_context(self, session_ids: list[str]) -> list[dict]:
        """
        Fetch enriched context for sessions.

        Includes summary, topics, entities, and continuation chain.
        """
        if not session_ids:
            return []

        driver = self._get_driver()
        with driver.session() as session:
            results = session.run(
                """
                UNWIND $ids AS sid
                MATCH (sess:Session {id: sid})
                OPTIONAL MATCH (sess)-[:DISCUSSES]->(t:Topic)
                OPTIONAL MATCH (sess)-[:MENTIONS]->(e:Entity)
                OPTIONAL MATCH (sess)-[:CONTINUES]->(prev:Session)
                RETURN
                    sess.id AS id,
                    sess.title AS title,
                    sess.summary AS summary,
                    collect(DISTINCT t.name) AS topics,
                    collect(DISTINCT {name: e.name, type: e.type}) AS entities,
                    prev.id AS continues_from,
                    prev.title AS continues_from_title
            """,
                ids=session_ids,
            ).data()

        # Preserve the RRF order
        id_to_ctx = {r["id"]: r for r in results}
        return [id_to_ctx[sid] for sid in session_ids if sid in id_to_ctx]

    def _format_context(self, sessions: list[dict]) -> str:
        """Format session context for LLM prompt."""
        parts = []
        for i, sess in enumerate(sessions, 1):
            title = sess.get("title") or sess.get("id", "")[:8]
            summary = sess.get("summary") or "(no summary)"
            topics = ", ".join(sess.get("topics") or []) or "none"
            entities = (
                ", ".join(
                    f"{e['name']} ({e['type']})"
                    for e in (sess.get("entities") or [])
                    if e.get("name")
                )
                or "none"
            )

            continues = ""
            if sess.get("continues_from"):
                cf_title = sess.get("continues_from_title") or sess["continues_from"]
                continues = f"\n    Continues from: {cf_title}"

            parts.append(
                f"[{i}] {title}\n"
                f"    Summary: {summary}\n"
                f"    Topics: {topics}\n"
                f"    Entities: {entities}"
                f"{continues}"
            )
        return "\n\n".join(parts)

    def _ask_llm(self, prompt: str, system: str) -> Optional[str]:
        """Ask LLM for response."""
        if self._llm_ask:
            return self._llm_ask(prompt, system=system)

        # Default: try local Ollama
        try:
            payload = json.dumps(
                {
                    "model": "llama3.2:3b",
                    "prompt": f"{system}\n\n{prompt}",
                    "stream": False,
                }
            ).encode()
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data.get("response", "")
        except Exception as e:
            return f"LLM call failed: {e}"

    def recall(self, question: str, top_k: int = 5, synthesize: bool = True) -> str:
        """
        Main recall function.

        Args:
            question: The question to answer
            top_k: Number of sessions to retrieve
            synthesize: If True, use LLM to synthesize answer. If False, return raw context.

        Returns:
            Answer string (synthesized or raw context)
        """
        # 1. Embed the question
        embedding = self._embed_question(question)
        if embedding is None:
            return (
                f"ERROR: Could not generate embedding for your question. "
                f"Ensure Ollama is running and '{OLLAMA_EMBED_MODEL}' is pulled.\n"
                f"Run: ollama pull {OLLAMA_EMBED_MODEL}"
            )

        # 2. ANN search on both indexes
        text_results = self._ann_search(TEXT_INDEX, embedding, top_k)
        struct_results = self._ann_search(STRUCT_INDEX, embedding, top_k)

        if not text_results and not struct_results:
            return (
                "No results found. The vector indexes may not be populated yet.\n"
                "Run embedding first: python -m agentic_brain.graphrag.embed_pipeline"
            )

        # 3. RRF merge
        merged_ids = self._rrf_merge(text_results, struct_results, top_k)

        # 4. Fetch enriched context
        sessions = self._fetch_session_context(merged_ids)
        context = self._format_context(sessions)

        # 5. Return raw or synthesized
        if not synthesize:
            return context

        prompt = (
            f"Given these sessions from my personal brain, answer: {question}\n\n"
            f"Sessions:\n{context}"
        )
        result = self._ask_llm(prompt, SYNTHESIS_SYSTEM)

        if not result or "failed" in result.lower():
            return f"Synthesis failed. Raw context:\n\n{context}"

        return result

    def close(self):
        """Close Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None


def recall(
    question: str, top_k: int = 5, synthesize: bool = True, llm_ask_fn=None
) -> str:
    """
    Query the brain using GraphRAG.

    Args:
        question: What to ask
        top_k: Number of sessions to retrieve
        synthesize: Use LLM to synthesize (True) or return raw context (False)
        llm_ask_fn: Optional custom LLM function

    Returns:
        Answer string
    """
    synth = GraphRAGSynthesis(llm_ask_fn=llm_ask_fn)
    try:
        return synth.recall(question, top_k=top_k, synthesize=synthesize)
    finally:
        synth.close()


def main():
    parser = argparse.ArgumentParser(description="GraphRAG recall from brain.")
    parser.add_argument("question", nargs="?", help="Question to ask.")
    parser.add_argument(
        "--top-k", type=int, default=5, help="Number of sessions (default 5)."
    )
    parser.add_argument(
        "--no-synthesis", action="store_true", help="Return raw summaries."
    )
    args = parser.parse_args()

    if not args.question:
        parser.print_help()
        return

    answer = recall(args.question, top_k=args.top_k, synthesize=not args.no_synthesis)
    print(answer)


if __name__ == "__main__":
    main()
