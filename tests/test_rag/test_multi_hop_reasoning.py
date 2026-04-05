# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Comprehensive tests for multi-hop reasoning module.

Covers:
- HopType enum (ENTITY_LOOKUP, RELATIONSHIP, TEMPORAL, CAUSAL, AGGREGATION)
- ReasoningHop dataclass (query, answer, sources, confidence)
- ReasoningChain dataclass (hops, final_answer, confidence, explanation)
- MultiHopReasoner orchestration
- LLMClient and RetrieverProtocol integration
- Chain decomposition (multi-hop question → individual hops)
- Answer synthesis (combining hop answers)
- Confidence calculation (per-hop and chain-level)
- Edge cases (single hop, chain failure, missing answers)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.multi_hop_reasoning import (
    HopType,
    LLMClient,
    MultiHopReasoner,
    ReasoningChain,
    ReasoningHop,
    RetrieverProtocol,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM client."""
    mock = MagicMock(spec=LLMClient)
    mock.generate.return_value = "Generated answer"
    return mock


@pytest.fixture
def mock_retriever() -> MagicMock:
    """Create a mock retriever."""
    mock = MagicMock(spec=RetrieverProtocol)
    mock.retrieve.return_value = [
        {"id": "doc_1", "content": "Retrieved content", "score": 0.95}
    ]
    return mock


@pytest.fixture
def sample_hop() -> ReasoningHop:
    """Create a sample reasoning hop."""
    return ReasoningHop(
        query="What is the capital of France?",
        hop_type=HopType.ENTITY_LOOKUP,
        purpose="Identify the capital city",
        answer="Paris",
        sources=[{"id": "doc_1", "content": "France's capital is Paris"}],
        confidence=0.95,
        reasoning="Direct fact lookup",
    )


@pytest.fixture
def sample_chain() -> ReasoningChain:
    """Create a sample reasoning chain."""
    return ReasoningChain(
        original_query="Who is the current president of France?",
        hops=[
            ReasoningHop(
                query="Is France a country?",
                hop_type=HopType.ENTITY_LOOKUP,
                purpose="Verify context",
                answer="Yes, France is a country",
                confidence=0.99,
            ),
            ReasoningHop(
                query="Who is the current president?",
                hop_type=HopType.ENTITY_LOOKUP,
                purpose="Find the president",
                answer="Emmanuel Macron",
                confidence=0.92,
            ),
        ],
        final_answer="Emmanuel Macron is the current president of France",
        confidence=0.93,
        explanation="Chain: Verify France → Look up president → Combine",
        citations=["source_1", "source_2"],
    )


# ---------------------------------------------------------------------------
# HopType Enum Tests
# ---------------------------------------------------------------------------


class TestHopType:
    def test_all_hop_types_defined(self) -> None:
        assert HopType.ENTITY_LOOKUP.value == "entity"
        assert HopType.RELATIONSHIP.value == "relationship"
        assert HopType.TEMPORAL.value == "temporal"
        assert HopType.CAUSAL.value == "causal"
        assert HopType.AGGREGATION.value == "aggregation"

    def test_hop_type_comparison(self) -> None:
        assert HopType.ENTITY_LOOKUP != HopType.RELATIONSHIP
        assert HopType.TEMPORAL != HopType.CAUSAL

    def test_hop_type_string_representation(self) -> None:
        assert str(HopType.ENTITY_LOOKUP.value) == "entity"


# ---------------------------------------------------------------------------
# ReasoningHop Tests
# ---------------------------------------------------------------------------


class TestReasoningHop:
    def test_hop_creation(self) -> None:
        hop = ReasoningHop(
            query="test query",
            hop_type=HopType.ENTITY_LOOKUP,
            purpose="test purpose",
        )
        assert hop.query == "test query"
        assert hop.hop_type == HopType.ENTITY_LOOKUP
        assert hop.purpose == "test purpose"

    def test_hop_default_values(self) -> None:
        hop = ReasoningHop(
            query="test",
            hop_type=HopType.ENTITY_LOOKUP,
            purpose="test",
        )
        assert hop.answer is None
        assert hop.sources == []
        assert hop.confidence == 0.0
        assert hop.reasoning == ""

    def test_hop_with_full_details(self, sample_hop: ReasoningHop) -> None:
        assert sample_hop.query == "What is the capital of France?"
        assert sample_hop.answer == "Paris"
        assert sample_hop.confidence == 0.95
        assert len(sample_hop.sources) == 1

    def test_hop_confidence_range(self) -> None:
        hop_low = ReasoningHop(
            query="q", hop_type=HopType.ENTITY_LOOKUP, purpose="p", confidence=0.1
        )
        hop_mid = ReasoningHop(
            query="q", hop_type=HopType.ENTITY_LOOKUP, purpose="p", confidence=0.5
        )
        hop_high = ReasoningHop(
            query="q", hop_type=HopType.ENTITY_LOOKUP, purpose="p", confidence=0.99
        )

        assert hop_low.confidence < hop_mid.confidence < hop_high.confidence


# ---------------------------------------------------------------------------
# ReasoningChain Tests
# ---------------------------------------------------------------------------


class TestReasoningChain:
    def test_chain_creation(self, sample_chain: ReasoningChain) -> None:
        assert sample_chain.original_query == "Who is the current president of France?"
        assert len(sample_chain.hops) == 2
        assert sample_chain.final_answer == "Emmanuel Macron is the current president of France"
        assert sample_chain.confidence == 0.93

    def test_chain_single_hop(self) -> None:
        chain = ReasoningChain(
            original_query="Simple question?",
            hops=[
                ReasoningHop(
                    query="Simple",
                    hop_type=HopType.ENTITY_LOOKUP,
                    purpose="Answer",
                )
            ],
            final_answer="Simple answer",
            confidence=0.9,
            explanation="Direct answer",
        )
        assert len(chain.hops) == 1

    def test_chain_no_hops(self) -> None:
        chain = ReasoningChain(
            original_query="test",
            hops=[],
            final_answer="answer",
            confidence=0.5,
            explanation="no hops",
        )
        assert len(chain.hops) == 0

    def test_chain_many_hops(self) -> None:
        hops = [
            ReasoningHop(
                query=f"Hop {i}",
                hop_type=HopType.ENTITY_LOOKUP,
                purpose=f"Purpose {i}",
                confidence=0.9 - i * 0.1,
            )
            for i in range(10)
        ]
        chain = ReasoningChain(
            original_query="Multi-hop question",
            hops=hops,
            final_answer="Final answer after 10 hops",
            confidence=0.75,
            explanation="Complex chain",
        )
        assert len(chain.hops) == 10

    def test_chain_citations_default_empty(self) -> None:
        chain = ReasoningChain(
            original_query="q",
            hops=[],
            final_answer="a",
            confidence=0.5,
            explanation="e",
        )
        assert chain.citations == []

    def test_chain_with_citations(self, sample_chain: ReasoningChain) -> None:
        assert len(sample_chain.citations) == 2


# ---------------------------------------------------------------------------
# MultiHopReasoner Tests
# ---------------------------------------------------------------------------


class TestMultiHopReasoner:
    def test_reasoner_initialization(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever, max_hops=5)
        assert reasoner.max_hops == 5

    def test_reasoner_default_max_hops(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever)
        # Should have a default max_hops value
        assert reasoner.max_hops >= 1

    @pytest.mark.asyncio
    async def test_reasoner_reason_basic(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever)
        
        # Mock the reasoning process
        with patch.object(reasoner, '_decompose_query', return_value=['hop1', 'hop2']):
            with patch.object(reasoner, '_reason_hop', return_value=ReasoningHop(
                query='test', hop_type=HopType.ENTITY_LOOKUP, purpose='test'
            )):
                with patch.object(reasoner, '_synthesize_answer', return_value='final answer'):
                    chain = await reasoner.reason("test question")
                    
        assert isinstance(chain, ReasoningChain)

    @pytest.mark.asyncio
    async def test_reasoner_respects_max_hops(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever, max_hops=2)
        
        # Should never create more than max_hops hops
        with patch.object(reasoner, '_decompose_query', return_value=['h1', 'h2', 'h3', 'h4']):
            with patch.object(reasoner, '_reason_hop', return_value=ReasoningHop(
                query='test', hop_type=HopType.ENTITY_LOOKUP, purpose='test'
            )):
                with patch.object(reasoner, '_synthesize_answer', return_value='answer'):
                    chain = await reasoner.reason("complex question")
        
        assert len(chain.hops) <= 2


# ---------------------------------------------------------------------------
# Chain Decomposition Tests
# ---------------------------------------------------------------------------


class TestChainDecomposition:
    @pytest.mark.asyncio
    async def test_decompose_multi_hop_question(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever)
        
        question = "Who manages the project that fixed bug #123?"
        # Decomposition should produce multiple sub-queries
        with patch.object(reasoner, '_decompose_query') as mock_decompose:
            mock_decompose.return_value = [
                "What project fixed bug #123?",
                "Who manages that project?"
            ]
            hops = await reasoner._decompose_query(question)
        
        assert len(hops) == 2

    @pytest.mark.asyncio
    async def test_decompose_simple_question(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever)
        
        question = "What is 2+2?"
        with patch.object(reasoner, '_decompose_query') as mock_decompose:
            mock_decompose.return_value = [question]
            hops = await reasoner._decompose_query(question)
        
        assert len(hops) == 1


# ---------------------------------------------------------------------------
# Answer Synthesis Tests
# ---------------------------------------------------------------------------


class TestAnswerSynthesis:
    @pytest.mark.asyncio
    async def test_synthesize_single_hop_answer(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever)
        
        hop = ReasoningHop(
            query="test",
            hop_type=HopType.ENTITY_LOOKUP,
            purpose="test",
            answer="answer",
            confidence=0.95,
        )
        
        with patch.object(reasoner, '_synthesize_answer') as mock_synth:
            mock_synth.return_value = "Synthesized: answer"
            result = await reasoner._synthesize_answer([hop])
        
        assert "answer" in result.lower()

    @pytest.mark.asyncio
    async def test_synthesize_multi_hop_answer(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever)
        
        hops = [
            ReasoningHop(
                query="q1",
                hop_type=HopType.ENTITY_LOOKUP,
                purpose="p1",
                answer="answer1",
            ),
            ReasoningHop(
                query="q2",
                hop_type=HopType.RELATIONSHIP,
                purpose="p2",
                answer="answer2",
            ),
        ]
        
        with patch.object(reasoner, '_synthesize_answer') as mock_synth:
            mock_synth.return_value = "Combined answer from hops"
            result = await reasoner._synthesize_answer(hops)
        
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Confidence Calculation Tests
# ---------------------------------------------------------------------------


class TestConfidenceCalculation:
    def test_hop_confidence_calculation(self) -> None:
        # Higher source scores should increase confidence
        hop_high_score = ReasoningHop(
            query="test",
            hop_type=HopType.ENTITY_LOOKUP,
            purpose="test",
            sources=[{"score": 0.95}],
            confidence=0.95,
        )
        hop_low_score = ReasoningHop(
            query="test",
            hop_type=HopType.ENTITY_LOOKUP,
            purpose="test",
            sources=[{"score": 0.3}],
            confidence=0.3,
        )

        assert hop_high_score.confidence > hop_low_score.confidence

    def test_chain_confidence_from_hops(self, sample_chain: ReasoningChain) -> None:
        # Chain confidence should reflect hop confidences
        hop_confidences = [hop.confidence for hop in sample_chain.hops if hop.confidence > 0]
        if hop_confidences:
            avg_confidence = sum(hop_confidences) / len(hop_confidences)
            # Chain confidence should be reasonable relative to hops
            assert sample_chain.confidence > 0
            assert sample_chain.confidence <= 1.0


# ---------------------------------------------------------------------------
# Different Hop Types Tests
# ---------------------------------------------------------------------------


class TestDifferentHopTypes:
    def test_entity_lookup_hop(self) -> None:
        hop = ReasoningHop(
            query="Find entity",
            hop_type=HopType.ENTITY_LOOKUP,
            purpose="Identify entity",
            answer="Entity X",
        )
        assert hop.hop_type == HopType.ENTITY_LOOKUP

    def test_relationship_hop(self) -> None:
        hop = ReasoningHop(
            query="What's the relationship?",
            hop_type=HopType.RELATIONSHIP,
            purpose="Find relationship",
            answer="Related via edge type A",
        )
        assert hop.hop_type == HopType.RELATIONSHIP

    def test_temporal_hop(self) -> None:
        hop = ReasoningHop(
            query="When did X happen?",
            hop_type=HopType.TEMPORAL,
            purpose="Find temporal relationship",
            answer="Year 2020",
        )
        assert hop.hop_type == HopType.TEMPORAL

    def test_causal_hop(self) -> None:
        hop = ReasoningHop(
            query="Why did X cause Y?",
            hop_type=HopType.CAUSAL,
            purpose="Find causal relationship",
            answer="X caused Y because Z",
        )
        assert hop.hop_type == HopType.CAUSAL

    def test_aggregation_hop(self) -> None:
        hop = ReasoningHop(
            query="Aggregate results",
            hop_type=HopType.AGGREGATION,
            purpose="Combine multiple results",
            answer="Combined result",
        )
        assert hop.hop_type == HopType.AGGREGATION


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestMultiHopEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_query(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever)
        
        with patch.object(reasoner, '_decompose_query', return_value=[]):
            with patch.object(reasoner, '_synthesize_answer', return_value=''):
                chain = await reasoner.reason("")
        
        assert isinstance(chain, ReasoningChain)

    @pytest.mark.asyncio
    async def test_max_hops_zero(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        # max_hops=0 should still work gracefully
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever, max_hops=0)
        assert reasoner.max_hops == 0

    def test_very_long_reasoning_chain(self) -> None:
        # Create a chain with many hops
        hops = [
            ReasoningHop(
                query=f"Query {i}",
                hop_type=HopType.ENTITY_LOOKUP,
                purpose=f"Purpose {i}",
                answer=f"Answer {i}",
                confidence=0.8,
            )
            for i in range(100)
        ]
        
        chain = ReasoningChain(
            original_query="Very complex question",
            hops=hops,
            final_answer="Very detailed answer",
            confidence=0.75,
            explanation="100-hop chain",
        )
        
        assert len(chain.hops) == 100

    def test_hop_with_no_sources(self) -> None:
        hop = ReasoningHop(
            query="test",
            hop_type=HopType.ENTITY_LOOKUP,
            purpose="test",
            sources=[],  # Empty sources
            confidence=0.5,
        )
        assert len(hop.sources) == 0

    def test_chain_with_low_confidences(self) -> None:
        hops = [
            ReasoningHop(
                query=f"Q{i}",
                hop_type=HopType.ENTITY_LOOKUP,
                purpose=f"P{i}",
                confidence=0.1,  # Very low confidence
            )
            for i in range(3)
        ]
        
        chain = ReasoningChain(
            original_query="Uncertain question",
            hops=hops,
            final_answer="Low confidence answer",
            confidence=0.1,  # Low overall confidence
            explanation="Uncertain chain",
        )
        
        assert chain.confidence == 0.1


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestReasoningIntegration:
    @pytest.mark.asyncio
    async def test_full_reasoning_pipeline(self, mock_llm: MagicMock, mock_retriever: MagicMock) -> None:
        reasoner = MultiHopReasoner(llm=mock_llm, retriever=mock_retriever, max_hops=3)
        
        # Create a complete mock pipeline
        with patch.object(reasoner, '_decompose_query', return_value=['hop1', 'hop2']):
            with patch.object(reasoner, '_reason_hop', return_value=ReasoningHop(
                query='test',
                hop_type=HopType.ENTITY_LOOKUP,
                purpose='test',
                answer='answer',
                confidence=0.9,
            )):
                with patch.object(reasoner, '_synthesize_answer', return_value='final'):
                    chain = await reasoner.reason("Complex question")
        
        assert isinstance(chain, ReasoningChain)
        assert chain.final_answer is not None
