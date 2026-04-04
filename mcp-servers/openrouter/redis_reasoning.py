#!/usr/bin/env python3
"""
🧠 REDIS SHARED REASONING SYSTEM
=================================

Redis-based shared context, reasoning chains, and provider health tracking
for the LLM cascade. Enables multiple LLMs to:
- Share cached responses (avoid duplicate work)
- Build on each other's reasoning (chain of thought)
- Track provider health (auto-route around failures)
- Aggregate consensus (multiple LLM verification)

Key Features:
1. Response caching (1 hour TTL) - check before calling any LLM
2. Reasoning chain storage - LLMs build on previous steps
3. Provider status tracking - real-time health monitoring
4. Pub/sub for instant updates - broadcast responses
5. Response aggregation - combine multiple LLM outputs

Redis Keys:
- llm:cache:{hash} - Cached query responses
- llm:reasoning:{session_id}:{step} - Reasoning steps
- llm:status:{provider} - Provider health (up/down, latency)
- llm:aggregate:{query_id} - Aggregated responses
- Channel: llm:responses - Real-time response pub/sub
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import redis
from redis.connection import ConnectionPool


class RedisReasoningSystem:
    """Shared reasoning and caching system backed by Redis."""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        db: int = 0
    ):
        """
        Initialize Redis connection with pooling.
        
        Args:
            host: Redis host (default from env: REDIS_HOST or localhost)
            port: Redis port (default from env: REDIS_PORT or 6379)
            password: Redis password (default from env: REDIS_PASSWORD)
            db: Redis database number (default 0)
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = int(port or os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD", None)
        self.db = db
        
        # Connection pool for efficiency
        pool_params = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "decode_responses": True,  # Auto-decode bytes to strings
            "max_connections": 20,
            "socket_timeout": 5,
            "socket_connect_timeout": 5
        }
        
        # Only add password if it's set
        if self.password:
            pool_params["password"] = self.password
        
        self.pool = ConnectionPool(**pool_params)
        
        self._redis: Optional[redis.Redis] = None
        self._pubsub = None
    
    @property
    def redis(self) -> redis.Redis:
        """Lazy connection to Redis (for startup performance)."""
        if self._redis is None:
            self._redis = redis.Redis(connection_pool=self.pool)
            # Test connection
            try:
                self._redis.ping()
            except redis.ConnectionError as e:
                raise ConnectionError(
                    f"Cannot connect to Redis at {self.host}:{self.port}. "
                    f"Is Redis running? Try: docker-compose up -d redis\n"
                    f"Error: {e}"
                )
        return self._redis
    
    def _query_hash(self, query: str) -> str:
        """Generate stable hash for query (for cache keys)."""
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    # ═══════════════════════════════════════════════════════════════
    # 1. RESPONSE CACHE (check before calling LLMs)
    # ═══════════════════════════════════════════════════════════════
    
    def cache_get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Check cache for existing response to this query.
        
        Args:
            query: The user query/prompt
        
        Returns:
            Cached response dict with keys: response, provider, timestamp
            None if not in cache
        """
        try:
            cache_key = f"llm:cache:{self._query_hash(query)}"
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            # Don't fail on cache errors - just miss cache
            print(f"⚠️  Redis cache read error: {e}")
            return None
    
    def cache_set(
        self,
        query: str,
        response: str,
        provider: str,
        ttl: int = 3600
    ) -> bool:
        """
        Cache a query response (default 1 hour TTL).
        
        Args:
            query: The user query/prompt
            response: LLM response text
            provider: Which provider/model generated this
            ttl: Time to live in seconds (default 3600 = 1 hour)
        
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            cache_key = f"llm:cache:{self._query_hash(query)}"
            data = {
                "response": response,
                "provider": provider,
                "timestamp": time.time(),
                "query": query[:200]  # Store snippet for debugging
            }
            self.redis.setex(cache_key, ttl, json.dumps(data))
            return True
        except Exception as e:
            print(f"⚠️  Redis cache write error: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # 2. REASONING CHAIN (LLMs build on each other's steps)
    # ═══════════════════════════════════════════════════════════════
    
    def share_reasoning(
        self,
        session_id: str,
        step: int,
        content: Dict[str, Any],
        ttl: int = 3600
    ) -> bool:
        """
        Share a reasoning step so other LLMs can build on it.
        
        Args:
            session_id: Unique session/query identifier
            step: Step number (0, 1, 2, ...)
            content: Dict with keys like: provider, thought, conclusion, data
            ttl: How long to keep (default 1 hour)
        
        Returns:
            True if stored successfully
        """
        try:
            key = f"llm:reasoning:{session_id}:{step}"
            data = {
                **content,
                "timestamp": time.time(),
                "step": step
            }
            self.redis.setex(key, ttl, json.dumps(data))
            return True
        except Exception as e:
            print(f"⚠️  Redis reasoning write error: {e}")
            return False
    
    def get_reasoning_chain(
        self,
        session_id: str,
        max_steps: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all reasoning steps for this session.
        
        Args:
            session_id: Session identifier
            max_steps: Maximum steps to retrieve
        
        Returns:
            List of reasoning step dicts, sorted by step number
        """
        try:
            pattern = f"llm:reasoning:{session_id}:*"
            keys = self.redis.keys(pattern)
            
            steps = []
            for key in keys:
                data = self.redis.get(key)
                if data:
                    steps.append(json.loads(data))
            
            # Sort by step number
            steps.sort(key=lambda x: x.get("step", 0))
            return steps[:max_steps]
        except Exception as e:
            print(f"⚠️  Redis reasoning read error: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════
    # 3. PROVIDER STATUS (track which LLMs are up/down)
    # ═══════════════════════════════════════════════════════════════
    
    def update_provider_status(
        self,
        provider: str,
        is_up: bool,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update provider health status.
        
        Args:
            provider: Provider name (e.g., "groq", "ollama", "claude-emulator")
            is_up: True if provider is responding
            latency_ms: Response latency in milliseconds
            error: Error message if down
        
        Returns:
            True if updated successfully
        """
        try:
            key = f"llm:status:{provider}"
            data = {
                "provider": provider,
                "is_up": is_up,
                "latency_ms": latency_ms,
                "error": error,
                "last_check": time.time(),
                "timestamp": time.time()
            }
            # Keep status for 5 minutes
            self.redis.setex(key, 300, json.dumps(data))
            return True
        except Exception as e:
            print(f"⚠️  Redis status update error: {e}")
            return False
    
    def get_provider_status(self, provider: str) -> Optional[Dict[str, Any]]:
        """Get current status for a specific provider."""
        try:
            key = f"llm:status:{provider}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"⚠️  Redis status read error: {e}")
            return None
    
    def get_healthy_providers(self) -> List[str]:
        """
        Get list of providers that are currently up.
        
        Returns:
            List of provider names that are responding
        """
        try:
            pattern = "llm:status:*"
            keys = self.redis.keys(pattern)
            
            healthy = []
            for key in keys:
                data = self.redis.get(key)
                if data:
                    status = json.loads(data)
                    if status.get("is_up"):
                        # Extract provider name from key
                        provider = key.replace("llm:status:", "")
                        healthy.append(provider)
            
            return healthy
        except Exception as e:
            print(f"⚠️  Redis health check error: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════
    # 4. PUB/SUB (instant broadcast of responses)
    # ═══════════════════════════════════════════════════════════════
    
    def publish_response(
        self,
        query_id: str,
        response: Dict[str, Any]
    ) -> bool:
        """
        Publish a response to the pub/sub channel.
        Other processes listening can react instantly.
        
        Args:
            query_id: Query identifier
            response: Response dict with provider, text, etc.
        
        Returns:
            True if published successfully
        """
        try:
            message = {
                "query_id": query_id,
                "timestamp": time.time(),
                **response
            }
            self.redis.publish("llm:responses", json.dumps(message))
            return True
        except Exception as e:
            print(f"⚠️  Redis publish error: {e}")
            return False
    
    def subscribe_responses(self, callback):
        """
        Subscribe to response channel and call callback on each message.
        
        Args:
            callback: Function that takes (message_dict) as argument
        
        Note: This is blocking! Run in a separate thread if needed.
        """
        try:
            if self._pubsub is None:
                self._pubsub = self.redis.pubsub()
                self._pubsub.subscribe("llm:responses")
            
            for message in self._pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    callback(data)
        except Exception as e:
            print(f"⚠️  Redis subscribe error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 5. RESPONSE AGGREGATION (combine multiple LLM responses)
    # ═══════════════════════════════════════════════════════════════
    
    def add_response_to_aggregate(
        self,
        query_id: str,
        provider: str,
        response: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add a response to the aggregation set for consensus/verification.
        
        Args:
            query_id: Query identifier
            provider: Which provider generated this
            response: Response text
            metadata: Optional extra data (latency, tokens, etc.)
        
        Returns:
            True if added successfully
        """
        try:
            key = f"llm:aggregate:{query_id}"
            
            # Get existing aggregate
            existing = self.redis.get(key)
            if existing:
                aggregate = json.loads(existing)
            else:
                aggregate = {
                    "query_id": query_id,
                    "created_at": time.time(),
                    "responses": []
                }
            
            # Add new response
            aggregate["responses"].append({
                "provider": provider,
                "response": response,
                "metadata": metadata or {},
                "timestamp": time.time()
            })
            
            # Store with 1 hour TTL
            self.redis.setex(key, 3600, json.dumps(aggregate))
            return True
        except Exception as e:
            print(f"⚠️  Redis aggregate add error: {e}")
            return False
    
    def get_aggregated_responses(
        self,
        query_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get all responses for this query.
        
        Args:
            query_id: Query identifier
        
        Returns:
            Dict with query_id, created_at, responses list
            None if not found
        """
        try:
            key = f"llm:aggregate:{query_id}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"⚠️  Redis aggregate read error: {e}")
            return None
    
    def aggregate_responses(
        self,
        query_id: str,
        responses: List[Dict[str, Any]],
        strategy: str = "consensus"
    ) -> Dict[str, Any]:
        """
        Combine multiple LLM responses using specified strategy.
        
        Args:
            query_id: Query identifier
            responses: List of response dicts from different providers
            strategy: How to combine:
                - "consensus": Find common elements/agreement
                - "longest": Use longest response
                - "fastest": Use first response
                - "combine": Concatenate all responses
        
        Returns:
            Dict with combined response and metadata
        """
        if not responses:
            return {
                "combined_response": "",
                "strategy": strategy,
                "count": 0,
                "providers": []
            }
        
        providers = [r.get("provider") for r in responses]
        
        if strategy == "fastest":
            # Sort by timestamp, take earliest
            sorted_responses = sorted(responses, key=lambda r: r.get("timestamp", 0))
            chosen = sorted_responses[0]
            return {
                "combined_response": chosen.get("response", ""),
                "strategy": "fastest",
                "chosen_provider": chosen.get("provider"),
                "count": len(responses),
                "providers": providers
            }
        
        elif strategy == "longest":
            # Take longest response
            longest = max(responses, key=lambda r: len(r.get("response", "")))
            return {
                "combined_response": longest.get("response", ""),
                "strategy": "longest",
                "chosen_provider": longest.get("provider"),
                "count": len(responses),
                "providers": providers
            }
        
        elif strategy == "combine":
            # Concatenate all responses
            combined = "\n\n---\n\n".join([
                f"**{r.get('provider')}:**\n{r.get('response', '')}"
                for r in responses
            ])
            return {
                "combined_response": combined,
                "strategy": "combine",
                "count": len(responses),
                "providers": providers
            }
        
        elif strategy == "consensus":
            # Find common themes (simple version - just return all for now)
            # TODO: Use NLP to find agreement/disagreement
            combined = "CONSENSUS ANALYSIS:\n\n"
            for i, r in enumerate(responses, 1):
                combined += f"{i}. {r.get('provider')}: {r.get('response', '')}\n\n"
            
            return {
                "combined_response": combined,
                "strategy": "consensus",
                "count": len(responses),
                "providers": providers,
                "note": "Simple aggregation - upgrade to NLP consensus later"
            }
        
        else:
            # Unknown strategy - return first response
            return {
                "combined_response": responses[0].get("response", ""),
                "strategy": "fallback",
                "count": len(responses),
                "providers": providers
            }
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Redis connection and return stats.
        
        Returns:
            Dict with connection status, server info, key counts
        """
        try:
            # Test ping
            start = time.time()
            self.redis.ping()
            latency_ms = (time.time() - start) * 1000
            
            # Get server info
            info = self.redis.info("server")
            
            # Count keys
            cache_count = len(self.redis.keys("llm:cache:*"))
            reasoning_count = len(self.redis.keys("llm:reasoning:*"))
            status_count = len(self.redis.keys("llm:status:*"))
            aggregate_count = len(self.redis.keys("llm:aggregate:*"))
            
            return {
                "connected": True,
                "latency_ms": round(latency_ms, 2),
                "redis_version": info.get("redis_version"),
                "uptime_days": info.get("uptime_in_days"),
                "keys": {
                    "cache": cache_count,
                    "reasoning": reasoning_count,
                    "status": status_count,
                    "aggregate": aggregate_count,
                    "total": cache_count + reasoning_count + status_count + aggregate_count
                }
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "note": "Is Redis running? Try: docker-compose up -d redis"
            }
    
    def clear_cache(self, pattern: str = "llm:*") -> int:
        """
        Clear Redis keys matching pattern.
        
        Args:
            pattern: Key pattern to match (default "llm:*" = all LLM keys)
        
        Returns:
            Number of keys deleted
        """
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            print(f"⚠️  Redis clear error: {e}")
            return 0
    
    def close(self):
        """Close Redis connections gracefully."""
        if self._pubsub:
            self._pubsub.close()
        if self._redis:
            self._redis.close()


# ═══════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE (lazy initialized)
# ═══════════════════════════════════════════════════════════════════

_redis_reasoning: Optional[RedisReasoningSystem] = None


def get_redis_reasoning() -> RedisReasoningSystem:
    """Get or create global Redis reasoning instance."""
    global _redis_reasoning
    if _redis_reasoning is None:
        _redis_reasoning = RedisReasoningSystem()
    return _redis_reasoning


# ═══════════════════════════════════════════════════════════════════
# QUICK USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Example usage
    redis = RedisReasoningSystem()
    
    print("🧠 Redis Reasoning System Test\n")
    
    # 1. Health check
    print("1. Health Check:")
    health = redis.health_check()
    print(f"   Connected: {health.get('connected')}")
    print(f"   Latency: {health.get('latency_ms')}ms")
    print(f"   Keys: {health.get('keys')}\n")
    
    # 2. Test cache
    print("2. Cache Test:")
    query = "What is Python?"
    print(f"   Query: {query}")
    
    # Check cache (should miss)
    cached = redis.cache_get(query)
    print(f"   Cache hit: {cached is not None}")
    
    # Set cache
    redis.cache_set(query, "Python is a programming language", "local-test")
    print(f"   Cached response")
    
    # Check again (should hit)
    cached = redis.cache_get(query)
    print(f"   Cache hit: {cached is not None}")
    if cached:
        print(f"   Provider: {cached['provider']}")
        print(f"   Response: {cached['response'][:50]}...\n")
    
    # 3. Test reasoning chain
    print("3. Reasoning Chain Test:")
    session_id = "test-session-123"
    redis.share_reasoning(session_id, 0, {
        "provider": "claude-emulator",
        "thought": "First, let's break down the problem..."
    })
    redis.share_reasoning(session_id, 1, {
        "provider": "groq",
        "thought": "Building on previous step, we can..."
    })
    
    chain = redis.get_reasoning_chain(session_id)
    print(f"   Steps in chain: {len(chain)}")
    for step in chain:
        print(f"   - Step {step['step']}: {step['provider']}")
    print()
    
    # 4. Test provider status
    print("4. Provider Status Test:")
    redis.update_provider_status("groq", True, 150.5)
    redis.update_provider_status("ollama", True, 50.2)
    redis.update_provider_status("claude", False, error="Rate limited")
    
    healthy = redis.get_healthy_providers()
    print(f"   Healthy providers: {healthy}\n")
    
    # 5. Test aggregation
    print("5. Aggregation Test:")
    query_id = "test-query-456"
    redis.add_response_to_aggregate(query_id, "groq", "Response from Groq")
    redis.add_response_to_aggregate(query_id, "ollama", "Response from Ollama")
    
    aggregate = redis.get_aggregated_responses(query_id)
    if aggregate:
        print(f"   Responses: {len(aggregate['responses'])}")
        
        # Test different strategies
        result = redis.aggregate_responses(query_id, aggregate['responses'], "fastest")
        print(f"   Fastest provider: {result['chosen_provider']}")
    
    print("\n✅ All tests complete!")
    
    redis.close()
