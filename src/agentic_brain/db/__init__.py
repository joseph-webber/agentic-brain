# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import os
from typing import Any, Dict, Optional

import redis.asyncio as redis


class BrainRedis:
    """Redis client for session management."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self.client = redis.from_url(self.url, decode_responses=True)

    async def set_session(
        self, session_id: str, data: Dict[str, Any], expire: int = 3600
    ):
        import json

        await self.client.set(f"session:{session_id}", json.dumps(data), ex=expire)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        import json

        data = await self.client.get(f"session:{session_id}")
        return json.loads(data) if data else None
