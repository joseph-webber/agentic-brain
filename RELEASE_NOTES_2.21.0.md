# Release Notes v2.21.0

## Voice Phase 3 integration

This release adds the Phase 3 voice integration facade and hardens lazy-loading
across the voice stack.

### Added

- `src/agentic_brain/voice/phase3.py`
  - `Phase3VoiceSystem`
  - `get_phase3_voice_system()`
  - unified health reporting for Kokoro, earcons, live daemon, speed profiles,
    and optional Phase 3 modules
- `tests/test_voice_phase3_integration.py`
  - comprehensive integration coverage
  - graceful degradation checks
  - CLI compatibility coverage

### Updated

- `src/agentic_brain/voice/__init__.py`
  - lazy exports for `Phase3VoiceSystem`
  - compatibility aliases for `KokoroVoice` / `KokoroTTS`
  - corrected lazy earcon import to use the audio package
- `docs/voice/README.md`
  - documented Phase 3 facade and health model

### Notes

- Phase 3 integration is intentionally tolerant of missing optional modules.
- Existing serialized speech remains the safe fallback path.
- Health reports now make degraded states explicit instead of failing import-time.
