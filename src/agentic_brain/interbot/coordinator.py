# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Bot Coordinator - manages inter-LLM communication."""

import asyncio
import json
from datetime import datetime
from typing import Callable, Dict, List, Optional

from ..router.redis_cache import RedisRouterCache
from .protocol import CHANNELS, BotMessage, MessageType, Priority


class BotCoordinator:
    """Coordinates communication between all LLM bots."""

    def __init__(self, bot_id: str, capabilities: List[str]):
        self.bot_id = bot_id
        self.capabilities = capabilities
        self.redis = RedisRouterCache()
        self.handlers: Dict[MessageType, Callable] = {}
        self._register()

    def _register(self):
        """Register this bot in the network."""
        self.redis.set_bot_status(
            self.bot_id,
            {
                "capabilities": self.capabilities,
                "status": "online",
                "channel": f"llm:{self.bot_id}",
            },
        )
        self.send(
            BotMessage(
                from_bot=self.bot_id,
                to_bot="all",
                msg_type=MessageType.REGISTER,
                payload={"capabilities": self.capabilities},
            )
        )

    def send(self, message: BotMessage):
        """Send message to another bot or broadcast."""
        channel = CHANNELS.get(message.to_bot, f"llm:{message.to_bot}")
        self.redis.client.publish(channel, message.to_json())

    def request_help(self, task: str, prefer_capability: str = None):
        """Request help from other bots."""
        self.send(
            BotMessage(
                from_bot=self.bot_id,
                to_bot="all",
                msg_type=MessageType.HELP,
                priority=Priority.HIGH,
                payload={"task": task, "prefer_capability": prefer_capability},
                requires_response=True,
            )
        )

    def vote(self, proposal_id: str, approve: bool, comments: str = ""):
        """Vote on a consensus proposal."""
        self.send(
            BotMessage(
                from_bot=self.bot_id,
                to_bot="consensus",
                msg_type=MessageType.CONSENSUS,
                payload={
                    "proposal_id": proposal_id,
                    "vote": "approve" if approve else "reject",
                    "comments": comments,
                },
            )
        )

    def heartbeat(self):
        """Send heartbeat to show bot is alive."""
        self.redis.set_bot_status(
            self.bot_id,
            {"status": "online", "last_heartbeat": datetime.utcnow().isoformat()},
        )
