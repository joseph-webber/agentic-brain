# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
RAG Pipeline - Complete retrieval-augmented generation.

Combines retrieval, context building, and LLM generation
into a single easy-to-use pipeline.

For enterprise features (multi-tenant, cross-encoder reranking,
streaming responses, MLX acceleration), see brain-core.
"""

import os
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from .retriever import Retriever, RetrievedChunk
from .embeddings import EmbeddingProvider, get_embeddings

logger = logging.getLogger(__name__)


# Response cache
CACHE_DIR = Path.home() / ".agentic_brain" / "rag_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RAGResult:
    """Result from RAG query."""
    query: str
    answer: str
    sources: List[RetrievedChunk]
    confidence: float
    model: str
    cached: bool = False
    generation_time_ms: float = 0
    
    @property
    def has_sources(self) -> bool:
        return len(self.sources) > 0
    
    @property
    def confidence_level(self) -> str:
        if self.confidence >= 0.8:
            return "high"
        elif self.confidence >= 0.5:
            return "medium"
        elif self.confidence >= 0.3:
            return "low"
        return "uncertain"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "sources": [
                {"content": s.content[:200], "source": s.source, "score": s.score}
                for s in self.sources
            ],
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "model": self.model,
        }
    
    def format_with_citations(self) -> str:
        """Format answer with source citations."""
        lines = [self.answer, "", "---", "Sources:"]
        for i, source in enumerate(self.sources[:3], 1):
            lines.append(f"[{i}] {source.source} (confidence: {source.confidence})")
        return "\n".join(lines)


class RAGPipeline:
    """
    Complete RAG pipeline.
    
    Usage:
        # Simple usage
        rag = RAGPipeline()
        result = rag.query("What is the deployment process?")
        print(result.answer)
        
        # With Neo4j
        rag = RAGPipeline(
            neo4j_uri="bolt://localhost:7687",
            neo4j_password="password"
        )
        result = rag.query("Status of project X?", sources=["JiraTicket"])
        
        # With specific LLM
        rag = RAGPipeline(llm_provider="ollama", llm_model="llama3.1:8b")
    """
    
    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        llm_provider: str = "ollama",
        llm_model: str = "llama3.1:8b",
        llm_base_url: str = "http://localhost:11434",
        cache_ttl_hours: int = 4,
    ):
        self.retriever = Retriever(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            embedding_provider=embedding_provider
        )
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.cache_ttl_hours = cache_ttl_hours
    
    def _cache_key(self, query: str, sources: List[str]) -> str:
        """Generate cache key."""
        key_data = f"{query}:{sorted(sources)}:{self.llm_model}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _get_cached(self, cache_key: str) -> Optional[RAGResult]:
        """Get cached result if valid."""
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                cached_time = datetime.fromisoformat(data["timestamp"])
                age_hours = (datetime.now() - cached_time).total_seconds() / 3600
                
                if age_hours < self.cache_ttl_hours:
                    return RAGResult(
                        query=data["query"],
                        answer=data["answer"],
                        sources=[],  # Don't cache full sources
                        confidence=data["confidence"],
                        model=data["model"],
                        cached=True
                    )
            except (json.JSONDecodeError, ValueError, KeyError, IOError) as e:
                # json.JSONDecodeError: corrupted cache file
                # ValueError: invalid datetime format
                # KeyError: missing expected field
                # IOError: file read error
                logger.debug(f"Cache read failed: {e}")
                pass
        return None
    
    def _set_cached(self, cache_key: str, result: RAGResult) -> None:
        """Cache a result."""
        cache_file = CACHE_DIR / f"{cache_key}.json"
        data = {
            "query": result.query,
            "answer": result.answer,
            "confidence": result.confidence,
            "model": result.model,
            "timestamp": datetime.now().isoformat()
        }
        cache_file.write_text(json.dumps(data))
    
    def _build_context(self, chunks: List[RetrievedChunk], max_tokens: int = 3000) -> str:
        """Build context string from chunks."""
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough token estimate
        
        for chunk in chunks:
            chunk_context = chunk.to_context()
            if total_chars + len(chunk_context) > max_chars:
                break
            context_parts.append(chunk_context)
            total_chars += len(chunk_context)
        
        return "\n\n".join(context_parts)
    
    def _generate_ollama(self, prompt: str, context: str) -> str:
        """Generate response using Ollama."""
        import requests
        
        system = """You are a helpful assistant. Answer based on the provided context.
If the context doesn't contain relevant information, say so.
Be concise and accurate. Cite sources when possible."""
        
        full_prompt = f"""Context:
{context}

Question: {prompt}

Answer:"""
        
        response = requests.post(
            f"{self.llm_base_url}/api/generate",
            json={
                "model": self.llm_model,
                "prompt": full_prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.3}
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["response"]
    
    def _generate_openai(self, prompt: str, context: str) -> str:
        """Generate response using OpenAI."""
        import requests
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required")
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": "Answer based on the provided context. Be concise and accurate."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {prompt}"}
                ],
                "temperature": 0.3
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def _generate(self, prompt: str, context: str) -> str:
        """Generate response using configured LLM."""
        if self.llm_provider == "ollama":
            return self._generate_ollama(prompt, context)
        elif self.llm_provider == "openai":
            return self._generate_openai(prompt, context)
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
    
    def query(
        self,
        query: str,
        k: int = 5,
        sources: Optional[List[str]] = None,
        use_cache: bool = True,
        min_score: float = 0.3
    ) -> RAGResult:
        """
        Query the RAG pipeline.
        
        Args:
            query: Question to answer
            k: Number of documents to retrieve
            sources: Specific sources to search
            use_cache: Whether to use cached responses
            min_score: Minimum relevance score
        
        Returns:
            RAGResult with answer and sources
        """
        import time
        start = time.time()
        
        sources = sources or ["Document", "Memory", "Knowledge"]
        
        # Check cache
        if use_cache:
            cache_key = self._cache_key(query, sources)
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        # Retrieve relevant documents
        chunks = self.retriever.search(query, k=k, sources=sources)
        chunks = [c for c in chunks if c.score >= min_score]
        
        # Build context
        context = self._build_context(chunks)
        
        # Generate response
        if not context:
            answer = "I don't have enough information to answer that question."
            confidence = 0.0
        else:
            answer = self._generate(query, context)
            # Confidence based on source scores
            confidence = sum(c.score for c in chunks) / len(chunks) if chunks else 0.0
        
        elapsed = (time.time() - start) * 1000
        
        result = RAGResult(
            query=query,
            answer=answer,
            sources=chunks,
            confidence=confidence,
            model=f"{self.llm_provider}/{self.llm_model}",
            generation_time_ms=elapsed
        )
        
        # Cache result
        if use_cache and context:
            self._set_cached(cache_key, result)
        
        return result
    
    def close(self):
        """Close connections."""
        self.retriever.close()


# Convenience function
_default_pipeline: Optional[RAGPipeline] = None

def ask(
    query: str,
    k: int = 5,
    sources: Optional[List[str]] = None
) -> str:
    """
    Quick RAG query - returns just the answer.
    
    Usage:
        from agentic_brain.rag import ask
        answer = ask("How do I deploy?")
    """
    global _default_pipeline
    
    if _default_pipeline is None:
        _default_pipeline = RAGPipeline()
    
    result = _default_pipeline.query(query, k=k, sources=sources)
    return result.answer
