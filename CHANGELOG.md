# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.22.0] - 2026-03-29

### Added

- **CI/CD Workflows** - GitHub Actions pipelines for automated quality
  - `staging.yml` - Pre-release validation pipeline
  - `release.yml` - Automated release on version tags

### Improved

- **Privacy Cleanup** - Full open source readiness pass
  - 407 privacy violations fixed across codebase
  - 399 copyright headers updated for open source
  - Author info anonymized to "Agentic Brain Contributors"
  - Examples and docs scrubbed of personal references
- **Voice Serialization** - Improved queue-based speech reliability
- **Default Voice** - Changed from Karen to Samantha for open source neutrality

### Fixed

- Voice mocking in tests for CI compatibility
- Hardcoded paths removed from CI tests
- Linting fixes across test suite

---

## [2.21.0] - 2026-03-29

### Added

- **Production Clock System** - Thread-safe singleton for correct dates (never stale!)
  - `src/agentic_brain/utils/clock.py` - Clock singleton with Adelaide timezone
  - `src/agentic_brain/mcp/clock_server.py` - 9 MCP tools for date/time
  - `config/timezone.yaml` - Adelaide timezone configuration with 2026 year awareness
  - `docs/CLOCK.md` - Usage documentation

- **Voice Phase 3** - Enhanced voice system with quality improvements
  - `src/agentic_brain/voice/serializer.py` - Queue-based non-overlapping speech
  - `src/agentic_brain/voice/lady_voices.py` - Lady personalities module
  - `src/agentic_brain/voice/quality_gate.py` - CI/CD voice validation
  - `src/agentic_brain/voice/emotions.py` - Expressive speech support
  - `src/agentic_brain/voice/voice_cloning.py` - Voice cloning foundation

- **Audio System Enhancements**
  - `src/agentic_brain/audio/audio_normalizer.py` - Consistent volume levels
  - `src/agentic_brain/audio/quality_analyzer.py` - Voice output analysis
  - `src/agentic_brain/audio/sound_themes.py` - Theme-based sound selection
  - 10 new earcon WAV files for audio feedback

### Improved

- Voice resilient fallback chain (5 layers - never fails)
- Regional voice expressions (Adelaide, Melbourne, Sydney)
- Voice CI tests (23 tests, all passing)

### Documentation

- `docs/voice/TECHNICAL_DEBT.md` - Voice overlap flagged for future rebuild
- `docs/voice/CLONING.md` - Voice cloning documentation
- `docs/voice/EMOTIONS.md` - Emotion system documentation
- `docs/voice/LADIES.md` - Lady voices documentation

## [2.17.0] - 2026-03-28

### Added

- `docs/WOOCOMMERCE.md` - Comprehensive WooCommerce integration guide
- `docs/WORDPRESS_PLUGIN.md` - Full WordPress plugin documentation
- `docs/COMMERCE_API.md` - Complete API reference for WooCommerce & WordPress
- `docs/COMMERCE_CHATBOT.md` - Commerce chatbot capabilities guide
- `plugins/wordpress/agentic-brain/README.md` - Plugin installation guide

### Improved

- README.md now prominently features e-commerce capabilities
- Commerce module properly documented (was 15,000 lines with no docs!)
- Added code examples for all commerce operations

### Documentation

- Full coverage of WooCommerce API (products, orders, customers, coupons, shipping, taxes)
- Full coverage of WordPress API (posts, pages, media, users, taxonomies)
- Chatbot examples for natural language store management
- Plugin developer guide with hooks and filters

## [2.16.0] - 2026-03-30

### Added

- **🧠 GraphRAG Upgrades**
  - Real MLX embeddings throughout `graph.py`, `graph_rag.py`, and `knowledge_extractor.py` — Apple Silicon deployments now generate production vectors locally.
  - Neo4j GDS Leiden community detection is the documented default via `GraphRAGConfig.community_algorithm`.
  - Hybrid retrieval now surfaces reciprocal-rank fusion (RRF) metadata (`vector_rank`, `keyword_rank`, `graph_rank`, `rrf_score`) in every result.
  - Async Neo4j driver path is documented with examples plus guidance in `docs/GRAPHRAG.md` and the new `docs/neo4j.md`.
  - Transaction retry helpers (`resilient_query_sync` and async equivalents) highlighted so every custom Cypher call inherits the same resilience profile.

