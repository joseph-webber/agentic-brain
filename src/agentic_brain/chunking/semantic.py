from __future__ import annotations

import re
from typing import Any

from .base import Chunk, Span
from .sentence import SentenceChunker

_WORD_PATTERN = re.compile(r"\w+")


def _similarity(left: str, right: str) -> float:
    left_tokens = set(_WORD_PATTERN.findall(left.casefold()))
    right_tokens = set(_WORD_PATTERN.findall(right.casefold()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


class SemanticChunker(SentenceChunker):
    strategy_name = "semantic"

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int | None = None,
        *,
        deduplicate: bool = False,
        similarity_threshold: float = 0.18,
        min_chunk_size: int = 1,
        separator: str = "\n\n",
    ) -> None:
        super().__init__(
            chunk_size, overlap, deduplicate=deduplicate, separator=separator
        )
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size

    def chunk(
        self, text: str | bytes | None, metadata: dict[str, Any] | None = None
    ) -> list[Chunk]:
        source = self._prepare_text(text)
        if not source:
            return []

        sentences = self._sentence_spans(source)
        if not sentences:
            return []

        chunks: list[Chunk] = []
        window: list[Span] = []

        def flush() -> None:
            if not window:
                return
            content = source[window[0].start_char : window[-1].end_char].strip()
            if content:
                chunks.append(
                    Chunk(
                        content=content,
                        start_char=window[0].start_char,
                        end_char=window[-1].end_char,
                        chunk_index=len(chunks),
                        metadata=self._merge_metadata(
                            window,
                            metadata,
                            extra={
                                "strategy": self.strategy_name,
                                "semantic_similarity_threshold": self.similarity_threshold,
                            },
                        ),
                    )
                )
            window.clear()

        for sentence in sentences:
            if not window:
                window.append(sentence)
                continue

            current_len = window[-1].end_char - window[0].start_char
            candidate = source[window[0].start_char : sentence.end_char]
            similarity = _similarity(
                source[window[-1].start_char : window[-1].end_char], sentence.text
            )
            if current_len < self.min_chunk_size:
                window.append(sentence)
                continue
            if (
                len(candidate) <= self.chunk_size
                and similarity >= self.similarity_threshold
            ):
                window.append(sentence)
                continue

            flush()
            if self.overlap > 0 and chunks:
                previous = chunks[-1]
                overlap_start = max(
                    previous.start_char, previous.end_char - self.overlap
                )
                overlap_text = source[overlap_start : previous.end_char].strip()
                if overlap_text:
                    window.append(
                        Span(
                            overlap_text,
                            overlap_start,
                            previous.end_char,
                            {"kind": "semantic-overlap"},
                        )
                    )
            window.append(sentence)

        flush()
        return self._deduplicate_chunks(chunks)
