# Router Refactor Plan: Three Systems to One

**Status**: PROPOSED  
**Author**: Architecture Review  
**Date**: 2026-07-14  
**Scope**: `agentic_brain.llm.router`, `agentic_brain.router.routing`, `agentic_brain.smart_router`

---

## 1. Problem Statement

The codebase has **three overlapping LLM routing systems** totaling 3,500+ lines:

| System | Location | Lines | Class | Purpose |
|--------|----------|-------|-------|---------|
| **Lightweight** | `llm/router.py` | 787 | `LLMRouterCore` | Alias resolution, retry/backoff, cost tracking, dispatches to OpenAI/Anthropic/Ollama |
| **Main** | `router/routing.py` | 1,548 | `LLMRouter(LLMRouterCore)` | Full routing: smart_route(), fallback chains, streaming, caching, HTTP pooling, 10 providers |
| **Smart** | `smart_router/` | ~900 | `SmartRouter` | Master/worker parallel execution (turbo/cascade/consensus), heat-map load balancing, security posture |

**Key confusion points:**
- Both `llm/router.py` and `router/routing.py` export a class called `LLMRouter`
- `SmartRouter` duplicates provider HTTP calls already in `router/` (via `workers.py`)
- `smart_router/workers.py` has its own OpenAI/Groq/Gemini/etc. HTTP client code that ignores RouterConfig, HTTP pooling, retry logic, and cost tracking from the main router
- Importing `from agentic_brain.llm import LLMRouter` gives a different class than `from agentic_brain.router import LLMRouter`

---

## 2. Analysis: What Each System Owns

### 2.1 LLMRouterCore (`llm/router.py`) — KEEP as base class

**Unique responsibilities (not duplicated elsewhere):**
- Unified message normalization (`normalize_messages`)
- Model alias resolution via `MODEL_ALIASES` + friendly aliases
- `ModelRoute` dataclass (provider + model + alias)
- Priority model ordering and route resolution
- Per-request cost estimation with token-level granularity
- Retry with exponential backoff + `Retry-After` header parsing
- Rate-limit–aware retry logic
- Direct provider dispatch: `_dispatch_openai`, `_dispatch_anthropic`, `_dispatch_ollama`
- Convenience wrappers: `_chat_openai`, `_chat_anthropic`, `_chat_ollama`

**Assessment**: This is solid infrastructure. It provides the low-level "call one provider with retries" primitive that everything else builds on. **Keep as-is.**

### 2.2 LLMRouter (`router/routing.py`) — KEEP as primary router

**Unique responsibilities (builds on LLMRouterCore):**
- `smart_route(message)` — keyword-based task classification (code/reasoning/fast/default)
- Fallback chain definitions: `FALLBACK_CHAIN`, `FASTEST_CHAIN`, `CODE_CHAIN`, `REASONING_CHAIN`
- Dynamic availability checking (`_available_routes`, `_provider_is_configured`)
- Round-robin load balancing (`_select_balanced_route`, `_provider_usage`)
- UnifiedBrain integration (`_route_from_brain`)
- Semantic prompt caching (SQLite/Redis backends)
- Redis inter-bot cache coordination
- HTTP connection pooling via `PoolManager`
- Streaming support for all 10 providers
- Provider health checking (`check_all_providers`)
- Persona support
- Async context manager for pool lifecycle

**Assessment**: This is the production router. It handles the full request lifecycle: route selection → cache check → dispatch → fallback → cache store → stream. All 26+ consumer files import from `agentic_brain.router`. **Keep as primary public API.**

### 2.3 SmartRouter (`smart_router/`) — MERGE selectively, then deprecate

**Unique responsibilities (not available in the main router):**
- **Parallel execution modes**: `SmashMode.TURBO` (fire all, fastest wins), `CONSENSUS` (fire 3+, compare), `CASCADE` (free-first fallback)
- **Heat-map load balancing**: tracks per-worker usage to avoid hot-spotting
- **Security posture**: `PostureMode` enum + `SecurityPosture` dataclass controlling which workers are allowed, cost caps, rate limits
- **Redis-based distributed coordination** (`RedisCoordinator`)
- **Worker warm-up**: `warmup_ping()` to measure latency

