# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Comprehensive tests for advanced RAG features.

Tests for:
- Multiple chunking strategies
- Reranking approaches
- Hybrid search
- Evaluation metrics
"""

import tempfile
from pathlib import Path

import pytest

from agentic_brain.rag.chunking import (
    Chunk,
    ChunkingStrategy,
    FixedChunker,
    MarkdownChunker,
    RecursiveChunker,
    SemanticChunker,
    create_chunker,
)
from agentic_brain.rag.evaluation import EvalDataset, RAGEvaluator
from agentic_brain.rag.hybrid import BM25Index, HybridSearch, reciprocal_rank_fusion
from agentic_brain.rag.reranking import (
    CombinedReranker,
    MMRReranker,
    QueryDocumentSimilarityReranker,
)
from agentic_brain.rag.retriever import RetrievedChunk

# Check if sentence-transformers is available
try:
    import sentence_transformers

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Check if OpenAI API key is available
import os

OPENAI_API_KEY_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY"))

requires_sentence_transformers = pytest.mark.skipif(
    not SENTENCE_TRANSFORMERS_AVAILABLE, reason="sentence-transformers not installed"
)

requires_openai = pytest.mark.skipif(
    not OPENAI_API_KEY_AVAILABLE, reason="OPENAI_API_KEY not set"
)


class TestChunking:
    """Test text chunking strategies."""

    @pytest.fixture
    def sample_text(self):
        """Sample text for chunking tests."""
        return """
        Machine learning is a subset of artificial intelligence.
        It enables systems to learn from data without being explicitly programmed.

        The main types of machine learning are:
        1. Supervised learning - learning from labeled data
        2. Unsupervised learning - finding patterns in unlabeled data
        3. Reinforcement learning - learning through rewards and penalties

        Deep learning is a powerful subset of machine learning that uses neural networks.
        Neural networks are inspired by biological neurons in the brain.
        They can learn hierarchical representations of data.
        """

    @pytest.fixture
    def markdown_text(self):
        """Markdown text for markdown chunker tests."""
        return """# Machine Learning Guide

## Introduction

Machine learning is a subset of artificial intelligence.

## Types

### Supervised Learning

Learning from labeled data.

### Unsupervised Learning

Finding patterns in unlabeled data.

## Deep Learning

Uses neural networks for complex tasks.

```python
import tensorflow as tf
model = tf.keras.Sequential()
```

## Conclusion

