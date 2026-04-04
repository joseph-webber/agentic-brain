# Security Role System Tests

Comprehensive CI/CD tests for the three-tier security role system in agentic-brain.

## Overview

These tests verify that the security role system works correctly across all three security levels:

- **ADMIN**: Full system access, no restrictions (Joseph's mode)
- **USER**: Safe operations only, cannot harm OS
- **GUEST**: Read-only chat access, help desk mode

## Test Files

### `test_admin_mode.py`
Tests ADMIN role - verifies full access to everything:
- Can execute dangerous commands (rm -rf, sudo, etc.)
- Can write/read any file path
- Has full LLM access with code execution
- No rate limits
- Can access secrets and admin APIs

**11 tests** - All verify ADMIN has unrestricted access.

### `test_user_mode.py`
Tests USER role - verifies safe operations only:
- **Cannot** delete system files or use sudo
- **Cannot** write to system paths (/etc, /usr, etc.)
- **Can** write to allowed paths (~/brain/data, ~/brain/logs, etc.)
- **Can** run safe development commands (ls, cat, grep, python, npm, git)
- **Cannot** chmod 777, modify firewall, kill all processes
- **Cannot** git push --force
- Has standard LLM access with rate limits
- No admin API access

**15 tests** - Verify USER is restricted but functional for development.

### `test_guest_mode.py`
Tests GUEST role - verifies read-only chat mode:
- **Cannot** execute any commands (even safe ones)
- **Cannot** write any files
- **Can** read public documentation (README.md, docs/)
- **Cannot** read sensitive files
- Chat-only LLM access, no code execution
- Strict rate limits
- No secrets or admin access

**13 tests** - Verify GUEST is completely locked down.

### `test_bypass_prevention.py`
Tests security bypass prevention mechanisms:
- **Regex detection** of dangerous commands (rm, sudo, chmod 777, dd, fork bombs)
- **Path traversal** attack prevention (../ sequences)
- **Symlink** attack prevention
- **Command injection** prevention (semicolons, pipes, backticks)
- **Environment manipulation** blocking (PATH, LD_PRELOAD)
- **Database destruction** blocking (DROP DATABASE, TRUNCATE)
- **Shell config tampering** blocking
- **Role escalation** prevention
- **Audit trail** logging

**18 tests** - Verify security cannot be bypassed.

## Running Tests

### Run all security tests:
```bash
pytest tests/security/ -v
```

### Run specific test files:
```bash
pytest tests/security/test_admin_mode.py -v
pytest tests/security/test_user_mode.py -v
pytest tests/security/test_guest_mode.py -v
pytest tests/security/test_bypass_prevention.py -v
```

### Run with coverage:
```bash
pytest tests/security/ \
  --cov=src/agentic_brain/security \
  --cov-report=html \
  --cov-report=term \
  --cov-fail-under=80
```

## CI/CD Integration

Tests run automatically via GitHub Actions on:
- Every push to `main` or `develop`
- Every pull request
- Daily at 2 AM UTC (scheduled run)

### Workflow: `.github/workflows/security.yml`

The workflow includes:

1. **Security Role Tests** (matrix: Python 3.11, 3.12)
   - All 57 security tests
   - Coverage report generation (80% minimum)
   - Artifact upload for coverage reports

2. **Bandit Security Scan**
   - Static analysis for security issues
   - SARIF report upload to GitHub Security

3. **Dependency Audit**
   - pip-audit for known vulnerabilities
   - safety check for dependency issues

4. **Trivy Scans**
   - Filesystem scan
   - Container image scan

## Test Coverage

**Current: 57 tests**

- ADMIN mode: 11 tests ✅
- USER mode: 15 tests ✅
- GUEST mode: 13 tests ✅
- Bypass prevention: 18 tests ✅

**Coverage target: 80%+** of security module

## Key Security Verifications

### Command Blocking
✅ Dangerous patterns detected:
- `rm -rf /`, `sudo`, `chmod 777`, `dd to /dev`
- Fork bombs, infinite loops
- `git push --force`, `DROP DATABASE`
- Environment tampering, firewall changes

### Path Security
✅ Path access controlled:
- USER can write to `~/brain/data`, `~/brain/logs`, etc.
- USER **cannot** write to `/etc`, `/usr`, `/var`
- Path traversal attacks blocked
- Symlinks resolved to real paths

### Role Boundaries
✅ Roles strictly enforced:
- ADMIN: Full access (rate_limit ≥ 1000/min)
- USER: Standard access (rate_limit < 1000/min)
- GUEST: Chat only (rate_limit ≤ 60/min)
- No role escalation possible

### Audit Trail
✅ All security events logged:
- Command execution attempts
- File access attempts
- Violations tracked with timestamp, role, reason

## Fixtures

`conftest.py` provides shared fixtures:
```python
@pytest.fixture
def admin_guard():
    return SecurityGuard(SecurityRole.ADMIN)

@pytest.fixture
def user_guard():
    return SecurityGuard(SecurityRole.USER)

@pytest.fixture
def guest_guard():
    return SecurityGuard(SecurityRole.GUEST)
```

## Adding New Tests

When adding security features:

1. **Add test to appropriate file**:
   - Admin features → `test_admin_mode.py`
   - User restrictions → `test_user_mode.py`
   - Guest restrictions → `test_guest_mode.py`
   - Bypass prevention → `test_bypass_prevention.py`

2. **Follow naming conventions**:
   - `test_[role]_can_[action]` for allowed actions
   - `test_[role]_cannot_[action]` for blocked actions

3. **Run tests locally** before pushing:
   ```bash
   pytest tests/security/ -v --tb=short
   ```

4. **Verify coverage** doesn't drop:
   ```bash
   pytest tests/security/ --cov=src/agentic_brain/security --cov-report=term
   ```

## Security Issues Found

If security tests fail:

1. **DO NOT DISABLE THE TEST** without investigation
2. Security failures indicate real vulnerabilities
3. Fix the security implementation, not the test
4. Document any intentional changes to security model

## License

SPDX-License-Identifier: Apache-2.0  
Copyright 2024-2026 Agentic Brain Contributors
