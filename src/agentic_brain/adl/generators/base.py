# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""Base class for ADL generators."""

from __future__ import annotations

import re
from typing import Any, List, Optional

from ..parser import (
    ADLConfig,
    FieldDef,
    RelationshipDef,
)


def to_snake_case(name: str) -> str:
    """Convert PascalCase/camelCase to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0].lower() + "".join(p.title() for p in parts[1:])


ADL_TO_PYTHON_TYPE = {
    "String": "str",
    "TextBlob": "str",
    "Text": "str",
    "Integer": "int",
    "Long": "int",
    "Float": "float",
    "Double": "float",
    "BigDecimal": "Decimal",
    "Boolean": "bool",
    "LocalDate": "date",
    "Instant": "datetime",
    "DateTime": "datetime",
    "ZonedDateTime": "datetime",
    "Duration": "timedelta",
    "UUID": "UUID",
    "Blob": "bytes",
    "AnyBlob": "bytes",
    "ImageBlob": "bytes",
    "Vector": "List[float]",
}

ADL_TO_NEO4J_TYPE = {
    "String": "STRING",
    "TextBlob": "STRING",
    "Text": "STRING",
    "Integer": "INTEGER",
    "Long": "INTEGER",
    "Float": "FLOAT",
    "Double": "FLOAT",
    "BigDecimal": "FLOAT",
    "Boolean": "BOOLEAN",
    "LocalDate": "DATE",
    "Instant": "DATETIME",
    "DateTime": "DATETIME",
    "ZonedDateTime": "ZONED DATETIME",
    "Duration": "DURATION",
    "UUID": "STRING",
    "Vector": "LIST<FLOAT>",
}

ADL_TO_TS_TYPE = {
    "String": "string",
    "TextBlob": "string",
    "Text": "string",
    "Integer": "number",
    "Long": "number",
    "Float": "number",
    "Double": "number",
    "BigDecimal": "number",
    "Boolean": "boolean",
    "LocalDate": "string",
    "Instant": "string",
    "DateTime": "string",
    "ZonedDateTime": "string",
    "Duration": "string",
    "UUID": "string",
    "Blob": "Uint8Array",
    "AnyBlob": "Uint8Array",
    "ImageBlob": "string",
    "Vector": "number[]",
}


def python_type(adl_type: str) -> str:
    return ADL_TO_PYTHON_TYPE.get(adl_type, "Any")


def neo4j_type(adl_type: str) -> str:
    return ADL_TO_NEO4J_TYPE.get(adl_type, "STRING")


def ts_type(adl_type: str) -> str:
    return ADL_TO_TS_TYPE.get(adl_type, "any")


def has_validator(field: FieldDef, name: str) -> bool:
    """Check if a field has a specific validator."""
    return any(v.name == name for v in (field.validators or []))


def get_validator_arg(field: FieldDef, name: str, default: Any = None) -> Any:
    """Get first arg from a named validator."""
    for v in field.validators or []:
        if v.name == name and v.args:
            return v.args[0]
    return default


def entity_has_pagination(cfg: ADLConfig, entity_name: str) -> Optional[str]:
    """Return pagination style if entity is configured for pagination."""
    for p in cfg.paginations:
        if entity_name in p.entities or "*" in p.entities or "all" in p.entities:
            return p.style
    return None


def entity_has_dto(cfg: ADLConfig, entity_name: str) -> Optional[str]:
    """Return DTO mapper if entity is configured for DTO."""
    for d in cfg.dtos:
        if entity_name in d.entities or "*" in d.entities or "all" in d.entities:
            return d.mapper
    return None


def entity_has_service(cfg: ADLConfig, entity_name: str) -> Optional[str]:
    """Return service impl if entity is configured for service layer."""
    for s in cfg.services:
        if entity_name in s.entities or "*" in s.entities or "all" in s.entities:
            return s.impl
    return None


def get_relationships_for_entity(
    cfg: ADLConfig, entity_name: str
) -> List[RelationshipDef]:
    """Get all relationships where entity is the 'from' end."""
    return [r for r in cfg.relationships if r.from_end.entity == entity_name]


def get_incoming_relationships(
    cfg: ADLConfig, entity_name: str
) -> List[RelationshipDef]:
    """Get all relationships where entity is the 'to' end."""
    return [r for r in cfg.relationships if r.to_end.entity == entity_name]
