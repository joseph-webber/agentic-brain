# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import json
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.interbot import BotCoordinator, BotMessage, MessageType, Priority


@pytest.fixture
def mock_redis():
    with patch("agentic_brain.router.redis_cache.redis.Redis") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


def test_coordinator_initialization(mock_redis):
    BotCoordinator("test-bot", ["coding", "testing"])

    # Check if bot status was set in redis (via set_bot_status -> hset)
    # The RedisRouterCache.set_bot_status calls hset on "llm:bots"

    # There might be multiple calls (init sets status).
    # RedisRouterCache.__init__ creates self.client.
    # BotCoordinator.__init__ calls self._register()
    # self._register calls self.redis.set_bot_status(...)

    assert mock_redis.hset.called
    # Get the arguments of the call to hset
    # hset("llm:bots", bot_id, json_status)

    # We want to find the call for "llm:bots"
    found = False
    for call in mock_redis.hset.call_args_list:
        args = call[0]
        if args[0] == "llm:bots" and args[1] == "test-bot":
            status = json.loads(args[2])
            if status.get("capabilities") == ["coding", "testing"]:
                found = True
                assert status["status"] == "online"
                break
    assert found, "Bot registration not found in redis calls"


def test_send_message(mock_redis):
    coordinator = BotCoordinator("test-bot", [])
    message = BotMessage(
        from_bot="test-bot",
        to_bot="other-bot",
        msg_type=MessageType.TASK,
        payload={"task": "do something"},
    )

    coordinator.send(message)

    # Check if message was published
    assert mock_redis.publish.called

    # Find the publish call
    # channel = llm:other-bot
    found = False
    for call in mock_redis.publish.call_args_list:
        args = call[0]
        if args[0] == "llm:other-bot":
            msg_data = json.loads(args[1])
            if (
                msg_data.get("msg_type") == "task"
                and msg_data["payload"]["task"] == "do something"
            ):
                found = True
                assert msg_data["from_bot"] == "test-bot"
                assert msg_data["to_bot"] == "other-bot"
                break
    assert found, "Message publication not found"


def test_request_help(mock_redis):
    coordinator = BotCoordinator("test-bot", [])
    coordinator.request_help("fix bug", prefer_capability="debugging")

    # Expect publish to "llm:broadcast" (from CHANNELS["all"])
    found = False
    for call in mock_redis.publish.call_args_list:
        args = call[0]
        if args[0] == "llm:broadcast":
            msg_data = json.loads(args[1])
            if msg_data.get("msg_type") == "help":
                found = True
                assert msg_data["priority"] == "high"
                assert msg_data["payload"]["task"] == "fix bug"
                assert msg_data["payload"]["prefer_capability"] == "debugging"
                assert msg_data["requires_response"] is True
                break
    assert found, "Help request not published correctly"


def test_vote(mock_redis):
    coordinator = BotCoordinator("test-bot", [])
    coordinator.vote("prop-123", True, "looks good")

    # Expect publish to "llm:consensus"
    found = False
    for call in mock_redis.publish.call_args_list:
        args = call[0]
        if args[0] == "llm:consensus":
            msg_data = json.loads(args[1])
            if msg_data.get("msg_type") == "consensus":
                found = True
                assert msg_data["payload"]["proposal_id"] == "prop-123"
                assert msg_data["payload"]["vote"] == "approve"
                assert msg_data["payload"]["comments"] == "looks good"
                break
    assert found, "Vote not published correctly"


def test_heartbeat(mock_redis):
    coordinator = BotCoordinator("test-bot", [])
    coordinator.heartbeat()

    # Check for heartbeat status update
    found = False
    for call in mock_redis.hset.call_args_list:
        args = call[0]
        if args[0] == "llm:bots" and args[1] == "test-bot":
            status = json.loads(args[2])
            if "last_heartbeat" in status:
                found = True
                assert status["status"] == "online"
                break
    assert found, "Heartbeat update not found"
