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

"""Tests for Neo4j connection pooling."""

import os
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.requires_neo4j

from agentic_brain.pooling.neo4j_pool import Neo4jPool, Neo4jPoolConfig

try:
    import neo4j  # noqa: F401

    _NEO4J_DRIVER_AVAILABLE = True
except Exception:
    _NEO4J_DRIVER_AVAILABLE = False

no_neo4j = not _NEO4J_DRIVER_AVAILABLE


@pytest.mark.asyncio
async def test_neo4j_pool_initialization():
    """Test pool initializes with correct settings."""
    config = Neo4jPoolConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
        max_connections=42,
    )
    pool = Neo4jPool(config)

    mock_driver = MagicMock()
    mock_driver.verify_connectivity = MagicMock()

    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver) as driver:
        await pool.startup()

        _, kwargs = driver.call_args
        assert kwargs["max_connection_pool_size"] == 42

        await pool.shutdown()
        mock_driver.close.assert_called_once()


@pytest.mark.asyncio
async def test_neo4j_connection_reuse():
    """Test connections are reused from pool."""
    config = Neo4jPoolConfig(password="test", min_connections=1, max_connections=2)
    pool = Neo4jPool(config)

    mock_driver = MagicMock()
    mock_driver.verify_connectivity = MagicMock()

    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        await pool.startup()

        async with pool.acquire() as conn1:
            pass
        async with pool.acquire() as conn2:
            pass

        assert conn1 is conn2
        await pool.shutdown()


@pytest.mark.asyncio
async def test_neo4j_pool_cleanup():
    """Test pool cleans up properly."""
    pool = Neo4jPool(Neo4jPoolConfig(password="test"))

    mock_driver = MagicMock()
    mock_driver.verify_connectivity = MagicMock()

    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        await pool.startup()
        await pool.shutdown()

    mock_driver.close.assert_called_once()


@pytest.mark.skipif(no_neo4j, reason="Neo4j not available")
@pytest.mark.asyncio
async def test_neo4j_pool_integration():
    """Integration test with real Neo4j."""
    config = Neo4jPoolConfig(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", ""),
    )
    pool = Neo4jPool(config)

    try:
        await pool.startup()
        async with pool.acquire() as conn:
            result = await conn.run("RETURN 1 as value")
        assert result[0]["value"] == 1
    except Exception:
        pytest.skip("Neo4j not available")
    finally:
        await pool.shutdown()
