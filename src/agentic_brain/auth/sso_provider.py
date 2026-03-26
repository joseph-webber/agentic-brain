# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# High-level OAuth2/OIDC SSO helper for Agentic Brain.
#
# This module provides a lightweight abstraction for common SSO providers
# (Google, Microsoft, GitHub, and generic OIDC). It focuses on:
# - Building authorization URLs
# - Exchanging authorization codes for tokens (via injected HTTP client)
# - Performing basic ID token validation (issuer + audience)
#
# It deliberately avoids hard dependencies on specific HTTP libraries so it
# can be exercised in CI with simple stubs.

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlencode

from agentic_brain.auth.config import AuthConfig, OAuth2Config, get_auth_config


@dataclass
class OAuthProviderSettings:
    """Configuration for a single OAuth2/OIDC provider."""

    name: str
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    userinfo_url: Optional[str] = None
    scope: str = "openid email profile"
    redirect_uri: Optional[str] = None
    issuer: Optional[str] = None


class SSOProvider:
    """Small facade for OAuth2/OIDC based Single Sign-On.

    The provider is intentionally minimal and easy to unit test. Callers
    are expected to inject an HTTP client with a ``post(url, data)``
    method returning an object that exposes ``status_code`` and ``json()``.
    """

    def __init__(
        self,
        providers: Mapping[str, OAuthProviderSettings],
        http_client: Optional[Any] = None,
    ) -> None:
        if not providers:
            raise ValueError("At least one SSO provider configuration is required")
        # Normalize provider keys to lowercase for lookups
        self._providers: Dict[str, OAuthProviderSettings] = {
            key.lower(): value for key, value in providers.items()
        }
        self._http_client = http_client

    def get_authorization_url(
        self,
        provider: str,
        state: str,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build an authorization URL for the given provider.

        Args:
            provider: Provider key (e.g. "google", "microsoft", "github", "oidc")
            state: Opaque state value for CSRF protection
            extra_params: Optional additional query parameters
        """

        settings = self._get_provider(provider)
        params: Dict[str, str] = {
            "response_type": "code",
            "client_id": settings.client_id,
            "redirect_uri": settings.redirect_uri or "",
            "scope": settings.scope,
            "state": state,
        }
        if extra_params:
            params.update(extra_params)
        return f"{settings.auth_url}?{urlencode(params)}"

    def exchange_code_for_token(
        self,
        provider: str,
        code: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange an authorization code for tokens.

        The exact HTTP behaviour is delegated to the injected ``http_client``.
        This method is synchronous by design so tests can stub it with a
        simple in-memory client.
        """

        if self._http_client is None:
            raise RuntimeError("HTTP client is not configured for SSOProvider")

        settings = self._get_provider(provider)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or settings.redirect_uri or "",
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
        }
        response = self._http_client.post(settings.token_url, data=data)
        status = getattr(response, "status_code", None)
        if status is not None and status >= 400:
            raise ValueError(f"Token endpoint returned status {status}")
        return response.json()

    def validate_id_token(self, provider: str, id_token: Any) -> Dict[str, Any]:
        """Perform basic issuer/audience validation on an ID token.

        The token is expected to already be decoded into a mapping or a
        JSON string. Cryptographic verification is intentionally not
        implemented here – upstream components should handle JWT
        signature checks using python-jose or PyJWT.
        """

        import json

        payload = json.loads(id_token) if isinstance(id_token, str) else dict(id_token)

        settings = self._get_provider(provider)

        # Audience may be a string or list of strings
        aud = payload.get("aud")
        if isinstance(aud, str):
            audiences = {aud}
        elif isinstance(aud, (list, tuple, set)):
            audiences = set(aud)
        else:
            audiences = set()

        if settings.client_id and settings.client_id not in audiences:
            raise ValueError("Invalid audience in ID token")

        if settings.issuer and payload.get("iss") != settings.issuer:
            raise ValueError("Invalid issuer in ID token")

        return payload

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------

    def _get_provider(self, provider: str) -> OAuthProviderSettings:
        key = provider.lower()
        if key not in self._providers:
            raise KeyError(f"Unknown SSO provider: {provider}")
        return self._providers[key]


