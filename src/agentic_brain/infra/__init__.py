# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Infrastructure health monitoring and management.

Provides:
- Health monitoring for Redis, Neo4j, Redpanda
- Auto-restart capabilities
- Event bridge between Redis and Redpanda
"""

from .event_bridge import EventBridge, RedisRedpandaBridge
from .health_monitor import HealthMonitor, ServiceStatus

__all__ = [
    "HealthMonitor",
    "ServiceStatus",
    "EventBridge",
    "RedisRedpandaBridge",
]
