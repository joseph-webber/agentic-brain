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
Neo4j integration for agentic-brain memory.

Neo4j Access Architecture
=========================

There are **three** places in the codebase that touch Neo4j.  This is
intentional — each serves a different abstraction level.  Understanding the
split prevents accidental duplication.

Layer 1 — ``memory.Neo4jMemory``  (high-level ORM-like interface)
-----------------------------------------------------------------
*Location*: ``agentic_brain/memory/_neo4j_memory.py``

The public API for persistent agent memory.  Application code and Agent
instances always go through this layer.

- Stores / searches :class:`~agentic_brain.memory.Memory` objects
- Handles data-scope isolation (PUBLIC / PRIVATE / CUSTOMER)
- Falls back to :class:`~agentic_brain.memory.InMemoryStore` when Neo4j is
  unavailable
- Reuses the shared driver from :mod:`agentic_brain.core.neo4j_pool`

Usage::

    from agentic_brain import Neo4jMemory, DataScope
    memory = Neo4jMemory()
    memory.store("User prefers dark mode", scope=DataScope.PRIVATE)
    results = memory.search("dark mode", scope=DataScope.PRIVATE)

Layer 2 — ``pooling.Neo4jPool``  (connection-pool for raw Cypher)
-----------------------------------------------------------------
*Location*: ``agentic_brain/pooling/neo4j_pool.py``

An async connection-pool designed for high-throughput, direct Cypher
execution.  Used by the API server and any component that runs many concurrent
queries without needing the ORM model.

- Manages a pool of ``neo4j.AsyncGraphDatabase`` connections
- Exposes an ``async with pool.acquire() as conn:`` context manager
- Tracks connection metrics and enforces circuit-breaking
- Managed by :class:`~agentic_brain.pooling.PoolManager` (startup/shutdown)

Usage::

    from agentic_brain.pooling import PoolManager
    pool_manager = PoolManager()
    await pool_manager.startup()
    async with pool_manager.neo4j.acquire() as conn:
        result = await conn.run("MATCH (n) RETURN count(n) AS n")

Layer 3 — ``neo4j`` package (this module)
-----------------------------------------
*Location*: ``agentic_brain/neo4j/__init__.py``

Reserved namespace for shared Neo4j utilities (schema helpers, index
management, migration utilities).  Currently empty — utilities are added here
as the need arises rather than scattering them across the codebase.

Why not unify Layers 1 and 2?
-----------------------------
``Neo4jMemory`` is synchronous and focused on a single semantic domain
(agent memory), while ``Neo4jPool`` is async and general-purpose.  The split
remains intentional even though both layers now share the same driver factory
via :mod:`agentic_brain.core.neo4j_pool`.
"""

__all__ = []
