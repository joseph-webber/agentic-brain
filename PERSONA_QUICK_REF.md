# Persona Mode Quick Reference

## One Command Setup

```bash
agentic persona
```

Pick a persona → Everything configured automatically!

## Personas at a Glance

| Persona | Mode | Temp | Best For | Token Limit |
|---------|------|------|----------|-------------|
| **Professional** | B | 0.3 | Business, formal | 2048 |
| **Technical** | D | 0.2 | Coding, debugging | 4096 |
| **Creative** | CR | 0.9 | Writing, brainstorming | 4096 |
| **Accessibility** | H | 0.4 | Screen readers | 2048 |
| **Research** | R | 0.5 | Academic, citations | 4096 |
| **Minimal** | F | 0.7 | Simple chatbot | 2048 |

## Temperature Guide

- **0.2** - Very focused, deterministic (code)
- **0.3** - Focused, precise (business)
- **0.5** - Balanced (research)
- **0.7** - Balanced, general (default)
- **0.9** - Creative, diverse (writing)

## Commands

```bash
# Interactive installer
agentic persona

# Quick install (no prompts)
agentic persona --persona technical --non-interactive

# Generate from existing ADL
agentic adl generate

# Validate ADL syntax
agentic adl validate

# Chat after setup
python -m agentic_brain.chat
```

## File Structure After Install

```
your-project/
├── brain.adl              # Your configuration
├── adl_config.py          # Generated Python config
├── .env                   # Environment variables
├── docker-compose.yml     # Deployment
└── adl_api.py            # FastAPI application
```

## Defaults

All personas use:
- **Provider:** `auto` (tries Ollama → OpenAI → Groq)
- **Model:** `llama3.2:3b` (fast, local)
- **Voice:** System default
- **RAG:** Basic (no Neo4j needed)
- **Router:** Smart
- **Rate Limit:** 100/min (150 for technical)

## Customization Flow

1. Install: `agentic persona`
2. Edit: `nano brain.adl`
3. Regenerate: `agentic adl generate`
4. Use: `python -m agentic_brain.chat`

## Switch Models

Edit `brain.adl`:
```adl
llm Primary {
  model "llama3.2:8b"    # Larger model
  temperature 0.5         # Adjust creativity
}
```

Then: `agentic adl generate`

## Use OpenAI

```adl
llm Primary {
  provider openai
  apiKey "${OPENAI_API_KEY}"
  model "gpt-4"
}
```

Add to `.env`:
```bash
OPENAI_API_KEY=sk-your-key
```

## Documentation

- **Full Guide:** [docs/PERSONA_SETUP.md](../docs/PERSONA_SETUP.md)
- **Examples:** [examples/personas/](../examples/personas/)
- **ADL Reference:** Run `agentic adl --help`

---

**Everything flows from persona choice. Pick once, configured forever!**
