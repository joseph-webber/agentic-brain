# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Memory Module
=============

Unified memory and summarization for agentic-brain.
Compatible with brain-core's session_stitcher format.

Exports:
    Core Memory Classes (from _neo4j_memory.py):
    - Neo4jMemory: Persistent memory backed by Neo4j
    - InMemoryStore: In-memory fallback storage
    - Memory: Memory entry dataclass
    - DataScope: Data scope enum (PUBLIC, PRIVATE, CUSTOMER)
    - MemoryConfig: Memory configuration dataclass

    Factory Functions (auto-fallback pattern):
    - get_memory_backend: Get memory with automatic Neo4j -> InMemory fallback
    - reset_memory_backend: Reset the global memory instance

    Summarization (from summarization.py):
    - ConversationSummary: Unified summary format
    - SummaryType: Types of summaries
    - UnifiedSummarizer: Real-time and session summarization
"""

# Import from the neo4j memory module
from ._neo4j_memory import (
    DataScope,
    InMemoryStore,
    Memory as MemoryDataclass,
    MemoryConfig,
    Neo4jMemory,
    get_memory_backend,
    reset_memory_backend,
)
from .unified import (
    Memory,
    MemoryEntry,
    MemoryType,
    SimpleHashEmbedding,
    SQLiteMemoryStore,
    UnifiedMemory,
    get_unified_memory,
)

# Export summarization classes
from .summarization import (
    ConversationSummary,
    SummaryType,
    UnifiedSummarizer,
)

__all__ = [
    # Original memory exports
    "Neo4jMemory",
    "InMemoryStore",
    "Memory",
    "MemoryDataclass",
    "DataScope",
    "MemoryConfig",
    "MemoryEntry",
    "MemoryType",
    "SimpleHashEmbedding",
    "SQLiteMemoryStore",
    "UnifiedMemory",
    # Factory functions (auto-fallback)
    "get_memory_backend",
    "reset_memory_backend",
    "get_unified_memory",
    # Summarization exports
    "ConversationSummary",
    "SummaryType",
    "UnifiedSummarizer",
]
