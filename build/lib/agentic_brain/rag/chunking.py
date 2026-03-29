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
Advanced text chunking strategies for RAG.

Provides multiple chunking approaches optimized for different content types:
- Fixed-size: Simple, predictable chunks
- Semantic: Chunks based on semantic boundaries
- Recursive: Hierarchical chunking with fallback
- Markdown-aware: Respects document structure

Usage:
    from agentic_brain.rag.chunking import SemanticChunker, MarkdownChunker

    # Semantic chunking
    chunker = SemanticChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk("Your text here...")

    # Markdown-aware chunking
    md_chunker = MarkdownChunker()
    chunks = md_chunker.chunk("# Title\n\nContent...")
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# Default chunking parameters
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_MIN_CHUNK_SIZE = 100


class ChunkingStrategy(Enum):
    """Available chunking strategies."""

    FIXED = "fixed"
    SEMANTIC = "semantic"
    RECURSIVE = "recursive"
    MARKDOWN = "markdown"


@dataclass
class Chunk:
    """A text chunk with metadata."""

    content: str
    start_char: int
    end_char: int
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """Rough estimate of token count (1 token ≈ 4 chars). Minimum 1 token."""
        return max(1, len(self.content) // 4)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to chunk."""
        self.metadata[key] = value


class BaseChunker(ABC):
    """Base class for all chunking strategies."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        separator: str = "\n\n",
    ) -> None:
        """
        Initialize base chunker.

        Args:
            chunk_size: Target chunk size in characters
            overlap: Character overlap between chunks
            separator: Primary separator for splitting
        """
        if overlap >= chunk_size:
            raise ValueError("Overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separator = separator

    @abstractmethod
    def chunk(
        self, text: str, metadata: Optional[dict[str, Any]] = None
    ) -> list[Chunk]:
        """
        Split text into chunks.

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to all chunks

        Returns:
            List of Chunk objects
        """
        pass

    def _add_metadata(
        self, chunks: list[Chunk], metadata: Optional[dict[str, Any]]
    ) -> None:
        """Add metadata to all chunks."""
        if not metadata:
            return

        for chunk in chunks:
            for key, value in metadata.items():
                chunk.add_metadata(key, value)

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 chars)."""
        return len(text) // 4


class FixedChunker(BaseChunker):
    """
    Fixed-size chunking strategy.

    Simple approach: split text into fixed-size chunks with overlap.
    Best for: Uniform content where size is more important than boundaries.
    """

    def chunk(
        self, text: str, metadata: Optional[dict[str, Any]] = None
    ) -> list[Chunk]:
        """Split text into fixed-size chunks."""
        if not text:
            return []

        chunks = []
        char_pos = 0
        chunk_idx = 0

        while char_pos < len(text):
            # Calculate end position
            end_pos = min(char_pos + self.chunk_size, len(text))

            # If not at end of text, try to break at separator
            if end_pos < len(text):
                # Look for last separator within a reasonable distance
                search_start = max(char_pos + self.chunk_size - 200, char_pos)
                last_sep = text.rfind(self.separator, search_start, end_pos)

                if last_sep > char_pos:
                    end_pos = last_sep + len(self.separator)

            chunk_text = text[char_pos:end_pos].strip()
            if chunk_text:
                chunk = Chunk(
                    content=chunk_text,
                    start_char=char_pos,
                    end_char=end_pos,
                    chunk_index=chunk_idx,
                )
                chunks.append(chunk)
                chunk_idx += 1

            # Move position with overlap, but ensure forward progress
            new_char_pos = end_pos - self.overlap
            if new_char_pos <= char_pos:
                # Prevent infinite loop: advance at least by 1 character
                new_char_pos = char_pos + 1
            char_pos = new_char_pos

        self._add_metadata(chunks, metadata)
        return chunks


class SemanticChunker(BaseChunker):
    """
    Semantic chunking strategy.

    Uses sentence boundaries and semantic markers to create meaningful chunks.
    Best for: Articles, documentation, natural language where meaning matters.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
    ) -> None:
        super().__init__(chunk_size, overlap)
        self.min_chunk_size = min_chunk_size

    def _split_sentences(self, text: str) -> list[tuple[str, int, int]]:
        """
        Split text into sentences.

        Returns:
            List of (sentence, start_pos, end_pos)
        """
        # Simple sentence splitting on common boundaries
        sentence_pattern = r"(?<=[.!?])\s+|(?<=[.!?])(?=[A-Z])|(?<=\n)\s*(?=[A-Z])"
        sentences = []

        pos = 0
        for match in re.finditer(sentence_pattern, text):
            sentence = text[pos : match.start()].strip()
            if sentence:
                sentences.append((sentence, pos, match.start()))
            pos = match.end()

        # Add remaining text
        remaining = text[pos:].strip()
        if remaining:
            sentences.append((remaining, pos, len(text)))

        return sentences

    def chunk(
        self, text: str, metadata: Optional[dict[str, Any]] = None
    ) -> list[Chunk]:
        """Split text into semantic chunks."""
        if not text:
            return []

        sentences = self._split_sentences(text)
        if not sentences:
            return [
                Chunk(
                    content=text.strip(),
                    start_char=0,
                    end_char=len(text),
                    chunk_index=0,
                )
            ]

        chunks = []
        current_chunk_sentences = []
        current_chunk_start = sentences[0][1]
        chunk_idx = 0

        for sentence, start_pos, end_pos in sentences:
            current_chunk_sentences.append(sentence)
            current_length = sum(len(s) + 1 for s in current_chunk_sentences)

            # Create chunk if size exceeded
            if current_length >= self.chunk_size:
                if current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences).strip()
                    if len(chunk_text) >= self.min_chunk_size:
                        chunk = Chunk(
                            content=chunk_text,
                            start_char=current_chunk_start,
                            end_char=end_pos,
                            chunk_index=chunk_idx,
                        )
                        chunks.append(chunk)
                        chunk_idx += 1

                # Start new chunk with overlap (previous sentences)
                overlap_sentences = []
                overlap_length = 0
                for s in reversed(current_chunk_sentences):
                    if overlap_length + len(s) < self.overlap:
                        overlap_sentences.insert(0, s)
                        overlap_length += len(s) + 1
                    else:
                        break

                current_chunk_sentences = overlap_sentences + [sentence]
                current_chunk_start = start_pos

        # Add remaining chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences).strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunk = Chunk(
                    content=chunk_text,
                    start_char=current_chunk_start,
                    end_char=len(text),
                    chunk_index=chunk_idx,
                )
                chunks.append(chunk)

        self._add_metadata(chunks, metadata)
        return chunks


class RecursiveChunker(BaseChunker):
    """
    Recursive chunking strategy.

    Tries multiple separators at increasing granularity: \n\n, \n, ". ", " "
    Best for: Mixed content with various structures.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        separators: Optional[list[str]] = None,
    ) -> None:
        super().__init__(chunk_size, overlap, separators[0] if separators else "\n\n")
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def _recursive_split(
        self, text: str, separators: list[str], depth: int = 0
    ) -> list[str]:
        """Recursively split text using separators."""
        good_splits = []
        separator = separators[depth]

        if separator == "":
            # Split character by character as fallback
            return list(text)

        splits = text.split(separator) if separator in text else [text]

        # Filter out empty splits and ones that are too small
        good_splits = [
            s for s in splits if (len(s) > self.min_chunk_size if depth > 0 else True)
        ]

        # If we have good splits at this level, return them
        if len(good_splits) > 1:
            return good_splits

        # Otherwise, try next separator
        if depth < len(separators) - 1:
            new_text = separator.join(splits)
            return self._recursive_split(new_text, separators, depth + 1)

        return good_splits

    @property
    def min_chunk_size(self) -> int:
        """Minimum chunk size before moving to next separator."""
        return self.chunk_size // 4

    def chunk(
        self, text: str, metadata: Optional[dict[str, Any]] = None
    ) -> list[Chunk]:
        """Split text recursively using multiple separators."""
        if not text:
            return []

        # First pass: recursive split
        splits = self._recursive_split(text, self.separators)

        # Merge splits into chunks of target size
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_idx = 0

        for split in splits:
            if not split:
                continue

            # Check if adding this split exceeds chunk size
            test_length = len(current_chunk) + len(split)

            if test_length > self.chunk_size and current_chunk:
                # Finalize current chunk
                chunk = Chunk(
                    content=current_chunk.strip(),
                    start_char=current_start,
                    end_char=current_start + len(current_chunk),
                    chunk_index=chunk_idx,
                )
                chunks.append(chunk)
                chunk_idx += 1

                # Start new chunk with overlap
                overlap_size = min(self.overlap, len(current_chunk))
                current_chunk = current_chunk[-overlap_size:] + split
                current_start += len(current_chunk) - len(split) - overlap_size
            else:
                current_chunk += split

        # Add final chunk
        if current_chunk.strip():
            chunk = Chunk(
                content=current_chunk.strip(),
                start_char=current_start,
                end_char=current_start + len(current_chunk),
                chunk_index=chunk_idx,
            )
            chunks.append(chunk)

        self._add_metadata(chunks, metadata)
        return chunks


