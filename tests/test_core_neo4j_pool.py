# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Tests for agentic_brain.core.neo4j_pool."""

from __future__ import annotations

import builtins
import sys
from unittest import mock

from agentic_brain.core.neo4j_pool import (
    configure_pool as configure_neo4j_pool,
)
from agentic_brain.core.neo4j_pool import (
    get_driver as get_neo4j_driver,
)
from agentic_brain.core.neo4j_pool import (
    query as neo4j_query,
)


@mock.patch.dict(sys.modules, {"neo4j": mock.Mock()})
def test_get_neo4j_driver_is_lazy():
    graph_database_mock = mock.Mock()
    graph_database_mock.driver.return_value = mock.Mock()
    sys_modules = builtins.__import__("sys").modules
    sys_modules["neo4j"].GraphDatabase = graph_database_mock

    driver = get_neo4j_driver(uri="bolt://example", user="neo4j", password="secret")
    assert driver is graph_database_mock.driver.return_value
    graph_database_mock.driver.assert_called_once()


@mock.patch.dict(sys.modules, {"neo4j": mock.Mock()})
def test_query_uses_shared_driver():
    graph_database_mock = mock.Mock()
    sys_modules = builtins.__import__("sys").modules
    sys_modules["neo4j"].GraphDatabase = graph_database_mock

    mock_session = mock.MagicMock()
    mock_session.run.return_value = [
        {"value": 1},
        {"value": 2},
    ]

    mock_driver = mock.MagicMock()
    mock_driver.session.return_value = mock_session
    graph_database_mock.driver.return_value = mock_driver

    configure_neo4j_pool(uri="bolt://example", user="neo4j", password="secret")
    rows = neo4j_query("RETURN 1 AS value")

    assert rows == [{"value": 1}, {"value": 2}]
    mock_session.run.assert_called_once()
    mock_session.close.assert_called_once()


@mock.patch.dict(sys.modules, {"neo4j": mock.Mock()})
def test_reconfigure_closes_previous_driver():
    graph_database_mock = mock.Mock()
    sys_modules = builtins.__import__("sys").modules
    sys_modules["neo4j"].GraphDatabase = graph_database_mock

    mock_driver = mock.MagicMock()
    graph_database_mock.driver.return_value = mock_driver

    first = get_neo4j_driver(uri="bolt://example", user="neo4j", password="secret")
    assert first is mock_driver

    # Reconfigure with new URI, should close and recreate driver
    graph_database_mock.driver.return_value = mock.MagicMock()
    second = get_neo4j_driver(uri="bolt://other", user="neo4j", password="secret")

    assert second is graph_database_mock.driver.return_value
    mock_driver.close.assert_called_once()
