# Persona ADL Examples

This directory contains complete ADL configuration files for each persona mode.

## Quick Start

Copy an example to your project:

```bash
# Copy professional persona
cp examples/personas/professional.adl ./brain.adl

# Generate config
agentic adl generate

# Start using
python -m agentic_brain.chat
```

Or use the installer to generate automatically:

```bash
agentic persona --persona professional
```

## Available Personas

### professional.adl
**Best for:** Business, enterprise, formal communication  
**Mode:** Business (B)  
**Temperature:** 0.3 (focused, deterministic)

Features:
- Concise, accurate responses
- Standard document processing (PDF, TXT, MD)
- Smart routing
- 100 requests/min rate limit

### technical.adl
**Best for:** Software development, debugging, sysadmin  
**Mode:** Developer (D)  
**Temperature:** 0.2 (very deterministic)

Features:
- Code-focused responses
- Extended token limit (4096)
- Supports multiple code formats
- 150 requests/min rate limit (higher for dev)

### minimal.adl
**Best for:** Simple chatbot, learning, prototyping  
**Mode:** Free (F)  
**Temperature:** 0.7 (balanced)

Features:
- Bare minimum configuration
- No RAG, no voice
- Simple routing (no smart router)
- Perfect for getting started

### creative.adl
**Best for:** Writing, brainstorming, content generation  
**Mode:** Creator (CR)  
**Temperature:** 0.9 (highly creative)

Features:
- Imaginative, engaging responses
- Extended token limit (4096)
- Larger chunks for narrative context
- Document format support

### accessibility.adl
**Best for:** Screen reader optimization, WCAG compliance  
**Mode:** Home (H)  
**Temperature:** 0.4 (balanced)

Features:
- WCAG 2.1 Level AA compliance
- Screen reader optimized
- High contrast support
- Clear, structured responses

### research.adl
**Best for:** Academic research, data analysis, citations  
**Mode:** Research (R)  
**Temperature:** 0.5 (balanced)

Features:
- Citation support
- Objective analysis
- Logical argument structure
- Extended chunks for context

## Customization

### Change Model

Edit the `llm Primary` block:

```adl
llm Primary {
  model "llama3.2:8b"  // Use larger model
  temperature 0.5      // Adjust creativity
}
```

### Add OpenAI Support

```adl
llm Primary {
  provider openai
  apiKey "${OPENAI_API_KEY}"
  model "gpt-4"
}
```

Then add to `.env`:
```bash
OPENAI_API_KEY=sk-...
```

### Enable Neo4j RAG

```adl
rag MainRAG {
  vectorStore neo4j    // Use Neo4j instead of basic
  graphEnabled true
  neo4jUri "${NEO4J_URI}"
  neo4jUser "${NEO4J_USER}"
  neo4jPassword "${NEO4J_PASSWORD}"
}
```

## Generating Config

After customizing:

```bash
# Validate syntax
agentic adl validate

# Generate config files
agentic adl generate

# Generate with overwrite
agentic adl generate --force
```

This creates:
- `adl_config.py` - Python configuration
- `.env` - Environment variables
- `docker-compose.yml` - Deployment config
- `adl_api.py` - FastAPI application

## See Also

- [Persona Setup Guide](../docs/PERSONA_SETUP.md) - Complete documentation
- [ADL Specification](../docs/ADL_SPEC.md) - Language reference
- [Main README](../README.md) - Project overview
