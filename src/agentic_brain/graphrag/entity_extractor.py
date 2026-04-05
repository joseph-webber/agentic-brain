#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Entity Extractor — Extract named entities from sessions

Uses LLM to extract Tools, Systems, Persons, and Projects from session text.
Creates Entity nodes and MENTIONS relationships in Neo4j.

Adapted from Arraz's P23-brain-graphrag/entity_extractor.py.

Usage:
    python -m agentic_brain.graphrag.entity_extractor
    python -m agentic_brain.graphrag.entity_extractor --dry-run
    python -m agentic_brain.graphrag.entity_extractor --session-id <uuid>
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional

# Neo4j config
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "Brain2026")

# Entity types we extract
ENTITY_TYPES = {"Tool", "System", "Person", "Project", "Concept"}

# Confidence threshold for storing
CONFIDENCE_GATE = 0.7

# Extraction log
LOG_PATH = Path.home() / ".agentic-brain" / "graphrag" / "extraction_log.jsonl"

EXTRACTION_SYSTEM = (
    "You are an entity extractor for a personal knowledge base. "
    "Extract only entities that appear clearly and explicitly in the text. "
    "Do NOT extract the user themselves as a Person entity. "
    "Output ONLY valid JSON — no explanation, no markdown."
)

EXTRACTION_PROMPT = """Extract named entities from this session log. Return a JSON array only.

Entity types allowed:
- Tool: scripts, files, CLI tools, libraries (e.g. llm_router.py, neo4j driver, pandas)
- System: platforms, services, databases, containers (e.g. Neo4j, Ollama, Docker, Redis)
- Person: external contacts, team members (NOT the user themselves)
- Project: project references or named projects
- Concept: key technical concepts, methodologies, patterns

Format: [{{"name": "...", "type": "Tool|System|Person|Project|Concept", "confidence": 0.0-1.0}}]

Session text:
{text}"""


class EntityExtractor:
    """Extract named entities from text using LLM."""

    def __init__(self, llm_ask_fn=None):
        """
        Initialize extractor.

        Args:
            llm_ask_fn: Function to call LLM. Signature: (prompt, system=None) -> str
                       If None, uses local Ollama or falls back to simple extraction.
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

    def _ask_llm(self, prompt: str, system: str) -> Optional[str]:
        """Ask LLM for response."""
        if self._llm_ask:
            return self._llm_ask(prompt, system=system)

        # Default: try local Ollama
        try:
            import urllib.request

            payload = json.dumps(
                {
                    "model": "llama3.2:3b",
                    "prompt": f"{system}\n\n{prompt}",
                    "stream": False,
                }
            ).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data.get("response", "")
        except Exception as e:
            print(f"  WARNING: LLM call failed: {e}")
            return None

    def _repair_truncated_json(self, raw: str) -> str:
        """Try to salvage truncated JSON."""
        last_close = raw.rfind("}")
        if last_close == -1:
            return raw
        truncated = raw[: last_close + 1].rstrip().rstrip(",")
        start = truncated.find("[")
        if start == -1:
            return raw
        return truncated[start:] + "]"

    def extract(self, text: str) -> list[dict]:
        """
        Extract entities from text.

        Returns:
            List of {"name": str, "type": str, "confidence": float}
        """
        if not text or len(text) < 10:
            return []

        prompt = EXTRACTION_PROMPT.format(text=text[:8000])
        response = self._ask_llm(prompt, EXTRACTION_SYSTEM)

        if not response:
            return []

        raw = response.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

        try:
            entities = json.loads(raw)
        except json.JSONDecodeError:
            try:
                entities = json.loads(self._repair_truncated_json(raw))
            except json.JSONDecodeError:
                return []

        if not isinstance(entities, list):
            return []

        # Validate entities
        validated = []
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            name = ent.get("name", "").strip()
            etype = ent.get("type", "").strip()
            confidence = float(ent.get("confidence", 0.0))

            if not name or etype not in ENTITY_TYPES:
                continue

            validated.append({"name": name, "type": etype, "confidence": confidence})

        return validated

    def extract_and_store(
        self, session_id: str, text: str, dry_run: bool = False
    ) -> list[dict]:
        """
        Extract entities and store to Neo4j.

        Args:
            session_id: Session UUID to link entities to
            text: Text to extract from
            dry_run: If True, don't write to Neo4j

        Returns:
            List of entities that were stored
        """
        all_entities = self.extract(text)
        above_gate = [e for e in all_entities if e["confidence"] >= CONFIDENCE_GATE]

        if not dry_run and above_gate:
            self._write_entities(session_id, above_gate)

        # Log extraction
        self._log_extraction(session_id, all_entities, above_gate, dry_run)

        return above_gate

    def _write_entities(self, session_id: str, entities: list[dict]):
        """Write entity nodes and relationships to Neo4j."""
        driver = self._get_driver()
        with driver.session() as session:
            for ent in entities:
                session.run(
                    """
                    MERGE (e:Entity {name: $name, type: $type})
                    ON CREATE SET e.confidence = $confidence
                    ON MATCH SET e.confidence = CASE
                        WHEN $confidence > e.confidence THEN $confidence
                        ELSE e.confidence
                    END
                    WITH e
                    MATCH (sess:Session {id: $sid})
                    MERGE (sess)-[:MENTIONS]->(e)
                """,
                    name=ent["name"],
                    type=ent["type"],
                    confidence=ent["confidence"],
                    sid=session_id,
                )

    def _log_extraction(
        self,
        session_id: str,
        all_entities: list[dict],
        written: list[dict],
        dry_run: bool,
    ):
        """Log extraction for debugging."""
        entry = {
            "session_id": session_id,
            "dry_run": dry_run,
            "total_extracted": len(all_entities),
            "written": len(written),
            "filtered_out": len(all_entities) - len(written),
            "entities": all_entities,
        }
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def close(self):
        """Close Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None


