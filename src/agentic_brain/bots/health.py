# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Health monitoring module for agentic-brain agents.

Provides system health checks for Neo4j, Ollama, and services,
with Mac notification support and health tracking.

Example:
    >>> from agentic_brain.bots import BotHealth, HealthStatus
    >>>
    >>> health = BotHealth("my_agent")
    >>>
    >>> # Run all health checks
    >>> status = health.check_all()
    >>> print(status)  # {"neo4j": True, "ollama": True, ...}
    >>>
    >>> # Get overall status
    >>> if health.is_healthy():
    ...     print("All systems operational")
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """
    Result of a single health check.

    Attributes:
        service: Name of the service checked
        status: Whether the check passed
        message: Human-readable status message
        timestamp: When the check was performed
        duration_ms: How long the check took in milliseconds
    """

    service: str
    status: bool
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0


@dataclass
class RunRecord:
    """
    Record of a bot run.

    Attributes:
        status: Run status (e.g., 'completed', 'failed', 'timeout')
        duration: Run duration in seconds
        error: Optional error message
        timestamp: When the run occurred
    """

    status: str
    duration: float
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class BotHealth:
    """
    Health monitoring for a bot with Mac notifications.

    Provides health checking for system services, run tracking,
    and macOS notification support.

    Example:
        >>> health = BotHealth("my_agent")
        >>>
        >>> # Check individual services
        >>> if health.check_neo4j():
        ...     print("Neo4j is up")
        >>>
        >>> # Check all services
        >>> status = health.check_all()
        >>>
        >>> # Record a run
        >>> health.record_run("completed", 15.5)
        >>>
        >>> # Get statistics
        >>> stats = health.get_stats()
        >>> print(f"Success rate: {stats['success_rate']:.1%}")
    """

    def __init__(self, bot_id: str, logger: Any | None = None) -> None:
        """
        Initialize health monitor for a bot.

        Args:
            bot_id: Unique identifier for the bot
            logger: Optional logger instance for logging
        """
        self.bot_id = bot_id
        self._logger = logger or logging.getLogger(__name__)
        self.history: list[HealthCheckResult] = []
        self.run_records: list[RunRecord] = []
        self._last_notification_time: dict[str, float] = {}
        self._notification_cooldown = 60

        # Service URLs from environment
        self._neo4j_http_url = os.environ.get(
            "NEO4J_HTTP_URL", "http://localhost:7474/db/neo4j/"
        )
        self._ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def check_neo4j(self) -> bool:
        """
        Test Neo4j connection.

        Returns:
            True if Neo4j is accessible, False otherwise
        """
        start = time.time()
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "5", self._neo4j_http_url],
                capture_output=True,
                timeout=10,
            )
            success = result.returncode == 0
            duration = (time.time() - start) * 1000

            self._record_check(
                "neo4j",
                success,
                duration,
                "Connected" if success else "Connection failed",
            )
            return success
        except subprocess.TimeoutExpired:
            duration = (time.time() - start) * 1000
            self._record_check("neo4j", False, duration, "Timeout")
            return False
        except OSError as e:
            duration = (time.time() - start) * 1000
            self._record_check("neo4j", False, duration, str(e))
            return False

    async def check_neo4j_async(self) -> bool:
        """
        Test Neo4j connection asynchronously.

        Returns:
            True if Neo4j is accessible, False otherwise
        """
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl",
                "-s",
                "-m",
                "5",
                self._neo4j_http_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            success = proc.returncode == 0
            duration = (time.time() - start) * 1000

            self._record_check(
                "neo4j",
                success,
                duration,
                "Connected" if success else "Connection failed",
            )
            return success
        except TimeoutError:
            duration = (time.time() - start) * 1000
            self._record_check("neo4j", False, duration, "Timeout")
            return False
        except OSError as e:
            duration = (time.time() - start) * 1000
            self._record_check("neo4j", False, duration, str(e))
            return False

    def check_ollama(self) -> bool:
        """
        Test Ollama availability.

        Returns:
            True if Ollama is accessible, False otherwise
        """
        start = time.time()
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "5", f"{self._ollama_url}/api/tags"],
                capture_output=True,
                timeout=10,
            )
            success = result.returncode == 0
            duration = (time.time() - start) * 1000

            self._record_check(
                "ollama",
                success,
                duration,
                "Available" if success else "Not responding",
            )
            return success
        except subprocess.TimeoutExpired:
            duration = (time.time() - start) * 1000
            self._record_check("ollama", False, duration, "Timeout")
            return False
        except OSError as e:
            duration = (time.time() - start) * 1000
            self._record_check("ollama", False, duration, str(e))
            return False

    async def check_ollama_async(self) -> bool:
        """
        Test Ollama availability asynchronously.

        Returns:
            True if Ollama is accessible, False otherwise
        """
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl",
                "-s",
                "-m",
                "5",
                f"{self._ollama_url}/api/tags",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            success = proc.returncode == 0
            duration = (time.time() - start) * 1000

            self._record_check(
                "ollama",
                success,
                duration,
                "Available" if success else "Not responding",
            )
            return success
        except TimeoutError:
            duration = (time.time() - start) * 1000
            self._record_check("ollama", False, duration, "Timeout")
            return False
        except OSError as e:
            duration = (time.time() - start) * 1000
            self._record_check("ollama", False, duration, str(e))
            return False

    def check_copilot(self) -> bool:
        """
        Test GitHub Copilot CLI availability.

        Returns:
            True if gh copilot CLI is available, False otherwise
        """
        start = time.time()
        try:
            result = subprocess.run(
                ["gh", "copilot", "--version"], capture_output=True, timeout=5
            )
            success = result.returncode == 0
            duration = (time.time() - start) * 1000

            self._record_check(
                "copilot", success, duration, "Available" if success else "Not found"
            )
            return success
        except subprocess.TimeoutExpired:
            duration = (time.time() - start) * 1000
            self._record_check("copilot", False, duration, "Timeout")
            return False
        except FileNotFoundError:
            duration = (time.time() - start) * 1000
            self._record_check("copilot", False, duration, "Not installed")
            return False
        except OSError as e:
            duration = (time.time() - start) * 1000
            self._record_check("copilot", False, duration, str(e))
            return False

    def check_all(self) -> dict[str, bool]:
        """
        Run all health checks.

        Returns:
            Dictionary with service names as keys and health status as values
        """
        return {
            "neo4j": self.check_neo4j(),
            "ollama": self.check_ollama(),
            "copilot": self.check_copilot(),
        }

    async def check_all_async(self) -> dict[str, bool]:
        """
        Run all health checks asynchronously.

        Returns:
            Dictionary with service names as keys and health status as values
        """
        neo4j, ollama = await asyncio.gather(
            self.check_neo4j_async(),
            self.check_ollama_async(),
        )
        return {
            "neo4j": neo4j,
            "ollama": ollama,
            "copilot": self.check_copilot(),
        }

    def notify(
        self,
        message: str,
        title: str | None = None,
        sound: bool = True,
    ) -> None:
        """
        Send a Mac notification.

        Args:
            message: Notification message
            title: Optional notification title (default: bot_id)
            sound: Whether to play notification sound
        """
        title = title or self.bot_id
        self._send_mac_notification(message, title, sound)
        self._log(f"Notification: {title} - {message}")

    def notify_success(self, message: str) -> None:
        """
        Send a success notification.

        Args:
            message: Success message
        """
        self.notify(message, title=f"✓ {self.bot_id}", sound=True)

    def notify_error(self, message: str) -> None:
        """
        Send an error notification.

        Args:
            message: Error message
        """
        self.notify(message, title=f"✗ {self.bot_id}", sound=True)

    def notify_warning(self, message: str) -> None:
        """
        Send a warning notification.

        Args:
            message: Warning message
        """
        self.notify(message, title=f"⚠ {self.bot_id}", sound=True)

    def _send_mac_notification(
        self,
        message: str,
        title: str,
        sound: bool = True,
    ) -> bool:
        """
        Send notification via macOS notification center.

        Args:
            message: Notification message
            title: Notification title
            sound: Whether to play sound

        Returns:
            True if notification was sent successfully
        """
        try:
            message = message.replace('"', '\\"')
            title = title.replace('"', '\\"')

            sound_name = "Glass" if sound else ""

            script = (
                f'display notification "{message}" '
                f'with title "{title}" '
                f'sound name "{sound_name}"'
            )

            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, OSError) as e:
            self._log(f"Failed to send notification: {e}")
            return False

    def record_run(
        self,
        status: str,
        duration: float,
        error: str | None = None,
    ) -> None:
        """
        Record a bot run.

        Args:
            status: Run status (e.g., 'completed', 'failed', 'timeout')
            duration: Run duration in seconds
            error: Optional error message
        """
        record = RunRecord(status=status, duration=duration, error=error)
        self.run_records.append(record)
        self._log(f"Run recorded: {status} ({duration:.2f}s)")

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about bot runs.

        Returns:
            Dictionary with success rate, average duration, and last run info
        """
        if not self.run_records:
            return {
                "total_runs": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "last_run": None,
                "last_status": None,
            }

        successful = sum(1 for r in self.run_records if r.status == "completed")
        total = len(self.run_records)
        avg_duration = sum(r.duration for r in self.run_records) / total
        last_run = self.run_records[-1]

        return {
            "total_runs": total,
            "successful_runs": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_duration": avg_duration,
            "last_run": last_run.timestamp.isoformat(),
            "last_status": last_run.status,
            "last_duration": last_run.duration,
            "last_error": last_run.error,
        }

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get health check history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of health check records
        """
        records = self.history[-limit:]
        return [
            {
                "service": r.service,
                "status": r.status,
                "message": r.message,
                "timestamp": r.timestamp.isoformat(),
                "duration_ms": r.duration_ms,
            }
            for r in records
        ]

    def is_healthy(self) -> bool:
        """
        Check overall system health.

        Returns:
            True if all services are healthy
        """
        if not self.history:
            return True

        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        recent_failures = [
            h for h in self.history if not h.status and h.timestamp > cutoff
        ]

        return len(recent_failures) == 0

    def get_health_status(self) -> HealthStatus:
        """
        Get overall health status.

        Returns:
            HealthStatus enum value
        """
        if not self.history:
            return HealthStatus.UNKNOWN

        recent_checks = self.history[-5:] if len(self.history) >= 5 else self.history
        failed = sum(1 for h in recent_checks if not h.status)

        if failed == 0:
            return HealthStatus.HEALTHY
        elif failed < len(recent_checks) // 2:
            return HealthStatus.WARNING
        else:
            return HealthStatus.ERROR

    def get_status_report(self) -> str:
        """
        Get formatted status report for display.

        Returns:
            Formatted status report string
        """
        lines = [
            f"Bot Health Report: {self.bot_id}",
            f"Timestamp: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Overall Status: {self.get_health_status().value.upper()}",
            "",
        ]

        if self.history:
            lines.append("Recent Health Checks:")
            for check in self.history[-5:]:
                status_icon = "✓" if check.status else "✗"
                lines.append(
                    f"  {status_icon} {check.service}: {check.message} "
                    f"({check.duration_ms:.1f}ms)"
                )
        else:
            lines.append("No health checks performed yet")

        stats = self.get_stats()
        if stats["total_runs"] > 0:
            lines.extend(
                [
                    "",
                    "Run Statistics:",
                    f"  Total Runs: {stats['total_runs']}",
                    f"  Successful: {stats['successful_runs']}",
                    f"  Success Rate: {stats['success_rate']*100:.1f}%",
                    f"  Avg Duration: {stats['avg_duration']:.2f}s",
                    f"  Last Status: {stats['last_status']}",
                ]
            )
            if stats["last_error"]:
                lines.append(f"  Last Error: {stats['last_error']}")

        return "\n".join(lines)

    def _record_check(
        self,
        service: str,
        status: bool,
        duration_ms: float,
        message: str,
    ) -> None:
        """
        Record a health check result.

        Args:
            service: Service name
            status: Health status
            duration_ms: Check duration in milliseconds
            message: Status message
        """
        result = HealthCheckResult(
            service=service, status=status, message=message, duration_ms=duration_ms
        )
        self.history.append(result)

        if not status:
            self._log(f"Health check failed for {service}: {message}")

    def _log(self, message: str) -> None:
        """
        Log a message.

        Args:
            message: Message to log
        """
        self._logger.debug(message)


__all__ = [
    "BotHealth",
    "HealthStatus",
    "HealthCheckResult",
    "RunRecord",
]
