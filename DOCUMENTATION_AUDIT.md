# Documentation Audit

Date: 2026-04-04  
Scope: `agentic-brain/docs/` plus checklist files referenced by the audit request.

## Issues Found and Fixed

### 1. Stale installation and quick-start guidance
- **Problem:** `INSTALL.md`, `docs/INSTALL.md`, and `docs/QUICK_START.md` contained outdated version references and older setup flows.
- **Fix:** Rewrote them to reflect Agentic Brain 3.1.0, current extras from `pyproject.toml`, and working CLI commands (`ab doctor`, `ab serve`, `agentic adl validate`).
- **Verified:**
  - `PYTHONPATH=src python3 -m agentic_brain.cli --help`
  - `PYTHONPATH=src python3 -m agentic_brain.cli adl validate --file test.adl`

### 2. API docs described endpoints and responses inaccurately
- **Problem:** `docs/API.md`, `docs/API_REFERENCE.md`, `docs/api-reference.md`, `docs/API_DOCS_SUMMARY.md`, and `docs/INDEX.md` documented unimplemented endpoints and stale response shapes.
- **Fix:** Rewrote the core API docs to match the currently mounted FastAPI routes and refreshed `docs/openapi.json` from the running app.
- **Verified:**
  - `TESTING=1 PYTHONPATH=src python3 - <<'PY' ... create_app().openapi() ... PY`
  - OpenAPI snapshot now reports version `3.1.0`

### 3. Public API behavior did not match documented delete/health responses
- **Problem:** `DELETE /session/{session_id}` and `DELETE /sessions` raised FastAPI response validation errors, and `/health` response documentation drifted from the response model.
- **Fix:**
  - Updated `HealthResponse` to match the real health payload.
  - Made both delete endpoints return `DeleteResponse` objects.
  - Set API version from package version and updated `agentic_brain.__version__` to `3.1.0`.
- **Verified:**
  - `TESTING=1 PYTHONPATH=src python3 -m pytest -q tests/test_api_server.py -k 'health_response or delete_session or clear_all_sessions'`
  - Result: `6 passed`

### 4. WebSocket docs did not match implementation
- **Problem:** `docs/WEBSOCKET_API.md` documented behavior that is not present (for example, unsupported assumptions about keep-alives and optional auth).
- **Fix:** Rewrote the file to match `src/agentic_brain/api/websocket.py` and `websocket_auth.py`, including JWT requirements, payload format, and actual error frames.
- **Verified:**
  - `TESTING=1 PYTHONPATH=src JWT_SECRET=secret python3 - <<'PY' ... TestClient websocket checks ... PY`
  - Confirmed `INVALID_JSON` and `MISSING_MESSAGE` error frames.

### 5. Missing voice coverage file from the checklist
- **Problem:** `docs/VOICE_GUIDE.md` did not exist.
- **Fix:** Created `docs/VOICE_GUIDE.md` as the top-level entry point to the voice documentation set.
- **Verified:** Included in link check and opens local references correctly.

### 6. GraphRAG installation examples used incorrect extras
- **Problem:** `docs/GRAPHRAG.md` referenced outdated optional extras.
- **Fix:** Updated install examples to use extras that exist in `pyproject.toml`.
- **Verified:** Spot-checked against `pyproject.toml` optional dependency list.

### 7. Broken internal links across the docs set
- **Problem:** 29 local markdown links were broken.
- **Fix:** Corrected broken paths in tutorial, chat, migration, Firebase, macOS checklist, memory, and API index docs.
- **Verified:** Repo-wide local markdown link check now reports `MISSING_LINKS 0`.

### 8. Deployment and security guides were overly aspirational
- **Problem:** `docs/DEPLOYMENT.md` and `docs/SECURITY.md` claimed files, flows, or guarantees that were not directly backed by the current repository.
- **Fix:** Rewrote both guides to document only repository-backed deployment manifests and implemented security controls.
- **Verified:** Content cross-checked against repository manifests and API/security modules.

## Issues Needing Manual Review

1. **Root `README.md` external claims**  
   Local links are valid, but external badges, deploy buttons, and marketing claims (for example compliance/readiness statements and ecosystem links) were not exercised end-to-end during this audit.

2. **Cloud deployment manifests**  
   `render.yaml`, `railway.json`, `fly.toml`, `app.yaml`, `azuredeploy.json`, and `heroku.yml` exist and are documented, but this audit did not deploy each target platform.

3. **Highly specialized docs outside the core checklist**  
   Files such as Postman docs, legal/commercial guidance, roadmap material, and deep voice architecture notes were spot-checked for link/version consistency, but not execution-tested line by line.

4. **Document-version markers vs package version**  
   Some files contain document-specific version labels (`1.0.0`, roadmap snapshots, legal doc versions) that may be intentional document revisions rather than package versions. These should be reviewed in context before bulk normalization.

## Coverage Report

| Item | Status | Notes |
| --- | --- | --- |
| `README.md` | Audited | Present, local links valid; external marketing claims need manual review |
| `INSTALL.md` | Fixed | Rewritten to current install flow |
| `QUICK_START.md` | Fixed | Rewritten to working CLI/API flow |
| `API_REFERENCE.md` | Fixed | Rewritten to current mounted endpoints |
| `GRAPHRAG.md` | Fixed | Installation extras corrected |
| `ADL.md` | Verified | Commands validated with `agentic adl validate --file test.adl` |
| `WEBSOCKET_API.md` | Fixed | Rewritten to current JWT + error behavior |
| `VOICE_GUIDE.md` | Created | New top-level voice guide added |
| `DEPLOYMENT.md` | Fixed | Reduced to repo-backed deployment artifacts |
| `SECURITY.md` | Fixed | Reduced to implemented controls and realistic production checklist |

Additional audit coverage:
- `docs/API.md`, `docs/api-reference.md`, `docs/API_DOCS_SUMMARY.md`, and `docs/INDEX.md` were also updated for consistency.
- `docs/openapi.json` was regenerated from the current app.
- Broken internal links were corrected across multiple supporting docs.

## Recommendations

1. **Generate API docs from one source of truth**  
   Keep `docs/openapi.json` and human-readable API docs synchronized from `create_app().openapi()` during release or CI.

2. **Add a docs link checker to CI**  
   The broken-link sweep found 29 local link errors quickly; this should run automatically.

3. **Use a single package version source**  
   Keep `pyproject.toml`, `agentic_brain.__version__`, and API/OpenAPI version strings aligned automatically.

4. **Add docs smoke tests for examples**  
   At minimum, CI should exercise:
   - CLI help / install examples
   - `agentic adl validate`
   - `/health`, `/chat`, and session delete flows
   - WebSocket invalid-input behavior

5. **Review high-visibility marketing docs periodically**  
   Root README, deployment buttons, and compliance claims should get a separate release-gate review because they can drift even when internal docs are correct.
