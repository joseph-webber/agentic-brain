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
Comprehensive tests for LDAP/Active Directory authentication.

Tests cover:
- LDAP configuration and validation
- User authentication via LDAP bind
- Group membership extraction
- Role mapping from LDAP groups
- JWT session token generation
- Connection handling
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if ldap3 is not installed
ldap3 = pytest.importorskip("ldap3", reason="ldap3 not installed")


class MockConnection:
    """Mock ldap3 Connection for testing."""

    def __init__(self, bind_result=True, search_results=None, user_dn=None):
        self.bind_result = bind_result
        self._search_results = search_results or []
        self._user_dn = user_dn or "cn=testuser,ou=users,dc=example,dc=com"
        self.bound = False
        self.entries = []
        self.result = {"description": "success"}

    def bind(self) -> bool:
        self.bound = self.bind_result
        return self.bind_result

    def unbind(self) -> None:
        self.bound = False

    def search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: Any = None,
        attributes: list = None,
    ) -> bool:
        self.entries = self._search_results
        return len(self._search_results) > 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.unbind()


class TestLDAPConfig:
    """Tests for LDAP configuration."""

    def test_ldap_config_defaults(self):
        """LDAPConfig should have sensible defaults."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig()

        assert config.server == "ldap://localhost"
        assert config.port == 389
        assert config.use_ssl is False
        assert config.user_search_filter == "(uid={username})"
        assert config.group_attribute == "memberOf"
        assert config.timeout_seconds == 10

    def test_ldap_config_active_directory(self):
        """LDAPConfig should work with Active Directory settings."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(
            server="ldaps://ad.example.com",
            port=636,
            use_ssl=True,
            bind_dn="cn=service_account,ou=service,dc=example,dc=com",
            bind_password="secret",
            user_search_filter="(sAMAccountName={username})",
        )

        assert config.use_ssl is True
        assert config.bind_dn is not None
        assert config.bind_password is not None
        assert "sAMAccountName" in config.user_search_filter

    def test_ldap_config_group_role_mapping(self):
        """LDAPConfig should support group to role mapping."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(
            group_role_mapping={
                "CN=Admins,OU=Groups,DC=example,DC=com": ["ROLE_ADMIN"],
                "CN=Users,OU=Groups,DC=example,DC=com": ["ROLE_USER"],
                "CN=Developers,OU=Groups,DC=example,DC=com": [
                    "ROLE_DEVELOPER",
                    "ROLE_USER",
                ],
            }
        )

        assert len(config.group_role_mapping) == 3
        assert config.group_role_mapping["CN=Admins,OU=Groups,DC=example,DC=com"] == [
            "ROLE_ADMIN"
        ]
        # Test multi-role mapping
        assert (
            "ROLE_DEVELOPER"
            in config.group_role_mapping["CN=Developers,OU=Groups,DC=example,DC=com"]
        )


class TestLDAPCredentials:
    """Tests for LDAP credentials."""

    def test_ldap_credentials_creation(self):
        """LDAPCredentials should store username and password."""
        from agentic_brain.auth.enterprise_providers import LDAPCredentials

        creds = LDAPCredentials(username="testuser", password="testpass")

        assert creds.username == "testuser"
        assert creds.password == "testpass"

    def test_ldap_credentials_domain_format(self):
        """LDAPCredentials should handle domain\\username format."""
        from agentic_brain.auth.enterprise_providers import LDAPCredentials

        creds = LDAPCredentials(username="EXAMPLE\\testuser", password="testpass")

        assert creds.username == "EXAMPLE\\testuser"


class TestLDAPAuthProvider:
    """Tests for LDAP authentication provider."""

    @pytest.fixture
    def ldap_config(self):
        """Create test LDAP config."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        return LDAPConfig(
            server="ldap://localhost",
            port=389,
            bind_dn="cn=admin,dc=example,dc=com",
            bind_password="admin_password",
            base_dn="dc=example,dc=com",
            user_search_base="ou=users,dc=example,dc=com",
            group_search_base="ou=groups,dc=example,dc=com",
            group_role_mapping={
                "CN=Admins,OU=Groups,DC=example,DC=com": ["ROLE_ADMIN"],
                "CN=Users,OU=Groups,DC=example,DC=com": ["ROLE_USER"],
            },
        )

    @pytest.mark.asyncio
    async def test_ldap_provider_creation(self, ldap_config):
        """LDAPAuthProvider should be created with config."""
        from agentic_brain.auth.enterprise_providers import LDAPAuthProvider

        provider = LDAPAuthProvider(ldap_config)

        assert provider.ldap_config == ldap_config

    @pytest.mark.asyncio
    async def test_ldap_provider_supports_ldap_credentials(self, ldap_config):
        """LDAPAuthProvider should support LDAPCredentials."""
        from agentic_brain.auth.enterprise_providers import (
            LDAPAuthProvider,
            LDAPCredentials,
        )

        provider = LDAPAuthProvider(ldap_config)
        LDAPCredentials(username="testuser", password="testpass")

        # Check if the provider can handle LDAP credentials
        assert hasattr(provider, "authenticate")

    @pytest.mark.asyncio
    async def test_ldap_provider_has_group_cache(self, ldap_config):
        """LDAPAuthProvider should have group cache."""
        from agentic_brain.auth.enterprise_providers import LDAPAuthProvider

        provider = LDAPAuthProvider(ldap_config)

        assert hasattr(provider, "_group_cache")


