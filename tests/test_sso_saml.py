# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""SSO and SAML helper tests for CI.

These tests exercise the lightweight SAMLProvider and SSOProvider
abstractions without requiring any external IdP or HTTP calls.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from agentic_brain.auth.saml_provider import SAMLConfig, SAMLProvider
from agentic_brain.auth.sso_provider import OAuthProviderSettings, SSOProvider
from agentic_brain.ethics.guidelines import publish_auth_ethics_discussion


class DummyResponse:
    """Simple HTTP-like response for SSOProvider tests."""

    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:  # pragma: no cover - trivial
        return self._payload


class DummyHttpClient:
    """In-memory HTTP client that records POSTs."""

    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, data: dict[str, Any]) -> DummyResponse:
        self.requests.append((url, data))
        return DummyResponse(200, self.payload)


def _make_saml_provider() -> SAMLProvider:
    return SAMLProvider(
        SAMLConfig(
            idp_entity_id="https://idp.example.com/metadata",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="CERT",
            sp_entity_id="agentic-brain",
            sp_acs_url="https://app.example.com/auth/saml/acs",
        )
    )


def test_saml_authn_request_generation() -> None:
    """AuthnRequest XML should contain core SAML fields."""

    provider = _make_saml_provider()
    xml = provider.create_authn_request()

    assert "AuthnRequest" in xml
    assert provider.config.idp_sso_url in xml
    assert provider.config.sp_acs_url in xml
    assert provider.config.sp_entity_id in xml


def test_saml_response_validation() -> None:
    """SAML response parsing should extract NameID and attributes."""

    provider = _make_saml_provider()

    saml_response = """
    <samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                    ID="_resp1" Version="2.0">
      <saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
        https://idp.example.com/metadata
      </saml:Issuer>
      <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
        <saml:Subject>
          <saml:NameID>user@example.com</saml:NameID>
        </saml:Subject>
        <saml:AttributeStatement>
          <saml:Attribute Name="email">
            <saml:AttributeValue>user@example.com</saml:AttributeValue>
          </saml:Attribute>
          <saml:Attribute Name="role">
            <saml:AttributeValue>ROLE_USER</saml:AttributeValue>
          </saml:Attribute>
        </saml:AttributeStatement>
      </saml:Assertion>
    </samlp:Response>
    """.strip()

    result = provider.validate_response(saml_response)

    assert result["name_id"] == "user@example.com"
    assert result["attributes"]["email"] == "user@example.com"
    assert result["attributes"]["role"] == "ROLE_USER"


def test_saml_metadata_generation() -> None:
    """SP metadata XML should describe the ACS endpoint and entity ID."""

    provider = _make_saml_provider()
    xml = provider.get_metadata()

    assert "EntityDescriptor" in xml
    assert provider.config.sp_entity_id in xml
    assert provider.config.sp_acs_url in xml


def test_sso_oauth_flow() -> None:
    """SSOProvider should build auth URL and exchange code via HTTP client."""

    settings = OAuthProviderSettings(
        name="oidc",
        client_id="client-123",
        client_secret="secret-xyz",
        auth_url="https://auth.example.com/authorize",
        token_url="https://auth.example.com/token",
        userinfo_url="https://auth.example.com/userinfo",
        scope="openid email",
        redirect_uri="https://app.example.com/callback",
        issuer="https://auth.example.com/",
    )

    dummy_payload = {
        "access_token": "access-123",
        "id_token": json.dumps(
            {
                "iss": "https://auth.example.com/",
                "aud": "client-123",
                "sub": "user-1",
                "email": "user@example.com",
            }
        ),
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    client = DummyHttpClient(dummy_payload)
    sso = SSOProvider({"oidc": settings}, http_client=client)

    url = sso.get_authorization_url("oidc", state="state-abc")
    assert url.startswith(settings.auth_url)
    assert "response_type=code" in url
    assert "client_id=client-123" in url
    assert "state=state-abc" in url

    tokens = sso.exchange_code_for_token("oidc", code="auth-code")
    assert tokens["access_token"] == "access-123"
    assert client.requests  # HTTP client was used


def test_sso_token_validation() -> None:
    """validate_id_token should enforce issuer and audience checks."""

    settings = OAuthProviderSettings(
        name="google",
        client_id="client-abc",
        client_secret="secret-def",
        auth_url="https://accounts.example.com/auth",
        token_url="https://accounts.example.com/token",
        issuer="https://accounts.example.com",
    )

    sso = SSOProvider({"google": settings})

    good_token = {
        "iss": "https://accounts.example.com",
        "aud": "client-abc",
        "sub": "user-42",
    }

    claims = sso.validate_id_token("google", good_token)
    assert claims["sub"] == "user-42"

    bad_aud = {
        "iss": "https://accounts.example.com",
        "aud": "wrong-client",
    }
    with pytest.raises(ValueError):
        sso.validate_id_token("google", bad_aud)

    bad_iss = {
        "iss": "https://other.example.com",
        "aud": "client-abc",
    }
    with pytest.raises(ValueError):
        sso.validate_id_token("google", bad_iss)


def test_auth_ethics_discussion_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ethics helper should publish the expected JSON payload to Redis."""

    class StubRedis:
        def __init__(self) -> None:
            self.published: list[tuple[str, str]] = []

        def publish(self, channel: str, message: str) -> int:
            self.published.append((channel, message))
            return 1

    stub = StubRedis()

    count = publish_auth_ethics_discussion(redis_client=stub)

    assert count == 1
    assert stub.published
    channel, message = stub.published[0]
    assert channel == "agentic-brain:ethics-discussion"
    payload = json.loads(message)
    assert payload["agent"] == "gpt-sso"
    assert "privacy" in payload["topic"].lower()
    assert "password" in payload["recommendation"].lower()
