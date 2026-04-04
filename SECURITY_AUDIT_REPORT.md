# Security Audit Report

## Scope
Audited the four-role security model in `src/agentic_brain/security`, `src/agentic_brain/yolo`, and related tests.

## Final Compliance Status
- FULL_ADMIN: Compliant
- SAFE_ADMIN: Compliant
- USER: Compliant
- GUEST: Compliant with one explicit nuance: read-only public API access is allowed for product/help content, but no write/authenticated/admin API access exists.

## Feature Matrix

| Feature | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
|---|---|---|---|---|
| YOLO mode | Yes | Yes, confirmation required for dangerous ops | No | No |
| Shell execution | Yes | Yes, guarded | No | No |
| File write access | Anywhere | Project/dev-safe paths only | No | No |
| File read access | Anywhere | Anywhere | Public docs only | Public docs only |
| Database access | Yes | Yes | No | No |
| LLM access | All providers | All providers | Chat access, all standard providers | Chat/help access, limited safe providers |
| Code execution | Yes | Yes | No | No |
| System configuration | Yes | Yes, guardrails apply | No | No |
| User management | Yes | No | No | No |
| Rate limit | Unlimited | High | Limited | Heavy |
| API access | All scopes | Read/write/delete | Read/write only | Read-only public endpoints only |

## Gaps Found During Audit
1. `llm_guard.py` used a separate 3-role enum and did not model `SAFE_ADMIN` / `FULL_ADMIN` consistently.
2. LLM role inference defaulted to elevated access when no auth context existed; this was tightened.
3. `security/__init__.py` exported only partial security symbols, which broke YOLO security imports.
4. `yolo/executor.py` allowed low-privilege roles to access machine-oriented actions like status/search/tests.
5. `auth.py` did not refresh env-based admin key state for runtime authentication checks.
6. Test coverage was partly stale versus the required four-role model.

## Fixes Applied
- Unified LLM security onto shared role definitions.
- Added SAFE_ADMIN/FULL_ADMIN-aware LLM permission matrix.
- Restricted unauthenticated/default LLM role inference to guest-safe behavior.
- Restored security package exports needed by guards, agents, and YOLO.
- Enforced SAFE_ADMIN-or-higher for YOLO machine actions.
- Added compatibility aliases/helpers in role permissions for older callers.
- Refreshed admin env-key auth behavior.
- Updated security tests to match the required role model.

## Verification
Executed:

```bash
pytest tests/test_security_roles.py tests/test_llm_security.py tests/security/test_admin_mode.py tests/security/test_guest_mode.py tests/security/test_user_mode.py tests/security/test_agent_security.py tests/security/test_api_access.py -q
```

Result: **103 passed**.

## Notes
- Guest access remains strictly non-machine and non-write; read-only public API exposure is limited to public/help/product-style content.
- Existing pytest warnings are unrelated to the audited permission model and did not affect pass/fail status.
