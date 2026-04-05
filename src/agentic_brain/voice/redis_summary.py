# SPDX-License-Identifier: Apache-2.0
"""
Redis Voice Summary Feature

Provides voice summaries of what's happening in Redis/Redpanda:
- Event stream status
- Queue lengths
- Recent events
- System health

Perfect for accessibility - Joseph can hear what the brain is doing!
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .resilient import ResilientVoice


@dataclass
class RedisSummary:
    """Summary of Redis state."""

    connected: bool = False
    queue_length: int = 0
    recent_events: int = 0
    last_event_type: str = ""
    last_event_time: Optional[datetime] = None
    memory_usage: str = ""
    uptime: str = ""
    error: str = ""


class RedisVoiceSummary:
    """Provide voice summaries of Redis/Redpanda activity."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> bool:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            return False

        try:
            self._redis = aioredis.from_url(self.redis_url)
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get_summary(self) -> RedisSummary:
        """Get current Redis summary."""
        summary = RedisSummary()

        if not self._redis:
            if not await self.connect():
                summary.error = "Could not connect to Redis"
                return summary

        try:
            # Check connection
            await self._redis.ping()
            summary.connected = True

            # Voice queue length
            queue_len = await self._redis.llen("agentic-brain-voice-queue")
            summary.queue_length = queue_len or 0

            # Recent events (from brain.events list)
            events_len = await self._redis.llen("brain.events")
            summary.recent_events = events_len or 0

            # Last event
            last_event = await self._redis.lindex("brain.events", 0)
            if last_event:
                try:
                    event = json.loads(last_event)
                    summary.last_event_type = event.get("type", "unknown")
                    if "timestamp" in event:
                        summary.last_event_time = datetime.fromisoformat(
                            event["timestamp"]
                        )
                except (json.JSONDecodeError, ValueError):
                    pass

            # Memory usage
            info = await self._redis.info("memory")
            if "used_memory_human" in info:
                summary.memory_usage = info["used_memory_human"]

            # Uptime
            server_info = await self._redis.info("server")
            if "uptime_in_seconds" in server_info:
                uptime_secs = int(server_info["uptime_in_seconds"])
                hours, remainder = divmod(uptime_secs, 3600)
                minutes, _ = divmod(remainder, 60)
                summary.uptime = f"{hours} hours {minutes} minutes"

        except Exception as e:
            summary.error = str(e)

        return summary

    def _format_summary_text(self, summary: RedisSummary) -> str:
        """Format summary as speakable text."""
        if not summary.connected:
            return f"Redis is not connected. {summary.error}"

        parts = ["Here's what's happening in the brain."]

        # Queue status
        if summary.queue_length > 0:
            parts.append(f"Voice queue has {summary.queue_length} messages waiting.")
        else:
            parts.append("Voice queue is empty, all caught up!")

        # Events
        if summary.recent_events > 0:
            parts.append(f"There are {summary.recent_events} recent events in the log.")

            if summary.last_event_type:
                parts.append(
                    f"Last event was: {summary.last_event_type.replace('_', ' ')}."
                )

                if summary.last_event_time:
                    delta = datetime.now() - summary.last_event_time
                    if delta < timedelta(minutes=1):
                        parts.append("That was just now.")
                    elif delta < timedelta(hours=1):
                        mins = int(delta.total_seconds() / 60)
                        parts.append(f"That was {mins} minutes ago.")
                    else:
                        hours = int(delta.total_seconds() / 3600)
                        parts.append(f"That was {hours} hours ago.")
        else:
            parts.append("No recent events recorded.")

        # System health
        if summary.memory_usage:
            parts.append(f"Redis is using {summary.memory_usage} of memory.")

        if summary.uptime:
            parts.append(f"System has been up for {summary.uptime}.")

        return " ".join(parts)

    async def speak_summary(
        self,
        voice: str = "Karen (Premium)",
        rate: int = 155,
        speak_func=None,
    ) -> bool:
        """Get and speak the Redis summary."""
        summary = await self.get_summary()
        text = self._format_summary_text(summary)

        speaker = speak_func or ResilientVoice.speak
        return await speaker(text, voice=voice, rate=rate)

    async def get_voice_queue_status(self) -> str:
        """Get just voice queue status as speakable text."""
        if not self._redis:
            if not await self.connect():
                return "Cannot connect to Redis to check voice queue."

        try:
            queue_len = await self._redis.llen("agentic-brain-voice-queue")

            if queue_len == 0:
                return "Voice queue is empty. Ready for new messages."
            elif queue_len == 1:
                return "One message in the voice queue."
            else:
                return f"{queue_len} messages waiting in the voice queue."
        except Exception as e:
            return f"Could not check voice queue: {e}"

    async def speak_queue_status(
        self, voice: str = "Karen (Premium)", rate: int = 155
    ) -> bool:
        """Speak current voice queue status."""
        text = await self.get_voice_queue_status()
        return await ResilientVoice.speak(text, voice=voice, rate=rate)


# Global instance
_summary_instance: Optional[RedisVoiceSummary] = None


async def get_redis_summary() -> RedisVoiceSummary:
    """Get global Redis summary instance."""
    global _summary_instance
    if _summary_instance is None:
        _summary_instance = RedisVoiceSummary()
        await _summary_instance.connect()
    return _summary_instance


async def speak_redis_summary(voice: str = "Karen (Premium)") -> bool:
    """Speak Redis summary using default voice."""
    summary = await get_redis_summary()
    return await summary.speak_summary(voice=voice)


async def speak_queue_status(voice: str = "Karen (Premium)") -> bool:
    """Speak voice queue status."""
    summary = await get_redis_summary()
    return await summary.speak_queue_status(voice=voice)
