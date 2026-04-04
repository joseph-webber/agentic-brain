# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""Agentic Definition Language (ADL).

High-level configuration DSL for Agentic Brain, inspired by JHipster JDL.

This package provides:
- A small, friendly DSL for describing an AI brain (LLMs, RAG, voice, API, security)
- A parser that turns `.adl` files into structured Python objects
- A generator that maps ADL configs to concrete runtime configuration
- Persona templates that provide complete configurations for different use cases

Public entry points:
- :func:`parse_adl` / :func:`parse_adl_file` / :func:`parse_adl_string`
- :func:`generate_from_adl` / :func:`generate_config_from_adl`
- Persona templates via :mod:`.personas`
"""

from .generator import ADLGenerationResult, generate_from_adl
from .parser import (
    ADLConfig,
    DtoDef,
    EntityDef,
    EnumDef,
    FieldDef,
    PaginationDef,
    RelationshipDef,
    RelationshipEnd,
    ServiceDef,
    Validator,
    parse_adl,
    parse_adl_file,
)
from .personas import (
    PERSONA_TEMPLATES,
    PersonaTemplate,
    generate_adl_from_persona,
    get_persona_mode,
    get_persona_template,
    list_personas,
)

__all__ = [
    "ADLConfig",
    "ADLGenerationResult",
    "DtoDef",
    "EntityDef",
    "EnumDef",
    "FieldDef",
    "PaginationDef",
    "RelationshipDef",
    "RelationshipEnd",
    "ServiceDef",
    "Validator",
    "generate_from_adl",
    "parse_adl",
    "parse_adl_file",
    # Personas
    "PersonaTemplate",
    "PERSONA_TEMPLATES",
    "get_persona_template",
    "list_personas",
    "generate_adl_from_persona",
    "get_persona_mode",
]
