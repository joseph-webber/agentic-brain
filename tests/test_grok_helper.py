# SPDX-License-Identifier: Apache-2.0
import json
import time

import fakeredis

from agentic_brain.router.grok_helper import GrokHelperService


def _get_pubsub_message(pubsub):
    deadline = time.time() + 1
    while time.time() < deadline:
        message = pubsub.get_message(timeout=0.1)
        if message and message["type"] == "message":
            return message
        time.sleep(0.01)
    return None


def test_handle_payload_publishes_answer_and_updates_status():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    helper = GrokHelperService(
        redis_client=redis_client,
        requester=lambda prompt: f"reply for {prompt}",
    )
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("voice:coordination")

    result = helper.handle_payload(
        {"agent": "claude-agent", "prompt": "write a witty line", "request_id": "req-1"}
    )

    assert result is not None
    assert result["answer"] == "reply for write a witty line"
    assert redis_client.get("voice:grok_helper_status") == "idle"

    message = _get_pubsub_message(pubsub)
    assert message is not None
    payload = json.loads(message["data"])
    assert payload["request_id"] == "req-1"
    assert payload["in_reply_to"] == "claude-agent"
    assert payload["answer"] == "reply for write a witty line"


def test_handle_payload_without_api_key_publishes_error(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    helper = GrokHelperService(redis_client=redis_client)
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("voice:coordination")

    result = helper.handle_payload({"prompt": "need help", "agent": "gpt-agent"})

    assert result is not None
    assert result["status"] == "error"
    assert "XAI_API_KEY" in result["error"]
    assert "XAI_API_KEY" in redis_client.get("voice:grok_helper_status")

    message = _get_pubsub_message(pubsub)
    assert message is not None
    payload = json.loads(message["data"])
    assert payload["status"] == "error"


def test_process_helper_tasks_consumes_queue_and_publishes():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    helper = GrokHelperService(
        redis_client=redis_client,
        requester=lambda prompt: prompt.upper(),
    )
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("voice:coordination")
    redis_client.rpush("voice:helper_tasks", json.dumps({"prompt": "quick answer"}))

    processed = helper.process_helper_tasks()

    assert processed == 1
    assert redis_client.llen("voice:helper_tasks") == 0
    payload = json.loads(_get_pubsub_message(pubsub)["data"])
    assert payload["answer"] == "QUICK ANSWER"


def test_announce_ready_sets_ready_key_and_status():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    helper = GrokHelperService(
        redis_client=redis_client,
        requester=lambda prompt: prompt,
    )
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("voice:coordination")

    helper.announce_ready()

    assert redis_client.get("voice:grok_helper_ready") == "true"
    assert (
        redis_client.get("voice:grok_helper_status")
        == "ready - waiting for XAI_API_KEY"
    )
    payload = json.loads(_get_pubsub_message(pubsub)["data"])
    assert payload["status"] == "ready"
