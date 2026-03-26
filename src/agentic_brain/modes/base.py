# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# Copyright 2026 Joseph Webber
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
Mode base classes and configuration dataclasses.

Defines the core Mode and ModeConfig structures that power the
42-mode Agentic Brain system with GraphRAG at its core.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModeCategory(Enum):
    """Categories of operational modes."""

    USER = "user"
    INDUSTRY = "industry"
    ARCHITECTURE = "architecture"
    COMPLIANCE = "compliance"
    POWER = "power"


class RagType(Enum):
    """RAG implementation types."""

    GRAPHRAG = "graphrag"  # Default: Neo4j-based knowledge graph RAG
    VECTOR = "vector"  # Pure vector similarity
    HYBRID = "hybrid"  # GraphRAG + Vector combined
    NONE = "none"  # No RAG (lightweight modes)


class SecurityLevel(Enum):
    """Security classification levels."""

    PUBLIC = "public"  # Open access
    INTERNAL = "internal"  # Internal use only
    CONFIDENTIAL = "confidential"  # Business confidential
    SECRET = "secret"  # High security clearance
    TOP_SECRET = "top_secret"  # Maximum security (military/gov)


class VoicePersonality(Enum):
    """Voice personality presets."""

    PROFESSIONAL = "professional"  # Karen, business-like
    FRIENDLY = "friendly"  # Samantha, warm
    TECHNICAL = "technical"  # Daniel, precise
    CALM = "calm"  # Moira, soothing
    ENERGETIC = "energetic"  # Alex, upbeat
    CUSTOM = "custom"  # User-defined


@dataclass
class LLMConfig:
    """LLM configuration for a mode."""

    primary_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "gpt-4o"
    local_model: str = "llama3.1:8b"
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: int = 128000
    use_local_fallback: bool = True
    streaming: bool = True
    reasoning_enabled: bool = False  # For complex analysis


@dataclass
class RAGConfig:
    """RAG/GraphRAG configuration."""

    rag_type: RagType = RagType.GRAPHRAG
    neo4j_enabled: bool = True
    vector_db: str = "chromadb"
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 10
    similarity_threshold: float = 0.7
    graph_depth: int = 3  # Relationship traversal depth
    use_knowledge_graph: bool = True
    semantic_cache: bool = True


@dataclass
class SecurityConfig:
    """Security settings for a mode."""

    level: SecurityLevel = SecurityLevel.INTERNAL
    encryption_required: bool = False
    audit_logging: bool = True
    pii_detection: bool = True
    pii_redaction: bool = False
    data_retention_days: int = 365
    allowed_domains: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    require_authentication: bool = True
    mfa_required: bool = False
    air_gapped: bool = False  # No external network access


@dataclass
class VoiceConfig:
    """Voice and audio configuration."""

    enabled: bool = True
    personality: VoicePersonality = VoicePersonality.PROFESSIONAL
    primary_voice: str = "Karen (Premium)"
    fallback_voice: str = "Samantha"
    speech_rate: int = 160
    volume: float = 1.0
    announce_mode_changes: bool = True
    speak_errors: bool = True
    persona_mode: bool = False  # Use primary multi-voice personas
    ambient_music: bool = False


@dataclass
class ComplianceConfig:
    """Compliance framework configuration."""

    frameworks: List[str] = field(default_factory=list)  # HIPAA, GDPR, SOX, etc.
    data_residency: Optional[str] = None  # e.g., "AU", "EU", "US"
    consent_tracking: bool = False
    right_to_deletion: bool = False
    breach_notification: bool = False
    audit_trail: bool = True
    retention_policy: Optional[str] = None


@dataclass
class ResourceConfig:
    """Resource allocation configuration."""

    max_agents: int = 10
    max_memory_mb: int = 4096
    max_cpu_percent: float = 80.0
    max_concurrent_requests: int = 100
    request_timeout_seconds: int = 300
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    priority: int = 5  # 1-10, higher = more priority


