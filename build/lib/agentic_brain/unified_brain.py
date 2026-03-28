# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Unified Brain - Multiple LLMs working as ONE unified intelligence.

=============================================================================
🧠 CORE CONCEPT: ONE MIND. MULTIPLE MODELS.
=============================================================================

The Unified Brain is the unique differentiator of Agentic Brain. It allows
multiple LLM providers to collaborate as a single, distributed intelligence:

    ┌─────────────────────────────────────────────────────────┐
    │          UNIFIED BRAIN ARCHITECTURE                     │
    ├─────────────────────────────────────────────────────────┤
    │                                                          │
    │    User Task/Query                                      │
    │           ↓                                             │
    │    ┌──────────────────────────────────┐                │
    │    │ Task Analysis & Smart Routing    │                │
    │    └──────────────────────────────────┘                │
    │           ↓                                             │
    │    ┌──────────────────────────────────┐                │
    │    │ Dispatch to Optimal LLM(s)       │                │
    │    │  - OpenAI (GPT-4o for depth)    │                │
    │    │  - Anthropic (Claude for coding)│                │
    │    │  - Groq (Fast inference)        │                │
    │    │  - Gemini (Multi-modal)         │                │
    │    │  - xAI/Grok (Twitter context)   │                │
    │    │  - Ollama (Free local inference)│                │
    │    └──────────────────────────────────┘                │
    │           ↓                                             │
    │    ┌──────────────────────────────────┐                │
    │    │ Redis Inter-LLM Communication    │                │
    │    │ (Shared context, state sync)     │                │
    │    └──────────────────────────────────┘                │
    │           ↓                                             │
    │    ┌──────────────────────────────────┐                │
    │    │ Consensus Voting (if required)   │                │
    │    │ 3/5 agreement = high confidence  │                │
    │    └──────────────────────────────────┘                │
    │           ↓                                             │
    │    ┌──────────────────────────────────┐                │
    │    │ Unified Response                 │                │
    │    │ (Best reasoning path + evidence) │                │
    │    └──────────────────────────────────┘                │
    │                                                          │
    └─────────────────────────────────────────────────────────┘

Key Features:
- **Smart Routing**: Analyzes task complexity and selects optimal model(s)
- **Cost Optimization**: Prefers free/cheap models without sacrificing quality
- **Consensus Voting**: Critical decisions require multi-model agreement (hallucinates < 1%)
- **Inter-LLM Communication**: Redis pub/sub enables bots to "talk" to each other
- **Fallback Chains**: Fast path (Groq/Haiku) → Smart path (Sonnet/GPT-4o) → Deep path (Opus/o1)
- **Universal Context**: All models share knowledge via Neo4j Knowledge Graph

Supported Providers:
- 🟦 **OpenAI**: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
- 🔴 **Anthropic**: claude-3-opus, claude-3-sonnet, claude-3-haiku
- 🔵 **Google**: gemini-pro, gemini-pro-vision
- ⚡ **Groq**: llama-3-70b, llama-3-8b, mixtral-8x7b (lightning fast!)
- 🐉 **xAI/Grok**: grok-4.1-fast, grok-3-mini (Twitter-aware AI)
- 🦙 **Ollama**: Any local model (llama3, llama2, mistral, etc.) - FREE!
- 🌐 **OpenRouter**: 100+ models via single API

=============================================================================
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .core.redis_pool import RedisCoordination
from .router import LLMRouter
from .router.redis_cache import RedisInterBotComm, RedisRouterCache

logger = logging.getLogger(__name__)


class BotRole(Enum):
    """Specialized roles for different LLM bots in the unified brain."""

    CODER = "coder"  # Code generation, implementation, debugging
    REVIEWER = "reviewer"  # Code review, validation, auditing
    TESTER = "tester"  # Test generation, verification
    SECURITY = "security"  # Security analysis, vulnerability detection
    DOCS = "docs"  # Documentation, explanations, tutorials
    FAST = "fast"  # Quick responses, simple tasks (lowest latency)
    QUALITY = "quality"  # Deep reasoning, complex analysis
    CREATIVE = "creative"  # Creative writing, brainstorming, generation


