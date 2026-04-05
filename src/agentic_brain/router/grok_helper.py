from __future__ import annotations

"""Redis-backed Grok helper for inter-agent coordination."""

import argparse
import json
import os
import time
from collections.abc import Callable
from typing import Any

import requests

try:
    import redis
except ImportError:  # pragma: no cover - optional runtime dependency
    redis = None

DEFAULT_REDIS_URL = os.getenv(
    "VOICE_REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0"
)
DEFAULT_CHANNEL = "voice:coordination"
DEFAULT_TASK_LIST = "voice:helper_tasks"
DEFAULT_STATUS_KEY = "voice:grok_helper_status"
DEFAULT_READY_KEY = "voice:grok_helper_ready"


class GrokHelperService:
    """Coordinate Grok-backed help over Redis."""

    def __init__(
        self,
        *,
        redis_client: Any | None = None,
        redis_url: str = DEFAULT_REDIS_URL,
        agent_name: str = "grok-helper",
        model: str = "grok-3",
        channel: str = DEFAULT_CHANNEL,
        task_list_key: str = DEFAULT_TASK_LIST,
        status_key: str = DEFAULT_STATUS_KEY,
        ready_key: str = DEFAULT_READY_KEY,
        requester: Callable[[str], str] | None = None,
        xai_api_key: str | None = None,
        timeout: int = 30,
    ):
        if redis_client is None:
            if redis is None:  # pragma: no cover - depends on optional package
                raise ImportError("redis package is required for GrokHelperService")
            redis_client = redis.from_url(redis_url, decode_responses=True)

        self.redis = redis_client
        self.agent_name = agent_name
        self.model = model
        self.channel = channel
        self.task_list_key = task_list_key
        self.status_key = status_key
        self.ready_key = ready_key
        self.timeout = timeout
        self.xai_api_key = xai_api_key or os.getenv("XAI_API_KEY")
        self.requester = requester or self.ask_grok

    def ask_grok(self, prompt: str) -> str:
        """Call the xAI chat completions API using environment configuration."""
        if not self.xai_api_key:
            raise RuntimeError("XAI_API_KEY is not configured")

        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.xai_api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"]

    def set_status(self, status: str) -> None:
        self.redis.set(self.status_key, status)

    def set_ready(self, ready: bool = True) -> None:
        self.redis.set(self.ready_key, "true" if ready else "false")

    def publish(self, payload: dict[str, Any]) -> None:
        event = {
            "agent": self.agent_name,
            "timestamp": time.time(),
            **payload,
        }
        self.redis.publish(self.channel, json.dumps(event))

    @staticmethod
    def decode_task(raw: Any) -> dict[str, Any]:
        """Convert Redis task payloads into a normalized dict."""
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

    def should_handle(self, payload: dict[str, Any]) -> bool:
        """Decide if this helper should answer the payload."""
        if not payload:
            return False

        if payload.get("agent") == self.agent_name:
            return False

        if payload.get("answer"):
            return False

        target = payload.get("target") or payload.get("helper")
        if target and target not in {self.agent_name, "grok", "xai"}:
            return False

        return any(
            payload.get(key)
            for key in ("prompt", "question", "task", "content", "request")
        )

    def extract_prompt(self, payload: dict[str, Any]) -> str | None:
        for key in ("prompt", "question", "task", "content", "request"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def handle_payload(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Answer a coordination payload and publish the result."""
        if not self.should_handle(payload):
            return None

        prompt = self.extract_prompt(payload)
        if not prompt:
            return None

        request_id = payload.get("request_id")
        source_agent = payload.get("agent") or payload.get("from") or "unknown"
        self.set_status(f"helping with {prompt[:80]}")

        try:
            answer = self.requester(prompt)
            response = {
                "request_id": request_id,
                "in_reply_to": source_agent,
                "prompt": prompt,
                "answer": answer,
                "status": "completed",
                "provider": "xai",
                "model": self.model,
            }
            self.publish(response)
            self.set_status("idle")
            return response
        except Exception as exc:
            error_response = {
                "request_id": request_id,
                "in_reply_to": source_agent,
                "prompt": prompt,
                "error": str(exc),
                "status": "error",
                "provider": "xai",
                "model": self.model,
            }
            self.publish(error_response)
            self.set_status(f"error: {exc}")
            return error_response

    def process_helper_tasks(self, limit: int | None = None) -> int:
        """Process queued tasks from the helper task list."""
        processed = 0
        while limit is None or processed < limit:
            raw = self.redis.lpop(self.task_list_key)
            if raw is None:
                break
            payload = self.decode_task(raw)
            if self.handle_payload(payload):
                processed += 1
        return processed

    def announce_ready(self) -> None:
        self.set_ready(True)
        if self.xai_api_key:
            self.set_status("ready - waiting for tasks")
        else:
            self.set_status("ready - waiting for XAI_API_KEY")
        self.publish(
            {
                "status": "ready",
                "answer": "Grok helper is online and monitoring Redis.",
                "provider": "xai",
                "model": self.model,
            }
        )

    def monitor_once(self) -> int:
        """Process current backlog once and return tasks handled."""
        return self.process_helper_tasks()

    def run_forever(self, poll_interval: float = 1.0) -> None:
        """Continuously monitor Redis list and coordination channel."""
        self.announce_ready()
        pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(self.channel)
        try:
            while True:
                self.process_helper_tasks()
                message = pubsub.get_message(timeout=poll_interval)
                if message and message.get("type") == "message":
                    payload = self.decode_task(message.get("data"))
                    self.handle_payload(payload)
                time.sleep(poll_interval)
        finally:
            self.set_status("stopped")
            pubsub.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redis-backed Grok helper")
    parser.add_argument(
        "--once", action="store_true", help="Process backlog once and exit"
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
    helper = GrokHelperService()
    helper.announce_ready()
    if args.once:
        helper.monitor_once()
        return 0

    try:
        helper.run_forever(poll_interval=args.poll_interval)
    except KeyboardInterrupt:
        helper.set_status("stopped")
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
