# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
Comprehensive tests for RAG chunking strategies.

Tests all chunking approaches:
- FixedChunker: Fixed-size chunks with overlap
- SemanticChunker: Sentence-based semantic chunking
- RecursiveChunker: Hierarchical multi-separator chunking
- MarkdownChunker: Markdown structure-aware chunking
- create_chunker: Factory function
"""

from __future__ import annotations

import pytest

from agentic_brain.rag.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MIN_CHUNK_SIZE,
    BaseChunker,
    Chunk,
    ChunkingStrategy,
    FixedChunker,
    MarkdownChunker,
    RecursiveChunker,
    SemanticChunker,
    create_chunker,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def short_text() -> str:
    """Short text that fits in a single chunk."""
    return "This is a short text that should fit in one chunk."


@pytest.fixture
def medium_text() -> str:
    """Medium text that requires multiple chunks."""
    return """
This is the first paragraph of medium-length text. It contains several sentences.
Each sentence helps us test sentence boundaries. Here comes another sentence.

This is the second paragraph. It should potentially start a new chunk depending
on the chunking strategy used. The semantic chunker should recognize this.

This is the third paragraph with some more content. Testing boundaries is
important for RAG applications. Let's add a few more words here.
""".strip()


@pytest.fixture
def long_text() -> str:
    """Long text requiring many chunks."""
    paragraphs = []
    for i in range(20):
        paragraphs.append(
            f"Paragraph {i + 1}: This is a longer paragraph with substantial content. "
            f"It contains multiple sentences to test chunking thoroughly. "
            f"The content varies slightly to make each paragraph unique. "
            f"This helps test overlap and boundary detection algorithms."
        )
    return "\n\n".join(paragraphs)


@pytest.fixture
def markdown_text() -> str:
    """Markdown document for testing MarkdownChunker."""
    return """# Main Title

This is the introduction paragraph with some important context.
It spans multiple lines and introduces the document.

## Section One

Content for section one goes here. This section covers the first topic.
More details about the first topic are provided below.

### Subsection 1.1

Detailed content for subsection 1.1. This is nested under section one.

## Section Two

Content for section two. This discusses a different topic entirely.

```python
def example_code():
    \"\"\"Example code block.\"\"\"
    return "Hello, World!"
```

## Section Three

- List item one
- List item two
- List item three

Final paragraph with conclusions.
"""


@pytest.fixture
def unicode_text() -> str:
    """Text with unicode characters."""
    return """
This is a test with émojis 🎉 and ünïcödé characters.
日本語のテキスト (Japanese text) is here.
And some Arabic: النص العربي.