**Duplicated responsibilities (already done better in main router):**
- `workers.py` re-implements HTTP calls for 8 providers (OpenAI, Azure, Groq, Gemini, Local, Together, DeepSeek, OpenRouter) using raw `httpx` — no retries, no backoff, no cost tracking, no connection pooling
- `WorkerConfig` duplicates provider metadata already in `RouterConfig`
- Sequential fallback in `SmartRouter.route()` DEDICATED mode duplicates `LLMRouter.chat()` fallback logic
- Per-worker stats tracking duplicates `LLMRouterCore._record_usage`

**Assessment**: The *modes* (turbo/cascade/consensus), *posture*, and *heat-map* are genuinely valuable. The *worker HTTP implementations* are inferior duplicates. **Extract the unique concepts into the main router; delete the duplicate HTTP code.**

---

## 3. Target Architecture

### 3.1 Layer Diagram

```
                        PUBLIC API
                            │
              ┌─────────────┴─────────────┐
              │    agentic_brain.router    │   ← single import path
              │    (LLMRouter class)       │
              └─────────────┬─────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
    ┌────┴────┐      ┌─────┴─────┐     ┌─────┴──────┐
    │ Strategy │      │   Core    │     │  Provider  │
    │  Layer   │      │  Layer    │     │  Layer     │
    │          │      │           │     │            │
    │ SmashMode│      │ LLMRouter │     │ chat_*()   │
    │ Posture  │      │   Core    │     │ stream_*() │
    │ HeatMap  │      │           │     │            │
    └─────────┘      └───────────┘     └────────────┘
```

### 3.2 Module Layout (after refactor)

```
src/agentic_brain/
├── router/                          # PRIMARY package — all routing lives here
│   ├── __init__.py                  # Public API (unchanged import surface)
│   ├── config.py                    # Provider, RouterConfig, Message, Response (KEEP)
│   ├── core.py                      # LLMRouterCore (MOVED from llm/router.py)
│   ├── routing.py                   # LLMRouter (KEEP, gains smash/posture features)
│   ├── strategy.py                  # NEW: SmashMode, SmashResult, parallel execution
│   ├── posture.py                   # MOVED from smart_router/posture.py
│   ├── heat_map.py                  # NEW: extracted from smart_router/core.py
│   ├── provider_checker.py          # KEEP
│   ├── http.py                      # KEEP
│   ├── ollama.py                    # KEEP
│   ├── openai.py                    # KEEP
│   ├── anthropic.py                 # KEEP
│   ├── google.py                    # KEEP
│   ├── groq.py                      # KEEP
│   ├── openrouter.py                # KEEP
│   ├── together.py                  # KEEP
│   ├── azure_openai.py              # KEEP
│   └── xai.py                       # KEEP
│
├── llm/
│   ├── __init__.py                  # Deprecation shim → re-exports from router
│   └── router.py                    # Deprecation shim → re-exports from router.core
│
├── smart_router/                    # Deprecation shim package
│   ├── __init__.py                  # Deprecation shim → re-exports from router
│   ├── core.py                      # Deprecation shim
│   ├── workers.py                   # Deprecation shim
│   ├── posture.py                   # Deprecation shim → router.posture
│   └── coordinator.py               # Deprecation shim → router.strategy
│
└── router/smart_router.py           # KEEP as bridge (already a re-export shim)
```

---

## 4. What Changes for Each System

### 4.1 `llm/router.py` (LLMRouterCore) → Move to `router/core.py`

**Action**: MOVE + DEPRECATION SHIM

1. Move `LLMRouterCore` and `ModelRoute` to `router/core.py`
2. Leave `llm/router.py` as a deprecation shim:

