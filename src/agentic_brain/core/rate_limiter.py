"""
Rate Limit Manager - Learns from 429 errors and manages API quotas intelligently.

This module prevents rate limit exhaustion by:
1. Tracking usage across providers (Claude, GPT, Groq, etc.)
2. Implementing exponential backoff with jitter
3. Learning optimal request rates from historical data
4. Distributing load across available providers
5. Queueing requests when limits are approached

Created after massive swarm deployment hit rate limits - lesson learned!
"""

import asyncio
import json
import random
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class RateLimitStrategy(Enum):
    """How to handle rate limits."""

    BACKOFF = "backoff"  # Exponential backoff with jitter
    QUEUE = "queue"  # Queue requests for later
    FAILOVER = "failover"  # Switch to alternate provider
    REJECT = "reject"  # Reject immediately
    PROTECT_ROYALTY = (
        "protect_royalty"  # Use cheap/local LLMs to protect expensive ones
    )


class ProviderTier(Enum):
    """
    Provider tiers for the "Protect the Royalty" strategy.

    Like chess: protect the King (Claude) and Queen (GPT) with
    Knights (Groq/Gemini) and Pawns (local LLMs).
    """

    KING = "king"  # Claude - most capable, expensive, rate limited
    QUEEN = "queen"  # GPT - powerful, costs money
    KNIGHT = "knight"  # Groq/Gemini - fast, free/cheap, some limits
    PAWN = "pawn"  # Local LLM (Ollama) - unlimited, slower, free


@dataclass
class ProviderQuota:
    """Quota configuration for an API provider."""

    name: str
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    tokens_per_minute: int = 100000
    concurrent_limit: int = 10
    cooldown_seconds: int = 60
    priority: int = 1  # Lower = higher priority
    tier: str = "knight"  # king, queen, knight, pawn
    cost_per_1k_tokens: float = 0.0  # For cost tracking
    is_local: bool = False  # Local LLMs can't be rate limited externally


@dataclass
class RateLimitEvent:
    """Record of a rate limit event for learning."""

    provider: str
    timestamp: datetime
    error_code: int
    retry_after: Optional[int]
    request_count_before: int
    tokens_used_before: int
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderState:
    """Current state of a provider's rate limits."""

    name: str
    requests_this_minute: int = 0
    requests_this_hour: int = 0
    requests_this_day: int = 0
    tokens_this_minute: int = 0
    active_requests: int = 0
    last_request_time: Optional[datetime] = None
    last_rate_limit: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    consecutive_errors: int = 0
    total_requests: int = 0
    total_rate_limits: int = 0

    @property
    def is_cooling_down(self) -> bool:
        if not self.cooldown_until:
            return False
        return datetime.now() < self.cooldown_until

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return 1 - (self.total_rate_limits / self.total_requests)


