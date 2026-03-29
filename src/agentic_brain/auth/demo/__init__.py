# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Demo Authentication Module - JHipster Style.

Provides simple SQLite in-memory auth for development and testing.
Follows JHipster patterns for user management and JWT tokens.

Demo Users (like JHipster):
- admin/admin - ROLE_ADMIN, ROLE_USER
- user/user - ROLE_USER
- guest/(empty) - ROLE_GUEST (no password required)

Dev Mode:
- /api/login-hints returns demo credentials
- Demo users are created automatically

Prod Mode:
- /api/login-hints returns 404
- Demo users can be disabled
"""

from agentic_brain.auth.demo.simple_auth import (
    DemoAuthService,
    DemoUser,
    LoginHints,
    LoginRequest,
    TokenResponse,
    cli_login,
    cli_show_hints,
    create_demo_router,
    get_current_user,
    get_demo_auth_service,
    is_dev_mode,
)

__all__ = [
    "DemoAuthService",
    "DemoUser",
    "LoginHints",
    "LoginRequest",
    "TokenResponse",
    "cli_login",
    "cli_show_hints",
    "create_demo_router",
    "get_current_user",
    "get_demo_auth_service",
    "is_dev_mode",
]
