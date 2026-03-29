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
Bot implementations for agentic-brain.

Provides infrastructure for autonomous bot operations:
- Recovery: Retry logic, checkpoints, error recovery
- Messaging: Inter-bot communication via Neo4j
- Health: Service monitoring and notifications

Example:
    >>> from agentic_brain.bots import RecoveryManager, BotMessaging, BotHealth
    >>>
    >>> # Set up recovery with checkpoints
    >>> recovery = RecoveryManager("my_bot")
    >>> recovery.checkpoint("step_1", {"data": "value"})
    >>>
    >>> # Inter-bot messaging
    >>> messaging = BotMessaging("bot_1")
    >>> messaging.send("bot_2", "Hello!", {"key": "value"})
    >>>
    >>> # Health monitoring
    >>> health = BotHealth("my_bot")
    >>> status = health.check_all()
"""

from agentic_brain.bots.health import (
    BotHealth,
    HealthCheckResult,
    HealthStatus,
    RunRecord,
)
from agentic_brain.bots.messaging import (
    BotHandoff,
    BotMessage,
    BotMessaging,
)
from agentic_brain.bots.recovery import (
    RecoveryManager,
    RetryConfig,
    retry,
)
from agentic_brain.bots.secrets import AgentSecrets, BotSecrets
from agentic_brain.bots.session import (
    AgentSession,
    BotSession,
    generate_session_id,
    get_session_key,
)

__all__ = [
    # Recovery
    "RetryConfig",
    "RecoveryManager",
    "retry",
    # Sessions
    "AgentSession",
    "BotSession",
    "generate_session_id",
    "get_session_key",
    # Secrets
    "AgentSecrets",
    "BotSecrets",
    # Messaging
    "BotMessage",
    "BotHandoff",
    "BotMessaging",
    # Health
    "BotHealth",
    "HealthStatus",
    "HealthCheckResult",
    "RunRecord",
]
