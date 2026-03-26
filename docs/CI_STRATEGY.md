# CI/CD Strategic Review & Plan

**Date:** 2026-03-22
**Status:** DRAFT
**Author:** CI/CD Architect Agent (Iris Lumina)

## 1. Executive Summary

The current CI/CD pipeline (`.github/workflows/ci.yml`) is suffering from **fragility due to inconsistency**. We have two competing ways of running tests:
1.  **Bare-metal `test` job:** Installs dependencies on the runner, starts services (Neo4j, Redis, Redpanda) via disjointed scripts and Docker commands.
2.  **Containerized `docker-test` job:** Uses `docker-compose.test.yml` with proper healthchecks and dependency management.

**Recommendation:** Shift the primary integration testing strategy to **Docker Compose**. Keep the bare-metal job ONLY for fast unit tests and linting.

## 2. Current State Analysis

### Strengths
*   **Docker Compose Setup:** `docker-compose.test.yml` is well-configured with `tmpfs` for performance and proper healthchecks.
*   **Pyproject Configuration:** `pyproject.toml` correctly defines a `test` extra with necessary dependencies.
*   **Matrix Testing:** Testing across Python 3.11-3.13 is good.

### Weaknesses (Root Causes of Failure)
*   **Service Startup Fragility:** The `test` job manual startup scripts for Redpanda and Redis are prone to race conditions and timeouts. They duplicate logic handled better by Docker Compose.
*   **Test Selection Bleed:** The `pytest tests/` command in the `test` job runs *everything*. Without strict marker exclusion, it attempts to run integration tests (requiring services) in an environment where services might not be ready or configured identically to dev.
*   **Dependency Drift:** The `test` job installs `.[test,dev]` on the runner, while `docker-test` builds a Docker image. These environments can drift, leading to "works on my machine, fails in CI" issues.
*   **Noise:** `continue-on-error: true` for linting/security scanners creates log noise that gets ignored.

## 3. Strategic Recommendations

### A. Test Organization (Pytest)
We must strictly respect the testing pyramid:

1.  **Unit Tests (`@pytest.mark.unit` or default):**
    *   **Constraint:** NO external services (mock Redis, Neo4j, LLMs).
    *   **Environment:** GitHub Actions Runner (Bare Metal).
    *   **Goal:** Fast feedback (< 2 mins).

2.  **Integration Tests (`@pytest.mark.integration`):**
    *   **Constraint:** Real services allowed (Dockerized).
    *   **Environment:** Docker Compose (`docker-test` job).
    *   **Goal:** Reliability and correctness.

3.  **E2E Tests (`@pytest.mark.e2e`):**
    *   **Constraint:** Full system (CLI, Installer).
    *   **Environment:** OS Matrix (Ubuntu, MacOS).

### B. CI Workflow Restructuring

Refactor `ci.yml` into clearly defined stages:

1.  **Static Analysis (Fastest):**
    *   Black, Ruff, Mypy.
    *   Fail FAST. No `continue-on-error` for formatting/syntax.

2.  **Unit Tests (Fast):**
    *   Run `pytest -v -m "not integration and not requires_docker" tests/`.
    *   Uses GitHub Services (optional) or just mocks.

3.  **Integration Tests (Robust):**
    *   Run `docker compose -f docker-compose.test.yml run test`.
    *   This replaces the fragile `test` job service setup.

### C. Service Handling
*   **Redis/Neo4j/Kafka:** DO NOT install `redis-tools` or run `docker run` commands in the CI YAML steps.
*   **Use Compose:** The `docker-compose.test.yml` file is the Source of Truth for the test environment.

### D. Policy Changes
*   **Linting:** Enforce passing lint checks. If a rule is too strict, disable it in `pyproject.toml`, don't ignore failure in CI.
*   **Markers:** Enforce use of `@pytest.mark.integration` for ANY test touching a socket.

## 4. Implementation Plan

1.  **Phase 1 (Immediate):**
    *   Update `ci.yml` to split "Unit" and "Integration".
    *   Modify `test` job to run ONLY unit tests (skip `integration` marker).
    *   Make `docker-test` the primary blocker for merging (Integration).

2.  **Phase 2 (Cleanup):**
    *   Remove custom Redpanda/Redis startup scripts from `ci.yml`.
    *   Remove `services:` block from `ci.yml` (since Unit tests shouldn't need them, and Integration uses Compose).

3.  **Phase 3 (Optimization):**
    *   Cache Docker layers for the test image.

## 5. Summary
Stop hacking the YAML file. Trust Docker Compose for complex environments. Keep the base runner simple for unit tests.