```python
# llm/router.py — DEPRECATED, use agentic_brain.router instead
import warnings
warnings.warn(
    "agentic_brain.llm.router is deprecated. "
    "Import from agentic_brain.router instead.",
    DeprecationWarning,
    stacklevel=2,
)
from agentic_brain.router.core import LLMRouterCore, ModelRoute  # noqa: F401

# The LLMRouter that was here was a thin subclass; use the real one.
LLMRouter = LLMRouterCore
```

3. Update `llm/__init__.py` to match:

```python
# llm/__init__.py — DEPRECATED
import warnings
warnings.warn(
    "agentic_brain.llm is deprecated. "
    "Import from agentic_brain.router instead.",
    DeprecationWarning,
    stacklevel=2,
)
from agentic_brain.router.core import LLMRouterCore, ModelRoute  # noqa: F401
LLMRouter = LLMRouterCore
```

**Impact**: Only `router/routing.py` imports `LLMRouterCore` internally. Update that one import. Tests (`test_llm_router_lightweight.py`) continue working via the shim.

### 4.2 `router/routing.py` (LLMRouter) → Gains strategy + posture

**Action**: ENHANCE in-place

1. Change the `LLMRouterCore` import:
   ```python
   # Before
   from agentic_brain.llm.router import LLMRouterCore
   # After
   from agentic_brain.router.core import LLMRouterCore
   ```

2. Add new methods to `LLMRouter` that wrap the strategy layer:
   ```python
   async def smash(
       self,
       message: str,
       mode: SmashMode = SmashMode.TURBO,
       timeout: float = 30.0,
       posture: SecurityPosture | None = None,
   ) -> SmashResult:
       """Fire multiple providers in parallel using a smash strategy."""
       from .strategy import execute_smash
       return await execute_smash(
           self, message, mode=mode, timeout=timeout, posture=posture
       )
   ```

3. No changes to `chat()`, `stream()`, `smart_route()`, or any existing public methods.

### 4.3 `smart_router/` → Extract unique code, then deprecate package

**Action**: EXTRACT + DEPRECATION SHIMS

#### 4.3.1 Extract `strategy.py` (NEW file in `router/`)

Move the parallel execution logic from `smart_router/coordinator.py`:
- `turbo_smash()` — fire all providers, return fastest
- `cascade_smash()` — try free providers first, then paid
- `execute_smash()` — new unified entry point

**Critical change**: Replace raw `httpx` worker calls with the existing provider `chat_*()` functions from `router/`. This means:
- Workers get retry logic, backoff, cost tracking for free
- Workers use the shared HTTP pool
- Workers respect `RouterConfig` settings
- ~400 lines of duplicated HTTP code in `workers.py` are deleted

```python
# router/strategy.py (sketch)
from .config import Provider, Response
from .core import SmashResult, SmashMode

async def execute_smash(
    router: "LLMRouter",
    message: str,
    *,
    mode: SmashMode,
    timeout: float = 30.0,
    posture: "SecurityPosture | None" = None,
) -> SmashResult:
    """Execute a multi-provider smash strategy using the main router's providers."""
    # Use router's existing _chat_* methods instead of raw httpx workers
    ...
```

#### 4.3.2 Move `posture.py` to `router/posture.py`

Move as-is. No logic changes needed. Update imports.

#### 4.3.3 Extract `heat_map.py` (NEW file in `router/`)

Extract the heat-map tracking from `smart_router/core.py`:
- `HeatMap` class with `add_heat()`, `cool_down()`, `get_coolest()`
- Used by `strategy.py` for load-balancing parallel execution

#### 4.3.4 Deprecation shims for `smart_router/`

Every file in `smart_router/` becomes a re-export shim:

```python
# smart_router/__init__.py — DEPRECATED
import warnings
warnings.warn(
    "agentic_brain.smart_router is deprecated. "
    "Import from agentic_brain.router instead.",
    DeprecationWarning,
    stacklevel=2,
)
from agentic_brain.router.strategy import SmashMode, SmashResult  # noqa: F401
from agentic_brain.router.posture import PostureMode, SecurityPosture  # noqa: F401
from agentic_brain.router import SmartRouter  # noqa: F401 (compat alias)
```

