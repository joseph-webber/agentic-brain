from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Sequence

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_MIN_CHUNK_SIZE = 100

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Span:
    text: str
    start_char: int
    end_char: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Chunk:
    content: str
    start_char: int
    end_char: int
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return max(1, len(self.content) // 4)

    def add_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value


class ChunkingStrategy(Enum):
    SEMANTIC = "semantic"
    RECURSIVE = "recursive"
    MARKDOWN = "markdown"
    FIXED = "fixed"


ChunkingStrategy.TOKEN = "token"  # type: ignore[attr-defined]
ChunkingStrategy.SENTENCE = "sentence"  # type: ignore[attr-defined]


class Chunker(ABC):
    strategy_name = "chunker"

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int | None = None,
        *,
        deduplicate: bool = False,
        separator: str = "\n\n",
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap is None:
            overlap = min(DEFAULT_CHUNK_OVERLAP, max(0, chunk_size // 4))
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("Overlap must be less than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.deduplicate = deduplicate
        self.separator = separator

    def _prepare_text(self, text: Any) -> str:
        if text is None:
            return ""
        if isinstance(text, bytes):
            return text.decode("utf-8")
        if not isinstance(text, str):
            raise TypeError("chunkers expect str or bytes input")
        return text.strip()

    def _normalize_for_dedupe(self, content: str) -> str:
        return _WHITESPACE_PATTERN.sub(" ", content).strip().casefold()

    def _deduplicate_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        if not self.deduplicate:
            return chunks
        seen: set[str] = set()
        deduped: list[Chunk] = []
        for chunk in chunks:
            key = self._normalize_for_dedupe(chunk.content)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(chunk)
        for index, chunk in enumerate(deduped):
            chunk.chunk_index = index
        return deduped

    def _merge_metadata(
        self,
        spans: Sequence[Span],
        chunk_metadata: dict[str, Any] | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "strategy": self.strategy_name,
            "span_count": len(spans),
            "overlap": self.overlap,
        }
        if chunk_metadata:
            metadata.update(chunk_metadata)
        if extra:
            metadata.update(extra)

        kinds = [span.metadata.get("kind") for span in spans if span.metadata.get("kind")]
        if kinds:
            metadata["kinds"] = sorted(set(kinds))
        heading_paths = [
            tuple(span.metadata.get("heading_path", ()))
            for span in spans
            if span.metadata.get("heading_path")
        ]
        if heading_paths:
            metadata["heading_path"] = heading_paths[-1]
        headings = [span.metadata.get("heading") for span in spans if span.metadata.get("heading")]
        if headings:
            metadata["heading"] = headings[-1]
            metadata["last_header"] = headings[-1]
        levels = [span.metadata.get("heading_level") for span in spans if span.metadata.get("heading_level")]
        if levels:
            metadata["heading_level"] = levels[-1]
            metadata["header_level"] = levels[-1]
        return metadata

    def _chunk_from_spans(
        self,
        text: str,
        spans: Sequence[Span],
        *,
        chunk_metadata: dict[str, Any] | None = None,
        strategy_name: str | None = None,
        measure: str = "chars",
    ) -> list[Chunk]:
        if not spans:
            return []
        usable = [span for span in spans if span.text]
        if not usable:
            return []
        usable = sorted(usable, key=lambda span: (span.start_char, span.end_char))
        chunks: list[Chunk] = []
        index = 0
        start = 0

        def span_size(first: int, last: int) -> int:
            if measure == "spans":
                return last - first + 1
            return usable[last].end_char - usable[first].start_char

        while start < len(usable):
            end = start
            while end + 1 < len(usable) and span_size(start, end + 1) <= self.chunk_size:
                end += 1

            content = text[usable[start].start_char : usable[end].end_char].strip()
            if content:
                chunks.append(
                    Chunk(
                        content=content,
                        start_char=usable[start].start_char,
                        end_char=usable[end].end_char,
                        chunk_index=index,
                        metadata=self._merge_metadata(
                            usable[start : end + 1],
                            chunk_metadata,
                            extra={"strategy": strategy_name or self.strategy_name},
                        ),
                    )
                )
                index += 1

            if end >= len(usable) - 1:
                break

            if self.overlap <= 0:
                start = end + 1
                continue

            boundary = max(usable[start].start_char, usable[end].end_char - self.overlap)
            next_start = end
            while next_start > start and usable[next_start].start_char >= boundary:
                next_start -= 1
            if next_start <= start:
                next_start = start + 1
            start = next_start

        return self._deduplicate_chunks(chunks)

    @abstractmethod
    def chunk(self, text: str | bytes | None, metadata: dict[str, Any] | None = None) -> list[Chunk]:
        raise NotImplementedError


BaseChunker = Chunker


class FixedChunker(Chunker):
    strategy_name = "fixed"

    def chunk(self, text: str | bytes | None, metadata: dict[str, Any] | None = None) -> list[Chunk]:
        source = self._prepare_text(text)
        if not source:
            return []

        chunks: list[Chunk] = []
        position = 0
        index = 0
        separator_window = max(1, min(200, self.chunk_size // 2))

        while position < len(source):
            end = min(position + self.chunk_size, len(source))
            if end < len(source) and self.separator:
                search_start = max(position, end - separator_window)
                sep_index = source.rfind(self.separator, search_start, end)
                if sep_index > position:
                    end = sep_index + len(self.separator)

            content = source[position:end].strip()
            if content:
                chunk = Chunk(
                    content=content,
                    start_char=position,
                    end_char=end,
                    chunk_index=index,
                    metadata={
                        "strategy": self.strategy_name,
                        "separator": self.separator,
                        "overlap": self.overlap,
                    },
                )
                if metadata:
                    chunk.metadata.update(metadata)
                chunks.append(chunk)
                index += 1

            if end >= len(source):
                break

            next_position = end - self.overlap
            if next_position <= position:
                next_position = position + 1
            position = next_position

        return self._deduplicate_chunks(chunks)


def create_chunker(
    strategy: ChunkingStrategy | str = ChunkingStrategy.SEMANTIC,
    **kwargs: Any,
) -> Chunker:
    from .markdown import MarkdownChunker
    from .recursive import RecursiveChunker
    from .semantic import SemanticChunker
    from .sentence import SentenceChunker
    from .token import TokenChunker

    normalized = strategy
    if isinstance(strategy, str):
        lowered = strategy.lower()
        if lowered == "token":
            from .token import TokenChunker

            return TokenChunker(**kwargs)
        if lowered == "sentence":
            from .sentence import SentenceChunker

            return SentenceChunker(**kwargs)
        try:
            normalized = ChunkingStrategy(lowered)
        except ValueError as exc:
            raise ValueError(f"Unknown strategy: {strategy}") from exc

    if normalized == ChunkingStrategy.FIXED:
        return FixedChunker(**kwargs)
    if normalized == ChunkingStrategy.TOKEN:
        return TokenChunker(**kwargs)
    if normalized == ChunkingStrategy.SENTENCE:
        return SentenceChunker(**kwargs)
    if normalized == ChunkingStrategy.SEMANTIC:
        return SemanticChunker(**kwargs)
    if normalized == ChunkingStrategy.RECURSIVE:
        return RecursiveChunker(**kwargs)
    if normalized == ChunkingStrategy.MARKDOWN:
        return MarkdownChunker(**kwargs)
    raise ValueError(f"Unknown strategy: {strategy}")
