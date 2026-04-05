# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""Generate FastAPI CRUD routes from ADL entities."""

from __future__ import annotations

from typing import List

from ..parser import ADLConfig, EntityDef
from .base import (
    entity_has_pagination,
    entity_has_service,
    to_snake_case,
)


class ApiRouteGenerator:
    """Generates FastAPI route modules from parsed ADL config."""

    def generate(self, cfg: ADLConfig) -> str:
        """Return a complete FastAPI routes module for all entities."""
        lines: List[str] = [
            '"""Auto-generated FastAPI routes from ADL."""',
            "",
            "from __future__ import annotations",
            "",
            "from typing import List, Optional",
            "",
            "from fastapi import APIRouter, HTTPException, Query",
            "from pydantic import BaseModel",
            "",
        ]

        for name, entity in cfg.entities.items():
            lines.extend(self._generate_routes(cfg, name, entity))
            lines.append("")

        return "\n".join(lines)

    def generate_entity_routes(self, cfg: ADLConfig, entity_name: str) -> str:
        """Generate routes for a single entity."""
        entity = cfg.entities.get(entity_name)
        if entity is None:
            raise ValueError(f"Entity '{entity_name}' not found")
        return "\n".join(self._generate_routes(cfg, entity_name, entity))

    # --- internal ---

    def _generate_routes(
        self, cfg: ADLConfig, name: str, entity: EntityDef
    ) -> List[str]:
        snake = to_snake_case(name)
        plural = f"{snake}s"
        tag = name

        pagination = entity_has_pagination(cfg, name)
        entity_has_service(cfg, name)

        lines: List[str] = [
            f"# --- {name} Routes ---",
            f'{snake}_router = APIRouter(prefix="/{plural}", tags=["{tag}"])',
            "",
        ]

        # In-memory store for generated routes (real app would use DI)
        lines.append(f"_{plural}_db: list = []")
        lines.append("")

        # CREATE
        lines.extend(
            [
                f"@{snake}_router.post('/', status_code=201)",
                f"async def create_{snake}(data: dict):",
                f'    """Create a new {name}."""',
                f"    _{plural}_db.append(data)",
                f"    return data",
                "",
            ]
        )

        # LIST (with pagination if configured)
        if pagination:
            lines.extend(
                [
                    f"@{snake}_router.get('/')",
                    f"async def list_{plural}(",
                    f"    page: int = Query(1, ge=1),",
                    f"    size: int = Query(20, ge=1, le=100),",
                    f"):",
                    f'    """List {name}s with {pagination} pagination."""',
                    f"    start = (page - 1) * size",
                    f"    end = start + size",
                    f"    items = _{plural}_db[start:end]",
                    f"    return {{",
                    f'        "items": items,',
                    f'        "page": page,',
                    f'        "size": size,',
                    f'        "total": len(_{plural}_db),',
                    f"    }}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"@{snake}_router.get('/')",
                    f"async def list_{plural}(",
                    f"    skip: int = Query(0, ge=0),",
                    f"    limit: int = Query(100, ge=1, le=1000),",
                    f"):",
                    f'    """List all {name}s."""',
                    f"    return _{plural}_db[skip:skip + limit]",
                    "",
                ]
            )

        # GET by index
        lines.extend(
            [
                f"@{snake}_router.get('/{{item_id}}')",
                f"async def get_{snake}(item_id: int):",
                f'    """Get {name} by ID."""',
                f"    if item_id < 0 or item_id >= len(_{plural}_db):",
                f'        raise HTTPException(404, "{name} not found")',
                f"    return _{plural}_db[item_id]",
                "",
            ]
        )

        # DELETE
        lines.extend(
            [
                f"@{snake}_router.delete('/{{item_id}}', status_code=204)",
                f"async def delete_{snake}(item_id: int):",
                f'    """Delete {name} by ID."""',
                f"    if item_id < 0 or item_id >= len(_{plural}_db):",
                f'        raise HTTPException(404, "{name} not found")',
                f"    _{plural}_db.pop(item_id)",
                "",
            ]
        )

        return lines