#### 4.3.5 Delete `smart_router/workers.py` (after extraction)

This file contains ~400 lines of duplicated HTTP client code. Once `strategy.py` uses the main router's provider functions, `workers.py` is dead code.

**Provide a deprecation shim for the worker class names only:**

```python
# smart_router/workers.py — DEPRECATED
import warnings
warnings.warn(
    "agentic_brain.smart_router.workers is deprecated. "
    "Use agentic_brain.router provider functions instead.",
    DeprecationWarning,
    stacklevel=2,
)
# Provide empty stubs for any code that checks class existence
```

---

## 5. Public API Surface (post-refactor)

All imports continue to work through `agentic_brain.router`:

```python
# Primary import path (UNCHANGED)
from agentic_brain.router import LLMRouter, Provider, RouterConfig, Response, Message

# Smart routing (UNCHANGED)
from agentic_brain.router import SmartRouter, SmashMode, SmashResult

# Security posture (UNCHANGED path via router/__init__.py)
from agentic_brain.router import SecurityPosture, PostureMode

# Convenience functions (UNCHANGED)
from agentic_brain.router import get_router, chat, chat_async

# Provider-specific (UNCHANGED)
from agentic_brain.router import chat_ollama, stream_openai, chat_groq

# New: parallel execution via LLMRouter instance
router = LLMRouter()
result = await router.smash("Hello!", mode=SmashMode.TURBO)
```

### 5.1 New Public Methods on LLMRouter

| Method | Description |
|--------|-------------|
| `smash(message, mode, timeout, posture)` | Parallel multi-provider execution |
| `get_heat_map()` | Current worker load distribution |
| `set_posture(posture)` | Set security posture for all operations |

### 5.2 SmartRouter Compatibility

`SmartRouter` becomes a thin facade that delegates to `LLMRouter.smash()`:

```python
# router/__init__.py or router/compat.py
class SmartRouter:
    """Backward-compatible wrapper. Prefer LLMRouter.smash() directly."""
    def __init__(self):
        self._router = get_router()

    async def route(self, task_type, prompt, mode=SmashMode.DEDICATED, **kw):
        return await self._router.smash(prompt, mode=mode, **kw)

    def get_status(self):
        return self._router.get_heat_map()
```

---

## 6. Deleted Code Summary

| File | Lines | Reason |
|------|-------|--------|
| `smart_router/workers.py` (body) | ~400 | Duplicate HTTP clients; replaced by `router/*.py` providers |
| `smart_router/core.py` (body) | ~200 | `SmartRouter` logic absorbed into `router/strategy.py` + `router/heat_map.py` |
| `smart_router/coordinator.py` (body) | ~200 | `turbo_smash`/`cascade_smash` moved to `router/strategy.py` |
| `llm/router.py` (body) | ~780 | `LLMRouterCore` moved to `router/core.py` |
| **Total deleted** | **~1,580** | **45% reduction** |

All files above retain deprecation shims (5-15 lines each) so old imports still resolve.

---

## 7. Migration Path

### Phase 1: Prepare (no breaking changes)

1. Create `router/core.py` by moving `LLMRouterCore` from `llm/router.py`
2. Create `router/strategy.py` with `execute_smash()` using existing provider functions
3. Move `smart_router/posture.py` → `router/posture.py`
4. Create `router/heat_map.py` extracted from `smart_router/core.py`
5. Add `smash()` method to `LLMRouter` in `routing.py`
6. Update `router/__init__.py` exports to include new modules
7. **All old import paths continue to work** — no shims yet

### Phase 2: Deprecation warnings

