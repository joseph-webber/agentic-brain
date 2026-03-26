# 🛠️ Troubleshooting Guide

This guide helps you resolve common issues encountered while using the Agentic Brain.

## ⚠️ Startup Issues

### 1. `ModuleNotFoundError: No module named 'agentic_brain'`
**Cause:** Python environment issue.
**Solution:**
- Ensure `venv` is activated (`source venv/bin/activate`).
- Run `pip install -r requirements.txt`.
- Check your `PYTHONPATH`.

### 2. `.env` File Missing
**Cause:** Configuration file not found.
**Solution:**
- Copy `.env.example` to `.env`.
- Fill in required keys.

## 📡 Connection Failures

### 1. Neo4j Connection Refused
**Cause:** Neo4j service not running or misconfigured.
**Solution:**
- Check `NEO4J_URI` in `.env` (default: `bolt://localhost:7687`).
- Ensure Neo4j container/service is active (`docker ps` or `neo4j status`).
- Verify credentials (`NEO4J_USER`, `NEO4J_PASSWORD`).

### 2. LLM Provider Error (401/403)
**Cause:** Invalid API key or quota exceeded.
**Solution:**
- Double-check `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.
- Verify your account billing status.

## 💾 Memory Issues

### 1. "I forgot what you said"
**Cause:** Embedding failure or Neo4j query timeout.
**Solution:**
- Check `OPENAI_API_KEY` (embeddings require it).
- Inspect logs for Neo4j errors.
- Restart Neo4j if queries are hanging.

### 2. Slow Response Times
**Cause:** Large context window or complex graph queries.
**Solution:**
- Run `context_compact()` to clean up old context.
- Optimize Neo4j indexes.

## 🐛 Debugging

### Enable Verbose Logging
Set `LOG_LEVEL=DEBUG` in your `.env` file to see detailed logs.

### Check Logs
Inspect `logs/brain.log` (or console output) for stack traces.

### Need More Help?
- Check GitHub Issues.
- Review `docs/` folder.