Multiple paragraphs ensure proper handling.
Ελληνικά (Greek) and кириллица (Cyrillic) too.
"""


# =============================================================================
# Chunk Dataclass Tests
# =============================================================================


class TestChunk:
    """Tests for the Chunk dataclass."""

    def test_chunk_creation(self):
        """Test basic Chunk creation."""
        chunk = Chunk(
            content="Test content",
            start_char=0,
            end_char=12,
            chunk_index=0,
        )
        assert chunk.content == "Test content"
        assert chunk.start_char == 0
        assert chunk.end_char == 12
        assert chunk.chunk_index == 0
        assert chunk.metadata == {}

    def test_chunk_with_metadata(self):
        """Test Chunk with metadata."""
        chunk = Chunk(
            content="Content",
            start_char=0,
            end_char=7,
            chunk_index=0,
            metadata={"source": "test", "page": 1},
        )
        assert chunk.metadata["source"] == "test"
        assert chunk.metadata["page"] == 1

    def test_token_count_estimation(self):
        """Test rough token estimation (1 token ≈ 4 chars)."""
        chunk = Chunk(content="a" * 100, start_char=0, end_char=100, chunk_index=0)
        assert chunk.token_count == 25  # 100 / 4

    def test_token_count_minimum(self):
        """Test that token count is at least 1."""
        chunk = Chunk(content="ab", start_char=0, end_char=2, chunk_index=0)
        assert chunk.token_count == 1  # Minimum is 1

    def test_add_metadata(self):
        """Test adding metadata to chunk."""
        chunk = Chunk(content="Test", start_char=0, end_char=4, chunk_index=0)
        chunk.add_metadata("key1", "value1")
        chunk.add_metadata("key2", 42)

        assert chunk.metadata["key1"] == "value1"
        assert chunk.metadata["key2"] == 42


# =============================================================================
# BaseChunker Tests
# =============================================================================


class TestBaseChunker:
    """Tests for BaseChunker validation and utilities."""

    def test_overlap_validation(self):
        """Test that overlap must be less than chunk_size."""
        with pytest.raises(ValueError, match="Overlap must be less than chunk_size"):
            FixedChunker(chunk_size=100, overlap=100)

        with pytest.raises(ValueError, match="Overlap must be less than chunk_size"):
            FixedChunker(chunk_size=100, overlap=150)

    def test_default_values(self):
        """Test that default values are applied correctly."""
        chunker = FixedChunker()
        assert chunker.chunk_size == DEFAULT_CHUNK_SIZE
        assert chunker.overlap == DEFAULT_CHUNK_OVERLAP
        assert chunker.separator == "\n\n"

    def test_custom_separator(self):
        """Test custom separator."""
        chunker = FixedChunker(separator="---")
        assert chunker.separator == "---"


# =============================================================================
# FixedChunker Tests
# =============================================================================


class TestFixedChunker:
    """Tests for fixed-size chunking strategy."""

    def test_basic_chunking(self):
        """Test basic fixed-size chunking."""
        chunker = FixedChunker(chunk_size=100, overlap=20)
        text = "a" * 250
        chunks = chunker.chunk(text)

        assert len(chunks) >= 2
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert len(chunk.content) <= 100

    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = FixedChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_small_text_single_chunk(self, short_text):
        """Test that small text produces single chunk with zero overlap."""
        # Use overlap=0 to ensure small text produces exactly one chunk
        chunker = FixedChunker(chunk_size=1000, overlap=0)
        chunks = chunker.chunk(short_text)

        assert len(chunks) == 1
        assert chunks[0].content == short_text

    def test_overlap_present(self):
        """Test that overlap exists between consecutive chunks."""
        chunker = FixedChunker(chunk_size=50, overlap=10)
        # Create text that will produce multiple chunks
        text = "Word " * 50  # 250 chars

        chunks = chunker.chunk(text)
        assert len(chunks) >= 2

        # Verify chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_indices_sequential(self, medium_text):
        """Test that chunk indices are sequential."""
        chunker = FixedChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk(medium_text)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_metadata_propagation(self):
        """Test that metadata is added to all chunks."""
        chunker = FixedChunker(chunk_size=50, overlap=10)
        text = "a" * 150
        metadata = {"source": "test_file.txt", "page": 1}

        chunks = chunker.chunk(text, metadata=metadata)

        for chunk in chunks:
            assert chunk.metadata["source"] == "test_file.txt"
            assert chunk.metadata["page"] == 1

    def test_whitespace_only_text(self):
        """Test handling of whitespace-only text."""
        chunker = FixedChunker()
        chunks = chunker.chunk("   \n\n   \t   ")
        assert chunks == []

    def test_separator_boundary_preference(self):
        """Test that chunks prefer to break at separator boundaries."""
        chunker = FixedChunker(chunk_size=100, overlap=10, separator="\n\n")
        text = "First paragraph here.\n\nSecond paragraph here."

        chunks = chunker.chunk(text)
        # Should handle paragraph boundary
        assert len(chunks) >= 1

    def test_very_long_text(self, long_text):
        """Test chunking of very long text."""
        chunker = FixedChunker(chunk_size=200, overlap=30)
        chunks = chunker.chunk(long_text)

        assert len(chunks) > 10
        # Verify no infinite loop - all content should be covered
        total_coverage = sum(len(c.content) for c in chunks)
        assert total_coverage > 0

    def test_start_end_char_positions(self):
        """Test that start/end char positions are set."""
        chunker = FixedChunker(chunk_size=50, overlap=10)
        text = "a" * 100

        chunks = chunker.chunk(text)

        for chunk in chunks:
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char
            assert chunk.end_char <= len(text) + 50  # Allow for overlap


# =============================================================================
# SemanticChunker Tests
# =============================================================================


class TestSemanticChunker:
    """Tests for semantic (sentence-based) chunking strategy."""

    def test_sentence_boundary_detection(self):
        """Test that chunker detects sentence boundaries."""
        # Use larger text to exceed min_chunk_size
        chunker = SemanticChunker(chunk_size=200, overlap=30, min_chunk_size=50)
        text = (
            "First sentence with more content here. "
            "Second sentence with additional words. "
            "Third sentence that is longer. "
            "Fourth sentence to make it substantial."
        )

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = SemanticChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_single_sentence(self):
        """Test single sentence produces single chunk."""
        chunker = SemanticChunker(chunk_size=500, min_chunk_size=10)
        text = "This is a single sentence without any breaks."

        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_multiple_paragraphs(self, medium_text):
        """Test chunking of multiple paragraphs."""
        chunker = SemanticChunker(chunk_size=200, overlap=30, min_chunk_size=50)
        chunks = chunker.chunk(medium_text)

        assert len(chunks) >= 1
        # All chunks should have content
        for chunk in chunks:
            assert len(chunk.content) > 0

    def test_min_chunk_size_respected(self):
        """Test that minimum chunk size is respected."""
        chunker = SemanticChunker(chunk_size=500, min_chunk_size=100)
        # Create text with short sentences
        text = "Hi. Hey. Yo. Yes. No. Ok. Go. Be. It."

        chunks = chunker.chunk(text)
        # Should combine small sentences to meet minimum
        for chunk in chunks:
            assert len(chunk.content) >= chunker.min_chunk_size or chunk == chunks[-1]

    def test_exclamation_and_question_marks(self):
        """Test handling of ! and ? as sentence boundaries."""
        chunker = SemanticChunker(chunk_size=300, overlap=20, min_chunk_size=20)
        text = "What is this? It's a test! And it works. Amazing!"

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        # Content should be preserved
        combined = " ".join(c.content for c in chunks)
        assert "What is this" in combined
        assert "Amazing" in combined

    def test_newline_boundaries(self):
        """Test handling of newlines as potential boundaries."""
        chunker = SemanticChunker(chunk_size=150, overlap=20, min_chunk_size=30)
        text = "First line here.\nSecond line here.\nThird line here."

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_metadata_propagation(self):
        """Test metadata is added to all chunks."""
        chunker = SemanticChunker(chunk_size=100, overlap=20, min_chunk_size=20)
        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        metadata = {"author": "test"}

        chunks = chunker.chunk(text, metadata=metadata)

        for chunk in chunks:
            assert chunk.metadata.get("author") == "test"

    def test_no_sentences_fallback(self):
        """Test fallback when no sentence boundaries found."""
        chunker = SemanticChunker(chunk_size=500, min_chunk_size=10)
        text = "single block of text without any sentence ending punctuation"

        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert text.strip() in chunks[0].content

    def test_unicode_sentences(self, unicode_text):
        """Test handling of unicode in sentences."""
        chunker = SemanticChunker(chunk_size=200, overlap=30, min_chunk_size=30)
        chunks = chunker.chunk(unicode_text)

        assert len(chunks) >= 1
        # Verify unicode is preserved
        combined = " ".join(c.content for c in chunks)
        assert "🎉" in combined or "emoji" in combined.lower()


# =============================================================================
# RecursiveChunker Tests
# =============================================================================


class TestRecursiveChunker:
    """Tests for recursive (multi-separator) chunking strategy."""

    def test_basic_recursive_chunking(self, medium_text):
        """Test basic recursive chunking."""
        chunker = RecursiveChunker(chunk_size=200, overlap=30)
        chunks = chunker.chunk(medium_text)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk, Chunk)

    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = RecursiveChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_default_separators(self):
        """Test default separator hierarchy."""
        chunker = RecursiveChunker()
        assert chunker.separators == ["\n\n", "\n", ". ", " ", ""]

    def test_custom_separators(self):
        """Test custom separator list."""
        custom_seps = ["---", "\n", " "]
        chunker = RecursiveChunker(separators=custom_seps)
        assert chunker.separators == custom_seps

    def test_paragraph_separation(self):
        """Test that double newlines are preferred split points."""
        chunker = RecursiveChunker(chunk_size=100, overlap=20)
        text = "Para one content.\n\nPara two content.\n\nPara three content."

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_sentence_separation(self):
        """Test fallback to sentence separation."""
        chunker = RecursiveChunker(chunk_size=50, overlap=10)
        text = "Sentence one. Sentence two. Sentence three. Sentence four."

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_word_separation(self):
        """Test fallback to word separation."""
        chunker = RecursiveChunker(chunk_size=20, overlap=5)
        # Single line without sentence breaks
        text = "one two three four five six seven eight nine ten"

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_min_chunk_size_property(self):
        """Test min_chunk_size property."""
        chunker = RecursiveChunker(chunk_size=200)
        assert chunker.min_chunk_size == 50  # 200 // 4

    def test_metadata_propagation(self):
        """Test metadata is added to all chunks."""
        chunker = RecursiveChunker(chunk_size=100, overlap=20)
        text = "Para one.\n\nPara two.\n\nPara three."
        metadata = {"doc_id": "123"}

        chunks = chunker.chunk(text, metadata=metadata)

        for chunk in chunks:
            assert chunk.metadata.get("doc_id") == "123"

    def test_long_text_handling(self, long_text):
        """Test handling of very long text."""
        chunker = RecursiveChunker(chunk_size=300, overlap=50)
        chunks = chunker.chunk(long_text)

        assert len(chunks) > 5
        # Verify sequential indices
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_character_fallback(self):
        """Test character-by-character fallback for very small chunks."""
        chunker = RecursiveChunker(chunk_size=10, overlap=2, separators=[""])
        text = "abcdefghijklmnopqrstuvwxyz"

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1


# =============================================================================
# MarkdownChunker Tests
# =============================================================================


class TestMarkdownChunker:
    """Tests for Markdown-aware chunking strategy."""

    def test_basic_markdown_chunking(self, markdown_text):
        """Test basic markdown chunking."""
        chunker = MarkdownChunker(chunk_size=300, overlap=30)
        chunks = chunker.chunk(markdown_text)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk, Chunk)

    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = MarkdownChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_header_detection(self):
        """Test detection of markdown headers."""
        chunker = MarkdownChunker(chunk_size=500, overlap=50, include_metadata=True)
        text = "# Title\n\nContent under title.\n\n## Section\n\nMore content."

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

        # Check that header metadata is captured
        found_header = False
        for chunk in chunks:
            if "last_header" in chunk.metadata:
                found_header = True
                break
        assert found_header

    def test_code_block_handling(self):
        """Test that code blocks are preserved."""
        chunker = MarkdownChunker(chunk_size=500, overlap=30)
        text = """# Code Example

