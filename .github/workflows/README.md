# CI Workflows

Main workflows that run on every push:
- ci.yml: Main CI (lint, test, build)
- security.yml: Security scanning
- license-check.yml: License compliance

Release workflows (workflow_dispatch only):
- release.yml: Python package release
- brainchat-release.yml: BrainChat macOS release
- cd.yml: Docker deployment

