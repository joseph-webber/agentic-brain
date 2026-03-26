# Agentic Brain Release Checklist

**Version**: 2.11.0 → 3.0.0 (Major Release)  
**License**: Apache 2.0  
**Mission**: Making computers accessible for everyone

---

## Pre-Release Audit

### Code Quality
- [x] All code uses professional terminology (Ludicrous mode renamed to Turbo)
- [x] No playful/internal naming (e.g., Ludicrous mode)
- [ ] Type hints on all public functions
- [ ] Docstrings on all public classes/functions
- [ ] No hardcoded credentials or secrets
- [ ] All secrets from environment variables

### Documentation
- [x] README updated with all features (counts, modes, providers, and voice system verified)
- [x] Python version badge correct (3.11+)
- [x] GraphRAG prominently featured
- [x] Hardware acceleration documented
- [ ] API reference complete
- [x] Examples are professional and SFW

### Testing
- [ ] All tests pass locally
- [ ] CI pipeline green
- [ ] Coverage > 80%
- [ ] Integration tests pass
- [ ] No private data in test fixtures

### Security
- [ ] No private data leaked
- [ ] No personal emails/credentials
- [ ] Secrets management documented
- [ ] Security policy in place
- [ ] Dependencies audited

### Accessibility
- [ ] CLI accessible (screen reader friendly)
- [ ] Error messages clear
- [ ] Documentation accessible
- [ ] Examples work for all users

---

## Modules Status

| Module | Status | Notes |
|--------|--------|-------|
| router | ✅ | LLM routing, 18 models |
| rag | ✅ | GraphRAG, vectors, Neo4j |
| smart_router | 🔄 | Needs professional rename |
| chat | ✅ | Chatbot with slash commands |
| cli | ✅ | Full command set |
| api | ✅ | FastAPI server |
| durability | ✅ | Event store, retry logic |
| auth | ✅ | JWT, API keys |
| transport | ✅ | WebSocket, SSE |
| memory | ✅ | Neo4j persistence |

---

## Release Steps

1. [ ] Rename smart_router to `parallel_router` or `provider_pool`
2. [ ] Run full test suite
3. [ ] Update CHANGELOG.md
4. [ ] Version bump to 3.0.0
5. [ ] Build and test package
6. [ ] Publish to PyPI
7. [ ] Create GitHub release
8. [ ] Update documentation site
9. [ ] Announce on social media

