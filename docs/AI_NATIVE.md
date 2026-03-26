# 🤖 AI-Native Architecture

> **Agentic Brain is built AI-first** — not retrofitted. Every design decision optimizes for AI agent operation.

---

## 🎯 Multi-Provider Philosophy

**No vendor lock-in. Ever.**

```
┌─────────────────────────────────────────────────────────────────┐
│                        AGENTIC BRAIN                            │
├─────────────────────────────────────────────────────────────────┤
│  Anthropic  │  OpenAI  │  GitHub  │  Local  │  Custom          │
│  Claude     │  GPT     │  Copilot │  Ollama │  Endpoints       │
└─────────────────────────────────────────────────────────────────┘
```

Switch providers with one line:

```bash
ab config set llm.provider anthropic   # Claude
ab config set llm.provider openai      # GPT
ab config set llm.provider ollama      # Local
```

---

## 🟠 Claude / Anthropic Native

**First-class Anthropic integration** — we speak Claude's language.

### Supported Models

| Model | Use Case | Context | Speed |
|-------|----------|---------|-------|
| **Claude 3.5 Sonnet** | Daily driver, balanced | 200K | Fast |
| **Claude 3.5 Haiku** | High-volume, quick tasks | 200K | Fastest |
| **Claude 3 Opus** | Complex reasoning, creative | 200K | Thorough |
| **Claude 4** | Latest capabilities | 200K+ | Varies |

### MCP (Model Context Protocol) Support

Full MCP integration for tool orchestration:

```python
from agentic_brain import Brain
from agentic_brain.mcp import MCPServer

# Register MCP tools
brain = Brain(llm="claude-3-5-sonnet")
brain.mcp.register_server("filesystem", MCPServer("@modelcontextprotocol/server-filesystem"))
brain.mcp.register_server("github", MCPServer("@modelcontextprotocol/server-github"))

# Tools are automatically available to Claude
result = brain.chat("Read the README and summarize it")
```

### Tool Use / Function Calling

Native Anthropic tool use:

```python
from agentic_brain.tools import Tool

@Tool(description="Search the codebase")
def search_code(query: str, file_type: str = "py") -> list[str]:
    """Search code files for a pattern."""
    return grep(query, f"**/*.{file_type}")

brain = Brain(tools=[search_code])
brain.chat("Find all functions that handle authentication")
# Claude automatically calls search_code with appropriate parameters
```

### Vision Capabilities

Image understanding out of the box:

```python
from agentic_brain import Brain

brain = Brain(llm="claude-3-5-sonnet")

# Analyze images
result = brain.vision.analyze("screenshot.png", "Describe any accessibility issues")

# Multi-image comparison
result = brain.vision.compare(["design_v1.png", "design_v2.png"], "What changed?")

# Chart/diagram extraction
data = brain.vision.extract_data("chart.png")  # Returns structured data
```

### Direct API Integration

```python
from agentic_brain.providers import AnthropicProvider

# Direct access when needed
provider = AnthropicProvider(api_key="sk-ant-...")
response = provider.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

---

## 🐙 GitHub Copilot Integration

**Agentic Brain complements GitHub Copilot** — they work together, not against each other.

### Seamless Setup

```bash
# If you already have Copilot, Agentic Brain detects it
ab init --detect-copilot

# Copilot handles inline completion
# Agentic Brain handles agentic workflows
```

### Complementary Workflows

| Copilot Does | Agentic Brain Does |
|--------------|-------------------|
| Inline code completion | Multi-file refactoring |
| Single function generation | Entire feature implementation |
| Tab autocomplete | Natural language orchestration |
| IDE integration | CLI-first automation |
| Code suggestions | Autonomous task execution |

### Working with Copilot CLI

```bash
# Use both together
gh copilot suggest "fix the bug"      # Copilot suggests
ab agent run fix-and-test             # Brain executes, tests, commits

# Brain respects Copilot settings
ab config sync-from-copilot
```

### GitHub Copilot Workspace Alignment

```python
from agentic_brain.integrations import GitHubWorkspace

# Load Copilot Workspace context
workspace = GitHubWorkspace.from_issue("owner/repo#123")
brain.context.add(workspace)

# Brain understands the full issue context
brain.agent("Implement this feature based on the issue requirements")
```

---

## 🟢 OpenAI Native

**Full OpenAI compatibility** — GPT-4, Assistants API, function calling.

### Supported Models

| Model | Strengths | Best For |
|-------|-----------|----------|
| **GPT-4o** | Multimodal, fast | Daily tasks, vision |
| **GPT-4.1** | Latest, improved | Complex reasoning |
| **GPT-4 Turbo** | Large context | Document analysis |
| **GPT-3.5 Turbo** | Fast, cheap | High-volume tasks |
| **o1-preview** | Deep reasoning | Hard problems |
| **o1-mini** | Efficient reasoning | Quick logic tasks |

### Assistants API Integration

```python
from agentic_brain import Brain

# Create persistent assistant
brain = Brain(llm="gpt-4o", mode="assistant")

# Assistant persists across sessions
assistant = brain.assistants.create(
    name="Code Reviewer",
    instructions="You review Python code for best practices",
    tools=["code_interpreter", "retrieval"]
)

# Thread-based conversations
thread = assistant.create_thread()
thread.message("Review this PR: #123")
```

### Function Calling

```python
from agentic_brain.tools import Tool

@Tool(description="Deploy to production")
def deploy(environment: str, version: str) -> dict:
    """Deploy application to specified environment."""
    return run_deployment(environment, version)

