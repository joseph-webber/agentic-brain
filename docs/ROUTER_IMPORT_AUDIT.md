# Router Import Audit

**Scope:** `/Users/joe/brain/agentic-brain`  
**Search commands executed:**  
`grep -r "from agentic_brain.router import" src/ --include="*.py"`  
`grep -r "from agentic_brain.llm import" src/ --include="*.py"`  
`grep -r "from agentic_brain.smart_router import" src/ --include="*.py"`  
`grep -r "LLMRouter" src/ --include="*.py"`  
`grep -r "LLMRouterCore" src/ --include="*.py"`  
`grep -r "SmartRouter" src/ --include="*.py"`  
`rg -n "from \\.{1,2}router import" src/agentic_brain`

## 1. Files importing routing components

### Absolute imports (`from agentic_brain.router import …`)
| File | Imported symbols | Router classes/utilities referenced | Notes |
| --- | --- | --- | --- |
| `src/agentic_brain/api/routes.py` | `ProviderChecker`, `format_provider_status_report`, `get_setup_help` | Diagnostics helpers only | Used inside `_register_setup_routes` for the `/setup` FastAPI endpoint. |
| `src/agentic_brain/cli/commands.py` | Same trio above + standalone `get_setup_help` | Diagnostics helpers only | Powers `agentic check` and `agentic setup-help` CLI flows. |
| `src/agentic_brain/health/__init__.py` | `LLMRouter` (runtime import inside `LLMHealthIndicator`) | `LLMRouter` | Lazy import avoids heavy dependencies unless health check runs. |
| `src/agentic_brain/router/__init__.py` | N/A (module itself) | Re-exports `LLMRouter`, `SmartRouter`, diagnostics helpers, deprecated aliases via lazy import map. |

### Relative imports of the router package
| File | Import statement | Router class/utilities used | Purpose |
| --- | --- | --- | --- |
| `src/agentic_brain/agent.py` | `from .router import LLMRouter, Provider, RouterConfig`; runtime `from .router import ProviderChecker` | Instantiates `LLMRouter`, validates providers | Core Agent bootstrap; ProviderChecker only used for warnings. |
| `src/agentic_brain/unified_brain.py` | `from .router import LLMRouter` | `LLMRouter` | UnifiedBrain composes routers with Redis coordination. |
| `src/agentic_brain/chat/chatbot.py` | `from ..router import get_router` | `get_router` helper returning singleton `LLMRouter` | Chatbot obtains router lazily. |
| `src/agentic_brain/llm/__init__.py` | `from .router import LLMRouterCore as _LLMRouterCore, ModelRoute` | `LLMRouterCore` (aliases) | LLM package exposes lightweight core without pulling in `agentic_brain.router`. |

### Direct imports of `agentic_brain.llm.router` and `agentic_brain.smart_router`
| File | Import statement | Router class | Notes |
| --- | --- | --- | --- |
| `src/agentic_brain/router/routing.py` | `from agentic_brain.llm.router import LLMRouterCore` | `LLMRouterCore` | `LLMRouter` extends the lightweight core here; only direct consumer. |
| `src/agentic_brain/router/smart_router.py` | `from agentic_brain.smart_router import SmartRouter, SmashMode, SmashResult, SecurityPosture, PostureMode` | `SmartRouter` & related enums | Acts as a re-export layer so callers can keep importing via `agentic_brain.router`. |

### Other references surfaced by keyword searches
- `LLMRouter` appears (via `grep`) in `agentic_brain/agent.py`, `agentic_brain/unified_brain.py`, `agentic_brain/chat/chatbot.py`, `agentic_brain/health/__init__.py`, `agentic_brain/router/{__init__,routing}.py`, `agentic_brain/__init__.py`, and docstrings within `agentic_brain/smart_router/core.py`.  
- `LLMRouterCore` text hits stay within the `agentic_brain/llm` and `agentic_brain/router/routing.py` modules—no external callers import it directly.  
- `SmartRouter` literal matches are confined to the smart-router package plus router re-export wrappers; no external module imports it directly.