1. Replace `llm/router.py` body with deprecation shim + re-exports
2. Replace `llm/__init__.py` body with deprecation shim + re-exports
3. Replace `smart_router/*.py` bodies with deprecation shims + re-exports
4. Update internal import in `routing.py`: `from .core import LLMRouterCore`
5. Run full test suite to verify backward compatibility

### Phase 3: Documentation + cleanup

1. Update README/docs to show single import path
2. Update all examples to use `from agentic_brain.router import ...`
3. Update all internal code to use new paths (eliminate self-deprecation warnings)
4. Add migration guide to CHANGELOG

### Phase 4: Removal (future major version)

1. Remove `llm/` package entirely
2. Remove `smart_router/` package entirely
3. Remove `router/smart_router.py` bridge
4. Bump major version

---

## 8. Testing Strategy

### 8.1 Existing Tests (must pass unchanged)

| Test File | Imports From | Status |
|-----------|-------------|--------|
| `test_router.py` | `agentic_brain.router` | Must pass as-is |
| `test_router_features.py` | `agentic_brain.router` | Must pass as-is |
| `test_router_config.py` | `agentic_brain.router` | Must pass as-is |
| `test_smart_router.py` | `agentic_brain.router` | Must pass as-is |
| `test_smart_routing.py` | `agentic_brain.router` | Must pass as-is |
| `test_llm_router_lightweight.py` | `agentic_brain.llm.router` | Must pass (via shim) |
| `test_documented_features.py` | `agentic_brain.router` | Must pass as-is |
| `test_personas.py` | `agentic_brain.router` | Must pass as-is |
| `test_imports.py` | `agentic_brain.router` | Must pass as-is |
| `test_ecosystem_integration.py` | `agentic_brain.router` | Must pass as-is |
| `e2e/test_llm_integration.py` | `agentic_brain.router` | Must pass as-is |
| `e2e/test_installation.py` | string check | Must pass as-is |

### 8.2 New Tests to Add

| Test | Validates |
|------|-----------|
| `test_deprecation_warnings.py` | Old import paths emit `DeprecationWarning` |
| `test_strategy.py` | `SmashMode.TURBO/CASCADE/CONSENSUS` execution |
| `test_heat_map.py` | Heat tracking, cool-down, coolest-worker selection |
| `test_posture_integration.py` | Security posture filters workers correctly |
| `test_smash_method.py` | `LLMRouter.smash()` delegates correctly |

### 8.3 Verification Commands

```bash
# Phase 1: All existing tests pass
pytest tests/ -x -q

# Phase 2: Deprecation warnings appear
python -W error::DeprecationWarning -c "from agentic_brain.llm.router import LLMRouterCore"
# Should raise DeprecationWarning

# Existing imports still work
python -c "from agentic_brain.router import LLMRouter, SmartRouter, SmashMode"
# Should succeed silently

# New API works
python -c "from agentic_brain.router import LLMRouter; r = LLMRouter(); print(hasattr(r, 'smash'))"
# Should print True
```

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Circular import during move | Medium | High | Phase 1 keeps both copies; delete old in Phase 2 |
| `workers.py` httpx code used directly | Low | Medium | Search confirmed no external imports of worker classes |
| SmartRouter singleton users break | Low | Low | `get_router()` in `smart_router/core.py` shim delegates to main singleton |
| Redis coordinator breaks | Low | Medium | `RedisCoordinator` shim in `smart_router/__init__.py` preserves import |
| Performance regression in smash modes | Medium | Medium | Strategy layer reuses proven provider code; benchmark before/after |

---

## 10. Success Criteria

- [ ] Single canonical import: `from agentic_brain.router import LLMRouter`
- [ ] All 12+ existing test files pass without modification
- [ ] Old imports (`agentic_brain.llm.router`, `agentic_brain.smart_router`) emit `DeprecationWarning` but still work
- [ ] `LLMRouter` gains `smash()` for parallel execution
- [ ] Net code reduction of 1,000+ lines (after removing duplicate HTTP clients)
- [ ] Zero new dependencies added
- [ ] `router/__init__.py` exports remain backward-compatible
