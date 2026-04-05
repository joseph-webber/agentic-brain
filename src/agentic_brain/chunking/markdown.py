from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .base import BaseChunker, Chunk, Span

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
_CODE_FENCE_PATTERN = re.compile(r"^```")
_LIST_PATTERN = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")


@dataclass(frozen=True, slots=True)
class MarkdownBlock(Span):
    pass


class MarkdownChunker(BaseChunker):
    strategy_name = "markdown"

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int | None = None,
        *,
        deduplicate: bool = False,
        include_metadata: bool = True,
        separator: str = "\n\n",
    ) -> None:
        super().__init__(
            chunk_size, overlap, deduplicate=deduplicate, separator=separator
        )
        self.include_metadata = include_metadata

    def _parse_blocks(self, text: str) -> list[MarkdownBlock]:
        lines = text.splitlines(keepends=True)
        blocks: list[MarkdownBlock] = []
        cursor = 0
        current_lines: list[str] = []
        current_start = 0
        heading_path: list[str] = []

        def flush(kind: str = "paragraph") -> None:
            nonlocal current_lines, current_start
            if not current_lines:
                return
            content = "".join(current_lines)
            blocks.append(
                MarkdownBlock(
                    content,
                    current_start,
                    current_start + len(content),
                    {
                        "kind": kind,
                        "heading_path": tuple(heading_path),
                        "heading": heading_path[-1] if heading_path else None,
                        "heading_level": len(heading_path),
                    },
                )
            )
            current_lines = []

        index = 0
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped:
                flush()
                cursor += len(line)
                index += 1
                continue

            heading = _HEADING_PATTERN.match(stripped)
            if heading:
                flush()
                level = len(heading.group(1))
                heading_text = heading.group(2).strip()
                heading_path[:] = heading_path[: level - 1]
                heading_path.append(heading_text)
                blocks.append(
                    MarkdownBlock(
                        line,
                        cursor,
                        cursor + len(line),
                        {
                            "kind": "heading",
                            "heading_path": tuple(heading_path),
                            "heading": heading_text,
                            "heading_level": level,
                        },
                    )
                )
                cursor += len(line)
                index += 1
                continue

            if _CODE_FENCE_PATTERN.match(stripped):
                flush()
                start = cursor
                code_lines = [line]
                cursor += len(line)
                index += 1
                while index < len(lines):
                    code_line = lines[index]
                    code_lines.append(code_line)
                    cursor += len(code_line)
                    index += 1
                    if _CODE_FENCE_PATTERN.match(code_line.strip()):
                        break
                content = "".join(code_lines)
                blocks.append(
                    MarkdownBlock(
                        content,
                        start,
                        start + len(content),
                        {
                            "kind": "code",
                            "heading_path": tuple(heading_path),
                            "heading": heading_path[-1] if heading_path else None,
                            "heading_level": len(heading_path),
                        },
                    )
                )
                continue

            if _LIST_PATTERN.match(stripped):
                flush()
                start = cursor
                list_lines = [line]
                cursor += len(line)
                index += 1
                while index < len(lines):
                    next_line = lines[index]
                    next_stripped = next_line.strip()
                    if (
                        not next_stripped
                        or _HEADING_PATTERN.match(next_stripped)
                        or _CODE_FENCE_PATTERN.match(next_stripped)
                    ):
                        break
                    if _LIST_PATTERN.match(next_stripped):
                        list_lines.append(next_line)
                        cursor += len(next_line)
                        index += 1
                        continue
                    break
                content = "".join(list_lines)
                blocks.append(
                    MarkdownBlock(
                        content,
                        start,
                        start + len(content),
                        {
                            "kind": "list",
                            "heading_path": tuple(heading_path),
                            "heading": heading_path[-1] if heading_path else None,
                            "heading_level": len(heading_path),
                        },
                    )
                )
                continue

            if not current_lines:
                current_start = cursor
            current_lines.append(line)
            cursor += len(line)
            index += 1

        flush()
        return blocks

    def chunk(
        self, text: str | bytes | None, metadata: dict[str, Any] | None = None
    ) -> list[Chunk]:
        source = self._prepare_text(text)
        if not source:
            return []

        blocks = self._parse_blocks(source)
        spans = [
            Span(block.text, block.start_char, block.end_char, dict(block.metadata))
            for block in blocks
        ]
        chunks = self._chunk_from_spans(
            source,
            spans,
            chunk_metadata=metadata if self.include_metadata else {},
            strategy_name=self.strategy_name,
            measure="chars",
        )
        if not self.include_metadata:
            for chunk in chunks:
                chunk.metadata = metadata.copy() if metadata else {}
        return chunks
