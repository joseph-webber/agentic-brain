# ADL — Agentic Definition Language

ADL (Agentic Definition Language) is a **JDL-inspired DSL** for configuring an **Agentic Brain** instance from a single, readable source file.

Where JHipster JDL describes an application (entities, relationships, deployment), **ADL describes an AI brain** (LLMs, RAG, voice, API, security, modes, deployment).

ADL is intentionally:

- **Human-first**: meant to be written and reviewed like infrastructure-as-code.
- **Small and regular**: a minimal grammar parsed by a hand-written parser (no external parser dependencies).
- **Generator-friendly**: it can materialise concrete runtime artefacts (`adl_config.py`, `.env`, `docker-compose.yml`, `adl_api.py`).

---

## Contents

- [Quickstart](#quickstart)
- [Core concepts](#core-concepts)
- [Full syntax reference](#full-syntax-reference)
- [Blocks reference](#blocks-reference)
  - [`application`](#application-block)
  - [`llm`](#llm-block)
  - [`rag`](#rag-block)
  - [`voice`](#voice-block)
  - [`api`](#api-block)
  - [`security`](#security-block)
  - [`modes`](#modes-block)
  - [`deployment`](#deployment-block)
- [CLI commands](#cli-commands)
- [Generated files](#generated-files)
- [Mapping to runtime configuration](#mapping-to-runtime-configuration)
- [Comparison to JHipster JDL](#comparison-to-jhipster-jdl)
- [Migration guide (from manual config)](#migration-guide-from-manual-config)
- [Troubleshooting](#troubleshooting)

---

## Quickstart

1. Create an ADL template:

```bash
agentic adl init
# or
agentic adl init --file config/brain.adl
```

2. Validate syntax:

```bash
agentic adl validate
# or
agentic adl validate --file config/brain.adl
```

3. Generate runtime artefacts:

```bash
agentic adl generate
# or
agentic adl generate --file config/brain.adl --output ./generated

# overwrite existing generated artefacts
agentic adl generate --force
```

---

## Core concepts

### One file describes the whole brain
ADL is a top-level file (commonly `brain.adl`) with **order-independent** blocks.

### Blocks
ADL supports these top-level constructs (order-independent):

**Configuration blocks**

- `application <Name> { ... }`
- `llm <Name> { ... }`
- `rag <Name> { ... }`
- `voice <Name> { ... }`
- `api <Name> { ... }`
- `security { ... }`
- `modes { ... }`
- `deployment { ... }`

**Modelling blocks (JDL-style)**

- `entity <Name> { ... }`
- `enum <Name> { ... }`
- `relationship <Kind> { ... }`

**Annotations (JDL-style)**

- `@name(value)` applied to the *next* construct (blocks, entity fields, relationship lines)

All blocks are optional. The generator uses **the first** `llm`, `rag`, `voice`, and `api` block as the **primary** block when producing `.env`, `docker-compose.yml`, and `adl_config.py`.

### Names
- `llm`, `rag`, `voice`, and `api` **require a name**.
- `security`, `modes`, and `deployment` are **global blocks** (no name).
- `application` may include a name (recommended).

### Key/value bodies
Block bodies are **key/value pairs**:

```adl
llm Primary {
  provider OpenAI
  model gpt-4o
  temperature 0.7
}
```

Keys are identifiers. Values can be identifiers, strings, numbers, booleans, lists, or nested blocks.

### Extensibility (important)
ADL’s parser is intentionally permissive: you can add additional keys to any block. Unknown keys are still parsed and preserved (for example in the generated `adl_config.py` dictionaries), even if the current generator/runtime does not use them yet.

---

## Full syntax reference

### Comments
Line comments start with `//` and run to the end of the line.

```adl
// This is a comment
llm Primary { provider Ollama }
```

### Whitespace
Spaces, tabs, and newlines are insignificant except to separate tokens.

### Identifiers
Identifiers are unquoted words used for:

- block keywords (`llm`, `rag`, `security`)
- block names (`Primary`, `KnowledgeBase`)
- keys (`provider`, `defaultVoice`)
- identifier values (`OpenAI`, `Neo4j`, `JWT`, `unless-stopped`)

Allowed characters:

- letters and digits
- underscore `_`
- dash `-`
- dot `.`
- slash `/`
- colon `:` (allows model names like `llama3.2:8b`)

Examples:

```adl
provider OpenAI
license Apache-2.0
model llama3.2:8b
embeddingModel sentence-transformers/all-MiniLM-L6-v2
restart unless-stopped
```

### Strings
Use double quotes for strings, especially when you need spaces.

```adl
name "My Enterprise AI"
baseUrl "http://localhost:11434"
```

Supported escapes:

- `\n`, `\t`, and generic `\"` style escapes.

### Numbers
Numbers can be integers or floats:

```adl
port 8000
temperature 0.7
```

### Booleans
Booleans are `true` and `false` (case-insensitive). Example:

```adl
publishNeo4jPorts true
```

### Lists
Lists are bracketed and comma-separated. Trailing commas are not required.

```adl
loaders [PDF, Markdown, Code]
robotVoices ["Zarvox", "Ralph"]
```

### Nested blocks
A key can be followed by a nested block to form a dictionary:

```adl
api REST {
  rateLimit {
    requests 100
    window "1m"
    burstLimit 20
  }
}
```

### Optional key colon (`Key:`)
For readability (JDL-style), keys may be written with a trailing colon:

```adl
modes {
  Polymorphic: [Consensus, RoundRobin, Specialist]
  Default: Consensus
}
```

This colon is part of the key token and is stripped during parsing.

### Annotations (JDL-style)
Annotations can be applied to the *next* construct.

```adl
@priority(high)
llm Primary {
  provider OpenAI
}
```

You can also annotate entity fields and relationship lines:

```adl
entity KnowledgeSource {
  @indexed(true)
  name String required
}

relationship OneToMany {
  @ownedBy(Agent)
  Agent{sources} to KnowledgeSource
}
```

### Informal grammar (EBNF)

```text
adl           := { block } EOF
block         := keyword [name] "{" { pair } "}"
keyword       := IDENT
name          := IDENT
pair          := key [":"] value
key           := IDENT | IDENT ":"        // trailing ':' is allowed
value         := IDENT | STRING | NUMBER | BOOLEAN | list | dict
list          := "[" [ value { "," value } ] "]"
dict          := "{" { pair } "}"
```

Notes:

- Keys are effectively always identifiers. For interoperability and tooling, prefer `camelCase` keys.
- ADL does not currently support multi-line strings.

---

## Modelling reference

This section documents ADL's JDL-style modelling features.

### `enum` block

```adl
enum SourceType {
  DATABASE, API, FILE, STREAM
}
```

### `entity` block

Entity bodies declare fields using:

```
<fieldName> <Type> <validator> <validator>...
```

Example:

```adl
entity KnowledgeSource {
  name String required
  type SourceType
  url String
  refreshInterval Duration
}
```

Validators are parsed as metadata and surfaced in generated artefacts.
Recommended, production-safe validators:

- `required`
- `unique`
- `min(n)` / `max(n)`
- `pattern("regex")`

### `relationship` block

Relationships are declared inside a relationship kind block:

```adl
relationship OneToMany {
  Agent{sources} to KnowledgeSource
}
```

You may select fields with `{field}` on either side.

---

## Blocks reference

This section documents the **standard ADL blocks and properties** supported by `agentic-brain`.

Important notes:

- **Parsing** accepts any keys.
- **Generation** and runtime mapping only use documented keys (others are carried through in `adl_config.py`).
- Unless otherwise specified, values are case-insensitive identifiers or strings.

### `application` block

Defines human-facing metadata.

**Syntax**

```adl
application AgenticBrain {
  name "My Enterprise AI"
  version "1.0.0"
  license Apache-2.0
}
```

**Properties**

| Property | Type | Default | Used by generator | Notes |
|---|---:|---:|---:|---|
| `name` | string | _(none)_ | Yes | Sets API title and `APP_NAME` in `.env`. |
| `version` | string | `"1.0.0"` | Yes | Sets API version and `APP_VERSION` in `.env`. |
| `license` | identifier/string | _(none)_ | Yes | Mapped to `APP_LICENSE` in `.env`. |

**Example (minimal)**

```adl
application Brain {
  name "Brain"
  version "0.1.0"
}
```

---

### `llm` block

Defines one LLM provider + model configuration. Multiple `llm` blocks can be defined.

The generator uses the **first** `llm` block as the **primary** LLM for `.env` and `docker-compose.yml`.

**Syntax**

```adl
llm Primary {
  provider OpenAI
  model gpt-4o
  temperature 0.7
  maxTokens 4096
  fallback Local
}

llm Local {
  provider Ollama
  model llama3.2:8b
  baseUrl "http://localhost:11434"
}
```

**Properties (standard)**

| Property | Type | Default | Used by generator | Notes |
|---|---:|---:|---:|---|
| `provider` | identifier | `Ollama` | Yes | Mapped to `DEFAULT_LLM_PROVIDER` (lowercased). Supported: `Ollama`, `OpenAI`, `Anthropic`, `OpenRouter`, `Groq`, `Together`, `Google`, `XAI`, `Azure_OpenAI`/`azure_openai`. |
| `model` | identifier/string | provider-specific | Yes | Mapped to `DEFAULT_LLM_MODEL`. Model names may include `:` (example `llama3.2:8b`). |
| `baseUrl` | string | `"http://localhost:11434"` | Yes (Ollama only) | Mapped to `OLLAMA_API_BASE`/`OLLAMA_HOST` when present. (Alias `baseURL` also accepted.) |
| `temperature` | number | provider default | Stored only | Parsed and preserved, but not currently applied by the generator. |
| `maxTokens` | number | provider default | Stored only | Parsed and preserved. |
| `timeout` | number | runtime default | Stored only | Parsed and preserved. |
| `maxRetries` | number | runtime default | Stored only | Parsed and preserved. |
| `fallback` | identifier | _(none)_ | Yes (config) | Name of another `llm` block to use as fallback (wired in `adl_config.py`). |

**Defaults**

If you omit an `llm` block entirely, generated `docker-compose.yml` falls back to:

- provider: `ollama`
- model: `llama3.2:3b`
- Ollama base URL: `http://host.docker.internal:11434`

For best results and predictable behavior, **always specify at least one `llm` block**.

**Examples**

_Ollama (local, default)_

```adl
llm Local {
  provider Ollama
  model llama3.2:3b
  baseUrl "http://localhost:11434"
}
```

_OpenRouter (cloud)_

```adl
llm Cloud {
  provider OpenRouter
  model "anthropic/claude-3.5-sonnet"
}
```

_Azure OpenAI (deployment-based model names)_

```adl
llm Azure {
  provider azure_openai
  model gpt-4o   // model is the Azure deployment name
}
```

---

### `rag` block

Defines Retrieval-Augmented Generation settings.

The generator uses the **first** `rag` block as the **primary** RAG configuration and emits related `RAG_*` environment variables.

**Syntax**

```adl
rag KnowledgeBase {
  vectorStore Neo4j
  embeddingModel "sentence-transformers/all-MiniLM-L6-v2"
  chunkSize 512
  chunkOverlap 50

  loaders [PDF, Markdown, Code, JIRA]
}
```

**Properties (standard)**

| Property | Type | Default | Used by generator | Notes |
|---|---:|---:|---:|---|
| `vectorStore` | identifier/string | _(none)_ | Yes | Mapped to `RAG_VECTOR_STORE`. Common: `Neo4j`. |
| `embeddingModel` | string/identifier | _(none)_ | Yes | Mapped to `RAG_EMBEDDING_MODEL`. |
| `chunkSize` | number | _(none)_ | Yes | Mapped to `RAG_CHUNK_SIZE`. |
| `chunkOverlap` | number | _(none)_ | Yes | Mapped to `RAG_CHUNK_OVERLAP`. |
| `loaders` | list | _(none)_ | Yes | Mapped to `RAG_LOADERS` as comma-separated values. |

**Examples**

_Minimal Neo4j RAG_

```adl
rag Main {
  vectorStore Neo4j
  embeddingModel "sentence-transformers/all-MiniLM-L6-v2"
}
```

_With chunking and loaders_

```adl
rag Docs {
  vectorStore Neo4j
  embeddingModel "sentence-transformers/all-MiniLM-L6-v2"
  chunkSize 800
  chunkOverlap 100
  loaders [Markdown, Code, PDF]
}
```

---

### `voice` block

Defines voice/TTS configuration (for accessibility and hands-free operation).

The generator uses the **first** `voice` block as the **primary** voice configuration and maps some values to `AGENTIC_BRAIN_*` environment variables.

**Syntax**

```adl
voice Assistant {
  provider macOS
  defaultVoice "Karen"
  rate 160
  fallbackVoice "Samantha"
  robotVoices ["Zarvox", "Ralph"]
}
```

**Properties (standard)**

| Property | Type | Default | Used by generator | Notes |
|---|---:|---:|---:|---|
| `provider` | identifier/string | `system` | Yes | Mapped to `AGENTIC_BRAIN_VOICE_PROVIDER` (lowercased). Examples: `system`, `macOS`, `azure`, `google`, `aws`, `elevenlabs`. |
| `defaultVoice` | string/identifier | `Karen` | Yes | Mapped to `AGENTIC_BRAIN_VOICE`. |
| `rate` | number | `160` | Yes | Mapped to `AGENTIC_BRAIN_RATE`. |
| `language` | string | `en-AU` | Stored only | Parsed and preserved; runtime reads `AGENTIC_BRAIN_LANGUAGE`. |
| `pitch` | number | `1.0` | Stored only | Parsed and preserved; runtime reads `AGENTIC_BRAIN_PITCH`. |
| `volume` | number | `0.8` | Stored only | Parsed and preserved; runtime reads `AGENTIC_BRAIN_VOLUME`. |
| `enabled` | boolean | `true` | Stored only | Parsed and preserved; runtime reads `AGENTIC_BRAIN_VOICE_ENABLED`. |
| `fallbackVoice` | string | `Samantha` | Yes (config) | Used for voice fallback chain. |
| `regional` | map | _(none)_ | Yes (config) | Map of locale codes (e.g. `"en-AU"`) to voice names. |
| `robotVoices` | list | _(none)_ | Yes (config) | List of robotic voices for specific agents. |
| `quality` | identifier | `premium` | Stored only | Preserved; runtime reads `AGENTIC_BRAIN_VOICE_QUALITY`. |

**Examples**

_Default macOS voice_

```adl
voice Default {
  provider system
  defaultVoice "Karen"
  rate 160
}
```

_Disable voice (CI / server mode)_

```adl
voice Silent {
  enabled false
}
```

---

### `api` block

Defines REST API server defaults.

The generator uses the **first** `api` block as the **primary** API configuration and maps key settings to `.env` and the generated `adl_api.py` entrypoint.

**Syntax**

```adl
api REST {
  port 8000
  cors ["*"]
  rateLimit {
    requests 100
    window "1m"
    burstLimit 20
  }
}
```

**Properties (standard)**

| Property | Type | Default | Used by generator | Notes |
|---|---:|---:|---:|---|
| `port` | number | `8000` | Yes | Mapped to `API_PORT` and `SERVER_PORT` in `.env`. Also used by `docker-compose.yml` if no `deployment.apiPort`. |
| `cors` | list | `["*"]` | Yes | Mapped to `SECURITY_CORS_ORIGINS` (comma-separated) and applied in `adl_api.py`. |
| `rateLimit` | dict | _(none)_ | Yes | Nested block. Keys: `requests`, `window`, `burstLimit`. Mapped to `API_RATE_LIMIT_*` env vars. |

`rateLimit` nested properties:

| Property | Type | Default | Notes |
|---|---:|---:|---|
| `requests` | number | `100` | Requests per time window. |
| `window` | string | `"1m"` | Human-friendly (example `"1m"`, `"10s"`). |
| `burstLimit` | number | `20` | Short burst limit. |

**Examples**

_Minimal API_

```adl
api REST { port 8000 }
```

_Strict CORS and rate limits_

```adl
api REST {
  port 8080
  cors ["https://portal.example.com"]
  rateLimit { requests 60 window "1m" burstLimit 10 }
}
```

---

### `security` block

Defines authentication/SSO and high-level security posture.

**Syntax**

```adl
security {
  authentication JWT
  sso [Google, Microsoft, GitHub]
  saml enabled
  rateLimit strict
}
```

**Properties (standard)**

| Property | Type | Default | Used by generator | Notes |
|---|---:|---:|---:|---|
| `authentication` | identifier/string | _(none)_ | Yes | Enables auth in `.env` (`AUTH_ENABLED=true`) and sets `AUTH_TYPE` (lowercased). Example: `JWT`. |
| `sso` | list | _(none)_ | Yes | Mapped to `OAUTH2_PROVIDERS` as comma-separated. |
| `saml` | boolean/identifier | `false` | Yes | Accepts `true/false` or `enabled/disabled`. Mapped to `SAML_ENABLED`. |
| `rateLimit` | identifier/string | _(none)_ | Yes | Mapped to `SECURITY_RATE_LIMIT_PROFILE`. Example: `strict`. |

**Examples**

_JWT only_

```adl
security { authentication JWT }
```

_SSO providers + SAML_

```adl
security {
  authentication JWT
  sso [Google, Microsoft]
  saml enabled
}
```

---

### `modes` block

Defines higher-level “brain modes” and routing/strategy presets.

This block is **currently parsed and preserved** and is intended to drive higher-level orchestration.

**Syntax**

```adl
modes {
  Polymorphic: [Consensus, RoundRobin, Specialist]
  Default: Consensus
}
```

**Properties (conventions)**

Because `modes` is intentionally flexible, there is no strict schema. Recommended keys:

| Property | Type | Default | Notes |
|---|---:|---:|---|
| `Default` | identifier/string | _(none)_ | The default mode name. |
| `<ModeGroup>` | list | _(none)_ | A list of available modes for a group (example `Polymorphic`). |

**Example (multiple groups)**

```adl
modes {
  Default: Consensus
  Routing: [Consensus, RoundRobin]
  Safety: [Normal, Cautious, Maximum]
}
```

---

### `deployment` block

Defines deployment/generation preferences, primarily for the generated `docker-compose.yml`.

This block is **global** (no name):

```adl
deployment { ... }
```

**Syntax**

```adl
deployment {
  composeVersion "3.8"
  serviceName "agentic-brain"
  image "agentic-brain:latest"
  restart unless-stopped

  // Docker-for-Mac default. Override if Ollama is elsewhere.
  ollamaApiBase "http://host.docker.internal:11434"

  neo4jImage "neo4j:5"
  publishNeo4jPorts true
}
```

**Properties (standard)**

| Property | Type | Default | Used by generator | Notes |
|---|---:|---:|---:|---|
| `composeVersion` | string/identifier | `"3.8"` | Yes | Sets `version:` in `docker-compose.yml`. |
| `serviceName` | string/identifier | `"agentic-brain"` | Yes | Service key name for the Agentic Brain container. |
| `image` | string/identifier | `"agentic-brain:latest"` | Yes | Docker image for Agentic Brain service. If omitted and `dockerRepositoryName` is set, the generator uses `<dockerRepositoryName>/<serviceName>:latest`. |
| `restart` | identifier/string | `unless-stopped` | Yes | Restart policy for services. |
| `deploymentType` | identifier/string | _(none)_ | Stored only | For multi-target generators (`docker-compose`, `kubernetes`, `aws`, etc.). Parsed and preserved. |
| `dockerRepositoryName` | string/identifier | _(none)_ | Yes | When set and `image` is not provided, controls default image naming. |
| `kubernetesNamespace` | string/identifier | _(none)_ | Stored only | Captured for Kubernetes generation (not yet emitted by the default generator). |
| `apiPort` | number/string | _(from `api.port` or `8000`)_ | Yes | Overrides the port used in `docker-compose.yml`. |
| `ollamaApiBase` | string | _(from `llm.baseUrl` or Docker default)_ | Yes | Overrides `OLLAMA_API_BASE` in `docker-compose.yml`. |
| `neo4jServiceName` | string/identifier | `"neo4j"` | Yes | Service key name for Neo4j. |
| `neo4jImage` | string/identifier | `"neo4j:5"` | Yes | Docker image for Neo4j. |
| `neo4jPasswordDefault` | string | `"neo4j"` | Yes | Used in `${NEO4J_PASSWORD:-...}` defaults. Prefer leaving this default and setting `NEO4J_PASSWORD` in `.env`. |
| `neo4jAuth` | string | `neo4j/${NEO4J_PASSWORD:-neo4j}` | Yes | Full `NEO4J_AUTH` expression. |
| `publishNeo4jPorts` | boolean | `true` | Yes | When `false`, Neo4j ports are not published to the host. |
| `neo4jBrowserPort` | number | `7474` | Yes | Host and container port for Neo4j Browser (if published). |
| `neo4jBoltPort` | number | `7687` | Yes | Host and container port for Bolt (if published). |

**Examples**

_Minimal (accept defaults)_

```adl
deployment {
  image "agentic-brain:latest"
}
```

_No Neo4j ports published (safer for servers)_

```adl
deployment {
  publishNeo4jPorts false
}
```

_Custom service names_

```adl
deployment {
  serviceName brain
  neo4jServiceName graph
}
```

---

## CLI commands

ADL is integrated into the `agentic` CLI under the `adl` group.

### `agentic adl init`
Creates a new ADL template file.

```bash
agentic adl init
agentic adl init --file config/brain.adl
```

Options:

- `--file`, `-f`: output path (default: `brain.adl`).

### `agentic adl validate`
Validates ADL syntax (parser-level validation). This is intentionally conservative: it checks **grammar**, not semantics.

```bash
agentic adl validate
agentic adl validate --file config/brain.adl
```

Options:

- `--file`, `-f`: ADL path (default: `brain.adl`).

### `agentic adl generate`
Generates runtime artefacts from an ADL file.

```bash
agentic adl generate
agentic adl generate --file config/brain.adl
agentic adl generate --output ./generated
agentic adl generate --force
```

Options:

- `--file`, `-f`: ADL path (default: `brain.adl`).
- `--output`, `-o`: output directory (default: ADL file directory).
- `--force`: overwrite generated artefacts.

---

## Generated files

`agentic adl generate` creates the following files in the ADL directory (or `--output`):

### `adl_config.py`
A small Python module containing:

- `APPLICATION`, `DEPLOYMENT` dictionaries
- `PRIMARY_LLM`, `PRIMARY_RAG`, `PRIMARY_VOICE`, `PRIMARY_API` dictionaries
- helper functions:
  - `create_router_config()` → `RouterConfig`
  - `create_graph_rag_config()` → `GraphRAGConfig` (currently returns defaults)
  - `create_voice_config()` → `VoiceConfig`
  - `apply_api_settings(settings: Settings) -> Settings`

This is the “single source of truth” bridge from ADL to runtime Python.

### `.env`
Derived environment variables (non-destructive merge):

- Existing keys/values are preserved.
- Missing keys are appended.

### `docker-compose.yml`
A minimal compose stack:

- Agentic Brain service wired with `.env` values
- Neo4j service (configurable via `deployment`)

### `adl_api.py`
A minimal FastAPI entrypoint wrapper that calls:

- `agentic_brain.api.server.create_app(...)`

with ADL-derived title/version/CORS defaults.

---

## Mapping to runtime configuration

ADL → runtime mapping happens in two places:

1. The generator writes environment variables (`.env`) for settings that are primarily env-driven.
2. The generator writes `adl_config.py` helpers to construct config objects.

Current generator mapping:

| ADL block | Keys used | Output |
|---|---|---|
| `application` | `name`, `version`, `license` | `.env` (`APP_*`), `adl_api.py` title/version, `adl_config.APPLICATION` |
| `llm` (primary) | `provider`, `model`, `baseUrl`/`baseURL` | `.env` (`DEFAULT_LLM_*`, `OLLAMA_*`), `docker-compose.yml`, `adl_config.create_router_config()` |
| `rag` (primary) | `vectorStore`, `embeddingModel`, `chunkSize`, `chunkOverlap`, `loaders` | `.env` (`RAG_*`), `adl_config.PRIMARY_RAG` |
| `voice` (primary) | `provider`, `defaultVoice`, `rate` | `.env` (`AGENTIC_BRAIN_*`), `adl_config.create_voice_config()` |
| `api` (primary) | `port`, `cors`, `rateLimit.*` | `.env` (`API_PORT`, `SECURITY_CORS_ORIGINS`, `API_RATE_LIMIT_*`), `adl_api.py`, `adl_config.apply_api_settings()` |
| `security` | `authentication`, `sso`, `saml`, `rateLimit` | `.env` (`AUTH_*`, `OAUTH2_PROVIDERS`, `SAML_ENABLED`, `SECURITY_RATE_LIMIT_PROFILE`) |
| `modes` | (free-form) | `adl_config` dictionaries (preserved) |
| `deployment` | see block | `docker-compose.yml` |

If you need additional mappings, the intended extension point is to enhance `agentic_brain/adl/generator.py`.

---

## Comparison to JHipster JDL

### Similarities

- **Single declarative file** to describe a system.
- **Block-based structure** with key/value bodies.
- **Order-independent definitions**.
- **Generation workflow** (`init` → `validate` → `generate`).

### Differences

- JDL is focused on **entities, relationships, and application architecture**.
- ADL is focused on **AI system composition**:
  - LLM providers and models
  - RAG stack
  - voice/TTS settings (accessibility)
  - API/security posture
  - deployment scaffolding

ADL is intentionally smaller than JDL: it aims to be easy to parse, easy to diff, and safe to generate.

---

## Migration guide (from manual config)

If you currently configure Agentic Brain using a mix of `.env` values, python modules, and ad-hoc scripts, migrate in this order:

### 1) Identify your current values
Common existing environment variables:

- LLM:
  - `DEFAULT_LLM_PROVIDER`, `DEFAULT_LLM_MODEL`
  - `OLLAMA_HOST` / `OLLAMA_API_BASE`
- API:
  - `API_PORT` / `SERVER_PORT`
  - `SECURITY_CORS_ORIGINS`
- Voice:
  - `AGENTIC_BRAIN_VOICE`, `AGENTIC_BRAIN_RATE`, `AGENTIC_BRAIN_VOICE_PROVIDER`
- Security:
  - `AUTH_TYPE`, `AUTH_ENABLED`, `OAUTH2_PROVIDERS`, `SAML_ENABLED`

### 2) Create `brain.adl`

```bash
agentic adl init
```

Copy your values into the relevant ADL blocks.

### 3) Validate syntax

```bash
agentic adl validate
```

### 4) Generate artefacts

```bash
agentic adl generate
```

This will produce:

- `adl_config.py` (Python bridge)
- `.env` (merged)
- `docker-compose.yml`
- `adl_api.py`

### 5) Point your runtime to the generated files

- Use `.env` in your run scripts / Docker compose.
- Import helper functions from `adl_config.py` where appropriate.

### 6) Iterate

ADL is designed to evolve with your brain. Add keys as needed; if a key is not yet mapped by the generator, it will still be preserved for future wiring.

---

## Troubleshooting

### “Invalid ADL syntax” / parse errors

ADL parsing errors include line/column positions.

Common causes:

- Missing closing brace `}`.
- Using quotes incorrectly (strings must use double quotes).
- Accidentally writing a value that the parser interprets as two tokens.

### Model names with colon (`llama3.2:8b`)

Colons are allowed in identifiers, so this is valid:

```adl
llm Local { model llama3.2:8b }
```

### Lists failing to parse

Prefer comma separation:

```adl
loaders [PDF, Markdown, Code]
```

### `validate` passes, but runtime doesn’t behave as expected

`agentic adl validate` currently validates **syntax only**. It does not enforce:

- required keys within blocks
- provider/model compatibility
- known-key constraints

If generation/runtime ignores a key, check whether the generator maps it.

### Generator didn’t overwrite files

By default, generation is conservative and will not overwrite existing generated artefacts.

Use:

```bash
agentic adl generate --force
```

### “My ADL key didn’t show up in `.env`”

Only keys explicitly mapped by the generator are emitted into `.env`. All keys are still preserved in `adl_config.py` dictionaries.

### Base URL key naming (`baseUrl` vs `baseURL`)

The generator supports both for compatibility:

```adl
baseUrl "http://localhost:11434"
// or
baseURL "http://localhost:11434"
```

---

## See also

- Parser: `src/agentic_brain/adl/parser.py`
- Generator: `src/agentic_brain/adl/generator.py`
- CLI commands: `src/agentic_brain/cli/__init__.py` and `src/agentic_brain/cli/commands.py`
