# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""OpenAPI 3.0 schema generation for Agentic Brain APIs.

This module provides comprehensive OpenAPI documentation generation with:
- Full schema generation from Pydantic models
- Swagger UI integration
- ReDoc integration
- Interactive API documentation
- Machine-readable schema exports

Features:
    - Automatic endpoint discovery and documentation
    - Request/response schema inference
    - Security scheme documentation (Bearer tokens)
    - Rate limit header documentation
    - Example requests and responses
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

logger = logging.getLogger(__name__)


class OpenAPIGenerator:
    """Generate OpenAPI 3.0 schemas for Agentic Brain APIs."""

    def __init__(self, app: FastAPI):
        """Initialize OpenAPI generator.

        Args:
            app: FastAPI application instance
        """
        self.app = app

    def generate_schema(self) -> dict[str, Any]:
        """Generate complete OpenAPI 3.0 schema.

        Returns:
            OpenAPI 3.0 specification dictionary

        Example:
            >>> from agentic_brain.api.server import app
            >>> generator = OpenAPIGenerator(app)
            >>> schema = generator.generate_schema()
            >>> print(json.dumps(schema, indent=2))
        """
        schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            routes=self.app.routes,
        )

        # Enhance schema with custom components
        schema["components"] = schema.get("components", {})
        schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Bearer token authentication",
            }
        }

        # Add rate limiting headers to all responses
        schema["components"]["headers"] = {
            "X-RateLimit-Limit": {
                "description": "The number of allowed requests per minute",
                "schema": {"type": "integer"},
            },
            "X-RateLimit-Remaining": {
                "description": "The number of requests left for the time window",
                "schema": {"type": "integer"},
            },
            "X-RateLimit-Reset": {
                "description": "The UTC epoch seconds when the rate limit window resets",
                "schema": {"type": "integer"},
            },
        }

        return schema

    def get_schema_json(self) -> str:
        """Get OpenAPI schema as JSON string.

        Returns:
            JSON string representation of OpenAPI schema
        """
        schema = self.generate_schema()
        return json.dumps(schema, indent=2)

    def save_schema(self, filepath: str) -> None:
        """Save OpenAPI schema to file.

        Args:
            filepath: Path to save OpenAPI schema JSON

        Example:
            >>> generator = OpenAPIGenerator(app)
            >>> generator.save_schema("/path/to/openapi.json")
        """
        schema = self.generate_schema()
        with open(filepath, "w") as f:
            json.dump(schema, f, indent=2)
        logger.info(f"OpenAPI schema saved to {filepath}")


def setup_swagger_ui(app: FastAPI, title: str = "Swagger UI") -> None:
    """Setup custom Swagger UI with enhanced styling.

    Args:
        app: FastAPI application instance
        title: Browser title for Swagger UI

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> setup_swagger_ui(app)
    """
    from fastapi.openapi.docs import get_swagger_ui_html

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui():
        """Serve custom Swagger UI."""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - {title}",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.css",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.bundle.js",
            swagger_ui_parameters={
                "syntaxHighlight": "monokai",
                "theme": "dark",
                "displayOperationId": True,
                "filter": True,
                "tryItOutEnabled": True,
                "requestSnippetsEnabled": True,
            },
        )


def setup_redoc(app: FastAPI, title: str = "ReDoc") -> None:
    """Setup ReDoc for static API documentation.

    Args:
        app: FastAPI application instance
        title: Browser title for ReDoc

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> setup_redoc(app)
    """
    from fastapi.openapi.docs import get_redoc_html

    @app.get("/redoc", include_in_schema=False)
    async def redoc():
        """Serve ReDoc documentation."""
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - {title}",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js",
            redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )


def document_endpoint(
    method: str,
    path: str,
    summary: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Generate documentation metadata for an endpoint.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: URL path for the endpoint
        summary: Short description of what the endpoint does
        description: Detailed description of the endpoint
        tags: List of OpenAPI tags for grouping

    Returns:
        Documentation metadata dictionary

    Example:
        >>> docs = document_endpoint(
        ...     method="POST",
        ...     path="/chat",
        ...     summary="Send a chat message",
        ...     tags=["chat"]
        ... )
    """
    return {
        "method": method,
        "path": path,
        "summary": summary,
        "description": description or summary,
        "tags": tags or [],
    }


def generate_openapi_from_docstrings(module: object) -> dict[str, Any]:
    """Generate OpenAPI documentation from module docstrings.

    Scans a module for public API functions and generates OpenAPI
    documentation from their docstrings.

    Args:
        module: Python module to scan

    Returns:
        Dictionary of endpoint documentation

    Example:
        >>> from agentic_brain import api
        >>> docs = generate_openapi_from_docstrings(api)
    """
    from inspect import getmembers, isfunction

    docs = {}

    for name, obj in getmembers(module, isfunction):
        if name.startswith("_"):
            continue

        docstring = obj.__doc__
        if not docstring:
            continue

        # Parse docstring for OpenAPI metadata
        lines = docstring.split("\n")
        summary = lines[0].strip() if lines else ""

        if summary:
            docs[name] = {
                "name": name,
                "summary": summary,
                "docstring": docstring,
            }

    return docs


class OpenAPIDocumenter:
    """Helper class for adding structured documentation to endpoints."""

    @staticmethod
    def format_schema_table(schema_dict: dict[str, Any]) -> str:
        """Format Pydantic schema as markdown table.

        Args:
            schema_dict: Pydantic schema dictionary

        Returns:
            Markdown-formatted table

        Example:
            >>> schema = {"properties": {"id": {"type": "string"}}}
            >>> table = OpenAPIDocumenter.format_schema_table(schema)
        """
        lines = ["| Field | Type | Description |", "|-------|------|-------------|"]

        properties = schema_dict.get("properties", {})
        for field_name, field_info in properties.items():
            field_type = field_info.get("type", "object")
            description = field_info.get("description", "")
            lines.append(f"| {field_name} | {field_type} | {description} |")

        return "\n".join(lines)

    @staticmethod
    def format_example(name: str, code: str, language: str = "python") -> str:
        """Format code example for documentation.

        Args:
            name: Example name/title
            code: Example code
            language: Programming language

        Returns:
            Markdown-formatted code block

        Example:
            >>> example = OpenAPIDocumenter.format_example(
            ...     "Send message",
            ...     'response = await client.chat("Hello")',
            ...     language="python"
            ... )
        """
        return f"### {name}\n\n```{language}\n{code}\n```\n"


def create_api_reference(app: FastAPI) -> str:
    """Generate markdown API reference from FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        Markdown string with API reference

    Example:
        >>> from agentic_brain.api.server import app
        >>> reference = create_api_reference(app)
    """
    lines = ["# API Reference\n"]

    for route in app.routes:
        if not hasattr(route, "methods"):
            continue

        for method in route.methods:
            if method == "OPTIONS":
                continue

            path = route.path
            summary = getattr(route, "summary", path)
            tags = getattr(route, "tags", [])

            lines.append(f"## {method} {path}")
            lines.append(f"\n{summary}\n")

            if tags:
                lines.append(f"**Tags:** {', '.join(tags)}\n")

    return "\n".join(lines)
