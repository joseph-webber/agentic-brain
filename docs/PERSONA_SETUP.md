# Persona-Driven Setup for Agentic Brain

**Everything flows from persona selection.**

Persona modes are the primary control mechanism for Agentic Brain. Choose a persona, and ADL generates everything else automatically.

## Quick Start

### Simple Install (Recommended)

```bash
# Interactive installer
python -m agentic_brain.installer_persona

# Non-interactive with specific persona
python -m agentic_brain.installer_persona --persona professional --non-interactive
```

### Advanced Install

```bash
# Start with a persona template, edit manually
python -m agentic_brain.installer_persona --persona technical

# Then edit brain.adl and regenerate
agentic adl generate
```

## Available Personas

### 1. Professional
**Best for:** Business/enterprise use, formal communication  
**Mode:** Business  
**Temperature:** 0.3 (focused, deterministic)  
**Features:**
- Concise, accurate responses
- Formal tone
- Standard document processing (PDF, TXT, MD)
- Smart routing for optimal provider

**Example use cases:**
- Business assistant
- Customer support
- Data analysis
- Report generation

### 2. Technical
**Best for:** Software development, debugging, system administration  
**Mode:** Developer  
**Temperature:** 0.2 (very deterministic for code)  
**Features:**
- Code-focused responses
- Extended token limit (4096) for examples
- Supports multiple code formats
- Higher rate limit for dev workflows

**Example use cases:**
- Code review
- Debugging assistance
- System administration
- Documentation

### 3. Creative
**Best for:** Writing, brainstorming, content generation  
**Mode:** Creator  
**Temperature:** 0.9 (highly creative)  
**Features:**
- Imaginative, engaging responses
- Longer responses (4096 tokens)
- Larger chunks for narrative context
- Document format support

**Example use cases:**
- Creative writing
- Marketing copy
- Brainstorming
- Content creation

### 4. Accessibility
**Best for:** Screen reader optimization, WCAG compliance  
**Mode:** Home  
**Temperature:** 0.4 (balanced)  
**Features:**
- WCAG 2.1 Level AA compliance
- Screen reader optimized
- High contrast support
- Clear, structured responses

**Example use cases:**
- Accessible interfaces
- Screen reader users
- Accessibility-first applications

### 5. Research
**Best for:** Academic research, data analysis, citations  
**Mode:** Research  
**Temperature:** 0.5 (balanced)  
**Features:**
- Citation support
- Objective analysis
- Logical argument structure
- Extended chunks for context

**Example use cases:**
- Academic research
- Literature review
- Data analysis
- Report writing

### 6. Minimal
**Best for:** Simple chatbot, no extras  
**Mode:** Free  
**Temperature:** 0.7 (balanced)  
**Features:**
- Bare minimum
- No RAG, no voice
- Simple routing

**Example use cases:**
- Learning
- Prototyping
- Basic chat

## How It Works

### Flow Diagram

```
User picks persona
       ↓
ADL template selected
       ↓
ADL generates:
  - adl_config.py (router, LLM, RAG, voice)
  - .env (environment variables)
  - docker-compose.yml (deployment)
       ↓
Mode manager configures:
  - Default operational mode
  - Router template
  - Provider fallbacks
       ↓
Brain ready to use!
```

### Persona → Mode Mapping

| Persona | Mode Code | Mode Name | Router Template |
|---------|-----------|-----------|-----------------|
| Professional | `B` | business | smart |
| Technical | `D` | developer | smart |
| Creative | `CR` | creator | smart |
| Accessibility | `H` | home | smart |
| Research | `R` | research | smart |
| Minimal | `F` | free | simple |

### Sensible Defaults

All personas use these defaults unless overridden:

- **LLM Provider:** `auto` (auto-detects best available)
  - Tries Ollama first (local, free)
  - Falls back to OpenAI
  - Then Groq
  
- **Default Model:** `llama3.2:3b` (fast, efficient)

- **Voice Provider:** `system` (uses OS default)

- **RAG Vector Store:** `basic` (no Neo4j required)

- **Security Level:** `standard`

- **Rate Limit:** 100 requests/minute (150 for technical)

## Customization

### Modify Existing Persona

1. Generate config from persona:
   ```bash
   python -m agentic_brain.installer_persona --persona professional
   ```