class MarkdownChunker(BaseChunker):
    """
    Markdown-aware chunking strategy.

    Respects markdown structure: headers, code blocks, lists.
    Best for: Documentation, markdown files, structured content.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        include_metadata: bool = True,
    ) -> None:
        super().__init__(chunk_size, overlap)
        self.include_metadata = include_metadata

    def _parse_structure(self, text: str) -> list[tuple[str, int, int, int, str]]:
        """
        Parse markdown structure.

        Returns:
            List of (content, start, end, level, type)
            type: "header", "code", "list", "paragraph"
        """
        elements = []

        # Find headers
        for match in re.finditer(r"^(#{1,6})\s+(.+?)$", text, re.MULTILINE):
            level = len(match.group(1))
            elements.append(
                (match.group(0), match.start(), match.end(), level, "header")
            )

        # Find code blocks
        for match in re.finditer(r"```[\s\S]*?```", text):
            elements.append((match.group(0), match.start(), match.end(), 0, "code"))

        # Find lists
        for match in re.finditer(
            r"^[\s]*[-*+]\s+.+?(?=\n(?:[-*+]|\n|#)|$)", text, re.MULTILINE
        ):
            elements.append((match.group(0), match.start(), match.end(), 0, "list"))

        return sorted(elements, key=lambda x: x[1])

    def chunk(
        self, text: str, metadata: Optional[dict[str, Any]] = None
    ) -> list[Chunk]:
        """Split markdown respecting structure."""
        if not text:
            return []

        self._parse_structure(text)
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_idx = 0
        current_metadata = {}

        # Split into paragraphs
        paragraphs = re.split(r"\n\n+", text)

        para_pos = 0
        for para in paragraphs:
            if not para.strip():
                para_pos += len(para) + 2
                continue

            test_length = len(current_chunk) + len(para)

            # Check if this paragraph is a header (update context)
            if para.lstrip().startswith("#"):
                match = re.match(r"^(#{1,6})\s+(.+?)$", para.strip())
                if match:
                    level = len(match.group(1))
                    header = match.group(2)
                    current_metadata["last_header"] = header
                    current_metadata["header_level"] = level

            # Create chunk if size exceeded
            if test_length > self.chunk_size and current_chunk:
                chunk = Chunk(
                    content=current_chunk.strip(),
                    start_char=current_start,
                    end_char=current_start + len(current_chunk),
                    chunk_index=chunk_idx,
                    metadata=current_metadata.copy() if self.include_metadata else {},
                )
                chunks.append(chunk)
                chunk_idx += 1

                # Start new chunk with overlap
                overlap_lines = current_chunk.strip().split("\n")[-2:]
                current_chunk = "\n".join(overlap_lines) + "\n\n" + para
                current_start = para_pos - len("\n".join(overlap_lines)) - 2
            else:
                current_chunk += para + "\n\n"

            para_pos += len(para) + 2

        # Add final chunk
        if current_chunk.strip():
            chunk = Chunk(
                content=current_chunk.strip(),
                start_char=current_start,
                end_char=current_start + len(current_chunk),
                chunk_index=chunk_idx,
                metadata=current_metadata.copy() if self.include_metadata else {},
            )
            chunks.append(chunk)

        self._add_metadata(chunks, metadata)
        return chunks


def create_chunker(
    strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC, **kwargs
) -> BaseChunker:
    """
    Factory function to create chunker instances.

    Args:
        strategy: ChunkingStrategy to use
        **kwargs: Additional arguments for the specific chunker

    Returns:
        BaseChunker instance

    Example:
        chunker = create_chunker(ChunkingStrategy.MARKDOWN)
        chunks = chunker.chunk(text)
    """
    if strategy == ChunkingStrategy.FIXED:
        return FixedChunker(**kwargs)
    elif strategy == ChunkingStrategy.SEMANTIC:
        return SemanticChunker(**kwargs)
    elif strategy == ChunkingStrategy.RECURSIVE:
        return RecursiveChunker(**kwargs)
    elif strategy == ChunkingStrategy.MARKDOWN:
        return MarkdownChunker(**kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