### Fixed

- **⚡ N+1 Query Fixes**
  - Documented the new `UNWIND` batching pipelines across GraphRAG modules to make the ingest behavior transparent.

### Improved

- **📚 Documentation**
  - README GraphRAG section now highlights the 2.16.0 improvements and links to deeper documentation.
  - `docs/GRAPHRAG.md` expanded with sections on MLX embeddings, RRF scoring, async Neo4j usage, and transaction retries.
  - Added `docs/neo4j.md` as the canonical integration guide covering community detection, hybrid search, and operational best practices.

## [2.15.0] - 2026-03-28

### Added

- **🧠 GraphRAG Improvements**
  - GDS community detection via Louvain algorithm in `graph_rag.py` for entity clustering
  - Hybrid search with Reciprocal Rank Fusion (RRF) in `hybrid.py` — combines vector and keyword results
  - `MLXEmbeddings` provider in `rag/embeddings.py` — Apple Silicon native embedding generation
  - Semantic router (`SemanticRouter`) for intelligent query routing across RAG strategies

### Fixed

- **⚡ N+1 Query Fixes**
  - Batched `UNWIND` for entity extraction in `neo4j_memory.py` — eliminates per-entity round trips
  - `embed_batch()` in `UnifiedMemory` — batch embedding generation instead of one-at-a-time
  - Eager fetching patterns in memory and pooling modules

- **🔧 Async/Sync Fixes**
  - Synchronous wrappers for async memory operations in `unified.py`
  - Correct event loop handling across memory and RAG pipelines

- **🔍 Router Fixes**
  - Semantic router route matching with cached embeddings
  - Proper fallback when no route matches query threshold

### Improved

- **📈 Index Improvements**
  - Vector and fulltext index strategies in `graph_rag.py`
  - Search strategy enum (VECTOR, HYBRID, GRAPH, FULLTEXT) for flexible retrieval

- **📦 Office Document Processing** (Phase 5)
  - 15 new office format loaders (Word, Excel, PowerPoint, Pages, Keynote, Numbers, RTF, ODF, images)
  - Layout analysis, table extraction, unified markdown/JSON export
  - Accessibility module for document processing

- **🧠 Enhanced Memory System**
  - Mem0-inspired memory patterns with zero external dependencies
  - Chonkie-powered fast chunking for RAG pipelines with token-accuracy benchmarks

### Removed

- Removed 14K-line `_monolith_backup.py` dead code
- Removed `docling` dependency — replaced by 102 built-in loaders
- Removed `mem0ai` dependency — replaced by built-in `UnifiedMemory`

## [2.12.0] - 2026-03-26

### Added

- **🛍️ Commerce Module** (`agentic_brain.commerce`)
  - `WooCommerceAgent` — async-first agent for WooCommerce REST API (products, orders, customers)
  - Full CRUD: `get_products()`, `get_orders()`, `get_customers()`, `create_product()`, `update_order()`, and more
  - Synchronous wrappers (`get_products_sync()`, `get_product_sync()`) for non-async usage
  - `search_products(query)` for RAG pipeline integration
  - Pydantic v2 data models: `WooProduct`, `WooOrder`, `WooCustomer`, `WooOrderItem`, `WooCoupon`, and more
  - `WordPressClient` — full WordPress REST API client (posts, pages, media, auth)
  - `WooCommerceChatbot` — AI storefront assistant for admin, customer, and guest flows with WordPress widgets and shortcodes
  - WordPress plugin helpers: `generate_wp_widget_plugin`, `generate_wp_hooks_plugin`, and `WordPressChatWidgetConfig` for drop-in chat widgets
  - `WooCommerceAnalytics` — high-level sales, funnel, CLV, and inventory reports for stores
  - Payments, shipping, inventory, and webhook facades wired into `CommerceHub` for a single integration surface
  - `from agentic_brain.commerce import WooCommerceAgent` now works at top level
  - `from agentic_brain import WooCommerceAgent` also works (exported from package root)

