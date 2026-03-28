# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
ADL Entity Parser - Hybrid DAO + RAG Pattern
============================================

Parses ADL (Agentic Definition Language) entity definitions
and extracts field types, relationships, access control, and storage config.

Supports both DAO (relationships, CRUD) and RAG (semantic search) patterns.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ADLParseError(Exception):
    """Exception raised for ADL parsing errors."""

    def __init__(self, message: str, error_type: str = "ParseError"):
        self.error_type = error_type
        super().__init__(f"{error_type}: {message}")


class FieldType(Enum):
    """Supported ADL field types."""

    STRING = "String"
    TEXT = "Text"
    INTEGER = "Integer"
    FLOAT = "Float"
    BOOLEAN = "Boolean"
    DATETIME = "DateTime"
    LIST = "List"
    DICT = "Dict"


@dataclass
class FieldDefinition:
    """Parsed field definition."""

    name: str
    type: str
    required: bool = False
    searchable: bool = False
    unique: bool = False
    maxLength: Optional[int] = None
    minLength: Optional[int] = None
    default: Optional[str] = None
    foreignKey: Optional[str] = None


@dataclass
class RelationshipDefinition:
    """Parsed relationship definition."""

    type: str  # belongsTo, hasMany, manyToMany
    target: str
    alias: Optional[str] = None
    cascade: Optional[str] = None
    through: Optional[str] = None


@dataclass
class EntityDefinition:
    """Complete parsed entity."""

    name: str
    fields: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    access: Dict[str, List[str]] = field(default_factory=dict)
    storage: Dict[str, str] = field(default_factory=dict)
    validation: Dict[str, List[str]] = field(default_factory=dict)


