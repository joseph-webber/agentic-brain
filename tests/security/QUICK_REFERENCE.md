# Security Tests Quick Reference

## 🚀 Quick Start

```bash
cd /Users/joe/brain/agentic-brain

# Run all security tests
pytest tests/security/ -v

# Run specific role tests
pytest tests/security/test_admin_mode.py -v
pytest tests/security/test_user_mode.py -v
pytest tests/security/test_guest_mode.py -v
pytest tests/security/test_bypass_prevention.py -v

# With coverage
pytest tests/security/ --cov=src/agentic_brain/security --cov-report=term
```

## 📊 Test Breakdown

| File | Tests | Purpose |
|------|-------|---------|
| `test_admin_mode.py` | 11 | Verify ADMIN has full access |
| `test_user_mode.py` | 15 | Verify USER is safe but functional |
| `test_guest_mode.py` | 13 | Verify GUEST is read-only |
| `test_bypass_prevention.py` | 18 | Verify security cannot be bypassed |
| **TOTAL** | **57** | **Complete security validation** |

## 🔒 Security Roles

### ADMIN
- ✅ Full system access
- ✅ Can execute ANY command
- ✅ Can write/read ANY file
- ✅ Full LLM + code execution
- ✅ No rate limits
- ✅ Admin API access

### USER
- ✅ Safe development commands
- ✅ Write to ~/brain/* paths only
- ✅ Standard LLM access
- ❌ No sudo/dangerous commands
- ❌ No system file writes
- ❌ Rate limited

### GUEST
- ✅ Read public docs only
- ✅ Chat-only LLM
- ❌ No command execution
- ❌ No file writes
- ❌ Strict rate limits

## 🛡️ Security Mechanisms Tested

✅ **Command Blocking**
- rm -rf, sudo, chmod 777, dd, fork bombs
- git push --force, DROP DATABASE
- iptables, killall, systemctl

✅ **Path Security**
- Path traversal (../) blocked
- Symlinks resolved to real paths
- System paths protected

✅ **Injection Prevention**
- Command injection via ; | ` blocked
- Environment tampering blocked
- Shell config tampering blocked

✅ **Audit Trail**
- All violations logged
- Timestamp, role, reason tracked

## 📝 Adding Tests

1. Choose correct file:
   - Admin features → `test_admin_mode.py`
   - User restrictions → `test_user_mode.py`
   - Guest restrictions → `test_guest_mode.py`
   - Bypass prevention → `test_bypass_prevention.py`

2. Use naming convention:
   ```python
   def test_[role]_can_[action](self, [role]_guard):
       """Description."""
       allowed, reason = [role]_guard.check_command("cmd")
       assert allowed, f"Should allow: {reason}"
   
   def test_[role]_cannot_[action](self, [role]_guard):
       """Description."""
       allowed, reason = [role]_guard.check_command("cmd")
       assert not allowed, "Should block"
   ```

3. Run tests:
   ```bash
   pytest tests/security/ -v --tb=short
   ```

## 🔄 CI/CD

Tests run automatically on:
- ✅ Push to main/develop
- ✅ Pull requests
- ✅ Daily at 2 AM UTC

Matrix: Python 3.11, 3.12

Workflow: `.github/workflows/security.yml`

## 📚 Documentation

- `tests/security/README.md` - Full documentation
- `SECURITY_TESTS_COMPLETE.md` - Implementation summary
- Inline docstrings in all test files

## ⚠️ Important

**NEVER disable a failing security test without investigation!**

Security test failures indicate real vulnerabilities. Fix the implementation, not the test.

---

**Status**: ✅ 57/57 tests passing  
**Coverage**: 80%+ of security module  
**Last Updated**: 2026-04-04
