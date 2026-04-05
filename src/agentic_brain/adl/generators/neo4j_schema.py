# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""Generate Neo4j Cypher schema from ADL entities and relationships."""

from __future__ import annotations

from typing import List

from ..parser import ADLConfig, EntityDef, RelationshipDef
from .base import (
    has_validator,
    to_snake_case,
)


class Neo4jSchemaGenerator:
    """Generates Cypher DDL (constraints, indexes) from parsed ADL config."""

    def generate(self, cfg: ADLConfig) -> str:
        """Return a complete Cypher schema script."""
        lines: List[str] = [
            "// Auto-generated Neo4j schema from ADL",
            "// ==========================================",
            "",
        ]

        # Enum comments (Neo4j doesn't have enums, but we document them)
        for name, enum_def in cfg.enums.items():
            vals = ", ".join(enum_def.values)
            lines.append(f"// Enum {name}: {vals}")
        if cfg.enums:
            lines.append("")

        # Node constraints and indexes
        for name, entity in cfg.entities.items():
            lines.append(f"// --- {name} ---")
            lines.extend(self._entity_constraints(name, entity))
            lines.extend(self._entity_indexes(name, entity))
            lines.append("")

        # Relationship types
        for rel in cfg.relationships:
            lines.append(self._relationship_comment(rel))
        if cfg.relationships:
            lines.append("")

        return "\n".join(lines)

    def generate_migration(self, cfg: ADLConfig) -> str:
        """Generate a migration-safe Cypher script (IF NOT EXISTS)."""
        lines: List[str] = [
            "// ADL Migration Script (idempotent)",
            "",
        ]

        for name, entity in cfg.entities.items():
            for field in entity.fields:
                if has_validator(field, "unique"):
                    lines.append(
                        f"CREATE CONSTRAINT {to_snake_case(name)}_{field.name}_unique "
                        f"IF NOT EXISTS FOR (n:{name}) REQUIRE n.{field.name} IS UNIQUE;"
                    )
                if has_validator(field, "required"):
                    lines.append(
                        f"CREATE CONSTRAINT {to_snake_case(name)}_{field.name}_exists "
                        f"IF NOT EXISTS FOR (n:{name}) REQUIRE n.{field.name} IS NOT NULL;"
                    )

            # Full-text index for searchable fields
            searchable = [f for f in entity.fields if has_validator(f, "searchable")]
            if searchable:
                props = ", ".join(f"n.{f.name}" for f in searchable)
                idx_name = f"{to_snake_case(name)}_fulltext"
                lines.append(
                    f"CREATE FULLTEXT INDEX {idx_name} IF NOT EXISTS "
                    f"FOR (n:{name}) ON EACH [{props}];"
                )

        lines.append("")
        return "\n".join(lines)

    # --- helpers ---

    def _entity_constraints(self, name: str, entity: EntityDef) -> List[str]:
        out: List[str] = []
        for field in entity.fields:
            if has_validator(field, "unique"):
                out.append(
                    f"CREATE CONSTRAINT {to_snake_case(name)}_{field.name}_unique "
                    f"IF NOT EXISTS FOR (n:{name}) REQUIRE n.{field.name} IS UNIQUE;"
                )
            if has_validator(field, "required"):
                out.append(
                    f"CREATE CONSTRAINT {to_snake_case(name)}_{field.name}_exists "
                    f"IF NOT EXISTS FOR (n:{name}) REQUIRE n.{field.name} IS NOT NULL;"
                )
        return out

    def _entity_indexes(self, name: str, entity: EntityDef) -> List[str]:
        out: List[str] = []
        searchable = [f for f in entity.fields if has_validator(f, "searchable")]
        if searchable:
            props = ", ".join(f"n.{f.name}" for f in searchable)
            out.append(
                f"CREATE FULLTEXT INDEX {to_snake_case(name)}_fulltext "
                f"IF NOT EXISTS FOR (n:{name}) ON EACH [{props}];"
            )
        return out

    def _relationship_comment(self, rel: RelationshipDef) -> str:
        rel_type = rel.kind.upper().replace("ONETOMANY", "HAS_MANY").replace(
            "MANYTOMANY", "MANY_TO_MANY"
        ).replace("ONETOONE", "HAS_ONE").replace(
            "ManyToMany", "MANY_TO_MANY"
        ).replace("OneToMany", "HAS_MANY").replace("OneToOne", "HAS_ONE")

        from_field = f"{{{rel.from_end.field}}}" if rel.from_end.field else ""
        to_field = f"{{{rel.to_end.field}}}" if rel.to_end.field else ""
        return (
            f"// (:{rel.from_end.entity}{from_field})"
            f"-[:{rel_type}]->"
            f"(:{rel.to_end.entity}{to_field})"
        )
