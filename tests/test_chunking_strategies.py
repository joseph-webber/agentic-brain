# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from agentic_brain.chunking import (
    BaseChunker,
    Chunk,
    ChunkingStrategy,
    FixedChunker,
    MarkdownChunker,
    RecursiveChunker,
    SemanticChunker,
    SentenceChunker,
    TokenChunker,
    create_chunker,
)
from agentic_brain.rag.chunking.base import (
    ChunkingStrategy as RagChunkingStrategy,
)
from agentic_brain.rag.chunking.base import (
    FixedChunker as RagFixedChunker,
)
from agentic_brain.rag.chunking.base import (
    create_chunker as rag_create_chunker,
)

TOKEN_TEXT = "alpha beta gamma delta epsilon zeta eta theta"
SENTENCE_TEXT = "One. Two. Three. Four."
SEMANTIC_TEXT = (
    "Cats purr softly. Cats chase yarn. Quantum fields curve space. "
    "Black holes warp time."
)
MARKDOWN_TEXT = """# Title

Intro text here.

- item one
- item two

```python
print('hi')
```

## Subsection

More text.
"""
RECURSIVE_TEXT = "alpha beta gamma delta epsilon zeta eta theta iota kappa"


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(-1, 0), (0, 0), (10, -1), (10, 10)],
)
def test_chunker_rejects_invalid_parameters(chunk_size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        TokenChunker(chunk_size=chunk_size, overlap=overlap)


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        (b"alpha beta", ["alpha beta"]),
        ("   ", []),
        (123, TypeError),
    ],
)
def test_token_chunker_handles_input_types(value, expected) -> None:
    chunker = TokenChunker(chunk_size=5, overlap=0)
    if expected is TypeError:
        with pytest.raises(TypeError):
            chunker.chunk(value)
    else:
        chunks = chunker.chunk(value)
        assert [chunk.content for chunk in chunks] == expected


@pytest.mark.parametrize(
    "content, tokens",
    [
        ("hello", 1),
        ("hello world", 2),
        ("hello, world!", 3),
        ("One two three four", 4),
    ],
)
def test_chunk_token_count(content: str, tokens: int) -> None:
    assert Chunk(content, 0, len(content), 0).token_count == tokens


@pytest.mark.parametrize(
    "strategy, expected_type",
    [
        (ChunkingStrategy.TOKEN, TokenChunker),
        (ChunkingStrategy.FIXED, FixedChunker),
        (ChunkingStrategy.SENTENCE, SentenceChunker),
        (ChunkingStrategy.SEMANTIC, SemanticChunker),
        (ChunkingStrategy.RECURSIVE, RecursiveChunker),
        (ChunkingStrategy.MARKDOWN, MarkdownChunker),
        ("fixed", FixedChunker),
        ("token", TokenChunker),
    ],
)
def test_create_chunker_maps_strategies(strategy, expected_type) -> None:
    chunker = create_chunker(strategy)
    assert isinstance(chunker, expected_type)


def test_fixed_chunker_alias_is_token_chunker() -> None:
    assert FixedChunker is not TokenChunker
    assert RagFixedChunker is FixedChunker
    assert RagChunkingStrategy.FIXED.value == "fixed"


@pytest.mark.parametrize(
    "chunk_size, overlap, expected",
    [
        (3, 0, ["alpha beta gamma", "delta epsilon zeta", "eta theta"]),
        (4, 1, ["alpha beta gamma delta", "delta epsilon zeta eta", "eta theta"]),
        (5, 2, ["alpha beta gamma delta epsilon", "epsilon zeta eta theta"]),
        (8, 0, [TOKEN_TEXT]),
    ],
)
def test_token_chunker_windowing(
    chunk_size: int, overlap: int, expected: list[str]
) -> None:
    chunks = TokenChunker(chunk_size=chunk_size, overlap=overlap).chunk(TOKEN_TEXT)
    assert [chunk.content for chunk in chunks] == expected


@pytest.mark.parametrize(
    "text, expected_count",
    [
        ("alpha beta gamma alpha beta gamma delta", 2),
        ("repeat repeat repeat unique", 2),
        ("one two one two one two", 2),
        ("alpha alpha beta beta gamma", 2),
    ],
)
def test_token_chunker_deduplicates(text: str, expected_count: int) -> None:
    chunks = TokenChunker(chunk_size=3, overlap=0, deduplicate=True).chunk(text)
    assert len(chunks) == expected_count
    assert len({chunk.content for chunk in chunks}) == expected_count


