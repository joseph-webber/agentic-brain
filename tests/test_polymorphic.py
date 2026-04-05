# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for the polymorphic behavior system."""

from agentic_brain.core.polymorphic import (
    ComplianceMode,
    ContextType,
    EnvironmentType,
    PolymorphicBrain,
    UserType,
)


def test_detect_user_type_uses_history_context() -> None:
    """History should influence automatic persona detection."""
    brain = PolymorphicBrain()

    detected = brain.detect_user_type(
        "Can you help with this rollout?",
        history=[
            {"content": "We need SOC2 audit evidence for enterprise security."},
            "Please document our compliance controls.",
        ],
    )

    assert detected == UserType.ENTERPRISE


def test_adapt_applies_context_environment_and_compliance() -> None:
    """Resolved profile should reflect combined modifiers."""
    brain = PolymorphicBrain()

    profile = brain.adapt(
        user_type=UserType.DEVELOPER,
        context=ContextType.CLASSIFIED,
        environment=EnvironmentType.AIRLOCKED,
        compliance=ComplianceMode.FEDRAMP,
    )

    assert brain.environment == EnvironmentType.AIRLOCKED
    assert profile.prefer_local is True
    assert profile.require_consensus is True
    assert profile.citation_required is True
    assert profile.allowed_providers == ["local"]
    assert profile.encryption == "military"
    assert profile.data_retention == "none"
    assert profile.max_latency_ms <= 3000


def test_profile_presets_are_not_mutated_across_instances() -> None:
    """Context modifiers should not leak back into preset profiles."""
    first = PolymorphicBrain()
    first.adapt(user_type=UserType.DEVELOPER, context=ContextType.CLASSIFIED)

    second = PolymorphicBrain()
    second_profile = second.adapt(user_type=UserType.DEVELOPER)

    assert second_profile.prefer_local is False
    assert second_profile.require_consensus is False
    assert second_profile.allowed_providers == [
        "local",
        "openrouter",
        "anthropic",
        "openai",
    ]


def test_system_prompt_modifier_reflects_active_profile() -> None:
    """Prompt modifier should expose the safety posture clearly."""
    brain = PolymorphicBrain()
    brain.adapt(
        user_type=UserType.MEDICAL,
        context=ContextType.LEGAL,
        environment=EnvironmentType.HYBRID,
        compliance=ComplianceMode.HIPAA,
    )

    modifier = brain.get_system_prompt_modifier()

    assert "Always cite sources." in modifier
    assert "verify with multiple sources" in modifier
    assert "Prefer local or offline-capable tools" in modifier
    assert "professional tone" in modifier or "formal language" in modifier


def test_should_use_consensus_for_high_stakes_queries() -> None:
    """High-stakes actions should trigger consensus even for relaxed profiles."""
    brain = PolymorphicBrain()
    brain.adapt(user_type=UserType.BEGINNER, context=ContextType.CASUAL)

    assert (
        brain.should_use_consensus("Should I deploy this to production today?") is True
    )
    assert brain.should_use_consensus("Tell me a fun fact about Adelaide.") is False
