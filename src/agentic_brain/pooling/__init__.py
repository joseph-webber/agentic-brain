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
Connection pooling for Neo4j and HTTP.

Provides efficient connection management with:
- Neo4j connection pooling
- HTTP connection pooling with keep-alive
- Circuit breaker pattern
- Unified pool management

Example:
    >>> from agentic_brain.pooling import PoolManager
    >>>
    >>> pool_manager = PoolManager()
    >>> await pool_manager.startup()
    >>>
    >>> # Neo4j with pooling
    >>> async with pool_manager.neo4j.acquire() as conn:
    ...     result = await conn.run("MATCH (n) RETURN n LIMIT 10")
    >>>
    >>> # HTTP with pooling
    >>> response = await pool_manager.http.get("https://api.example.com/data")
    >>>
    >>> await pool_manager.shutdown()
"""

from agentic_brain.pooling.http_pool import HttpPool, HttpPoolConfig
from agentic_brain.pooling.manager import PoolManager
from agentic_brain.pooling.neo4j_pool import Neo4jPool, Neo4jPoolConfig

__all__ = [
    "Neo4jPool",
    "Neo4jPoolConfig",
    "HttpPool",
    "HttpPoolConfig",
    "PoolManager",
]