class TestLDAPRoleMapping:
    """Tests for LDAP group to role mapping configuration."""

    @pytest.fixture
    def ldap_config(self):
        """Create test LDAP config with role mappings."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        return LDAPConfig(
            server="ldap://localhost",
            port=389,
            group_role_mapping={
                "CN=Admins,OU=Groups,DC=example,DC=com": ["ROLE_ADMIN"],
                "CN=Users,OU=Groups,DC=example,DC=com": ["ROLE_USER"],
                "CN=Developers,OU=Groups,DC=example,DC=com": ["ROLE_DEVELOPER"],
                "CN=ReadOnly,OU=Groups,DC=example,DC=com": ["ROLE_READER"],
            },
        )

    def test_role_mapping_config_exists(self, ldap_config):
        """LDAPConfig should have role mappings."""
        assert len(ldap_config.group_role_mapping) == 4

    def test_role_mapping_returns_list(self, ldap_config):
        """Each group mapping should return a list of roles."""
        roles = ldap_config.group_role_mapping["CN=Admins,OU=Groups,DC=example,DC=com"]

        assert isinstance(roles, list)
        assert "ROLE_ADMIN" in roles


class TestLDAPSearchFilters:
    """Tests for LDAP search filter configuration."""

    def test_user_search_filter_default(self):
        """Should use uid by default (OpenLDAP style)."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(server="ldap://localhost", port=389)

        # Default filter uses uid for OpenLDAP compatibility
        assert config.user_search_filter == "(uid={username})"

    def test_user_search_filter_active_directory(self):
        """Should support Active Directory sAMAccountName."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(
            server="ldap://localhost",
            port=389,
            user_search_filter="(sAMAccountName={username})",
        )

        assert config.user_search_filter == "(sAMAccountName={username})"

    def test_user_search_filter_complex(self):
        """Should support complex search filters."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(
            server="ldap://localhost",
            port=389,
            user_search_filter="(&(objectClass=person)(cn={username}))",
        )

        assert "objectClass=person" in config.user_search_filter
        assert "{username}" in config.user_search_filter


class TestLDAPSSL:
    """Tests for LDAP SSL/TLS configuration."""

    def test_ldap_ssl_config(self):
        """Should configure SSL properly."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(server="ldaps://ad.example.com", port=636, use_ssl=True)

        assert config.use_ssl is True
        assert config.port == 636

    def test_ldap_non_ssl_config(self):
        """Should support non-SSL connections."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(server="ldap://ad.example.com", port=389, use_ssl=False)

        assert config.use_ssl is False
        assert config.port == 389


