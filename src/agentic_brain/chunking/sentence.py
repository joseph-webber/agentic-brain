from __future__ import annotations

import re
from typing import Any

from .base import BaseChunker, Chunk, Span

_SENTENCE_PATTERN = re.compile(r"[^.!?]+(?:[.!?]+(?:['\"]+)?)?", re.S)


class SentenceChunker(BaseChunker):
    strategy_name = "sentence"

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int | None = None,
        *,
        deduplicate: bool = False,
        max_sentences: int | None = None,
        separator: str = "\n\n",
    ) -> None:
        super().__init__(
            chunk_size, overlap, deduplicate=deduplicate, separator=separator
        )
        self.max_sentences = max_sentences

    def _sentence_spans(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for match in _SENTENCE_PATTERN.finditer(text):
            sentence = match.group(0).strip()
            if sentence:
                spans.append(
                    Span(sentence, match.start(), match.end(), {"kind": "sentence"})
                )
        return spans

    def chunk(
        self,
        text: str | bytes | None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        source = self._prepare_text(text)
        if not source:
            return []
        spans = self._sentence_spans(source)
        if not spans:
            return []
        if self.max_sentences:
            spans = spans[: self.max_sentences]
        return self._chunk_from_spans(
            source,
            spans,
            chunk_metadata=metadata,
            strategy_name=self.strategy_name,
            measure="chars",
        )
