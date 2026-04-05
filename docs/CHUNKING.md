# Chunking

Agentic Brain now exposes a dedicated `agentic_brain.chunking` package with:

- `TokenChunker` for token-aware splits
- `SentenceChunker` for sentence boundary splits
- `SemanticChunker` for topic-shift aware grouping
- `RecursiveChunker` for hierarchical fallback splitting
- `MarkdownChunker` for heading/code/list-aware document splits

## Shared features

- Character/token overlap support
- Optional chunk deduplication
- Start/end offsets for every chunk
- Metadata propagation
- `Chunk.token_count` helper

## Quick start

```python
from agentic_brain.chunking import ChunkingStrategy, create_chunker

chunker = create_chunker(ChunkingStrategy.TOKEN, chunk_size=128, overlap=16)
chunks = chunker.chunk("Some long text ...")
```

## Strategy guide

| Strategy | Best for |
| --- | --- |
| `token` | Precise model-context budgeting |
| `sentence` | General prose |
| `semantic` | Topic-aware document grouping |
| `recursive` | Mixed structure and fallback splitting |
| `markdown` | README/docs and structured markdown |
| `fixed` | Backwards-compatible alias for token chunking |

## Compatibility

The legacy `agentic_brain.rag.chunking` import path still works and now re-exports
the new implementation.