- **🎪 Demo environment** (`demo/`)
  - End-to-end demo stack with WordPress + WooCommerce + API via `demo/docker-compose.demo.yml`
  - One-command scripts: `demo/setup-demo.sh`, `demo/verify-demo.sh`, `demo/cleanup-demo.sh`
  - CI demo workflow (`.github/workflows/demo.yml`) can run automatically on release publish

- **🐳 Docker deployment** (`docker/` + root `docker-compose*.yml`)
  - Dev/test/prod compose files + demo compose for consistent deployments
  - Docker-first deployment docs and environment templates

- **📚 RAG Improvements**
  - `WooCommerceLoader` now available in `agentic_brain.rag.loaders` for bulk document ingestion
  - Graph method accuracy improvements for ingest pipelines
  - Improved `add_to_graph()` error handling with structured fallback

- **🔢 Accurate loader count** — updated package description to reflect verified 155+ RAG loader classes

### Fixed

- `commerce/__init__.py` was missing `WooCommerceAgent` and `WooBaseModel` exports
- Top-level `__init__.py` was missing `WooCommerceAgent` and `WooBaseModel` in imports and `__all__`
- README.md compliance language: changed "SOC 2 Type II Certified" → "SOC 2 Type II Ready" (accurate pre-certification status)
- `pyproject.toml` description updated from "54+ integrations" to "155+ RAG loaders" for consistency with README
- Code example formatting fixes across documentation

### Changed

- Package description now reads "155+ RAG loaders" (verified: 155 loader classes defined) instead of "54+ integrations"
- Compliance badge and trust section now accurately state SOC 2 "Ready" (not "Certified")

## [2.11.0] - 2026-03-23

### Added

- **🔐 Full LDAP/Active Directory Authentication**
  - Complete LDAPAuthProvider implementation with ldap3 library
  - Support for both Active Directory and OpenLDAP
  - Group membership extraction with nested group resolution (AD)
  - Flexible group-to-role mapping configuration
  - JWT session token generation after authentication
  - Group caching with configurable TTL (default 5 minutes)
  - Connection test diagnostics for troubleshooting
  - `pip install agentic-brain[enterprise]` for LDAP support

- **🔄 Temporal.io Compatibility Layer** (100% API compatible!)
  - Drop-in replacement for temporalio SDK - just change your imports
  - Full workflow and activity decorators: `@workflow.defn`, `@workflow.run`, `@activity.defn`
  - Workflow utilities: `workflow.now()`, `workflow.uuid4()`, `workflow.random()`, `workflow.sleep()`
  - NEW: `workflow.execute_local_activity()` - run activities in-process
  - NEW: `workflow.wait_condition()` - wait for conditions with timeout
  - Client with `execute_workflow()`, `get_workflow_handle()`, `start_workflow()`
  - WorkflowHandle with `result()`, `cancel()`, `terminate()`, `signal()`, `query()`
  - Worker class with activity and workflow registration
  - Testing utilities: `WorkflowEnvironment`, `ActivityEnvironment`
  - Comprehensive migration guide: `docs/TEMPORAL_MIGRATION_GUIDE.md`

- **🛡️ Complete Durability Module** (27 enterprise-grade modules)
  - **Core**: Events, State Machine, Recovery, Checkpoints, Replay
  - **Workflow Control**: Signals, Queries, Updates, Timers, Cancellation
  - **Activities**: Heartbeats, Timeouts, Local Activities, Async Completion
  - **Advanced**: Child Workflows, Continue-as-New, Sagas, Versioning
  - **Infrastructure**: Task Queues, Worker Pools, Namespaces, Search Attributes
  - **Serialization**: Payload Converters, Memos
  - **Enterprise**: Interceptors, Schedules, Dashboard
  - All with production-ready error handling and retry logic

- **📊 GraphQL API Layer** (Strawberry integration)
  - Full GraphQL schema with queries, mutations, subscriptions
  - Workflow management: start, signal, query, cancel
  - Activity status and result retrieval
  - Real-time subscriptions for workflow updates

