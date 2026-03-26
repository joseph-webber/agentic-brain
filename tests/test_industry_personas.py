# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import pytest

from agentic_brain.personas.industries import INDUSTRY_PERSONAS
from agentic_brain.personas.manager import PersonaManager


def test_industry_personas_registered():
    """Verify all industry personas are registered in PersonaManager."""
    manager = PersonaManager.get_instance()

    # Force re-registration (in case singleton was initialized before industries imported)
    manager._register_defaults()

    for name, persona in INDUSTRY_PERSONAS.items():
        registered = manager.get(name)
        assert registered is not None, f"Persona '{name}' not registered"
        assert registered.name == persona.name
        assert registered.description == persona.description
        assert registered.system_prompt == persona.system_prompt
        assert registered.temperature == persona.temperature
        assert registered.safety_level == persona.safety_level


def test_defense_persona_attributes():
    """Verify specific attributes for Defense persona."""
    defense = INDUSTRY_PERSONAS["defense"]
    assert defense.temperature == 0.2
    assert defense.safety_level == "high"
    assert (
        "security" in defense.description.lower()
        or "secure" in defense.description.lower()
    )
    assert "BLUF" in defense.system_prompt or "BLUF" in str(defense.style_guidelines)


def test_healthcare_persona_attributes():
    """Verify specific attributes for Healthcare persona."""
    healthcare = INDUSTRY_PERSONAS["healthcare"]
    assert healthcare.temperature == 0.1
    assert healthcare.safety_level == "high"
    assert "HIPAA" in healthcare.system_prompt
    assert (
        "clinical" in healthcare.description.lower()
        or "medical" in healthcare.description.lower()
    )


def test_legal_persona_attributes():
    """Verify specific attributes for Legal persona."""
    legal = INDUSTRY_PERSONAS["legal"]
    assert legal.temperature == 0.3
    assert legal.safety_level == "high"
    assert "citation" in legal.description.lower() or "citation" in str(
        legal.style_guidelines
    )


def test_finance_persona_attributes():
    """Verify specific attributes for Finance persona."""
    finance = INDUSTRY_PERSONAS["finance"]
    assert finance.temperature == 0.2
    assert finance.safety_level == "high"
    assert "compliance" in finance.description.lower()


def test_education_persona_attributes():
    """Verify specific attributes for Education persona."""
    education = INDUSTRY_PERSONAS["education"]
    assert education.temperature == 0.5
    assert education.safety_level == "standard"
    assert "step-by-step" in education.description.lower()


def test_engineering_persona_attributes():
    """Verify specific attributes for Engineering persona."""
    engineering = INDUSTRY_PERSONAS["engineering"]
    assert engineering.temperature == 0.3
    assert engineering.safety_level == "standard"
    assert "technical" in engineering.description.lower()
