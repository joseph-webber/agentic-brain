# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
ADL Entity Generator - Generates all 7 layers from parsed ADL entities.

Uses Jinja2 templates to generate:
1. Model (SQLModel + Pydantic)
2. DAO (CRUD operations)
3. Service (business logic)
4. Business Object (domain rules)
5. API Routes (FastAPI)
6. React Component (CRUD UI)
7. CLI Commands (Typer)

Part of the hybrid DAO+RAG pattern for agentic-brain.
"""

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .entity_parser import EntityDefinition, FieldDefinition, RelationshipDefinition

logger = logging.getLogger(__name__)


@dataclass
class GeneratedFile:
    """Represents a generated file."""

    path: str
    content: str
    layer: str


class EntityGenerator:
    """
    Generates all 7 layers from parsed ADL entity definitions.
    Uses Jinja2 templates for code generation.
    """

    LAYERS = ["model", "dao", "service", "business_object", "routes", "react", "cli"]

    def __init__(
        self, template_dir: Optional[str] = None, output_dir: Optional[str] = None
    ):
        """
        Initialize generator with template and output directories.

        Args:
            template_dir: Path to Jinja2 templates
            output_dir: Path to write generated files
        """
        self.template_dir = Path(template_dir or Path(__file__).parent / "templates")
        self.output_dir = Path(output_dir or Path(__file__).parent / "generated")

        # Ensure directories exist
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters["capitalize"] = str.capitalize
        self.env.filters["lower"] = str.lower
        self.env.filters["upper"] = str.upper
        self.env.filters["snake_case"] = self._to_snake_case
        self.env.filters["camel_case"] = self._to_camel_case
        self.env.filters["pascal_case"] = self._to_pascal_case
        self.env.filters["python_type"] = self._to_python_type
        self.env.filters["ts_type"] = self._to_typescript_type

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert to snake_case."""
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @staticmethod
    def _to_camel_case(name: str) -> str:
        """Convert to camelCase."""
        components = name.split("_")
        return components[0].lower() + "".join(x.title() for x in components[1:])

    @staticmethod
    def _to_pascal_case(name: str) -> str:
        """Convert to PascalCase."""
        return "".join(x.title() for x in name.split("_"))

    @staticmethod
    def _to_python_type(field_type: str) -> str:
        """Convert ADL type to Python type."""
        type_map = {
            "String": "str",
            "Text": "str",
            "Integer": "int",
            "Float": "float",
            "Boolean": "bool",
            "DateTime": "datetime",
            "Date": "date",
            "UUID": "UUID",
            "JSON": "Dict[str, Any]",
            "Bytes": "bytes",
            "Decimal": "Decimal",
        }
        return type_map.get(field_type, "Any")

    @staticmethod
    def _to_typescript_type(field_type: str) -> str:
        """Convert ADL type to TypeScript type."""
        type_map = {
            "String": "string",
            "Text": "string",
            "Integer": "number",
            "Float": "number",
            "Boolean": "boolean",
            "DateTime": "Date",
            "Date": "Date",
            "UUID": "string",
            "JSON": "Record<string, any>",
            "Bytes": "Uint8Array",
            "Decimal": "number",
        }
        return type_map.get(field_type, "any")

    def generate(self, entity: EntityDefinition) -> List[GeneratedFile]:
        """
        Generate all 7 layers for an entity.

        Args:
            entity: Parsed entity definition

        Returns:
            List of generated files
        """
        generated_files: List[GeneratedFile] = []

        # Prepare context for templates
        context = self._prepare_context(entity)

        for layer in self.LAYERS:
            try:
                file = self._generate_layer(layer, context)
                if file:
                    generated_files.append(file)
                    logger.info(f"Generated {layer} for {entity.name}")
            except Exception as e:
                logger.error(f"Failed to generate {layer} for {entity.name}: {e}")

        return generated_files

    def _prepare_context(self, entity: EntityDefinition) -> Dict[str, Any]:
        """Prepare template context from entity definition."""
        return {
            "entity_name": entity.name,
            "entity_name_lower": entity.name.lower(),
            "entity_name_snake": self._to_snake_case(entity.name),
            "entity_name_camel": self._to_camel_case(entity.name),
            "entity_name_pascal": self._to_pascal_case(entity.name),
            "fields": [self._field_to_dict(f) for f in entity.fields],
            "relationships": [
                self._relationship_to_dict(r) for r in entity.relationships
            ],
            "access": entity.access,
            "storage": entity.storage,
            "searchable_fields": [f for f in entity.fields if f.searchable],
            "required_fields": [f for f in entity.fields if f.required],
            "unique_fields": [f for f in entity.fields if f.unique],
            "has_rag": entity.storage.get("rag") is not None,
            "has_dao": entity.storage.get("dao") is not None,
            "has_graph": entity.storage.get("graph") is not None,
        }

    def _field_to_dict(self, field: FieldDefinition) -> Dict[str, Any]:
        """Convert FieldDefinition to dict for template."""
        return {
            "name": field.name,
            "type": field.field_type,
            "python_type": self._to_python_type(field.field_type),
            "ts_type": self._to_typescript_type(field.field_type),
            "required": field.required,
            "unique": field.unique,
            "searchable": field.searchable,
            "max_length": field.max_length,
            "min_length": field.min_length,
            "default": field.default,
            "foreign_key": field.foreign_key,
            "optional": not field.required,
            "primary_key": field.name == "id",
        }

    def _relationship_to_dict(self, rel: RelationshipDefinition) -> Dict[str, Any]:
        """Convert RelationshipDefinition to dict for template."""
        return {
            "name": rel.name,
            "type": rel.rel_type,
            "target_entity": rel.target_entity,
            "alias": rel.alias,
            "cascade": rel.cascade,
            "through": rel.through,
            "back_populates": rel.alias or rel.name.lower(),
        }

    def _generate_layer(
        self, layer: str, context: Dict[str, Any]
    ) -> Optional[GeneratedFile]:
        """Generate a single layer using template."""
        template_name = f"{layer}.py.j2"
        if layer == "react":
            template_name = "react.tsx.j2"

        template_path = self.template_dir / template_name

        # Check if template exists, if not create default
        if not template_path.exists():
            self._create_default_template(layer, template_path)

        try:
            template = self.env.get_template(template_name)
            content = template.render(**context)

            # Determine output path
            if layer == "react":
                ext = "tsx"
                subdir = "react"
            else:
                ext = "py"
                subdir = layer

            output_subdir = self.output_dir / context["entity_name_lower"] / subdir
            output_subdir.mkdir(parents=True, exist_ok=True)

            filename = f"{context['entity_name_snake']}_{layer}.{ext}"
            output_path = output_subdir / filename

            # Write file
            output_path.write_text(content)

            return GeneratedFile(path=str(output_path), content=content, layer=layer)
        except Exception as e:
            logger.error(f"Template error for {layer}: {e}")
            return None

    def _create_default_template(self, layer: str, template_path: Path) -> None:
        """Create default template for a layer."""
        templates = {
            "model": MODEL_TEMPLATE,
            "dao": DAO_TEMPLATE,
            "service": SERVICE_TEMPLATE,
            "business_object": BUSINESS_OBJECT_TEMPLATE,
            "routes": ROUTES_TEMPLATE,
            "react": REACT_TEMPLATE,
            "cli": CLI_TEMPLATE,
        }

        template_content = templates.get(
            layer, "# TODO: Add template for {{ entity_name }}"
        )
        template_path.write_text(template_content)

    def write_all(
        self, entities: List[EntityDefinition]
    ) -> Dict[str, List[GeneratedFile]]:
        """
        Generate all layers for multiple entities.

        Args:
            entities: List of entity definitions

        Returns:
            Dict mapping entity name to generated files
        """
        results = {}
        for entity in entities:
            results[entity.name] = self.generate(entity)
        return results


