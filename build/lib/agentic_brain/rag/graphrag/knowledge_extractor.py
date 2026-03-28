# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Neo4j knowledge extraction with a lightweight built-in GraphRAG path (batched UNWIND writes, MLX embeddings, async-friendly drivers)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import combinations
from typing import Any, Optional, Sequence

from agentic_brain.core.neo4j_utils import resilient_query_sync
from agentic_brain.core.neo4j_schema import VECTOR_INDEX_NAME, ensure_indexes_sync
from agentic_brain.core.neo4j_pool import configure_pool as configure_neo4j_pool
from agentic_brain.core.neo4j_pool import get_driver as get_neo4j_driver
from agentic_brain.core.neo4j_pool import get_session as get_neo4j_session

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import Neo4jError, ServiceUnavailable

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore[assignment]
    Neo4jError = Exception  # type: ignore[assignment]
    ServiceUnavailable = Exception  # type: ignore[assignment]
    NEO4J_AVAILABLE = False


ENTITY_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z0-9]+|[A-Z]{2,})(?:[\s-]+(?:[A-Z][a-z0-9]+|[A-Z]{2,}))*\b"
)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]+")
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
ORGANIZATION_HINTS = {
    "inc",
    "corp",
    "corporation",
    "company",
    "ltd",
    "llc",
    "university",
    "institute",
    "bank",
    "team",
    "group",
}
LOCATION_HINTS = {
    "city",
    "state",
    "country",
    "street",
    "road",
    "avenue",
    "mount",
    "river",
    "bay",
}
PERSON_HINTS = {"mr", "mrs", "ms", "dr", "prof", "sir", "lady", "duke"}
QUERY_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "show",
    "tell",
    "the",
    "to",
    "what",
    "where",
    "who",
}


class KnowledgeExtractorError(RuntimeError):
    """Raised when extraction or query execution fails."""


class GraphRAGDependencyError(KnowledgeExtractorError):
    """Raised when optional LLM-powered functionality is requested without support."""


@dataclass(slots=True)
class ExtractedEntity:
    """Entity extracted from source text."""

    id: str
    name: str
    type: str = "Entity"
    normalized_name: str = ""
    mention_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractedRelationship:
    """Relationship extracted between two entities."""

    source_entity_id: str
    target_entity_id: str
    type: str
    evidence: str
    weight: float = 1.0


@dataclass(slots=True)
class KnowledgeExtractionResult:
    """Structured result returned after text extraction."""

    document_id: str
    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]
    pipeline_used: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)


@dataclass(slots=True)
class GraphQueryResult:
    """Structured result returned from natural-language graph queries."""

    query: str
    mode: str
    results: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KnowledgeExtractorConfig:
    """Configuration for GraphRAG-backed knowledge extraction."""

    uri: str = field(
        default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687")
    )
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "Brain2026")
    )
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))
    use_connection_pool: bool = True
    create_schema: bool = True
    vector_index_name: str = VECTOR_INDEX_NAME
    perform_entity_resolution: bool = True
    on_error: str = "IGNORE"
    max_entities: int = 50
    schema: dict[str, list[Any]] = field(
        default_factory=lambda: {
            "node_types": ["Entity", "Person", "Organization", "Location", "Concept"],
            "relationship_types": [
                "RELATED_TO",
                "WORKS_AT",
                "LOCATED_IN",
                "PART_OF",
                "MENTIONS",
            ],
            "patterns": [
                ("Person", "WORKS_AT", "Organization"),
                ("Organization", "LOCATED_IN", "Location"),
                ("Entity", "RELATED_TO", "Entity"),
                ("Entity", "PART_OF", "Entity"),
            ],
        }
    )


