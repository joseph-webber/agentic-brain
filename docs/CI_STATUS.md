# CI Status

- Current status: ✅ PASSING
- Last verified: 2026-03-26 UTC

## Verified workflows
- CI — ✅ PASSING (run 23585688580)
- Continuous Deployment — ✅ PASSING (run 23585688610)
- Documentation — ✅ PASSING (latest successful run)
- License Check — ✅ PASSING (run 23585688597)

## Workflow inventory
- CI — ✅ Passing
- Continuous Deployment — ✅ Passing
- Documentation — ✅ Passing
- License Check — ✅ Passing
- Deploy to AWS — ⏸ Conditional/manual
- Deploy to Azure — ⏸ Conditional/manual
- Deploy to GCP — ⏸ Conditional/manual
- Docker Build and Publish — ⏸ Not part of this verification
- Firebase Integration Tests — ⏸ Not part of this verification
- LLM Smoke Tests — ⏸ Not part of this verification
- Release — ⏸ Not part of this verification

## Notes
- Investigated recent failed runs 23584229539 and 23584229547.
- Those failures were caused by cancellation after newer main-branch runs started.
- Fixed the current CD issue by preventing the self-hosted Local Mac Docker job from running automatically on every push to `main`.