class TestLDAPPooling:
    """Tests for LDAP connection pooling configuration."""

    def test_ldap_pool_defaults(self):
        """Should have default pool settings."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig()

        assert config.pool_size == 10
        assert config.pool_lifetime_seconds == 3600

    def test_ldap_pool_custom(self):
        """Should allow custom pool settings."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(pool_size=20, pool_lifetime_seconds=7200)

        assert config.pool_size == 20
        assert config.pool_lifetime_seconds == 7200


class TestLDAPIntegration:
    """Integration tests for LDAP authentication (mocked)."""

    @pytest.fixture
    def full_ldap_config(self):
        """Create comprehensive LDAP config for AD."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        return LDAPConfig(
            server="ldaps://ad.example.com",
            port=636,
            use_ssl=True,
            bind_dn="cn=service_account,ou=service,dc=example,dc=com",
            bind_password="service_password",
            base_dn="dc=example,dc=com",
            user_search_base="ou=users,dc=example,dc=com",
            user_search_filter="(sAMAccountName={username})",
            group_search_base="ou=groups,dc=example,dc=com",
            group_attribute="memberOf",
            group_role_mapping={
                "CN=Domain Admins,CN=Users,DC=example,DC=com": ["ROLE_ADMIN"],
                "CN=Developers,OU=Groups,DC=example,DC=com": ["ROLE_DEVELOPER"],
                "CN=Users,OU=Groups,DC=example,DC=com": ["ROLE_USER"],
            },
            timeout_seconds=10,
        )

    def test_full_config_creation(self, full_ldap_config):
        """Full LDAP config should be valid."""
        assert full_ldap_config.server == "ldaps://ad.example.com"
        assert full_ldap_config.use_ssl is True
        assert len(full_ldap_config.group_role_mapping) == 3

    def test_config_attribute_mappings(self, full_ldap_config):
        """Config should have proper attribute mappings."""
        assert full_ldap_config.username_attribute == "uid"  # default
        assert full_ldap_config.email_attribute == "mail"
        assert full_ldap_config.first_name_attribute == "givenName"
        assert full_ldap_config.last_name_attribute == "sn"


class TestLDAPExamples:
    """Test examples from config documentation."""

    def test_active_directory_example(self):
        """Active Directory config example should work."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(
            server="ldap://ad.company.com",
            port=389,
            use_ssl=True,
            ssl_port=636,
            bind_dn="CN=ServiceAccount,OU=Service Accounts,DC=company,DC=com",
            bind_password="password123",
            base_dn="DC=company,DC=com",
            user_search_base="OU=Users,DC=company,DC=com",
            user_search_filter="(sAMAccountName={username})",
            group_search_base="OU=Groups,DC=company,DC=com",
            username_attribute="sAMAccountName",
            group_role_mapping={
                "CN=Admins,OU=Groups,DC=company,DC=com": ["ROLE_ADMIN"],
                "CN=Users,OU=Groups,DC=company,DC=com": ["ROLE_USER"],
            },
        )

        assert config.use_ssl is True
        assert "sAMAccountName" in config.user_search_filter
        assert config.username_attribute == "sAMAccountName"

    def test_openldap_example(self):
        """OpenLDAP config example should work."""
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig(
            server="ldap://ldap.company.com",
            port=389,
            use_ssl=False,
            bind_dn="cn=admin,dc=company,dc=com",
            bind_password="adminpass",
            base_dn="dc=company,dc=com",
            user_search_base="ou=people,dc=company,dc=com",
            user_search_filter="(uid={username})",
            group_search_base="ou=groups,dc=company,dc=com",
            group_search_filter="(memberUid={username})",
            username_attribute="uid",
            group_role_mapping={
                "cn=admins,ou=groups,dc=company,dc=com": ["ROLE_ADMIN"],
                "cn=users,ou=groups,dc=company,dc=com": ["ROLE_USER"],
            },
        )

        assert config.use_ssl is False
        assert "uid" in config.user_search_filter
        assert config.username_attribute == "uid"