- **📁 CMIS Content Management** (Enterprise document management)
  - CMIS 1.1 compliant with AtomPub binding
  - Repository info, folder browsing, document management
  - Check-in/check-out, versioning, content streaming
  - Query language support (CMIS-QL)

- **🗄️ SQLAlchemy Database Loaders** (Connection pooling included)
  - PostgreSQL, MySQL, SQLite, Oracle support
  - Automatic connection pooling with health checks
  - Transaction management and query builder
  - Async support with proper cleanup

- **🔮 Semantic Caching** (Redis-backed with embeddings)
  - Semantic similarity matching for cache hits
  - Configurable similarity thresholds
  - TTL-based expiration with LRU eviction
  - Cost tracking and analytics

- **🧪 Comprehensive Test Coverage**
  - 48 unit tests for Temporal compatibility
  - 24 E2E tests for workflow scenarios
  - 2,949 total tests passing
  - 0 failures, 233 skipped (E2E requiring full environment)

### Changed
- Updated test count: 2,876 → 2,970 tests (21 new LDAP tests)
- LLMRouter now supports pool metrics with `get_pool_stats()`
- Improved error messages with actionable guidance

### Fixed
- **Deprecated `datetime.utcnow()` calls** - Fixed 272 calls across 31 files
  - Now uses `datetime.now(timezone.utc)` (Python 3.12+ compatible)
- **Blocking `time.sleep()` in async code** - Fixed 4 calls in recovery/retry modules
  - Now uses async-safe sleep helper that detects context
- `ContinueAsNewError` now supports both positional args and `args=()` keyword
- `workflow.sleep()` works outside workflow context (for testing)
- `activity.Info` dataclass field ordering for Python 3.10 compatibility
- Black formatting applied to 55 files for consistency

## [2.10.0] - 2026-03-22

### Added
- **Windows Installer Improvements**
  - Auto-detects OS, Python version, and hardware capabilities
  - Supports Debian, RedHat, Arch, macOS (Intel + ARM), and Windows
  - Idempotent setup - safe to run multiple times
  - PowerShell-native installer with proper logging
  - Docker-only install path option
  - SSL trusted-host defaults for seamless setup

- **Docker Management Menu**
  - Easy Docker container lifecycle management
  - Neo4j setup and teardown commands
  - Volume and network management
  - Health checks and diagnostics

- **Free LLM Providers Support**
  - Groq API (free tier available)
  - Google Generative AI
  - Together AI
  - xAI Grok support
  - No API key required for local Ollama

- **Automatic Port Detection**
  - Smart port selection for Neo4j, services
  - Conflict resolution and logging
  - Simplified configuration

- **Neo4j Optional**
  - Core framework works without Neo4j
  - Neo4j now an optional dependency for advanced memory features
  - Chat and RAG functional with or without database
  - Helpful error messages guide setup

- **28 New RAG Loaders** (54 total integrations)
  - Payment Gateways: Stripe, PayPal, Square, Afterpay, Braintree
  - E-Commerce: Shopify, WooCommerce, BigCommerce, Magento
  - Australian Accounting: MYOB, Xero, QuickBooks
  - Australian HR: Employment Hero, Deputy
  - Cloud Storage: Azure Blob, GCS, MinIO
  - Databases: PostgreSQL, MySQL, Elasticsearch, Redis, Oracle
  - Enterprise: SAP, ServiceNow, Workday, Dynamics 365, Zoho, Jira Service Desk

### Changed
- Updated integrations count: 26 → 54
- All loaders follow BaseLoader pattern with authenticate(), load_document(), load_folder(), and search() methods
- Installation now more user-friendly with guided setup
- Error messages now more helpful with actionable guidance

## [2.8.0] - 2026-03-22

### Added
- **Enterprise Authentication Module**
  - JWT authentication (HS512 algorithm)
  - OAuth2/OIDC with JWKS support
  - Basic auth for microservices
  - Session auth with remember-me tokens
  - Role decorators: `@require_role`, `@require_authority`, `@pre_authorize`
  - Thread-safe and async-safe security context
  - See `docs/AUTHENTICATION.md` for full documentation

