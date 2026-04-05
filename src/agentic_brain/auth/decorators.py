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

"""
Authorization decorators for FastAPI endpoints.

Provides role-based and authority-based access control decorators
following JHipster patterns.

Example:
    @app.get("/admin")
    @require_role("ADMIN")
    async def admin_endpoint():
        return {"message": "Admin only"}

    @app.get("/users")
    @require_authority("USER_VIEW")
    async def list_users():
        return {"users": []}
"""

from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agentic_brain.auth.context import (
    get_security_context,
)
from agentic_brain.auth.context import (
    has_any_authority as ctx_has_any_authority,
)
from agentic_brain.auth.context import (
    has_authority as ctx_has_authority,
)
from agentic_brain.auth.context import (
    has_role as ctx_has_role,
)
from agentic_brain.auth.context import (
    is_authenticated as ctx_is_authenticated,
)
from agentic_brain.auth.models import User

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# HTTP Bearer scheme for extracting tokens
http_bearer = HTTPBearer(auto_error=False)


class RoleChecker:
    """
    Dependency for checking user roles.

    Can be used as a FastAPI dependency:
        @app.get("/admin", dependencies=[Depends(RoleChecker(["ADMIN"]))])
        async def admin_endpoint():
            pass
    """

    def __init__(self, required_roles: list[str]):
        """Initialize with required roles."""
        self.required_roles = required_roles

    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    ) -> User:
        """Check if the current user has any of the required roles."""
        ctx = get_security_context()

        if ctx is None or not ctx.authenticated or ctx.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user has any of the required roles
        has_role = any(ctx.user.has_role(role) for role in self.required_roles)

        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(self.required_roles)}",
            )

        return ctx.user


class AuthorityChecker:
    """
    Dependency for checking user authorities.

    Can be used as a FastAPI dependency:
        @app.get("/users", dependencies=[Depends(AuthorityChecker(["USER_VIEW"]))])
        async def list_users():
            pass
    """

    def __init__(self, required_authorities: list[str], require_all: bool = False):
        """
        Initialize with required authorities.

        Args:
            required_authorities: List of authorities to check.
            require_all: If True, user must have ALL authorities. If False, any one.
        """
        self.required_authorities = required_authorities
        self.require_all = require_all

    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    ) -> User:
        """Check if the current user has the required authorities."""
        ctx = get_security_context()

        if ctx is None or not ctx.authenticated or ctx.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if self.require_all:
            has_auth = ctx.user.has_all_authorities(*self.required_authorities)
        else:
            has_auth = ctx.user.has_any_authority(*self.required_authorities)

        if not has_auth:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required authorities: {', '.join(self.required_authorities)}",
            )

        return ctx.user


class AuthenticationChecker:
    """
    Dependency that just checks authentication (no role/authority requirements).

    Can be used as a FastAPI dependency:
        @app.get("/profile", dependencies=[Depends(AuthenticationChecker())])
        async def get_profile():
            pass
    """

    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    ) -> User:
        """Check if the current user is authenticated."""
        ctx = get_security_context()

        if ctx is None or not ctx.authenticated or ctx.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return ctx.user


def require_role(*roles: str) -> Callable[[F], F]:
    """
    Decorator that requires the user to have one of the specified roles.

    Args:
        roles: One or more roles (can include or omit ROLE_ prefix).

    Returns:
        Decorated function.

    Example:
        @require_role("ADMIN")
        async def admin_only():
            pass

        @require_role("ADMIN", "MODERATOR")
        async def admin_or_mod():
            pass
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not ctx_is_authenticated():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check if user has any of the required roles
            has_role = any(ctx_has_role(role) for role in roles)

            if not has_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {', '.join(roles)}",
                )

            return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def require_authority(*authorities: str, require_all: bool = False) -> Callable[[F], F]:
    """
    Decorator that requires the user to have specified authorities.

    Args:
        authorities: One or more authorities to require.
        require_all: If True, user must have ALL authorities. Default is any.

    Returns:
        Decorated function.

    Example:
        @require_authority("USER_VIEW")
        async def view_users():
            pass

        @require_authority("USER_CREATE", "USER_DELETE", require_all=True)
        async def manage_users():
            pass
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not ctx_is_authenticated():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if require_all:
                has_auth = all(ctx_has_authority(auth) for auth in authorities)
            else:
                has_auth = ctx_has_any_authority(*authorities)

            if not has_auth:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required authorities: {', '.join(authorities)}",
                )

            return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def require_authenticated(func: F) -> F:
    """
    Decorator that requires the user to be authenticated.

    No role or authority checks, just authentication.

    Example:
        @require_authenticated
        async def protected_endpoint():
            pass
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not ctx_is_authenticated():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await func(*args, **kwargs)

    return wrapper  # type: ignore


def allow_anonymous(func: F) -> F:
    """
    Decorator that explicitly marks an endpoint as allowing anonymous access.

    This is mostly for documentation purposes - it doesn't prevent
    authentication from happening, just doesn't require it.

    Example:
        @allow_anonymous
        async def public_endpoint():
            pass
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # No authentication check - just pass through
        return await func(*args, **kwargs)

    # Mark as allowing anonymous for introspection
    wrapper.__allow_anonymous__ = True  # type: ignore

    return wrapper  # type: ignore


