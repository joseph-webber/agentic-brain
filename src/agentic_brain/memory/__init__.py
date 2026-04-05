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
    
    **Unified Session Management (CANONICAL - from session_manager.py):**
    - SessionManager: Factory/manager with auto-fallback
    - Session: Active conversation session
    - SessionMessage: Message dataclass with importance scoring
    - SessionSummary: Session summary for persistence
    - SessionConfig: Configuration options
    - get_session_manager: Get global singleton instance
    
    See docs/SESSION_MANAGEMENT.md for the canonical approach.
"""

# Import from the neo4j memory module
from ._neo4j_memory import (
    DataScope,
    InMemoryStore,
    MemoryConfig,
    Neo4jMemory,
    get_memory_backend,
    reset_memory_backend,
)
from ._neo4j_memory import (
    Memory as MemoryDataclass,
)

# Export Neo4j conversation memory
from .neo4j_memory import (
    ConversationMemory,
    Message,
)
from .neo4j_memory import (
    MemoryConfig as ConversationMemoryConfig,
)

# Export unified session management (canonical)
from .session_manager import (
    MessageRole,
    Neo4jSessionBackend,
    Session,
    SessionConfig,
    SessionManager,
    SessionMessage,
    SessionSummary,
    SQLiteSessionBackend,
    get_session_manager,
    reset_session_manager,
)

# Export summarization classes
from .summarization import (
    ConversationSummary,
    SummaryType,
    UnifiedSummarizer,
)
from .unified import (
    HookEvent,
    Memory,
    MemoryEntry,
    MemoryType,
    SessionHooks,
    SessionLink,
    SessionStitcher,
    SimpleHashEmbedding,
    SQLiteMemoryStore,
    UnifiedMemory,
    find_related_sessions,
    get_session_context,
    get_session_hooks,
    get_session_stitcher,
    get_unified_memory,
    on_assistant_response,
    on_session_end,
    on_session_start,
    on_tool_use,
    on_user_prompt,
    on_voice_input,
    stitch_message,
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
    # Neo4j conversation memory
    "ConversationMemory",
    "ConversationMemoryConfig",
    "Message",
    # Summarization exports
    "ConversationSummary",
    "SummaryType",
    "UnifiedSummarizer",
    # Unified Session Management (canonical)
    "SessionManager",
    "Session",
    "SessionMessage",
    "SessionSummary",
    "SessionConfig",
    "MessageRole",
    "Neo4jSessionBackend",
    "SQLiteSessionBackend",
    "get_session_manager",
    "reset_session_manager",
    # Consolidated hook and stitcher exports (CANONICAL)
    "HookEvent",
    "SessionLink",
    "SessionHooks",
    "SessionStitcher",
    "get_session_hooks",
    "get_session_stitcher",
    "on_session_start",
    "on_session_end",
    "on_user_prompt",
    "on_assistant_response",
    "on_tool_use",
    "on_voice_input",
    "stitch_message",
    "find_related_sessions",
    "get_session_context",
]
