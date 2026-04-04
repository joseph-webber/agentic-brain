# BrainChat Integration Review

## Scope
Reviewed `apps/BrainChat/` against the Python backend under `src/agentic_brain/`.

## Integration Matrix

| Component | Status | Notes |
|-----------|--------|-------|
| WebSocket API | ✅ Fixed | Added `AgenticBrainBackendClient` with `/ws/chat` support plus REST fallback to `/chat`. Auth headers now support `X-API-Key` and `Authorization: Bearer`. |
| Graph RAG | 🟡 Partial | BrainChat now sends Graph RAG metadata (`rag.enabled`, `scope`, profile, mode) through backend chat requests. Swift still has no dedicated Graph RAG mutation endpoint because the backend does not expose one in the current public API. |
| Voice Input | ✅ Verified | Existing STT stack already supports Apple Speech plus local Whisper bridges. |
| Voice Output | ✅ Verified | Existing TTS stack already supports macOS voice output and cloud engines. |
| LLM Router | ✅ Fixed | Router now supports backend orchestration, ADL/profile-driven prompts, and explicit fallback chains without breaking provider-specific selection. |
| Redpanda | ✅ Fixed | Added listener recovery with bounded reconnect attempts after Pandaproxy polling failures. |
| ADL Config | ✅ Fixed | Added ADL loading/parsing, profile mapping, fallback parsing, and settings application. |
| Self-Healing | ✅ Fixed | Added `SelfHealingMonitor` for backend retries and REST fallback recovery; Redpanda reconnect now auto-recovers transient failures. |
| Polymorphic | ✅ Fixed | Added beginner/developer/enterprise behavior profiles with prompt, routing, STT, and TTS defaults. |

## What Was Verified

### 1. Backend API
Python already exposes:
- `POST /chat`
- `GET /health`
- `GET /session/{session_id}/messages`
- `WS /ws/chat`
- optional auth in `api/auth.py`

Swift previously had provider-direct networking but no first-class agentic-brain API client. This review added one.

### 2. Graph RAG
Python contains Graph/GraphRAG capabilities, but BrainChat did not pass Graph RAG intent into backend requests. Swift now forwards Graph RAG metadata so backend routing can use it.

### 3. Voice System
BrainChat already had:
- Apple Speech recognition
- faster-whisper / whisper.cpp bridges
- macOS native speech output
- cloud voice engines
- audio level/VAD-style mic activity reporting

No blocking integration gaps were found here.

### 4. LLM Orchestration
BrainChat already had multi-provider routing and layered responses. The main gap was lack of backend orchestration support. Swift now:
- tries agentic-brain backend first when enabled
- falls back to direct providers on failure
- preserves explicit provider selection for provider-specific flows

### 5. Event Bus / Redpanda
BrainChat already published/subscribed through Pandaproxy. The missing piece was disconnection recovery. That is now implemented with bounded retry and consumer re-creation.

### 6. ADL Configuration
Added:
- ADL file path setting
- parser for persona, routing, fallback list, system prompt, and Graph RAG signals
- profile/mode application into runtime settings

### 7. Self-Healing
Added:
- retry wrapper for backend operations
- WebSocket to REST degradation path
- Redpanda reconnect path
- issue recording via `SelfHealingMonitor`

### 8. Polymorphic Behaviors
Added `BrainChatBehaviorProfile`:
- `beginner`
- `developer`
- `enterprise`

These now influence prompt defaults, fallback providers, speech engine defaults, and voice output defaults.

## Files Changed

### Swift app
- `apps/BrainChat/AgenticBrainIntegration.swift`
- `apps/BrainChat/LLMRouter.swift`
- `apps/BrainChat/Models.swift`
- `apps/BrainChat/SettingsView.swift`
- `apps/BrainChat/RedpandaBridge.swift`
- `apps/BrainChat/APIKeyManager.swift`
- `apps/BrainChat/Package.swift`
- `apps/BrainChat/Tests/LLMTestSupport.swift`
- `apps/BrainChat/Tests/AgenticBrainIntegrationTests.swift`

## Tests Added
- ADL parsing
- backend auth/header and Graph RAG metadata propagation
- backend-first routing
- backend failure fallback
- Redpanda reconnect recovery

## Validation
Executed:
- `cd agentic-brain/apps/BrainChat && swift test --quiet`

Result: passing.

## Remaining Gap
A dedicated Swift-side Graph RAG knowledge update API is still not wired because the current backend public API reviewed here does not expose a dedicated Graph RAG update endpoint. BrainChat now sends the right metadata for backend routing, but a future backend endpoint would be needed for full CRUD-style knowledge updates from Swift.
