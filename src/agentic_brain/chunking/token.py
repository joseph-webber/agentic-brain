# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
from typing import Any

from .base import BaseChunker, Chunk, Span

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class TokenChunker(BaseChunker):
    strategy_name = "token"

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int | None = None,
        *,
        deduplicate: bool = False,
        separator: str = "\n\n",
    ) -> None:
        super().__init__(
            chunk_size, overlap, deduplicate=deduplicate, separator=separator
        )

    def _token_spans(self, text: str) -> list[Span]:
        return [
            Span(m.group(0), m.start(), m.end(), {"kind": "token"})
            for m in _TOKEN_PATTERN.finditer(text)
        ]

    def chunk(
        self, text: str | bytes | None, metadata: dict[str, Any] | None = None
    ) -> list[Chunk]:
        source = self._prepare_text(text)
        if not source:
            return []
        return self._chunk_from_spans(
            source,
            self._token_spans(source),
            chunk_metadata=metadata,
            strategy_name=self.strategy_name,
            measure="spans",
        )


FixedChunker = TokenChunker
