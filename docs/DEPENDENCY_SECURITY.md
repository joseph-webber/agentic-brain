Dependency Security and Audit
=============================

This document describes the dependency security controls used by Agentic Brain.

Running the audit locally
-------------------------

Install the audit helpers (recommended in a venv):

python -m pip install --upgrade pip
python -m pip install pip-audit safety pip-licenses pipdeptree

Run the audit CLI:

agentic audit-deps --output reports/dependency_audit.json

Or run the module directly:

python -m agentic_brain.security.dependency_audit --output reports/dependency_audit.json

CI integration
--------------

The project's CI runs pip-audit and safety during the lint job and will fail if
critical vulnerabilities are detected. Dependabot is configured to open weekly
pull requests for direct Python dependencies.

Handling results
----------------

 - pip-audit: Consult the CVE entries and upgrade pins or apply mitigations
 - safety: See advisory details; patch or upgrade accordingly
 - pip-licenses: Verify license compatibility and consult LEGAL if needed
 - pipdeptree: Use this to identify transitive packages that require upgrades

If an automated fix is available, prefer Dependabot PRs. For complex cases,
create a human-reviewed PR that updates pinned versions and runs the test suite.