class RateLimitManager:
    """
    Intelligent rate limit manager that learns from failures.

    Features:
    - Per-provider quota tracking
    - Exponential backoff with jitter
    - Provider failover
    - Request queuing
    - Historical learning
    - Concurrent request limiting

    Usage:
        manager = RateLimitManager()

        # Check before making request
        if manager.can_request("claude"):
            async with manager.request_context("claude"):
                response = await make_api_call()
        else:
            # Handle rate limit
            alternative = manager.get_available_provider()
    """

    # Default quotas for known providers
    # PROTECT THE ROYALTY: Use pawns (local) and knights (fast cloud) to protect king (Claude) and queen (GPT)
    DEFAULT_QUOTAS = {
        # KING - Most capable, expensive, protect at all costs
        "claude": ProviderQuota(
            name="claude",
            requests_per_minute=50,
            requests_per_hour=500,
            concurrent_limit=5,
            priority=10,  # HIGH priority number = use LAST (protect!)
            tier="king",
            cost_per_1k_tokens=0.015,
            is_local=False,
        ),
        # QUEEN - Powerful, costs money, protect
        "gpt": ProviderQuota(
            name="gpt",
            requests_per_minute=60,
            requests_per_hour=1000,
            concurrent_limit=10,
            priority=9,  # Use second-to-last
            tier="queen",
            cost_per_1k_tokens=0.01,
            is_local=False,
        ),
        # KNIGHTS - Fast, free/cheap, use freely
        "groq": ProviderQuota(
            name="groq",
            requests_per_minute=30,
            requests_per_hour=1000,
            concurrent_limit=5,
            priority=2,  # Use early - it's fast and free!
            tier="knight",
            cost_per_1k_tokens=0.0,  # FREE
            is_local=False,
        ),
        "gemini": ProviderQuota(
            name="gemini",
            requests_per_minute=60,
            requests_per_hour=1500,
            concurrent_limit=10,
            priority=3,
            tier="knight",
            cost_per_1k_tokens=0.0,  # Free tier generous
            is_local=False,
        ),
        "grok": ProviderQuota(
            name="grok",
            requests_per_minute=60,
            requests_per_hour=1000,
            concurrent_limit=8,
            priority=3,
            tier="knight",
            cost_per_1k_tokens=0.0,
            is_local=False,
        ),
        # PAWNS - Local LLMs, unlimited, use as shields!
        "ollama": ProviderQuota(
            name="ollama",
            requests_per_minute=1000,  # Local, no external limit
            requests_per_hour=100000,
            concurrent_limit=4,  # Limited by hardware
            priority=1,  # LOWEST = use FIRST (it's free & unlimited!)
            tier="pawn",
            cost_per_1k_tokens=0.0,
            is_local=True,  # Can't be rate limited externally!
        ),
    }

    def __init__(
        self,
        quotas: Optional[Dict[str, ProviderQuota]] = None,
        strategy: RateLimitStrategy = RateLimitStrategy.FAILOVER,
        history_file: Optional[Path] = None,
        max_retries: int = 5,
        base_backoff: float = 1.0,
        max_backoff: float = 60.0,
    ):
        self.quotas = quotas or self.DEFAULT_QUOTAS.copy()
        self.strategy = strategy
        self.history_file = (
            history_file or Path.home() / ".agentic-brain" / "rate_limits.json"
        )
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff

        # State tracking
        self.states: Dict[str, ProviderState] = {}
        self.events: List[RateLimitEvent] = []
        self.request_queue: asyncio.Queue = asyncio.Queue()
        self._lock = threading.RLock()

        # Initialize states
        for name in self.quotas:
            self.states[name] = ProviderState(name=name)

        # Load historical data
        self._load_history()

        # Start cleanup task
        self._start_cleanup_task()

    def can_request(self, provider: str, tokens: int = 0) -> bool:
        """Check if a request can be made to this provider."""
        with self._lock:
            if provider not in self.quotas:
                return True  # Unknown provider, allow

            quota = self.quotas[provider]
            state = self.states.get(provider, ProviderState(name=provider))

            # Check cooldown
            if state.is_cooling_down:
                return False

            # Check concurrent limit
            if state.active_requests >= quota.concurrent_limit:
                return False

            # Check rate limits
            if state.requests_this_minute >= quota.requests_per_minute:
                return False
            if state.requests_this_hour >= quota.requests_per_hour:
                return False
            if state.requests_this_day >= quota.requests_per_day:
                return False

            # Check token limit
            return not (tokens > 0 and state.tokens_this_minute + tokens > quota.tokens_per_minute)

    def get_available_provider(
        self, exclude: Optional[List[str]] = None
    ) -> Optional[str]:
        """Get the best available provider, respecting priorities."""
        exclude = exclude or []

        available = []
        for name, quota in self.quotas.items():
            if name in exclude:
                continue
            if self.can_request(name):
                state = self.states.get(name, ProviderState(name=name))
                # Score by priority and success rate
                score = quota.priority * (1 + (1 - state.success_rate))
                available.append((name, score))

        if not available:
            return None

        # Sort by score (lower is better)
        available.sort(key=lambda x: x[1])
        return available[0][0]

    def record_request(self, provider: str, tokens: int = 0) -> None:
        """Record a request being made."""
        with self._lock:
            if provider not in self.states:
                self.states[provider] = ProviderState(name=provider)

            state = self.states[provider]
            state.requests_this_minute += 1
            state.requests_this_hour += 1
            state.requests_this_day += 1
            state.tokens_this_minute += tokens
            state.active_requests += 1
            state.last_request_time = datetime.now()
            state.total_requests += 1

    def record_complete(self, provider: str) -> None:
        """Record a request completing."""
        with self._lock:
            if provider in self.states:
                self.states[provider].active_requests = max(
                    0, self.states[provider].active_requests - 1
                )
                self.states[provider].consecutive_errors = 0

    def record_rate_limit(
        self,
        provider: str,
        error_code: int = 429,
        retry_after: Optional[int] = None,
        context: Optional[Dict] = None,
    ) -> None:
        """Record a rate limit error for learning."""
        with self._lock:
            if provider not in self.states:
                self.states[provider] = ProviderState(name=provider)

            state = self.states[provider]
            state.active_requests = max(0, state.active_requests - 1)
            state.consecutive_errors += 1
            state.total_rate_limits += 1
            state.last_rate_limit = datetime.now()

            # Set cooldown
            cooldown = retry_after or self._calculate_cooldown(provider)
            state.cooldown_until = datetime.now() + timedelta(seconds=cooldown)

            # Record event for learning
            event = RateLimitEvent(
                provider=provider,
                timestamp=datetime.now(),
                error_code=error_code,
                retry_after=retry_after,
                request_count_before=state.requests_this_minute,
                tokens_used_before=state.tokens_this_minute,
                context=context or {},
            )
            self.events.append(event)

            # Learn and adjust quotas
            self._learn_from_event(event)

            # Save history
            self._save_history()

    def _calculate_cooldown(self, provider: str) -> int:
        """Calculate cooldown with exponential backoff and jitter."""
        state = self.states.get(provider, ProviderState(name=provider))
        quota = self.quotas.get(provider, ProviderQuota(name=provider))

        # Exponential backoff
        backoff = min(
            self.base_backoff * (2**state.consecutive_errors), self.max_backoff
        )

        # Add jitter (±25%)
        jitter = backoff * 0.25 * (2 * random.random() - 1)

        return int(max(quota.cooldown_seconds, backoff + jitter))

    def _learn_from_event(self, event: RateLimitEvent) -> None:
        """Learn from rate limit events and adjust quotas."""
        provider = event.provider
        if provider not in self.quotas:
            return

        quota = self.quotas[provider]

        # If we hit limit at X requests/min, set quota to 80% of X
        if event.request_count_before > 0:
            learned_limit = int(event.request_count_before * 0.8)
            if learned_limit < quota.requests_per_minute:
                quota.requests_per_minute = max(1, learned_limit)

        # Reduce concurrent limit if we keep hitting limits
        recent_events = [e for e in self.events[-10:] if e.provider == provider]
        if len(recent_events) >= 3:
            quota.concurrent_limit = max(1, quota.concurrent_limit - 1)

    async def request_context(self, provider: str, tokens: int = 0):
        """Async context manager for tracking requests."""
        return _RequestContext(self, provider, tokens)

    def get_wait_time(self, provider: str) -> float:
        """Get seconds to wait before next request is allowed."""
        with self._lock:
            state = self.states.get(provider)
            if not state or not state.cooldown_until:
                return 0.0

            wait = (state.cooldown_until - datetime.now()).total_seconds()
            return max(0.0, wait)

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all providers."""
        with self._lock:
            return {
                name: {
                    "can_request": self.can_request(name),
                    "requests_this_minute": state.requests_this_minute,
                    "active_requests": state.active_requests,
                    "is_cooling_down": state.is_cooling_down,
                    "cooldown_remaining": self.get_wait_time(name),
                    "success_rate": f"{state.success_rate:.1%}",
                    "total_requests": state.total_requests,
                    "total_rate_limits": state.total_rate_limits,
                }
                for name, state in self.states.items()
            }

    def reset_provider(self, provider: str) -> None:
        """Reset a provider's state (use after extended cooldown)."""
        with self._lock:
            if provider in self.states:
                self.states[provider] = ProviderState(name=provider)

    def _start_cleanup_task(self) -> None:
        """Start background task to reset minute/hour counters."""

        def cleanup():
            while True:
                time.sleep(60)  # Run every minute
                with self._lock:
                    now = datetime.now()
                    for state in self.states.values():
                        # Reset minute counters
                        state.requests_this_minute = 0
                        state.tokens_this_minute = 0

                        # Reset hour counters on the hour
                        if now.minute == 0:
                            state.requests_this_hour = 0

                        # Reset day counters at midnight
                        if now.hour == 0 and now.minute == 0:
                            state.requests_this_day = 0

        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()

    def _load_history(self) -> None:
        """Load historical rate limit data."""
        try:
            if self.history_file.exists():
                data = json.loads(self.history_file.read_text())

                # Restore learned quotas
                for name, quota_data in data.get("quotas", {}).items():
                    if name in self.quotas:
                        self.quotas[name].requests_per_minute = quota_data.get(
                            "requests_per_minute", self.quotas[name].requests_per_minute
                        )
                        self.quotas[name].concurrent_limit = quota_data.get(
                            "concurrent_limit", self.quotas[name].concurrent_limit
                        )
        except Exception:
            pass  # Ignore errors loading history

    def _save_history(self) -> None:
        """Save rate limit history for learning."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "quotas": {
                    name: {
                        "requests_per_minute": quota.requests_per_minute,
                        "concurrent_limit": quota.concurrent_limit,
                    }
                    for name, quota in self.quotas.items()
                },
                "last_updated": datetime.now().isoformat(),
                "recent_events": [
                    {
                        "provider": e.provider,
                        "timestamp": e.timestamp.isoformat(),
                        "error_code": e.error_code,
                    }
                    for e in self.events[-100:]  # Keep last 100 events
                ],
            }

            self.history_file.write_text(json.dumps(data, indent=2))
        except Exception:
            pass  # Ignore errors saving


class _RequestContext:
    """Context manager for tracking API requests."""

    def __init__(self, manager: RateLimitManager, provider: str, tokens: int):
        self.manager = manager
        self.provider = provider
        self.tokens = tokens

    async def __aenter__(self):
        self.manager.record_request(self.provider, self.tokens)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.manager.record_complete(self.provider)
        elif exc_type.__name__ in ("RateLimitError", "HTTPError") or "429" in str(
            exc_val
        ):
            self.manager.record_rate_limit(self.provider)
        else:
            self.manager.record_complete(self.provider)
        return False


# Global instance
_manager: Optional[RateLimitManager] = None


def get_rate_limit_manager() -> RateLimitManager:
    """Get the global rate limit manager instance."""
    global _manager
    if _manager is None:
        _manager = RateLimitManager()
    return _manager


def calculate_safe_agent_count(
    provider: str = "claude",
    task_duration_minutes: int = 10,
    requests_per_agent: int = 20,
) -> int:
    """
    Calculate how many agents can safely run concurrently without hitting rate limits.

    This is the key learning from the swarm deployment!

    Args:
        provider: API provider to use
        task_duration_minutes: Expected duration of each agent task
        requests_per_agent: Estimated API calls per agent

    Returns:
        Safe number of concurrent agents
    """
    manager = get_rate_limit_manager()
    quota = manager.quotas.get(provider, ProviderQuota(name=provider))

    # Calculate requests per minute per agent
    requests_per_minute_per_agent = requests_per_agent / task_duration_minutes

    # Safe agent count = quota / (requests per agent per minute) * safety factor
    safety_factor = 0.7  # 30% buffer
    safe_count = int(
        (quota.requests_per_minute * safety_factor) / requests_per_minute_per_agent
    )

    # Also respect concurrent limit
    safe_count = min(safe_count, quota.concurrent_limit)

    return max(1, safe_count)


# Convenience functions
def can_deploy_agents(count: int, provider: str = "claude") -> bool:
    """Check if it's safe to deploy N agents."""
    safe = calculate_safe_agent_count(provider)
    return count <= safe


