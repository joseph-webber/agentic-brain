# Agentic Brain RAG CLI Usage Guide

## Overview

The Agentic Brain CLI provides powerful commands for managing Retrieval-Augmented Generation (RAG) workflows, including document indexing, semantic search, result evaluation, and system health monitoring.

**Installation:**

```bash
pip install agentic-brain
```

**Quick Start:**

```bash
# Query documents
agentic-brain query "What is machine learning?"

# Index documents
agentic-brain index ./my_documents

# Check system health
agentic-brain health

# Show configuration
agentic-brain config
```

---

## Commands

### 1. Query Command

Execute semantic search queries against your indexed documents.

**Syntax:**
```bash
agentic-brain query "your question here" [OPTIONS]
```

**Examples:**

```bash
# Basic query
agentic-brain query "What are the benefits of machine learning?"

# Get top 10 results
agentic-brain query "machine learning" --top-k 10

# Output as JSON
agentic-brain query "AI" --json

# Filter by document source
agentic-brain query "Python programming" --filters '{"source": "pdf"}'
```

**Options:**

- `question` (required): The question to search for
- `--top-k INTEGER`: Number of top results to return (default: 5)
- `--filters JSON`: JSON object for filtering documents
- `--json`: Output results as JSON

**Output:**

**Text format:**
```
→ RAG Query

ℹ Querying: What is machine learning?

✓ Query completed in 1.23s

Answer:
Machine learning is a subset of artificial intelligence that enables systems
to learn and improve from experience without being explicitly programmed.

Sources:
  1. machine_learning_101.pdf
  2. ai_fundamentals.md
  3. data_science_guide.pdf

Relevance Score: 92%
```

**JSON format:**
```json
{
  "question": "What is machine learning?",
  "answer": "Machine learning is a subset of artificial intelligence...",
  "sources": [
    "machine_learning_101.pdf",
    "ai_fundamentals.md"
  ],
  "relevance_score": 0.92,
  "elapsed_ms": 1234.56
}
```

---

### 2. Index Command

Index documents from a directory for semantic search.

**Syntax:**
```bash
agentic-brain index <path> [OPTIONS]
```

**Examples:**

```bash
# Index a directory
agentic-brain index ./documents

# Index with subdirectories
agentic-brain index ./docs --recursive

# Custom chunk size
agentic-brain index ./research --chunk-size 1024

# Get JSON output
agentic-brain index ./papers --json
```

**Options:**

- `path` (required): Path to documents directory or file
- `--recursive`: Index subdirectories recursively
- `--chunk-size INTEGER`: Size of document chunks (default: 512)
- `--overlap INTEGER`: Overlap between chunks in tokens (default: 50)
- `--json`: Output indexing statistics as JSON

**Output:**

**Text format:**
```
→ Document Indexing

ℹ Indexing documents from: ./documents

✓ Indexed 42 documents (256 chunks) in 12.45s
```

**JSON format:**
```json
{
  "path": "./documents",
  "documents_indexed": 42,
  "chunks_created": 256,
  "elapsed_ms": 12450
}
```

**Supported File Types:**

- PDF (.pdf)
- Markdown (.md, .markdown)
- Text (.txt)
- Word (.docx)
- Excel (.xlsx)
- PowerPoint (.pptx)
- HTML (.html)
- JSON (.json)
- YAML (.yml, .yaml)

---

### 3. Eval Command

Evaluate RAG results and calculate performance metrics.

**Syntax:**
```bash
agentic-brain eval <results-file> [OPTIONS]
```

**Examples:**

```bash
# Evaluate results from file
agentic-brain eval results.json

# Get metrics as JSON
agentic-brain eval test_results.json --json

# Evaluate multiple result sets
for file in results_*.json; do
  agentic-brain eval "$file"
done
```

**Options:**

- `results` (required): Path to results file (JSON format)
- `--json`: Output metrics as JSON

**Results File Format:**

```json
[
  {
    "question": "What is AI?",
    "expected_answer": "Artificial Intelligence...",
    "actual_answer": "AI is artificial intelligence...",
    "relevance_score": 0.95
  },
  {
    "question": "How does ML work?",
    "expected_answer": "ML uses algorithms...",
    "actual_answer": "Machine learning works by...",
    "relevance_score": 0.88
  }
]
```

**Output:**

