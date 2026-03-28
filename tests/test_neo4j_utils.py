from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from neo4j.exceptions import ClientError, ServiceUnavailable, TransientError

from agentic_brain.core.neo4j_utils import resilient_query, resilient_query_sync


class FakeAsyncResult:
    def __init__(self, payload):
        self._payload = payload

    async def data(self):
        return self._payload


@pytest.mark.asyncio
async def test_resilient_query_retries_transient_error():
    session = AsyncMock()
    session.run.side_effect = [
        TransientError("Neo.TransientError.General.DatabaseUnavailable", "retry me"),
        FakeAsyncResult([{"value": 1}]),
    ]

    with patch(
        "agentic_brain.core.neo4j_utils.asyncio.sleep", new=AsyncMock()
    ) as sleep:
        result = await resilient_query(session, "RETURN 1 AS value")

    assert result == [{"value": 1}]
    sleep.assert_awaited_once_with(1)


def test_resilient_query_sync_retries_service_unavailable():
    first_result = MagicMock()
    first_result.data.side_effect = ServiceUnavailable("neo4j down")
    second_result = MagicMock()
    second_result.data.return_value = [{"value": 1}]
    session = MagicMock()
    session.run.side_effect = [first_result, second_result]

    with patch("agentic_brain.core.neo4j_utils.time.sleep") as sleep:
        result = resilient_query_sync(session, "RETURN 1 AS value")

    assert result == [{"value": 1}]
    sleep.assert_called_once_with(1)


def test_resilient_query_sync_does_not_retry_client_error():
    result = MagicMock()
    result.data.side_effect = ClientError(
        "Neo.ClientError.Statement.SyntaxError",
        "bad cypher",
    )
    session = MagicMock()
    session.run.return_value = result

    with patch("agentic_brain.core.neo4j_utils.time.sleep") as sleep:
        with pytest.raises(ClientError):
            resilient_query_sync(session, "RETURN broken")

    sleep.assert_not_called()
