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

Provides multiple chunking approaches:
- Fixed-size: Simple, predictable chunks
- Semantic: Chunks based on semantic boundaries
- Recursive: Hierarchical chunking with fallback
- Markdown-aware: Respects document structure
- Chonkie-powered: 33x faster chunking via the Chonkie library
  (token, sentence, and semantic strategies with GPU acceleration)

Usage:
    # Built-in chunkers
    from agentic_brain.rag.chunking import SemanticChunker, create_chunker

    chunker = SemanticChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk("Your text here...")

    # Chonkie-powered fast chunking (33x faster)
    from agentic_brain.rag.chunking import ChonkieChunker

    chunker = ChonkieChunker(strategy="semantic", chunk_size=512)
    chunks = chunker.chunk("Your text here...")
"""

# Re-export everything from the original base module
from .base import (
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

# Chonkie-powered fast chunking (optional dependency)
CHONKIE_AVAILABLE = False
try:
    from .chonkie_chunker import (
        CHONKIE_AVAILABLE,
        ChonkieChunker,
        ChonkieStrategy,
        benchmark_chunkers,
    )
except (ImportError, ModuleNotFoundError):
    pass

__all__ = [
    # Base chunking
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_MIN_CHUNK_SIZE",
    "BaseChunker",
    "Chunk",
    "ChunkingStrategy",
    "FixedChunker",
    "SemanticChunker",
    "RecursiveChunker",
    "MarkdownChunker",
    "create_chunker",
    # Chonkie fast chunking
    "CHONKIE_AVAILABLE",
    "ChonkieChunker",
    "ChonkieStrategy",
    "benchmark_chunkers",
]
