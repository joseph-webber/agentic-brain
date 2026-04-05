# Rate Limit Management

> **Lesson Learned**: Deploying 12 concurrent agents hit rate limits on 8 of them. This module prevents that.

## Quick Start

```python
from agentic_brain.core import (
    get_rate_limit_manager,
    calculate_safe_agent_count,
    can_deploy_agents,
    get_deployment_recommendation
)

# Before deploying agents, check what's safe
safe_count = calculate_safe_agent_count("claude")
print(f"Safe to deploy: {safe_count} agents")

# Or get a full recommendation
rec = get_deployment_recommendation(desired_count=12, provider="claude")
if not rec["safe"]:
    print(f"Warning: {rec['message']}")
    print(f"Batch strategy: {rec['batch_strategy']}")
```

## How It Works

### 1. Provider Quotas

Each API provider has configured limits:

| Provider | Requests/min | Concurrent | Priority |
|----------|-------------|------------|----------|
| Claude   | 50          | 5          | 1 (best) |
| Groq     | 30          | 5          | 1        |
| GPT      | 60          | 10         | 2        |
| Gemini   | 60          | 10         | 3        |
| Ollama   | 1000        | 2          | 4 (slow) |

### 2. Automatic Learning

When a 429 error occurs, the system:
1. Records the event with context
2. Calculates learned rate (80% of what triggered the limit)
3. Adjusts future quotas automatically
4. Persists learned limits to `~/.agentic-brain/rate_limits.json`

### 3. Failover Strategy

```python
manager = get_rate_limit_manager()

# Get best available provider
provider = manager.get_available_provider()

# If Claude is rate limited, automatically get next best
if not manager.can_request("claude"):
    provider = manager.get_available_provider(exclude=["claude"])
```

### 4. Request Tracking

```python
async with manager.request_context("claude", tokens=1000):
    response = await make_api_call()
# Automatically tracks success/failure and adjusts state
```

## Safe Agent Deployment

### The Formula

```
safe_agents = (requests_per_minute × 0.7) / requests_per_agent_per_minute
```

With defaults:
- Claude: 50 req/min × 0.7 = 35 available
- 10-min task with 20 requests = 2 req/min per agent
- Safe count = 35 / 2 = **17 agents max**

But also capped by concurrent limit (5 for Claude), so actual safe = **5 agents**.

### Batch Deployment Strategy

For deploying many agents:

```python
desired = 12
safe = calculate_safe_agent_count("claude")  # Returns 5

# Deploy in batches
for batch in range(0, desired, safe):
    batch_size = min(safe, desired - batch)
    deploy_agents(batch_size)
    if batch + batch_size < desired:
        await asyncio.sleep(300)  # Wait 5 minutes between batches
```

## API Reference

### `RateLimitManager`

Main class for tracking and managing rate limits.

**Methods:**
- `can_request(provider, tokens=0)` - Check if request is allowed
- `get_available_provider(exclude=None)` - Get best available provider
- `record_request(provider, tokens=0)` - Record request start
- `record_complete(provider)` - Record request completion
- `record_rate_limit(provider, error_code, retry_after, context)` - Record 429 error
- `get_wait_time(provider)` - Seconds until provider available
- `get_status()` - Get all provider statuses

### `calculate_safe_agent_count(provider, task_duration_minutes, requests_per_agent)`

Calculate safe concurrent agent count.

### `get_deployment_recommendation(desired_count, provider)`

Get detailed recommendation for agent deployment.

## Best Practices

1. **Always check before deploying**: Use `can_deploy_agents()` before spawning agents
2. **Use failover**: Don't rely on single provider
3. **Batch large deployments**: Deploy in waves with cooldown
4. **Monitor status**: Check `manager.get_status()` regularly
5. **Learn from history**: The system improves over time

## Example: Safe Swarm Deployment

```python
from agentic_brain.core import get_deployment_recommendation

def deploy_swarm(tasks: list, provider: str = "claude"):
    rec = get_deployment_recommendation(len(tasks), provider)
    
    if rec["safe"]:
        # Deploy all at once
        return [deploy_agent(task) for task in tasks]
    else:
        # Batch deployment
        batch_size = rec["recommended_count"]
        results = []
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            results.extend([deploy_agent(task) for task in batch])
            
            if i + batch_size < len(tasks):
                print(f"Waiting 5 min before next batch...")
                time.sleep(300)
        
        return results
```

---

*Created after the Great Swarm Rate Limit Incident of 2026-04-05*