- **Enterprise Secrets Management**
  - HashiCorp Vault backend (KV v2)
  - AWS Secrets Manager backend
  - Azure Key Vault backend
  - GCP Secret Manager backend
  - Apple Keychain backend (macOS)
  - Environment variable and .env file backends
  - Unified interface with fallback chains

- **15 New RAG Loaders** (26 total integrations)
  - Cloud Storage: Dropbox, Box, OneDrive, SharePoint
  - Communication: Discord, Microsoft Teams
  - Project Management: Jira, Asana, Trello, Airtable
  - CRM & Support: HubSpot, Salesforce, Zendesk, Intercom, Freshdesk

- **Australian Compliance Section**
  - Privacy Act 1988, Essential Eight, AML/CTF
  - NDIS Quality & Safeguards, Aged Care Act 2024
  - APAC: Singapore MAS TRM, NZ Privacy Act 2020

- **Professional Networking Examples**
  - Enterprise talent network (professional_community.py)
  - Career opportunity matcher (career_opportunity_matcher.py)
  - Skills knowledge graph (skills_graph.py)

### Changed
- Updated integrations count: 12 → 26
- Updated dependencies count: 1 → 2 (aiohttp + questionary)
- Updated test count: 2,200+ tests
- Documentation cleanup: removed vaporware and unsubstantiated claims
- Added author credentials to README footer

### Fixed
- Corrected LOC counts in badges
- Removed fake case studies from enterprise docs
- Toned down SOC 2 claims to "compatible" not "certified"

## [2.7.0] - 2026-03-22

### Added
- **One-Command Installation**
  - `setup.sh` for macOS/Linux with install/update/reset modes
  - `setup.ps1` for Windows PowerShell
  - Auto-detects OS, Python version, and hardware
  - Supports Debian, RedHat, Arch, macOS (Intel + ARM)

- **Interactive Configuration Wizard**
  - `agentic-brain new-config` command
  - Template selection: minimal, retail, support, enterprise
  - Guided setup for Neo4j, LLM providers, API settings
  - Model autocomplete based on selected provider

- **Installation E2E Tests**
  - 18 comprehensive tests in `tests/e2e/test_installation.py`
  - CI runs on Ubuntu + macOS, Python 3.11/3.12
  - Verifies setup script, CLI, config wizard

- **CI Pipeline Enhancement**
  - New `installation-tests` job in GitHub Actions
  - Build now requires passing installation tests

### Changed
- README simplified - removed competitor comparisons
- Australian-first marketing approach
- Features speak for themselves

### Removed
- Removed comparison tables against other frameworks
- Removed fear-based marketing copy

## [2.6.0] - 2026-03-21

### Added
- **HTTP Connection Pooling**
  - Centralized `_post_request()` and `_get_request()` helpers in LLMRouter
  - Connection reuse reduces latency ~50ms → ~1ms
  - Automatic retries with circuit breaker
  - Pool auto-starts on first request (lazy initialization)
  - `get_pool_stats()` for observability

- **Provider Health Checks**
  - `check_all_providers()` method to verify Ollama, OpenAI, Anthropic, OpenRouter
  - Returns detailed status for each provider
  - Useful for diagnostics and monitoring dashboards

- **Per-Provider Timeouts**
  - Ollama: 120s (local models slow on first load)
  - Anthropic: 90s (Claude can be slower)
  - OpenAI: 60s
  - OpenRouter: 60s

- **Token Usage Tracking**
  - `get_token_stats()` returns usage by provider
  - `reset_token_stats()` to clear counters
  - Track prompt/completion tokens separately

- **Async Context Manager**
  - `async with LLMRouter() as router:` for clean resource management
  - Auto-starts and stops HTTP pool

- **LLM Benchmark Module**
  - CLI: `agentic-brain benchmark`
  - Hardware detection (MLX, CUDA, ROCm, MPS, CPU)
  - Latency, throughput, memory profiling
  - JSON export for CI integration

- **Vector Database Section** in README
  - Pinecone, Weaviate, Qdrant, Neo4j Vector adapters showcased

