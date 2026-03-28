# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Inter-bot communication protocol for Agentic Brain."""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Supported message types in the inter-bot protocol."""

    REGISTER = "register"
    HELP = "help"
    CONSENSUS = "consensus"
    HEARTBEAT = "heartbeat"
    TASK = "task"
    RESPONSE = "response"
    STATUS = "status"
    ACK = "ack"


class Priority(Enum):
    """Priority levels for inter-bot messages."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# Finalized protocol channels from the meeting inputs.
CHANNELS = {
    "all": "llm:broadcast",
    "coders": "llm:coders",
    "reviewers": "llm:reviewers",
    "fast": "llm:fast",
    "consensus": "llm:consensus",
}


PROTOCOL: Dict[str, Any] = {
    "version": "1.0",
    "message_format": {
        "id": "uuid - unique message id",
        "from": "bot-id (e.g., gpt-coder, gemini-reviewer)",
        "to": "bot-id or 'all' for broadcast",
        "type": "task|response|status|help|consensus",
        "priority": "low|normal|high|critical",
        "payload": {
            "task": "description of what to do",
            "context": "relevant context",
            "code": "optional code snippet",
            "files": ["list of relevant files"],
        },
        "timestamp": "ISO8601",
        "ttl": "seconds until message expires",
        "requires_response": True,
    },
    "channels": {
        "llm:broadcast": "broadcast to all bots",
        "llm:all": "legacy alias for broadcast",
        "llm:coders": "coding tasks",
        "llm:reviewers": "review tasks",
        "llm:fast": "quick simple tasks",
        "llm:consensus": "voting/agreement",
        "llm:{bot-id}": "direct message to specific bot",
    },
    "handshake": {
        "register": "bot announces itself on startup",
        "heartbeat": "every 30s to show alive",
        "capabilities": "what the bot can do",
    },
    "reliability": {
        "error_handling": {
            "on_timeout": "retry with exponential backoff",
            "on_failure": "route to fallback bot",
            "max_retries": 3,
        },
        "load_balancing": {
            "strategy": "round-robin with capability matching",
            "health_check": "use heartbeat to exclude dead bots",
        },
        "message_acknowledgment": {
            "ack_required": "for high/critical priority",
            "ack_timeout": 10,
        },
        "rate_limiting": {
            "per_bot": "100 msgs/minute",
            "global": "1000 msgs/minute",
        },
    },
    "local_first": {
        "simple_tasks": "Route to local LLM first",
        "fallback_order": ["ollama", "groq", "gemini", "openai", "anthropic"],
        "cost_aware": "Prefer free tiers",
    },
    "compression": {
        "large_payloads": "gzip for > 1KB",
        "binary_support": "for embeddings",
    },
}

# Backwards-compatible alias for callers that want the finalized protocol blob.
FINAL_PROTOCOL = PROTOCOL


@dataclass
class BotMessage:
    """Standard message format for inter-bot communication."""

    from_bot: str
    to_bot: str
    msg_type: MessageType
    payload: Dict[str, Any]
    priority: Priority = Priority.NORMAL
    requires_response: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    id: str = field(
        default_factory=lambda: uuid.uuid4().hex,
    )
    ttl: int = 300

    def to_json(self) -> str:
        """Serialize to the finalized wire format."""
        return json.dumps(
            {
                "id": self.id,
                "from_bot": self.from_bot,
                "to_bot": self.to_bot,
                "msg_type": self.msg_type.value,
                "from": self.from_bot,
                "to": self.to_bot,
                "type": self.msg_type.value,
                "payload": self.payload,
                "priority": self.priority.value,
                "requires_response": self.requires_response,
                "timestamp": self.timestamp,
                "ttl": self.ttl,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> BotMessage:
        """Deserialize from either the finalized or legacy wire format."""
        data = json.loads(json_str)
        return cls(
            from_bot=data.get("from", data.get("from_bot", "")),
            to_bot=data.get("to", data.get("to_bot", "")),
            msg_type=MessageType(data.get("type", data.get("msg_type", "task"))),
            payload=data.get("payload", {}),
            priority=Priority(data.get("priority", "normal")),
            requires_response=data.get(
                "requires_response", data.get("requires_ack", False)
            ),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            id=data.get("id", uuid.uuid4().hex),
            ttl=data.get("ttl", 300),
        )


class InterBotProtocol:
    """
    Redis-based inter-bot communication protocol.

    Implements:
    - Message routing and delivery
    - Exponential backoff on failures
    - Load balancing with health checks
    - ACKs for high-priority traffic
    - Rate limiting
    """

    def __init__(self, redis_client, bot_id: str):
        self.redis = redis_client
        self.bot_id = bot_id
        self.handlers: Dict[MessageType, Callable] = {}

        self.rate_limit_window = 60.0
        self.max_msgs_per_window = 100
        self.msg_count = 0
        self.window_start = time.time()

        self.pending_acks: Dict[str, float] = {}
        self.max_retries = 3

    def _check_rate_limit(self) -> bool:
        """Check if message sending is within rate limits."""
        now = time.time()
        if now - self.window_start > self.rate_limit_window:
            self.window_start = now
            self.msg_count = 0

        if self.msg_count >= self.max_msgs_per_window:
            logger.warning("Rate limit exceeded for bot %s", self.bot_id)
            return False

        self.msg_count += 1
        return True

    def register_handler(self, message_type: MessageType, handler: Callable) -> None:
        """Register a callback for a specific message type."""
        self.handlers[message_type] = handler

    def send_message(
        self,
        target_bot: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: Priority = Priority.NORMAL,
        timeout: int = 10,
    ) -> Optional[str]:
        """Send a message to another bot."""
        if not self._check_rate_limit():
            return None

        requires_response = priority in [Priority.HIGH, Priority.CRITICAL]
        msg = BotMessage(
            from_bot=self.bot_id,
            to_bot=target_bot,
            msg_type=message_type,
            payload=payload,
            priority=priority,
            requires_response=requires_response,
        )

        try:
            self.redis.publish(f"llm:{target_bot}", msg.to_json())
            if requires_response:
                self.pending_acks[msg.id] = time.time() + timeout
            return msg.id
        except Exception as exc:  # pragma: no cover - redis/network failures
            logger.error("Failed to send message to %s: %s", target_bot, exc)
            return None

    def receive_message(self, raw_message: str) -> None:
        """Process an incoming message from Redis."""
        try:
            msg = BotMessage.from_json(raw_message)

            if msg.msg_type == MessageType.ACK:
                ack_for = msg.payload.get("ack_for")
                if ack_for in self.pending_acks:
                    del self.pending_acks[ack_for]
                return

            if msg.requires_response:
                self._send_ack(msg.from_bot, msg.id)

            handler = self.handlers.get(msg.msg_type)
            if handler:
                handler(msg.payload)
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.error("Unexpected error processing message: %s", exc)

    def _send_ack(self, target_bot: str, original_msg_id: str) -> None:
        """Send an acknowledgment receipt."""
        ack_msg = BotMessage(
            from_bot=self.bot_id,
            to_bot=target_bot,
            msg_type=MessageType.ACK,
            payload={"ack_for": original_msg_id},
            priority=Priority.HIGH,
            requires_response=False,
        )
        self.redis.publish(f"llm:{target_bot}", ack_msg.to_json())

    def register_heartbeat(self, role: str) -> None:
        """Register a heartbeat for load balancing."""
        self.redis.setex(f"bot:{self.bot_id}:health", 30, str(time.time()))
        self.redis.sadd(f"registry:role:{role}", self.bot_id)

    def get_healthy_bot(self, role: str) -> Optional[str]:
        """Find a healthy bot for a given role."""
        candidates = self.redis.smembers(f"registry:role:{role}")
        if not candidates:
            return None

        valid_bots = []
        now = time.time()
        for candidate in candidates:
            bot = (
                candidate.decode("utf-8") if isinstance(candidate, bytes) else candidate
            )
            last_heartbeat = self.redis.get(f"bot:{bot}:health")
            if not last_heartbeat:
                continue
            try:
                ts = (
                    float(last_heartbeat)
                    if not isinstance(last_heartbeat, bytes)
                    else float(last_heartbeat.decode("utf-8"))
                )
            except (TypeError, ValueError):
                continue
            if now - ts < 30:
                valid_bots.append(bot)

        if not valid_bots:
            return None
        return random.choice(valid_bots)
