#!/usr/bin/env python3
"""
🎯 EVENT BUS LLM INTEGRATION
=============================

Integrates Redpanda event bus with OpenRouter LLM routing system.
Allows ANY external agent or process to use smart LLM routing via event bus.

Topics:
- brain.llm.request  → External agents send requests here
- brain.llm.response → Responses published here (or callback_topic)
- brain.llm.status   → Provider health updates
- brain.llm.reasoning → Shared reasoning chain updates

Features:
- Smart routing (uses existing openrouter logic)
- Redis caching (deduplication)
- Graceful fallback (Groq → Ollama → Cloud)
- Async responses via callback topics
- Reasoning chain sharing for multi-agent collaboration

Usage:
    # Start consumer (daemon)
    python3 -m mcp-servers.openrouter.event_bus_llm start
    
    # Publish a request
    from event_bus_llm import publish_llm_request
    request_id = publish_llm_request("What is 2+2?", task_type="simple")
    
    # Wait for response
    response = wait_for_response(request_id, timeout=10)
    print(response["response"])
"""

import json
import os
import sys
import time
import uuid
import threading
import subprocess
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import redis

# Add brain to path
sys.path.insert(0, os.path.expanduser("~/brain"))

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "BrainRedis2026")

# Topics
TOPIC_REQUEST = "brain.llm.request"
TOPIC_RESPONSE = "brain.llm.response"
TOPIC_STATUS = "brain.llm.status"
TOPIC_REASONING = "brain.llm.reasoning"

# Cache settings
CACHE_TTL = 3600  # 1 hour for cached responses
CACHE_PREFIX = "llm:response:"

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════

_producer: Optional[KafkaProducer] = None
_consumer: Optional[KafkaConsumer] = None
_redis_client: Optional[redis.Redis] = None
_consumer_thread: Optional[threading.Thread] = None
_running = False
_response_callbacks: Dict[str, Callable] = {}
_pending_responses: Dict[str, Dict[str, Any]] = {}


# ═══════════════════════════════════════════════════════════════
# KAFKA CONNECTION
# ═══════════════════════════════════════════════════════════════


def get_producer() -> KafkaProducer:
    """Get or create Kafka producer (lazy initialization)"""
    global _producer
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks=1,  # Wait for leader acknowledgment
                retries=3,
                max_in_flight_requests_per_connection=5,
            )
        except Exception as e:
            print(f"❌ Failed to create Kafka producer: {e}")
            raise
    return _producer


def get_consumer(topics: List[str]) -> KafkaConsumer:
    """Create Kafka consumer for specified topics"""
    try:
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id="openrouter-llm-pool",
            auto_offset_reset="latest",  # Only new messages
            enable_auto_commit=True,
            # Removed consumer_timeout_ms to keep consumer running indefinitely
        )
        return consumer
    except Exception as e:
        print(f"❌ Failed to create Kafka consumer: {e}")
        raise


def get_redis() -> redis.Redis:
    """Get or create Redis client (lazy initialization)"""
    global _redis_client
    if _redis_client is None:
        try:
            # Try with password first
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            # Test connection
            _redis_client.ping()
        except redis.exceptions.AuthenticationError:
            # Try without password (might be SSH tunnel or local instance)
            try:
                _redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                )
                _redis_client.ping()
            except Exception as e:
                print(f"⚠️  Redis unavailable (caching disabled): {e}")
                _redis_client = None
        except Exception as e:
            print(f"⚠️  Redis unavailable (caching disabled): {e}")
            _redis_client = None
    return _redis_client


# ═══════════════════════════════════════════════════════════════
# CACHE OPERATIONS
# ═══════════════════════════════════════════════════════════════


def get_cached_response(query: str, task_type: str) -> Optional[Dict[str, Any]]:
    """Check Redis cache for existing response"""
    r = get_redis()
    if not r:
        return None

    try:
        cache_key = f"{CACHE_PREFIX}{task_type}:{hash(query)}"
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"⚠️  Cache read failed: {e}")

    return None


def cache_response(query: str, task_type: str, response_data: Dict[str, Any]):
    """Store response in Redis cache"""
    r = get_redis()
    if not r:
        return

    try:
        cache_key = f"{CACHE_PREFIX}{task_type}:{hash(query)}"
        r.setex(cache_key, CACHE_TTL, json.dumps(response_data))
    except Exception as e:
        print(f"⚠️  Cache write failed: {e}")


# ═══════════════════════════════════════════════════════════════
# LLM ROUTING (imports from existing OpenRouter system)
# ═══════════════════════════════════════════════════════════════


