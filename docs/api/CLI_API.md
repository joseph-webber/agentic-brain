# CLI API Reference

## Installation

```bash
pip install agentic-brain
# OR
pipx install agentic-brain
```

## Usage

```bash
agentic [command] [options]
```

## Global Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message |
| `--version` | Show version |
| `--config <file>` | Configuration file path |
| `--debug` | Enable debug logging |
| `--quiet` | Suppress output |

## Commands

### chat

Start an interactive chat session with the agent.

```bash
agentic chat [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--model <name>` | LLM model to use (default: llama3.1:8b) |
| `--provider <name>` | LLM provider (ollama, groq, claude, openai) |
| `--system-prompt <text>` | System prompt for agent |
| `--temperature <float>` | LLM temperature (0.0-1.0) |
| `--session-id <id>` | Resume existing session |
| `--stream` | Stream responses |
| `--voice <voice>` | Voice for audio output |
| `--no-memory` | Disable memory persistence |

**Examples:**

```bash
# Start interactive chat
agentic chat

# Chat with specific model
agentic chat --model claude-3-sonnet

# Chat with custom system prompt
agentic chat --system-prompt "You are a Python expert"

# Resume previous session
agentic chat --session-id sess_abc123

# Stream responses with voice output
agentic chat --stream --voice Karen
```

**Interactive Commands:**

In chat mode, use these commands:

| Command | Description |
|---------|-------------|
| `/exit` or `/quit` | Exit chat |
| `/clear` | Clear memory |
| `/memory` | Show memory state |
| `/model <name>` | Switch model |
| `/export <file>` | Export conversation |
| `/help` | Show help |

---

### stream

Stream chat responses from a single query.

```bash
agentic stream "Your message here" [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--model <name>` | LLM model |
| `--provider <name>` | LLM provider |
| `--temperature <float>` | LLM temperature |

**Examples:**

```bash
agentic stream "Tell me a story about AI"

agentic stream "Write a poem" --model gpt-4 --provider openai
```

---

### memory

Manage agent memory.

```bash
agentic memory [subcommand] [options]
```

**Subcommands:**

#### memory show

Show memory contents.

```bash
agentic memory show [options]
```

**Options:**
- `--session-id <id>` - Show specific session memory
- `--entities` - Show entities only
- `--relationships` - Show relationships only
- `--topics` - Show topics only
- `--format json|yaml` - Output format

**Examples:**

```bash
# Show all memory
agentic memory show

# Show entities
agentic memory show --entities

# Export as JSON
agentic memory show --format json > memory.json
```

---

#### memory clear

Clear memory.

```bash
agentic memory clear [options]
```

**Options:**
- `--session-id <id>` - Clear specific session
- `--type <type>` - Clear specific type (entities, relationships, topics)
- `--confirm` - Skip confirmation prompt

**Examples:**

```bash
agentic memory clear

agentic memory clear --session-id sess_123 --confirm
```

---

#### memory recall

Query memory for information.

```bash
agentic memory recall "Your query"
```

**Examples:**

```bash
agentic memory recall "What do we know about Alice?"

agentic memory recall "Tell me about our conversations"
```

---

### config

Manage configuration.

```bash
agentic config [subcommand] [options]
```

**Subcommands:**

#### config show

Show current configuration.

```bash
agentic config show [--format json|yaml]
```

**Examples:**

```bash
agentic config show

agentic config show --format yaml
```

---

#### config set

Set configuration value.

```bash
agentic config set <key> <value>
```

**Examples:**

```bash
agentic config set llm.provider ollama

agentic config set llm.temperature 0.5

agentic config set memory.cache_enabled true
```

---

#### config init

Initialize configuration file.

```bash
agentic config init [--template <template>]
```

**Templates:**

- `default` - Default configuration
- `dev` - Development configuration
- `prod` - Production configuration
- `minimal` - Minimal configuration

**Examples:**

```bash
agentic config init

agentic config init --template dev > .env.dev
```

---

### eval

Evaluate agent responses.

```bash
agentic eval [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--question <text>` | Question to evaluate |
| `--answer <text>` | Answer to evaluate |
| `--ground-truth <text>` | Ground truth reference |
| `--metrics <list>` | Metrics to compute |

**Examples:**

```bash
agentic eval \
  --question "What is AI?" \
  --answer "AI is artificial intelligence" \
  --ground-truth "AI is artificial intelligence"

agentic eval \
  --metrics relevance,accuracy,completeness \
  --question "How to learn Python?" \
  --answer "Use online courses and practice"
```

