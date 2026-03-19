# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
Embedding Provider - Generate embeddings for semantic search.

Supports:
- Ollama (local, free, fast on Apple Silicon)
- OpenAI (cloud, best quality)
- Sentence Transformers (local, good balance)

For MLX-accelerated embeddings on Apple Silicon, see brain-core.
"""

import os
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Cache for embeddings
CACHE_DIR = Path.home() / ".agentic_brain" / "embedding_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    text: str
    embedding: List[float]
    model: str
    dimensions: int
    cached: bool = False


class EmbeddingProvider(ABC):
    """Base class for embedding providers."""
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding dimensions."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier."""
        pass


class OllamaEmbeddings(EmbeddingProvider):
    """
    Ollama embeddings - local, free, fast.
    
    Requires: ollama running with nomic-embed-text model
    Install: ollama pull nomic-embed-text
    """
    
    def __init__(
        self, 
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url
        self._dimensions = 768  # nomic-embed-text default
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        import requests
        
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["embedding"]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch (sequential for Ollama)."""
        return [self.embed(text) for text in texts]
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    @property
    def model_name(self) -> str:
        return f"ollama/{self.model}"


class OpenAIEmbeddings(EmbeddingProvider):
    """
    OpenAI embeddings - best quality, requires API key.
    
    Set OPENAI_API_KEY environment variable.
    """
    
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None
    ):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._dimensions = 1536 if "large" in model else 512
        
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY.")
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding using OpenAI."""
        import requests
        
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={"model": self.model, "input": text},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch."""
        import requests
        
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={"model": self.model, "input": texts},
            timeout=60
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    @property
    def model_name(self) -> str:
        return f"openai/{self.model}"


class CachedEmbeddings(EmbeddingProvider):
    """
    Caching wrapper for any embedding provider.
    
    Caches embeddings to disk to avoid recomputation.
    """
    
    def __init__(self, provider: EmbeddingProvider, cache_dir: Optional[Path] = None):
        self.provider = provider
        self.cache_dir = cache_dir or CACHE_DIR / provider.model_name.replace("/", "_")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    def _get_cached(self, text: str) -> Optional[List[float]]:
        """Get cached embedding if exists."""
        cache_file = self.cache_dir / f"{self._cache_key(text)}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except (json.JSONDecodeError, ValueError, IOError) as e:
                # json.JSONDecodeError: corrupted cache file
                # ValueError: invalid JSON content
                # IOError: read error
                logger.debug(f"Cache read failed for {cache_file}: {e}")
                pass
        return None
    
    def _set_cached(self, text: str, embedding: List[float]) -> None:
        """Cache embedding."""
        cache_file = self.cache_dir / f"{self._cache_key(text)}.json"
        cache_file.write_text(json.dumps(embedding))
    
    def embed(self, text: str) -> List[float]:
        """Get embedding (from cache or generate)."""
        cached = self._get_cached(text)
        if cached:
            return cached
        
        embedding = self.provider.embed(text)
        self._set_cached(text, embedding)
        return embedding
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for batch with caching."""
        results = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache first
        for i, text in enumerate(texts):
            cached = self._get_cached(text)
            if cached:
                results.append(cached)
            else:
                results.append(None)
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # Generate missing embeddings
        if uncached_texts:
            new_embeddings = self.provider.embed_batch(uncached_texts)
            for idx, embedding in zip(uncached_indices, new_embeddings):
                results[idx] = embedding
                self._set_cached(texts[idx], embedding)
        
        return results
    
    @property
    def dimensions(self) -> int:
        return self.provider.dimensions
    
    @property
    def model_name(self) -> str:
        return f"cached/{self.provider.model_name}"


def get_embeddings(
    provider: str = "auto",
    cache: bool = True
) -> EmbeddingProvider:
    """
    Get an embedding provider.
    
    Args:
        provider: "ollama", "openai", or "auto" (tries ollama first)
        cache: Whether to cache embeddings
    
    Returns:
        EmbeddingProvider instance
    
    Example:
        embeddings = get_embeddings()
        vector = embeddings.embed("Hello world")
    """
    if provider == "auto":
        # Try Ollama first (local, free)
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.ok:
                provider = "ollama"
            else:
                provider = "openai"
        except (ConnectionError, TimeoutError, OSError) as e:
            # ConnectionError: network unreachable
            # TimeoutError: request timeout
            # OSError: system error
            logger.debug(f"Ollama not available, falling back to OpenAI: {e}")
            provider = "openai"
    
    if provider == "ollama":
        base = OllamaEmbeddings()
    elif provider == "openai":
        base = OpenAIEmbeddings()
    else:
        raise ValueError(f"Unknown provider: {provider}")
    
    if cache:
        return CachedEmbeddings(base)
    return base
