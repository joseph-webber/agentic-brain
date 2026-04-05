from __future__ import annotations

"""Redis-backed backup coder standby service."""

import argparse
import inspect
import json
import os
import time
from collections.abc import Callable
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover - optional runtime dependency
    redis = None

DEFAULT_REDIS_URL = os.getenv(
    "VOICE_REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0"
)
DEFAULT_CHANNEL = "voice:coordination"
DEFAULT_TASK_LIST = "voice:coding_tasks"
DEFAULT_STATUS_KEY = "voice:gpt_backup_status"
DEFAULT_READY_KEY = "voice:gpt_backup_ready"
DEFAULT_RESULTS_KEY = "voice:gpt_backup_results"
DEFAULT_LAST_RESULT_KEY = "voice:gpt_backup_last_result"
DEFAULT_CLAIM_PREFIX = "voice:gpt_backup_claim:"
DEFAULT_TAGS = frozenset({"gpt-backup", "gpt_backup", "backup-coder-2", "gpt-backup-2"})
SOURCE_AGENTS = ("gpt", "claude")


class GPTBackupCoderService:
    """Monitor Redis for coding requests and publish structured results."""

    def __init__(
        self,
        *,
        redis_client: Any | None = None,
        redis_url: str = DEFAULT_REDIS_URL,
        agent_name: str = "gpt-backup-2",
        channel: str = DEFAULT_CHANNEL,
        task_list_key: str = DEFAULT_TASK_LIST,
        status_key: str = DEFAULT_STATUS_KEY,
        ready_key: str = DEFAULT_READY_KEY,
        results_key: str = DEFAULT_RESULTS_KEY,
        last_result_key: str = DEFAULT_LAST_RESULT_KEY,
        claim_prefix: str = DEFAULT_CLAIM_PREFIX,
        requester: Callable[..., Any] | None = None,
        claim_ttl: int = 300,
    ):
        if redis_client is None:
            if redis is None:  # pragma: no cover - depends on optional package
                raise ImportError("redis package is required for GPTBackupCoderService")
            redis_client = redis.from_url(redis_url, decode_responses=True)

        self.redis = redis_client
        self.agent_name = agent_name
        self.channel = channel
        self.task_list_key = task_list_key
        self.status_key = status_key
        self.ready_key = ready_key
        self.results_key = results_key
        self.last_result_key = last_result_key
        self.claim_prefix = claim_prefix
        self.claim_ttl = claim_ttl
        self.requester = requester or self.default_requester

    def default_requester(
        self, prompt: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fallback requester for standby coordination mode."""
        return {
            "summary": prompt,
            "message": (
                "Backup coder #2 received the request, but no executor is configured. "
                "Attach a requester callback to perform coding work automatically."
            ),
            "task_type": payload.get("task_type", "coding") if payload else "coding",
            "mode": "standby",
        }

    def set_status(self, status: str) -> None:
        self.redis.set(self.status_key, status)

    def set_ready(self, ready: bool = True) -> None:
        self.redis.set(self.ready_key, "true" if ready else "false")

    def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "agent": self.agent_name,
            "timestamp": time.time(),
            **payload,
        }
        encoded = json.dumps(event)
        self.redis.publish(self.channel, encoded)
        self.redis.set(self.last_result_key, encoded)
        self.redis.rpush(self.results_key, encoded)
        return event

    @staticmethod
    def decode_task(raw: Any) -> dict[str, Any]:
        """Convert Redis payloads into a normalized dictionary."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return {}
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                return {"prompt": raw}
            return decoded if isinstance(decoded, dict) else {"prompt": str(decoded)}

        if isinstance(raw, dict):
            return raw

        return {"prompt": str(raw)}

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip().lower()

    def _is_source_agent(self, payload: dict[str, Any]) -> bool:
        for key in ("agent", "from", "source_agent", "requested_by", "requester"):
            value = self._normalize_text(payload.get(key))
            if value and any(agent in value for agent in SOURCE_AGENTS):
                return True
        return False

    def _extract_tags(self, payload: dict[str, Any]) -> set[str]:
        tags: set[str] = set()
        for key in ("tag", "tags", "target", "helper", "worker", "role"):
            value = payload.get(key)
            if isinstance(value, str):
                tags.update(
                    part.strip().lower()
                    for chunk in value.split(",")
                    for part in chunk.split()
                    if part.strip()
                )
            elif isinstance(value, (list, tuple, set)):
                tags.update(
                    str(item).strip().lower() for item in value if str(item).strip()
                )
        return tags

    def should_handle(self, payload: dict[str, Any]) -> bool:
        """Only handle requests meant for backup coder #2."""
        if not payload:
            return False

        if payload.get("agent") == self.agent_name:
            return False

        if payload.get("answer") or payload.get("result"):
            return False

        has_prompt = any(
            self._normalize_text(payload.get(key))
            for key in (
                "prompt",
                "question",
                "task",
                "content",
                "request",
                "description",
            )
        )
        if not has_prompt:
            return False

        tags = self._extract_tags(payload)
        if tags & DEFAULT_TAGS:
            return True

        if payload.get("_source") == "task_list":
            return True

        return self._is_source_agent(payload)

    def extract_prompt(self, payload: dict[str, Any]) -> str | None:
        for key in ("prompt", "question", "task", "content", "request", "description"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _claim_request(self, request_id: str | None) -> bool:
        if not request_id:
            return True
        claim_key = f"{self.claim_prefix}{request_id}"
        claimed = self.redis.set(claim_key, self.agent_name, nx=True, ex=self.claim_ttl)
        return bool(claimed)

    def _call_requester(self, prompt: str, payload: dict[str, Any]) -> Any:
        try:
            signature = inspect.signature(self.requester)
        except (TypeError, ValueError):
            signature = None

        if signature and len(signature.parameters) >= 2:
            return self.requester(prompt, payload)
        return self.requester(prompt)

    def handle_payload(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Process a coding request and publish a structured result."""
        if not self.should_handle(payload):
            return None

        prompt = self.extract_prompt(payload)
        if not prompt:
            return None

        request_id = payload.get("request_id")
        if not self._claim_request(request_id):
            return None

        source_agent = (
            payload.get("agent")
            or payload.get("from")
            or payload.get("source_agent")
            or payload.get("requested_by")
            or "unknown"
        )
        self.set_status(f"working: {prompt[:80]}")
        self.publish(
            {
                "request_id": request_id,
                "in_reply_to": source_agent,
                "status": "accepted",
                "prompt": prompt,
                "specialties": [
                    "complex async code",
                    "api wrappers",
                    "test fixtures",
                    "performance optimization",
                    "code review",
                ],
            }
        )

        try:
            result = self._call_requester(prompt, payload)
            response = {
                "request_id": request_id,
                "in_reply_to": source_agent,
                "prompt": prompt,
                "status": "completed",
                "result": result,
                "tag": "gpt-backup",
            }
            self.publish(response)
            self.set_status("standby")
            return response
        except Exception as exc:
            response = {
                "request_id": request_id,
                "in_reply_to": source_agent,
                "prompt": prompt,
                "status": "error",
                "error": str(exc),
                "tag": "gpt-backup",
            }
            self.publish(response)
            self.set_status(f"error: {exc}")
            return response

    def process_task_queue(self, limit: int | None = None) -> int:
        """Process queued coding tasks from Redis."""
        processed = 0
        while limit is None or processed < limit:
            raw = self.redis.lpop(self.task_list_key)
            if raw is None:
                break
            payload = self.decode_task(raw)
            payload["_source"] = "task_list"
            if self.handle_payload(payload):
                processed += 1
        return processed

    def announce_ready(self) -> dict[str, Any]:
        self.set_ready(True)
        self.set_status("standby")
        return self.publish(
            {
                "status": "ready",
                "tag": "gpt-backup",
                "answer": "Backup coder #2 is online, monitoring Redis, and standing by.",
            }
        )

    def monitor_once(self) -> int:
        """Process the current queue once and return handled tasks."""
        return self.process_task_queue()

    def run_forever(self, poll_interval: float = 1.0) -> None:
        """Continuously monitor Redis list and coordination channel."""
        self.announce_ready()
        pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(self.channel)
        try:
            while True:
                self.process_task_queue()
                message = pubsub.get_message(timeout=poll_interval)
                if message and message.get("type") == "message":
                    payload = self.decode_task(message.get("data"))
                    self.handle_payload(payload)
                time.sleep(poll_interval)
        finally:
            self.set_status("stopped")
            pubsub.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redis-backed GPT backup coder")
    parser.add_argument(
        "--once", action="store_true", help="Process queued tasks once and exit"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds for Redis monitoring",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = GPTBackupCoderService()
    service.announce_ready()
    if args.once:
        service.monitor_once()
        return 0

    try:
        service.run_forever(poll_interval=args.poll_interval)
    except KeyboardInterrupt:
        service.set_status("stopped")
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