class KnowledgeExtractor:
    """Extract entities and relationships into Neo4j using the shared pool.

    The built-in path uses lightweight heuristics plus raw Cypher persistence.
    When an LLM is supplied, the extractor upgrades to prompt-based entity and
    relationship extraction plus a read-only Text2Cypher planner without
    depending on ``neo4j-graphrag``.
    """

    def __init__(
        self,
        config: Optional[KnowledgeExtractorConfig] = None,
        *,
        driver: Any | None = None,
        llm: Any | None = None,
        embedder: Any | None = None,
    ) -> None:
        self.config = config or KnowledgeExtractorConfig()
        self._driver = driver
        self._owns_driver = False
        self._llm = llm
        self._embedder = embedder
        self._initialized = False

    def _get_embedder(self) -> Any | None:
        """Return the embedder, lazily defaulting to MLXEmbeddings."""
        if self._embedder is not None:
            return self._embedder
        try:
            from agentic_brain.rag.mlx_embeddings import MLXEmbeddings

            if MLXEmbeddings.is_available():
                self._embedder = MLXEmbeddings
        except Exception:
            pass
        return self._embedder

    def initialize(self) -> None:
        """Prepare the Neo4j connection and create graph schema if needed."""
        if self._initialized:
            return

        driver = self._get_driver()
        try:
            driver.verify_connectivity()
        except ServiceUnavailable as exc:
            raise KnowledgeExtractorError(
                f"Neo4j is unavailable at {self.config.uri}: {exc}"
            ) from exc
        except Exception as exc:  # pragma: no cover
            raise KnowledgeExtractorError(
                f"Neo4j connectivity check failed: {exc}"
            ) from exc

        if self.config.create_schema:
            self._ensure_schema()

        self._initialized = True

    def close(self) -> None:
        """Close the owned driver when direct connections are used."""
        if self._owns_driver and self._driver is not None:
            self._driver.close()
            self._driver = None
            self._initialized = False

    def extract_graph_only(
        self,
        text: str,
        *,
        document_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        use_graphrag_pipeline: bool = True,
    ) -> KnowledgeExtractionResult:
        """Extract entities/relationships without persisting to Neo4j."""
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("text must not be empty")

        metadata = dict(metadata or {})
        document_id = document_id or self._build_document_id(normalized_text)

        entities, relationships, pipeline_used = self._extract_graph_payload(
            normalized_text,
            document_id=document_id,
            metadata=metadata,
            use_graphrag_pipeline=use_graphrag_pipeline,
        )

        return KnowledgeExtractionResult(
            document_id=document_id,
            entities=entities,
            relationships=relationships,
            pipeline_used=pipeline_used,
            metadata=metadata,
        )

    async def extract_from_text(
        self,
        text: str,
        *,
        document_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        use_graphrag_pipeline: bool = True,
    ) -> KnowledgeExtractionResult:
        """Extract entities and relationships from text and persist them in Neo4j."""
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("text must not be empty")

        self.initialize()
        metadata = dict(metadata or {})
        document_id = document_id or self._build_document_id(normalized_text)
        timestamp = datetime.now(UTC).isoformat()

        entities, relationships, pipeline_used = self._extract_graph_payload(
            normalized_text,
            document_id=document_id,
            metadata=metadata,
            use_graphrag_pipeline=use_graphrag_pipeline,
        )

        self._persist_extraction(
            document_id=document_id,
            text=normalized_text,
            metadata=metadata,
            entities=entities,
            relationships=relationships,
            timestamp=timestamp,
        )

        return KnowledgeExtractionResult(
            document_id=document_id,
            entities=entities,
            relationships=relationships,
            pipeline_used=pipeline_used,
            metadata=metadata,
        )

    def _extract_graph_payload(
        self,
        text: str,
        *,
        document_id: str,
        metadata: dict[str, Any],
        use_graphrag_pipeline: bool,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelationship], bool]:
        pipeline_used = False
        if use_graphrag_pipeline and self._llm is not None:
            try:
                entities, relationships = self._extract_graph_with_llm(text)
                pipeline_used = True
                metadata.setdefault("pipeline", "builtin_llm")
                return entities, relationships, pipeline_used
            except Exception as exc:
                logger.warning(
                    "LLM graph extraction failed for %s, falling back to heuristics: %s",
                    document_id,
                    exc,
                )
                if self.config.on_error.upper() != "IGNORE":
                    raise KnowledgeExtractorError(
                        f"LLM graph extraction failed: {exc}"
                    ) from exc
                metadata["llm_extraction_error"] = str(exc)

        entities = self._extract_entities(text)
        relationships = self._extract_relationships(text, entities)
        metadata.setdefault("pipeline", "heuristic")
        return entities, relationships, pipeline_used

    def extract_from_text_sync(
        self,
        text: str,
        *,
        document_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        use_graphrag_pipeline: bool = True,
    ) -> KnowledgeExtractionResult:
        """Synchronous wrapper around :meth:`extract_from_text`."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.extract_from_text(
                    text,
                    document_id=document_id,
                    metadata=metadata,
                    use_graphrag_pipeline=use_graphrag_pipeline,
                )
            )
        raise KnowledgeExtractorError(
            "extract_from_text_sync cannot be used inside an active event loop; "
            "await extract_from_text instead."
        )

    def query(
        self,
        question: str,
        *,
        prompt_params: Optional[dict[str, Any]] = None,
        limit: int = 10,
    ) -> GraphQueryResult:
        """Run a natural-language query against the extracted knowledge graph."""
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")

        self.initialize()

        if self._can_use_text2cypher():
            try:
                return self._text2cypher_query(
                    normalized_question,
                    prompt_params=prompt_params,
                    limit=limit,
                )
            except Exception as exc:
                logger.warning(
                    "Text2Cypher query failed, falling back to keyword search: %s",
                    exc,
                )
                if self.config.on_error.upper() != "IGNORE":
                    raise KnowledgeExtractorError(
                        f"Built-in Text2Cypher query failed: {exc}"
                    ) from exc

        return self._fallback_query(normalized_question, limit=limit)

    def _get_driver(self) -> Any:
        if self._driver is not None:
            return self._driver

        if self.config.use_connection_pool:
            configure_neo4j_pool(
                uri=self.config.uri,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
            )
            self._driver = get_neo4j_driver(
                uri=self.config.uri,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
            )
            return self._driver

        if not NEO4J_AVAILABLE or GraphDatabase is None:
            raise GraphRAGDependencyError(
                "neo4j package is required for direct connections"
            )

        self._driver = GraphDatabase.driver(
            self.config.uri,
            auth=(self.config.user, self.config.password),
        )
        self._owns_driver = True
        return self._driver

    @contextmanager
    def _session_scope(self):
        if self.config.use_connection_pool:
            with get_neo4j_session(database=self.config.database) as session:
                yield session
            return

        session = self._get_driver().session(database=self.config.database)
        try:
            yield session
        finally:
            session.close()

    def _run_query(
        self,
        session: Any,
        query: str,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Run a Neo4j query with retry handling."""
        return resilient_query_sync(session, query, params)

    def _ensure_schema(self) -> None:
        statements = [
            """
            CREATE CONSTRAINT graphrag_source_document_id IF NOT EXISTS
            FOR (d:SourceDocument) REQUIRE d.id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT graphrag_entity_id IF NOT EXISTS
            FOR (e:Entity) REQUIRE e.id IS UNIQUE
            """,
            """
            CREATE INDEX graphrag_entity_name IF NOT EXISTS
            FOR (e:Entity) ON (e.name)
            """,
            """
            CREATE INDEX graphrag_entity_normalized_name IF NOT EXISTS
            FOR (e:Entity) ON (e.normalized_name)
            """,
        ]
        try:
            with self._session_scope() as session:
                for statement in statements:
                    self._run_query(session, statement)
                ensure_indexes_sync(session)
        except Neo4jError as exc:
            raise KnowledgeExtractorError(
                f"Failed to initialize GraphRAG schema: {exc}"
            ) from exc

    def _persist_extraction(
        self,
        *,
        document_id: str,
        text: str,
        metadata: dict[str, Any],
        entities: Sequence[ExtractedEntity],
        relationships: Sequence[ExtractedRelationship],
        timestamp: str,
    ) -> None:
        entity_payload = [asdict(entity) for entity in entities]
        relationship_payload = [asdict(rel) for rel in relationships]

        try:
            with self._session_scope() as session:
                self._run_query(
                    session,
                    """
                    MERGE (d:SourceDocument {id: $document_id})
                    SET d.content = $text,
                        d.metadata = $metadata,
                        d.updated_at = $timestamp
                    ON CREATE SET d.created_at = $timestamp
                    """,
                    document_id=document_id,
                    text=text,
                    metadata=metadata,
                    timestamp=timestamp,
                )

                if entity_payload:
                    self._run_query(
                        session,
                        """
                        MATCH (d:SourceDocument {id: $document_id})
                        UNWIND $entities AS entity
                        MERGE (e:Entity {id: entity.id})
                        SET e.name = entity.name,
                            e.type = entity.type,
                            e.normalized_name = entity.normalized_name,
                            e.metadata = entity.metadata,
                            e.updated_at = $timestamp
                        ON CREATE SET e.created_at = $timestamp
                        SET e.mention_count = coalesce(e.mention_count, 0) + entity.mention_count
                        MERGE (d)-[m:MENTIONS]->(e)
                        SET m.frequency = entity.mention_count,
                            m.updated_at = $timestamp
                        ON CREATE SET m.created_at = $timestamp
                        """,
                        document_id=document_id,
                        entities=entity_payload,
                        timestamp=timestamp,
                    )

                if relationship_payload:
                    self._run_query(
                        session,
                        """
                        UNWIND $relationships AS rel
                        MATCH (source:Entity {id: rel.source_entity_id})
                        MATCH (target:Entity {id: rel.target_entity_id})
                        MERGE (source)-[r:RELATES_TO]->(target)
                        ON CREATE SET r.created_at = $timestamp
                        SET r.type = rel.type,
                            r.evidence = rel.evidence,
                            r.weight = rel.weight,
                            r.updated_at = $timestamp
                        """,
                        relationships=relationship_payload,
                        timestamp=timestamp,
                    )
        except Neo4jError as exc:
            raise KnowledgeExtractorError(
                f"Failed to persist extracted knowledge: {exc}"
            ) from exc

    def _extract_entities(self, text: str) -> list[ExtractedEntity]:
        counts: dict[str, int] = {}
        original_forms: dict[str, str] = {}
        for match in ENTITY_PATTERN.finditer(text):
            candidate = match.group(0).strip(" -")
            normalized = self._normalize_entity_name(candidate)
            if not normalized or normalized.lower() in QUERY_STOP_WORDS:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
            original_forms.setdefault(normalized, candidate)

        ranked_entities = sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[: self.config.max_entities]

        return [
            ExtractedEntity(
                id=self._build_entity_id(normalized_name),
                name=original_forms[normalized_name],
                type=self._classify_entity(original_forms[normalized_name]),
                normalized_name=normalized_name,
                mention_count=mention_count,
            )
            for normalized_name, mention_count in ranked_entities
        ]

    def _extract_graph_with_llm(
        self, text: str
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
        response = self._generate_with_llm(
            self._build_entity_extraction_prompt(text),
            temperature=0,
        )
        payload = self._parse_llm_json(response)

        entities_by_name: dict[str, ExtractedEntity] = {}
        for item in payload.get("entities", []):
            if not isinstance(item, dict):
                continue
            raw_name = str(item.get("name", "")).strip()
            if not raw_name:
                continue
            normalized_name = self._normalize_entity_name(raw_name)
            if not normalized_name:
                continue
            mention_count = int(item.get("mention_count", 1) or 1)
            entity = ExtractedEntity(
                id=self._build_entity_id(normalized_name),
                name=raw_name,
                type=str(item.get("type") or self._classify_entity(raw_name)),
                normalized_name=normalized_name,
                mention_count=max(1, mention_count),
                metadata={
                    "source": "llm",
                    **(
                        item.get("metadata")
                        if isinstance(item.get("metadata"), dict)
                        else {}
                    ),
                },
            )
            entities_by_name.setdefault(normalized_name, entity)

        if not entities_by_name:
            raise KnowledgeExtractorError("LLM did not return any entities")

        relationships: list[ExtractedRelationship] = []
        for item in payload.get("relationships", []):
            if not isinstance(item, dict):
                continue
            source_name = self._normalize_entity_name(
                str(item.get("source", "")).strip()
            )
            target_name = self._normalize_entity_name(
                str(item.get("target", "")).strip()
            )
            if (
                source_name not in entities_by_name
                or target_name not in entities_by_name
            ):
                continue
            relationship_type = self._sanitize_relationship_type(
                str(item.get("type") or "RELATED_TO")
            )
            relationships.append(
                ExtractedRelationship(
                    source_entity_id=entities_by_name[source_name].id,
                    target_entity_id=entities_by_name[target_name].id,
                    type=relationship_type,
                    evidence=str(item.get("evidence") or text[:240]).strip(),
                    weight=float(item.get("weight", 1.0) or 1.0),
                )
            )

        if not relationships:
            relationships = self._extract_relationships(
                text, list(entities_by_name.values())
            )

        return list(entities_by_name.values()), relationships

    def _extract_relationships(
        self, text: str, entities: Sequence[ExtractedEntity]
    ) -> list[ExtractedRelationship]:
        relationships: dict[tuple[str, str, str], ExtractedRelationship] = {}

        for sentence in filter(None, SENTENCE_SPLIT_PATTERN.split(text)):
            matching_entities = [
                entity
                for entity in entities
                if entity.name in sentence or entity.normalized_name in sentence.lower()
            ]
            for source, target in combinations(matching_entities, 2):
                relationship_type = self._infer_relationship_type(sentence)
                key = (source.id, target.id, relationship_type)
                if key in relationships:
                    continue
                relationships[key] = ExtractedRelationship(
                    source_entity_id=source.id,
                    target_entity_id=target.id,
                    type=relationship_type,
                    evidence=sentence.strip(),
                    weight=1.0,
                )

        return list(relationships.values())

    def _fallback_query(self, question: str, *, limit: int) -> GraphQueryResult:
        terms = [
            term.lower()
            for term in TOKEN_PATTERN.findall(question)
            if len(term) > 2 and term.lower() not in QUERY_STOP_WORDS
        ]
        if not terms:
            terms = [question.lower()]

        with self._session_scope() as session:
            result = self._run_query(
                session,
                """
                MATCH (d:SourceDocument)-[:MENTIONS]->(e:Entity)
                WHERE any(term IN $terms WHERE
                    toLower(e.name) CONTAINS term OR
                    toLower(e.normalized_name) CONTAINS term OR
                    toLower(d.content) CONTAINS term
                )
                OPTIONAL MATCH (e)-[r:RELATES_TO]->(related:Entity)
                RETURN
                    d.id AS document_id,
                    d.content AS content,
                    e.name AS entity,
                    e.type AS entity_type,
                    collect(DISTINCT {
                        related_entity: related.name,
                        relationship_type: r.type,
                        evidence: r.evidence
                    })[..5] AS relationships
                LIMIT $limit
                """,
                terms=terms,
                limit=limit,
            )
            records = list(result)

        return GraphQueryResult(
            query=question,
            mode="keyword_fallback",
            results=records,
            metadata={"terms": terms},
        )

    def _text2cypher_query(
        self,
        question: str,
        *,
        prompt_params: Optional[dict[str, Any]],
        limit: int,
    ) -> GraphQueryResult:
        prompt = self._build_text2cypher_prompt(
            question=question,
            prompt_params=prompt_params,
            limit=limit,
        )
        response = self._generate_with_llm(prompt, temperature=0)
        payload = self._parse_llm_json(response)
        cypher = str(payload.get("cypher", "")).strip()
        params = (
            payload.get("params") if isinstance(payload.get("params"), dict) else {}
        )
        params = dict(params)
        params["limit"] = limit

        if not cypher:
            raise KnowledgeExtractorError("LLM did not return a Cypher query")
        if "$limit" not in cypher:
            cypher = f"{cypher.rstrip()} LIMIT $limit"
        if not self._is_safe_read_only_cypher(cypher):
            raise KnowledgeExtractorError("LLM generated unsafe Cypher")

        with self._session_scope() as session:
            results = self._run_query(session, cypher, **params)

        return GraphQueryResult(
            query=question,
            mode="text2cypher",
            results=results,
            metadata={
                "cypher": cypher,
                "params": params,
                "generator": "built_in_llm",
                "reasoning": str(payload.get("reasoning", "")).strip(),
            },
        )

    def _build_schema_description(self) -> str:
        return (
            "Nodes:\n"
            "- SourceDocument(id, content, metadata, created_at, updated_at)\n"
            "- Entity(id, name, normalized_name, type, metadata, mention_count)\n"
            "Relationships:\n"
            "- (:SourceDocument)-[:MENTIONS]->(:Entity)\n"
            "- (:Entity)-[:RELATES_TO {type, evidence, weight}]->(:Entity)\n"
            "Use the RELATES_TO.type property to distinguish semantic relationship types."
        )

    def _can_use_text2cypher(self) -> bool:
        return self._llm is not None

    def _build_entity_extraction_prompt(self, text: str) -> str:
        return (
            "Extract a lightweight knowledge graph from the text.\n"
            "Return strict JSON with this shape:\n"
            '{"entities":[{"name":"Alice","type":"Person","mention_count":2}],'
            '"relationships":[{"source":"Alice","target":"Acme Corp","type":"WORKS_AT","evidence":"Alice works at Acme Corp."}]}'
            "\nRules:\n"
            "- Entity types must be one of Person, Organization, Location, Concept, Entity.\n"
            "- Relationship types must be uppercase snake case.\n"
            "- Only include entities and relationships directly supported by the text.\n"
            "- Do not include markdown fences or commentary.\n\n"
            f"Text:\n{text}"
        )

    def _build_text2cypher_prompt(
        self,
        *,
        question: str,
        prompt_params: Optional[dict[str, Any]],
        limit: int,
    ) -> str:
        extra_context = json.dumps(prompt_params or {}, sort_keys=True)
        return (
            "Translate the question into a SAFE read-only Cypher query.\n"
            "Return strict JSON with keys cypher, params, reasoning.\n"
            "Schema:\n"
            f"{self._build_schema_description()}\n"
            "Rules:\n"
            "- Read only. Never use CREATE, MERGE, DELETE, SET, REMOVE, DROP, CALL, LOAD, APOC, or dbms.\n"
            "- Query only SourceDocument, Entity, MENTIONS, and RELATES_TO.\n"
            "- Prefer exact or contains matching against e.name, e.normalized_name, and d.content.\n"
            "- Always use parameter placeholders instead of hardcoding user text.\n"
            f"- The final Cypher must support LIMIT $limit where limit={limit}.\n"
            "- Do not include markdown fences or explanation outside JSON.\n\n"
            f"Question: {question}\n"
            f"Prompt params: {extra_context}"
        )

    def _generate_with_llm(self, prompt: str, **kwargs: Any) -> str:
        llm = self._llm
        if llm is None:
            raise GraphRAGDependencyError("An LLM is required for this operation")

        if hasattr(llm, "generate"):
            result = llm.generate(prompt, **kwargs)
        elif hasattr(llm, "chat_sync"):
            result = llm.chat_sync(prompt, **kwargs)
            result = getattr(result, "content", result)
        elif hasattr(llm, "chat"):
            result = llm.chat(prompt, **kwargs)
            result = getattr(result, "content", result)
        else:
            raise GraphRAGDependencyError(
                "LLM must implement generate(), chat_sync(), or chat()"
            )
        if not isinstance(result, str):
            result = str(result)
        return result

    def _parse_llm_json(self, text: str) -> dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if "\n" in candidate:
                candidate = candidate.split("\n", 1)[1]
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            match = JSON_OBJECT_PATTERN.search(text)
            if match:
                payload = json.loads(match.group(0))
                if isinstance(payload, dict):
                    return payload
        raise KnowledgeExtractorError("LLM did not return valid JSON")

    @staticmethod
    def _build_document_id(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _build_entity_id(normalized_name: str) -> str:
        return hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _normalize_entity_name(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip()).lower()

    @staticmethod
    def _sanitize_relationship_type(value: str) -> str:
        cleaned = re.sub(r"[^A-Z0-9_]+", "_", value.strip().upper()).strip("_")
        return cleaned or "RELATED_TO"

    @staticmethod
    def _infer_relationship_type(sentence: str) -> str:
        lowered = sentence.lower()
        if "works at" in lowered or "works for" in lowered:
            return "WORKS_AT"
        if "located in" in lowered or "based in" in lowered:
            return "LOCATED_IN"
        if "part of" in lowered or "member of" in lowered:
            return "PART_OF"
        if "created by" in lowered or "built by" in lowered:
            return "CREATED_BY"
        return "RELATED_TO"

    @staticmethod
    def _classify_entity(name: str) -> str:
        lowered = name.lower()
        if any(hint in lowered.split() for hint in ORGANIZATION_HINTS):
            return "Organization"
        if any(hint in lowered.split() for hint in LOCATION_HINTS):
            return "Location"
        if any(hint in lowered.split() for hint in PERSON_HINTS):
            return "Person"
        if len(name.split()) >= 2:
            return "Person"
        if name.isupper():
            return "Organization"
        return "Entity"

    @staticmethod
    def _is_safe_read_only_cypher(cypher: str) -> bool:
        stripped = re.sub(r"\s+", " ", cypher).strip().lower()
        if not stripped.startswith(("match ", "with ", "optional match ", "return ")):
            return False
        forbidden = (
            " create ",
            " merge ",
            " delete ",
            " detach delete ",
            " set ",
            " remove ",
            " drop ",
            " call ",
            " load csv",
            " apoc.",
            " dbms.",
        )
        return not any(token in f" {stripped} " for token in forbidden)
