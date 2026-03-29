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

"""Tests for Firebase API authentication helpers."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import agentic_brain.auth.firebase_auth as firebase_auth_module
from agentic_brain.auth.firebase_auth import (
    FirebaseAPIAuth,
    FirebaseAuthConfig,
    FirebaseTokenClaims,
)
from agentic_brain.exceptions import AuthenticationError


@pytest.fixture
def auth_manager():
    firebase_auth_module.FIREBASE_AUTH_AVAILABLE = True
    firebase_auth_module.auth = MagicMock()
    firebase_auth_module.firebase_admin = MagicMock()
    firebase_auth_module.credentials = MagicMock()
    manager = FirebaseAPIAuth(
        FirebaseAuthConfig(project_id="demo-project", allow_anonymous=True)
    )
    manager._app = MagicMock()
    manager._initialized = True
    return manager


class TestFirebaseAPIAuth:
    def test_verify_token_success(self, auth_manager):
        future = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
        decoded = {
            "uid": "user-123",
            "email": "joseph@example.com",
            "name": "Joseph Webber",
            "iat": future - 300,
            "exp": future,
            "auth_time": future - 600,
            "firebase": {"sign_in_provider": "password"},
            "roles": ["admin", "user"],
        }
        with patch(
            "agentic_brain.auth.firebase_auth.auth.verify_id_token",
            return_value=decoded,
        ):
            claims = auth_manager.verify_token("token-123")
        assert claims.uid == "user-123"
        assert claims.email == "joseph@example.com"
        assert claims.is_anonymous is False

    def test_authenticate_bearer_token_extracts_roles(self, auth_manager):
        with patch.object(
            auth_manager,
            "verify_token",
            return_value=FirebaseTokenClaims(
                uid="user-1",
                email="user@example.com",
                name="User One",
                picture=None,
                issuer="issuer",
                audience="aud",
                issued_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                sign_in_provider="password",
                claims={"roles": ["editor"], "authorities": ["ROLE_REPORTS"]},
            ),
        ):
            result = auth_manager.authenticate_bearer_token("Bearer abc.def.ghi")
        assert result.success is True
        assert result.user is not None
        assert result.user.has_role("EDITOR")
        assert result.user.has_authority("ROLE_REPORTS")

    def test_authenticate_bearer_token_allows_anonymous(self, auth_manager):
        result = auth_manager.authenticate_bearer_token(None)
        assert result.success is True
        assert result.user is not None
        assert result.user.has_role("ANONYMOUS")

    def test_anonymous_claim_rejected_when_disabled(self):
        firebase_auth_module.FIREBASE_AUTH_AVAILABLE = True
        firebase_auth_module.auth = MagicMock()
        manager = FirebaseAPIAuth(
            FirebaseAuthConfig(project_id="demo-project", allow_anonymous=False)
        )
        manager._app = MagicMock()
        manager._initialized = True
        decoded = {
            "uid": "anon-1",
            "iat": 1,
            "exp": 2,
            "auth_time": 1,
            "firebase": {"sign_in_provider": "anonymous"},
        }
        with patch(
            "agentic_brain.auth.firebase_auth.auth.verify_id_token",
            return_value=decoded,
        ):
            with pytest.raises(AuthenticationError):
                manager.verify_token("anon-token")

    def test_require_roles_raises_for_missing_role(self, auth_manager):
        user = auth_manager.create_anonymous_user()
        with pytest.raises(PermissionError, match="ROLE_ADMIN"):
            auth_manager.require_roles(user, "admin")

    def test_user_management_helpers(self, auth_manager):
        record = MagicMock(
            uid="managed-user",
            email="managed@example.com",
            display_name="Managed User",
            photo_url=None,
            provider_id="password",
            custom_claims={"roles": ["admin"]},
        )
        with patch(
            "agentic_brain.auth.firebase_auth.auth.create_user", return_value=record
        ) as create_user:
            user = auth_manager.create_user(email="managed@example.com")
        create_user.assert_called_once()
        assert user.login == "managed@example.com"
        assert user.has_role("ADMIN")

    def test_set_user_roles_normalizes_claims(self, auth_manager):
        with patch(
            "agentic_brain.auth.firebase_auth.auth.set_custom_user_claims"
        ) as set_claims:
            auth_manager.set_user_roles(
                "user-1", ["admin", "editor"], {"tenant": "citb"}
            )
        args, kwargs = set_claims.call_args
        assert args[0] == "user-1"
        assert args[1]["roles"] == ["ROLE_ADMIN", "ROLE_EDITOR"]
        assert args[1]["tenant"] == "citb"
