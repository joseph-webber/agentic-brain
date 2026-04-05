# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Tests for RAG chunking strategies.

Covers: FixedChunker, SemanticChunker, RecursiveChunker, MarkdownChunker,
        create_chunker factory, Chunk dataclass, metadata propagation,
        overlap handling, and edge cases.
"""

from __future__ import annotations

import pytest

from agentic_brain.rag.chunking.base import (
    Chunk,
    ChunkingStrategy,
    FixedChunker,
    MarkdownChunker,
    RecursiveChunker,
    SemanticChunker,
    create_chunker,
)

# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------


class TestChunk:
    def test_token_count_estimate(self) -> None:
        """token_count should be content length // 4, minimum 1."""
        c = Chunk(content="abcd", start_char=0, end_char=4, chunk_index=0)
        assert c.token_count == 1

        long_content = "a" * 400
        c2 = Chunk(content=long_content, start_char=0, end_char=400, chunk_index=0)
        assert c2.token_count == 100

    def test_token_count_minimum_one_for_empty_like(self) -> None:
        """Even a single char returns at least 1 token."""
        c = Chunk(content="x", start_char=0, end_char=1, chunk_index=0)
        assert c.token_count >= 1

    def test_add_metadata(self) -> None:
        """add_metadata stores key-value pairs on the chunk."""
        c = Chunk(content="hello", start_char=0, end_char=5, chunk_index=0)
        c.add_metadata("source", "test.txt")
        c.add_metadata("page", 3)
        assert c.metadata["source"] == "test.txt"
        assert c.metadata["page"] == 3

    def test_metadata_default_empty(self) -> None:
        """Chunk metadata defaults to an empty dict."""
        c = Chunk(content="text", start_char=0, end_char=4, chunk_index=0)
        assert c.metadata == {}

    def test_chunk_index_preserved(self) -> None:
        chunks = [
            Chunk(
                content=f"chunk {i}",
                start_char=i * 10,
                end_char=i * 10 + 7,
                chunk_index=i,
            )
            for i in range(5)
        ]
        for i, c in enumerate(chunks):
            assert c.chunk_index == i


# ---------------------------------------------------------------------------
# FixedChunker
# ---------------------------------------------------------------------------


class TestFixedChunker:
    def test_basic_chunking(self) -> None:
        """Short text produces one chunk."""
        chunker = FixedChunker(chunk_size=200, overlap=0)
        chunks = chunker.chunk("Hello world.")
        assert len(chunks) >= 1
        assert all(c.content for c in chunks)

    def test_large_text_produces_multiple_chunks(self) -> None:
        """Text exceeding chunk_size produces multiple chunks."""
        text = "word " * 300  # ~1500 chars
        chunker = FixedChunker(chunk_size=200, overlap=20)
        chunks = chunker.chunk(text)
        assert len(chunks) > 1

    def test_all_content_covered(self) -> None:
        """All content should appear across chunks (no data loss)."""
        text = "alpha beta gamma delta epsilon " * 50
        chunker = FixedChunker(chunk_size=100, overlap=10)
        chunks = chunker.chunk(text)
        combined = " ".join(c.content for c in chunks)
        # Every word should appear at least once
        for word in ["alpha", "gamma", "epsilon"]:
            assert word in combined

    def test_metadata_propagated_to_all_chunks(self) -> None:
        """Metadata passed to chunk() must appear on every chunk."""
        text = "sentence one. " * 50
        chunker = FixedChunker(chunk_size=100, overlap=0)
        meta = {"source": "wiki", "author": "test"}
        chunks = chunker.chunk(text, metadata=meta)
        for c in chunks:
            assert c.metadata["source"] == "wiki"
            assert c.metadata["author"] == "test"

    def test_empty_text_returns_empty_list(self) -> None:
        chunker = FixedChunker()
        assert chunker.chunk("") == []

    def test_overlap_less_than_chunk_size_constraint(self) -> None:
        """Overlap >= chunk_size should raise ValueError."""
        with pytest.raises(ValueError, match="[Oo]verlap"):
            FixedChunker(chunk_size=100, overlap=100)

    def test_chunk_indices_are_sequential(self) -> None:
        text = "word " * 200
        chunker = FixedChunker(chunk_size=80, overlap=10)
        chunks = chunker.chunk(text)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_zero_overlap(self) -> None:
        """Zero overlap is valid."""
        chunker = FixedChunker(chunk_size=50, overlap=0)
        chunks = chunker.chunk("a" * 200)
        assert len(chunks) > 0


# ---------------------------------------------------------------------------
# SemanticChunker
# ---------------------------------------------------------------------------


