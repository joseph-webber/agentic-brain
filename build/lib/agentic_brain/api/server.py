# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

from __future__ import annotations

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
FastAPI Server for Agentic Brain — The Universal AI Platform
==============================================================

Production-ready REST API and WebSocket interface for AI agents with:
- GraphRAG memory (Neo4j knowledge graphs)
- Multi-tenant session management
- Real-time streaming via SSE and WebSocket
- Enterprise-grade audit logging and auth

Example:
    Start the server:
        >>> from agentic_brain.api.server import run_server
        >>> run_server(host="0.0.0.0", port=8000)

    Or with uvicorn:
        >>> uvicorn agentic_brain.api.server:app --host 0.0.0.0 --port 8000

Author: Joseph Webber
License: Apache-2.0
"""

import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI

from ..dashboard import create_dashboard_router
from .audit import AUDIT_ENABLED, AuditLogger, AuditMiddleware
from .middleware import SecurityHeadersMiddleware, setup_cors, setup_exception_handlers
from .routes import lifespan, register_routes, session_messages, sessions
from .websocket import register_websocket_routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(
    title: str = "Agentic Brain API",
    version: str = "2.11.0",
    description: str = "The Universal AI Platform — REST API and WebSocket interface for AI agents with GraphRAG memory, multi-tenant sessions, and enterprise-grade security.",
    cors_origins: list[str | None] = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application with all routes and middleware.

    Initializes a production-ready FastAPI application with:
    - CORS middleware for web frontend support
    - Exception handlers for validation and HTTP errors
    - Chat endpoints (REST and WebSocket)
    - Session management endpoints
    - Dashboard router for admin interface
    - Comprehensive API documentation (OpenAPI/Swagger)

    Args:
        title (str): API title for OpenAPI documentation
        version (str): API version for OpenAPI documentation
        description (str): API description for OpenAPI documentation
        cors_origins (List[str | None]): List of allowed CORS origins. If None,
            defaults to localhost variants (3000, 8000)

    Returns:
        FastAPI: Fully configured FastAPI application ready to be run

    Example:
        >>> app = create_app(
        ...     title="My Chat API",
        ...     version="2.0.0",
        ...     cors_origins=["https://example.com", "https://app.example.com"]
        ... )
        >>> # Run with: uvicorn agentic_brain.api.server:app
    """

    app = FastAPI(
        title=title,
        version=version,
        description=description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Store version and start time for health check endpoint
    app.version = version
    from datetime import datetime, timezone

    app._start_time = datetime.now(timezone.utc)

    # Setup middleware
    setup_cors(app, cors_origins)
    setup_exception_handlers(app)

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add audit middleware (if enabled)
    if AUDIT_ENABLED:
        audit_logger = AuditLogger()
        app.add_middleware(AuditMiddleware, audit_logger=audit_logger)
        # Store audit logger for route-level access
        app.state.audit_logger = audit_logger
        logger.info("Audit logging enabled")

    # Register route handlers
    register_routes(app)

    # Register WebSocket routes
    register_websocket_routes(app)

    # Mount dashboard
    dashboard_router = create_dashboard_router(
        sessions_dict=sessions,
        session_messages_dict=session_messages,
    )
    app.include_router(dashboard_router)

    return app


# Create the default app instance
app = create_app()


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
):
    """Run the FastAPI server.

    Args:
        host: Server host
        port: Server port
        reload: Enable auto-reload on file changes
        log_level: Logging level
    """
    uvicorn.run(
        "agentic_brain.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    run_server(reload=True)
