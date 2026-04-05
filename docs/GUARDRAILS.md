# Guardrails and Safety System

This document describes the simple guardrails added for agentic-brain.

Components:

- InputValidator: validates incoming text for length, PII, toxicity.
- PiiDetector: regex-based PII detection and masking.
- ToxicityDetector: keyword-based toxicity detection and sanitization.
- HallucinationDetector: heuristic detection for hedging, numeric claims, absolutes.
- OutputFilter: applies profanity masking and PII masking to outputs.
- PolicyEnforcer: composes detectors and filters to enforce policies.

Limitations:
- These components are intentionally simple and pattern-based for tests.
- Production systems should integrate ML detectors and external DLP services.

Usage examples are provided in code and tests.