# Default templates (embedded)
MODEL_TEMPLATE = '''"""
SQLModel entity for {{ entity_name }}.
Auto-generated by ADL EntityGenerator.
"""

from typing import Optional, List, Any, Dict
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID


class {{ entity_name }}Base(SQLModel):
    """Base model with shared fields."""
    {% for field in fields %}
    {% if not field.primary_key %}
    {{ field.name }}: {% if field.optional %}Optional[{{ field.python_type }}]{% else %}{{ field.python_type }}{% endif %}{% if field.default %} = {{ field.default }}{% elif field.optional %} = None{% endif %}{% if field.max_length %} = Field(max_length={{ field.max_length }}){% endif %}
    {% endif %}
    {% endfor %}


class {{ entity_name }}({{ entity_name }}Base, table=True):
    """Database table model."""
    __tablename__ = "{{ entity_name_snake }}s"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    {% for rel in relationships %}
    {% if rel.type == 'belongsTo' %}
    {{ rel.target_entity | lower }}_id: Optional[int] = Field(default=None, foreign_key="{{ rel.target_entity | lower }}s.id")
    {{ rel.name }}: Optional["{{ rel.target_entity }}"] = Relationship(back_populates="{{ rel.back_populates }}")
    {% elif rel.type == 'hasMany' %}
    {{ rel.name }}: List["{{ rel.target_entity }}"] = Relationship(back_populates="{{ entity_name_lower }}"{% if rel.cascade %}, sa_relationship_kwargs={"cascade": "all, delete-orphan"}{% endif %})
    {% endif %}
    {% endfor %}


class {{ entity_name }}Create({{ entity_name }}Base):
    """Schema for creating entity."""
    pass


class {{ entity_name }}Update(SQLModel):
    """Schema for updating entity."""
    {% for field in fields %}
    {% if not field.primary_key %}
    {{ field.name }}: Optional[{{ field.python_type }}] = None
    {% endif %}
    {% endfor %}


class {{ entity_name }}Read({{ entity_name }}Base):
    """Schema for reading entity."""
    id: int
    created_at: datetime
    updated_at: datetime
'''

