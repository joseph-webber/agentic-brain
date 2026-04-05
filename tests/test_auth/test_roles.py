from __future__ import annotations

import pytest

from agentic_brain.auth.constants import (
    ROLE_ADMIN,
    ROLE_ANONYMOUS,
    ROLE_MANAGER,
    ROLE_USER,
)
from agentic_brain.auth.context import (
    SecurityContextManager,
    current_user,
    get_authorities,
    has_any_authority,
    has_authority,
    has_role,
    require_authenticated,
    require_role,
)
from agentic_brain.auth.models import AuthMethod, SecurityContext, Token, User


def test_user_has_role_accepts_prefixed_and_unprefixed_values(auth_user):
    assert auth_user.has_role("ADMIN") is True
    assert auth_user.has_role("ROLE_ADMIN") is True
    assert auth_user.has_role("MANAGER") is False


def test_user_has_any_authority_returns_true_on_first_match(auth_user):
    assert auth_user.has_any_authority("NOPE", "USER_VIEW") is True
    assert auth_user.has_any_authority("NOPE", "ALSO_NOPE") is False


def test_user_has_all_authorities_requires_every_permission(auth_user):
    assert auth_user.has_all_authorities("USER_VIEW", "USER_EDIT") is True
    assert auth_user.has_all_authorities("USER_VIEW", "USER_DELETE") is False


def test_security_context_anonymous_is_not_authenticated():
    anonymous = SecurityContext.anonymous()

    assert anonymous.authenticated is False
    assert anonymous.auth_method == AuthMethod.ANONYMOUS
    assert anonymous.user is not None
    assert anonymous.user.login == "anonymousUser"
    assert anonymous.user.authorities == [ROLE_ANONYMOUS]


def test_security_context_from_user_marks_context_authenticated(auth_user):
    token = Token(access_token="access", token_type="Bearer")

    context = SecurityContext.from_user(
        auth_user, token=token, auth_method=AuthMethod.JWT
    )

    assert context.authenticated is True
    assert context.user == auth_user
    assert context.token == token
    assert context.auth_method == AuthMethod.JWT


def test_context_helpers_reflect_current_user_authorities(auth_user):
    with SecurityContextManager(auth_user):
        assert current_user() == auth_user
        assert has_role("ADMIN") is True
        assert has_authority("USER_VIEW") is True
        assert has_any_authority("OTHER", "USER_EDIT") is True
        assert get_authorities() == auth_user.authorities


def test_require_authenticated_returns_current_user(auth_user):
    with SecurityContextManager(auth_user):
        assert require_authenticated() == auth_user


def test_require_authenticated_raises_when_no_context_is_set():
    with pytest.raises(ValueError, match="Authentication required"):
        require_authenticated()


def test_require_role_returns_current_user_when_role_is_present(auth_user):
    with SecurityContextManager(auth_user):
        assert require_role("ADMIN") == auth_user
        assert require_role("ROLE_ADMIN") == auth_user


def test_require_role_raises_when_role_is_missing():
    user = User(login="viewer", authorities=[ROLE_USER, "USER_VIEW"])

    with SecurityContextManager(user):
        with pytest.raises(ValueError, match="Role 'ADMIN' required"):
            require_role("ADMIN")


def test_admin_role_does_not_implicitly_grant_other_roles():
    user = User(login="admin", authorities=[ROLE_ADMIN])

    with SecurityContextManager(user):
        assert has_role("ADMIN") is True
        assert has_role("USER") is False
        assert has_role("MANAGER") is False


def test_role_upgrade_takes_effect_after_authority_is_added():
    user = User(login="operator", authorities=[ROLE_USER])

    with SecurityContextManager(user):
        assert has_role("ADMIN") is False
        user.authorities.append(ROLE_ADMIN)
        assert has_role("ADMIN") is True


def test_role_downgrade_removes_access_immediately():
    user = User(login="manager", authorities=[ROLE_USER, ROLE_ADMIN, ROLE_MANAGER])

    with SecurityContextManager(user):
        assert has_role("ADMIN") is True
        user.authorities.remove(ROLE_ADMIN)
        assert has_role("ADMIN") is False
        assert has_role("MANAGER") is True


def test_full_name_falls_back_to_login_when_names_missing():
    user = User(login="fallback-user", authorities=[ROLE_USER])

    assert user.full_name == "fallback-user"


def test_full_name_joins_first_and_last_name():
    user = User(
        login="named-user",
        first_name="Named",
        last_name="Person",
        authorities=[ROLE_USER],
    )

    assert user.full_name == "Named Person"