---

### rag

Work with RAG (Retrieval-Augmented Generation).

```bash
agentic rag [subcommand] [options]
```

**Subcommands:**

#### rag index

Index documents for retrieval.

```bash
agentic rag index <file> [options]
```

**Options:**
- `--name <name>` - Index name
- `--format auto|pdf|txt|json` - File format
- `--chunk-size <size>` - Document chunk size

**Examples:**

```bash
agentic rag index documents.pdf --name my_docs

agentic rag index data.json --format json --name products
```

---

#### rag query

Query the indexed documents.

```bash
agentic rag query "Your question" [options]
```

**Options:**
- `--index <name>` - Index to query
- `--top-k <number>` - Number of results (default: 5)
- `--threshold <float>` - Relevance threshold

**Examples:**

```bash
agentic rag query "How to deploy?" --index my_docs --top-k 3

agentic rag query "Python installation" --threshold 0.7
```

---

#### rag list

List available indexes.

```bash
agentic rag list
```

---

### server

Run the API server.

```bash
agentic server [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--host <host>` | Server host (default: 0.0.0.0) |
| `--port <port>` | Server port (default: 8000) |
| `--reload` | Auto-reload on file changes |
| `--workers <num>` | Number of worker processes |
| `--log-level <level>` | Logging level |

**Examples:**

```bash
agentic server

agentic server --port 8080 --reload

agentic server --host 127.0.0.1 --workers 4
```

---

### version

Show version information.

```bash
agentic version
```

---

### health

Check system health.

```bash
agentic health [options]
```

**Options:**
- `--detailed` - Show detailed health info
- `--format json|yaml` - Output format

**Examples:**

```bash
agentic health

agentic health --detailed --format json
```

---

## Configuration File

### Location

Configuration is read from (in order):
1. `--config` argument
2. `.env` file in current directory
3. `~/.agentic/config.yaml`
4. System defaults

### Example Configuration

```yaml
llm:
  provider: ollama
  model: llama3.1:8b
  temperature: 0.7
  top_p: 0.9
  max_tokens: 2048

memory:
  type: neo4j
  uri: bolt://localhost:7687
  user: neo4j
  password: ""
  cache_enabled: true
  cache_ttl: 3600

audio:
  enabled: true
  voice: Karen
  rate: 175

security:
  audit_enabled: true
  rate_limit: 60

api:
  host: 0.0.0.0
  port: 8000
  workers: 4
```

---

## Environment Variables

```bash
# LLM Settings
AGENTIC_LLM_PROVIDER=ollama
AGENTIC_LLM_MODEL=llama3.1:8b
AGENTIC_LLM_TEMPERATURE=0.7

# Memory Settings
AGENTIC_MEMORY_TYPE=neo4j
AGENTIC_MEMORY_URI=bolt://localhost:7687
AGENTIC_MEMORY_USER=neo4j
AGENTIC_MEMORY_PASSWORD=

# Audio Settings
AGENTIC_AUDIO_ENABLED=true
AGENTIC_AUDIO_VOICE=Karen

# Security
AGENTIC_RATE_LIMIT=60
AGENTIC_AUDIT_ENABLED=true
```

---

## Examples

### Interactive Chat Session

```bash
$ agentic chat
Agentic Brain v3.1.0
Type /help for commands or /exit to quit

> What is machine learning?
Machine learning is a subset of artificial intelligence...

> /model gpt-4
Switched to gpt-4 model

> Tell me more
[Continues conversation]

> /export conversation.txt
Conversation exported to conversation.txt

> /exit
Goodbye!
```

### Single Query with Streaming

```bash
$ agentic stream "Tell me about quantum computing" --stream

Streaming response from llama3.1:8b:
Quantum computing is a revolutionary technology that harnesses
the principles of quantum mechanics to process information...
[Response continues streaming in real-time]
```

### Query RAG Index

```bash
$ agentic rag index documents.pdf --name knowledge_base

Successfully indexed 50 documents

$ agentic rag query "How do I reset my password?" --index knowledge_base --top-k 3

[1] To reset your password, go to Settings > Security (score: 0.98)
[2] Password recovery steps are documented in FAQ (score: 0.85)
[3] You can also contact support for password help (score: 0.72)
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Usage error (wrong arguments) |
| 127 | Command not found |

---

## See Also

- [REST API Documentation](./REST_API.md)
- [Python SDK Reference](./PYTHON_API.md)
- [Code Examples](./EXAMPLES.md)
- [Configuration Guide](../configuration.md)
