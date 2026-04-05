# 🏎️ Turbo Chess Swarm - Maximum Speed, Zero Rate Limits

The Turbo Chess Swarm is agentic-brain's strategy for deploying massive parallel agent swarms without hitting rate limits.

## The Chess Analogy

Like chess, we protect our most valuable pieces:

| Tier | Piece | Models | Strategy |
|------|-------|--------|----------|
| **King** 👑 | Claude Opus/Sonnet | Most capable, expensive | PROTECT - use sparingly |
| **Queen** ♛ | GPT-4, Claude Haiku | Powerful, moderate cost | Use for complex tasks |
| **Knight** ♞ | Groq, Gemini, GPT-mini | Fast, cheap/free | Use freely! |
| **Pawn** ♟ | Ollama (local) | Unlimited, free | Use as shields |

## Why This Works

1. **Local LLMs (Pawns)** - UNLIMITED, can't be rate limited
2. **Groq/Gemini (Knights)** - Fast, free/cheap, generous limits
3. **GPT-mini (Knights)** - Cheap, fast, high limits
4. **Claude/GPT-4 (King/Queen)** - Expensive, rate limited - PROTECT!

## The Lesson Learned

```
❌ 12 Claude agents = instant 429 rate limit errors
✅ 12 agents across tiers = zero errors, maximum speed!
```

## Quick Start

```python
from agentic_brain.core.rate_limiter import turbo_deploy, TurboChessSwarm

# Quick: Get optimal models for 12 tasks
models = turbo_deploy(12, "medium")
# Returns: ["gpt-5-mini", "groq/llama-3.3-70b", "ollama/llama3.2:3b", ...]

# Advanced: Full control
swarm = TurboChessSwarm()
tasks = [
    SwarmTask(id="1", name="docs", prompt="Write docs", complexity="simple"),
    SwarmTask(id="2", name="refactor", prompt="Refactor", complexity="complex"),
    SwarmTask(id="3", name="security", prompt="Audit", complexity="critical"),
]
assignments = swarm.plan_deployment(tasks, max_king_usage=1)

# Deploy
for agent in assignments:
    print(f"Task {agent.task_id} -> {agent.model} ({agent.tier})")
```

## Complexity Mapping

| Complexity | Eligible Tiers | Example Tasks |
|------------|----------------|---------------|
| `simple` | Pawn, Knight | Docs, formatting, simple edits |
| `medium` | Knight, Queen | Tests, refactoring, debugging |
| `complex` | Queen, King | Architecture, complex reasoning |
| `critical` | King only | Security audits, critical fixes |

## Task Flags

- `requires_reasoning=True` - Bumps task to higher tier
- `requires_code=True` - Bumps task to higher tier
- `priority=1-10` - Lower = assigned first to best tiers

## Deployment Summary

```python
swarm.plan_deployment(tasks)
summary = swarm.get_deployment_summary()
# {
#     "total_agents": 12,
#     "tier_distribution": {"pawn": 4, "knight": 5, "queen": 2, "king": 1},
#     "estimated_total_cost": "$0.0821",
#     "rate_limit_risk": "LOW",
#     "strategy": "TURBO_CHESS"
# }
```

## Concurrency Limits (Default)

| Tier | Max Concurrent |
|------|----------------|
| Pawn | 10 (hardware) |
| Knight | 8 |
| Queen | 6 |
| King | 3 |

## Cost Estimates (per task)

| Tier | Estimated Cost |
|------|----------------|
| Pawn | $0.00 (free!) |
| Knight | $0.001 |
| Queen | $0.01 |
| King | $0.05 |

## The Golden Rule

> **Use pawns and knights liberally. Protect the king at all costs!**

This strategy enabled deploying 20+ agents simultaneously with ZERO rate limits.

---

*Created after learning the hard way - 12 Claude agents = instant 429 errors!*