def route_llm_request(
    query: str, task_type: str, preferred_provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Route LLM request using existing OpenRouter smart routing.

    Returns:
        {
            "response": "LLM response text",
            "provider_used": "groq",
            "latency_ms": 150,
            "tokens_used": 100,
            "cached": false,
            "error": null
        }
    """
    start_time = time.time()

    try:
        # Import routing function (lazy to avoid startup delays)
        # Use relative import since we're in the same directory
        import server as openrouter_server

        # Use smart routing
        if preferred_provider and preferred_provider != "any":
            # TODO: Add provider-specific routing
            result = openrouter_server.openrouter_smart_route(query, task=task_type)
        else:
            # Default: smart routing with cascade fallback
            result = openrouter_server.openrouter_cascade(
                query, timeout_per_provider=30
            )

        # Parse result (it returns formatted string, we need to extract)
        latency_ms = int((time.time() - start_time) * 1000)

        # Extract provider from result string (look for provider mentions)
        provider_used = "unknown"
        result_lower = result.lower()
        if "groq" in result_lower:
            provider_used = "groq"
        elif "ollama" in result_lower or "local" in result_lower:
            provider_used = "ollama"
        elif "claude" in result_lower:
            provider_used = "claude"
        elif "openai" in result_lower or "gpt" in result_lower:
            provider_used = "openai"

        return {
            "response": result,
            "provider_used": provider_used,
            "latency_ms": latency_ms,
            "tokens_used": len(result.split()),  # Rough estimate
            "cached": False,
            "error": None,
        }

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        import traceback

        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"❌ Routing error: {error_detail}")
        return {
            "response": None,
            "provider_used": None,
            "latency_ms": latency_ms,
            "tokens_used": 0,
            "cached": False,
            "error": str(e),
        }


# ═══════════════════════════════════════════════════════════════
# REQUEST HANDLING
# ═══════════════════════════════════════════════════════════════


def handle_llm_request(message: Dict[str, Any]):
    """Process an LLM request from the event bus"""
    request_id = message.get("request_id", str(uuid.uuid4()))
    query = message.get("query")
    task_type = message.get("task_type", "general")
    preferred_provider = message.get("preferred_provider", "any")
    callback_topic = message.get("callback_topic", TOPIC_RESPONSE)
    context = message.get("context", {})

    if not query:
        print(f"⚠️  Invalid request {request_id}: missing query")
        return

    print(f"📨 Processing LLM request {request_id[:8]}...")
    print(f"   Query: {query[:80]}...")
    print(f"   Task: {task_type}, Provider: {preferred_provider}")

    # Check cache first
    cached = get_cached_response(query, task_type)
    if cached:
        print(f"✅ Cache hit for {request_id[:8]}!")
        response_data = cached.copy()
        response_data["cached"] = True
        response_data["request_id"] = request_id
    else:
        # Route to appropriate provider
        response_data = route_llm_request(query, task_type, preferred_provider)
        response_data["request_id"] = request_id

        # Cache successful responses
        if response_data.get("response") and not response_data.get("error"):
            cache_response(query, task_type, response_data)

    # Add reasoning steps if available (from context)
    if "reasoning_steps" in context:
        response_data["reasoning_steps"] = context["reasoning_steps"]

    # Publish response
    publish_response(response_data, callback_topic)

    # Update status
    publish_status_update(response_data)

    print(f"✅ Request {request_id[:8]} completed in {response_data['latency_ms']}ms")


def publish_response(response_data: Dict[str, Any], topic: str = TOPIC_RESPONSE):
    """Publish LLM response to event bus"""
    try:
        producer = get_producer()
        producer.send(topic, value=response_data)
        producer.flush()

        # Store for synchronous waiters
        request_id = response_data.get("request_id")
        if request_id:
            _pending_responses[request_id] = response_data

            # Call any registered callbacks
            if request_id in _response_callbacks:
                try:
                    _response_callbacks[request_id](response_data)
                    del _response_callbacks[request_id]
                except Exception as e:
                    print(f"⚠️  Callback failed: {e}")

    except Exception as e:
        print(f"❌ Failed to publish response: {e}")


def publish_status_update(response_data: Dict[str, Any]):
    """Publish provider status update"""
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "provider": response_data.get("provider_used"),
            "latency_ms": response_data.get("latency_ms"),
            "success": response_data.get("error") is None,
            "error": response_data.get("error"),
        }

        producer = get_producer()
        producer.send(TOPIC_STATUS, value=status)
        producer.flush()
    except Exception as e:
        print(f"⚠️  Failed to publish status: {e}")


# ═══════════════════════════════════════════════════════════════
# CONSUMER SERVICE
# ═══════════════════════════════════════════════════════════════


def consumer_loop():
    """Main consumer loop - listens for LLM requests"""
    global _running, _consumer

    print(f"🎧 Starting LLM consumer on {TOPIC_REQUEST}...")

    try:
        _consumer = get_consumer([TOPIC_REQUEST])
        _running = True

        print(f"✅ LLM consumer ready!")

        # Poll with timeout to allow clean shutdown
        while _running:
            # Poll for messages with 1 second timeout
            msg_pack = _consumer.poll(timeout_ms=1000, max_records=10)

            for topic_partition, messages in msg_pack.items():
                for message in messages:
                    if not _running:
                        break

                    try:
                        handle_llm_request(message.value)
                    except Exception as e:
                        print(f"❌ Error handling request: {e}")
                        import traceback

                        traceback.print_exc()

    except KeyboardInterrupt:
        print("\n🛑 Consumer interrupted")
    except Exception as e:
        print(f"❌ Consumer error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if _consumer:
            _consumer.close()
        _running = False
        print("🛑 Consumer stopped")


def start_llm_consumer(background: bool = False) -> bool:
    """
    Start the LLM consumer service

    Args:
        background: If True, run in background thread

    Returns:
        True if started successfully
    """
    global _consumer_thread, _running

    if _running:
        print("⚠️  Consumer already running")
        return True  # Already running counts as success

    if background:
        _consumer_thread = threading.Thread(target=consumer_loop, daemon=True)
        _consumer_thread.start()

        # Wait for startup with timeout
        for _ in range(20):  # 2 second timeout
            if _running:
                return True
            time.sleep(0.1)

        return _running
    else:
        consumer_loop()
        return True


def stop_llm_consumer():
    """Stop the LLM consumer service"""
    global _running

    if not _running:
        print("⚠️  Consumer not running")
        return

    print("🛑 Stopping consumer...")
    _running = False

    if _consumer_thread:
        _consumer_thread.join(timeout=5)


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════


def publish_llm_request(
    query: str,
    task_type: str = "general",
    preferred_provider: str = "any",
    timeout_ms: int = 30000,
    callback_topic: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Publish an LLM request to the event bus

    Args:
        query: The question or prompt
        task_type: Type of task (simple, complex, coding, general)
        preferred_provider: Preferred provider (groq, ollama, claude, any)
        timeout_ms: Timeout in milliseconds
        callback_topic: Optional custom response topic
        context: Optional context data

    Returns:
        request_id: UUID of the request
    """
    request_id = str(uuid.uuid4())

    message = {
        "request_id": request_id,
        "query": query,
        "task_type": task_type,
        "preferred_provider": preferred_provider,
        "timeout_ms": timeout_ms,
        "callback_topic": callback_topic or TOPIC_RESPONSE,
        "context": context or {},
        "timestamp": datetime.now().isoformat(),
    }

    try:
        producer = get_producer()
        producer.send(TOPIC_REQUEST, value=message)
        producer.flush()
        print(f"✅ Published request {request_id[:8]}...")
        return request_id
    except Exception as e:
        print(f"❌ Failed to publish request: {e}")
        raise


def wait_for_response(request_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    Wait synchronously for a response to a request

    Args:
        request_id: The request ID to wait for
        timeout: Timeout in seconds

    Returns:
        Response data or None if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if request_id in _pending_responses:
            response = _pending_responses[request_id]
            del _pending_responses[request_id]
            return response
        time.sleep(0.1)

    print(f"⏱️  Timeout waiting for response to {request_id[:8]}")
    return None


def subscribe_responses(
    callback: Callable[[Dict[str, Any]], None], request_id: Optional[str] = None
):
    """
    Subscribe to LLM responses (async)

    Args:
        callback: Function to call when response arrives
        request_id: Optional specific request ID to listen for
    """
    if request_id:
        _response_callbacks[request_id] = callback
    else:
        # Global subscription - listen to all responses
        def response_listener():
            consumer = get_consumer([TOPIC_RESPONSE])
            for message in consumer:
                callback(message.value)

        thread = threading.Thread(target=response_listener, daemon=True)
        thread.start()


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    """CLI entry point"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m mcp-servers.openrouter.event_bus_llm [start|test]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        print("🚀 Starting LLM Event Bus Consumer...")
        start_llm_consumer(background=False)

    elif command == "test":
        print("🧪 Testing LLM Event Bus...")

        # Start consumer in background
        print("📡 Starting consumer in background...")
        success = start_llm_consumer(background=True)

        if not success:
            print("❌ Failed to start consumer!")
            sys.exit(1)

        print("✅ Consumer is running")
        time.sleep(5)  # Give it more time to start

        # Send test request
        print("\n📤 Sending test request...")
        try:
            request_id = publish_llm_request(
                query="What is 2+2? Respond with just the number.",
                task_type="simple",
                preferred_provider="any",
            )
        except Exception as e:
            print(f"❌ Failed to publish: {e}")
            stop_llm_consumer()
            sys.exit(1)

        # Wait for response
        print(f"⏳ Waiting for response to {request_id[:8]}...")
        response = wait_for_response(request_id, timeout=35)

        if response:
            print(f"\n✅ Got response!")
            print(f"   Provider: {response.get('provider_used')}")
            print(f"   Latency: {response.get('latency_ms')}ms")
            print(f"   Cached: {response.get('cached')}")
            print(f"   Response: {response.get('response')[:200]}")
        else:
            print("\n❌ No response received!")
            print("   This could mean:")
            print("   1. Consumer not processing messages")
            print("   2. Routing failed")
            print("   3. Kafka connectivity issue")

        # Cleanup
        print("\n🛑 Stopping consumer...")
        stop_llm_consumer()
        print("✅ Test complete")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
