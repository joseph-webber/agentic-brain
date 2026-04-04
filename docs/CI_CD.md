# CI/CD Guide

Continuous Integration and Deployment with GitHub Actions.

<div align="center">

[![CI](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/ci.yml)
[![Release](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/release.yml/badge.svg)](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/release.yml)
[![CodeQL](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/codeql.yml/badge.svg)](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/codeql.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025E8C?logo=dependabot&logoColor=white)](https://github.com/agentic-brain-project/agentic-brain/security/dependabot)

</div>

---

## 📋 Table of Contents

- [GitHub Actions Workflows](#github-actions-workflows)
- [Complete CI Pipeline](#complete-ci-pipeline)
- [Multi-Environment Deployment](#multi-environment-deployment)
- [Automated Releases](#automated-releases)
- [Security Scanning](#security-scanning)
- [GitHub Packages](#github-packages)
- [Secrets Management](#secrets-management)
- [Dependabot](#dependabot-integration)

---

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR | Test, lint, build |
| `release.yml` | Tag | Publish to PyPI/Docker |
| `deploy.yml` | Manual/Release | Deploy to environments |
| `codeql.yml` | Push/Schedule | Security analysis |
| `dependabot.yml` | Schedule | Dependency updates |

---

## Complete CI Pipeline

### .github/workflows/ci.yml

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:

env:
  PYTHON_VERSION: "3.11"
  NODE_VERSION: "20"

jobs:
  # =====================================================
  # LINT & FORMAT CHECK
  # =====================================================
  lint:
    name: Lint & Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install ruff black mypy
      
      - name: Ruff lint
        run: ruff check .
      
      - name: Black format check
        run: black --check .
      
      - name: MyPy type check
        run: mypy agentic_brain --ignore-missing-imports

  # =====================================================
  # UNIT TESTS
  # =====================================================
  test:
    name: Test Python ${{ matrix.python-version }} on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev,test]"
      
      - name: Run tests with coverage
        run: |
          pytest tests/ \
            --cov=agentic_brain \
            --cov-report=xml \
            --cov-report=term-missing \
            -v
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.11'
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: ./coverage.xml
          fail_ci_if_error: true

  # =====================================================
  # INTEGRATION TESTS
  # =====================================================
  integration:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: [lint, test]
    
    services:
      neo4j:
        image: neo4j:5-community
        ports:
          - 7687:7687
          - 7474:7474
        env:
          NEO4J_AUTH: neo4j/testpassword
        options: >-
          --health-cmd "cypher-shell -u neo4j -p testpassword 'RETURN 1'"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 10
      
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev,test]"
      
      - name: Run integration tests
        env:
          NEO4J_URI: bolt://localhost:7687
          NEO4J_USER: neo4j
          NEO4J_PASSWORD: testpassword
          REDIS_URL: redis://localhost:6379
          SESSION_BACKEND: redis
        run: |
          pytest tests/integration/ -v --timeout=300

  # =====================================================
  # BUILD DOCKER IMAGE
  # =====================================================
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: [test]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: agentic-brain:test
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Test Docker image
        run: |
          docker run --rm agentic-brain:test python -c "import agentic_brain; print('OK')"

  # =====================================================
  # E2E TESTS
  # =====================================================
  e2e:
    name: E2E Tests
    runs-on: ubuntu-latest
    needs: [build]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Start services
        run: docker-compose -f docker-compose.test.yml up -d
      
      - name: Wait for services
        run: |
          timeout 60 bash -c 'until curl -s http://localhost:8000/health; do sleep 2; done'
      
      - name: Run E2E tests
        run: |
          pip install pytest requests
          pytest tests/e2e/ -v
      
      - name: Stop services
        if: always()
        run: docker-compose -f docker-compose.test.yml down -v

  # =====================================================
  # DOCUMENTATION
  # =====================================================
  docs:
    name: Build Documentation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install MkDocs
        run: pip install mkdocs mkdocs-material mkdocstrings[python]
      
      - name: Build docs
        run: mkdocs build --strict
      
      - name: Upload docs artifact
        uses: actions/upload-artifact@v4
        with:
          name: docs
          path: site/
```

---

## Multi-Environment Deployment

### .github/workflows/deploy.yml

```yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        type: choice
        options:
          - staging
          - production
      version:
        description: 'Version to deploy (leave empty for latest)'
        required: false
        type: string
  
  release:
    types: [published]

jobs:
  # =====================================================
  # DETERMINE VERSION
  # =====================================================
  setup:
    name: Setup Deployment
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.version }}
      environment: ${{ steps.env.outputs.environment }}
    
    steps:
      - name: Determine version
        id: version
        run: |
          if [ "${{ github.event_name }}" = "release" ]; then
            echo "version=${{ github.event.release.tag_name }}" >> $GITHUB_OUTPUT
          elif [ -n "${{ inputs.version }}" ]; then
            echo "version=${{ inputs.version }}" >> $GITHUB_OUTPUT
          else
            echo "version=latest" >> $GITHUB_OUTPUT
          fi
      
      - name: Determine environment
        id: env
        run: |
          if [ "${{ github.event_name }}" = "release" ]; then
            echo "environment=production" >> $GITHUB_OUTPUT
          else
            echo "environment=${{ inputs.environment }}" >> $GITHUB_OUTPUT
          fi

  # =====================================================
  # DEPLOY TO STAGING
  # =====================================================
  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: setup
    if: needs.setup.outputs.environment == 'staging'
    environment:
      name: staging
      url: https://staging.agentic-brain.dev
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Deploy to Railway (Staging)
        uses: bervProject/railway-deploy@v0.1.1
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN_STAGING }}
          service: agentic-brain
      
      - name: Smoke test
        run: |
          timeout 120 bash -c 'until curl -sf https://staging.agentic-brain.dev/health; do sleep 5; done'
      
      - name: Notify Slack
        uses: slackapi/slack-github-action@v1.25.0
        with:
          payload: |
            {
              "text": "✅ Deployed ${{ needs.setup.outputs.version }} to staging"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}

  # =====================================================
  # DEPLOY TO PRODUCTION
  # =====================================================
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: setup
    if: needs.setup.outputs.environment == 'production'
    environment:
      name: production
      url: https://api.agentic-brain.dev
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      # Option 1: Deploy to Fly.io
      - name: Deploy to Fly.io
        uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
      
      # Option 2: Deploy to GCP Cloud Run
      # - name: Deploy to Cloud Run
      #   uses: google-github-actions/deploy-cloudrun@v2
      #   with:
      #     service: agentic-brain
      #     region: australia-southeast1
      #     image: ghcr.io/agentic-brain-project/agentic-brain:${{ needs.setup.outputs.version }}
      
      # Option 3: Deploy to AWS ECS
      # - name: Deploy to ECS
      #   uses: aws-actions/amazon-ecs-deploy-task-definition@v1
      #   with:
      #     task-definition: ecs-task-definition.json
      #     service: agentic-brain-service
      #     cluster: agentic-brain-cluster
      
      - name: Health check
        run: |
          timeout 180 bash -c 'until curl -sf https://api.agentic-brain.dev/health; do sleep 5; done'
      
      - name: Create deployment record
        uses: chrnorm/deployment-action@v2
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          environment: production
          ref: ${{ github.sha }}
      
      - name: Notify Slack
        uses: slackapi/slack-github-action@v1.25.0
        with:
          payload: |
            {
              "text": "🚀 Deployed ${{ needs.setup.outputs.version }} to production!"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Automated Releases

### .github/workflows/release.yml

```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to release (e.g., 1.2.3)'
        required: true
        type: string
      prerelease:
        description: 'Is this a pre-release?'
        required: false
        type: boolean
        default: false

jobs:
  # =====================================================
  # BUILD & TEST
  # =====================================================
  test:
    name: Test Before Release
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e ".[dev,test]"
      
      - name: Run tests
        run: pytest tests/ -v

  # =====================================================
  # BUILD PYTHON PACKAGE
  # =====================================================
  build-python:
    name: Build Python Package
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install build tools
        run: pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Check package
        run: twine check dist/*
      
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: python-package
          path: dist/

  # =====================================================
  # BUILD DOCKER IMAGE
  # =====================================================
  build-docker:
    name: Build Docker Images
    runs-on: ubuntu-latest
    needs: test
    permissions:
      contents: read
      packages: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Extract version
        id: version
        run: |
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            echo "version=${{ inputs.version }}" >> $GITHUB_OUTPUT
          else
            echo "version=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT
          fi
      
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ghcr.io/agentic-brain-project/agentic-brain:${{ steps.version.outputs.version }}
            ghcr.io/agentic-brain-project/agentic-brain:latest
            josephwebber/agentic-brain:${{ steps.version.outputs.version }}
            josephwebber/agentic-brain:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
          labels: |
            org.opencontainers.image.version=${{ steps.version.outputs.version }}
            org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}

  # =====================================================
  # PUBLISH TO PYPI
  # =====================================================
  publish-pypi:
    name: Publish to PyPI
    runs-on: ubuntu-latest
    needs: [build-python, build-docker]
    environment:
      name: pypi
      url: https://pypi.org/project/agentic-brain/
    permissions:
      id-token: write  # For trusted publishing
    
    steps:
      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: python-package
          path: dist/
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          print-hash: true

  # =====================================================
  # CREATE GITHUB RELEASE
  # =====================================================
  create-release:
    name: Create GitHub Release
    runs-on: ubuntu-latest
    needs: [publish-pypi]
    permissions:
      contents: write
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: python-package
          path: dist/
      
      - name: Generate changelog
        id: changelog
        uses: mikepenz/release-changelog-builder-action@v4
        with:
          configuration: ".github/changelog-config.json"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: ${{ github.ref_name }}
          name: Release ${{ github.ref_name }}
          body: ${{ steps.changelog.outputs.changelog }}
          prerelease: ${{ inputs.prerelease || false }}
          files: dist/*
          generate_release_notes: true
```

---

## Security Scanning

### .github/workflows/codeql.yml

```yaml
name: CodeQL Security Analysis

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write
    
    strategy:
      fail-fast: false
      matrix:
        language: [python, javascript]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
          queries: security-extended
      
      - name: Autobuild
        uses: github/codeql-action/autobuild@v3
      
      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"

  # =====================================================
  # DEPENDENCY SCANNING
  # =====================================================
  dependency-scan:
    name: Dependency Vulnerability Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install safety
        run: pip install safety pip-audit
      
      - name: Safety check
        run: safety check --json --output safety-report.json || true
      
      - name: Pip audit
        run: pip-audit --output pip-audit-report.json || true
      
      - name: Upload reports
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: |
            safety-report.json
            pip-audit-report.json

  # =====================================================
  # SECRET SCANNING
  # =====================================================
  secret-scan:
    name: Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Gitleaks scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  # =====================================================
  # CONTAINER SCANNING
  # =====================================================
  container-scan:
    name: Container Vulnerability Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build image
        run: docker build -t agentic-brain:scan .
      
      - name: Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: agentic-brain:scan
          format: sarif
          output: trivy-results.sarif
      
      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: trivy-results.sarif
```

---

## GitHub Packages

### Publishing Docker Images

```yaml
# Automatically publish to ghcr.io on release
name: Publish Docker

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=sha
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

### Pulling from GitHub Packages

```bash
# Authenticate
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull image
docker pull ghcr.io/agentic-brain-project/agentic-brain:latest

# Run
docker run -p 8000:8000 ghcr.io/agentic-brain-project/agentic-brain:latest
```

---

## Secrets Management

### Required Secrets

| Secret | Purpose | Where to Get |
|--------|---------|--------------|
| `CODECOV_TOKEN` | Coverage upload | codecov.io |
| `DOCKERHUB_USERNAME` | Docker Hub | Docker Hub account |
| `DOCKERHUB_TOKEN` | Docker Hub | Docker Hub → Security |
| `PYPI_API_TOKEN` | PyPI publishing | pypi.org → API tokens |
| `FLY_API_TOKEN` | Fly.io deploy | `fly auth token` |
| `RAILWAY_TOKEN` | Railway deploy | Railway dashboard |
| `SLACK_WEBHOOK` | Notifications | Slack App config |
| `GCP_SA_KEY` | Google Cloud | GCP IAM |
| `AWS_ACCESS_KEY_ID` | AWS | AWS IAM |
| `AWS_SECRET_ACCESS_KEY` | AWS | AWS IAM |
| `AZURE_CREDENTIALS` | Azure | Azure AD |

### Setting Secrets

```bash
# Using GitHub CLI
gh secret set DOCKERHUB_TOKEN --body "your-token"
gh secret set FLY_API_TOKEN --body "your-token"

# For environments
gh secret set FLY_API_TOKEN --env production --body "your-token"
```

### Environment Protection Rules

```yaml
# Settings → Environments → production
# - Required reviewers: 1
# - Wait timer: 5 minutes
# - Deployment branches: main only
```

---

## Dependabot Integration

### .github/dependabot.yml

```yaml
version: 2

updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    reviewers:
      - "agentic-brain-project"
    labels:
      - "dependencies"
      - "python"
    groups:
      python-minor-updates:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    reviewers:
      - "agentic-brain-project"
    labels:
      - "dependencies"
      - "github-actions"

  # Docker
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
    reviewers:
      - "agentic-brain-project"
    labels:
      - "dependencies"
      - "docker"

  # npm (for docs/frontend)
  - package-ecosystem: "npm"
    directory: "/docs"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "javascript"
```

### Auto-Merge Dependabot PRs

```yaml
# .github/workflows/dependabot-auto-merge.yml
name: Dependabot Auto-Merge

on: pull_request

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.actor == 'dependabot[bot]'
    steps:
      - name: Dependabot metadata
        id: metadata
        uses: dependabot/fetch-metadata@v2
        with:
          github-token: "${{ secrets.GITHUB_TOKEN }}"
      
      - name: Auto-merge minor/patch updates
        if: steps.metadata.outputs.update-type == 'version-update:semver-minor' || steps.metadata.outputs.update-type == 'version-update:semver-patch'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Quick Commands

```bash
# Run CI locally (using act)
act push

# Test specific workflow
act -j test

# Manually trigger deployment
gh workflow run deploy.yml -f environment=staging

# View workflow runs
gh run list

# View specific run
gh run view <run-id>

# Download artifacts
gh run download <run-id>

# Re-run failed jobs
gh run rerun <run-id> --failed
```

---

## Pipeline Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Push/PR   │───▶│    Lint     │───▶│    Test     │
└─────────────┘    └─────────────┘    └─────────────┘
                                            │
                                            ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Deploy    │◀───│   Release   │◀───│    Build    │
│ (Staging)   │    │  (Tag/PyPI) │    │  (Docker)   │
└─────────────┘    └─────────────┘    └─────────────┘
       │
       ▼
┌─────────────┐    ┌─────────────┐
│  Approval   │───▶│   Deploy    │
│             │    │(Production) │
└─────────────┘    └─────────────┘
```

---

## See Also

- [DEPLOYMENT.md](./DEPLOYMENT.md) — Cloud deployment options
- [SECURITY.md](./SECURITY.md) — Security practices
- [TESTING.md](./TESTING.md) — Testing guide
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

**Last Updated**: 2026-03-22

---

## BrainChat Swift CI

The BrainChat Swift pipeline lives in `.github/workflows/brainchat.yml`.

### Triggers

- Pushes that change `apps/BrainChat/**`
- Pushes that change `.github/workflows/brainchat.yml`
- Pull requests that change `apps/BrainChat/**`

### Job flow

The `build-and-test` job runs on `macos-latest` and:

1. Checks out the repository
2. Installs Swift 5.9
3. Builds BrainChat in release mode
4. Runs the Swift test suite in parallel
5. Performs a lightweight security audit for obvious hardcoded secrets
6. On `main`, builds a macOS app bundle and uploads it as a GitHub Actions artifact

### Artifact

When the workflow runs on `main`, it uploads:

- `BrainChat-macOS` from `apps/BrainChat/BrainChat.app`
