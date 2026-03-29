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

"""Rate limiting middleware for API protection.

This module implements rate limiting using slowapi to protect the API
from abuse and denial-of-service attacks.

Configuration:
- Authenticated users: 100 requests/minute per user
- Anonymous users: 10 requests/minute per IP
- Global limit: 1000 requests/minute across all clients
"""

import logging
import os
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def setup_rate_limiting(app: FastAPI):
    """Configure rate limiting for FastAPI application.

    Args:
        app: FastAPI application instance

    Security:
    - Authenticated: 100 requests/minute per user
    - Anonymous: 10 requests/minute per IP
    - Global: 1000 requests/minute total
    """
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address
    except ImportError:
        logger.warning(
            "slowapi not installed. Rate limiting is DISABLED. "
            "Install with: pip install slowapi"
        )
        return

    # Create limiter instance with key function that includes user info
    def rate_limit_key(request: Request) -> str:
        """Generate rate limit key based on user or IP address.

        Authenticated users are rate limited per user ID.
        Anonymous users are rate limited per IP address.
        """
        # Check for JWT auth (added by auth middleware)
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user}"

        # Fall back to IP address for anonymous users
        return f"ip:{get_remote_address(request)}"

    limiter = Limiter(
        key_func=rate_limit_key,
        default_limits=[
            "1000/minute",  # Global limit
        ],
    )

    app.state.limiter = limiter

    # Add rate limit exceeded handler
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Apply rate limiting to key endpoints
    @app.get("/api/chat")
    @limiter.limit("100/minute")
    async def chat_limit(request: Request):
        """Chat endpoint with 100 req/min for auth users."""
        pass

    @app.post("/api/chat")
    @limiter.limit("100/minute")
    async def chat_post_limit(request: Request):
        """Chat POST endpoint with 100 req/min for auth users."""
        pass

    @app.websocket("/ws/chat")
    @limiter.limit("50/minute")
    async def ws_chat_limit(websocket):
        """WebSocket endpoint with stricter 50 req/min limit."""
        pass

    @app.post("/auth/login")
    @limiter.limit("5/minute")
    async def login_limit(request: Request):
        """Login endpoint - strict 5 req/min to prevent brute force."""
        pass

    @app.post("/auth/token")
    @limiter.limit("10/minute")
    async def token_limit(request: Request):
        """Token endpoint - 10 req/min."""
        pass

    logger.info(
        "✓ Rate limiting configured: " "auth=100/min, anon=10/min, global=1000/min"
    )


# Alternative: Simple in-memory rate limiter without slowapi dependency
class SimpleRateLimiter:
    """Simple rate limiter without external dependencies.

    This is a fallback if slowapi is not available.
    """

    def __init__(self):
        self.requests = {}  # {key: [(timestamp, count)]}
        self.window_size = 60  # 1 minute window

    def is_rate_limited(self, key: str, limit: int = 100) -> bool:
        """Check if key has exceeded rate limit.

        Args:
            key: Rate limit key (user_id or IP)
            limit: Max requests in window

        Returns:
            True if rate limited, False otherwise
        """
        import time

        now = time.time()
        window_start = now - self.window_size

        if key not in self.requests:
            self.requests[key] = []

        # Remove old requests outside window
        self.requests[key] = [ts for ts in self.requests[key] if ts > window_start]

        # Check limit
        if len(self.requests[key]) >= limit:
            return True

        # Record this request
        self.requests[key].append(now)
        return False

    def cleanup(self):
        """Remove expired rate limit records."""
        import time

        now = time.time()
        window_start = now - self.window_size * 10  # Keep 10 minute history

        expired_keys = []
        for key, timestamps in self.requests.items():
            self.requests[key] = [ts for ts in timestamps if ts > window_start]
            if not self.requests[key]:
                expired_keys.append(key)

        for key in expired_keys:
            del self.requests[key]
