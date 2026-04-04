# Installation

This guide reflects the current `pyproject.toml` for Agentic Brain 3.1.0.

## Requirements

- Python 3.11 or newer
- `pip` or `pipx`
- Optional: Docker / Docker Compose for local services
- Optional: Ollama for local LLM chat

## Recommended install

### PyPI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "agentic-brain[api,llm]"
```

### Editable checkout

```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,api,llm]"
```

## Extras you can enable

```bash
pip install "agentic-brain[memory]"
pip install "agentic-brain[graphrag]"
pip install "agentic-brain[mlx]"
pip install "agentic-brain[enhanced]"
pip install "agentic-brain[docs]"
```

## CLI verification

```bash
ab --help
ab doctor
ab version
```

## Run the API server

```bash
ab serve --host 127.0.0.1 --port 8000
```

Available endpoints after startup:

- `GET /health`
- `POST /chat`
- `GET /chat/stream`
- `WS /ws/chat`
- `GET /docs`

## Optional local services

### Ollama

```bash
ollama serve
ollama pull llama3.1:8b
```

### Docker compose

Use the repository manifests that already exist (`docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.test.yml`) if you want a container-based stack.

## Environment variables

Most installs start with just one provider configured. Common variables:

```bash
OLLAMA_HOST=http://localhost:11434
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GROQ_API_KEY=...
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=replace-me-in-production
```

## Troubleshooting

- `ab doctor` shows provider status and setup hints.
- `GET /setup` returns provider diagnostics from the running API.
- `GET /setup/help/{provider}` returns provider-specific setup help.
