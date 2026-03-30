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
Agent registry with capability matching and load-balancing.

The registry wraps a ``SwarmCoordinator`` and adds higher-level concerns:
- Capability-based queries ("give me an agent that can do Python")
- Load balancing across available agents (least-loaded wins)
- Health checks via heartbeat TTL expiry
- Agent workload counters (active_tasks field)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .redis_coordinator import SwarmCoordinator, _dumps, _loads, _key_agents_hash, _key_agents_set, _key_hb

logger = logging.getLogger(__name__)

# Increment / decrement key for agent workload tracking.
def _key_workload(swarm_id: str, agent_id: str) -> str:
    return f"swarm:{swarm_id}:workload:{agent_id}"


@dataclass
class AgentProfile:
    """Full agent profile as returned by the registry."""

    agent_id: str
    swarm_id: str
    capabilities: List[str]
    registered_at: float
    status: str = "ready"
    active_tasks: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AgentProfile:
        return cls(
            agent_id=d["agent_id"],
            swarm_id=d.get("swarm_id", ""),
            capabilities=d.get("capabilities", []),
            registered_at=float(d.get("registered_at", 0)),
            status=d.get("status", "ready"),
            active_tasks=int(d.get("active_tasks", 0)),
            metadata={k: v for k, v in d.items()
                      if k not in ("agent_id", "swarm_id", "capabilities",
                                   "registered_at", "status", "active_tasks")},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "swarm_id": self.swarm_id,
            "capabilities": self.capabilities,
            "registered_at": self.registered_at,
            "status": self.status,
            "active_tasks": self.active_tasks,
            **self.metadata,
        }


class AgentRegistry:
    """
    High-level agent registry built on top of ``SwarmCoordinator``.

    Example::

        reg = AgentRegistry(coordinator, swarm_id="pr-review-42")
        reg.register("agent-1", capabilities=["python", "git", "review"])
        reg.register("agent-2", capabilities=["python", "tests"])

        # Pick the least-loaded agent that can review
        agent = reg.pick(required_capabilities=["review"])
        if agent:
            reg.increment_workload(agent.agent_id)
            # ... do work ...
            reg.decrement_workload(agent.agent_id)
    """

    def __init__(self, coordinator: SwarmCoordinator, swarm_id: str) -> None:
        self._c = coordinator
        self._r = coordinator._r
        self.swarm_id = swarm_id

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        agent_id: str | None = None,
        *,
        capabilities: List[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        ttl: int = 60,
    ) -> AgentProfile:
        """Register an agent.  Auto-generates an ID if not provided."""
        agent_id = agent_id or str(uuid.uuid4())
        self._c.register_agent(
            self.swarm_id,
            agent_id,
            capabilities=capabilities,
            metadata=metadata,
            ttl=ttl,
        )
        return self.get(agent_id)  # type: ignore[return-value]

    def deregister(self, agent_id: str) -> None:
        self._c.deregister_agent(self.swarm_id, agent_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        """Return the profile of a single agent (None if no heartbeat)."""
        hb = self._r.get(_key_hb(self.swarm_id, agent_id))
        if hb is None:
            return None
        raw = self._r.hget(_key_agents_hash(self.swarm_id), agent_id)
        if not raw:
            return None
        d = _loads(raw)
        d["active_tasks"] = int(self._r.get(_key_workload(self.swarm_id, agent_id)) or 0)
        return AgentProfile.from_dict(d)

    def all_active(self) -> List[AgentProfile]:
        """Return profiles for all agents with a live heartbeat."""
        ids = self._r.smembers(_key_agents_set(self.swarm_id)) or set()
        profiles: List[AgentProfile] = []
        for aid in ids:
            p = self.get(str(aid))
            if p is not None:
                profiles.append(p)
        return profiles

    def with_capability(self, capability: str) -> List[AgentProfile]:
        """Return active agents that advertise *capability*."""
        return [p for p in self.all_active() if capability in p.capabilities]

    def with_capabilities(self, required: List[str]) -> List[AgentProfile]:
        """Return active agents that have ALL required capabilities."""
        req = set(required)
        return [p for p in self.all_active() if req.issubset(set(p.capabilities))]

    # ------------------------------------------------------------------
    # Load balancing
    # ------------------------------------------------------------------

    def pick(
        self,
        *,
        required_capabilities: List[str] | None = None,
        strategy: str = "least_loaded",
    ) -> Optional[AgentProfile]:
        """
        Pick the best available agent.

        Strategies:
        - ``least_loaded``: agent with fewest active_tasks (default)
        - ``round_robin``: next agent in registration order
        - ``random``: uniform random selection
        """
        import random as _random

        candidates = (
            self.with_capabilities(required_capabilities)
            if required_capabilities
            else self.all_active()
        )
        if not candidates:
            return None

        if strategy == "least_loaded":
            return min(candidates, key=lambda p: p.active_tasks)
        elif strategy == "random":
            return _random.choice(candidates)
        else:
            # round_robin: sort by registration time, pick oldest
            return min(candidates, key=lambda p: p.registered_at)

    def increment_workload(self, agent_id: str) -> int:
        """Increment the agent's active task counter."""
        return int(self._r.incr(_key_workload(self.swarm_id, agent_id)))

    def decrement_workload(self, agent_id: str) -> int:
        """Decrement the agent's active task counter (floor at 0)."""
        new_val = int(self._r.decr(_key_workload(self.swarm_id, agent_id)))
        if new_val < 0:
            self._r.set(_key_workload(self.swarm_id, agent_id), 0)
            return 0
        return new_val

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def health_check(self, agent_id: str) -> Dict[str, Any]:
        """Return health status for a single agent."""
        hb = self._r.get(_key_hb(self.swarm_id, agent_id))
        if hb is None:
            return {"agent_id": agent_id, "healthy": False, "reason": "heartbeat_expired"}
        last_beat = float(hb)
        age = time.time() - last_beat
        profile = self.get(agent_id)
        return {
            "agent_id": agent_id,
            "healthy": True,
            "heartbeat_age_seconds": round(age, 2),
            "active_tasks": profile.active_tasks if profile else 0,
            "capabilities": profile.capabilities if profile else [],
        }

    def health_report(self) -> List[Dict[str, Any]]:
        """Return health status for every registered agent (including expired)."""
        ids = self._r.smembers(_key_agents_set(self.swarm_id)) or set()
        return [self.health_check(str(aid)) for aid in ids]

    def prune_dead_agents(self) -> List[str]:
        """Remove agents whose heartbeat has expired from the active set."""
        ids = list(self._r.smembers(_key_agents_set(self.swarm_id)) or set())
        pruned: List[str] = []
        for aid in ids:
            if self._r.get(_key_hb(self.swarm_id, str(aid))) is None:
                self._r.srem(_key_agents_set(self.swarm_id), aid)
                pruned.append(str(aid))
                logger.info("Pruned dead agent %s from swarm %s", aid, self.swarm_id)
        return pruned
