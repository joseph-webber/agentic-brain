# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""Generate accessible React CRUD components from ADL entities."""

from __future__ import annotations

from typing import List

from ..parser import ADLConfig, EntityDef
from .base import (
    entity_has_pagination,
    has_validator,
    to_snake_case,
    ts_type,
)


class ReactComponentGenerator:
    """Generates accessible React TSX components from parsed ADL config.

    All generated components follow WCAG 2.1 AA:
    - Proper ARIA labels on all interactive elements
    - Keyboard navigation support
    - Visible focus indicators
    - Semantic HTML (table, form, button)
    """

    def generate(self, cfg: ADLConfig) -> str:
        """Return a complete TSX module for all entities."""
        parts: List[str] = []
        for name, entity in cfg.entities.items():
            parts.append(self._generate_component(cfg, name, entity))
        return "\n\n".join(parts)

    def generate_entity_component(self, cfg: ADLConfig, entity_name: str) -> str:
        """Generate a single entity component."""
        entity = cfg.entities.get(entity_name)
        if entity is None:
            raise ValueError(f"Entity '{entity_name}' not found")
        return self._generate_component(cfg, entity_name, entity)

    # --- internal ---

    def _generate_component(self, cfg: ADLConfig, name: str, entity: EntityDef) -> str:
        snake = to_snake_case(name)
        plural = f"{snake}s"
        pagination = entity_has_pagination(cfg, name)

        fields_ts = self._interface_fields(entity)
        form_fields = self._form_fields(entity)
        table_headers = self._table_headers(entity)
        table_cells = self._table_cells(entity)

        pagination_block = ""
        if pagination:
            pagination_block = f"""
      <nav aria-label="{name} pagination">
        <button
          onClick={{() => setPage(p => Math.max(1, p - 1))}}
          disabled={{page <= 1}}
          aria-label="Previous page"
        >
          Previous
        </button>
        <span aria-live="polite">Page {{page}}</span>
        <button
          onClick={{() => setPage(p => p + 1)}}
          aria-label="Next page"
        >
          Next
        </button>
      </nav>"""

        page_state = ""
        if pagination:
            page_state = "\n  const [page, setPage] = useState(1);"

        return f"""/**
 * Accessible CRUD component for {name}.
 * Auto-generated from ADL — WCAG 2.1 AA compliant.
 */

import React, {{ useState, useEffect }} from 'react';

interface I{name} {{
  id: number;
{fields_ts}
}}

const API = '/api/{plural}';

export const {name}List: React.FC = () => {{
  const [items, setItems] = useState<I{name}[]>([]);
  const [loading, setLoading] = useState(true);{page_state}

  useEffect(() => {{
    setLoading(true);
    fetch(API)
      .then(r => r.json())
      .then(data => {{ setItems(Array.isArray(data) ? data : data.items || []); setLoading(false); }})
      .catch(() => setLoading(false));
  }}, []);

  if (loading) return <p role="status" aria-live="polite">Loading {plural}…</p>;

  return (
    <section aria-label="{name} list">
      <h2>{name}s</h2>
      <table aria-label="{name} data table">
        <thead>
          <tr>
            <th scope="col">ID</th>
{table_headers}
          </tr>
        </thead>
        <tbody>
          {{items.map(item => (
            <tr key={{item.id}}>
              <td>{{item.id}}</td>
{table_cells}
            </tr>
          ))}}
        </tbody>
      </table>
{pagination_block}
    </section>
  );
}};

export const {name}Form: React.FC<{{ onSubmit: (data: Partial<I{name}>) => void }}> = ({{ onSubmit }}) => {{
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {{
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const data: Record<string, string> = {{}};
    form.forEach((v, k) => {{ data[k] = String(v); }});
    onSubmit(data as any);
  }};

  return (
    <form onSubmit={{handleSubmit}} aria-label="Create {name}">
{form_fields}
      <button type="submit" aria-label="Save {name}">
        Save
      </button>
    </form>
  );
}};
"""

    def _interface_fields(self, entity: EntityDef) -> str:
        lines: List[str] = []
        for f in entity.fields:
            t = ts_type(f.type)
            optional = "?" if not has_validator(f, "required") else ""
            lines.append(f"  {f.name}{optional}: {t};")
        return "\n".join(lines)

    def _table_headers(self, entity: EntityDef) -> str:
        return "\n".join(
            f'            <th scope="col">{f.name}</th>' for f in entity.fields
        )

    def _table_cells(self, entity: EntityDef) -> str:
        return "\n".join(
            f"              <td>{{item.{f.name}}}</td>" for f in entity.fields
        )

    def _form_fields(self, entity: EntityDef) -> str:
        lines: List[str] = []
        for f in entity.fields:
            required = has_validator(f, "required")
            req_attr = " required" if required else ""
            req_star = " *" if required else ""
            input_type = "text"
            if f.type in {"Integer", "Long", "Float", "Double", "BigDecimal"}:
                input_type = "number"
            elif f.type == "Boolean":
                input_type = "checkbox"
            lines.append("      <div>")
            lines.append(
                f'        <label htmlFor="{f.name}">{f.name}{req_star}</label>'
            )
            lines.append(
                f'        <input id="{f.name}" name="{f.name}" type="{input_type}"{req_attr}'
                f' aria-label="{f.name} field" />'
            )
            lines.append("      </div>")
        return "\n".join(lines)
