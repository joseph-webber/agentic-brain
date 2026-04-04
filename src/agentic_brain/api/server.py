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

from __future__ import annotations

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
import os
import threading
from datetime import UTC
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from .. import __version__

from ..dashboard import create_dashboard_router
from .audit import AUDIT_ENABLED, AuditLogger, AuditMiddleware
from .middleware import SecurityHeadersMiddleware, setup_cors, setup_exception_handlers
from .redis_health import get_redis_health_checker
from .routes import lifespan, register_routes, session_messages, sessions
from .websocket import register_websocket_routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(
    title: str = "Agentic Brain API",
    version: str = __version__,
    description: str = "Multi-LLM orchestration platform with GraphRAG, Unified Brain, and real-time chat",
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
    - Redis health checking on startup (BULLETPROOF)

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
    # BULLETPROOF: Check Redis on startup
    logger.info("🔴 Checking Redis availability...")
    redis_checker = get_redis_health_checker()
    is_test_environment = (
        os.getenv("TESTING", "").lower() in {"1", "true", "yes"}
        or os.getenv("CI", "").lower() in {"1", "true", "yes"}
        or "PYTEST_CURRENT_TEST" in os.environ
    )

    if is_test_environment:
        logger.info("Test environment detected — skipping Redis connectivity check")
    else:
        is_available, status_msg = redis_checker.check_redis_available()
        if not is_available:
            logger.warning(f"⚠️  Redis not available: {status_msg}")
            logger.info("Attempting to auto-start Redis in background...")

            def _bg_start():
                if redis_checker.try_auto_start_redis():
                    logger.info("✅ Redis auto-started successfully")
                else:
                    logger.warning(
                        "⚠️  Could not auto-start Redis. "
                        "Start manually with: docker-compose -f docker-compose-redis.yml up -d"
                    )

            threading.Thread(
                target=_bg_start, daemon=True, name="redis-autostart"
            ).start()
        else:
            logger.info(f"✅ Redis is available: {status_msg}")

    app = FastAPI(
        title=title,
        version=version,
        description=description,
        docs_url=None,  # Disabled for custom theme
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "chat", "description": "Real-time chat and messaging"},
            {"name": "rag", "description": "GraphRAG and knowledge retrieval"},
            {"name": "llm", "description": "LLM routing and orchestration"},
            {"name": "bots", "description": "Inter-bot communication"},
            {"name": "health", "description": "System health and monitoring"},
        ],
        lifespan=lifespan,
    )

    # Mount static files for custom Swagger UI theme
    static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")
    else:
        logger.warning(
            f"Static directory not found at {static_path}, custom theme disabled"
        )

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_css_url="/static/swagger-ui.css",
        )

    # Store version and start time for health check endpoint
    app.version = version
    from datetime import datetime, timezone

    app._start_time = datetime.now(UTC)

    # Store Redis health checker for route access
    app.state.redis_health_checker = redis_checker

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