**Text format:**
```
→ Results Evaluation

ℹ Evaluating 25 results

✓ Evaluation completed in 5.67s

Metrics:
  precision: 92%
  recall: 87%
  f1_score: 89%
  avg_relevance: 0.90
```

**JSON format:**
```json
{
  "total_results": 25,
  "metrics": {
    "precision": 0.92,
    "recall": 0.87,
    "f1_score": 0.89,
    "avg_relevance": 0.90
  },
  "elapsed_ms": 5670
}
```

---

### 4. Health Command

Check the health status of the RAG system and all components.

**Syntax:**
```bash
agentic-brain health [OPTIONS]
```

**Examples:**

```bash
# Check system health
agentic-brain health

# Output as JSON
agentic-brain health --json

# Monitor health in CI/CD
agentic-brain health --json | jq '.status'
```

**Options:**

- `--json`: Output health status as JSON

**Output:**

**Text format:**
```
→ System Health Check

✓ System status: healthy

Components:
  neo4j: ok
  redis: ok
  embeddings: ok
  openai: ok
```

**JSON format:**
```json
{
  "status": "healthy",
  "components": {
    "neo4j": {
      "status": "ok",
      "response_time_ms": 12
    },
    "redis": {
      "status": "ok",
      "response_time_ms": 5
    },
    "embeddings": {
      "status": "ok",
      "response_time_ms": 234
    },
    "openai": {
      "status": "ok",
      "response_time_ms": 345
    }
  },
  "elapsed_ms": 600
}
```

**Status Values:**

- `healthy`: All systems operational
- `degraded`: Some components slow or offline
- `offline`: System unavailable

---

### 5. Config Command

Manage RAG system configuration.

**Syntax:**
```bash
agentic-brain config [OPTIONS]
```

**Examples:**

```bash
# Show all configuration
agentic-brain config

# Get specific setting
agentic-brain config --get chunk_size

# Set configuration value
agentic-brain config --set top_k=10

# Export config as JSON
agentic-brain config --json > config.json
```

**Options:**

- `--get KEY`: Get specific configuration value
- `--set KEY=VALUE`: Set configuration value
- `--json`: Output configuration as JSON

**Output:**

**Text format (show all):**
```
→ Configuration

Configuration:
  chunk_size: 512
  overlap: 50
  top_k: 5
  model: gpt-4-turbo
  temperature: 0.7
  embeddings_model: text-embedding-3-large
  max_results: 100
```

**Text format (get specific):**
```
chunk_size: 512
```

**Text format (set):**
```
✓ Set top_k = 10
```

**JSON format:**
```json
{
  "chunk_size": 512,
  "overlap": 50,
  "top_k": 5,
  "model": "gpt-4-turbo",
  "temperature": 0.7,
  "embeddings_model": "text-embedding-3-large",
  "max_results": 100
}
```

**Common Configuration Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chunk_size` | int | 512 | Size of document chunks in tokens |
| `overlap` | int | 50 | Overlap between chunks |
| `top_k` | int | 5 | Number of results to return |
| `model` | string | gpt-4-turbo | LLM model for generation |
| `temperature` | float | 0.7 | Generation temperature (0-1) |
| `embeddings_model` | string | text-embedding-3-large | Embeddings model |
| `max_results` | int | 100 | Maximum stored results |

---

## JSON Output

All commands support `--json` flag for machine-readable output, perfect for scripts and CI/CD pipelines.

**Query JSON:**
```json
{
  "question": "string",
  "answer": "string",
  "sources": ["string"],
  "relevance_score": 0.0,
  "elapsed_ms": 0.0
}
```

**Index JSON:**
```json
{
  "path": "string",
  "documents_indexed": 0,
  "chunks_created": 0,
  "elapsed_ms": 0.0
}
```

**Eval JSON:**
```json
{
  "total_results": 0,
  "metrics": {"key": "value"},
  "elapsed_ms": 0.0
}
```

**Health JSON:**
```json
{
  "status": "healthy|degraded|offline",
  "components": {"name": {"status": "string"}},
  "elapsed_ms": 0.0
}
```

**Config JSON:**
```json
{
  "key1": "value1",
  "key2": "value2"
}
```

---

## Scripting Examples

### Batch Query Multiple Questions

```bash
#!/bin/bash

questions=(
  "What is machine learning?"
  "How does deep learning work?"
  "What are neural networks?"
)

