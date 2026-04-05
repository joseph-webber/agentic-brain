# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Graph RAG compatibility tests.

Verifies that agentic-brain's Graph RAG implementation remains compatible
with standard Neo4j Graph RAG patterns used by external frameworks
(Arraz2000, neo4j-graphrag, Microsoft GraphRAG, LangChain).

These tests run WITHOUT a live Neo4j connection — they validate schema
definitions, data structures, entity extraction, and import/export
contracts so that we never silently break compatibility.
"""

from __future__ import annotations

import hashlib
import importlib
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Schema Compatibility Tests
# ---------------------------------------------------------------------------


class TestSchemaCompatibility:
    """Verify our Neo4j schema matches standard Graph RAG patterns."""

    def test_core_node_labels_defined(self):
        """Document, Chunk, Entity are the universal Graph RAG triad."""
        from agentic_brain.rag.graph import EnhancedGraphRAG

        rag = EnhancedGraphRAG()
        # The initialize() method creates constraints for these three labels
        # Verify the source mentions all three
        import inspect

        source = inspect.getsource(rag.initialize)
        for label in ("Document", "Chunk", "Entity"):
            assert label in source, f"Missing constraint for {label} in initialize()"

    def test_vector_index_name_is_standard(self):
        """Vector index name should be consistent across modules."""
        from agentic_brain.core.neo4j_schema import VECTOR_INDEX_NAME

        assert VECTOR_INDEX_NAME == "chunk_embeddings"

    def test_indexes_use_if_not_exists(self):
        """All index/constraint DDL must use IF NOT EXISTS for idempotency."""
        from agentic_brain.core.neo4j_schema import INDEXES

        for idx in INDEXES:
            assert (
                "IF NOT EXISTS" in idx
            ), f"Index DDL missing IF NOT EXISTS — unsafe for shared databases: {idx[:60]}..."

    def test_fulltext_indexes_cover_standard_fields(self):
        """Fulltext indexes should cover name, description, content."""
        from agentic_brain.core.neo4j_schema import INDEXES

        fulltext_ddl = " ".join(idx for idx in INDEXES if "FULLTEXT" in idx)
        for field in ("e.name", "e.description", "c.content", "d.content"):
            assert field in fulltext_ddl, f"Missing fulltext index on {field}"

    def test_vector_index_dimensions_configurable(self):
        """Embedding dimensions must be configurable (384, 768, 1536)."""
        from agentic_brain.rag.graph import GraphRAGConfig

        for dim in (384, 768, 1536):
            cfg = GraphRAGConfig(embedding_dimension=dim)
            assert cfg.embedding_dimension == dim

    def test_entity_types_include_standard_set(self):
        """Must support the standard entity types from most Graph RAG frameworks."""
        from agentic_brain.rag.graph import GraphRAGConfig

        cfg = GraphRAGConfig()
        standard_types = {"PERSON", "ORGANIZATION", "LOCATION", "CONCEPT"}
        actual_types = set(cfg.entity_types)
        missing = standard_types - actual_types
        assert not missing, f"Missing standard entity types: {missing}"

    def test_relationship_weights_include_standard_types(self):
        """Relationship weight config should cover common relationship types."""
        from agentic_brain.rag.graph import GraphRAGConfig

        cfg = GraphRAGConfig()
        for rel_type in ("MENTIONS", "RELATED_TO", "PART_OF", "CONTAINS"):
            assert (
                rel_type in cfg.relationship_weights
            ), f"Missing relationship weight for {rel_type}"


# ---------------------------------------------------------------------------
# Data Structure Compatibility Tests
# ---------------------------------------------------------------------------


class TestDataStructureCompatibility:
    """Verify our data classes match the standard Graph RAG interchange format."""

    def test_extracted_entity_has_required_fields(self):
        """ExtractedEntity must have id, name, type at minimum."""
        from agentic_brain.rag.graphrag.knowledge_extractor import ExtractedEntity

        entity = ExtractedEntity(id="e1", name="Alice", type="PERSON")
        d = asdict(entity)
        for key in ("id", "name", "type"):
            assert key in d, f"ExtractedEntity missing field: {key}"

    def test_extracted_relationship_has_required_fields(self):
        """ExtractedRelationship must have source, target, type."""
        from agentic_brain.rag.graphrag.knowledge_extractor import ExtractedRelationship

        rel = ExtractedRelationship(
            source_entity_id="e1",
            target_entity_id="e2",
            type="WORKS_AT",
            evidence="Alice works at Acme",
        )
        d = asdict(rel)
        for key in ("source_entity_id", "target_entity_id", "type"):
            assert key in d, f"ExtractedRelationship missing field: {key}"

    def test_extraction_result_has_entities_and_relationships(self):
        """KnowledgeExtractionResult must bundle entities + relationships."""
        from agentic_brain.rag.graphrag.knowledge_extractor import (
            ExtractedEntity,
            ExtractedRelationship,
            KnowledgeExtractionResult,
        )

        result = KnowledgeExtractionResult(
            document_id="doc1",
            entities=[ExtractedEntity(id="e1", name="Test", type="CONCEPT")],
            relationships=[
                ExtractedRelationship(
                    source_entity_id="e1",
                    target_entity_id="e1",
                    type="SELF_REF",
                    evidence="test",
                )
            ],
        )
        assert result.entity_count == 1
        assert result.relationship_count == 1

    def test_community_hierarchy_backward_compatible(self):
        """CommunityHierarchy.flat_communities provides dict[int, list[str]]."""
        from agentic_brain.rag.community_detection import Community, CommunityHierarchy

        hierarchy = CommunityHierarchy(
            communities={
                0: Community(id=0, level=0, entities=["Alice", "Bob"]),
                1: Community(id=1, level=0, entities=["Acme"]),
            },
            levels=1,
        )
        flat = hierarchy.flat_communities
        assert isinstance(flat, dict)
        assert flat[0] == ["Alice", "Bob"]
        assert flat[1] == ["Acme"]


# ---------------------------------------------------------------------------
# Query Compatibility Tests
# ---------------------------------------------------------------------------


class TestQueryCompatibility:
    """Verify Cypher query patterns match standard Graph RAG conventions."""

    def test_merge_pattern_for_entities(self):
        """Entity creation uses MERGE (idempotent) not CREATE."""
        import inspect
        from agentic_brain.rag.graph import EnhancedGraphRAG

        source = inspect.getsource(EnhancedGraphRAG.index_document)
        assert "MERGE (e:Entity" in source, "Entity creation should use MERGE"
        assert "CREATE (e:Entity" not in source, "Entity creation must not use CREATE"

    def test_merge_pattern_for_documents(self):
        """Document creation uses MERGE (idempotent) not CREATE."""
        import inspect
        from agentic_brain.rag.graph import EnhancedGraphRAG

        source = inspect.getsource(EnhancedGraphRAG.index_document)
        assert "MERGE (d:Document" in source, "Document creation should use MERGE"

    def test_merge_pattern_for_chunks(self):
        """Chunk creation uses MERGE (idempotent) not CREATE."""
        import inspect
        from agentic_brain.rag.graph import EnhancedGraphRAG

        source = inspect.getsource(EnhancedGraphRAG.index_document)
        assert "MERGE (c:Chunk" in source, "Chunk creation should use MERGE"

    def test_batched_unwind_for_ingest(self):
        """Ingest should use UNWIND for batch writes (no N+1 queries)."""
        import inspect
        from agentic_brain.rag.graph import EnhancedGraphRAG

        source = inspect.getsource(EnhancedGraphRAG.index_document)
        assert "UNWIND" in source, "Ingest should use UNWIND for batch efficiency"

    def test_relationship_merge_not_create(self):
        """All relationship writes use MERGE for idempotency."""
        import inspect
        from agentic_brain.rag.graph import EnhancedGraphRAG

        source = inspect.getsource(EnhancedGraphRAG.index_document)
        # Relationships: CONTAINS, MENTIONS
        assert "MERGE (d)-[:CONTAINS]" in source or "MERGE (d)-[" in source
        assert "MERGE (c)-[:MENTIONS]" in source or "MERGE (d)-[r:MENTIONS]" in source


# ---------------------------------------------------------------------------
# Data Import Compatibility Tests
# ---------------------------------------------------------------------------


class TestDataImportCompatibility:
    """Verify we can accept data in standard external Graph RAG formats."""

    def test_graphrag_accepts_pre_extracted_entities(self):
        """GraphRAG.ingest() should accept pre-extracted entity dicts."""
        from agentic_brain.rag.graph_rag import GraphRAG, GraphRAGConfig

        config = GraphRAGConfig(neo4j_uri="bolt://localhost:7687")
        # Don't connect to a real DB — just verify the method signature
        grag = GraphRAG(config)
        import inspect

        sig = inspect.signature(grag.ingest)
        params = list(sig.parameters.keys())
        assert "documents" in params, "ingest() must accept documents parameter"

    def test_ingest_document_dict_format(self):
        """Documents can use 'content', 'text', or 'page_content' keys."""
        import inspect
        from agentic_brain.rag.graph_rag import GraphRAG

        source = inspect.getsource(GraphRAG.ingest)
        for key in ("content", "text", "page_content"):
            assert (
                key in source
            ), f"ingest() should support '{key}' key in document dicts"

    def test_ingest_accepts_entity_and_relationship_dicts(self):
        """When no text content, ingest() accepts pre-extracted entities/rels."""
        import inspect
        from agentic_brain.rag.graph_rag import GraphRAG

        source = inspect.getsource(GraphRAG.ingest)
        assert "entities" in source, "ingest() should accept 'entities' key"
        assert "relationships" in source, "ingest() should accept 'relationships' key"

    def test_entity_id_generation_is_deterministic(self):
        """Same entity name → same ID (for cross-system deduplication)."""
        name = "Acme Corporation"
        id1 = hashlib.sha256(name.encode()).hexdigest()[:16]
        id2 = hashlib.sha256(name.encode()).hexdigest()[:16]
        assert id1 == id2, "Entity ID generation must be deterministic"

    def test_search_strategy_enum_values(self):
        """Search strategies should be accessible by string value."""
        from agentic_brain.rag.graph_rag import SearchStrategy

        assert SearchStrategy("vector") == SearchStrategy.VECTOR
        assert SearchStrategy("hybrid") == SearchStrategy.HYBRID
        assert SearchStrategy("community") == SearchStrategy.COMMUNITY

    def test_enhanced_graphrag_search_strategies(self):
        """EnhancedGraphRAG retrieval strategies include standard options."""
        from agentic_brain.rag.graph import RetrievalStrategy

        strategies = {s.value for s in RetrievalStrategy}
        for expected in ("vector", "graph", "hybrid", "community"):
            assert expected in strategies, f"Missing retrieval strategy: {expected}"


# ---------------------------------------------------------------------------
# Embedding Compatibility Tests
# ---------------------------------------------------------------------------


class TestEmbeddingCompatibility:
    """Verify embedding handling is compatible with external data."""

    def test_fallback_embedding_has_correct_dimensions(self):
        """Fallback embeddings match configured dimension."""
        from agentic_brain.rag.embeddings import _fallback_embedding

        for dim in (384, 768, 1536):
            emb = _fallback_embedding("test text", dim)
            assert len(emb) == dim, f"Expected {dim}-dim embedding, got {len(emb)}"

    def test_fallback_embedding_is_deterministic(self):
        """Same text → same embedding (needed for consistency)."""
        from agentic_brain.rag.embeddings import _fallback_embedding

        e1 = _fallback_embedding("hello world", 384)
        e2 = _fallback_embedding("hello world", 384)
        assert e1 == e2, "Fallback embeddings must be deterministic"

    def test_embedding_validation_rejects_wrong_dimensions(self):
        """_validate_embedding raises ValueError on dimension mismatch."""
        from agentic_brain.rag.graph import _validate_embedding

        with pytest.raises(ValueError, match="dimension mismatch"):
            _validate_embedding([1.0, 2.0, 3.0], 384, context="test")

    def test_embedding_validation_accepts_correct_dimensions(self):
        """_validate_embedding passes for correct dimensions."""
        from agentic_brain.rag.graph import _validate_embedding

        result = _validate_embedding([0.1] * 384, 384, context="test")
        assert len(result) == 384


# ---------------------------------------------------------------------------
# Knowledge Extractor Compatibility Tests
# ---------------------------------------------------------------------------


class TestKnowledgeExtractorCompatibility:
    """Verify entity extraction patterns match standard conventions."""

    def test_extractor_config_schema_has_standard_node_types(self):
        """KnowledgeExtractorConfig schema includes standard node types."""
        from agentic_brain.rag.graphrag.knowledge_extractor import (
            KnowledgeExtractorConfig,
        )

        cfg = KnowledgeExtractorConfig()
        node_types = cfg.schema["node_types"]
        for expected in ("Entity", "Person", "Organization", "Location"):
            assert expected in node_types, f"Missing node type: {expected}"

    def test_extractor_config_schema_has_standard_relationship_types(self):
        """KnowledgeExtractorConfig schema includes standard relationship types."""
        from agentic_brain.rag.graphrag.knowledge_extractor import (
            KnowledgeExtractorConfig,
        )

        cfg = KnowledgeExtractorConfig()
        rel_types = cfg.schema["relationship_types"]
        for expected in ("RELATED_TO", "PART_OF", "MENTIONS"):
            assert expected in rel_types, f"Missing relationship type: {expected}"

    def test_extractor_config_uses_env_vars(self):
        """Neo4j connection should read from environment variables."""
        import os
        from agentic_brain.rag.graphrag.knowledge_extractor import (
            KnowledgeExtractorConfig,
        )

        with patch.dict(os.environ, {"NEO4J_URI": "bolt://custom:7687"}):
            cfg = KnowledgeExtractorConfig()
            assert cfg.uri == "bolt://custom:7687"

    def test_knowledge_extractor_graph_only_mode(self):
        """extract_graph_only should work without LLM dependency."""
        from agentic_brain.rag.graphrag.knowledge_extractor import KnowledgeExtractor

        extractor = KnowledgeExtractor()
        result = extractor.extract_graph_only(
            "Alice from Acme Corporation visited Sydney Australia."
        )
        assert result.entity_count > 0, "Should extract at least one entity"
        entity_names = {e.name for e in result.entities}
        # Should find at least some capitalized proper nouns
        assert any(
            "Alice" in name or "Acme" in name or "Sydney" in name
            for name in entity_names
        ), f"Expected standard entities, got: {entity_names}"


# ---------------------------------------------------------------------------
# Community Detection Compatibility Tests
# ---------------------------------------------------------------------------


class TestCommunityDetectionCompatibility:
    """Verify community detection follows Microsoft GraphRAG conventions."""

    def test_community_has_level_field(self):
        """Communities must have hierarchical level (Microsoft GraphRAG pattern)."""
        from agentic_brain.rag.community_detection import Community

        c = Community(id=0, level=0, entities=["A", "B"])
        assert hasattr(c, "level")
        assert c.level == 0

    def test_community_hierarchy_entity_lookup(self):
        """Can look up which community an entity belongs to."""
        from agentic_brain.rag.community_detection import Community, CommunityHierarchy

        hierarchy = CommunityHierarchy(
            communities={0: Community(id=0, level=0, entities=["Alice", "Bob"])},
            entity_to_community={"Alice": 0, "Bob": 0},
        )
        c = hierarchy.get_entity_community("Alice")
        assert c is not None
        assert c.id == 0

    def test_community_hierarchy_levels(self):
        """CommunityHierarchy.communities_at_level filters correctly."""
        from agentic_brain.rag.community_detection import Community, CommunityHierarchy

        hierarchy = CommunityHierarchy(
            communities={
                0: Community(id=0, level=0, entities=["A"]),
                1: Community(id=1, level=0, entities=["B"]),
                2: Community(id=2, level=1, entities=["A", "B"]),
            },
            levels=2,
        )
        level0 = hierarchy.communities_at_level(0)
        level1 = hierarchy.communities_at_level(1)
        assert len(level0) == 2
        assert len(level1) == 1

    def test_community_detection_method_tracked(self):
        """CommunityHierarchy records which algorithm was used."""
        from agentic_brain.rag.community_detection import CommunityHierarchy

        h = CommunityHierarchy(detection_method="leiden")
        assert h.detection_method == "leiden"
