# Security Testing & OWASP Audit Quick Reference

## Running Security Tests

```bash
# Run all OWASP security tests
pytest tests/test_security/test_owasp.py -v

# Run specific category
pytest tests/test_security/test_owasp.py::TestA03Injection -v

# Generate coverage report
pytest tests/test_security/test_owasp.py --cov=agentic_brain.security
```

## Using the OWASP Auditor

```python
from agentic_brain.security import OWASPAuditor

# Audit entire codebase
auditor = OWASPAuditor(verbose=True)
issues = auditor.audit_codebase("src/agentic_brain")

# Get critical issues only
critical = auditor.get_critical_issues()

# Get issues by category
from agentic_brain.security import OWASPCategory
injection_issues = auditor.get_issues_by_category(
    OWASPCategory.A03_INJECTION
)

# Generate report
report = auditor.generate_report("audit_report.md")
```

## Security Utilities

### Password Hashing (Constant-Time)
```python
from agentic_brain.security import hash_password, verify_password

# Hash password securely
hashed = hash_password("user_password")

# Verify with timing attack protection
is_valid = verify_password(provided_password, hashed)
```

### Secure Token Generation
```python
from agentic_brain.security import generate_secure_token

# Generate cryptographically secure token
token = generate_secure_token(32)  # 256-bit token
```

### Constant-Time Comparison (Timing Attack Prevention)
```python
from agentic_brain.security import constant_time_compare

# Compare tokens safely (prevents timing attacks)
if constant_time_compare(user_token, stored_token):
    authenticate()
```

### JWT Secret Validation
```python
from agentic_brain.security import validate_jwt_secret

# Validates JWT_SECRET environment variable
secret = validate_jwt_secret()  # Raises ValueError if invalid
```

## OWASP Top 10 Coverage

| Issue | Status | Evidence |
|-------|--------|----------|
| A01: Broken Access Control | ✅ SECURE | RBAC implemented, session tokens, audit logging |
| A02: Cryptographic Failures | ✅ MITIGATED | hmac.compare_digest(), secure token gen, validated secrets |
| A03: Injection | ✅ MONITORED | Parameterized queries, input validation, AST scanning |
| A04: Insecure Design | ✅ SECURE | Defense in depth, secure defaults, threat model |
| A05: Misconfiguration | ✅ MONITORED | Security headers, CORS validation, env-aware errors |
| A06: Vulnerable Components | ✅ SECURED | Current dependencies, CVE monitoring |
| A07: Auth Failures | ✅ SECURE | JWT + API Key auth, session management |
| A08: Data Integrity | ✅ SECURE | Signed cookies, JSON only (no pickle) |
| A09: Logging Failures | ✅ IMPLEMENTED | Audit logger, all auth events logged |
| A10: SSRF | ✅ SECURE | URL validation, IP whitelisting, timeout protection |

## CI/CD Integration

Add to your CI/CD pipeline:

```yaml
# .github/workflows/security.yml
- name: Run Security Tests
  run: pytest tests/test_security/test_owasp.py -v

- name: OWASP Audit
  run: |
    python3 -c "
    from agentic_brain.security import OWASPAuditor, Severity
    auditor = OWASPAuditor()
    auditor.audit_codebase('src/agentic_brain')
    critical = auditor.get_critical_issues()
    if critical:
        print(f'CRITICAL: {len(critical)} issues found')
        exit(1)
    "
```

## Environment Variables

```bash
# Required for secure JWT
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Optional: Configure API keys
export API_KEYS="key1,key2,key3"
export API_KEY_ROLES="key1:ADMIN;key2:USER"

# Optional: Session configuration
export SESSION_BACKEND="redis"  # or "memory"
export SESSION_MAX_AGE="3600"  # seconds

# Optional: Environment detection
export ENVIRONMENT="production"  # or "development"
```

## Common Security Patterns

### ✅ DO: Parameterized Queries
```python
# Neo4j (Cypher)
session.run("MATCH (n) WHERE n.id = $id", id=user_id)

# Pseudo-SQL
conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### ❌ DON'T: String Interpolation
```python
# VULNERABLE - Never do this!
query = f"SELECT * FROM users WHERE id = {user_id}"
result = session.run(f"MATCH (n) WHERE n.id = '{id}'")
```

### ✅ DO: Constant-Time Comparison
```python
import hmac
if hmac.compare_digest(user_token, stored_token):
    authenticate()
```

### ❌ DON'T: Direct Comparison
```python
# VULNERABLE - Timing attack!
if user_token == stored_token:
    authenticate()
```

### ✅ DO: Secure Token Generation
```python
import secrets
token = secrets.token_urlsafe(32)
```

### ❌ DON'T: Weak Randomness
```python
# VULNERABLE - Not cryptographically secure!
import random
token = str(random.randint(1000000, 9999999))
```

## Pre-Commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
python3 -m pytest tests/test_security/test_owasp.py || exit 1
```

## Performance Impact

- OWASP audit on 600 Python files: ~2 seconds
- Individual security tests: <100ms each
- No runtime performance impact for production code

## Disabling Warnings

If you get a false positive, add a comment:

```python
# nosec - Reviewed: this is safe because X
dangerous_function(user_input)
```

## Reporting Security Issues

🔒 **Do not open public issues for security vulnerabilities**

1. Use GitHub Security Advisory (Private)
2. Or email: security@agentic-brain.io

---

**Last Updated**: 2026-04-05  
**Test Count**: 41 comprehensive tests  
**Coverage**: All 10 OWASP categories
