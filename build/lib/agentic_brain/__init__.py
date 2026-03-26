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
- 54+ integrations (LLMs, vector DBs, enterprise auth)
- GPU-accelerated embeddings (Apple Silicon MLX, CUDA)
- Multi-tenant SaaS ready with audit logging
- Built-in legal disclaimers (medical, financial, NDIS)

Zero to AI in 60 seconds:
    pip install agentic-brain
    agentic chat

Copyright (C) 2024-2026 Joseph Webber
License: Apache-2.0

Example:
    >>> from agentic_brain import Agent, Neo4jMemory
    >>> memory = Neo4jMemory(uri="bolt://localhost:7687")
    >>> agent = Agent(name="assistant", memory=memory)
    >>> response = agent.chat("Hello!")
"""

__version__ = "2.11.0"
__author__ = "Joseph Webber"
__email__ = "joseph.webber@me.com"
__license__ = "Apache-2.0"
__tagline__ = "The Universal AI Platform — Install. Run. Create."
__description__ = "From Grandmother to Enterprise. Production-ready AI agents with GraphRAG, 54+ integrations, and enterprise-grade security."

from agentic_brain.agent import Agent
from agentic_brain.audio import (
    Audio,
    AudioConfig,
    Platform,
    Voice,
    VoiceInfo,
    VoiceQueue,
    VoiceRegistry,
    MACOS_VOICES,
    announce,
    get_audio,
    get_queue,
    get_registry,
    list_voices,
    play_queue,
    queue_speak,
    sound,
    speak,
    test_voice,
)
from agentic_brain.exceptions import (
    AgenticBrainError,
    APIError,
    ConfigurationError,
    LLMProviderError,
    MemoryError,
    ModelNotFoundError,
    Neo4jConnectionError,
    RateLimitError,
    SessionError,
    TimeoutError,
    TransportError,
    ValidationError,
)
from agentic_brain.governance import (
    AuditCategory,
    AuditEvent,
    AuditLog,
    AuditOutcome,
    ModelCard,
)
from agentic_brain.legal import (
    AI_DISCLAIMER,
    DEFENCE_DISCLAIMER,
    FINANCIAL_DISCLAIMER,
    LEGAL_DISCLAIMER,
    MEDICAL_DISCLAIMER,
    NDIS_DISCLAIMER,
    DisclaimerType,
    get_acl_notice,
    get_disclaimer,
)
from agentic_brain.memory import DataScope, Neo4jMemory
from agentic_brain.router import LLMRouter

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