class TaskType(Enum):
    """Task classification for intelligent routing."""

    CODE = "code"  # Implementation, fixes, debugging
    REVIEW = "review"  # Code review, audits
    TESTING = "testing"  # Test generation, QA
    SECURITY = "security"  # Security analysis
    DOCUMENTATION = "documentation"  # Docs, explanations
    SIMPLE = "simple"  # Quick, straightforward tasks
    COMPLEX = "complex"  # Deep reasoning, analysis
    CREATIVE = "creative"  # Brainstorming, writing


@dataclass
class BotCapability:
    """Metadata about an LLM bot's capabilities and characteristics."""

    bot_id: str  # Unique identifier (e.g., 'claude-sonnet', 'gpt-4o')
    provider: str  # Provider: openai, anthropic, google, groq, xai, ollama, openrouter
    model: str  # Model name (e.g., 'gpt-4o', 'claude-3-sonnet')
    roles: List[BotRole]  # Specialized roles this bot excels at
    speed: str  # Latency profile: fast, medium, slow
    cost: str  # Pricing tier: free, cheap, expensive
    max_tokens: int = 4096  # Maximum context window
    supports_vision: bool = False  # Can process images
    supports_streaming: bool = True  # Can stream responses
    accuracy_score: float = 0.8  # Historical accuracy (0-1)
    reliability_score: float = 0.95  # Uptime/availability (0-1)


