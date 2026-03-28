# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic_brain.core.neo4j_schema import (
    INDEXES,
    VECTOR_INDEX_NAME,
    ensure_indexes,
    ensure_indexes_sync,
)


@pytest.mark.asyncio
async def test_ensure_indexes_runs_all_statements():
    session = AsyncMock()

    await ensure_indexes(session)

    assert session.run.await_count == len(INDEXES)
    assert session.run.await_args_list[0].args[0] == INDEXES[0]


def test_ensure_indexes_sync_runs_all_statements():
    session = MagicMock()

    ensure_indexes_sync(session)

    assert session.run.call_count == len(INDEXES)
    assert (
        session.run.call_args_list[-1]
        .args[0]
        .startswith(f"CREATE VECTOR INDEX {VECTOR_INDEX_NAME}")
    )