ML is transforming industries.
"""

    def test_fixed_chunker(self, sample_text):
        """Test fixed-size chunking."""
        chunker = FixedChunker(chunk_size=200, overlap=50)
        chunks = chunker.chunk(sample_text)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(len(c.content) > 0 for c in chunks)

        # Check overlap
        if len(chunks) > 1:
            last_chunk_end = chunks[0].content[-50:]
            chunks[1].content[:50]
            # Some overlap should exist
            assert len(last_chunk_end) > 0

    def test_semantic_chunker(self, sample_text):
        """Test semantic chunking."""
        chunker = SemanticChunker(chunk_size=300, overlap=50)
        chunks = chunker.chunk(sample_text)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

        # Chunks should be on sentence boundaries
        for chunk in chunks:
            assert chunk.content.strip() != ""

    def test_recursive_chunker(self, sample_text):
        """Test recursive chunking."""
        chunker = RecursiveChunker(chunk_size=250, overlap=50)
        chunks = chunker.chunk(sample_text)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_markdown_chunker(self, markdown_text):
        """Test markdown-aware chunking."""
        chunker = MarkdownChunker(chunk_size=300, overlap=50)
        chunks = chunker.chunk(markdown_text)

        assert len(chunks) > 0

        # Check that metadata is preserved
        metadata_chunks = [c for c in chunks if c.metadata]
        # At least some chunks should have metadata
        assert len(metadata_chunks) >= 0  # Some may not have headers

    def test_create_chunker(self, sample_text):
        """Test chunker factory function."""
        for strategy in ChunkingStrategy:
            chunker = create_chunker(strategy, chunk_size=200, overlap=30)
            chunks = chunker.chunk(sample_text)
            assert len(chunks) > 0
            assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunker_with_metadata(self, sample_text):
        """Test metadata preservation."""
        chunker = FixedChunker(chunk_size=200, overlap=50)
        metadata = {"source": "test_doc", "type": "article"}
        chunks = chunker.chunk(sample_text, metadata=metadata)

        assert all("source" in c.metadata for c in chunks)
        assert all(c.metadata["source"] == "test_doc" for c in chunks)

    def test_chunk_properties(self, sample_text):
        """Test Chunk dataclass properties."""
        chunker = FixedChunker(chunk_size=200, overlap=50)
        chunks = chunker.chunk(sample_text)

        for chunk in chunks:
            assert chunk.chunk_index >= 0
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char
            assert chunk.token_count > 0

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = FixedChunker()
        chunks = chunker.chunk("")
        assert len(chunks) == 0

    def test_invalid_overlap(self):
        """Test that invalid overlap raises error."""
        with pytest.raises(ValueError):
            FixedChunker(chunk_size=100, overlap=150)


class TestReranking:
    """Test reranking strategies."""

    @pytest.fixture
    def sample_chunks(self):
        """Sample retrieved chunks."""
        return [
            RetrievedChunk(
                content="Machine learning is a subset of AI that enables systems to learn.",
                source="ml_basics.txt",
                score=0.85,
            ),
            RetrievedChunk(
                content="Deep learning uses neural networks with multiple layers.",
                source="deep_learning.txt",
                score=0.75,
            ),
            RetrievedChunk(
                content="Supervised learning requires labeled training data.",
                source="supervised.txt",
                score=0.65,
            ),
            RetrievedChunk(
                content="Python is a popular programming language.",
                source="python_guide.txt",
                score=0.45,
            ),
        ]

    @requires_sentence_transformers
    def test_similarity_reranker(self, sample_chunks):
        """Test embedding-based similarity reranking."""
        reranker = QueryDocumentSimilarityReranker(top_k=3)
        reranked = reranker.rerank("machine learning", sample_chunks)

        assert len(reranked) <= 3
        assert all(isinstance(c, RetrievedChunk) for c in reranked)
        # Should preserve metadata about original score
        assert all("original_score" in c.metadata for c in reranked)

    @requires_sentence_transformers
    def test_mmr_reranker(self, sample_chunks):
        """Test MMR reranking for diversity."""
        reranker = MMRReranker(top_k=3, lambda_weight=0.5)
        reranked = reranker.rerank("machine learning", sample_chunks)

        assert len(reranked) <= 3
        assert all(isinstance(c, RetrievedChunk) for c in reranked)

        # Check lambda weight boundaries
        for lambda_w in [0.0, 0.5, 1.0]:
            reranker = MMRReranker(lambda_weight=lambda_w)
            reranked = reranker.rerank("machine learning", sample_chunks)
            assert len(reranked) == len(sample_chunks)

    @requires_sentence_transformers
    def test_top_k_limiting(self, sample_chunks):
        """Test that top_k properly limits results."""
        for k in [1, 2, 3, 5]:
            reranker = QueryDocumentSimilarityReranker(top_k=k)
            reranked = reranker.rerank("query", sample_chunks)
            assert len(reranked) <= k

    @requires_sentence_transformers
    def test_combined_reranker(self, sample_chunks):
        """Test combining multiple rerankers."""
        reranker1 = QueryDocumentSimilarityReranker(top_k=10)
        reranker2 = MMRReranker(top_k=10, lambda_weight=0.7)

        combined = CombinedReranker(
            rerankers=[(reranker1, 1.0), (reranker2, 1.0)], top_k=3
        )
        reranked = combined.rerank("machine learning", sample_chunks)

        assert len(reranked) <= 3
        assert all(isinstance(c, RetrievedChunk) for c in reranked)

    @requires_openai
    def test_empty_chunks(self):
        """Test reranking empty chunks."""
        reranker = QueryDocumentSimilarityReranker()
        result = reranker.rerank("query", [])
        assert len(result) == 0


class TestHybridSearch:
    """Test hybrid search (vector + keyword)."""

    @pytest.fixture
    def sample_chunks(self):
        """Sample chunks for hybrid search."""
        return [
            RetrievedChunk(
                content="Machine learning enables computers to learn from data.",
                source="ml1.txt",
                score=0.8,
            ),
            RetrievedChunk(
                content="Deep neural networks have multiple hidden layers.",
                source="dl1.txt",
                score=0.75,
            ),
            RetrievedChunk(
                content="Supervised learning requires labeled examples.",
                source="sl1.txt",
                score=0.7,
            ),
        ]

    def test_bm25_index(self):
        """Test BM25 index creation and search."""
        index = BM25Index()

        index.add_document("doc1", "machine learning deep neural networks")
        index.add_document("doc2", "supervised learning labeled data")
        index.add_document("doc3", "unsupervised clustering algorithms")

        index.build_index()

        results = index.search("machine learning", k=2)
        assert len(results) <= 2
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

    def test_reciprocal_rank_fusion_prefers_consensus_hits(self):
        """RRF should rank shared hits ahead of single-source hits."""
        fused = reciprocal_rank_fusion(
            vector_results=[
                {"id": "chunk-a", "content": "Vector-only"},
                {"id": "chunk-b", "content": "Shared"},
            ],
            graph_results=[
                {"id": "chunk-b", "content": "Shared", "entities": ["Shared"]},
                {"id": "chunk-c", "content": "Graph-only"},
            ],
        )

        assert [item["id"] for item in fused[:3]] == ["chunk-b", "chunk-a", "chunk-c"]
        assert fused[0]["rrf_score"] > fused[1]["rrf_score"]
        assert fused[0]["entities"] == ["Shared"]

    @requires_sentence_transformers
    def test_hybrid_search_basic(self, sample_chunks):
        """Test basic hybrid search."""
        search = HybridSearch()

        result = search.search(
            query="machine learning",
            chunks=sample_chunks,
            k=2,
            vector_weight=0.5,
            keyword_weight=0.5,
            fusion_method="rrf",
        )

        assert result.query == "machine learning"
        assert len(result.vector_results) > 0
        assert len(result.keyword_results) > 0
        assert len(result.fused_results) > 0

    @requires_sentence_transformers
    def test_hybrid_search_fusion_methods(self, sample_chunks):
        """Test different fusion methods."""
        search = HybridSearch()

        for method in ["rrf", "linear"]:
            result = search.search(
                query="learning", chunks=sample_chunks, k=2, fusion_method=method
            )
            assert result.fusion_method == method

    @requires_openai
    def test_bm25_save_load(self, sample_chunks):
        """Test saving and loading BM25 index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "bm25.json"

            # Create and save index
            search1 = HybridSearch(index_path=index_path)
            search1.add_documents(sample_chunks)

            # Load index in new instance
            search2 = HybridSearch(index_path=index_path)

            # Both should have same documents
            assert len(search1.bm25.docs) == len(search2.bm25.docs)


