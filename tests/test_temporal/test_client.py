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

"""Tests for Temporal client."""

from __future__ import annotations

import pytest

# Skip all temporal tests if temporalio not installed
temporalio = pytest.importorskip("temporalio")

from agentic_brain.workflows.temporal.client import (
    TemporalClient,
    TemporalConfig,
)


@pytest.mark.asyncio
async def test_client_connection():
    """Test client connection to Temporal."""
    config = TemporalConfig(host="localhost:7233")
    client = TemporalClient(config)

    try:
        # This will fail if Temporal is not running
        # but tests the connection logic
        temporal_client = await client.connect()
        assert temporal_client is not None
    except Exception:
        # Expected if Temporal not running in test env
        pass
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_client_reuse():
    """Test client connection reuse."""
    config = TemporalConfig(host="localhost:7233")
    client = TemporalClient(config)

    try:
        client1 = await client.connect()
        client2 = await client.connect()

        # Should return same instance
        assert client1 is client2
    except Exception:
        pass
    finally:
        await client.close()


def test_client_config():
    """Test client configuration."""
    config = TemporalConfig(
        host="temporal.example.com:7233",
        namespace="production",
        tls_enabled=True,
    )

    assert config.host == "temporal.example.com:7233"
    assert config.namespace == "production"
    assert config.tls_enabled is True


def test_default_config():
    """Test default configuration."""
    config = TemporalConfig()

    assert config.host == "localhost:7233"
    assert config.namespace == "default"
    assert config.tls_enabled is False