## 2. Import consistency assessment

1. **Public consumers (CLI, API, health checks)** consistently use the absolute path `from agentic_brain.router import …`, which keeps the external API stable.  
2. **Internal modules** (`agent.py`, `unified_brain.py`, `chat/chatbot.py`, `llm/__init__.py`) rely on relative imports to avoid redundant package prefixes and keep refactors easier.  
3. **Runtime imports** exist only where startup costs or dependency availability are uncertain (`health/__init__.py` lazy import of `LLMRouter`, `_init_router` in `Agent` for `ProviderChecker`).  
4. **No modules import `agentic_brain.llm` wholesale.** Access to `LLMRouterCore` always happens via `agentic_brain.llm.router` or the re-export alias.  
5. **SmartRouter** is only imported in one place and then re-exported, so most of the codebase never couples directly to `agentic_brain.smart_router`.

Overall the pattern is mostly consistent: user-facing entry points stick to the public `agentic_brain.router` API, while core modules use relative imports. The dynamic import in `health/__init__.py` is the only deviation, and it is intentional to keep the health check resilient.

## 3. Circular import risk review

- `agentic_brain/router/__init__.py` lazily re-exports `LLMRouterCore` by pointing to `agentic_brain.llm`. Because `agentic_brain/llm/__init__.py` only imports from its own submodule (`agentic_brain.llm.router`) and never touches `agentic_brain.router`, the lazy lookup avoids an immediate cycle. Risk remains low as long as `agentic_brain.llm` continues to avoid importing `agentic_brain.router`.  
- `agentic_brain/agent.py` imports `LLMRouter` at module load and `ProviderChecker` inside `_init_router`. If `_init_router` were ever moved to the module level, it could create a circular dependency between `agent.py` and the diagnostics helpers in `agentic_brain.router`. Keeping the import inside the method mitigates that risk.  
- No other router consumer imports both `agentic_brain.router` and `agentic_brain.smart_router` directly, so SmartRouter orchestration currently has no observable cycle surface.

## 4. Recommendations

1. **Document the import contract:** Clarify in developer docs that external modules must use `from agentic_brain.router import …` while core modules may use relative imports. This formalizes the pattern already in practice.  
2. **Centralize diagnostics helpers:** both the CLI and API re-import `ProviderChecker`, `format_provider_status_report`, and `get_setup_help`. Consider exposing a `diagnostics` helper module (or `router.diagnostics`) to reduce duplicated import blocks.  
3. **Expose a single runtime health hook:** `health/__init__.py` lazily instantiates `LLMRouter`. Providing a `router.get_default_router()` (already exists) or `health.get_router_status()` helper could replace the inline import and make the health indicator mirror other consumers.  
4. **Guard against future cycles:** add a unit test that imports `agentic_brain.router` before `agentic_brain.llm` (and vice versa) to ensure no regressions introduce circular dependencies when refactoring router internals.  
5. **Audit SmartRouter consumers before refactors:** Since SmartRouter is funneled through `agentic_brain.router.smart_router`, any refactor of that bridge should include regression tests verifying the re-export still works and no other files accidentally import `agentic_brain.smart_router` directly.

## 5. Blast radius for router refactoring

- **Core classes affected:** `Agent`, `UnifiedBrain`, `Chatbot`, and the health indicator are the only modules instantiating or retrieving routers today.  
- **Diagnostics surface:** CLI and API depend on the diagnostics helpers but not router internals.  
- **LLMRouterCore inheritance:** Only `router/routing.py` depends on the lightweight core; refactoring LLMRouterCore would primarily affect that module plus any deprecated consumers still importing via `agentic_brain.router`.  
- **SmartRouter exposure:** Changes to the smart-router package will impact only the re-export shim and any downstream users who pull `SmartRouter` from `agentic_brain.router`. Keeping the shim stable maintains backward compatibility.

No circular import issues were observed during this audit, but the recommendations above should be implemented before large-scale router changes to keep the blast radius predictable.
