# Penetration Testing

Run the suite:

```bash
agentic-brain security-scan
```

What it checks:

- SQL injection
- Cypher injection
- Prompt injection
- Path traversal
- Command injection
- XSS safeguards
- Boundary handling
- Auth bypass attempts
- Rate-limit evasion
- Resource exhaustion

Pytest entry:

```bash
python -m pytest tests/test_security/test_pentest.py -v
```

The CLI exits non-zero if any attack vector is accepted.
