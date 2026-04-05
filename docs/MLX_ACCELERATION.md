# MLX Acceleration

Agentic Brain now has a small MLX backend for Apple Silicon:

- detects Apple Silicon and MLX availability
- batches embeddings with `mx.array`
- evaluates work with `mx.eval`
- falls back to CPU automatically

## Usage

```python
from agentic_brain.acceleration import get_best_backend

backend = get_best_backend()
print(backend.backend_name)   # mlx or cpu
print(backend.embed("hello"))
print(backend.infer("Summarize this text"))
```

## RAG integration

`RAGPipeline` now prefers the shared MLX backend when Apple Silicon + MLX
are available. Existing `get_embeddings(provider="mlx")` calls also route
through the backend and keep working on CPU-only hosts.

## CPU fallback

If MLX is missing, the backend keeps working with deterministic CPU
embeddings and CPU inference.

## Environment

Optional:

- `AGENTIC_BRAIN_MLX_LM_MODEL` — overrides the MLX generation model name