def _fetch_sessions(
    driver, session_id: Optional[str] = None, force: bool = False
) -> list[dict]:
    """Fetch sessions for extraction."""
    if session_id:
        query = """
            MATCH (s:Session {id: $sid})
            OPTIONAL MATCH (s)-[:HAS_CHECKPOINT]->(cp:Checkpoint)
            RETURN s.id AS id, s.summary AS summary, s.path AS path,
                   collect(cp.file) AS checkpoint_files
        """
        with driver.session() as session:
            return [dict(r) for r in session.run(query, sid=session_id)]
    elif force:
        query = """
            MATCH (s:Session)
            OPTIONAL MATCH (s)-[:HAS_CHECKPOINT]->(cp:Checkpoint)
            RETURN s.id AS id, s.summary AS summary, s.path AS path,
                   collect(cp.file) AS checkpoint_files
        """
    else:
        query = """
            MATCH (s:Session)
            WHERE NOT EXISTS { MATCH (s)-[:MENTIONS]->() }
            OPTIONAL MATCH (s)-[:HAS_CHECKPOINT]->(cp:Checkpoint)
            RETURN s.id AS id, s.summary AS summary, s.path AS path,
                   collect(cp.file) AS checkpoint_files
        """

    with driver.session() as session:
        return [dict(r) for r in session.run(query)]


def _read_checkpoint_content(
    session_path: Optional[str], checkpoint_files: list
) -> str:
    """Read checkpoint content from filesystem."""
    if not session_path or not checkpoint_files:
        return ""
    parts = []
    base = Path(session_path) / "checkpoints"
    for fname in checkpoint_files:
        if not fname:
            continue
        fpath = base / fname
        if fpath.exists():
            try:
                parts.append(fpath.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
    return "\n\n".join(parts)


def extract_entities(
    dry_run: bool = False,
    force: bool = False,
    session_id: Optional[str] = None,
    llm_ask_fn=None,
):
    """
    Extract entities from sessions and store to Neo4j.

    Args:
        dry_run: Show what would happen without writing
        force: Re-extract even sessions that have MENTIONS
        session_id: Extract from single session only
        llm_ask_fn: Optional LLM function
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()

    extractor = EntityExtractor(llm_ask_fn=llm_ask_fn)

    try:
        sessions = _fetch_sessions(driver, session_id=session_id, force=force)

        print(f"Sessions to process: {len(sessions)}")
        if dry_run:
            print("DRY RUN — no writes will occur.\n")

        total_written = 0
        total_errors = 0

        for i, sess in enumerate(sessions, 1):
            sid = sess["id"]
            summary = sess.get("summary") or ""
            checkpoint_files = sess.get("checkpoint_files") or []
            session_path = sess.get("path")

            checkpoint_text = _read_checkpoint_content(session_path, checkpoint_files)
            combined = f"{summary}\n\n{checkpoint_text}".strip()

            if not combined:
                print(f"  [{i}/{len(sessions)}] {sid[:8]}... — no text, skipping")
                continue

            print(
                f"  [{i}/{len(sessions)}] {sid[:8]}... ({len(checkpoint_files)} checkpoints, {len(combined)} chars)"
            )

            try:
                entities = extractor.extract_and_store(sid, combined, dry_run=dry_run)
                if entities:
                    total_written += len(entities)
                    for ent in entities:
                        print(
                            f"      [{ent['type']}] {ent['name']} (confidence={ent['confidence']:.2f})"
                        )
            except Exception as e:
                print(f"    ERROR: {e}")
                total_errors += 1

        print(f"\nDone.")
        print(f"  Sessions processed: {len(sessions)}")
        print(f"  Entity-session links written: {total_written}")
        print(f"  Errors: {total_errors}")
        print(f"  Extraction log: {LOG_PATH}")

    finally:
        driver.close()
        extractor.close()


def main():
    parser = argparse.ArgumentParser(
        description="Extract entities from Session checkpoints."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would happen without writing."
    )
    parser.add_argument("--force", action="store_true", help="Re-extract all sessions.")
    parser.add_argument(
        "--session-id", metavar="ID", help="Run on single session only."
    )
    args = parser.parse_args()

    extract_entities(dry_run=args.dry_run, force=args.force, session_id=args.session_id)


if __name__ == "__main__":
    main()