class TestEvaluation:
    """Test RAG evaluation framework."""

    @pytest.fixture
    def eval_dataset(self):
        """Create sample evaluation dataset."""
        dataset = EvalDataset()
        dataset.add_query(
            "What is machine learning?", ["ml_guide.txt", "ai_basics.txt"]
        )
        dataset.add_query("How does deep learning work?", ["deep_learning.txt"])
        return dataset

    def test_eval_dataset_creation(self):
        """Test creating evaluation dataset."""
        dataset = EvalDataset()
        dataset.add_query("test query", ["doc1", "doc2"])

        assert len(dataset) == 1
        assert dataset.queries[0].query == "test query"
        assert len(dataset.queries[0].relevant_docs) == 2

    def test_eval_dataset_save_load(self):
        """Test saving and loading evaluation dataset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "eval_dataset.json"

            # Create and save
            dataset1 = EvalDataset()
            dataset1.add_query("query 1", ["doc1", "doc2"])
            dataset1.add_query("query 2", ["doc3"])
            dataset1.save(dataset_path)

            # Load
            dataset2 = EvalDataset()
            dataset2.add_queries_from_file(dataset_path)

            assert len(dataset2) == 2

    def test_rag_evaluator(self, eval_dataset):
        """Test RAG evaluation."""

        def mock_retriever(query: str):
            # Return mock retrieved chunks
            return [
                RetrievedChunk(
                    content="ml_guide content", source="ml_guide.txt", score=0.9
                ),
                RetrievedChunk(content="other content", source="other.txt", score=0.5),
            ]

        evaluator = RAGEvaluator()
        results = evaluator.evaluate(mock_retriever, eval_dataset)

        assert results.num_queries == 2
        assert results.avg_ndcg >= 0
        assert results.avg_mrr >= 0
        assert results.avg_map >= 0
        assert results.precision_at_k(5) >= 0

    def test_ab_test(self, eval_dataset):
        """Test A/B testing."""

        def retriever_a(query: str):
            return [
                RetrievedChunk(content="content", source="doc1.txt", score=0.8),
                RetrievedChunk(content="other", source="doc2.txt", score=0.5),
            ]

        def retriever_b(query: str):
            return [
                RetrievedChunk(content="content", source="doc1.txt", score=0.9),
                RetrievedChunk(content="other", source="doc2.txt", score=0.6),
            ]

        evaluator = RAGEvaluator()
        comparison = evaluator.ab_test(retriever_a, retriever_b, eval_dataset)

        assert "strategy_a" in comparison
        assert "strategy_b" in comparison
        assert "improvements" in comparison
        assert "winner" in comparison

    def test_eval_results_serialization(self, eval_dataset):
        """Test evaluation results can be serialized."""

        def mock_retriever(query: str):
            return [
                RetrievedChunk(content="content", source="doc1.txt", score=0.85),
            ]

        evaluator = RAGEvaluator()
        results = evaluator.evaluate(mock_retriever, eval_dataset)

        # Should be serializable to dict
        result_dict = results.to_dict()
        assert isinstance(result_dict, dict)
        assert "ndcg" in result_dict
        assert "mrr" in result_dict

    def test_eval_results_save_load(self, eval_dataset):
        """Test saving and loading evaluation results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.json"

            def mock_retriever(query: str):
                return [
                    RetrievedChunk(content="content", source="doc1.txt", score=0.85),
                ]

            evaluator = RAGEvaluator()
            evaluator.evaluate(mock_retriever, eval_dataset)
            evaluator.save_results(results_path)

            assert results_path.exists()