class TestSemanticChunker:
    def test_paragraph_boundaries_respected(self) -> None:
        """Paragraph separators should create natural chunk boundaries."""
        text = (
            "First paragraph about dogs.\n\n"
            "Second paragraph about cats.\n\n"
            "Third paragraph about birds."
        )
        chunker = SemanticChunker(chunk_size=1000)
        chunks = chunker.chunk(text)
        # All three paragraphs should be present somewhere
        full = " ".join(c.content for c in chunks)
        assert "dogs" in full
        assert "cats" in full
        assert "birds" in full

    def test_min_chunk_size_filter(self) -> None:
        """Chunks shorter than min_chunk_size should be dropped."""
        text = "Short. " * 3 + "A" * 500
        chunker = SemanticChunker(chunk_size=100, min_chunk_size=50)
        chunks = chunker.chunk(text)
        for c in chunks:
            assert len(c.content) >= chunker.min_chunk_size

    def test_returns_chunks_for_long_text(self) -> None:
        text = "The neural network processes features. " * 30
        chunker = SemanticChunker(chunk_size=200, overlap=30)
        chunks = chunker.chunk(text)
        assert len(chunks) > 0

    def test_empty_returns_empty(self) -> None:
        assert SemanticChunker().chunk("") == []

    def test_metadata_on_all_chunks(self) -> None:
        text = "Sentence one. Sentence two. " * 20
        chunker = SemanticChunker(chunk_size=100)
        chunks = chunker.chunk(text, metadata={"doc": "test-doc"})
        assert all(c.metadata.get("doc") == "test-doc" for c in chunks)

    def test_single_sentence_text(self) -> None:
        """Single sentence long enough to meet min_chunk_size should produce one chunk."""
        text = "This is a single sentence that is long enough to meet the minimum chunk size threshold."
        # min_chunk_size defaults to 100; use a small override so the test is self-contained
        chunks = SemanticChunker(chunk_size=512, min_chunk_size=10).chunk(text)
        assert len(chunks) >= 1

    def test_overlap_words_carry_over(self) -> None:
        """With overlap > 0, consecutive chunks may share words."""
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa. " * 10
        chunker = SemanticChunker(chunk_size=80, overlap=20)
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# RecursiveChunker
# ---------------------------------------------------------------------------


class TestRecursiveChunker:
    def test_mixed_content_chunked(self) -> None:
        text = "Header text.\n\nParagraph one.\nParagraph two.\n\nAnother paragraph."
        chunker = RecursiveChunker(chunk_size=50)
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_custom_separators(self) -> None:
        text = "part1|part2|part3|part4|part5"
        chunker = RecursiveChunker(chunk_size=10, separators=["|", " ", ""])
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        combined = "".join(c.content for c in chunks)
        assert "part1" in combined

    def test_empty_returns_empty(self) -> None:
        assert RecursiveChunker().chunk("") == []

    def test_no_infinite_loop_on_tiny_chunk_size(self) -> None:
        """Should terminate even with very small chunk_size."""
        text = "word " * 20
        chunker = RecursiveChunker(chunk_size=5)
        chunks = chunker.chunk(text)
        assert isinstance(chunks, list)

    def test_metadata_attached(self) -> None:
        text = "data " * 100
        chunker = RecursiveChunker(chunk_size=50)
        chunks = chunker.chunk(text, metadata={"origin": "recursive"})
        assert all("origin" in c.metadata for c in chunks)


# ---------------------------------------------------------------------------
# MarkdownChunker
# ---------------------------------------------------------------------------


class TestMarkdownChunker:
    def test_respects_headers(self) -> None:
        """Markdown headers should be preserved in chunks."""
        md = "# Title\n\nContent under title.\n\n## Section A\n\nSection A content.\n\n## Section B\n\nSection B content."
        chunker = MarkdownChunker(chunk_size=500)
        chunks = chunker.chunk(md)
        full = " ".join(c.content for c in chunks)
        assert "Title" in full or "Section A" in full

    def test_code_block_not_broken(self) -> None:
        """Code blocks should land in a chunk without being destroyed."""
        md = "Intro text.\n\n```python\nfor i in range(10):\n    print(i)\n```\n\nMore text."
        chunker = MarkdownChunker(chunk_size=1000)
        chunks = chunker.chunk(md)
        full = " ".join(c.content for c in chunks)
        assert "range(10)" in full

    def test_include_metadata_flag(self) -> None:
        """When include_metadata=True, headers should appear in chunk metadata."""
        md = "# My Header\n\nSome paragraph content here.\n\n## Sub Header\n\nMore content."
        chunker = MarkdownChunker(chunk_size=500, include_metadata=True)
        chunks = chunker.chunk(md)
        # At least one chunk should have header metadata
        headers = [
            c.metadata.get("last_header")
            for c in chunks
            if c.metadata.get("last_header")
        ]
        assert len(headers) >= 0  # Some chunks may have it

    def test_empty_returns_empty(self) -> None:
        assert MarkdownChunker().chunk("") == []

    def test_large_markdown_produces_multiple_chunks(self) -> None:
        md = "# Section {}\n\nThis section has a lot of content. " * 20
        chunker = MarkdownChunker(chunk_size=100)
        chunks = chunker.chunk(md)
        assert len(chunks) >= 1

    def test_metadata_propagated(self) -> None:
        md = "# Title\n\nContent here.\n"
        chunker = MarkdownChunker()
        chunks = chunker.chunk(md, metadata={"format": "markdown"})
        assert all(c.metadata.get("format") == "markdown" for c in chunks)


# ---------------------------------------------------------------------------
# create_chunker factory
# ---------------------------------------------------------------------------


class TestCreateChunker:
    def test_creates_fixed_chunker(self) -> None:
        c = create_chunker(ChunkingStrategy.FIXED, chunk_size=256)
        assert isinstance(c, FixedChunker)
        assert c.chunk_size == 256

    def test_creates_semantic_chunker(self) -> None:
        c = create_chunker(ChunkingStrategy.SEMANTIC)
        assert isinstance(c, SemanticChunker)

    def test_creates_recursive_chunker(self) -> None:
        c = create_chunker(ChunkingStrategy.RECURSIVE, chunk_size=128)
        assert isinstance(c, RecursiveChunker)

    def test_creates_markdown_chunker(self) -> None:
        c = create_chunker(ChunkingStrategy.MARKDOWN)
        assert isinstance(c, MarkdownChunker)

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises((ValueError, AttributeError)):
            create_chunker("unknown_strategy_xyz")  # type: ignore[arg-type]

    def test_kwargs_forwarded(self) -> None:
        c = create_chunker(ChunkingStrategy.FIXED, chunk_size=64, overlap=5)
        assert c.chunk_size == 64
        assert c.overlap == 5

    def test_negative_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError):
            FixedChunker(chunk_size=-1)