@dataclass
class ModeConfig:
    """Complete configuration for a mode."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    resources: ResourceConfig = field(default_factory=ResourceConfig)

    # Feature flags
    features: Dict[str, bool] = field(
        default_factory=lambda: {
            "multi_agent": True,
            "code_execution": True,
            "web_browsing": True,
            "file_access": True,
            "external_apis": True,
            "learning": True,
            "memory": True,
            "plugins": True,
        }
    )

    # Custom settings per mode
    custom: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Mode:
    """
    Represents an operational mode of the Agentic Brain.

    Each mode configures LLM, RAG, security, voice, and compliance
    settings for specific use cases and industries.
    """

    name: str
    code: str  # Short code for quick switching (e.g., "D" for Developer)
    category: ModeCategory
    description: str
    config: ModeConfig

    # Metadata
    version: str = "1.0.0"
    author: str = "Agentic Brain Team"
    icon: str = "🧠"
    color: str = "#6366F1"  # Indigo default

    # State
    _activated_at: Optional[float] = field(default=None, repr=False)
    _previous_mode: Optional[str] = field(default=None, repr=False)

    def activate(self, previous_mode: Optional[str] = None) -> None:
        """Mark this mode as activated."""
        self._activated_at = time.time()
        self._previous_mode = previous_mode

    def deactivate(self) -> float:
        """Mark this mode as deactivated, return active duration."""
        if self._activated_at:
            duration = time.time() - self._activated_at
            self._activated_at = None
            return duration
        return 0.0

    @property
    def is_active(self) -> bool:
        """Check if this mode is currently active."""
        return self._activated_at is not None

    @property
    def active_duration(self) -> float:
        """Get how long this mode has been active."""
        if self._activated_at:
            return time.time() - self._activated_at
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert mode to dictionary representation."""
        return {
            "name": self.name,
            "code": self.code,
            "category": self.category.value,
            "description": self.description,
            "version": self.version,
            "icon": self.icon,
            "color": self.color,
            "is_active": self.is_active,
            "active_duration": self.active_duration,
        }

    def __str__(self) -> str:
        status = "🟢 ACTIVE" if self.is_active else "⚪ inactive"
        return f"{self.icon} {self.name} [{self.code}] - {status}"

    def __repr__(self) -> str:
        return f"Mode(name='{self.name}', code='{self.code}', category={self.category.value})"


# Pre-built configurations for common scenarios
def create_developer_llm() -> LLMConfig:
    """LLM config optimized for developers."""
    return LLMConfig(
        primary_model="claude-sonnet-4-20250514",
        temperature=0.3,
        max_tokens=8192,
        reasoning_enabled=True,
    )


def create_enterprise_security() -> SecurityConfig:
    """Security config for enterprise environments."""
    return SecurityConfig(
        level=SecurityLevel.CONFIDENTIAL,
        encryption_required=True,
        audit_logging=True,
        pii_detection=True,
        pii_redaction=True,
        mfa_required=True,
    )


def create_hipaa_compliance() -> ComplianceConfig:
    """Compliance config for HIPAA."""
    return ComplianceConfig(
        frameworks=["HIPAA", "HITECH"],
        data_residency="US",
        consent_tracking=True,
        right_to_deletion=True,
        breach_notification=True,
        audit_trail=True,
        retention_policy="7_years",
    )


def create_gdpr_compliance() -> ComplianceConfig:
    """Compliance config for GDPR."""
    return ComplianceConfig(
        frameworks=["GDPR"],
        data_residency="EU",
        consent_tracking=True,
        right_to_deletion=True,
        breach_notification=True,
        audit_trail=True,
        retention_policy="consent_based",
    )


def create_turbo_resources() -> ResourceConfig:
    """Resource config for Turbo mode - maximum power."""
    return ResourceConfig(
        max_agents=100,
        max_memory_mb=32768,
        max_cpu_percent=100.0,
        max_concurrent_requests=1000,
        request_timeout_seconds=3600,
        priority=10,
    )