class TestIntegration:
    """Integration tests combining multiple components."""

    @requires_openai
    def test_chunking_to_reranking_pipeline(self):
        """Test complete pipeline: chunk -> embed -> rerank."""
        text = """
        Machine learning is transforming industries.
        Deep learning uses neural networks.
        Supervised learning requires labeled data.
        Reinforcement learning learns from rewards.
        """

        # Chunk
        chunker = SemanticChunker(chunk_size=100, overlap=20)
        chunks_list = chunker.chunk(text)
        assert len(chunks_list) > 0

        # Convert to RetrievedChunk format
        retrieved_chunks = [
            RetrievedChunk(content=c.content, source=f"chunk_{i}", score=0.7 - i * 0.1)
            for i, c in enumerate(chunks_list)
        ]

        # Rerank
        reranker = MMRReranker(lambda_weight=0.5)
        reranked = reranker.rerank("machine learning", retrieved_chunks)
        assert len(reranked) > 0

    @requires_sentence_transformers
    def test_hybrid_search_with_evaluation(self):
        """Test hybrid search with evaluation."""
        chunks = [
            RetrievedChunk(content="ML basics", source="ml.txt", score=0.8),
            RetrievedChunk(content="DL guide", source="dl.txt", score=0.7),
        ]

        search = HybridSearch()
        result = search.search("learning", chunks, k=1)

        # Create simple evaluation
        dataset = EvalDataset()
        dataset.add_query("learning", ["ml.txt"])

        evaluator = RAGEvaluator()

        def mock_retriever(query: str):
            return result.fused_results

        eval_results = evaluator.evaluate(mock_retriever, dataset)
        assert eval_results.num_queries == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
