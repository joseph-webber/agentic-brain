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
Agentic Brain — The Universal AI Platform
==========================================

**Install. Run. Create.** From Grandmother to Enterprise.

A production-ready framework for building AI agents with:
- GraphRAG with Neo4j knowledge graphs
- 155+ RAG loaders (LLMs, vector DBs, enterprise, e-commerce)
- GPU-accelerated embeddings (Apple Silicon MLX, CUDA)
- Multi-tenant SaaS ready with audit logging
- Built-in legal disclaimers (medical, financial, NDIS)

Zero to AI in 60 seconds:
    pip install agentic-brain
    agentic chat

Copyright (C) 2024-2026 Joseph Webber
License: Apache-2.0

Import weight guide
-------------------
The imports below are split by cost.  If you only need a subset of the public
API you can import from the sub-packages directly to avoid loading unneeded
dependencies.

``agentic_brain.exceptions`` — lightweight (pure Python, no dependencies)
``agentic_brain.legal``      — lightweight (string constants only)
``agentic_brain.governance`` — lightweight (dataclasses + stdlib)
``agentic_brain.memory``     — medium   (imports ``neo4j`` driver on first use;
                                          falls back to in-memory automatically)
``agentic_brain.router``     — medium   (imports all provider config dataclasses;
                                          actual HTTP clients are lazy-loaded
                                          inside each chat/stream function)
``agentic_brain.audio``      — heavy    (spawns subprocess / uses macOS say;
                                          import cost is ~20 ms on Apple Silicon)
``agentic_brain.agent``      — heavy    (pulls in router + memory + audio)

Example:
    >>> from agentic_brain import Agent, Neo4jMemory
    >>> memory = Neo4jMemory(uri="bolt://localhost:7687")
    >>> agent = Agent(name="assistant", memory=memory)
    >>> response = agent.chat("Hello!")