class ADLEntityParser:
    """
    Parser for ADL (Agentic Definition Language) entity definitions.

    Supports hybrid DAO + RAG pattern:
    - DAO: relationships, foreign keys, cascades
    - RAG: searchable fields for semantic search

    Example ADL:
    ```
    entity Note {
        title String required maxLength(100)
        content Text searchable

        relationships {
            belongsTo User as author
            hasMany Comment cascade(delete)
        }

        access {
            read: USER, ADMIN
            write: owner, ADMIN
        }

        storage {
            dao: sqlite
            rag: chromadb
        }
    }
    ```
    """

    # Regex patterns
    ENTITY_PATTERN = re.compile(
        r"entity\s+(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", re.DOTALL
    )
    FIELD_PATTERN = re.compile(
        r"^\s*(\w+)\s+(String|Text|Integer|Float|Boolean|DateTime|List\[[^\]]+\]|Dict\[[^\]]+\])\s*(.*)$"
    )
    RELATIONSHIP_PATTERN = re.compile(
        r"(belongsTo|hasMany|manyToMany)\s+(\w+)(?:\s+as\s+(\w+))?(?:\s+cascade\((\w+)\))?(?:\s+through\((\w+)\))?"
    )
    ACCESS_PATTERN = re.compile(r"(\w+):\s*([^}\n]+)")
    STORAGE_PATTERN = re.compile(r"(\w+):\s*(\w+)")
    MODIFIER_PATTERN = re.compile(r"(\w+)(?:\(([^)]+)\))?")
    COMMENT_PATTERN = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)

    VALID_TYPES = {"String", "Text", "Integer", "Float", "Boolean", "DateTime"}

    def __init__(self):
        self.entities: Dict[str, EntityDefinition] = {}

    def parse(self, adl_content: str) -> Dict[str, Dict[str, Any]]:
        """
        Parse ADL content and return dictionary of entities.

        Args:
            adl_content: ADL source code

        Returns:
            Dictionary mapping entity names to their definitions

        Raises:
            ADLParseError: If ADL syntax is invalid
        """
        if not adl_content or not adl_content.strip():
            raise ADLParseError("ADL content is empty", "EmptyInput")

        # Remove comments
        content = self.COMMENT_PATTERN.sub("", adl_content)

        # Find all entities
        matches = self.ENTITY_PATTERN.findall(content)

        if not matches:
            # Check for partial entity definitions
            if "entity" in content and "{" not in content:
                raise ADLParseError("Entity body is missing", "MissingBody")
            if "entity" in content and content.count("{") != content.count("}"):
                raise ADLParseError("Unbalanced braces", "SyntaxError")
            if re.search(r"entity\s*\{", content):
                raise ADLParseError("Entity name is required", "MissingEntityName")

        result = {}
        for entity_name, entity_body in matches:
            entity = self._parse_entity(entity_name, entity_body)
            result[entity_name] = {
                "fields": entity.fields,
                "relationships": entity.relationships,
                "access": entity.access,
                "storage": entity.storage,
                "validation": entity.validation,
            }

        return result

    def _parse_entity(self, name: str, body: str) -> EntityDefinition:
        """Parse a single entity definition."""
        entity = EntityDefinition(name=name)

        # Extract sections
        sections = self._extract_sections(body)

        # Parse fields (main body)
        entity.fields = self._parse_fields(sections.get("main", ""))

        # Parse relationships
        if "relationships" in sections:
            entity.relationships = self._parse_relationships(sections["relationships"])

        # Parse access control
        if "access" in sections:
            entity.access = self._parse_access(sections["access"])

        # Parse storage config
        if "storage" in sections:
            entity.storage = self._parse_storage(sections["storage"])

        # Parse validation rules
        if "validation" in sections:
            entity.validation = self._parse_validation(sections["validation"])

        return entity

    def _extract_sections(self, body: str) -> Dict[str, str]:
        """Extract named sections from entity body."""
        sections = {"main": ""}

        # Find and extract named sections
        section_names = ["relationships", "access", "storage", "validation"]
        remaining = body

        for section_name in section_names:
            pattern = re.compile(rf"{section_name}\s*\{{([^{{}}]*)\}}", re.DOTALL)
            match = pattern.search(remaining)
            if match:
                sections[section_name] = match.group(1)
                remaining = remaining.replace(match.group(0), "")

        sections["main"] = remaining.strip()
        return sections

    def _parse_fields(self, fields_text: str) -> List[Dict[str, Any]]:
        """Parse field definitions."""
        fields = []

        for line in fields_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue

            # Try to match field pattern
            match = self.FIELD_PATTERN.match(line)
            if match:
                field_name, field_type, modifiers_text = match.groups()
                field_def = self._parse_field(field_name, field_type, modifiers_text)
                fields.append(field_def)
            elif line and not any(
                kw in line for kw in ["belongsTo", "hasMany", "manyToMany"]
            ):
                # Check if it looks like a field but is invalid
                if re.match(r"^\w+\s*$", line):
                    raise ADLParseError(
                        f"Field '{line.strip()}' missing type", "InvalidFieldDefinition"
                    )
                parts = line.split()
                if len(parts) >= 2 and parts[1] not in self.VALID_TYPES:
                    if not parts[1].startswith("List[") and not parts[1].startswith(
                        "Dict["
                    ):
                        raise ADLParseError(
                            f"Unknown field type '{parts[1]}'", "UnknownFieldType"
                        )

        return fields

    def _parse_field(
        self, name: str, type_str: str, modifiers_text: str
    ) -> Dict[str, Any]:
        """Parse a single field with its modifiers."""
        field_def: Dict[str, Any] = {
            "name": name,
            "type": type_str,
        }

        # Parse modifiers
        for modifier in self.MODIFIER_PATTERN.findall(modifiers_text):
            mod_name, mod_value = modifier

            if mod_name in ("required", "searchable", "unique"):
                field_def[mod_name] = True
            elif mod_name in ("maxLength", "minLength"):
                field_def[mod_name] = int(mod_value) if mod_value else None
            elif mod_name in ("default", "foreignKey"):
                field_def[mod_name] = mod_value

        return field_def

    def _parse_relationships(self, rel_text: str) -> List[Dict[str, Any]]:
        """Parse relationship definitions."""
        relationships = []

        for line in rel_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue

            match = self.RELATIONSHIP_PATTERN.match(line)
            if match:
                rel_type, target, alias, cascade, through = match.groups()
                rel = {
                    "type": rel_type,
                    "target": target,
                }
                if alias:
                    rel["alias"] = alias
                if cascade:
                    rel["cascade"] = cascade
                if through:
                    rel["through"] = through
                relationships.append(rel)
            elif line:
                raise ADLParseError(
                    f"Invalid relationship: {line}", "InvalidRelationship"
                )

        return relationships

    def _parse_access(self, access_text: str) -> Dict[str, List[str]]:
        """Parse access control rules."""
        access = {}

        for match in self.ACCESS_PATTERN.finditer(access_text):
            operation, roles_str = match.groups()
            roles = [r.strip() for r in roles_str.split(",")]
            access[operation] = roles

        return access

    def _parse_storage(self, storage_text: str) -> Dict[str, str]:
        """Parse storage configuration."""
        storage = {}

        for match in self.STORAGE_PATTERN.finditer(storage_text):
            key, value = match.groups()
            storage[key] = value

        return storage

    def _parse_validation(self, validation_text: str) -> Dict[str, List[str]]:
        """Parse validation rules."""
        validation = {}

        for match in self.ACCESS_PATTERN.finditer(validation_text):
            field_name, rules_str = match.groups()
            rules = [r.strip() for r in rules_str.split(",")]
            validation[field_name] = rules

        return validation


# ============== CONVENIENCE FUNCTIONS ==============


def parse_adl_file(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse an ADL file and return entities."""
    with open(filepath) as f:
        content = f.read()
    parser = ADLEntityParser()
    return parser.parse(content)


def parse_adl_string(content: str) -> Dict[str, Dict[str, Any]]:
    """Parse ADL string and return entities."""
    parser = ADLEntityParser()
    return parser.parse(content)