### Changed
- Neo4j now optional with `get_memory_backend()` auto-fallback to InMemoryStore
- HTTP pool enabled by default (`use_http_pool=True`)
- Chatbot now uses LLMRouter instead of direct aiohttp
- Updated README with hardware acceleration badges (M1-M4, CUDA, ROCm)
- Updated README with platform badges (macOS, Linux, Windows, Docker)
- Improved comparison table with integrations and GPU acceleration
- Project description updated to highlight minimal dependencies

### Fixed
- Router no longer creates new ClientSession per request (was causing connection churn)

### Documentation
- Updated `docs/architecture.md` with new Router interface
- Updated `docs/DEPENDENCIES.md` with all architectural decisions
- Added decision log entries for all 2026-03-21 changes

## [2.5.0] - 2026-03-20

### Added
- **Hardware Acceleration for Embeddings**
  - Apple Silicon (M1/M2/M3/M4) support via MLX and MPS
  - NVIDIA CUDA support with FP16 mixed precision
  - AMD ROCm support for Linux
  - Auto-detection with `detect_hardware()` and `get_best_device()`
  - `get_accelerated_embeddings()` for fastest GPU option
  - `SentenceTransformerEmbeddings` with automatic device selection
  - Benchmarks: MLX 14x, CUDA 10x, MPS 4x faster than CPU

- **Enterprise Document Loaders** (11 total)
  - NotionLoader: Pages, databases, blocks, search
  - ConfluenceLoader: Spaces, pages, CQL search, Cloud/Server auth
  - SlackLoader: Channels, threads, user resolution, search
  - Previously added: Google Drive, Gmail, iCloud, Firestore, S3, MongoDB, GitHub, Microsoft 365

- **RAG Improvements**
  - Enhanced chunking strategies
  - Hybrid search with BM25 + vector fusion
  - Multiple reranking options (Similarity, MMR, Combined)

### Changed
- `get_embeddings()` now supports 8 providers: auto, mlx, cuda, mps, rocm, sentence_transformers, ollama, openai
- Improved test coverage (1943 tests passing)

### Fixed
- Tests now properly skip when optional dependencies unavailable

## [2.4.0] - 2026-03-20

### Added
- **MCP Protocol Support**: Universal AI tool interoperability
  - `MCPServer`: Register tools, resources, prompts for external consumption
  - `MCPClient`: Connect to external MCP servers (stdio/WebSocket transports)
  - Full JSON-RPC request/response handling
  - 66 tests for MCP module

- **AI Governance Templates**: Enterprise compliance features
  - `ModelCard`: Google Model Card format with markdown/JSON/YAML export
  - `AuditLog`: Event recording with query, statistics, CSV/JSON export
  - Neo4j persistence support for audit trails
  - 35 tests for governance module

- **Model Explainability**: SHAP/LIME integration for regulated industries
  - `SHAPExplainer`: Tree, Kernel, Deep, Linear explainer support
  - `LIMEExplainer`: Tabular, text, image data support
  - `UnifiedExplainer`: Auto-selects best explainer for model type
  - Graceful fallback when libraries not installed
  - 58 tests for explainability module

- **Vector Database Adapters**: Connect to popular vector stores
  - `PineconeAdapter`: Full Pinecone support with namespaces
  - `WeaviateAdapter`: Schema creation, batch import, search
  - `QdrantAdapter`: Collections, filters, in-memory mode
  - `MemoryVectorAdapter`: In-memory option for testing
  - 48 tests for vectordb module

- **Fine-tuning Utilities**: Prepare models for customization
  - `DatasetBuilder`: Alpaca, ShareGPT, OpenAI JSONL, HuggingFace formats
  - `LoRAConfig`: Presets for default, aggressive, QLoRA 4-bit/8-bit
  - `TrainingJob`: Progress tracking, checkpoints, metrics
  - Memory/time estimation utilities
  - 82 tests for finetuning module

- **Market-Driven Roadmap**: Based on 2026 AI job market research
  - Analyzed 22 market requirements from Seek.com.au, GitHub, industry reports
  - Achieved 95%+ market fit score