for q in "${questions[@]}"; do
  echo "Query: $q"
  agentic-brain query "$q" --json | jq '.relevance_score'
  echo "---"
done
```

### Automated Health Monitoring

```bash
#!/bin/bash

# Check health every 5 minutes
while true; do
  health=$(agentic-brain health --json)
  status=$(echo $health | jq -r '.status')
  
  if [ "$status" != "healthy" ]; then
    echo "WARNING: System status is $status"
    echo $health | jq '.components'
  fi
  
  sleep 300
done
```

### Extract Metrics from Evaluation

```bash
#!/bin/bash

# Run eval and extract key metrics
metrics=$(agentic-brain eval results.json --json)

precision=$(echo $metrics | jq '.metrics.precision')
recall=$(echo $metrics | jq '.metrics.recall')
f1=$(echo $metrics | jq '.metrics.f1_score')

echo "Precision: $precision"
echo "Recall: $recall"
echo "F1 Score: $f1"

# Optional: Send to monitoring system
curl -X POST http://monitoring.example.com/metrics \
  -d "precision=$precision&recall=$recall&f1=$f1"
```

### Continuous Indexing Pipeline

```bash
#!/bin/bash

# Index documents from multiple sources
for source in ./docs ./papers ./kb; do
  if [ -d "$source" ]; then
    echo "Indexing: $source"
    agentic-brain index "$source" --recursive --json | jq '.'
  fi
done
```

---

## Error Handling

### Common Errors and Solutions

**Error: "No results found"**
```bash
# Try with less strict filters or higher top_k
agentic-brain query "question" --top-k 10 --filters '{}'
```

**Error: "Path does not exist"**
```bash
# Verify the path exists
ls -la ./documents

# Then index
agentic-brain index ./documents
```

**Error: "Results file not found"**
```bash
# Check file path and format
file results.json
cat results.json | head -20
```

**Error: "Connection failed"**
```bash
# Check system health first
agentic-brain health --json

# Verify Neo4j and Redis are running
docker ps | grep neo4j
docker ps | grep redis
```

---

## Performance Tips

1. **Optimize Chunk Size**: Balance between context and performance
   ```bash
   agentic-brain index ./docs --chunk-size 1024  # Larger chunks
   ```

2. **Use Filters**: Narrow down search space
   ```bash
   agentic-brain query "topic" --filters '{"type": "pdf"}'
   ```

3. **Batch Operations**: Use JSON output for automation
   ```bash
   for q in questions.txt; do
     agentic-brain query "$q" --json >> results.jsonl
   done
   ```

4. **Monitor Health**: Regular health checks prevent issues
   ```bash
   agentic-brain health --json | jq '.status'
   ```

---

## Integration Examples

### With Python Scripts

```python
import subprocess
import json

def query_rag(question: str) -> dict:
    result = subprocess.run(
        ["agentic-brain", "query", question, "--json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

answer = query_rag("What is AI?")
print(answer["answer"])
print(f"Relevance: {answer['relevance_score']:.1%}")
```

### With CI/CD (GitHub Actions)

```yaml
- name: Check RAG Health
  run: |
    health=$(agentic-brain health --json)
    status=$(echo $health | jq -r '.status')
    if [ "$status" != "healthy" ]; then
      echo "::error::RAG system not healthy: $status"
      exit 1
    fi

- name: Evaluate Results
  run: |
    agentic-brain eval test_results.json --json
```

### With Docker

```dockerfile
FROM python:3.11

RUN pip install agentic-brain

WORKDIR /app
COPY documents /app/documents

CMD ["agentic-brain", "index", "/app/documents", "--recursive"]
```

---

## Environment Variables

Configure default behavior via environment variables:

```bash
# Default LLM model
export AGENTIC_MODEL="gpt-4-turbo"

# Neo4j connection
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="password"

# Redis connection
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

# Embeddings API
export OPENAI_API_KEY="sk-..."
```

---

## Version Information

Get CLI version and system information:

```bash
# Show version
agentic-brain --version

# Show help
agentic-brain --help
agentic-brain query --help
agentic-brain index --help
```

---

## Support & Documentation

- **GitHub**: https://github.com/agentic-brain/agentic-brain
- **Issues**: https://github.com/agentic-brain/agentic-brain/issues
- **Docs**: https://agentic-brain.readthedocs.io

---

**Last Updated:** 2026-04-02  
**License:** Apache 2.0