2. Edit `brain.adl`:
   ```adl
   llm Primary {
     model "llama3.2:8b"  // Switch to larger model
     temperature 0.5      // Less focused
   }
   ```

3. Regenerate:
   ```bash
   agentic adl generate
   ```

### Create Custom Persona

Add to `src/agentic_brain/adl/personas.py`:

```python
"custom": PersonaTemplate(
    name="Custom",
    description="My custom persona",
    mode_code="D",  # Use developer mode
    adl_content='''
application AgenticBrain {
  name "Custom Assistant"
  persona custom
}

llm Primary {
  provider ollama
  model "mixtral:8x7b"
  temperature 0.6
  maxTokens 8192
}

modes {
  default developer
  routing smart
}
'''
)
```

## CLI Commands

### Installer

```bash
# Interactive
python -m agentic_brain.installer_persona

# With specific persona
python -m agentic_brain.installer_persona --persona technical

# Non-interactive
python -m agentic_brain.installer_persona --persona minimal --non-interactive
```

### Mode Switching (Runtime)

```python
from agentic_brain.modes import ModeManager

manager = ModeManager()

# Switch to developer mode
manager.switch("D")

# Switch to business mode
manager.switch("B")

# Get current mode
current = manager.current()
```

### ADL Generation

```bash
# Generate from existing brain.adl
agentic adl generate

# Generate with overwrite
agentic adl generate --overwrite

# Generate to specific directory
agentic adl generate --output-dir ./config
```

## Environment Variables

After installation, `.env` contains all settings:

```bash
# Application
APP_NAME="My AI Assistant"
APP_VERSION="1.0.0"

# LLM
DEFAULT_LLM_PROVIDER=auto
DEFAULT_LLM_MODEL=llama3.2:3b
OLLAMA_API_BASE=http://localhost:11434

# RAG
RAG_VECTOR_STORE=basic
RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50

# Voice
AGENTIC_BRAIN_VOICE=default
AGENTIC_BRAIN_RATE=160
AGENTIC_BRAIN_VOICE_PROVIDER=system

# Security
SECURITY_RATE_LIMIT_PROFILE=standard
```

## Integration with Router

Personas control router behavior through the `modes` block in ADL:

```adl
modes {
  default business      // Sets default operational mode
  routing smart         // Uses smart router template
  fallback ["ollama", "openai", "groq"]  // Provider cascade
}
```

This maps to:

1. **Mode Manager:** Sets default mode on startup
2. **Smart Router:** Configures provider selection strategy
3. **Fallback Chain:** Defines provider cascade on failure

## Testing Your Setup

```python
from agentic_brain.chat import chat_sync
from agentic_brain.modes import ModeManager

# Verify persona loaded
manager = ModeManager()
print(f"Current mode: {manager.current()}")

# Test chat
response = chat_sync("Hello, what can you help me with?")
print(response)
```

## Migration from Old Setup

**No backward compatibility needed!** ADL is new, so:

1. Pick a persona that matches your use case
2. Run the installer
3. Done!

Your old config files (if any) won't be touched unless you use `--overwrite`.

## Examples

See `examples/personas/` for complete ADL files:
- `professional.adl` - Business use
- `technical.adl` - Development
- `creative.adl` - Writing
- `accessibility.adl` - Screen reader optimized
- `research.adl` - Academic research
- `minimal.adl` - Bare minimum

## Troubleshooting

### Ollama not detected?

Add to `brain.adl`:
```adl
llm Primary {
  provider ollama
  baseURL "http://localhost:11434"
}
```

### Want different model?

Edit `brain.adl`:
```adl
llm Primary {
  model "llama3.2:8b"  // or mixtral:8x7b, etc.
}
```

Then regenerate: `agentic adl generate`

### Need OpenAI instead?

```adl
llm Primary {
  provider openai
  apiKey "${OPENAI_API_KEY}"  // From environment
  model "gpt-4"
}
```

Add to `.env`:
```bash
OPENAI_API_KEY=sk-...
```

## Next Steps

1. ✅ Pick your persona
2. ✅ Run installer
3. ✅ Review generated config
4. ⬜ Install dependencies: `pip install -e .`
5. ⬜ Start chatting: `python -m agentic_brain.chat`
6. ⬜ Deploy: `docker-compose up`

---

**Questions?** Check the main documentation or create an issue on GitHub.
