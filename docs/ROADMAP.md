# Authentication & Security Roadmap

The following authentication providers are intentionally shipped as **documented stubs**. They are visible in the API today so enterprise customers can plan integrations, but their production implementations are under active development.

## Coming Soon

- **SAML 2.0 Single Sign-On**
  - Service Provider metadata generation, AuthNRequest creation, IdP metadata parsing, signed/encrypted assertions, and Single Logout (SLO) handling.
  - Depends on `python3-saml` or `pysaml2`, `xmlsec1`, and hardened key management for certificate rotation.
  - Estimated effort: high (multiple sprints) due to security reviews and enterprise interoperability testing.

- **Multi-Factor Authentication (MFA) Platform**
  - Time-based OTP (TOTP), SMS/email one-time codes, recovery codes, device remembering, and future FIDO2/WebAuthn support.
  - Depends on `pyotp`, `qrcode`, secure SMS/email gateways (Twilio, AWS SNS, SES), and hardware key libraries.
  - Estimated effort: high (multi-module feature) spanning cryptography, transport integrations, and UX enrollment flows.

These items surface throughout the codebase (docstrings, README, test skips) to make their status explicit until the full implementations ship.
