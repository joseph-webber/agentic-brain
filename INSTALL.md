# Agentic Brain Installation Guide

> Version: 3.1.0 • Python: 3.11+

## Quick install

### From PyPI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "agentic-brain[api,llm]"
```

### From this repository

```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,api,llm]"
```

## Common extras

- `api` — FastAPI server and WebSocket support
- `llm` — cloud and local LLM integrations
- `memory` — memory integrations
- `graphrag` — Neo4j GraphRAG helpers
- `mlx` — Apple Silicon acceleration
- `enhanced` — convenience bundle of commonly used integrations
- `docs` — MkDocs documentation tooling

## Verify the install

```bash
ab --help
ab doctor
ab version
```

## Start the API

```bash
ab serve --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

## Optional services

The chat API works without Neo4j, Redis, or external LLM credentials. Add them when you need: 

- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
- `REDIS_URL`
- `OLLAMA_HOST` or provider API keys such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`

For platform details, see `docs/INSTALL.md`.
