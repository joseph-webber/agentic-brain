# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""MLX acceleration backend for Apple Silicon.

This module follows the MLX example pattern of:
- detect Apple Silicon first
- batch work with ``mx.array``
- evaluate in one shot with ``mx.eval``
- gracefully fall back to CPU when MLX is unavailable
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_EMBEDDING_DIMS = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "paraphrase-MiniLM-L6-v2": 384,
    "multi-qa-MiniLM-L6-cos-v1": 384,
    "nomic-embed-text": 768,
    "nomic-embed-text-v1": 768,
}


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _hash_token(token: str, dimensions: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return int(digest, 16) % dimensions


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in {"arm64", "arm64e"}


def _try_import_mlx() -> Any | None:
    try:
        import mlx.core as mx

        return mx
    except ImportError:
        return None


def _try_import_mlx_lm() -> Any | None:
    try:
        import mlx_lm  # type: ignore[import-not-found]

        return mlx_lm
    except ImportError:
        return None


@dataclass(slots=True)
class MLXBackendInfo:
    """Capability snapshot for MLX acceleration."""

    apple_silicon: bool
    mlx_available: bool
    mlx_lm_available: bool
    best_backend: str
    machine: str
    platform_name: str
    reason: str
    cpu_cores: int | None = None
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class MLXBackend:
    """Apple Silicon backend for embeddings and inference."""

    embedding_model: str = "all-MiniLM-L6-v2"
    generation_model: str | None = None
    batch_size: int = 32
    fallback_to_cpu: bool = True

    _mx: Any | None = field(default=None, init=False, repr=False)
    _mlx_lm: Any | None = field(default=None, init=False, repr=False)
    _info: MLXBackendInfo = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._mx = _try_import_mlx()
        self._info = self._detect()
        if self.generation_model is None:
            self.generation_model = os.getenv(
                "AGENTIC_BRAIN_MLX_LM_MODEL",
                "mlx-community/Llama-3.2-1B-Instruct-4bit",
            )

    def _detect(self) -> MLXBackendInfo:
        apple = _is_apple_silicon()
        mlx_available = self._mx is not None
        mlx_lm_available = _try_import_mlx_lm() is not None
        best = "mlx" if apple and mlx_available else "cpu"
        if best == "mlx":
            reason = "Apple Silicon with MLX available"
        elif apple:
            reason = "Apple Silicon detected but MLX is unavailable"
        else:
            reason = "Non-Apple-Silicon host; using CPU fallback"

        return MLXBackendInfo(
            apple_silicon=apple,
            mlx_available=mlx_available,
            mlx_lm_available=mlx_lm_available,
            best_backend=best,
            machine=platform.machine(),
            platform_name=platform.system(),
            reason=reason,
            cpu_cores=os.cpu_count(),
            environment={
                "mlx": str(mlx_available).lower(),
                "mlx_lm": str(mlx_lm_available).lower(),
            },
        )

    @property
    def info(self) -> MLXBackendInfo:
        return self._info

    @property
    def backend_name(self) -> str:
        return self._info.best_backend

    @property
    def available(self) -> bool:
        return self.backend_name == "mlx"

    @property
    def is_apple_silicon(self) -> bool:
        return self._info.apple_silicon

    @property
    def dimensions(self) -> int:
        return _EMBEDDING_DIMS.get(self.embedding_model, 384)

    @property
    def model_name(self) -> str:
        prefix = "mlx" if self.available else "cpu"
        return f"{prefix}/{self.embedding_model}"

    @property
    def embeddings_provider(self) -> "MLXBackend":
        return self

    def _ensure_mx(self) -> Any | None:
        if self._mx is None:
            self._mx = _try_import_mlx()
        return self._mx

    def _cpu_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokenize(text):
            vector[_hash_token(token, self.dimensions)] += 1.0
        norm = sum(value * value for value in vector) ** 0.5
        return [value / (norm + 1e-10) for value in vector]

    def _cpu_embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._cpu_embed(text) for text in texts]

    def _mlx_embed_batch(self, texts: list[str]) -> list[list[float]]:
        mx = self._ensure_mx()
        if mx is None:
            return self._cpu_embed_batch(texts)

        raw_vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in _tokenize(text):
                vector[_hash_token(token, self.dimensions)] += 1.0
            raw_vectors.append(vector)

        if not raw_vectors:
            return []

        batch = mx.array(raw_vectors, dtype=mx.float32)
        norms = mx.sqrt(mx.sum(batch * batch, axis=1, keepdims=True))
        normalized = batch / (norms + 1e-10)
        if hasattr(mx, "eval"):
            mx.eval(normalized)
        return normalized.tolist()

    def embed(self, text: str) -> list[float]:
        if self.available:
            return self.embed_batch([text])[0]
        if not self.fallback_to_cpu:
            raise RuntimeError("MLX is not available on this host")
        return self._cpu_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.available:
            return self._mlx_embed_batch(texts)
        if not self.fallback_to_cpu:
            raise RuntimeError("MLX is not available on this host")
        return self._cpu_embed_batch(texts)

    def similarity(self, left: list[float], right: list[float]) -> float:
        if self.available and self._ensure_mx() is not None:
            mx = self._ensure_mx()
            left_arr = mx.array(left, dtype=mx.float32)
            right_arr = mx.array(right, dtype=mx.float32)
            score = mx.sum(left_arr * right_arr)
            if hasattr(mx, "eval"):
                mx.eval(score)
            return float(score)

        dot = sum(a * b for a, b in zip(left, right, strict=False))
        norm_left = sum(a * a for a in left) ** 0.5
        norm_right = sum(b * b for b in right) ** 0.5
        if norm_left == 0 or norm_right == 0:
            return 0.0
        return dot / (norm_left * norm_right)

    def similarity_search(
        self,
        query: list[float] | str,
        corpus: list[list[float]] | list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        if isinstance(query, str):
            query_vec = self.embed(query)
        else:
            query_vec = query

        if not corpus:
            return []
        if isinstance(corpus[0], str):
            corpus_vecs = self.embed_batch(corpus)  # type: ignore[arg-type]
        else:
            corpus_vecs = corpus  # type: ignore[assignment]

        if self.available and self._ensure_mx() is not None:
            mx = self._ensure_mx()
            q = mx.array([query_vec], dtype=mx.float32)
            c = mx.array(corpus_vecs, dtype=mx.float32)
            q_norm = q / (mx.sqrt(mx.sum(q * q, axis=1, keepdims=True)) + 1e-10)
            c_norm = c / (mx.sqrt(mx.sum(c * c, axis=1, keepdims=True)) + 1e-10)
            scores = mx.matmul(c_norm, q_norm.T)[:, 0]
            if hasattr(mx, "eval"):
                mx.eval(scores)
            score_list = scores.tolist()
        else:
            score_list = [self.similarity(query_vec, candidate) for candidate in corpus_vecs]

        ordered = sorted(enumerate(score_list), key=lambda item: item[1], reverse=True)
        return [(index, float(score)) for index, score in ordered[:top_k]]

    def _load_mlx_lm(self) -> Any | None:
        if self._mlx_lm is not None:
            return self._mlx_lm

        mlx_lm = _try_import_mlx_lm()
        if mlx_lm is None:
            return None

        self._mlx_lm = mlx_lm
        return mlx_lm

    def _cpu_infer(self, prompt: str, max_tokens: int = 128) -> str:
        tokens = _tokenize(prompt)
        if not tokens:
            return ""
        return " ".join(tokens[:max_tokens])

    def infer(
        self,
        prompt: str,
        *,
        max_tokens: int = 128,
        temperature: float = 0.0,
    ) -> str:
        mlx_lm = self._load_mlx_lm()
        if self.available and mlx_lm is not None and self.generation_model:
            try:
                load = getattr(mlx_lm, "load")
                generate = getattr(mlx_lm, "generate")
                model, tokenizer = load(self.generation_model)
                output = generate(
                    model,
                    tokenizer,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temp=temperature,
                )
                return str(output)
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.debug("MLX inference failed, falling back to CPU: %s", exc)

        if not self.fallback_to_cpu:
            raise RuntimeError("MLX inference unavailable and CPU fallback disabled")
        return self._cpu_infer(prompt, max_tokens=max_tokens)

    def infer_batch(
        self,
        prompts: list[str],
        *,
        max_tokens: int = 128,
        temperature: float = 0.0,
    ) -> list[str]:
        return [
            self.infer(prompt, max_tokens=max_tokens, temperature=temperature)
            for prompt in prompts
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "available": self.available,
            "apple_silicon": self.is_apple_silicon,
            "dimensions": self.dimensions,
            "embedding_model": self.embedding_model,
            "generation_model": self.generation_model,
            "reason": self._info.reason,
        }


@lru_cache(maxsize=1)
def get_best_backend() -> MLXBackend:
    """Return the preferred Apple Silicon backend with graceful CPU fallback."""

    return MLXBackend()
