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
Semantic Prompt Caching for Agentic Brain.

This module provides intelligent caching of LLM responses based on
semantic similarity of prompts, reducing API costs by 50-90% for
repeated or similar queries.

Key Features:
- Semantic key normalization (whitespace, case, punctuation)
- Multiple backends: Memory, SQLite, Redis
- TTL-based expiration with LRU eviction
- Cache metrics for observability
- Thread-safe operations

Example:
    from agentic_brain.cache import SemanticCache, CacheConfig

    cache = SemanticCache(CacheConfig(ttl_seconds=3600))

    # Check cache before API call
    key = cache.create_key(prompt, system, model)
    if cached := await cache.get(key):
        return cached

    # Store after API call
    await cache.set(key, response)
"""

from .semantic_cache import (
    CacheBackend,
    CacheConfig,
    CacheEntry,
    CacheStats,
    MemoryBackend,
    SemanticCache,
    SemanticCacheKey,
    VectorCacheConfig,
    VectorCacheEntry,
    VectorMemoryBackend,
    VectorSemanticCache,
    VectorSQLiteBackend,
)
from .voice_cache import (
    Priority,
    VoiceCache,
    VoicePreferences,
    VoiceQueueItem,
    VoiceRedisCache,
    VoiceState,
    get_voice_cache,
)

__all__ = [
    "SemanticCache",
    "SemanticCacheKey",
    "CacheEntry",
    "CacheConfig",
    "CacheBackend",
    "MemoryBackend",
    "CacheStats",
    "VectorCacheConfig",
    "VectorCacheEntry",
    "VectorMemoryBackend",
    "VectorSQLiteBackend",
    "VectorSemanticCache",
    # Voice cache
    "VoiceCache",
    "VoiceState",
    "VoiceRedisCache",
    "VoiceQueueItem",
    "VoicePreferences",
    "Priority",
    "get_voice_cache",
]
