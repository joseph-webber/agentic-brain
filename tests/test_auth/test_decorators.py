# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from agentic_brain.auth.context import SecurityContextManager
from agentic_brain.auth.decorators import (
    AuthenticationChecker,
    AuthorityChecker,
    RoleChecker,
    _evaluate_security_expression,
    _split_expression,
    allow_anonymous,
    pre_authorize,
    require_authenticated,
    require_authority,
    require_role,
)
from agentic_brain.auth.models import User


def _admin_user() -> User:
    return User(
        login="admin",
        authorities=["ROLE_ADMIN", "ROLE_USER", "USER_VIEW", "USER_EDIT"],
    )


def _viewer_user() -> User:
    return User(login="viewer", authorities=["ROLE_USER", "USER_VIEW"])


@pytest.mark.asyncio
async def test_require_role_allows_matching_role():
    @require_role("ADMIN")
    async def endpoint():
        return "ok"

    with SecurityContextManager(_admin_user()):
        assert await endpoint() == "ok"


@pytest.mark.asyncio
async def test_require_role_allows_any_of_multiple_roles():
    @require_role("ADMIN", "MANAGER")
    async def endpoint():
        return "ok"

    with SecurityContextManager(_viewer_user()):
        with pytest.raises(HTTPException):
            await endpoint()

    manager = User(login="manager", authorities=["ROLE_MANAGER"])
    with SecurityContextManager(manager):
        assert await endpoint() == "ok"


@pytest.mark.asyncio
async def test_require_role_denies_missing_role():
    @require_role("ADMIN")
    async def endpoint():
        return "ok"

    with SecurityContextManager(_viewer_user()):
        with pytest.raises(HTTPException) as exc_info:
            await endpoint()

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_role_denies_unauthenticated_request():
    @require_role("ADMIN")
    async def endpoint():
        return "ok"

    with pytest.raises(HTTPException) as exc_info:
        await endpoint()

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_require_authority_allows_any_matching_authority():
    @require_authority("USER_DELETE", "USER_VIEW")
    async def endpoint():
        return "ok"

    with SecurityContextManager(_viewer_user()):
        assert await endpoint() == "ok"


@pytest.mark.asyncio
async def test_require_authority_require_all_allows_when_all_present():
    @require_authority("USER_VIEW", "USER_EDIT", require_all=True)
    async def endpoint():
        return "ok"

    with SecurityContextManager(_admin_user()):
        assert await endpoint() == "ok"


@pytest.mark.asyncio
async def test_require_authority_require_all_denies_partial_access():
    @require_authority("USER_VIEW", "USER_EDIT", require_all=True)
    async def endpoint():
        return "ok"

    with SecurityContextManager(_viewer_user()):
        with pytest.raises(HTTPException) as exc_info:
            await endpoint()

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_authenticated_preserves_args_and_kwargs():
    @require_authenticated
    async def endpoint(value: str, suffix: str = "!"):
        return f"{value}{suffix}"

    with SecurityContextManager(_viewer_user()):
        assert await endpoint("hello", suffix="?") == "hello?"


@pytest.mark.asyncio
async def test_require_authenticated_denies_unauthenticated_call():
    @require_authenticated
    async def endpoint():
        return "ok"

    with pytest.raises(HTTPException) as exc_info:
        await endpoint()

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_allow_anonymous_marks_function_and_allows_calls_without_context():
    @allow_anonymous
    async def endpoint():
        return "public"

    assert getattr(endpoint, "__allow_anonymous__", False) is True
    assert await endpoint() == "public"


@pytest.mark.asyncio
async def test_pre_authorize_allows_has_role_expression():
    @pre_authorize("hasRole('ADMIN')")
    async def endpoint():
        return "ok"

    with SecurityContextManager(_admin_user()):
        assert await endpoint() == "ok"


@pytest.mark.asyncio
async def test_pre_authorize_allows_complex_expression():
    @pre_authorize(
        "hasRole('MANAGER') or hasAuthority('USER_VIEW') and isAuthenticated()"
    )
    async def endpoint():
        return "ok"

    with SecurityContextManager(_viewer_user()):
        assert await endpoint() == "ok"


@pytest.mark.asyncio
async def test_pre_authorize_denies_unknown_expression():
    @pre_authorize("__import__('os').system('echo nope')")
    async def endpoint():
        return "ok"

    with SecurityContextManager(_admin_user()):
        with pytest.raises(HTTPException) as exc_info:
            await endpoint()

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


def test_evaluate_security_expression_supports_any_role_and_any_authority():
    with SecurityContextManager(_admin_user()):
        assert _evaluate_security_expression("hasAnyRole('MANAGER', 'ADMIN')") is True
        assert (
            _evaluate_security_expression("hasAnyAuthority('AUDIT', 'USER_VIEW')")
            is True
        )
        assert (
            _evaluate_security_expression("hasAnyAuthority('AUDIT', 'DELETE')") is False
        )


def test_split_expression_respects_parentheses():
    expression = "hasRole('ADMIN') or hasAuthority('USER_VIEW') and isAuthenticated()"

    assert _split_expression(expression, " or ") == [
        "hasRole('ADMIN')",
        "hasAuthority('USER_VIEW') and isAuthenticated()",
    ]


@pytest.mark.asyncio
async def test_role_checker_returns_user_for_authorized_context():
    checker = RoleChecker(["ADMIN"])

    with SecurityContextManager(_admin_user()):
        user = await checker()

    assert user.login == "admin"


@pytest.mark.asyncio
async def test_role_checker_raises_for_missing_role():
    checker = RoleChecker(["ADMIN"])

    with SecurityContextManager(_viewer_user()):
        with pytest.raises(HTTPException) as exc_info:
            await checker()

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_authority_checker_enforces_require_all():
    checker = AuthorityChecker(["USER_VIEW", "USER_EDIT"], require_all=True)

    with SecurityContextManager(_admin_user()):
        user = await checker()
        assert user.login == "admin"

    with SecurityContextManager(_viewer_user()):
        with pytest.raises(HTTPException) as exc_info:
            await checker()

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_authentication_checker_requires_authenticated_context():
    checker = AuthenticationChecker()

    with SecurityContextManager(_viewer_user()):
        user = await checker()
        assert user.login == "viewer"

    with pytest.raises(HTTPException) as exc_info:
        await checker()

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
