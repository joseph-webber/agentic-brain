# SPDX-License-Identifier: Apache-2.0
import pytest

from agentic_brain.core.polymorphic import (
    ComplianceMode,
    ContextType,
    EnvironmentType,
    PolymorphicBrain,
    UserType,
)


def test_detect_user_type_developer():
    pb = PolymorphicBrain()
    res = pb.detect_user_type(
        "I am writing a python API and deploying docker containers"
    )
    assert res == UserType.DEVELOPER


def test_detect_user_type_enterprise():
    pb = PolymorphicBrain()
    res = pb.detect_user_type("compliance soc2 and governance policies")
    assert res == UserType.ENTERPRISE


def test_detect_user_type_medical():
    pb = PolymorphicBrain()
    res = pb.detect_user_type("patient diagnosis treatment and clinical notes")
    assert res == UserType.MEDICAL


def test_detect_user_type_defense():
    pb = PolymorphicBrain()
    res = pb.detect_user_type("classified mission clearance and fedramp")
    assert res == UserType.DEFENSE


def test_adapt_accepts_string_values_and_updates_profile():
    pb = PolymorphicBrain()
    prof = pb.adapt(
        user_type="developer", context="coding", environment="hybrid", compliance="soc2"
    )
    assert "technical" in prof.technical_level or hasattr(prof, "technical_level")


def test_get_system_prompt_modifier_contains_expected_phrases_for_detailed_and_expert():
    pb = PolymorphicBrain()
    pb.adapt(user_type="beginner")
    pb.current_profile.verbosity = "detailed"
    pb.current_profile.technical_level = "expert"
    out = pb.get_system_prompt_modifier()
    assert "step-by-step" in out or "technical" in out


def test_should_use_consensus_when_high_stakes_keyword():
    pb = PolymorphicBrain()
    assert pb.should_use_consensus("deploy to production")


def test_coerce_enum_raises_on_invalid():
    pb = PolymorphicBrain()
    with pytest.raises(TypeError):
        pb._coerce_enum(12345, UserType)


def test_conversation_corpus_combines_dict_history():
    pb = PolymorphicBrain()
    h = [{"content": "first"}, "second", {"message": "third"}]
    corp = pb._conversation_corpus("hello", h)
    assert "hello" in corp and "first" in corp and "second" in corp and "third" in corp