@pytest.mark.parametrize(
    "chunk_size, overlap",
    [(8, 0), (9, 3), (10, 2), (12, 4)],
)
def test_sentence_chunker_splits_on_sentence_boundaries(
    chunk_size: int, overlap: int
) -> None:
    chunks = SentenceChunker(chunk_size=chunk_size, overlap=overlap).chunk(
        SENTENCE_TEXT
    )
    assert chunks
    assert all(chunk.content.endswith((".", "!", "?")) for chunk in chunks)
    assert chunks[0].content.startswith("One.")


@pytest.mark.parametrize(
    "text, expected_count",
    [
        ("Repeat. Repeat. Unique.", 2),
        ("Alpha. Alpha. Beta.", 2),
        ("One. One. One. Two.", 2),
        ("Hello. Hello. Hello.", 1),
    ],
)
def test_sentence_chunker_deduplicates(text: str, expected_count: int) -> None:
    chunks = SentenceChunker(chunk_size=8, overlap=0, deduplicate=True).chunk(text)
    assert len(chunks) == expected_count


@pytest.mark.parametrize(
    "similarity_threshold, expected_count",
    [(0.15, 3), (0.18, 3), (0.25, 4), (0.4, 4)],
)
def test_semantic_chunker_respects_topic_shifts(
    similarity_threshold: float, expected_count: int
) -> None:
    chunks = SemanticChunker(
        chunk_size=120,
        overlap=0,
        similarity_threshold=similarity_threshold,
    ).chunk(SEMANTIC_TEXT)
    assert len(chunks) == expected_count
    assert "Cats" in chunks[0].content


@pytest.mark.parametrize(
    "text, separators",
    [
        ("alpha\n\nbeta\n\ngamma\n\ndelta", None),
        ("alpha|beta|gamma|delta", ["|", ""]),
        ("alpha/beta/gamma/delta", ["/", ""]),
        (RECURSIVE_TEXT, ["\n\n", " ", ""]),
    ],
)
def test_recursive_chunker_splits_hierarchically(
    text: str, separators: list[str] | None
) -> None:
    chunker = RecursiveChunker(chunk_size=12, overlap=2, separators=separators)
    chunks = chunker.chunk(text)
    assert chunks
    assert all(chunk.content for chunk in chunks)
    assert all(chunk.end_char > chunk.start_char for chunk in chunks)


@pytest.mark.parametrize(
    "chunk_size, expected_min",
    [(20, 2), (30, 3), (40, 3), (60, 2)],
)
def test_markdown_chunker_recognizes_structure(
    chunk_size: int, expected_min: int
) -> None:
    chunks = MarkdownChunker(chunk_size=chunk_size, overlap=0).chunk(MARKDOWN_TEXT)
    assert len(chunks) >= expected_min
    assert any(chunk.metadata.get("heading") == "Title" for chunk in chunks)
    assert any("code" in chunk.metadata.get("kinds", []) for chunk in chunks)
    assert any("list" in chunk.metadata.get("kinds", []) for chunk in chunks)


@pytest.mark.parametrize(
    "include_metadata, expected",
    [(True, True), (False, False)],
)
def test_markdown_chunker_metadata_toggle(
    include_metadata: bool, expected: bool
) -> None:
    chunker = MarkdownChunker(
        chunk_size=40, overlap=0, include_metadata=include_metadata
    )
    chunks = chunker.chunk(MARKDOWN_TEXT, metadata={"source": "doc"})
    if expected:
        assert all(chunk.metadata.get("source") == "doc" for chunk in chunks)
        assert any(chunk.metadata for chunk in chunks)
    else:
        assert all(chunk.metadata == {"source": "doc"} for chunk in chunks)


@pytest.mark.parametrize(
    "strategy",
    [
        ChunkingStrategy.FIXED,
        ChunkingStrategy.TOKEN,
        ChunkingStrategy.SENTENCE,
        ChunkingStrategy.SEMANTIC,
        ChunkingStrategy.RECURSIVE,
        ChunkingStrategy.MARKDOWN,
    ],
)
def test_top_level_and_rag_chunking_paths_agree(strategy: ChunkingStrategy) -> None:
    top = create_chunker(strategy, chunk_size=20, overlap=0)
    rag = rag_create_chunker(strategy, chunk_size=20, overlap=0)
    assert type(top) is type(rag)


def test_public_exports_include_core_chunkers() -> None:
    assert BaseChunker is not None
    assert TokenChunker is not None
    assert SentenceChunker is not None
    assert SemanticChunker is not None
    assert RecursiveChunker is not None
    assert MarkdownChunker is not None
