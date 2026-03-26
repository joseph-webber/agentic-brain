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

"""
Security context management following JHipster's SecurityUtils pattern.

Provides thread-safe and async-safe access to the current security context,
user, and authentication state.

Example:
    from agentic_brain.auth.context import current_user, is_authenticated

    if is_authenticated():
        user = current_user()
        print(f"Hello, {user.login}!")
"""

import contextvars
from typing import Optional

from agentic_brain.auth.models import AuthMethod, SecurityContext, Token, User

# Context variable for async-safe security context storage
_security_context: contextvars.ContextVar[Optional[SecurityContext]] = (
    contextvars.ContextVar("security_context", default=None)
)


def set_security_context(
    context: SecurityContext,
) -> contextvars.Token[Optional[SecurityContext]]:
    """
    Set the current security context.

    Args:
        context: The security context to set.

    Returns:
        A token that can be used to reset the context.

    Example:
        ctx = SecurityContext.from_user(user)
        token = set_security_context(ctx)
        try:
            # Do work with context
            pass
        finally:
            reset_security_context(token)
    """
    return _security_context.set(context)


def reset_security_context(token: contextvars.Token[Optional[SecurityContext]]) -> None:
    """
    Reset the security context to its previous value.

    Args:
        token: The token returned from set_security_context.
    """
    _security_context.reset(token)


def get_security_context() -> Optional[SecurityContext]:
    """
    Get the current security context.

    Returns:
        The current security context, or None if not set.
    """
    return _security_context.get()


def clear_security_context() -> None:
    """Clear the current security context."""
    _security_context.set(None)


def current_user() -> Optional[User]:
    """
    Get the currently authenticated user.

    Returns:
        The current user, or None if not authenticated.

    Example:
        user = current_user()
        if user:
            print(f"Logged in as {user.login}")
    """
    ctx = get_security_context()
    return ctx.user if ctx else None


async def current_user_async() -> Optional[User]:
    """
    Get the currently authenticated user (async version).

    Identical to current_user() but can be awaited for consistency
    in async code paths.

    Returns:
        The current user, or None if not authenticated.
    """
    return current_user()


def is_authenticated() -> bool:
    """
    Check if the current context is authenticated.

    Returns:
        True if there is an authenticated user.
    """
    ctx = get_security_context()
    return ctx is not None and ctx.authenticated


def get_current_token() -> Optional[Token]:
    """
    Get the current authentication token.

    Returns:
        The current token, or None if not available.
    """
    ctx = get_security_context()
    return ctx.token if ctx else None


def get_current_login() -> Optional[str]:
    """
    Get the current user's login name.

    Returns:
        The login name, or None if not authenticated.
    """
    user = current_user()
    return user.login if user else None


def get_current_user_id() -> Optional[str]:
    """
    Get the current user's ID.

    Returns:
        The user ID, or None if not authenticated.
    """
    user = current_user()
    return user.id if user else None


def get_auth_method() -> Optional[AuthMethod]:
    """
    Get the authentication method used.

    Returns:
        The auth method, or None if not authenticated.
    """
    ctx = get_security_context()
    return ctx.auth_method if ctx else None


def has_authority(authority: str) -> bool:
    """
    Check if the current user has a specific authority.

    Args:
        authority: The authority to check for.

    Returns:
        True if the user has the authority.

    Example:
        if has_authority("ADMIN"):
            # Admin-only code
            pass
    """
    user = current_user()
    return user is not None and user.has_authority(authority)


def has_any_authority(*authorities: str) -> bool:
    """
    Check if the current user has any of the specified authorities.

    Args:
        authorities: The authorities to check for.

    Returns:
        True if the user has at least one of the authorities.

    Example:
        if has_any_authority("ADMIN", "MODERATOR"):
            # Admin or moderator code
            pass
    """
    user = current_user()
    return user is not None and user.has_any_authority(*authorities)


def has_all_authorities(*authorities: str) -> bool:
    """
    Check if the current user has all of the specified authorities.

    Args:
        authorities: The authorities to check for.

    Returns:
        True if the user has all of the authorities.
    """
    user = current_user()
    return user is not None and user.has_all_authorities(*authorities)


def has_role(role: str) -> bool:
    """
    Check if the current user has a specific role.

    Args:
        role: The role to check for (with or without ROLE_ prefix).

    Returns:
        True if the user has the role.

    Example:
        if has_role("ADMIN"):  # Checks for ROLE_ADMIN
            pass
    """
    user = current_user()
    return user is not None and user.has_role(role)


def get_authorities() -> list[str]:
    """
    Get all authorities of the current user.

    Returns:
        List of authorities, or empty list if not authenticated.
    """
    user = current_user()
    return user.authorities if user else []


def require_authenticated() -> User:
    """
    Require that the current context is authenticated.

    Returns:
        The current user.

    Raises:
        ValueError: If not authenticated.
    """
    user = current_user()
    if user is None or not is_authenticated():
        raise ValueError("Authentication required")
    return user


def require_authority(authority: str) -> User:
    """
    Require that the current user has a specific authority.

    Args:
        authority: The required authority.

    Returns:
        The current user.

    Raises:
        ValueError: If not authenticated or lacking authority.
    """
    user = require_authenticated()
    if not user.has_authority(authority):
        raise ValueError(f"Authority '{authority}' required")
    return user


def require_role(role: str) -> User:
    """
    Require that the current user has a specific role.

    Args:
        role: The required role.

    Returns:
        The current user.

    Raises:
        ValueError: If not authenticated or lacking role.
    """
    user = require_authenticated()
    if not user.has_role(role):
        raise ValueError(f"Role '{role}' required")
    return user


class SecurityContextManager:
    """
    Context manager for temporary security context.

    Useful for running code as a specific user.

    Example:
        with SecurityContextManager(user):
            # Code runs as user
            pass
        # Original context restored
    """

    def __init__(
        self,
        user: User,
        token: Optional[Token] = None,
        auth_method: Optional[AuthMethod] = None,
    ):
        """Initialize with user to run as."""
        self.context = SecurityContext.from_user(user, token, auth_method)
        self._token: Optional[contextvars.Token[Optional[SecurityContext]]] = None

    def __enter__(self) -> SecurityContext:
        """Enter the context."""
        self._token = set_security_context(self.context)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and restore previous."""
        if self._token is not None:
            reset_security_context(self._token)

    async def __aenter__(self) -> SecurityContext:
        """Async enter."""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async exit."""
        return self.__exit__(exc_type, exc_val, exc_tb)


def run_as_user(user: User) -> SecurityContextManager:
    """
    Run code as a specific user.

    Args:
        user: The user to run as.

    Returns:
        A context manager.

    Example:
        admin = User(login="admin", authorities=["ROLE_ADMIN"])
        with run_as_user(admin):
            # Code here runs as admin
            pass
    """
    return SecurityContextManager(user)
