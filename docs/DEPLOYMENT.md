# Deployment

This guide is limited to deployment artifacts that currently exist in the repository.

## Included manifests

- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `docker-compose.test.yml`
- `render.yaml`
- `railway.json`
- `fly.toml`
- `app.yaml`
- `azuredeploy.json`
- `heroku.yml`

## Local production-style run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[api,llm]"
ab serve --host 0.0.0.0 --port 8000
```

## Docker compose

Use the compose files already present in the repo. Review environment variables before starting them.

```bash
docker compose -f docker-compose.yml up -d --build
```

## Health checks after deploy

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/setup
```

## Platform notes

### Render
`render.yaml` exists and can be used as the deployment blueprint.

### Railway
`railway.json` exists and defines Dockerfile-based deployment.

### Fly.io
`fly.toml` exists and points at the repository `Dockerfile`.

### Azure / App Engine / Heroku
The repository includes starter manifests (`azuredeploy.json`, `app.yaml`, `heroku.yml`), but these should be reviewed against the target platform before use.

## Required environment variables

At minimum, set the provider and security values your deployment needs. Common examples:

```bash
JWT_SECRET=replace-me
NEO4J_URI=bolt://host:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=replace-me
REDIS_URL=redis://host:6379/0
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GROQ_API_KEY=...
OLLAMA_HOST=http://host:11434
```

## What this guide no longer claims

This document intentionally avoids undocumented `app.json`, `Procfile`, and other manifests that are not present in the repository.
