# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Middleware components for the Agentic Brain Chat API.

This module contains middleware for request/response logging, error handling,
and CORS configuration.
"""

import logging
from typing import Optional, List

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI):
    """Register exception handlers for the FastAPI app.
    
    Handles:
    - Pydantic validation errors
    - HTTP exceptions
    - Generic exceptions
    """
    
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request, exc):
        """Handle Pydantic validation errors."""
        logger.error(f"Validation error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation error",
                "detail": str(exc),
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            },
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        """Handle HTTP exceptions."""
        logger.warning(f"HTTP exception ({exc.status_code}): {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "detail": None,
                "status_code": exc.status_code,
            },
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        """Handle generic exceptions."""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )


def setup_cors(app: FastAPI, cors_origins: Optional[List[str]] = None):
    """Configure CORS middleware.
    
    Args:
        app: FastAPI application
        cors_origins: List of allowed CORS origins
    """
    if cors_origins is None:
        cors_origins = [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ]
    
    logger.info(f"Configuring CORS with origins: {cors_origins}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
