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
import time
import random
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from collections import defaultdict
import threading


class RateLimitStrategy(Enum):
    """How to handle rate limits."""
    BACKOFF = "backoff"          # Exponential backoff with jitter
    QUEUE = "queue"              # Queue requests for later
    FAILOVER = "failover"        # Switch to alternate provider
    REJECT = "reject"            # Reject immediately
    PROTECT_ROYALTY = "protect_royalty"  # Use cheap/local LLMs to protect expensive ones


class ProviderTier(Enum):
    """
    Provider tiers for the "Protect the Royalty" strategy.
    
    Like chess: protect the King (Claude) and Queen (GPT) with 
    Knights (Groq/Gemini) and Pawns (local LLMs).
    """
    KING = "king"          # Claude - most capable, expensive, rate limited
    QUEEN = "queen"        # GPT - powerful, costs money
    KNIGHT = "knight"      # Groq/Gemini - fast, free/cheap, some limits
    PAWN = "pawn"          # Local LLM (Ollama) - unlimited, slower, free


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
            is_local=False
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
            is_local=False
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
            is_local=False
        ),
        "gemini": ProviderQuota(
            name="gemini",
            requests_per_minute=60,
            requests_per_hour=1500,
            concurrent_limit=10,
            priority=3,
            tier="knight",
            cost_per_1k_tokens=0.0,  # Free tier generous
            is_local=False
        ),
        "grok": ProviderQuota(
            name="grok",
            requests_per_minute=60,
            requests_per_hour=1000,
            concurrent_limit=8,
            priority=3,
            tier="knight",
            cost_per_1k_tokens=0.0,
            is_local=False
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
            is_local=True  # Can't be rate limited externally!
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
        self.history_file = history_file or Path.home() / ".agentic-brain" / "rate_limits.json"
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
            if tokens > 0 and state.tokens_this_minute + tokens > quota.tokens_per_minute:
                return False
            
            return True
    
    def get_available_provider(self, exclude: Optional[List[str]] = None) -> Optional[str]:
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
                self.states[provider].active_requests = max(0, self.states[provider].active_requests - 1)
                self.states[provider].consecutive_errors = 0
    
    def record_rate_limit(
        self,
        provider: str,
        error_code: int = 429,
        retry_after: Optional[int] = None,
        context: Optional[Dict] = None
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
                context=context or {}
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
            self.base_backoff * (2 ** state.consecutive_errors),
            self.max_backoff
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
        recent_events = [
            e for e in self.events[-10:]
            if e.provider == provider
        ]
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
                            "requests_per_minute", 
                            self.quotas[name].requests_per_minute
                        )
                        self.quotas[name].concurrent_limit = quota_data.get(
                            "concurrent_limit",
                            self.quotas[name].concurrent_limit
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
                ]
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
        elif exc_type.__name__ in ("RateLimitError", "HTTPError") or "429" in str(exc_val):
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
    requests_per_agent: int = 20
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


def get_deployment_recommendation(desired_count: int, provider: str = "claude") -> Dict[str, Any]:
    """Get recommendation for deploying agents."""
    safe = calculate_safe_agent_count(provider)
    manager = get_rate_limit_manager()
    
    if desired_count <= safe:
        return {
            "safe": True,
            "recommended_count": desired_count,
            "message": f"Safe to deploy {desired_count} agents"
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
            "batch_strategy": f"Deploy {safe} agents, wait 5 min, repeat"
        }