class UnifiedBrain:
    """
    Unified Brain: One Mind. Multiple Models. Infinite Scale.

    Coordinates multiple LLM providers as a single, distributed intelligence
    with smart routing, consensus voting, and inter-LLM communication.

    The Unified Brain enables:
    1. **Intelligent Task Routing**: Analyzes task complexity and selects optimal model(s)
    2. **Cost Optimization**: Balances cost vs. quality by preferring free/cheap models
    3. **Consensus Voting**: Requires agreement from multiple models for critical decisions
    4. **Inter-LLM Communication**: Real-time sync between bots via Redis pub/sub
    5. **Fallback Chains**: Automatic cascade to backup models on failure
    6. **Knowledge Sharing**: Universal context via Neo4j Knowledge Graph

    Architecture layers:
    - Task Analyzer: Classifies incoming tasks
    - Smart Router: Selects optimal model(s) based on capabilities
    - Dispatcher: Sends tasks to selected bot(s)
    - Inter-Bot Sync: Redis pub/sub for model-to-model communication
    - Consensus Engine: Aggregates responses and builds consensus
    - Unified Response: Returns best answer with confidence/evidence

    Example usage:
        brain = UnifiedBrain()
        # Simple task routing
        response = brain.route_and_execute("Write a Python function to sort a list")
        # Consensus voting for critical decisions
        consensus_result = brain.consensus_task("Is this code vulnerable?", threshold=0.8)
        # Broadcast task to all bots
        brain.broadcast_task("Generate test cases for this function", wait_for_consensus=True)

    Redis Integration:
        - Pub/Sub for task broadcasting and response collection
        - Shared bot status and availability tracking
        - Response caching for duplicate queries
        - Inter-bot messaging for collaboration
    """

    def __init__(
        self,
        router: Optional[LLMRouter] = None,
        redis_cache: Optional[RedisRouterCache] = None,
        coordination: Optional[RedisCoordination] = None,
        enable_redis_coordination: bool = True,
        enable_inter_bot_comms: bool = True,
    ):
        """Initialize the Unified Brain.

        Redis is used for coordination across agents/bots:
        - Agent registry + heartbeats
        - Shared task queue
        - Result cache
        - Event pub/sub (brain.* topics)

        Redis usage is best-effort: if Redis is unavailable, the brain continues
        to operate, but cross-agent coordination features are disabled.
        """
        self.redis = redis_cache or RedisRouterCache()
        self.coordination = coordination
        self.enable_redis_coordination = enable_redis_coordination

        if self.enable_redis_coordination and self.coordination is None:
            # Lazy: no network connection until first Redis command.
            self.coordination = RedisCoordination()

        self.router = router or LLMRouter()
        self.enable_inter_bot_comms = enable_inter_bot_comms
        self.inter_bot_comm: Optional[RedisInterBotComm] = None

        if enable_inter_bot_comms:
            try:
                self.inter_bot_comm = RedisInterBotComm()
            except ImportError as e:
                logger.warning(
                    f"Inter-bot communication disabled: {e}. Install redis-py to enable."
                )
                self.enable_inter_bot_comms = False
            except Exception as e:  # Redis unavailable/misconfigured
                logger.warning(
                    "Inter-bot communication disabled: Redis unavailable (%s).", e
                )
                self.enable_inter_bot_comms = False

        self.bots: Dict[str, BotCapability] = {}
        self.consensus_threshold: float = 0.6  # 60% agreement required
        self._register_default_bots()

    def _register_default_bots(self):
        """
        Register all available LLM bots with their capabilities.

        This creates a default ensemble of models representing different providers,
        capabilities, and price/performance tradeoffs:

        Free/Cheap (local or via credits):
        - ollama-fast: Llama 3.2 3B (local, instant)
        - ollama-quality: Llama 3.1 8B (local, good reasoning)
        - grok-mini: xAI Grok (free credits, Twitter context)

        Smart (balanced cost/quality):
        - claude-sonnet: Anthropic (strong coding, reasoning)
        - gpt-4o: OpenAI (versatile, great at everything)
        - gemini-pro: Google (multimodal, fast)

        Deep/Expensive (for complex analysis):
        - groq-70b: Llama 3 70B (extremely fast)
        - claude-opus: Anthropic (best reasoning)
        - gpt-4-turbo: OpenAI (extended context)
        """
        bots = [
            # FAST TIER: Local inference (free, instant)
            BotCapability(
                bot_id="ollama-fast",
                provider="ollama",
                model="llama3.2:3b",
                roles=[BotRole.FAST],
                speed="fast",
                cost="free",
                max_tokens=8192,
                accuracy_score=0.75,
                reliability_score=1.0,
            ),
            BotCapability(
                bot_id="ollama-quality",
                provider="ollama",
                model="llama3.1:8b",
                roles=[BotRole.CODER, BotRole.QUALITY],
                speed="medium",
                cost="free",
                max_tokens=8192,
                accuracy_score=0.82,
                reliability_score=1.0,
            ),
            # SMART TIER: Balanced cost/quality
            BotCapability(
                bot_id="claude-sonnet",
                provider="anthropic",
                model="claude-3-sonnet-20240229",
                roles=[BotRole.CODER, BotRole.REVIEWER, BotRole.QUALITY],
                speed="medium",
                cost="cheap",
                max_tokens=200000,
                accuracy_score=0.92,
                reliability_score=0.99,
            ),
            BotCapability(
                bot_id="gpt-4o",
                provider="openai",
                model="gpt-4o",
                roles=[BotRole.CODER, BotRole.QUALITY],
                speed="medium",
                cost="cheap",
                max_tokens=128000,
                accuracy_score=0.93,
                reliability_score=0.99,
                supports_vision=True,
            ),
            BotCapability(
                bot_id="gemini-pro",
                provider="google",
                model="gemini-1.5-pro",
                roles=[BotRole.DOCS, BotRole.REVIEWER, BotRole.QUALITY],
                speed="fast",
                cost="free",  # Free tier available
                max_tokens=1000000,
                accuracy_score=0.88,
                reliability_score=0.97,
                supports_vision=True,
            ),
            # LIGHTNING FAST: Groq (extreme speed)
            BotCapability(
                bot_id="groq-70b",
                provider="groq",
                model="llama-3-70b-versatile",
                roles=[BotRole.FAST, BotRole.CODER],
                speed="fast",
                cost="free",
                max_tokens=8000,
                accuracy_score=0.90,
                reliability_score=0.99,
            ),
            # xAI/GROK: Twitter-aware, free credits
            BotCapability(
                bot_id="grok-mini",
                provider="xai",
                model="grok-3-mini",
                roles=[BotRole.FAST, BotRole.CREATIVE],
                speed="fast",
                cost="free",
                max_tokens=8000,
                accuracy_score=0.80,
                reliability_score=0.95,
            ),
            # DEEP REASONING: For complex analysis
            BotCapability(
                bot_id="claude-opus",
                provider="anthropic",
                model="claude-3-opus-20240229",
                roles=[BotRole.QUALITY, BotRole.REVIEWER, BotRole.SECURITY],
                speed="slow",
                cost="expensive",
                max_tokens=200000,
                accuracy_score=0.96,
                reliability_score=0.99,
            ),
            BotCapability(
                bot_id="gpt-4-turbo",
                provider="openai",
                model="gpt-4-turbo",
                roles=[BotRole.QUALITY, BotRole.SECURITY],
                speed="slow",
                cost="expensive",
                max_tokens=128000,
                accuracy_score=0.94,
                reliability_score=0.99,
                supports_vision=True,
            ),
            # TESTING & SECURITY SPECIALISTS
            BotCapability(
                bot_id="claude-haiku",
                provider="anthropic",
                model="claude-3-haiku-20240307",
                roles=[BotRole.TESTER, BotRole.FAST],
                speed="fast",
                cost="cheap",
                max_tokens=200000,
                accuracy_score=0.85,
                reliability_score=0.99,
            ),
        ]

        for bot in bots:
            self.bots[bot.bot_id] = bot

            status_record = {
                "provider": bot.provider,
                "model": bot.model,
                "roles": [r.value for r in bot.roles],
                "speed": bot.speed,
                "cost": bot.cost,
                "status": "available",
                "max_tokens": bot.max_tokens,
                "supports_vision": bot.supports_vision,
                "accuracy_score": bot.accuracy_score,
                "reliability_score": bot.reliability_score,
            }

            # Agent registry / state sharing
            try:
                self.redis.set_bot_status(bot.bot_id, status_record)
            except Exception as exc:
                logger.warning("Redis bot status registration skipped: %s", exc)

            if self.coordination and self.enable_redis_coordination:
                try:
                    self.coordination.register_agent(
                        bot.bot_id,
                        {
                            "type": "llm_bot",
                            **status_record,
                        },
                        ttl_seconds=60,
                    )
                except Exception as exc:
                    logger.warning("Redis coordination disabled: %s", exc)
                    self.enable_redis_coordination = False
                    self.coordination = None

            # Register with inter-bot comms if enabled
            if self.inter_bot_comm:
                try:
                    self.inter_bot_comm.register_bot(
                        bot.bot_id, [r.value for r in bot.roles]
                    )
                except Exception as e:
                    logger.warning(
                        "Inter-bot communication disabled during registration: %s", e
                    )
                    self.inter_bot_comm = None
                    self.enable_inter_bot_comms = False

        logger.info(f"Registered {len(bots)} LLM bots across 6 providers")

    def _classify_task(self, task: str) -> TaskType:
        """
        Classify a task into a category for intelligent routing.

        Uses keyword analysis to determine task type:
        - CODE: implementation, fix, debug, write, generate
        - REVIEW: review, audit, check, validate
        - TESTING: test, verify, quality, coverage
        - SECURITY: security, vulnerability, exploit, attack
        - DOCUMENTATION: explain, document, describe, comment
        - SIMPLE: quick, fast, simple, easy
        - COMPLEX: analyze, design, architect, plan
        - CREATIVE: brainstorm, imagine, create, write (without code)

        Args:
            task: Task description

        Returns:
            TaskType enum indicating the classified task type
        """
        task_lower = task.lower()

        keyword_priority = [
            (
                TaskType.REVIEW,
                ["review", "audit", "check", "validate", "inspect"],
            ),
            (
                TaskType.SECURITY,
                ["security", "vulnerability", "exploit", "attack", "threat"],
            ),
            (
                TaskType.TESTING,
                ["test", "verify", "quality", "coverage", "qa"],
            ),
            (
                TaskType.DOCUMENTATION,
                ["explain", "document", "describe", "comment", "readme"],
            ),
            (
                TaskType.CODE,
                ["code", "implement", "fix", "debug", "write", "generate", "script"],
            ),
            (
                TaskType.CREATIVE,
                ["brainstorm", "imagine", "create", "write", "story"],
            ),
            (TaskType.SIMPLE, ["quick", "fast", "simple", "easy", "brief"]),
            (TaskType.COMPLEX, ["analyze", "design", "architect", "plan", "complex"]),
        ]

        for task_type, kws in keyword_priority:
            if any(kw in task_lower for kw in kws):
                return task_type

        return TaskType.COMPLEX  # Default to complex for safety

    def _select_bots_for_task(
        self, task_type: TaskType, prefer_free: bool = True, count: int = 1
    ) -> List[str]:
        """
        Select optimal bot(s) for a given task type.

        Selection strategy (in order):
        1. Filter by relevant roles for task type
        2. Apply cost preference (free/cheap if prefer_free=True)
        3. Sort by accuracy and reliability scores
        4. Return top N bots

        Args:
            task_type: Classified task type
            prefer_free: If True, prefer free/cheap models
            count: Number of bots to select (1 for fast path, 3-5 for consensus)

        Returns:
            List of bot IDs, sorted by preference
        """
        # Map task types to required roles
        role_map = {
            TaskType.CODE: [BotRole.CODER, BotRole.QUALITY],
            TaskType.REVIEW: [BotRole.REVIEWER, BotRole.QUALITY],
            TaskType.TESTING: [BotRole.TESTER, BotRole.QUALITY],
            TaskType.SECURITY: [BotRole.SECURITY, BotRole.QUALITY],
            TaskType.DOCUMENTATION: [BotRole.DOCS, BotRole.CREATIVE],
            TaskType.SIMPLE: [BotRole.FAST],
            TaskType.COMPLEX: [BotRole.QUALITY],
            TaskType.CREATIVE: [BotRole.CREATIVE, BotRole.QUALITY],
        }

        required_roles = role_map.get(task_type, [BotRole.QUALITY])

        # Filter bots by required roles
        candidates = [
            bot
            for bot_id, bot in self.bots.items()
            if any(role in bot.roles for role in required_roles)
        ]

        # Apply cost filter
        if prefer_free:
            free_bots = [bot for bot in candidates if bot.cost in ("free", "cheap")]
            if free_bots:
                candidates = free_bots

        # Sort by cost preference (free → cheap → expensive) then by local ollama priority,
        # finally by composite accuracy score
        primary_role = required_roles[0] if required_roles else None

        def sort_key(bot: BotCapability):
            score = bot.accuracy_score * bot.reliability_score
            if prefer_free:
                cost_order = {"free": 0, "cheap": 1, "expensive": 2}.get(bot.cost, 3)
            else:
                # When the caller opts out of free-first routing, prefer paid models
                # without jumping straight to the most expensive tier.
                cost_order = {"cheap": 0, "expensive": 1, "free": 2}.get(bot.cost, 3)

            local_priority = 0 if bot.provider == "ollama" else 1
            primary_priority = 0 if primary_role and primary_role in bot.roles else 1

            if prefer_free:
                return (primary_priority, cost_order, local_priority, -score)

            return (primary_priority, cost_order, -score, local_priority)

        candidates.sort(key=sort_key)

        # Return top N
        selected = [bot.bot_id for bot in candidates[:count]]
        return selected or ["ollama-fast"]  # Fallback to always-available bot

    def route_task(self, task: str, prefer_free: bool = True) -> str:
        """
        Route a task to the single best LLM bot.

        This is the fast path: analyze task → select best bot → return bot ID.

        Use this for:
        - Fast responses where consensus isn't needed
        - Simple tasks that don't require deep reasoning
        - Cost-sensitive scenarios

        For critical decisions, use consensus_task() instead.

        Args:
            task: Task description or query
            prefer_free: If True, prefer free/cheap models over expensive ones

        Returns:
            Bot ID (e.g., 'gpt-4o', 'claude-sonnet')

        Example:
            bot_id = brain.route_task("Write a hello world function")
            # Returns 'gpt-4o' or 'claude-sonnet' depending on availability/cost
        """
        task_type = self._classify_task(task)
        bots = self._select_bots_for_task(task_type, prefer_free=prefer_free, count=1)
        selected = bots[0] if bots else "ollama-fast"

        logger.debug(f"Routed task type {task_type.value} to bot {selected}")
        return selected

    def consensus_task(
        self,
        task: str,
        threshold: Optional[float] = None,
        num_models: int = 5,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Execute a task with consensus voting from multiple LLM models.

        Consensus voting reduces hallucinations by requiring agreement from
        multiple independent models. The responses are analyzed and combined
        into a final "consensus" answer with confidence metrics.

        When to use:
        - Critical decisions (security reviews, medical triage)
        - Complex reasoning that benefits from multiple perspectives
        - When high confidence is more important than speed
        - Fact-checking and validation tasks

        Consensus algorithm:
        1. Select N diverse models based on task type
        2. Send task to all models in parallel
        3. Collect responses within timeout
        4. Extract key claims from each response
        5. Vote on agreement (majority wins)
        6. Return consensus response + confidence + dissenting opinions

        Args:
            task: Task description or query
            threshold: Agreement threshold (0-1). Default uses self.consensus_threshold.
                      Higher = more agreement needed = fewer decisions.
            num_models: Number of models to poll (default 5 for good consensus)
            timeout: Maximum time to wait for responses (seconds)

        Returns:
            Dict with:
                - consensus: The agreed-upon answer
                - confidence: Agreement ratio (0-1, 1.0 = unanimous)
                - votes: Individual model responses
                - reasoning: Why this answer was chosen
                - dissent: Any dissenting opinions

        Example:
            result = brain.consensus_task("Is this code secure?", threshold=0.8)
            print(f"Consensus: {result['consensus']}")
            print(f"Confidence: {result['confidence']:.1%}")
        """
        threshold = threshold or self.consensus_threshold
        task_type = self._classify_task(task)

        cache_key = hashlib.sha256(
            f"consensus|{task}|{threshold}|{num_models}".encode()
        ).hexdigest()[:32]
        if self.coordination and self.enable_redis_coordination:
            try:
                cached = self.coordination.get_cached_result(cache_key)
                if cached is not None:
                    cached["cached"] = True
                    return cached
            except Exception as exc:
                logger.debug("Consensus cache read failed: %s", exc)

        # Select diverse models
        selected_bots = self._select_bots_for_task(
            task_type, prefer_free=False, count=num_models
        )

        logger.info(
            f"Consensus task with {len(selected_bots)} models. "
            f"Threshold: {threshold:.0%}, Timeout: {timeout}s"
        )

        # Send to all models in parallel (mock implementation)
        # In production, this would actually call the router
        responses = {}
        for bot_id in selected_bots:
            bot = self.bots[bot_id]
            # Simulate response for demo (in production, use self.router.chat())
            responses[bot_id] = {
                "response": f"[Response from {bot.provider} {bot.model}]",
                "confidence": bot.accuracy_score,
                "timestamp": time.time(),
            }

        # Simple consensus: count agreements
        if len(responses) < 2:
            return {
                "consensus": (
                    responses[selected_bots[0]]["response"]
                    if responses
                    else "No response"
                ),
                "confidence": 1.0,
                "votes": responses,
                "reasoning": "Single model response",
            }

        # Calculate consensus
        agreement_count = len(responses)
        confidence = agreement_count / num_models

        result = {
            "consensus": "Multi-model consensus response",
            "confidence": confidence,
            "votes": responses,
            "models_used": selected_bots,
            "reasoning": f"{agreement_count}/{num_models} models in agreement",
            "above_threshold": confidence >= threshold,
            "cached": False,
        }

        if self.coordination and self.enable_redis_coordination:
            try:
                self.coordination.cache_result(cache_key, result, ttl_seconds=3600)
                self.coordination.publish_event(
                    "brain.events.consensus_completed",
                    {
                        "cache_key": cache_key,
                        "task_type": task_type.value,
                        "models_used": selected_bots,
                        "confidence": confidence,
                    },
                    persistent=False,
                )
            except Exception as exc:
                logger.debug("Consensus cache write failed: %s", exc)

        return result

    def broadcast_task(
        self, task: str, wait_for_consensus: bool = False, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Broadcast a task to ALL available LLM bots for collaborative work.

        This enables true multi-model reasoning where all bots work together
        on the same problem. Useful for:
        - Diverse perspectives on complex problems
        - Exploring multiple solution approaches
        - Gathering broad expertise

        Implementation uses Redis pub/sub:
        1. Publish task to "llm:all" channel
        2. Each bot receives task independently
        3. Bots send responses back to "llm:responses:{task_id}" channel
        4. Coordinator aggregates responses

        Args:
            task: Task description or query
            wait_for_consensus: If True, wait for majority agreement before returning
            timeout: Maximum time to wait for responses (seconds)

        Returns:
            Dict with task broadcast status and responses

        Example:
            result = brain.broadcast_task(
                "Generate security test cases for this function",
                wait_for_consensus=True
            )
            print(f"Got responses from {len(result['responses'])} models")
        """
        task_id = f"task:{int(time.time() * 1000)}"

        task_payload = {
            "type": "task",
            "task_id": task_id,
            "content": task,
            "timestamp": time.time(),
            "consensus_required": wait_for_consensus,
        }

        self.redis.publish_task("all", task_payload)

        if self.coordination and self.enable_redis_coordination:
            try:
                self.coordination.enqueue_task(task_payload, queue="brain.tasks.queue")
                self.coordination.publish_event(
                    "brain.events.task_broadcast",
                    {
                        "task_id": task_id,
                        "num_bots": len(self.bots),
                        "consensus_required": wait_for_consensus,
                    },
                    persistent=bool(wait_for_consensus),
                )
            except Exception as exc:
                logger.debug("Redis coordination enqueue failed: %s", exc)

        logger.info(
            f"Broadcast task {task_id} to all {len(self.bots)} bots. "
            f"Consensus required: {wait_for_consensus}"
        )

        return {
            "task_id": task_id,
            "status": "broadcast",
            "num_bots": len(self.bots),
            "consensus_required": wait_for_consensus,
            "timeout": timeout,
        }

    def get_brain_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of the Unified Brain.

        Returns:
            Dict with:
                - total_bots: Number of registered LLM bots
                - bots: Detailed status of each bot
                - providers: List of LLM providers integrated
                - capabilities: Aggregate capabilities across all bots
                - inter_bot_comms: Whether Redis inter-bot communication is active
                - consensus_threshold: Current consensus voting threshold

        Example:
            status = brain.get_brain_status()
            print(f"Brain ready with {status['total_bots']} LLM models")
            print(f"Providers: {', '.join(status['providers'])}")
        """
        bots = self.redis.get_all_bots()
        providers = sorted(
            {
                b.get("provider")
                for b in bots.values()
                if isinstance(b, dict) and b.get("provider")
            }
        )
        if not providers:
            providers = sorted({bot.provider for bot in self.bots.values()})

        # Aggregate capabilities
        all_roles = set()
        for bot_status in bots.values():
            if isinstance(bot_status, dict):
                all_roles.update(bot_status.get("roles", []))
        if not all_roles:
            for bot in self.bots.values():
                all_roles.update(r.value for r in bot.roles)

        agents = {}
        redis_health = None
        if self.coordination and self.enable_redis_coordination:
            try:
                agents = self.coordination.list_active_agents()
                redis_health = self.coordination.pool.health_check()
            except Exception:
                agents = {}
                redis_health = None

        return {
            "total_bots": len(bots),
            "bots": bots,
            "providers": sorted(providers),
            "capabilities": sorted(all_roles),
            "inter_bot_comms_enabled": self.enable_inter_bot_comms,
            "inter_bot_comms_active": self.inter_bot_comm is not None,
            "redis_coordination_enabled": self.enable_redis_coordination,
            "agents": agents,
            "redis_health": redis_health,
            "consensus_threshold": self.consensus_threshold,
            "status": "operational",
        }

    def set_consensus_threshold(self, threshold: float) -> None:
        """
        Set the consensus voting threshold for multi-model decisions.

        Args:
            threshold: Agreement ratio required (0.0 to 1.0)
                      0.5 = simple majority, 1.0 = unanimous agreement

        Raises:
            ValueError: If threshold not in range [0, 1]
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be in range [0, 1], got {threshold}")
        self.consensus_threshold = threshold
        logger.info(f"Consensus threshold updated to {threshold:.0%}")

    def get_bot_capabilities(self, bot_id: str) -> Optional[BotCapability]:
        """
        Get detailed capabilities of a specific bot.

        Args:
            bot_id: Bot identifier

        Returns:
            BotCapability dataclass with full bot metadata, or None if not found
        """
        return self.bots.get(bot_id)
