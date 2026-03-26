# Security Policy

<div align="center">

[![Security](https://img.shields.io/badge/Security-Enterprise_Grade-00A86B?style=for-the-badge)](./docs/SECURITY.md)
[![SOC 2](https://img.shields.io/badge/SOC_2-Type_II-FF6B35?style=for-the-badge)](./docs/COMPLIANCE.md)
[![HIPAA](https://img.shields.io/badge/HIPAA-Ready-4CAF50?style=for-the-badge)](./docs/COMPLIANCE.md)

**Enterprise-grade security for banks, hospitals, and government.**

[📖 Full Security Documentation](./docs/SECURITY.md) • [📋 Compliance Framework](./docs/COMPLIANCE.md)

</div>

---

## Supported Versions

Security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| 0.x     | :x:                |

We recommend always using the latest version to ensure you have the most recent security updates.

## Production Deployment Security

### Setting Production Secrets

**NEVER use default or example passwords in production.**

1. **Create a `.env.docker` file** (not committed to version control):
   ```bash
   cp .env.docker.example .env.docker
   ```

2. **Set secure passwords**:
   ```bash
   # Generate a secure password
   openssl rand -base64 32
   
   # Edit .env.docker
   NEO4J_PASSWORD=your_generated_secure_password
   ```

3. **Run with environment file**:
   ```bash
   docker-compose --env-file .env.docker up -d
   ```

### Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEO4J_PASSWORD` | Neo4j database password | Yes |
| `NEO4J_URI` | Neo4j connection URI | Yes (default: bolt://localhost:7687) |
| `NEO4J_USER` | Neo4j username | Yes (default: neo4j) |
| `OPENAI_API_KEY` | OpenAI API key | If using OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic API key | If using Claude |
| `OPENROUTER_API_KEY` | OpenRouter API key | If using OpenRouter |

### Docker Security Best Practices

1. **Never hardcode secrets in docker-compose.yml** - Use environment variables
2. **Use `.env` files** - Keep them out of version control (`.gitignore`)
3. **Restrict network access** - Use Docker networks to isolate services
4. **Run as non-root** - The Dockerfile creates a non-root user
5. **Limit container resources** - Set memory and CPU limits
6. **Keep images updated** - Regularly pull latest base images
7. **Scan for vulnerabilities** - Use `docker scan` or Trivy

### Security Headers

The API automatically adds these security headers to all responses:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enables XSS filter |
| `Strict-Transport-Security` | `max-age=31536000` | Enforces HTTPS |
| `Content-Security-Policy` | `default-src 'self'` | Restricts content sources |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer info |
| `Permissions-Policy` | `geolocation=(), microphone=()` | Restricts browser features |

### Input Validation

- All user inputs are validated using Pydantic models
- Cypher queries use parameterized inputs (never string concatenation)
- Session IDs are validated for format and length
- Message length is limited to prevent DoS

### Rate Limiting

- 60 requests per minute per IP address
- Automatic blocking after limit exceeded
- Rate limit counters reset every minute

## Reporting a Vulnerability

**Do not create a public GitHub issue for security vulnerabilities.** This allows time for a fix to be developed and released before public disclosure.

Instead, please report security vulnerabilities to: **security@agentic-brain.dev**

### What to Include

When reporting a vulnerability, please provide:

1. **Description**: Clear explanation of the vulnerability
2. **Type**: Classification (e.g., authentication bypass, data leak, injection, etc.)
3. **Reproduction Steps**: Detailed steps to reproduce the issue
4. **Impact**: Explanation of potential impact and severity
5. **Proof of Concept**: Optional - working example if available
6. **Suggested Fix**: Optional - if you have a proposed solution

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - **Critical**: Patch within 7 days
  - **High**: Patch within 14 days
  - **Medium**: Patch within 30 days
  - **Low**: Patched in next release cycle

### Severity Classification

- **Critical**: Remote code execution, authentication bypass, data corruption affecting integrity
- **High**: Privilege escalation, significant data exposure, service disruption
- **Medium**: Information disclosure, denial of service with workaround, minor privilege escalation
- **Low**: Minor information disclosure, edge cases affecting specific scenarios

## Security Practices

### Code Review

- All code changes require review before merging
- Security-sensitive code receives additional scrutiny
- Dependencies are regularly audited

### Dependency Management

- Dependencies are regularly updated
- Vulnerable dependencies are patched immediately
- We use tools to identify known vulnerabilities

### Testing

- Security tests are part of the test suite
- Input validation and sanitization are tested
- Authentication and authorization are tested
- Security headers are verified in tests

### Encryption

- Sensitive data at rest is encrypted
- Communication channels use TLS/HTTPS
- Cryptographic libraries are kept up to date

## Security Acknowledgments

We appreciate responsible vulnerability disclosure. Contributors who report security vulnerabilities will be:
- Credited in security advisories (unless they prefer anonymity)
- Recognized in project documentation
- Contacted before public disclosure

## Vulnerability Disclosure Timeline

1. **Day 1**: Vulnerability report received
2. **Day 2**: Initial assessment and confirmation
3. **Day 3-7**: Fix development and testing
4. **Day 8-14**: Patch release
5. **Day 15**: Public security advisory and disclosure

## Security Advisory Format

Security advisories are published in:
- GitHub Security Advisories
- Project changelog
- Mailing list (when available)

## Best Practices for Users

### Secure Configuration

- Use strong authentication credentials
- Enable encryption for sensitive data
- Restrict network access using firewalls
- Keep systems and dependencies updated

### Regular Updates

- Monitor security advisories
- Apply patches promptly
- Subscribe to release notifications
- Test updates in staging environments first

## Compliance & Certifications

Agentic Brain supports enterprise compliance requirements:

| Framework | Status | Documentation |
|-----------|--------|---------------|
| **SOC 2 Type II** | ✅ Certified | [Compliance Docs](./docs/COMPLIANCE.md) |
| **ISO 27001** | ✅ Aligned | [Compliance Docs](./docs/COMPLIANCE.md) |
| **HIPAA** | ✅ BAA Available | [Compliance Docs](./docs/COMPLIANCE.md) |
| **GDPR** | ✅ Compliant | [Compliance Docs](./docs/COMPLIANCE.md) |
| **APRA CPS 234** | ✅ Aligned | [Compliance Docs](./docs/COMPLIANCE.md) |

For compliance documentation or to request a BAA, contact: **compliance@agentic-brain.dev**

## Questions or Concerns?

For security-related questions or concerns, contact: **security@agentic-brain.dev**

For general inquiries or support, use GitHub Issues.

---

## 📖 Full Documentation

- **[Security Architecture](./docs/SECURITY.md)** — Defense in depth, zero trust, encryption
- **[Compliance Framework](./docs/COMPLIANCE.md)** — HIPAA, GDPR, SOX, APRA, SOC 2, ISO 27001
- **[Authentication Guide](./docs/AUTHENTICATION.md)** — JWT, OAuth 2.0, API keys, MFA

---

Thank you for helping keep Agentic Brain secure!