def get_deployment_recommendation(
    desired_count: int, provider: str = "claude"
) -> Dict[str, Any]:
    """Get recommendation for deploying agents."""
    safe = calculate_safe_agent_count(provider)
    manager = get_rate_limit_manager()

    if desired_count <= safe:
        return {
            "safe": True,
            "recommended_count": desired_count,
            "message": f"Safe to deploy {desired_count} agents",
        }
    else:
        alternatives = []
        for name in manager.quotas:
            alt_safe = calculate_safe_agent_count(name)
            if alt_safe >= desired_count:
                alternatives.append(name)

        return {
            "safe": False,
            "recommended_count": safe,
            "desired_count": desired_count,
            "message": f"Reduce to {safe} agents or deploy in batches of {safe}",
            "alternative_providers": alternatives,
            "batch_strategy": f"Deploy {safe} agents, wait 5 min, repeat",
        }


# =============================================================================
# TURBO CHESS SWARM - Maximum Speed, Zero Rate Limits
# =============================================================================
#
# The Turbo Chess Strategy: Use cheap/fast models as shields to protect
# expensive rate-limited models. Like chess - sacrifice pawns, protect the king!
#
# WHY THIS WORKS:
# 1. Local LLMs (Ollama) = UNLIMITED, can't be rate limited
# 2. Groq/Gemini = Fast, free/cheap, generous limits
# 3. GPT-mini = Cheap, fast, high limits
# 4. Claude/GPT-4 = Expensive, rate limited - PROTECT THESE!
#
# LESSON LEARNED: Deploying 12 Claude agents = instant 429 errors
# SOLUTION: Deploy 12 agents across ALL tiers = zero rate limits, max speed!
# =============================================================================