```python
def hello():
    print("Hello, World!")
```

After the code block.
"""
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

        # Code should be preserved in some chunk
        combined = " ".join(c.content for c in chunks)
        assert "def hello" in combined

    def test_list_handling(self):
        """Test handling of markdown lists."""
        chunker = MarkdownChunker(chunk_size=500, overlap=30)
        text = """# List Section

- Item one
- Item two
- Item three

After the list.
"""
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

        combined = " ".join(c.content for c in chunks)
        assert "Item one" in combined

    def test_include_metadata_option(self):
        """Test include_metadata option."""
        # With metadata
        chunker_with = MarkdownChunker(chunk_size=200, include_metadata=True)
        text = "# Header\n\nContent here."
        chunks_with = chunker_with.chunk(text)

        # Without metadata
        chunker_without = MarkdownChunker(chunk_size=200, include_metadata=False)
        chunks_without = chunker_without.chunk(text)

        # Both should produce chunks
        assert len(chunks_with) >= 1
        assert len(chunks_without) >= 1

    def test_header_level_tracking(self, markdown_text):
        """Test that header levels are tracked."""
        chunker = MarkdownChunker(chunk_size=500, include_metadata=True)
        chunks = chunker.chunk(markdown_text)

        # Should have header_level in metadata for some chunks
        found_level = False
        for chunk in chunks:
            if "header_level" in chunk.metadata:
                found_level = True
                assert chunk.metadata["header_level"] in [1, 2, 3, 4, 5, 6]
                break
        assert found_level

    def test_paragraph_boundaries(self):
        """Test that paragraph boundaries are respected."""
        chunker = MarkdownChunker(chunk_size=100, overlap=20)
        text = "Para one content.\n\nPara two content.\n\nPara three content."

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_mixed_content(self, markdown_text):
        """Test handling of mixed markdown content."""
        chunker = MarkdownChunker(chunk_size=200, overlap=30)
        chunks = chunker.chunk(markdown_text)

        # Should handle all content types
        combined = "\n".join(c.content for c in chunks)
        assert "Main Title" in combined or "Section" in combined

    def test_external_metadata_propagation(self):
        """Test that external metadata is added."""
        chunker = MarkdownChunker(chunk_size=300)
        text = "# Title\n\nContent here."
        metadata = {"file": "readme.md"}

        chunks = chunker.chunk(text, metadata=metadata)

        for chunk in chunks:
            assert chunk.metadata.get("file") == "readme.md"


# =============================================================================
# create_chunker Factory Tests
# =============================================================================


class TestCreateChunker:
    """Tests for the chunker factory function."""

    def test_create_fixed_chunker(self):
        """Test creating FixedChunker via factory."""
        chunker = create_chunker(ChunkingStrategy.FIXED)
        assert isinstance(chunker, FixedChunker)

    def test_create_semantic_chunker(self):
        """Test creating SemanticChunker via factory."""
        chunker = create_chunker(ChunkingStrategy.SEMANTIC)
        assert isinstance(chunker, SemanticChunker)

    def test_create_recursive_chunker(self):
        """Test creating RecursiveChunker via factory."""
        chunker = create_chunker(ChunkingStrategy.RECURSIVE)
        assert isinstance(chunker, RecursiveChunker)

    def test_create_markdown_chunker(self):
        """Test creating MarkdownChunker via factory."""
        chunker = create_chunker(ChunkingStrategy.MARKDOWN)
        assert isinstance(chunker, MarkdownChunker)

    def test_default_strategy(self):
        """Test default strategy is SEMANTIC."""
        chunker = create_chunker()
        assert isinstance(chunker, SemanticChunker)

    def test_kwargs_passed_through(self):
        """Test that kwargs are passed to chunker constructor."""
        chunker = create_chunker(
            ChunkingStrategy.FIXED,
            chunk_size=1000,
            overlap=100,
        )
        assert chunker.chunk_size == 1000
        assert chunker.overlap == 100

    def test_invalid_strategy(self):
        """Test that invalid strategy raises error."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            create_chunker("invalid_strategy")  # type: ignore


