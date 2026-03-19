# Security Policy

## Supported Versions

Security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| 0.x     | :x:                |

We recommend always using the latest version to ensure you have the most recent security updates.

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

## Questions or Concerns?

For security-related questions or concerns, contact: **security@agentic-brain.dev**

For general inquiries or support, use GitHub Issues.

---

Thank you for helping keep Agentic Brain secure!