### Changed
- Updated README with market-targeted messaging
- Added comparison table vs LangChain/CrewAI
- Updated badges for test count and coverage

## [Unreleased]

## [2.2.1] - 2026-03-20

### Added
- **Unified Summarization System**: Brain-core compatible conversation summarization
  - `ConversationSummary`: Unified data format compatible with brain-core's session_stitcher
  - `UnifiedSummarizer`: Real-time and session-level summarization with LLM support
  - Topic extraction with LLM or keyword-based fallback
  - Entity extraction (people, places, organizations)
  - Key fact extraction from conversations
  - Auto-summarize old sessions for storage optimization
  - Neo4j storage with brain-core schema compatibility
  - `memory/` module for summarization exports

### Changed
- `ConversationSummarizer` now wraps `UnifiedSummarizer` for brain-core compatibility
- Added `memory` parameter to `ConversationSummarizer` for Neo4j storage
- Added `unified` property to access advanced summarization features

## [2.2.0] - 2026-03-20

### Added
- **Conversation Intelligence**: Smart chatbot features for enhanced user interaction
  - `ConversationSummarizer`: Auto-compress long conversations while preserving key facts
  - `IntentDetector`: Detect user intent (action, question, chat, complaint, clarification, confirmation)
  - `ClarificationGenerator`: Generate smart follow-up questions for ambiguous messages
  - `ConfidenceScorer`: Know when guessing vs certain, with hedge-word detection
  - `MoodDetector`: Detect user mood (happy, frustrated, confused, urgent, neutral)
  - `PersonalityManager`: Switch between personality profiles (professional, friendly, technical, brief)
  - `ResponseLengthController`: Adjust verbosity based on user preference (brief/normal/detailed)
  - `BookmarkManager`: Mark important conversation moments for later recall
  - `CorrectionLearner`: Learn from user corrections to avoid repeating mistakes
  - `SafetyChecker`: Hallucination detection, dangerous action confirmation, rate limit warnings
- **Chatbot Intelligence Integration**: New `intelligence` parameter for `Chatbot` class
  - `detect_intent()` / `detect_intent_async()`: Sync/async intent detection
  - `get_mood()`: Detect user mood from message
  - `switch_personality()`: Change bot personality profile
  - `score_confidence()`: Score response confidence
  - `needs_safety_confirmation()`: Check if action needs user confirmation
  - `detect_hallucination_risk()`: Score potential hallucination risk
  - `summarize_history()`: Generate conversation summary
- **Comprehensive Tests**: 45+ test cases for all intelligence features

## [2.1.0] - 2026-03-20

### Added
- **Recovery System**: Retry with exponential backoff, checkpoint-based recovery
  - `RetryConfig` dataclass for retry configuration
  - `@retry` decorator for automatic retries (sync and async)
  - `RecoveryManager` for checkpoint save/load/resume
- **Inter-bot Messaging**: Bot-to-bot communication via Neo4j
  - `BotMessaging` class with pub/sub and handoff protocols
  - Message history and acknowledgment
- **Health Monitoring**: Service health checks
  - `BotHealth` class for Neo4j, Ollama, service diagnostics
  - Run statistics tracking
- **Secrets Management**: Secure credential handling
  - `BotSecrets` with keyring, environment, and .env support
  - Priority chain for secret retrieval

### Changed
- Populated `bots/` module with brain-core bot infrastructure
- Added `secrets/` module for credential management

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

- Project licensed under Apache-2.0 for maximum flexibility

[Unreleased]: https://github.com/agentic-brain-project/agentic-brain/compare/v2.5.0...HEAD
[2.5.0]: https://github.com/agentic-brain-project/agentic-brain/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/agentic-brain-project/agentic-brain/compare/v2.2.1...v2.4.0
[2.2.1]: https://github.com/agentic-brain-project/agentic-brain/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/agentic-brain-project/agentic-brain/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/agentic-brain-project/agentic-brain/compare/v1.0.0...v2.1.0
[1.0.0]: https://github.com/agentic-brain-project/agentic-brain/releases/tag/v1.0.0
