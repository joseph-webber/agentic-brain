# Security Assessment: WebSocket and Redis

**Date:** 2024-05-23
**Assessor:** Gemini Pen Tester
**Target:** agentic-brain (WebSocket API & Redis Cache)

## Executive Summary

The `agentic-brain` application exposes critical security vulnerabilities in its real-time communication infrastructure. Both the WebSocket API and the Redis data store are accessible without authentication, allowing unauthorized access to chat sessions, inter-bot communication, and potentially sensitive data.

## Findings

### 1. WebSocket Unauthenticated Access
- **Severity:** High
- **Component:** `agentic_brain.api.websocket`
- **Endpoint:** `ws://localhost:8765/ws/chat`
- **Finding:** The WebSocket endpoint does not implement any authentication mechanism. Any client can connect, establish a session, and interact with the LLM backend without credentials.
- **Proof of Concept:**
  ```python
  import asyncio
  import websockets

  async def test_ws():
      async with websockets.connect('ws://localhost:8765/ws/chat') as ws:
          await ws.send('{"message": "Hello without auth"}')
          response = await ws.recv()
          print(response)
  
  asyncio.run(test_ws())
  ```
- **Recommendation:** Implement JWT verification in the WebSocket connection handshake.

### 2. Redis Unauthenticated Access & Injection
- **Severity:** Critical
- **Component:** `agentic_brain.router.redis_cache`
- **Port:** 6379 (Default)
- **Finding:** The Redis instance is configured without a password (`requirepass` is empty). The `RedisRouterCache` client connects without credentials.
- **Impact:**
  - Full read/write access to all keys.
  - Ability to inject malicious tasks into the LLM router.
  - Ability to monitor inter-bot communication.
- **Proof of Concept:**
  ```python
  from agentic_brain.router.redis_cache import RedisRouterCache
  cache = RedisRouterCache()
  # Dump all keys
  print(cache.client.keys("*"))
  ```
- **Recommendation:** 
  - Enable Redis password authentication (`requirepass`).
  - Configure `RedisRouterCache` to use `REDIS_PASSWORD` env var.
  - Use ACLs to restrict key access.

### 3. Event Bus (Redpanda) Insecure Configuration
- **Severity:** Medium
- **Component:** `agentic_brain.durability.event_store`
- **Finding:** The Kafka/Redpanda client configuration (`EventStoreConfig`) lacks SASL/TLS settings, indicating plain-text, unauthenticated communication.
- **Recommendation:** Enable SASL SCRAM authentication and TLS encryption for the Redpanda cluster.

## Remediation Plan

1. **Secure Redis:**
   - Update `docker-compose.yml` to set `REDIS_PASSWORD`.
   - Update `RedisRouterCache` to read password from environment.

2. **Secure WebSocket:**
   - Add `token` query parameter to WebSocket URL.
   - Verify JWT in `register_websocket_routes` before accepting connection.

3. **Secure Event Bus:**
   - Configure Redpanda for SASL authentication.
   - Update `EventStore` to support secure connections.