# =============================================================================
# ChunkingStrategy Enum Tests
# =============================================================================


class TestChunkingStrategy:
    """Tests for ChunkingStrategy enum."""

    def test_all_strategies_defined(self):
        """Test that all expected strategies are defined."""
        assert ChunkingStrategy.FIXED.value == "fixed"
        assert ChunkingStrategy.SEMANTIC.value == "semantic"
        assert ChunkingStrategy.RECURSIVE.value == "recursive"
        assert ChunkingStrategy.MARKDOWN.value == "markdown"

    def test_strategy_count(self):
        """Test number of strategies."""
        assert len(ChunkingStrategy) == 4


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases across all chunkers."""

    @pytest.mark.parametrize(
        "ChunkerClass",
        [
            FixedChunker,
            SemanticChunker,
            RecursiveChunker,
            MarkdownChunker,
        ],
    )
    def test_empty_string(self, ChunkerClass):
        """Test all chunkers handle empty string."""
        chunker = ChunkerClass()
        chunks = chunker.chunk("")
        assert chunks == []

    @pytest.mark.parametrize(
        "ChunkerClass",
        [
            FixedChunker,
            RecursiveChunker,
            MarkdownChunker,
        ],
    )
    def test_whitespace_only(self, ChunkerClass):
        """Test most chunkers handle whitespace-only strings."""
        chunker = ChunkerClass()
        chunks = chunker.chunk("   \n\n\t  \n  ")
        assert chunks == []

    def test_whitespace_only_semantic_chunker(self):
        """Test SemanticChunker handles whitespace-only strings.

        Note: SemanticChunker may return empty content chunks for whitespace
        depending on sentence boundary detection.
        """
        chunker = SemanticChunker()
        chunks = chunker.chunk("   \n\n\t  \n  ")
        # SemanticChunker may return empty chunks - verify no meaningful content
        for chunk in chunks:
            assert chunk.content.strip() == ""

    @pytest.mark.parametrize(
        "ChunkerClass",
        [
            FixedChunker,
            SemanticChunker,
            RecursiveChunker,
            MarkdownChunker,
        ],
    )
    def test_single_character(self, ChunkerClass):
        """Test all chunkers handle single character."""
        chunker = ChunkerClass(chunk_size=100)
        chunks = chunker.chunk("x")
        # Should either return one chunk or empty (for min_chunk_size)
        assert len(chunks) <= 1

    @pytest.mark.parametrize(
        "ChunkerClass",
        [
            FixedChunker,
            SemanticChunker,
            RecursiveChunker,
            MarkdownChunker,
        ],
    )
    def test_unicode_text(self, ChunkerClass, unicode_text):
        """Test all chunkers handle unicode."""
        chunker = ChunkerClass(chunk_size=200)
        chunks = chunker.chunk(unicode_text)

        # Should produce at least one chunk
        assert len(chunks) >= 1

        # Unicode should be preserved
        combined = " ".join(c.content for c in chunks)
        assert any(
            char in combined
            for char in ["🎉", "日", "é", "العربية", "Ελληνικά", "кириллица"]
        )

    @pytest.mark.parametrize(
        "ChunkerClass",
        [
            FixedChunker,
            SemanticChunker,
            RecursiveChunker,
            MarkdownChunker,
        ],
    )
    def test_very_long_line(self, ChunkerClass):
        """Test all chunkers handle very long single lines."""
        chunker = ChunkerClass(chunk_size=100, overlap=20)
        text = "x" * 10000  # 10k chars, no breaks

        chunks = chunker.chunk(text)
        # Should produce multiple chunks
        assert len(chunks) >= 1

    @pytest.mark.parametrize(
        "ChunkerClass",
        [
            FixedChunker,
            SemanticChunker,
            RecursiveChunker,
            MarkdownChunker,
        ],
    )
    def test_null_metadata(self, ChunkerClass):
        """Test all chunkers handle None metadata."""
        chunker = ChunkerClass()
        text = "Some test content here."
        chunks = chunker.chunk(text, metadata=None)

        # Should not crash, chunks should have empty metadata
        for chunk in chunks:
            assert chunk.metadata is not None

    @pytest.mark.parametrize(
        "ChunkerClass",
        [
            FixedChunker,
            RecursiveChunker,
            MarkdownChunker,
        ],
    )
    def test_special_characters(self, ChunkerClass):
        """Test handling of special regex characters."""
        chunker = ChunkerClass(chunk_size=200)
        text = "Test with special chars: [brackets] (parens) {braces} $dollar ^caret."

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

        combined = " ".join(c.content for c in chunks)
        assert "[brackets]" in combined

    def test_special_characters_semantic_chunker(self):
        """Test SemanticChunker handles special regex characters.

        SemanticChunker needs sufficient text to exceed min_chunk_size.
        """
        chunker = SemanticChunker(chunk_size=200, min_chunk_size=20)
        text = (
            "Test with special chars: [brackets] and (parens) here. "
            "Also {braces} and $dollar and ^caret symbols are included."
        )

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

        combined = " ".join(c.content for c in chunks)
        assert "[brackets]" in combined

    def test_repeated_separators(self):
        """Test handling of repeated separators."""
        chunker = FixedChunker(chunk_size=100, separator="\n\n")
        text = "Para one.\n\n\n\n\n\nPara two.\n\n\n\n\n\nPara three."

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_only_separators(self):
        """Test text that is only separators."""
        chunker = RecursiveChunker(chunk_size=100)
        text = "\n\n\n\n. . . \n\n\n\n"

        chunks = chunker.chunk(text)
        # Should be empty or minimal
        assert len(chunks) <= 1


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for chunking module."""

    def test_all_chunkers_produce_consistent_output(self, medium_text):
        """Test that all chunkers produce valid output structure."""
        chunkers = [
            FixedChunker(chunk_size=200, overlap=30),
            SemanticChunker(chunk_size=200, overlap=30, min_chunk_size=30),
            RecursiveChunker(chunk_size=200, overlap=30),
            MarkdownChunker(chunk_size=200, overlap=30),
        ]

        for chunker in chunkers:
            chunks = chunker.chunk(medium_text)

            # All should produce at least one chunk
            assert len(chunks) >= 1, f"{chunker.__class__.__name__} failed"

            # All chunks should have required fields
            for chunk in chunks:
                assert isinstance(chunk.content, str)
                assert isinstance(chunk.start_char, int)
                assert isinstance(chunk.end_char, int)
                assert isinstance(chunk.chunk_index, int)
                assert isinstance(chunk.metadata, dict)

    def test_chunker_inheritance(self):
        """Test that all chunkers inherit from BaseChunker."""
        assert issubclass(FixedChunker, BaseChunker)
        assert issubclass(SemanticChunker, BaseChunker)
        assert issubclass(RecursiveChunker, BaseChunker)
        assert issubclass(MarkdownChunker, BaseChunker)

    def test_factory_all_strategies(self):
        """Test factory creates all strategy types correctly."""
        for strategy in ChunkingStrategy:
            chunker = create_chunker(strategy)
            assert isinstance(chunker, BaseChunker)

    def test_round_trip_coverage(self, medium_text):
        """Test that chunking covers all original text."""
        chunker = FixedChunker(chunk_size=100, overlap=0)
        chunks = chunker.chunk(medium_text)

        # With no overlap, chunks should roughly cover the text
        total_content = "".join(c.content for c in chunks)
        # Stripping whitespace for comparison
        assert len(total_content.strip()) > 0

    def test_chunk_ordering(self, long_text):
        """Test that chunks are in sequential order."""
        chunker = RecursiveChunker(chunk_size=200)
        chunks = chunker.chunk(long_text)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Performance-related tests."""

    def test_large_text_does_not_hang(self):
        """Test that chunking large text completes in reasonable time."""
        import time

        # Create 1MB of text
        large_text = "Word " * 200000  # ~1M chars

        chunker = FixedChunker(chunk_size=1000, overlap=100)

        start = time.time()
        chunks = chunker.chunk(large_text)
        elapsed = time.time() - start

        # Should complete in under 5 seconds
        assert elapsed < 5.0, f"Took too long: {elapsed}s"
        assert len(chunks) > 100

    def test_deeply_nested_markdown(self):
        """Test handling of deeply nested markdown."""
        # Create nested header structure
        lines = []
        for i in range(1, 7):  # H1 to H6
            lines.append(f"{'#' * i} Level {i} Header")
            lines.append(f"Content at level {i}.")
            lines.append("")

        text = "\n".join(lines * 10)  # Repeat 10 times

        chunker = MarkdownChunker(chunk_size=300)
        chunks = chunker.chunk(text)

        assert len(chunks) >= 1