@dataclass
class SwarmTask:
    """A task to be executed by the swarm."""

    id: str
    name: str
    prompt: str
    complexity: str = "medium"  # simple, medium, complex
    requires_reasoning: bool = False
    requires_code: bool = False
    priority: int = 5  # 1-10, lower = higher priority


@dataclass
class SwarmAgent:
    """An agent assignment in the swarm."""

    task_id: str
    model: str
    tier: str
    estimated_cost: float = 0.0
    estimated_time_seconds: int = 300


class TurboChessSwarm:
    """
    🏎️ TURBO CHESS SWARM - Maximum parallelism, zero rate limits!

    This is THE way to deploy massive agent swarms without hitting rate limits.
    Uses the chess strategy: pawns and knights do the heavy lifting,
    king and queen are protected for critical tasks only.

    Usage:
        swarm = TurboChessSwarm()

        # Add tasks
        tasks = [
            SwarmTask(id="1", name="docs", prompt="Write documentation"),
            SwarmTask(id="2", name="tests", prompt="Add unit tests"),
            SwarmTask(id="3", name="refactor", prompt="Refactor module", complexity="complex"),
        ]

        # Get optimal distribution
        assignments = swarm.plan_deployment(tasks)

        # Deploy!
        for agent in assignments:
            deploy_agent(agent.model, agent.task_id)

    The swarm automatically:
    - Assigns simple tasks to fast/cheap models (pawns)
    - Assigns medium tasks to Groq/Gemini (knights)
    - Assigns complex reasoning tasks to GPT (queen)
    - ONLY uses Claude (king) for the most critical tasks
    - Maximizes parallelism within rate limits
    - Tracks costs and estimates completion time
    """

    # Model assignments by tier
    TIER_MODELS = {
        "pawn": ["ollama/llama3.2:3b", "ollama/claude-emulator", "gpt-4.1"],
        "knight": [
            "groq/llama-3.3-70b",
            "gemini-1.5-flash",
            "gpt-5-mini",
            "gpt-5.4-mini",
        ],
        "queen": ["gpt-5.2", "gpt-5.4", "claude-haiku-4.5"],
        "king": ["claude-sonnet-4", "claude-opus-4.5", "gpt-5.3-codex"],
    }

    # Complexity to tier mapping
    COMPLEXITY_TIERS = {
        "simple": ["pawn", "knight"],  # Fast models handle simple tasks
        "medium": ["knight", "queen"],  # Mid-tier for medium complexity
        "complex": ["queen", "king"],  # Complex needs powerful models
        "critical": ["king"],  # Only the king for critical
    }

    # Max concurrent agents per tier (respects rate limits)
    TIER_CONCURRENCY = {
        "pawn": 10,  # Local LLMs - hardware limited only
        "knight": 8,  # Groq/Gemini - generous limits
        "queen": 6,  # GPT - moderate limits
        "king": 3,  # Claude - strict limits, PROTECT!
    }

    def __init__(self, rate_manager: Optional[RateLimitManager] = None):
        self.rate_manager = rate_manager or get_rate_limit_manager()
        self._assignments: List[SwarmAgent] = []
        self._tier_counts: Dict[str, int] = defaultdict(int)

    def plan_deployment(
        self,
        tasks: List[SwarmTask],
        prefer_speed: bool = True,
        prefer_cost: bool = True,
        max_king_usage: int = 2,  # Protect the king!
    ) -> List[SwarmAgent]:
        """
        Plan optimal task distribution across model tiers.

        Args:
            tasks: List of tasks to execute
            prefer_speed: Prioritize fast models when possible
            prefer_cost: Prioritize cheap/free models when possible
            max_king_usage: Maximum number of tasks for king tier (protect Claude!)

        Returns:
            List of SwarmAgent assignments
        """
        assignments = []
        tier_counts = defaultdict(int)
        king_count = 0

        # Sort tasks by priority and complexity
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                t.priority,
                {"simple": 0, "medium": 1, "complex": 2, "critical": 3}.get(
                    t.complexity, 1
                ),
            ),
        )

        for task in sorted_tasks:
            # Determine eligible tiers based on complexity
            eligible_tiers = self.COMPLEXITY_TIERS.get(
                task.complexity, ["knight", "queen"]
            )

            # If requires_reasoning or requires_code, bump up tier
            if task.requires_reasoning or task.requires_code:
                if "pawn" in eligible_tiers:
                    eligible_tiers = [t for t in eligible_tiers if t != "pawn"]
                if not eligible_tiers:
                    eligible_tiers = ["knight", "queen"]

            # Find best available tier
            selected_tier = None
            for tier in eligible_tiers:
                # Check concurrency limits
                if tier_counts[tier] < self.TIER_CONCURRENCY[tier]:
                    # Special protection for king
                    if tier == "king" and king_count >= max_king_usage:
                        continue
                    selected_tier = tier
                    break

            # Fallback: find ANY available tier
            if not selected_tier:
                for tier in ["pawn", "knight", "queen", "king"]:
                    if tier_counts[tier] < self.TIER_CONCURRENCY[tier]:
                        if tier == "king" and king_count >= max_king_usage:
                            continue
                        selected_tier = tier
                        break

            # If still no tier (all full), use knight as default
            if not selected_tier:
                selected_tier = "knight"

            # Select model from tier
            models = self.TIER_MODELS[selected_tier]
            model = models[tier_counts[selected_tier] % len(models)]

            # Track king usage
            if selected_tier == "king":
                king_count += 1

            # Create assignment
            assignment = SwarmAgent(
                task_id=task.id,
                model=model,
                tier=selected_tier,
                estimated_cost=self._estimate_cost(selected_tier),
                estimated_time_seconds=self._estimate_time(
                    selected_tier, task.complexity
                ),
            )

            assignments.append(assignment)
            tier_counts[selected_tier] += 1

        self._assignments = assignments
        self._tier_counts = dict(tier_counts)

        return assignments

    def get_deployment_summary(self) -> Dict[str, Any]:
        """Get summary of planned deployment."""
        if not self._assignments:
            return {"error": "No deployment planned. Call plan_deployment() first."}

        total_cost = sum(a.estimated_cost for a in self._assignments)
        max_time = (
            max(a.estimated_time_seconds for a in self._assignments)
            if self._assignments
            else 0
        )

        return {
            "total_agents": len(self._assignments),
            "tier_distribution": self._tier_counts,
            "estimated_total_cost": f"${total_cost:.4f}",
            "estimated_completion_seconds": max_time,
            "rate_limit_risk": (
                "LOW" if self._tier_counts.get("king", 0) <= 2 else "MEDIUM"
            ),
            "strategy": "TURBO_CHESS",
            "models_used": list({a.model for a in self._assignments}),
        }

    def _estimate_cost(self, tier: str) -> float:
        """Estimate cost for a task in this tier."""
        costs = {
            "pawn": 0.0,  # Local = free
            "knight": 0.001,  # Groq/Gemini = basically free
            "queen": 0.01,  # GPT = cheap
            "king": 0.05,  # Claude = expensive
        }
        return costs.get(tier, 0.01)

    def _estimate_time(self, tier: str, complexity: str) -> int:
        """Estimate completion time in seconds."""
        base_times = {
            "pawn": 600,  # Local slower
            "knight": 300,  # Groq FAST
            "queen": 400,  # GPT moderate
            "king": 500,  # Claude thorough
        }
        complexity_multiplier = {
            "simple": 0.5,
            "medium": 1.0,
            "complex": 2.0,
            "critical": 3.0,
        }
        return int(
            base_times.get(tier, 400) * complexity_multiplier.get(complexity, 1.0)
        )

    @classmethod
    def quick_deploy(
        cls,
        task_count: int,
        complexity: str = "medium",
    ) -> List[str]:
        """
        Quick helper to get optimal model distribution for N tasks.

        Usage:
            models = TurboChessSwarm.quick_deploy(12, "medium")
            # Returns: ["gpt-5-mini", "gpt-5.4-mini", "groq/llama-3.3-70b", ...]

        Args:
            task_count: Number of tasks to deploy
            complexity: Overall complexity level

        Returns:
            List of model names to use
        """
        swarm = cls()
        tasks = [
            SwarmTask(id=str(i), name=f"task_{i}", prompt="task", complexity=complexity)
            for i in range(task_count)
        ]
        assignments = swarm.plan_deployment(tasks)
        return [a.model for a in assignments]


# Convenience function for quick access
def turbo_deploy(task_count: int, complexity: str = "medium") -> List[str]:
    """
    🏎️ TURBO DEPLOY - Get optimal model distribution for maximum speed!

    This is the fastest way to deploy a swarm without rate limits.

    Example:
        models = turbo_deploy(12, "medium")
        for i, model in enumerate(models):
            deploy_agent(model, task_prompts[i])

    Args:
        task_count: How many agents to deploy
        complexity: simple, medium, complex, or critical

    Returns:
        List of model names optimized for speed and cost
    """
    return TurboChessSwarm.quick_deploy(task_count, complexity)
