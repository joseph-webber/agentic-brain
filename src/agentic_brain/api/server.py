# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
FastAPI Server for Agentic Brain Chatbot API
==============================================

This module provides a complete REST API and WebSocket interface for the Agentic Brain
chatbot system. It orchestrates routes, middleware, and WebSocket handlers.

Example:
    Start the server:
        >>> from agentic_brain.api.server import run_server
        >>> run_server(host="0.0.0.0", port=8000)
    
    Or with uvicorn:
        >>> uvicorn agentic_brain.api.server:app --host 0.0.0.0 --port 8000

Author: Joseph Webber
License: GPL-3.0-or-later
"""

import logging
from typing import Optional, List

from fastapi import FastAPI
import uvicorn

from .middleware import setup_cors, setup_exception_handlers
from .routes import register_routes, lifespan
from .websocket import register_websocket_routes
from ..dashboard import create_dashboard_router
from .routes import sessions, session_messages

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(
    title: str = "Agentic Brain Chatbot API",
    version: str = "1.0.0",
    description: str = "FastAPI server for agentic-brain chatbot with real-time chat support",
    cors_origins: Optional[List[str]] = None,
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
        cors_origins (Optional[List[str]]): List of allowed CORS origins. If None,
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
    
    # Store version for health check endpoint
    app.version = version
    
    # Setup middleware
    setup_cors(app, cors_origins)
    setup_exception_handlers(app)
    
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
