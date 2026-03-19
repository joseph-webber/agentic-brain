# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-03-20

### Added

#### Core Framework
- Agentic brain framework with AI agent orchestration
- Multi-agent system with Crew (sequential/parallel/hierarchical execution) and Workflow (step-based with branching)
- Session management with Neo4j-backed memory persistence
- Plugin architecture with lifecycle hooks and dynamic YAML-based loading
- CLI with project scaffolding and interactive commands
- FastAPI server with WebSocket support for real-time communication

#### LLM & Streaming
- Multi-provider LLM support (Ollama, OpenAI, Anthropic)
- Real-time token streaming with Server-Sent Events (SSE)
- Configurable streaming timeouts and retry logic
- Provider-agnostic token handling

#### Knowledge & RAG
- Advanced Retrieval-Augmented Generation (RAG) system
- Semantic chunking with multiple strategies (recursive, fixed-size, sliding-window)
- Hybrid search combining semantic and keyword matching
- Learning-to-rank reranking with query relevance scoring
- Token counting and evaluation metrics

#### Analytics & Observability
- Metrics collection and usage tracking
- Neo4j-based analytics dashboard
- Comprehensive logging across all modules
- Metrics export for monitoring
- Request/response timing and diagnostics

#### Built-in Plugins
- Logging plugin with configurable levels
- Analytics plugin with auto-collection
- Moderation plugin for content safety

#### API & UX
- RESTful API endpoints for chat, sessions, analytics
- Dashboard routes for metrics visualization
- Rate limiting (60 req/min per IP)
- Input validation with Pydantic
- Comprehensive API documentation with docstrings

#### Testing & Quality
- 401+ test cases covering all major components
- Full async/await support with pytest-asyncio
- Type hints throughout codebase
- Black code formatting
- MyPy type checking
- Ruff linting

### Security

- SQL injection protection with parameterized Neo4j queries
- Rate limiting on all API endpoints
- Input validation on message, session_id, and metadata fields
- Sensitive data protection (API keys not logged)
- Content moderation plugin support
- CODEOWNERS file for approval requirements

### Fixed

- datetime.utcnow() deprecation fixed across 67 occurrences (replaced with datetime.now(timezone.utc))
- Timezone-naive/aware comparison issues in session cleanup
- Streaming timeout infinite loops (now enforced 300s with 30s socket read timeout)
- Plugin memory leaks from timestamp list accumulation (now single timestamp)
- Rate limiter reset bugs with time-window-based limiting
- Orchestration failed agent result capture
- Workflow timeout enforcement with ThreadPoolExecutor
- RAG token count returning 0 for small chunks
- Async mock issues in streaming tests
- Exception handlers now use specific exception types instead of bare Exception catches

### Improved

- All public API methods have explicit return type hints
- Exception handling with specific exception types (18 improvements)
- Documentation consolidated (removed 5 redundant root docs, centralized in docs/ directory)
- Comprehensive docstrings for all API endpoints (1,500+ lines)
- Dashboard route handlers fully documented
- CLI commands documented with examples
- Module-level documentation added
- Project structure with __all__ exports for public API declarations
- .env.example created with all config options
- .gitignore updated for environment files

### Dependencies

- neo4j >= 5.14.0 (core)
- fastapi >= 0.104.0 (optional: api)
- uvicorn[standard] >= 0.24.0 (optional: api)
- pydantic >= 2.0.0 (optional: api)
- openai >= 1.0.0 (optional: llm)
- httpx >= 0.25.0 (optional: llm)
- requests >= 2.28.0 (optional: llm)
- pytest >= 8.0.0 (optional: dev)
- pytest-asyncio >= 0.21.0 (optional: dev)
- black >= 24.0.0 (optional: dev)
- mypy >= 1.8.0 (optional: dev)
- ruff >= 0.3.0 (optional: dev)

### Documentation

- README with architecture overview
- Setup guides for Mac, Windows, Linux
- Streaming documentation with examples
- Plugin system documentation
- API documentation with docstrings
- Contributing guidelines

### License

- Project licensed under GPL-3.0 for maximum protection

[Unreleased]: https://github.com/joseph-webber/agentic-brain/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/joseph-webber/agentic-brain/releases/tag/v1.0.0
