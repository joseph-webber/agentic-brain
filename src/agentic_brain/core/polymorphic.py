# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""Polymorphic behavior profiles for adapting the brain to each context."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class UserType(StrEnum):
    """Supported user personas."""

    BEGINNER = "beginner"
    DEVELOPER = "developer"
    ENTERPRISE = "enterprise"
    DEFENSE = "defense"
    MEDICAL = "medical"


class ContextType(StrEnum):
    """Conversation contexts that influence behavior."""

    CASUAL = "casual"
    WORK = "work"
    CODING = "coding"
    MEDICAL = "medical"
    LEGAL = "legal"
    CLASSIFIED = "classified"


class EnvironmentType(StrEnum):
    """Deployment environments with different trust boundaries."""

    CLOUD = "cloud"
    HYBRID = "hybrid"
    AIRLOCKED = "airlocked"


class ComplianceMode(StrEnum):
    """Compliance postures that tighten behavior requirements."""

    NONE = "none"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    FEDRAMP = "fedramp"
    DEFENSE = "defense"


@dataclass(slots=True)
class BehaviorProfile:
    """Defines how the brain behaves in a given context."""

    # Response style
    verbosity: str = "normal"  # brief, normal, detailed
    technical_level: str = "auto"  # simple, auto, technical, expert
    tone: str = "helpful"  # casual, helpful, professional, formal

    # Safety settings
    require_consensus: bool = False
    hallucination_threshold: float = 0.1  # Max allowed uncertainty
    citation_required: bool = False

    # Compliance
    audit_logging: bool = False
    data_retention: str = "default"
    encryption: str = "standard"

    # LLM routing
    prefer_local: bool = False
    allowed_providers: list[str] = field(default_factory=list)
    max_latency_ms: int = 10000

    def copy(self) -> BehaviorProfile:
        """Return an isolated copy safe to mutate."""
        return deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the profile for prompts, logs, or routing."""
        return asdict(self)


class PolymorphicBrain:
    """Adapt brain behavior based on persona, context, environment, and policy."""

    PROFILE_PRESETS: dict[UserType, BehaviorProfile] = {
        UserType.BEGINNER: BehaviorProfile(
            verbosity="detailed",
            technical_level="simple",
            tone="helpful",
            max_latency_ms=12000,
        ),
        UserType.DEVELOPER: BehaviorProfile(
            verbosity="normal",
            technical_level="technical",
            tone="casual",
            allowed_providers=["local", "openrouter", "anthropic", "openai"],
            max_latency_ms=8000,
        ),
        UserType.ENTERPRISE: BehaviorProfile(
            verbosity="normal",
            technical_level="auto",
            tone="professional",
            require_consensus=True,
            audit_logging=True,
            hallucination_threshold=0.05,
            allowed_providers=["local", "anthropic", "openai", "azure-openai"],
            max_latency_ms=6000,
        ),
        UserType.DEFENSE: BehaviorProfile(
            verbosity="brief",
            technical_level="expert",
            tone="formal",
            require_consensus=True,
            audit_logging=True,
            citation_required=True,
            hallucination_threshold=0.01,
            prefer_local=True,
            encryption="military",
            data_retention="none",
            allowed_providers=["local"],
            max_latency_ms=2500,
        ),
        UserType.MEDICAL: BehaviorProfile(
            verbosity="detailed",
            technical_level="auto",
            tone="professional",
            require_consensus=True,
            audit_logging=True,
            citation_required=True,
            hallucination_threshold=0.02,
            encryption="hipaa",
            allowed_providers=["local", "anthropic", "azure-openai"],
            max_latency_ms=4000,
        ),
    }

    _TECHNICAL_INDICATORS = (
        "api",
        "function",
        "class",
        "deploy",
        "kubernetes",
        "docker",
        "python",
        "typescript",
        "cli",
    )
    _ENTERPRISE_INDICATORS = (
        "compliance",
        "audit",
        "soc2",
        "enterprise",
        "security",
        "governance",
        "policy",
        "risk",
    )
    _DEFENSE_INDICATORS = (
        "classified",
        "clearance",
        "airlocked",
        "fedramp",
        "defense",
        "mission",
    )
    _MEDICAL_INDICATORS = (
        "patient",
        "hipaa",
        "diagnosis",
        "medical",
        "clinical",
        "treatment",
    )
    _HIGH_STAKES_KEYWORDS = (
        "delete",
        "deploy",
        "production",
        "money",
        "payment",
        "legal",
        "health",
        "medical",
        "patient",
        "classified",
    )

    def __init__(self) -> None:
        self.user_type: UserType = UserType.BEGINNER
        self.context: ContextType = ContextType.CASUAL
        self.environment: EnvironmentType = EnvironmentType.CLOUD
        self.compliance: ComplianceMode = ComplianceMode.NONE
        self.current_profile: BehaviorProfile = self._build_profile()

    def detect_user_type(
        self, message: str, history: list[str | dict[str, Any]] | None = None
    ) -> UserType:
        """Auto-detect user type from the current message plus prior history."""
        corpus = self._conversation_corpus(message, history)

        if self._contains_any(corpus, self._DEFENSE_INDICATORS):
            return UserType.DEFENSE
        if self._contains_any(corpus, self._MEDICAL_INDICATORS):
            return UserType.MEDICAL
        if self._contains_any(corpus, self._ENTERPRISE_INDICATORS):
            return UserType.ENTERPRISE
        if self._contains_any(corpus, self._TECHNICAL_INDICATORS):
            return UserType.DEVELOPER
        return UserType.BEGINNER

    def adapt(
        self,
        user_type: UserType | str | None = None,
        context: ContextType | str | None = None,
        environment: EnvironmentType | str | None = None,
        compliance: ComplianceMode | str | None = None,
    ) -> BehaviorProfile:
        """Adapt behavior to a new operating posture and return the active profile."""
        if user_type is not None:
            self.user_type = self._coerce_enum(user_type, UserType)
        if context is not None:
            self.context = self._coerce_enum(context, ContextType)
        if environment is not None:
            self.environment = self._coerce_enum(environment, EnvironmentType)
        if compliance is not None:
            self.compliance = self._coerce_enum(compliance, ComplianceMode)

        self.current_profile = self._build_profile()
        return self.current_profile

    def get_system_prompt_modifier(self) -> str:
        """Get system prompt additions that reflect the active profile."""
        modifiers: list[str] = []
        profile = self.current_profile

        if profile.verbosity == "brief":
            modifiers.append("Keep responses concise and action-oriented.")
        elif profile.verbosity == "detailed":
            modifiers.append("Provide step-by-step detail when it improves clarity.")

        if profile.technical_level == "simple":
            modifiers.append("Explain concepts simply and avoid unnecessary jargon.")
        elif profile.technical_level == "technical":
            modifiers.append(
                "Use precise technical language and implementation detail."
            )
        elif profile.technical_level == "expert":
            modifiers.append("Be precise and technical. Assume expert knowledge.")

        tone_map = {
            "casual": "Use a friendly, direct tone.",
            "helpful": "Be warm, supportive, and practical.",
            "professional": "Use a professional tone suitable for workplace decisions.",
            "formal": "Use formal language and avoid speculation.",
        }
        if profile.tone in tone_map:
            modifiers.append(tone_map[profile.tone])

        if profile.citation_required:
            modifiers.append("Always cite sources. Never make unsourced claims.")
        if profile.require_consensus:
            modifiers.append("For important claims, verify with multiple sources.")
        if profile.audit_logging:
            modifiers.append(
                "State assumptions and decisions clearly for auditability."
            )
        if profile.prefer_local:
            modifiers.append(
                "Prefer local or offline-capable tools and models when possible."
            )

        return " ".join(modifiers)

    def should_use_consensus(self, query: str) -> bool:
        """Determine whether the current query needs multi-source validation."""
        if self.current_profile.require_consensus:
            return True

        return self._contains_any(query.lower(), self._HIGH_STAKES_KEYWORDS)

    def get_active_configuration(self) -> dict[str, Any]:
        """Return the resolved posture and profile as a serializable snapshot."""
        return {
            "user_type": self.user_type.value,
            "context": self.context.value,
            "environment": self.environment.value,
            "compliance": self.compliance.value,
            "profile": self.current_profile.to_dict(),
        }

    def _build_profile(self) -> BehaviorProfile:
        profile = self.PROFILE_PRESETS[self.user_type].copy()
        self._apply_context_modifiers(profile, self.context)
        self._apply_environment_modifiers(profile, self.environment)
        self._apply_compliance_modifiers(profile, self.compliance)
        return profile

    def _apply_context_modifiers(
        self, profile: BehaviorProfile, context: ContextType
    ) -> None:
        """Apply context-specific modifications."""
        if context == ContextType.WORK:
            profile.tone = "professional"
        elif context == ContextType.CODING:
            profile.technical_level = "technical"
            profile.tone = "casual"
        elif context == ContextType.MEDICAL:
            profile.tone = "professional"
            profile.citation_required = True
            profile.require_consensus = True
            profile.hallucination_threshold = min(profile.hallucination_threshold, 0.02)
        elif context == ContextType.LEGAL:
            profile.tone = "formal"
            profile.citation_required = True
            profile.require_consensus = True
            profile.hallucination_threshold = min(profile.hallucination_threshold, 0.02)
        elif context == ContextType.CLASSIFIED:
            profile.prefer_local = True
            profile.require_consensus = True
            profile.citation_required = True
            profile.data_retention = "none"
            profile.allowed_providers = ["local"]

    def _apply_environment_modifiers(
        self, profile: BehaviorProfile, environment: EnvironmentType
    ) -> None:
        """Apply deployment-environment requirements."""
        if environment == EnvironmentType.CLOUD:
            return

        if environment == EnvironmentType.HYBRID:
            profile.prefer_local = True
            if not profile.allowed_providers:
                profile.allowed_providers = ["local", "anthropic", "openai"]
            elif "local" not in profile.allowed_providers:
                profile.allowed_providers.insert(0, "local")
        elif environment == EnvironmentType.AIRLOCKED:
            profile.prefer_local = True
            profile.allowed_providers = ["local"]
            profile.max_latency_ms = min(profile.max_latency_ms, 3000)
            profile.data_retention = "none"

    def _apply_compliance_modifiers(
        self, profile: BehaviorProfile, compliance: ComplianceMode
    ) -> None:
        """Apply compliance requirements."""
        if compliance == ComplianceMode.NONE:
            return

        if compliance in {ComplianceMode.SOC2, ComplianceMode.ISO27001}:
            profile.audit_logging = True
            profile.hallucination_threshold = min(profile.hallucination_threshold, 0.05)
        if compliance == ComplianceMode.HIPAA:
            profile.encryption = "hipaa"
            profile.audit_logging = True
            profile.citation_required = True
            profile.hallucination_threshold = min(profile.hallucination_threshold, 0.02)
        if compliance in {ComplianceMode.FEDRAMP, ComplianceMode.DEFENSE}:
            profile.prefer_local = True
            profile.require_consensus = True
            profile.citation_required = True
            profile.encryption = "military"
            profile.data_retention = "none"
            profile.allowed_providers = ["local"]
            profile.max_latency_ms = min(profile.max_latency_ms, 3000)

    @staticmethod
    def _coerce_enum(value: Any, enum_type: type[StrEnum]) -> StrEnum:
        if isinstance(value, enum_type):
            return value
        if isinstance(value, str):
            return enum_type(value.lower())
        raise TypeError(
            f"Expected {enum_type.__name__} or str, got {type(value).__name__}"
        )

    @staticmethod
    def _contains_any(text: str, indicators: tuple[str, ...]) -> bool:
        return any(indicator in text for indicator in indicators)

    @staticmethod
    def _conversation_corpus(
        message: str, history: list[str | dict[str, Any]] | None
    ) -> str:
        chunks = [message]
        for item in history or []:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                for key in ("content", "message", "text"):
                    value = item.get(key)
                    if isinstance(value, str):
                        chunks.append(value)
                        break
        return " ".join(chunks).lower()


__all__ = [
    "BehaviorProfile",
    "ComplianceMode",
    "ContextType",
    "EnvironmentType",
    "PolymorphicBrain",
    "UserType",
]
