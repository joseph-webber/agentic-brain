# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Shared fixtures for security tests."""

from __future__ import annotations

import pytest

from agentic_brain.security.roles import SecurityRole
from agentic_brain.security.guards import SecurityGuard


@pytest.fixture
def admin_guard():
    """Create an ADMIN security guard."""
    return SecurityGuard(SecurityRole.FULL_ADMIN)


@pytest.fixture
def user_guard():
    """Create a USER security guard."""
    return SecurityGuard(SecurityRole.USER)


@pytest.fixture
def guest_guard():
    """Create a GUEST security guard."""
    return SecurityGuard(SecurityRole.GUEST)


@pytest.fixture
def all_guards(admin_guard, user_guard, guest_guard):
    """Return all three guard types."""
    return {
        "admin": admin_guard,
        "user": user_guard,
        "guest": guest_guard,
    }