DAO_TEMPLATE = '''"""
DAO (Data Access Object) for {{ entity_name }}.
Auto-generated by ADL EntityGenerator.
"""

from typing import Optional, List
from sqlmodel import Session, select, create_engine
from .{{ entity_name_snake }}_model import {{ entity_name }}, {{ entity_name }}Create, {{ entity_name }}Update


class {{ entity_name }}DAO:
    """Data Access Object for {{ entity_name }} CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, data: {{ entity_name }}Create) -> {{ entity_name }}:
        """Create a new {{ entity_name }}."""
        entity = {{ entity_name }}.model_validate(data)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get(self, entity_id: int) -> Optional[{{ entity_name }}]:
        """Get {{ entity_name }} by ID."""
        return self.session.get({{ entity_name }}, entity_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> List[{{ entity_name }}]:
        """Get all {{ entity_name }} entities with pagination."""
        statement = select({{ entity_name }}).offset(skip).limit(limit)
        return list(self.session.exec(statement).all())

    def update(self, entity_id: int, data: {{ entity_name }}Update) -> Optional[{{ entity_name }}]:
        """Update {{ entity_name }} by ID."""
        entity = self.get(entity_id)
        if not entity:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)

        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, entity_id: int) -> bool:
        """Delete {{ entity_name }} by ID."""
        entity = self.get(entity_id)
        if not entity:
            return False

        self.session.delete(entity)
        self.session.commit()
        return True

    {% if searchable_fields %}
    def search(self, query: str) -> List[{{ entity_name }}]:
        """Search {{ entity_name }} by searchable fields (exact match)."""
        statement = select({{ entity_name }}).where(
            {% for field in searchable_fields %}
            {{ entity_name }}.{{ field.name }}.contains(query){% if not loop.last %} | {% endif %}
            {% endfor %}
        )
        return list(self.session.exec(statement).all())
    {% endif %}
'''

