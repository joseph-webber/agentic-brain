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
Middleware components for the Agentic Brain Chat API.

This module contains middleware for request/response logging, error handling,
CORS configuration, and security headers.
"""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Adds the following security headers:
    - X-Content-Type-Options: nosniff - Prevents MIME type sniffing
    - X-Frame-Options: DENY - Prevents clickjacking
    - X-XSS-Protection: 1; mode=block - Enables XSS filter
    - Strict-Transport-Security: max-age=31536000 - Enforces HTTPS
    - Content-Security-Policy: default-src 'self' - Restricts content sources
    - Referrer-Policy: strict-origin-when-cross-origin - Controls referrer info
    - Permissions-Policy: geolocation=(), microphone=() - Restricts features
    """

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS filter (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS (1 year)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Content Security Policy - restrict content sources
        # Use CSP_POLICY env var for custom policy, or CSP_STRICT=true for no unsafe-inline
        csp_policy = os.environ.get("CSP_POLICY")
        if csp_policy:
            response.headers["Content-Security-Policy"] = csp_policy
        elif os.environ.get("CSP_STRICT", "false").lower() == "true":
            # Strict mode: no unsafe-inline (requires external stylesheets)
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )
        else:
            # Default: allow inline styles for dashboard (production should externalize CSS)
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response


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


def setup_cors(app: FastAPI, cors_origins: list[str | None] = None):
    """Configure CORS middleware.

    Args:
        app: FastAPI application
        cors_origins: List of allowed CORS origins. Can be set via CORS_ORIGINS env var
                      as comma-separated list (e.g., "http://localhost:3000,http://example.com")
    """
    if cors_origins is None:
        # Check for environment variable
        env_origins = os.getenv("CORS_ORIGINS")
        if env_origins:
            cors_origins = [origin.strip() for origin in env_origins.split(",")]
        else:
            # Default development origins
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
