import json
import time

import fakeredis

from agentic_brain.router.gpt_backup import GPTBackupCoderService


def _get_pubsub_message(pubsub):
    deadline = time.time() + 1
    while time.time() < deadline:
        message = pubsub.get_message(timeout=0.1)
        if message and message["type"] == "message":
            return message
        time.sleep(0.01)
    return None


def test_announce_ready_sets_requested_keys():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    service = GPTBackupCoderService(redis_client=redis_client)
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("voice:coordination")

    service.announce_ready()

    assert redis_client.get("voice:gpt_backup_status") == "standby"
    assert redis_client.get("voice:gpt_backup_ready") == "true"
    payload = json.loads(_get_pubsub_message(pubsub)["data"])
    assert payload["status"] == "ready"
    assert payload["tag"] == "gpt-backup"


def test_handle_payload_for_tagged_request_publishes_result_and_resets_status():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    service = GPTBackupCoderService(
        redis_client=redis_client,
        requester=lambda prompt, payload: {
            "summary": prompt.upper(),
            "task_type": payload.get("task_type"),
        },
    )
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("voice:coordination")

    result = service.handle_payload(
        {
            "agent": "human",
            "tags": ["gpt-backup"],
            "prompt": "review async fixture",
            "request_id": "req-42",
            "task_type": "code-review",
        }
    )

    assert result is not None
    assert result["status"] == "completed"
    assert result["result"]["summary"] == "REVIEW ASYNC FIXTURE"
    assert redis_client.get("voice:gpt_backup_status") == "standby"
    assert redis_client.llen("voice:gpt_backup_results") == 2
    assert json.loads(redis_client.get("voice:gpt_backup_last_result"))["status"] == "completed"

    accepted = json.loads(_get_pubsub_message(pubsub)["data"])
    completed = json.loads(_get_pubsub_message(pubsub)["data"])
    assert accepted["status"] == "accepted"
    assert completed["status"] == "completed"
    assert completed["request_id"] == "req-42"


def test_process_task_queue_handles_voice_coding_tasks():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    service = GPTBackupCoderService(
        redis_client=redis_client,
        requester=lambda prompt: {"summary": f"done:{prompt}"},
    )
    redis_client.rpush(
        "voice:coding_tasks",
        json.dumps({"prompt": "optimize cache hit path", "request_id": "queue-1"}),
    )

    processed = service.process_task_queue()

    assert processed == 1
    assert redis_client.llen("voice:coding_tasks") == 0
    assert json.loads(redis_client.get("voice:gpt_backup_last_result"))["status"] == "completed"


def test_should_ignore_unaddressed_channel_noise():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    service = GPTBackupCoderService(redis_client=redis_client)

    result = service.handle_payload(
        {"agent": "browser-helper", "prompt": "this is not for backup coder"}
    )

    assert result is None
    assert redis_client.get("voice:gpt_backup_status") is None


def test_duplicate_request_id_is_claimed_once():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    service = GPTBackupCoderService(
        redis_client=redis_client,
        requester=lambda prompt: {"summary": prompt},
    )

    first = service.handle_payload(
        {"agent": "claude-agent", "prompt": "build fixture", "request_id": "same-1"}
    )
    second = service.handle_payload(
        {"agent": "claude-agent", "prompt": "build fixture", "request_id": "same-1"}
    )

    assert first is not None
    assert second is None
