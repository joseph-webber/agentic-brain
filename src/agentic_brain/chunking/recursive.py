from __future__ import annotations

from typing import Any

from .base import BaseChunker, Chunk, Span


class RecursiveChunker(BaseChunker):
    strategy_name = "recursive"

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int | None = None,
        *,
        deduplicate: bool = False,
        separators: list[str] | None = None,
        separator: str = "\n\n",
    ) -> None:
        super().__init__(chunk_size, overlap, deduplicate=deduplicate, separator=separator)
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def _split_by_separator(self, text: str, separator: str, kind: str) -> list[Span]:
        if not separator:
            return [
                Span(char, index, index + 1, {"kind": kind})
                for index, char in enumerate(text)
                if char
            ]

        pieces: list[Span] = []
        cursor = 0
        while cursor < len(text):
            idx = text.find(separator, cursor)
            if idx < 0:
                piece = text[cursor:]
                if piece:
                    pieces.append(Span(piece, cursor, len(text), {"kind": kind}))
                break
            piece = text[cursor:idx]
            if piece:
                pieces.append(Span(piece, cursor, idx, {"kind": kind}))
            cursor = idx + len(separator)
        return pieces

    def _recursive_spans(self, text: str, depth: int = 0) -> list[Span]:
        if depth >= len(self.separators) or len(text) <= self.chunk_size:
            return [Span(text, 0, len(text), {"kind": "leaf"})]

        separator = self.separators[depth]
        if not separator:
            return [
                Span(char, index, index + 1, {"kind": "character"})
                for index, char in enumerate(text)
                if char
            ]

        pieces = self._split_by_separator(text, separator, f"separator-{depth}")
        if len(pieces) == 1:
            return self._recursive_spans(text, depth + 1)

        result: list[Span] = []
        for piece in pieces:
            if len(piece.text) > self.chunk_size and depth + 1 < len(self.separators):
                result.extend(self._recursive_spans(piece.text, depth + 1))
            else:
                result.append(piece)
        return result

    @property
    def min_chunk_size(self) -> int:
        return self.chunk_size // 4

    def chunk(
        self,
        text: str | bytes | None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        source = self._prepare_text(text)
        if not source:
            return []
        return self._chunk_from_spans(
            source,
            self._recursive_spans(source),
            chunk_metadata=metadata,
            strategy_name=self.strategy_name,
            measure="chars",
        )