# ----------------------------------------------------------------------
# Factory helpers
# ----------------------------------------------------------------------


def _provider_from_oauth2_config(name: str, cfg: OAuth2Config) -> OAuthProviderSettings:
    """Create a provider config from the global OAuth2 settings.

    This gives users a simple "generic OIDC" option backed by the
    ``OAUTH2_*`` environment variables already used elsewhere in
    Agentic Brain.
    """

    return OAuthProviderSettings(
        name=name,
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        auth_url=cfg.authorization_uri,
        token_url=cfg.token_uri,
        userinfo_url=cfg.userinfo_uri or None,
        scope=" ".join(cfg.scopes),
        redirect_uri=os.environ.get(
            "OAUTH2_REDIRECT_URI", "http://localhost:8000/auth/sso/oidc/callback"
        ),
        issuer=cfg.issuer_uri or None,
    )


def create_default_sso_provider(http_client: Optional[Any] = None) -> SSOProvider:
    """Create an :class:`SSOProvider` from global :class:`AuthConfig`.

    This inspects the configured OAuth2 settings and, if enabled,
    exposes a generic ``oidc`` provider that can be used for SSO flows.
    Additional convenience providers (Google, Microsoft, GitHub) can be
    layered on top by callers if desired.
    """

    import os

    config: AuthConfig = get_auth_config()
    providers: Dict[str, OAuthProviderSettings] = {}

    if (
        config.oauth2.enabled
        and config.oauth2.authorization_uri
        and config.oauth2.token_uri
    ):
        providers["oidc"] = _provider_from_oauth2_config("oidc", config.oauth2)

    # Optional: Google, Microsoft, GitHub via dedicated env vars
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if google_client_id and google_client_secret:
        providers["google"] = OAuthProviderSettings(
            name="google",
            client_id=google_client_id,
            client_secret=google_client_secret,
            auth_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scope="openid email profile",
            redirect_uri=os.environ.get(
                "GOOGLE_REDIRECT_URI",
                "http://localhost:8000/auth/sso/google/callback",
            ),
            issuer="https://accounts.google.com",
        )

    ms_client_id = os.environ.get("MICROSOFT_CLIENT_ID")
    ms_client_secret = os.environ.get("MICROSOFT_CLIENT_SECRET")
    if ms_client_id and ms_client_secret:
        tenant = os.environ.get("MICROSOFT_TENANT_ID", "common")
        base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
        providers["microsoft"] = OAuthProviderSettings(
            name="microsoft",
            client_id=ms_client_id,
            client_secret=ms_client_secret,
            auth_url=f"{base}/authorize",
            token_url=f"{base}/token",
            userinfo_url="https://graph.microsoft.com/oidc/userinfo",
            scope="openid email profile",
            redirect_uri=os.environ.get(
                "MICROSOFT_REDIRECT_URI",
                "http://localhost:8000/auth/sso/microsoft/callback",
            ),
            issuer=f"https://login.microsoftonline.com/{tenant}/v2.0",
        )

    gh_client_id = os.environ.get("GITHUB_CLIENT_ID")
    gh_client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
    if gh_client_id and gh_client_secret:
        providers["github"] = OAuthProviderSettings(
            name="github",
            client_id=gh_client_id,
            client_secret=gh_client_secret,
            auth_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            scope=os.environ.get("GITHUB_OAUTH_SCOPE", "read:user user:email"),
            redirect_uri=os.environ.get(
                "GITHUB_REDIRECT_URI",
                "http://localhost:8000/auth/sso/github/callback",
            ),
            # GitHub does not issue standard OIDC ID tokens by default; issuer
            # is left unset so :meth:`validate_id_token` only checks audience.
            issuer=None,
        )

    if not providers:
        raise RuntimeError(
            "No SSO providers are configured. Enable OAUTH2_* or provider-specific env vars."
        )

    return SSOProvider(providers, http_client=http_client)
