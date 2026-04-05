# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""Generate Python (Pydantic) models from ADL entities."""

from __future__ import annotations

from typing import List

from ..parser import ADLConfig, EntityDef, EnumDef, FieldDef
from .base import (
    entity_has_dto,
    entity_has_pagination,
    get_validator_arg,
    has_validator,
    python_type,
)


class PythonModelGenerator:
    """Generates Pydantic v2 models from parsed ADL config."""

    def generate(self, cfg: ADLConfig) -> str:
        """Return a complete Python module with models for all entities."""
        lines: List[str] = [
            '"""Auto-generated Pydantic models from ADL."""',
            "",
            "from __future__ import annotations",
            "",
            "from datetime import date, datetime, timedelta",
            "from decimal import Decimal",
            "from enum import Enum",
            "from typing import Any, Dict, List, Optional",
            "from uuid import UUID",
            "",
            "from pydantic import BaseModel, Field",
            "",
        ]

        # Enums
        for name, enum_def in cfg.enums.items():
            lines.extend(self._generate_enum(name, enum_def))
            lines.append("")

        # Entities
        for name, entity in cfg.entities.items():
            lines.extend(self._generate_entity(cfg, name, entity))
            lines.append("")

            # Generate DTO if configured
            if entity_has_dto(cfg, name):
                lines.extend(self._generate_dto(name, entity))
                lines.append("")

        return "\n".join(lines)

    def generate_entity(self, cfg: ADLConfig, entity_name: str) -> str:
        """Generate a single entity model."""
        entity = cfg.entities.get(entity_name)
        if entity is None:
            raise ValueError(f"Entity '{entity_name}' not found in ADL config")
        lines = self._generate_entity(cfg, entity_name, entity)
        return "\n".join(lines)

    # --- internal ---

    def _generate_enum(self, name: str, enum_def: EnumDef) -> List[str]:
        lines = [f"class {name}(str, Enum):"]
        for val in enum_def.values:
            lines.append(f'    {val} = "{val}"')
        return lines

    def _generate_entity(
        self, cfg: ADLConfig, name: str, entity: EntityDef
    ) -> List[str]:
        lines = [f"class {name}(BaseModel):"]
        if not entity.fields:
            lines.append("    pass")
            return lines

        for field in entity.fields:
            lines.append(self._field_line(field))

        # Pagination hint as class var
        pag = entity_has_pagination(cfg, name)
        if pag:
            lines.append("")
            lines.append(f'    class Config:')
            lines.append(f'        pagination = "{pag}"')

        return lines

    def _generate_dto(self, name: str, entity: EntityDef) -> List[str]:
        dto_name = f"{name}DTO"
        lines = [f"class {dto_name}(BaseModel):"]
        if not entity.fields:
            lines.append("    pass")
            return lines
        for field in entity.fields:
            py = python_type(field.type)
            lines.append(f"    {field.name}: Optional[{py}] = None")
        return lines

    def _field_line(self, field: FieldDef) -> str:
        py = python_type(field.type)
        required = has_validator(field, "required")
        unique = has_validator(field, "unique")

        field_args: List[str] = []

        # min / max validators
        minlen = get_validator_arg(field, "minlength") or get_validator_arg(
            field, "minLength"
        )
        maxlen = get_validator_arg(field, "maxlength") or get_validator_arg(
            field, "maxLength"
        )
        minval = get_validator_arg(field, "min")
        maxval = get_validator_arg(field, "max")

        if minlen is not None:
            field_args.append(f"min_length={minlen}")
        if maxlen is not None:
            field_args.append(f"max_length={maxlen}")
        if minval is not None:
            field_args.append(f"ge={minval}")
        if maxval is not None:
            field_args.append(f"le={maxval}")
        if unique:
            field_args.append("json_schema_extra={'unique': True}")

        if required:
            if field_args:
                args_str = ", ".join(field_args)
                return f"    {field.name}: {py} = Field(..., {args_str})"
            return f"    {field.name}: {py}"
        else:
            if field_args:
                args_str = ", ".join(field_args)
                return f"    {field.name}: Optional[{py}] = Field(None, {args_str})"
            return f"    {field.name}: Optional[{py}] = None"
