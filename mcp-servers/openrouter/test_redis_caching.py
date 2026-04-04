#!/usr/bin/env python3
"""
Quick test to demonstrate Redis caching in action.
Shows the performance difference between cache hit and miss.
"""

import sys
import os
import time

sys.path.insert(0, os.path.expanduser('~/brain'))

from redis_reasoning import get_redis_reasoning

def main():
    print("🧠 Redis Caching Demo\n")
    
    # Get Redis instance
    redis = get_redis_reasoning()
    
    # Check health
    health = redis.health_check()
    if not health.get("connected"):
        print("❌ Redis not connected. Start with: docker-compose up -d redis")
        return
    
    print(f"✅ Redis connected ({health.get('latency_ms')}ms latency)\n")
    
    # Test query
    query = "What is Python programming language?"
    print(f"Query: '{query}'\n")
    
    # Test 1: Cache miss (first time)
    print("Test 1: First query (cache miss)")
    start = time.time()
    cached = redis.cache_get(query)
    elapsed_miss = time.time() - start
    print(f"  Result: {'HIT' if cached else 'MISS'}")
    print(f"  Time: {elapsed_miss * 1000:.2f}ms\n")
    
    # Simulate LLM response and cache it
    if not cached:
        print("Simulating LLM call and caching response...")
        response = "Python is a high-level, interpreted programming language known for its simplicity and readability."
        redis.cache_set(query, response, "test-provider")
        print(f"  Cached: {len(response)} chars\n")
    
    # Test 2: Cache hit (second time)
    print("Test 2: Same query (cache hit)")
    start = time.time()
    cached = redis.cache_get(query)
    elapsed_hit = time.time() - start
    print(f"  Result: {'HIT' if cached else 'MISS'}")
    print(f"  Time: {elapsed_hit * 1000:.2f}ms")
    
    if cached:
        print(f"  Provider: {cached['provider']}")
        print(f"  Response: {cached['response'][:60]}...\n")
    
    # Performance comparison
    if cached:
        speedup = elapsed_miss / elapsed_hit
        print(f"⚡ PERFORMANCE")
        print(f"  Cache miss: {elapsed_miss * 1000:.2f}ms")
        print(f"  Cache hit:  {elapsed_hit * 1000:.2f}ms")
        print(f"  Speedup:    {speedup:.1f}x faster!\n")
    
    # Show reasoning chain demo
    print("🧠 REASONING CHAIN DEMO\n")
    
    session_id = "demo-session"
    
    # Step 1
    redis.share_reasoning(session_id, 0, {
        "provider": "claude-emulator",
        "thought": "First, let's identify the programming paradigms Python supports."
    })
    print("Step 0: Claude shares initial analysis")
    
    # Step 2
    redis.share_reasoning(session_id, 1, {
        "provider": "groq",
        "thought": "Building on that, Python supports: OOP, functional, procedural, and imperative."
    })
    print("Step 1: Groq builds on previous step")
    
    # Get full chain
    chain = redis.get_reasoning_chain(session_id)
    print(f"\nReasoning chain has {len(chain)} steps:")
    for step in chain:
        print(f"  • Step {step['step']} ({step['provider']}): {step['thought'][:60]}...")
    
    print("\n✅ Demo complete!")
    
    redis.close()

if __name__ == "__main__":
    main()
