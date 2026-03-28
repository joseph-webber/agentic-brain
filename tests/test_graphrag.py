# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.graphrag import (
    GraphQueryResult,
    KnowledgeExtractionResult,
    KnowledgeExtractor,
    KnowledgeExtractorConfig,
)


class FakeLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def generate(self, prompt: str, **kwargs):
        assert prompt
        return self._responses.pop(0)


@pytest.fixture
def mock_pool_session():
    session = MagicMock()
    session.run.return_value = []
    return session


@pytest.fixture
def extractor():
    return KnowledgeExtractor(
        KnowledgeExtractorConfig(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="Brain2026",
            database="neo4j",
        )
    )


def test_initialize_uses_shared_pool(extractor, mock_pool_session):
    mock_driver = MagicMock()

    with (
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.configure_neo4j_pool"
        ) as mock_configure,
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_driver",
            return_value=mock_driver,
        ),
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_session"
        ) as mock_get_session,
    ):
        mock_get_session.return_value.__enter__.return_value = mock_pool_session

        extractor.initialize()

    mock_configure.assert_called_once_with(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="Brain2026",
        database="neo4j",
    )
    mock_driver.verify_connectivity.assert_called_once()
    assert mock_pool_session.run.call_count >= 4


@pytest.mark.asyncio
async def test_extract_from_text_persists_entities_and_relationships(
    extractor, mock_pool_session
):
    mock_driver = MagicMock()

    with (
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_driver",
            return_value=mock_driver,
        ),
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_session"
        ) as mock_get_session,
    ):
        mock_get_session.return_value.__enter__.return_value = mock_pool_session

        result = await extractor.extract_from_text(
            "Alice works at Acme Corp in Adelaide. Alice mentors Bob at Acme Corp.",
            document_id="doc-1",
            use_graphrag_pipeline=False,
        )

    assert isinstance(result, KnowledgeExtractionResult)
    assert result.document_id == "doc-1"
    assert result.entity_count >= 3
    assert result.relationship_count >= 1
    assert result.pipeline_used is False
    assert result.metadata["pipeline"] == "heuristic"
    assert mock_pool_session.run.call_count >= 6


@pytest.mark.asyncio
async def test_extract_from_text_uses_builtin_llm_pipeline(mock_pool_session):
    mock_driver = MagicMock()
    extractor = KnowledgeExtractor(
        KnowledgeExtractorConfig(),
        llm=FakeLLM(
            [
                '{"entities":[{"name":"Paul Atreides","type":"Person"},{"name":"Caladan","type":"Location"}],"relationships":[{"source":"Paul Atreides","target":"Caladan","type":"RULES","evidence":"Paul Atreides rules Caladan."}]}'
            ]
        ),
    )

    with (
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_driver",
            return_value=mock_driver,
        ),
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_session"
        ) as mock_get_session,
    ):
        mock_get_session.return_value.__enter__.return_value = mock_pool_session

        result = await extractor.extract_from_text("Paul Atreides rules Caladan.")

    assert result.pipeline_used is True
    assert result.metadata["pipeline"] == "builtin_llm"
    assert {entity.name for entity in result.entities} == {"Paul Atreides", "Caladan"}
    assert result.relationships[0].type == "RULES"


def test_query_uses_text2cypher_when_llm_available(mock_pool_session):
    mock_driver = MagicMock()
    mock_pool_session.run.return_value = [
        {
            "content": "Alice works at Acme Corp",
            "entity": "Alice",
        }
    ]
    llm = FakeLLM(
        [
            '{"cypher":"MATCH (d:SourceDocument)-[:MENTIONS]->(e:Entity) WHERE toLower(e.name) CONTAINS $name RETURN d.content AS content, e.name AS entity","params":{"name":"alice"},"reasoning":"lookup by entity name"}'
        ]
    )
    extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), llm=llm)

    with (
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_driver",
            return_value=mock_driver,
        ),
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_session"
        ) as mock_get_session,
    ):
        mock_get_session.return_value.__enter__.return_value = mock_pool_session

        result = extractor.query("Where does Alice work?")

    assert isinstance(result, GraphQueryResult)
    assert result.mode == "text2cypher"
    assert result.results[0]["content"] == "Alice works at Acme Corp"
    assert result.metadata["params"] == {"name": "alice", "limit": 10}
    assert "LIMIT $limit" in result.metadata["cypher"]
    assert result.metadata["generator"] == "built_in_llm"


def test_query_falls_back_to_keyword_search_when_llm_is_unsafe(
    extractor, mock_pool_session
):
    mock_driver = MagicMock()
    mock_record = {
        "document_id": "doc-1",
        "content": "Alice works at Acme Corp",
        "entity": "Alice",
        "entity_type": "Person",
        "relationships": [
            {"related_entity": "Acme Corp", "relationship_type": "WORKS_AT"}
        ],
    }

    def run_side_effect(query, **kwargs):
        if "d.id AS document_id" in query:
            return [mock_record]
        return []

    mock_pool_session.run.side_effect = run_side_effect
    extractor = KnowledgeExtractor(
        KnowledgeExtractorConfig(),
        llm=FakeLLM(['{"cypher":"MATCH (n) DELETE n","params":{}}']),
    )

    with (
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_driver",
            return_value=mock_driver,
        ),
        patch(
            "agentic_brain.rag.graphrag.knowledge_extractor.get_neo4j_session"
        ) as mock_get_session,
    ):
        mock_get_session.return_value.__enter__.return_value = mock_pool_session
        result = extractor.query("Alice Acme")

    assert result.mode == "keyword_fallback"
    assert result.results[0]["entity"] == "Alice"
    assert "alice" in result.metadata["terms"]