SERVICE_TEMPLATE = '''"""
Service layer for {{ entity_name }}.
Auto-generated by ADL EntityGenerator.
"""

from typing import Optional, List
from sqlmodel import Session
from .{{ entity_name_snake }}_dao import {{ entity_name }}DAO
from .{{ entity_name_snake }}_model import {{ entity_name }}, {{ entity_name }}Create, {{ entity_name }}Update
{% if has_rag %}
from ..rag.rag_service import RAGService
{% endif %}


class {{ entity_name }}Service:
    """Service layer for {{ entity_name }} business logic."""

    def __init__(self, session: Session{% if has_rag %}, rag_service: Optional[RAGService] = None{% endif %}):
        self.dao = {{ entity_name }}DAO(session)
        {% if has_rag %}
        self.rag = rag_service
        {% endif %}

    async def create(self, data: {{ entity_name }}Create) -> {{ entity_name }}:
        """Create a new {{ entity_name }}."""
        entity = self.dao.create(data)
        {% if has_rag %}
        # Sync to RAG for semantic search
        if self.rag:
            await self.rag.embed_entity(entity, "{{ entity_name_lower }}")
        {% endif %}
        return entity

    async def get(self, entity_id: int) -> Optional[{{ entity_name }}]:
        """Get {{ entity_name }} by ID."""
        return self.dao.get(entity_id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[{{ entity_name }}]:
        """Get all {{ entity_name }} entities."""
        return self.dao.get_all(skip=skip, limit=limit)

    async def update(self, entity_id: int, data: {{ entity_name }}Update) -> Optional[{{ entity_name }}]:
        """Update {{ entity_name }}."""
        entity = self.dao.update(entity_id, data)
        {% if has_rag %}
        if entity and self.rag:
            await self.rag.embed_entity(entity, "{{ entity_name_lower }}")
        {% endif %}
        return entity

    async def delete(self, entity_id: int) -> bool:
        """Delete {{ entity_name }}."""
        {% if has_rag %}
        if self.rag:
            await self.rag.delete_entity("{{ entity_name_lower }}", str(entity_id))
        {% endif %}
        return self.dao.delete(entity_id)

    {% if has_rag %}
    async def semantic_search(self, query: str, limit: int = 10) -> List[{{ entity_name }}]:
        """Semantic search using RAG."""
        if not self.rag:
            return []

        results = await self.rag.search_entities("{{ entity_name_lower }}", query, limit)
        entity_ids = [int(r.entity_id) for r in results]
        return [e for e in [self.dao.get(eid) for eid in entity_ids] if e]

    async def hybrid_search(self, query: str, limit: int = 10) -> List[{{ entity_name }}]:
        """Hybrid search combining DAO exact match + RAG semantic."""
        dao_results = self.dao.search(query) if hasattr(self.dao, 'search') else []
        rag_results = await self.semantic_search(query, limit)

        # Merge and deduplicate
        seen_ids = set()
        combined = []
        for entity in dao_results + rag_results:
            if entity.id not in seen_ids:
                seen_ids.add(entity.id)
                combined.append(entity)

        return combined[:limit]
    {% endif %}
'''

BUSINESS_OBJECT_TEMPLATE = '''"""
Business Object for {{ entity_name }}.
Domain rules and validation logic.
Auto-generated by ADL EntityGenerator.
"""

from typing import Optional, List, Any
from pydantic import BaseModel, validator
from .{{ entity_name_snake }}_model import {{ entity_name }}, {{ entity_name }}Create


class {{ entity_name }}BusinessObject:
    """
    Business Object encapsulating domain rules for {{ entity_name }}.
    Add custom business logic methods here.
    """

    def __init__(self, entity: {{ entity_name }}):
        self._entity = entity

    @property
    def entity(self) -> {{ entity_name }}:
        return self._entity

    # Add custom business methods below
    # Example:
    # def calculate_score(self) -> float:
    #     return ...

    {% for field in fields %}
    {% if field.required %}
    def validate_{{ field.name }}(self) -> bool:
        """Validate {{ field.name }} field."""
        value = getattr(self._entity, "{{ field.name }}", None)
        if value is None:
            return False
        {% if field.max_length %}
        if len(str(value)) > {{ field.max_length }}:
            return False
        {% endif %}
        {% if field.min_length %}
        if len(str(value)) < {{ field.min_length }}:
            return False
        {% endif %}
        return True
    {% endif %}
    {% endfor %}

    def validate_all(self) -> List[str]:
        """Validate all required fields. Returns list of errors."""
        errors = []
        {% for field in required_fields %}
        if not self.validate_{{ field.name }}():
            errors.append("{{ field.name }} validation failed")
        {% endfor %}
        return errors
'''

