# Agentic Brain RAG CLI Commands

This directory contains the CLI implementation for Agentic Brain's Retrieval-Augmented Generation (RAG) system.

## Quick Start

### Query Documents

```bash
# Basic query
agentic-brain query "What is machine learning?"

# Get top 10 results
agentic-brain query "machine learning" --top-k 10

# Filter results
agentic-brain query "Python" --filters '{"type": "pdf"}'

# Output as JSON
agentic-brain query "AI" --json
```

### Index Documents

```bash
# Index a directory
agentic-brain index ./documents

# Index recursively
agentic-brain index ./docs --recursive

# Custom chunk size
agentic-brain index ./papers --chunk-size 1024
```

### Evaluate Results

```bash
# Evaluate from results file
agentic-brain eval results.json

# Output metrics as JSON
agentic-brain eval results.json --json
```

### Health Check

```bash
# Check system health
agentic-brain health

# Output as JSON
agentic-brain health --json
```

### Configuration

```bash
# Show all configuration
agentic-brain config

# Get specific value
agentic-brain config --get chunk_size

# Set configuration
agentic-brain config --set top_k=10
```

## File Structure

- `__init__.py` - Main CLI entry point and argument parser
- `cli.py` - Legacy command definitions (preserved for compatibility)
- `rag_commands.py` - RAG-specific commands (query, index, eval, health, config)
- `commands.py` - Core command implementations and utilities
- `voice_commands.py` - Voice/TTS commands
- `audio_commands.py` - Audio playback commands
- `temporal_commands.py` - Temporal workflow commands
- `mode_commands.py` - Mode management commands
- `region_commands.py` - Regional preferences commands
- `new_config.py` - Configuration wizard

## Command Details

### Query

Retrieve relevant documents and generate answers.

**Usage:**
```bash
agentic-brain query <question> [OPTIONS]
```

**Options:**
- `--top-k INT`: Number of results (default: 5)
- `--filters JSON`: Document filters
- `--json`: JSON output

**Example:**
```bash
agentic-brain query "machine learning" --top-k 3 --json
```

### Index

Index documents for semantic search.

**Usage:**
```bash
agentic-brain index <path> [OPTIONS]
```

**Options:**
- `--recursive`: Search subdirectories
- `--chunk-size INT`: Chunk size in tokens (default: 512)
- `--overlap INT`: Chunk overlap (default: 50)
- `--json`: JSON output

**Example:**
```bash
agentic-brain index ./docs --recursive --json
```

### Eval

Evaluate RAG results against expected outputs.

**Usage:**
```bash
agentic-brain eval <results-file> [OPTIONS]
```

**Options:**
- `--json`: JSON output

**Results File Format (JSON):**
```json
[
  {
    "question": "What is AI?",
    "expected_answer": "Artificial Intelligence...",
    "actual_answer": "AI is...",
    "relevance_score": 0.95
  }
]
```

### Health

Check RAG system health and component status.

**Usage:**
```bash
agentic-brain health [OPTIONS]
```

**Options:**
- `--json`: JSON output

### Config

Get or set system configuration.

**Usage:**
```bash
agentic-brain config [OPTIONS]
```

**Options:**
- `--get KEY`: Get config value
- `--set KEY=VALUE`: Set config value
- `--json`: JSON output

## Testing

Run comprehensive CLI tests:

```bash
# All tests
pytest tests/test_cli_rag.py -v

# Specific test
pytest tests/test_cli_rag.py::test_query_with_valid_question -v

# With coverage
pytest tests/test_cli_rag.py --cov=agentic_brain.cli
```

## Documentation

See `../../docs/CLI_USAGE.md` for comprehensive user guide including:
- Detailed command reference
- Scripting examples
- Integration patterns
- Performance tips
- Troubleshooting

## Architecture

### Command Flow

1. **Argument Parsing** (`__init__.py`)
   - Parse command line arguments
   - Register subcommands
   - Handle global options

2. **Command Dispatch** (`rag_commands.py`)
   - Route to appropriate handler
   - Handle JSON/text output
   - Error handling

3. **RAG System** (`../rag/system.py`)
   - Core RAG logic
   - Document indexing
   - Query execution
   - Result evaluation

## JSON Output Format

All commands support `--json` for machine-readable output:

```json
{
  "command": "query",
  "status": "success|error",
  "data": {},
  "elapsed_ms": 1234
}
```

## Environment Variables

Configure defaults via environment:

```bash
export AGENTIC_MODEL="gpt-4-turbo"
export NEO4J_URI="bolt://localhost:7687"
export REDIS_HOST="localhost"
```

## Development

### Adding a New Command

1. Create command function in `rag_commands.py`:
```python
def cmd_mycommand(args: argparse.Namespace) -> int:
    try:
        # Implementation
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print_warning(f"Failed: {e}")
        return 1
```

2. Register in `register_rag_commands()`:
```python
mycommand_parser = subparsers.add_parser(
    "mycommand",
    help="My command description"
)
mycommand_parser.add_argument("arg", help="Argument")
mycommand_parser.set_defaults(func=cmd_mycommand)
```

3. Add tests in `tests/test_cli_rag.py`

4. Update documentation

## Error Handling

All commands provide helpful error messages:

**Text mode:**
```
⚠ Path does not exist: /invalid/path
```

**JSON mode:**
```json
{"error": "Path does not exist: /invalid/path"}
```

## Performance Tips

1. **Optimize Chunk Size**: Balance context vs. performance
2. **Use Filters**: Narrow document scope
3. **Batch Operations**: Process multiple queries
4. **Monitor Health**: Regular health checks

## Support

- **Documentation**: See `../../docs/CLI_USAGE.md`
- **Issues**: GitHub Issues
- **Examples**: See scripting examples in `../../docs/CLI_USAGE.md`

---

**Last Updated:** 2026-04-02  
**License:** Apache 2.0