"""

__version__ = "2.12.0"
__author__ = "Joseph Webber"
__email__ = "joseph.webber@me.com"
__license__ = "Apache-2.0"
__tagline__ = "The Universal AI Platform — Install. Run. Create."
__description__ = "From Grandmother to Enterprise. Production-ready AI agents with GraphRAG, 155+ RAG loaders, and enterprise-grade security."

__all__ = [
    # Core
    "Agent",
    "Audio",
    "AudioConfig",
    "Platform",
    "Voice",
    "VoiceInfo",
    "VoiceQueue",
    "VoiceRegistry",
    "MACOS_VOICES",
    "get_audio",
    "get_registry",
    "get_queue",
    "speak",
    "sound",
    "announce",
    "list_voices",
    "test_voice",
    "queue_speak",
    "play_queue",
    "Neo4jMemory",
    "DataScope",
    "LLMRouter",
    # Commerce
    "CashOnDeliveryGateway",
    "WooCommerceAgent",
    "WooCommerceChatbot",
    "CommerceContext",
    "CommerceIntent",
    "CommerceIntentDetector",
    "CommerceUserType",
    "WPAuth",
    "WPMedia",
    "WPPage",
    "WPPost",
    "WPRenderedText",
    "WordPressClient",
    "FraudRejectedError",
    "GatewayType",
    "PayPalGateway",
    "PaymentError",
    "PaymentGateway",
    "PaymentIntent",
    "PaymentMethodReference",
    "PaymentOperationNotSupported",
    "PaymentProcessor",
    "PaymentRequest",
    "PaymentResult",
    "PaymentSecurityError",
    "PaymentStatus",
    "RefundRequest",
    "RefundResult",
    "SquareGateway",
    "StripeGateway",
    "SubscriptionRequest",
    "TransactionRecord",
    "WebhookEvent",
    "WooAddress",
    "WooBaseModel",
    "WooCategory",
    "WooCoupon",
    "WooCustomer",
    "WooOrder",
    "WooOrderItem",
    "WooOrderTotals",
    "WooProduct",
    "WooProductImage",
    "WooTag",
    # Legal/Disclaimers
    "DisclaimerType",
    "MEDICAL_DISCLAIMER",
    "FINANCIAL_DISCLAIMER",
    "LEGAL_DISCLAIMER",
    "NDIS_DISCLAIMER",
    "DEFENCE_DISCLAIMER",
    "AI_DISCLAIMER",
    "get_disclaimer",
    "get_acl_notice",
    # Governance
    "ModelCard",
    "AuditEvent",
    "AuditLog",
    "AuditOutcome",
    "AuditCategory",
    # Exceptions
    "AgenticBrainError",
    "Neo4jConnectionError",
    "LLMProviderError",
    "MemoryError",
    "TransportError",
    "ConfigurationError",
    "RateLimitError",
    "SessionError",
    "ValidationError",
    "TimeoutError",
    "APIError",
    "ModelNotFoundError",
    # Metadata
    "__version__",
    "__author__",
    "__tagline__",
    "__description__",
]

_LAZY_EXPORTS = {
    # Core
    "Agent": ("agentic_brain.agent", "Agent"),
    "Audio": ("agentic_brain.audio", "Audio"),
    "AudioConfig": ("agentic_brain.audio", "AudioConfig"),
    "Platform": ("agentic_brain.audio", "Platform"),
    "Voice": ("agentic_brain.audio", "Voice"),
    "VoiceInfo": ("agentic_brain.audio", "VoiceInfo"),
    "VoiceQueue": ("agentic_brain.audio", "VoiceQueue"),
    "VoiceRegistry": ("agentic_brain.audio", "VoiceRegistry"),
    "MACOS_VOICES": ("agentic_brain.audio", "MACOS_VOICES"),
    "get_audio": ("agentic_brain.audio", "get_audio"),
    "get_registry": ("agentic_brain.audio", "get_registry"),
    "get_queue": ("agentic_brain.audio", "get_queue"),
    "speak": ("agentic_brain.audio", "speak"),
    "sound": ("agentic_brain.audio", "sound"),
    "announce": ("agentic_brain.audio", "announce"),
    "list_voices": ("agentic_brain.audio", "list_voices"),
    "test_voice": ("agentic_brain.audio", "test_voice"),
    "queue_speak": ("agentic_brain.audio", "queue_speak"),
    "play_queue": ("agentic_brain.audio", "play_queue"),
    "Neo4jMemory": ("agentic_brain.memory", "Neo4jMemory"),
    "DataScope": ("agentic_brain.memory", "DataScope"),
    "LLMRouter": ("agentic_brain.router", "LLMRouter"),
    # Commerce
    "FraudRejectedError": ("agentic_brain.commerce", "FraudRejectedError"),
    "CashOnDeliveryGateway": ("agentic_brain.commerce", "CashOnDeliveryGateway"),
    "GatewayType": ("agentic_brain.commerce", "GatewayType"),
    "PaymentError": ("agentic_brain.commerce", "PaymentError"),
    "PaymentGateway": ("agentic_brain.commerce", "PaymentGateway"),
    "PaymentIntent": ("agentic_brain.commerce", "PaymentIntent"),
    "PaymentMethodReference": (
        "agentic_brain.commerce",
        "PaymentMethodReference",
    ),
    "PaymentOperationNotSupported": (
        "agentic_brain.commerce",
        "PaymentOperationNotSupported",
    ),
    "PaymentProcessor": ("agentic_brain.commerce", "PaymentProcessor"),
    "PaymentRequest": ("agentic_brain.commerce", "PaymentRequest"),
    "PaymentResult": ("agentic_brain.commerce", "PaymentResult"),
    "PaymentSecurityError": ("agentic_brain.commerce", "PaymentSecurityError"),
    "PaymentStatus": ("agentic_brain.commerce", "PaymentStatus"),
    "PayPalGateway": ("agentic_brain.commerce", "PayPalGateway"),
    "RefundRequest": ("agentic_brain.commerce", "RefundRequest"),
    "RefundResult": ("agentic_brain.commerce", "RefundResult"),
    "SquareGateway": ("agentic_brain.commerce", "SquareGateway"),
    "StripeGateway": ("agentic_brain.commerce", "StripeGateway"),
    "SubscriptionRequest": ("agentic_brain.commerce", "SubscriptionRequest"),
    "TransactionRecord": ("agentic_brain.commerce", "TransactionRecord"),
    "WebhookEvent": ("agentic_brain.commerce", "WebhookEvent"),
    "WooAddress": ("agentic_brain.commerce", "WooAddress"),
    "WooBaseModel": ("agentic_brain.commerce", "WooBaseModel"),
    "WooCategory": ("agentic_brain.commerce", "WooCategory"),
    "WooCommerceAgent": ("agentic_brain.commerce", "WooCommerceAgent"),
    "WooCommerceChatbot": ("agentic_brain.commerce", "WooCommerceChatbot"),
    "CommerceContext": ("agentic_brain.commerce", "CommerceContext"),
    "CommerceIntent": ("agentic_brain.commerce", "CommerceIntent"),
    "CommerceIntentDetector": ("agentic_brain.commerce", "CommerceIntentDetector"),
    "CommerceUserType": ("agentic_brain.commerce", "CommerceUserType"),
    "WooCoupon": ("agentic_brain.commerce", "WooCoupon"),
    "WooCustomer": ("agentic_brain.commerce", "WooCustomer"),
    "WooOrder": ("agentic_brain.commerce", "WooOrder"),
    "WooOrderItem": ("agentic_brain.commerce", "WooOrderItem"),
    "WooOrderTotals": ("agentic_brain.commerce", "WooOrderTotals"),
    "WooProduct": ("agentic_brain.commerce", "WooProduct"),
    "WooProductImage": ("agentic_brain.commerce", "WooProductImage"),
    "WooTag": ("agentic_brain.commerce", "WooTag"),
    "CommerceHub": ("agentic_brain.commerce", "CommerceHub"),
    "CommerceConfig": ("agentic_brain.commerce", "CommerceConfig"),
    "WordPressClient": ("agentic_brain.commerce", "WordPressClient"),
    "WPAuth": ("agentic_brain.commerce", "WPAuth"),
    "WPMedia": ("agentic_brain.commerce", "WPMedia"),
    "WPPage": ("agentic_brain.commerce", "WPPage"),
    "WPPost": ("agentic_brain.commerce", "WPPost"),
    "WPRenderedText": ("agentic_brain.commerce", "WPRenderedText"),
    # Legal/Disclaimers
    "DisclaimerType": ("agentic_brain.legal", "DisclaimerType"),
    "MEDICAL_DISCLAIMER": ("agentic_brain.legal", "MEDICAL_DISCLAIMER"),
    "FINANCIAL_DISCLAIMER": ("agentic_brain.legal", "FINANCIAL_DISCLAIMER"),
    "LEGAL_DISCLAIMER": ("agentic_brain.legal", "LEGAL_DISCLAIMER"),
    "NDIS_DISCLAIMER": ("agentic_brain.legal", "NDIS_DISCLAIMER"),
    "DEFENCE_DISCLAIMER": ("agentic_brain.legal", "DEFENCE_DISCLAIMER"),
    "AI_DISCLAIMER": ("agentic_brain.legal", "AI_DISCLAIMER"),
    "get_disclaimer": ("agentic_brain.legal", "get_disclaimer"),
    "get_acl_notice": ("agentic_brain.legal", "get_acl_notice"),
    # Governance
    "ModelCard": ("agentic_brain.governance", "ModelCard"),
    "AuditEvent": ("agentic_brain.governance", "AuditEvent"),
    "AuditLog": ("agentic_brain.governance", "AuditLog"),
    "AuditOutcome": ("agentic_brain.governance", "AuditOutcome"),
    "AuditCategory": ("agentic_brain.governance", "AuditCategory"),
    # Exceptions
    "AgenticBrainError": ("agentic_brain.exceptions", "AgenticBrainError"),
    "Neo4jConnectionError": ("agentic_brain.exceptions", "Neo4jConnectionError"),
    "LLMProviderError": ("agentic_brain.exceptions", "LLMProviderError"),
    "MemoryError": ("agentic_brain.exceptions", "MemoryError"),
    "TransportError": ("agentic_brain.exceptions", "TransportError"),
    "ConfigurationError": ("agentic_brain.exceptions", "ConfigurationError"),
    "RateLimitError": ("agentic_brain.exceptions", "RateLimitError"),
    "SessionError": ("agentic_brain.exceptions", "SessionError"),
    "ValidationError": ("agentic_brain.exceptions", "ValidationError"),
    "TimeoutError": ("agentic_brain.exceptions", "TimeoutError"),
    "APIError": ("agentic_brain.exceptions", "APIError"),
    "ModelNotFoundError": ("agentic_brain.exceptions", "ModelNotFoundError"),
}


def __getattr__(name: str):
    """Lazy-load public exports so lightweight imports stay fast."""
    if name in _LAZY_EXPORTS:
        import importlib

        module_name, attribute_name = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attribute_name)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Expose lazy exports to dir() and star imports."""
    return sorted(set(globals()) | set(__all__))