ROUTES_TEMPLATE = '''"""
FastAPI routes for {{ entity_name }}.
Auto-generated by ADL EntityGenerator.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session

from .{{ entity_name_snake }}_model import {{ entity_name }}, {{ entity_name }}Create, {{ entity_name }}Update, {{ entity_name }}Read
from .{{ entity_name_snake }}_service import {{ entity_name }}Service
from ..database import get_session
{% if has_rag %}
from ..rag.rag_service import get_rag_service
{% endif %}

router = APIRouter(prefix="/{{ entity_name_lower }}s", tags=["{{ entity_name }}"])


def get_service(
    session: Session = Depends(get_session){% if has_rag %},
    rag = Depends(get_rag_service){% endif %}
) -> {{ entity_name }}Service:
    return {{ entity_name }}Service(session{% if has_rag %}, rag{% endif %})


@router.post("/", response_model={{ entity_name }}Read, status_code=status.HTTP_201_CREATED)
async def create_{{ entity_name_snake }}(
    data: {{ entity_name }}Create,
    service: {{ entity_name }}Service = Depends(get_service)
):
    """Create a new {{ entity_name }}."""
    return await service.create(data)


@router.get("/{entity_id}", response_model={{ entity_name }}Read)
async def get_{{ entity_name_snake }}(
    entity_id: int,
    service: {{ entity_name }}Service = Depends(get_service)
):
    """Get {{ entity_name }} by ID."""
    entity = await service.get(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="{{ entity_name }} not found")
    return entity


@router.get("/", response_model=List[{{ entity_name }}Read])
async def list_{{ entity_name_snake }}s(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: {{ entity_name }}Service = Depends(get_service)
):
    """List all {{ entity_name }}s with pagination."""
    return await service.get_all(skip=skip, limit=limit)


@router.put("/{entity_id}", response_model={{ entity_name }}Read)
async def update_{{ entity_name_snake }}(
    entity_id: int,
    data: {{ entity_name }}Update,
    service: {{ entity_name }}Service = Depends(get_service)
):
    """Update {{ entity_name }} by ID."""
    entity = await service.update(entity_id, data)
    if not entity:
        raise HTTPException(status_code=404, detail="{{ entity_name }} not found")
    return entity


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_{{ entity_name_snake }}(
    entity_id: int,
    service: {{ entity_name }}Service = Depends(get_service)
):
    """Delete {{ entity_name }} by ID."""
    if not await service.delete(entity_id):
        raise HTTPException(status_code=404, detail="{{ entity_name }} not found")


{% if has_rag %}
@router.get("/search/semantic", response_model=List[{{ entity_name }}Read])
async def semantic_search_{{ entity_name_snake }}(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    service: {{ entity_name }}Service = Depends(get_service)
):
    """Semantic search for {{ entity_name }}s using RAG."""
    return await service.semantic_search(query, limit)


@router.get("/search/hybrid", response_model=List[{{ entity_name }}Read])
async def hybrid_search_{{ entity_name_snake }}(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    service: {{ entity_name }}Service = Depends(get_service)
):
    """Hybrid search combining exact + semantic matching."""
    return await service.hybrid_search(query, limit)
{% endif %}
'''

REACT_TEMPLATE = """/**
 * React component for {{ entity_name }}.
 * Auto-generated by ADL EntityGenerator.
 */

import React, { useState, useEffect } from 'react';

interface {{ entity_name }} {
  id: number;
  {% for field in fields %}
  {{ field.name }}{% if field.optional %}?{% endif %}: {{ field.ts_type }};
  {% endfor %}
  created_at: string;
  updated_at: string;
}

interface {{ entity_name }}FormData {
  {% for field in fields %}
  {% if not field.primary_key %}
  {{ field.name }}{% if field.optional %}?{% endif %}: {{ field.ts_type }};
  {% endif %}
  {% endfor %}
}

const API_BASE = '/api/{{ entity_name_lower }}s';

export const {{ entity_name }}List: React.FC = () => {
  const [items, setItems] = useState<{{ entity_name }}[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(API_BASE)
      .then(res => res.json())
      .then(setItems)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="{{ entity_name_lower }}-list">
      <h2>{{ entity_name }}s</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            {% for field in fields %}
            {% if not field.primary_key %}
            <th>{{ field.name | capitalize }}</th>
            {% endif %}
            {% endfor %}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.id}>
              <td>{item.id}</td>
              {% for field in fields %}
              {% if not field.primary_key %}
              <td>{item.{{ field.name }}}</td>
              {% endif %}
              {% endfor %}
              <td>
                <button onClick={() => handleEdit(item)}>Edit</button>
                <button onClick={() => handleDelete(item.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const {{ entity_name }}Form: React.FC<{
  initial?: {{ entity_name }};
  onSubmit: (data: {{ entity_name }}FormData) => void;
}> = ({ initial, onSubmit }) => {
  const [formData, setFormData] = useState<{{ entity_name }}FormData>(
    initial || {
      {% for field in fields %}
      {% if not field.primary_key %}
      {{ field.name }}: {% if field.ts_type == 'string' %}''{% elif field.ts_type == 'number' %}0{% elif field.ts_type == 'boolean' %}false{% else %}undefined{% endif %},
      {% endif %}
      {% endfor %}
    }
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="{{ entity_name_lower }}-form">
      {% for field in fields %}
      {% if not field.primary_key %}
      <div className="form-group">
        <label htmlFor="{{ field.name }}">{{ field.name | capitalize }}{% if field.required %} *{% endif %}</label>
        <input
          type="{% if field.ts_type == 'number' %}number{% elif field.ts_type == 'boolean' %}checkbox{% else %}text{% endif %}"
          id="{{ field.name }}"
          name="{{ field.name }}"
          value={formData.{{ field.name }} || ''}
          onChange={handleChange}
          {% if field.required %}required{% endif %}
          {% if field.max_length %}maxLength={{ field.max_length }}{% endif %}
        />
      </div>
      {% endif %}
      {% endfor %}
      <button type="submit">{initial ? 'Update' : 'Create'}</button>
    </form>
  );
};

{% if has_rag %}
export const {{ entity_name }}Search: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<{{ entity_name }}[]>([]);
  const [searchType, setSearchType] = useState<'semantic' | 'hybrid'>('hybrid');

  const handleSearch = async () => {
    const url = `${API_BASE}/search/${searchType}?query=${encodeURIComponent(query)}`;
    const response = await fetch(url);
    const data = await response.json();
    setResults(data);
  };

  return (
    <div className="{{ entity_name_lower }}-search">
      <h3>Search {{ entity_name }}s</h3>
      <div>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Enter search query..."
        />
        <select value={searchType} onChange={e => setSearchType(e.target.value as any)}>
          <option value="hybrid">Hybrid (Exact + Semantic)</option>
          <option value="semantic">Semantic Only</option>
        </select>
        <button onClick={handleSearch}>Search</button>
      </div>
      <ul>
        {results.map(item => (
          <li key={item.id}>{JSON.stringify(item)}</li>
        ))}
      </ul>
    </div>
  );
};
{% endif %}

export default {{ entity_name }}List;
"""