brain = Brain(llm="gpt-4o", tools=[deploy])
brain.chat("Deploy version 2.1.0 to staging")
# GPT-4 calls deploy("staging", "2.1.0") automatically
```

### Streaming Responses

```python
# Real-time streaming
for chunk in brain.stream("Explain quantum computing"):
    print(chunk, end="", flush=True)

# With callbacks
brain.chat(
    "Write a long report",
    on_token=lambda t: speak(t),  # Speak each token!
    on_complete=lambda r: save(r)
)
```

---

## 🦙 Local AI (Zero Cloud Dependency)

**Run completely offline.** Your data never leaves your machine.

### Ollama Integration

```bash
# Install Ollama (if not present)
ab setup ollama

# Pull models
ab model pull llama3.1:8b
ab model pull mistral:7b
ab model pull phi3:mini
ab model pull codellama:13b
```

```python
from agentic_brain import Brain

# Use local model
brain = Brain(llm="ollama:llama3.1:8b")

# Automatic fallback chain
brain = Brain(
    llm="claude-3-5-sonnet",
    fallback=["ollama:llama3.1:8b", "ollama:phi3:mini"]
)
# If cloud fails, falls back to local
```

### LM Studio Support

```python
from agentic_brain import Brain

# Connect to LM Studio
brain = Brain(
    llm="lmstudio",
    base_url="http://localhost:1234/v1"
)

# Same API as cloud providers
result = brain.chat("Hello!")
```

### Air-Gapped Operation

```python
from agentic_brain import Brain

# Military/secure mode - zero network
brain = Brain(
    llm="ollama:llama3.1:70b",
    mode="airgapped",
    network=False,          # Disable all network
    telemetry=False,        # No analytics
    crash_reports=False     # No error reporting
)

# Everything runs locally
brain.agent("Analyze classified documents")
```

### Model Performance on Apple Silicon

| Model | M1 | M2 | M3 | M3 Max |
|-------|-----|-----|-----|--------|
| Phi-3 Mini | 45 t/s | 58 t/s | 72 t/s | 95 t/s |
| Llama 3.1 8B | 32 t/s | 41 t/s | 53 t/s | 78 t/s |
| Mistral 7B | 35 t/s | 44 t/s | 56 t/s | 82 t/s |
| Llama 3.1 70B | 5 t/s | 7 t/s | 12 t/s | 28 t/s |

*t/s = tokens per second. Apple Silicon MLX acceleration enabled.*

### Custom Endpoints

```python
from agentic_brain import Brain

# Self-hosted models (vLLM, TGI, etc.)
brain = Brain(
    llm="custom",
    base_url="https://your-inference-server.com/v1",
    api_key="your-key"
)

# OpenAI-compatible API
brain = Brain(
    llm="openai-compatible",
    base_url="http://localhost:8000/v1",
    model="your-fine-tuned-model"
)
```

---

## 🔄 Provider Switching

### Runtime Switching

```python
from agentic_brain import Brain

brain = Brain()

# Switch on the fly
brain.set_provider("anthropic")
brain.chat("Using Claude now")

brain.set_provider("openai")
brain.chat("Using GPT now")

brain.set_provider("ollama:llama3.1:8b")
brain.chat("Using local Llama now")
```

### Automatic Fallback

```python
from agentic_brain import Brain

# Cascading fallback
brain = Brain(
    primary="claude-3-5-sonnet",
    fallback=[
        "gpt-4o",              # If Claude down
        "ollama:llama3.1:70b", # If OpenAI down
        "ollama:phi3:mini"     # If all else fails
    ]
)

# Never fails - always has a fallback
result = brain.chat("Important task")
```

### Cost Optimization

```python
from agentic_brain import Brain

# Route by complexity
brain = Brain(
    router="auto",
    simple_tasks="ollama:phi3:mini",    # Free, local
    medium_tasks="gpt-4o-mini",          # Cheap cloud
    complex_tasks="claude-3-5-sonnet"    # Premium
)

brain.chat("What's 2+2?")           # Uses phi3
brain.chat("Summarize this doc")    # Uses gpt-4o-mini  
brain.chat("Debug this complex code") # Uses Claude
```

---

## 📊 Comparison Matrix

| Feature | Anthropic | OpenAI | Ollama | LM Studio |
|---------|-----------|--------|--------|-----------|
| Cloud | ✅ | ✅ | ❌ | ❌ |
| Local | ❌ | ❌ | ✅ | ✅ |
| Vision | ✅ | ✅ | ⚠️ | ⚠️ |
| Tool Use | ✅ | ✅ | ✅ | ✅ |
| MCP | ✅ | ❌ | ❌ | ❌ |
| Streaming | ✅ | ✅ | ✅ | ✅ |
| Cost | $$ | $$ | Free | Free |
| Privacy | Cloud | Cloud | Local | Local |
| Speed | Fast | Fast | Varies | Varies |

---

## 🔐 API Key Management

```bash
# Set via environment
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# Or via config
ab config set anthropic.api_key "sk-ant-..."
ab config set openai.api_key "sk-..."

# Keys stored securely in system keychain (macOS/Windows)
ab config set --secure anthropic.api_key
```

---

## 📚 Related Documentation

- [Quick Start](./QUICK_START.md) — Get running in 2 minutes
- [Model Guide](./MODEL_GUIDE.md) — Choosing the right model
- [RAG Guide](./RAG_GUIDE.md) — Retrieval-augmented generation
- [Deployment](./DEPLOYMENT.md) — Production deployment options

---

<div align="center">

**AI-Native by Design** · Built for the age of AI agents

</div>