def pre_authorize(expression: str) -> Callable[[F], F]:
    """
    Decorator with Spring Security-style expression evaluation.

    Supports basic expressions for role and authority checks.

    Args:
        expression: Security expression like "hasRole('ADMIN')" or
                   "hasAuthority('USER_VIEW')".

    Returns:
        Decorated function.

    Example:
        @pre_authorize("hasRole('ADMIN') or hasAuthority('USER_MANAGEMENT')")
        async def manage_users():
            pass
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not ctx_is_authenticated():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Parse and evaluate the expression
            if not _evaluate_security_expression(expression):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied by expression: {expression}",
                )

            return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def _evaluate_security_expression(expression: str) -> bool:
    """
    Evaluate a Spring Security-style expression.

    Supports:
    - hasRole('ROLE_NAME')
    - hasAuthority('AUTHORITY')
    - hasAnyRole('ROLE1', 'ROLE2')
    - hasAnyAuthority('AUTH1', 'AUTH2')
    - isAuthenticated()
    - and, or operators

    Args:
        expression: The security expression to evaluate.

    Returns:
        True if the expression evaluates to True.
    """
    import re

    expr = expression.strip()

    # Handle 'and' expressions first (higher precedence)
    # Use a simple split that doesn't break function calls
    if " and " in expr:
        # Split carefully to avoid splitting inside parentheses
        parts = _split_expression(expr, " and ")
        if len(parts) > 1:
            return all(_evaluate_security_expression(p.strip()) for p in parts)

    # Handle 'or' expressions
    if " or " in expr:
        parts = _split_expression(expr, " or ")
        if len(parts) > 1:
            return any(_evaluate_security_expression(p.strip()) for p in parts)

    # Handle isAuthenticated()
    if expr == "isAuthenticated()":
        return ctx_is_authenticated()

    # Handle hasRole('...')
    role_match = re.match(r"hasRole\(['\"](.+?)['\"]\)", expr)
    if role_match:
        return ctx_has_role(role_match.group(1))

    # Handle hasAuthority('...')
    auth_match = re.match(r"hasAuthority\(['\"](.+?)['\"]\)", expr)
    if auth_match:
        return ctx_has_authority(auth_match.group(1))

    # Handle hasAnyRole('...', '...')
    any_role_match = re.match(r"hasAnyRole\((.+)\)", expr)
    if any_role_match:
        roles = re.findall(r"['\"]([^'\"]+)['\"]", any_role_match.group(1))
        return any(ctx_has_role(r) for r in roles)

    # Handle hasAnyAuthority('...', '...')
    any_auth_match = re.match(r"hasAnyAuthority\((.+)\)", expr)
    if any_auth_match:
        auths = re.findall(r"['\"]([^'\"]+)['\"]", any_auth_match.group(1))
        return ctx_has_any_authority(*auths)

    # Unknown expression - deny by default
    return False


def _split_expression(expr: str, delimiter: str) -> list[str]:
    """
    Split expression by delimiter, respecting parentheses.

    Args:
        expr: The expression to split.
        delimiter: The delimiter to split on.

    Returns:
        List of parts.
    """
    parts = []
    current = []
    depth = 0
    i = 0

    while i < len(expr):
        # Check for delimiter at current position (when not inside parens)
        if depth == 0 and expr[i : i + len(delimiter)] == delimiter:
            parts.append("".join(current))
            current = []
            i += len(delimiter)
            continue

        char = expr[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1

        current.append(char)
        i += 1

    if current:
        parts.append("".join(current))

    return parts
    return False


# Dependency instances for common use cases
require_admin = RoleChecker(["ADMIN"])
require_user = RoleChecker(["USER"])
require_admin_or_user = RoleChecker(["ADMIN", "USER"])
authenticated = AuthenticationChecker()
