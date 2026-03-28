# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Security posture definitions for SmartRouter.

Security posture is the guard-rail concept that tells SmartRouter which
providers are allowed, how aggressively we can spend money, and whether we need
compliance logging.  Together with :class:`agentic_brain.smart_router.core.SmashMode`
it lets us smash tasks while still respecting enterprise policies.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class PostureMode(Enum):
    """High-level posture categories understood by SmartRouter.

    * ``OPEN`` – allow every enabled worker, useful for exploration.
    * ``STANDARD`` – default mode balancing safety and breadth.
    * ``RESTRICTED`` – only explicitly approved workers (e.g. OpenAI + local).
    * ``AIRGAPPED`` – local-only operation; never touch external APIs.
    * ``COMPLIANCE`` – approved workers with mandatory prompt/response logging.
    """

    OPEN = "open"
    STANDARD = "standard"
    RESTRICTED = "restricted"
    AIRGAPPED = "airgapped"
    COMPLIANCE = "compliance"


@dataclass
class SecurityPosture:
    """
    Declarative security contract for SmartRouter.

    A SecurityPosture combines the selected :class:`PostureMode` with
    fine-grained worker allow/block lists, logging requirements, and cost / rate
    guardrails.  SmartRouter consults this object before selecting workers so it
    can keep sensitive workloads on compliant providers while still using
    SmashMode for safe speed.
    """

    mode: PostureMode = PostureMode.STANDARD

    # Worker restrictions
    allowed_workers: Optional[List[str]] = None  # None = all allowed
    blocked_workers: Optional[List[str]] = None

    # Data handling
    log_prompts: bool = False  # Log all prompts (compliance)
    log_responses: bool = False  # Log all responses (compliance)
    redact_pii: bool = True  # Redact PII before sending

    # Rate limiting
    max_requests_per_minute: int = 60
    max_tokens_per_request: int = 4000

    # Cost controls
    max_cost_per_hour: float = 10.0
    prefer_free_workers: bool = True

    def __post_init__(self):
        if self.blocked_workers is None:
            self.blocked_workers = []

        # Apply mode defaults
        if self.mode == PostureMode.AIRGAPPED:
            self.allowed_workers = ["local"]
            self.log_prompts = False
            self.log_responses = False
        elif self.mode == PostureMode.COMPLIANCE:
            self.log_prompts = True
            self.log_responses = True
            self.redact_pii = True
        elif self.mode == PostureMode.RESTRICTED:
            if self.allowed_workers is None:
                self.allowed_workers = ["openai", "local"]

    def is_worker_allowed(self, worker_name: str) -> bool:
        """Check if a worker is allowed under current posture"""
        if self.blocked_workers and worker_name in self.blocked_workers:
            return False
        if self.allowed_workers is not None:
            return worker_name in self.allowed_workers
        return True

    def filter_workers(self, workers: List[str]) -> List[str]:
        """Filter list of workers to only allowed ones"""
        return [w for w in workers if self.is_worker_allowed(w)]


# Preset postures
POSTURES = {
    "open": SecurityPosture(mode=PostureMode.OPEN),
    "standard": SecurityPosture(mode=PostureMode.STANDARD),
    "restricted": SecurityPosture(
        mode=PostureMode.RESTRICTED,
        allowed_workers=["openai", "local"],
    ),
    "airgapped": SecurityPosture(
        mode=PostureMode.AIRGAPPED,
        allowed_workers=["local"],
    ),
    "compliance": SecurityPosture(
        mode=PostureMode.COMPLIANCE,
        log_prompts=True,
        log_responses=True,
    ),
    "cost_saver": SecurityPosture(
        mode=PostureMode.STANDARD,
        prefer_free_workers=True,
        allowed_workers=["groq", "gemini", "local", "together"],
        max_cost_per_hour=1.0,
    ),
}


def get_posture(name: str) -> SecurityPosture:
    """Get a preset posture by name"""
    return POSTURES.get(name, POSTURES["standard"])