CLI_TEMPLATE = '''"""
Typer CLI commands for {{ entity_name }}.
Auto-generated by ADL EntityGenerator.
"""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
import json

app = typer.Typer(help="{{ entity_name }} management commands")
console = Console()


@app.command("list")
def list_{{ entity_name_snake }}s(
    limit: int = typer.Option(100, "--limit", "-l", help="Max items to return"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json")
):
    """List all {{ entity_name }}s."""
    # TODO: Integrate with service layer
    console.print(f"Listing {{ entity_name }}s (limit={limit}, format={format})")


@app.command("get")
def get_{{ entity_name_snake }}(
    entity_id: int = typer.Argument(..., help="{{ entity_name }} ID")
):
    """Get a {{ entity_name }} by ID."""
    # TODO: Integrate with service layer
    console.print(f"Getting {{ entity_name }} with ID {entity_id}")


@app.command("create")
def create_{{ entity_name_snake }}(
    {% for field in fields %}
    {% if field.required and not field.primary_key %}
    {{ field.name }}: str = typer.Option(..., "--{{ field.name }}", help="{{ field.name }} value"),
    {% endif %}
    {% endfor %}
):
    """Create a new {{ entity_name }}."""
    data = {
        {% for field in fields %}
        {% if field.required and not field.primary_key %}
        "{{ field.name }}": {{ field.name }},
        {% endif %}
        {% endfor %}
    }
    console.print(f"Creating {{ entity_name }}: {json.dumps(data, indent=2)}")


@app.command("update")
def update_{{ entity_name_snake }}(
    entity_id: int = typer.Argument(..., help="{{ entity_name }} ID"),
    data: str = typer.Option(..., "--data", "-d", help="JSON data to update")
):
    """Update a {{ entity_name }}."""
    # TODO: Integrate with service layer
    console.print(f"Updating {{ entity_name }} {entity_id} with: {data}")


@app.command("delete")
def delete_{{ entity_name_snake }}(
    entity_id: int = typer.Argument(..., help="{{ entity_name }} ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Delete a {{ entity_name }}."""
    if not force:
        confirm = typer.confirm(f"Delete {{ entity_name }} {entity_id}?")
        if not confirm:
            raise typer.Abort()
    console.print(f"Deleted {{ entity_name }} {entity_id}")


{% if has_rag %}
@app.command("search")
def search_{{ entity_name_snake }}(
    query: str = typer.Argument(..., help="Search query"),
    mode: str = typer.Option("hybrid", "--mode", "-m", help="Search mode: hybrid, semantic")
):
    """Search {{ entity_name }}s using semantic search."""
    # TODO: Integrate with RAG service
    console.print(f"Searching {{ entity_name }}s for '{query}' (mode={mode})")
{% endif %}


if __name__ == "__main__":
    app()
'''
