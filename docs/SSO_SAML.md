# SSO & SAML Authentication

Agentic Brain ships with lightweight helpers for Single Sign-On (SSO) and SAML 2.0.

## SAML 2.0

Module: `agentic_brain.auth.saml_provider`

```python
from agentic_brain.auth.saml_provider import SAMLConfig, SAMLProvider

config = SAMLConfig(
    idp_entity_id="https://idp.example.com/metadata",
    idp_sso_url="https://idp.example.com/sso",
    idp_certificate="...x509...",
    sp_entity_id="agentic-brain",
    sp_acs_url="https://app.example.com/auth/saml/acs",
)
provider = SAMLProvider(config)

authn_xml = provider.create_authn_request()
metadata_xml = provider.get_metadata()
```

API routes (FastAPI):

- `POST /auth/saml/login` – generate AuthnRequest XML
- `POST /auth/saml/acs` – validate SAMLResponse and extract attributes
- `GET /auth/saml/metadata` – SP metadata for IdP configuration

## OAuth2 / OIDC SSO

Module: `agentic_brain.auth.sso_provider`

```python
from agentic_brain.auth.sso_provider import (
    OAuthProviderSettings,
    SSOProvider,
    create_default_sso_provider,
)

# Generic OIDC provider (from OAUTH2_* env vars)
sso = create_default_sso_provider(http_client=my_http_client)
url = sso.get_authorization_url("oidc", state="xyz")

# Provider-specific (Google / Microsoft / GitHub)
providers = {
    "google": OAuthProviderSettings(
        name="google",
        client_id="...",
        client_secret="...",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scope="openid email profile",
        redirect_uri="https://app.example.com/auth/sso/google/callback",
        issuer="https://accounts.google.com",
    ),
}

sso = SSOProvider(providers, http_client=my_http_client)
auth_url = sso.get_authorization_url("google", state="abc123")

token_payload = sso.exchange_code_for_token("google", code="auth-code")
claims = sso.validate_id_token("google", token_payload.get("id_token"))
```

API routes (FastAPI):

- `GET /auth/sso/{provider}/login` – build authorization URL for provider
- `GET /auth/sso/{provider}/callback` – exchange `code` for tokens, validate ID token

## Ethics & Privacy

Authentication must never log passwords or raw tokens.

```python
from agentic_brain.ethics.guidelines import publish_auth_ethics_discussion

# Records a short reminder that auth flows respect user privacy
publish_auth_ethics_discussion()
```

Best practices:

- Use HTTPS everywhere (including redirect URIs)
- Store client secrets and keys in secure secret stores
- Do not log passwords, raw tokens, or SAML assertions
- Prefer short-lived tokens with refresh/rotation
