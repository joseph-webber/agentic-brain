# Security Architecture Update - API-Only USER Role

## Summary

We implemented a key security insight: **customer chatbots should ONLY access APIs**, by converting the **USER** role to API-only mode.

## What Changed

### Before
- **ADMIN**: Full access
- **USER**: Limited machine access (safe coding assistant)
- **DEVELOPER**: (didn't exist)
- **GUEST**: Read-only, limited paths

### After
- **ADMIN**: Full access (unchanged)
- **DEVELOPER**: Limited machine access (safe coding assistant - **this is the old USER**)
- **USER**: **API-ONLY** (customer chatbots - **new security model**)
- **GUEST**: Read-only API access only

## Breaking Changes

### Test Failures

10 existing tests fail because they expect USER to have file/shell access:

```
FAILED tests/security/test_user_mode.py::TestUserMode::test_user_can_run_safe_commands
FAILED tests/security/test_user_mode.py::TestUserMode::test_user_can_write_to_allowed_paths
FAILED tests/security/test_user_mode.py::TestUserMode::test_user_can_write_to_test_artifacts
FAILED tests/security/test_user_mode.py::TestUserMode::test_user_has_standard_llm_access
```

**These tests were written for the old "coding assistant" USER role.**

## Two Options Forward

### Option 1: Update Tests to Match New Architecture ✅ RECOMMENDED

Update existing tests:
- Tests for "coding assistant" behavior → Test **DEVELOPER** role instead
- Tests for API-only customer behavior → Test **USER** role
- This matches the security model: USER = customer chatbots (API-only)

### Option 2: Add CUSTOMER Role (Keep USER as-is)

Keep USER as "safe coding assistant" and add new CUSTOMER role:
- **ADMIN**: Full access
- **DEVELOPER**: Limited machine access (power users)
- **USER**: Limited machine access (safe coding assistant)
- **CUSTOMER**: API-only (customer chatbots)
- **GUEST**: Read-only

**Downside**: More complexity, and USER is a confusing name for a coding assistant.

## Recommendation

**Option 1** is better because:

1. **Clearer naming**:
   - USER = customer/user of the application (API-only)
   - DEVELOPER = developer building with the brain (machine access)
   - ADMIN = system administrator (full access)

2. **Matches the security model**: 
   > "Customer/User chatbots should ONLY access external APIs"

3. **Simpler architecture**: 4 roles instead of 5

## Test Migration Guide

Update tests like this:

### Before
```python
def test_user_can_write_files(self, user):
    """User can write to safe directories."""
    guard = SecurityGuard(SecurityRole.USER)
    allowed, _ = guard.check_file_write("~/brain/data/output.json")
    assert allowed
```

### After
```python
def test_developer_can_write_files(self, developer):
    """Developer can write to safe directories."""
    guard = SecurityGuard(SecurityRole.DEVELOPER)
    allowed, _ = guard.check_file_write("~/brain/data/output.json")
    assert allowed

def test_user_cannot_write_files(self, user):
    """User (customer) cannot write files - API-only."""
    guard = SecurityGuard(SecurityRole.USER)
    allowed, reason = guard.check_file_write("~/brain/data/output.json")
    assert not allowed
    assert "API-only" in reason or "not permitted" in reason
```

## API-Only Architecture Benefits

1. **Security**: Customers can't access file system or run shell commands
2. **Isolation**: Each customer only accesses their data through APIs
3. **Auditability**: All API calls are logged
4. **Scalability**: API-based access is easier to scale than machine access
5. **Compliance**: Easier to prove security compliance (no direct DB access)

## Implementation Status

✅ **Completed**:
- `src/agentic_brain/security/api_access.py` - API access controller
- `src/agentic_brain/integrations/wordpress.py` - WordPress integration
- `src/agentic_brain/integrations/woocommerce.py` - WooCommerce integration
- `src/agentic_brain/security/roles.py` - Updated with API permissions
- `tests/security/test_api_access.py` - 21 tests, all passing ✅
- `examples/api_security_demo.py` - Working demonstration

⚠️ **Needs Update**:
- `tests/security/test_user_mode.py` - Update to test API-only behavior
- `tests/security/test_admin_mode.py` - Fix attribute name issues
- `tests/security/test_guest_mode.py` - Fix attribute name issues

## Next Steps

1. Update failing tests to match new architecture
2. Add tests for API-only USER behavior
3. Document the role mapping clearly
4. Update any documentation that mentions "USER as coding assistant"

## Conclusion

The **USER → API-only** change is the right architectural decision. It aligns with:
- Security architecture insight
- Industry best practices (principle of least privilege)
- Clear separation of concerns (customer vs developer vs admin)

The test failures are expected - they're testing the old architecture. We should update them to test the new one.
