# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
RAG System - Unified Interface for Retrieval-Augmented Generation
==================================================================

High-level interface for the RAG system, coordinating document indexing,
querying, evaluation, and health monitoring.

Copyright (C) 2026 Joseph Webber
License: Apache-2.0
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .retriever import Retriever
from .store import DocumentStore

try:
    from .ragas_eval import quick_evaluate
except ImportError:
    quick_evaluate = None


class RAGSystem:
    """Unified RAG System interface for CLI and programmatic access."""

    def __init__(self, **config: Any) -> None:
        """Initialize RAG system.
        
        Args:
            **config: Configuration options (chunk_size, top_k, model, etc.)
        """
        self.config_data = {
            "chunk_size": config.get("chunk_size", 512),
            "overlap": config.get("overlap", 50),
            "top_k": config.get("top_k", 5),
            "model": config.get("model", "gpt-4-turbo"),
            "temperature": config.get("temperature", 0.7),
            "embeddings_model": config.get("embeddings_model", "text-embedding-3-large"),
            "max_results": config.get("max_results", 100),
        }
        
        try:
            self.store = DocumentStore()
            self.retriever = Retriever()
        except Exception as e:
            # Handle initialization errors gracefully
            self.store = None
            self.retriever = None
            self._init_error = str(e)

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a RAG query.
        
        Args:
            question: The question to ask
            top_k: Number of results to return (default: config top_k)
            filters: Optional filters for document selection
            
        Returns:
            Dictionary with answer, sources, and relevance score
            
        Raises:
            Exception: If system not initialized
        """
        if self.retriever is None:
            raise Exception("RAG system not initialized")
        
        if top_k is None:
            top_k = self.config_data["top_k"]
        
        if filters is None:
            filters = {}
        
        try:
            # Retrieve relevant documents
            results = self.retriever.retrieve(
                query=question,
                top_k=top_k,
                filters=filters,
            )
            
            # Extract sources and calculate score
            sources = [r.get("source", "Unknown") for r in results]
            scores = [r.get("score", 0.0) for r in results]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            
            # Generate answer using LLM
            # This is simplified - in production would call actual LLM
            answer = self._generate_answer(question, results)
            
            return {
                "answer": answer,
                "sources": sources,
                "relevance_score": avg_score,
            }
        except Exception as e:
            raise Exception(f"Query failed: {str(e)}")

    def index(
        self,
        path: str,
        recursive: bool = True,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Index documents from a path.
        
        Args:
            path: Path to documents directory or file
            recursive: Whether to index subdirectories
            chunk_size: Size of chunks (default: config chunk_size)
            overlap: Overlap between chunks (default: config overlap)
            
        Returns:
            Dictionary with indexing statistics
            
        Raises:
            Exception: If path doesn't exist or indexing fails
        """
        if self.store is None:
            raise Exception("RAG system not initialized")
        
        path_obj = Path(path)
        if not path_obj.exists():
            raise Exception(f"Path does not exist: {path}")
        
        if chunk_size is None:
            chunk_size = self.config_data["chunk_size"]
        if overlap is None:
            overlap = self.config_data["overlap"]
        
        try:
            # Load documents
            documents = self._load_documents(path_obj, recursive)
            
            # Chunk documents
            chunks = self._chunk_documents(documents, chunk_size, overlap)
            
            # Store in vector database
            self.store.store_chunks(chunks)
            
            return {
                "count": len(documents),
                "chunks": len(chunks),
            }
        except Exception as e:
            raise Exception(f"Indexing failed: {str(e)}")

    def evaluate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate RAG results.
        
        Args:
            results: List of result dictionaries with expected and actual answers
            
        Returns:
            Dictionary with evaluation metrics
            
        Raises:
            Exception: If evaluation fails
        """
        try:
            metrics = {
                "total_results": len(results),
                "avg_relevance": 0.0,
                "avg_score": 0.0,
            }
            
            if not results:
                return {"metrics": metrics}
            
            # Calculate average relevance score
            scores = [r.get("relevance_score", 0.0) for r in results if "relevance_score" in r]
            if scores:
                metrics["avg_relevance"] = sum(scores) / len(scores)
            
            # Use RAGAS evaluation if available
            if quick_evaluate is not None:
                try:
                    eval_results = quick_evaluate(results)
                    if hasattr(eval_results, "metrics"):
                        metrics.update(eval_results.metrics)
                except Exception:
                    # Fallback to simple metrics
                    pass
            
            return {"metrics": metrics}
        except Exception as e:
            raise Exception(f"Evaluation failed: {str(e)}")

    def health(self) -> Dict[str, Any]:
        """Check system health status.
        
        Returns:
            Dictionary with system health status
        """
        components = {}
        all_healthy = True
        
        # Check components
        try:
            # Check store
            if self.store is not None:
                store_ok = self.store.health_check()
                components["store"] = {"status": "ok" if store_ok else "down"}
                all_healthy = all_healthy and store_ok
            else:
                components["store"] = {"status": "not_initialized"}
                all_healthy = False
        except Exception as e:
            components["store"] = {"status": "down", "error": str(e)}
            all_healthy = False
        
        try:
            # Check retriever
            if self.retriever is not None:
                components["retriever"] = {"status": "ok"}
            else:
                components["retriever"] = {"status": "not_initialized"}
                all_healthy = False
        except Exception as e:
            components["retriever"] = {"status": "down", "error": str(e)}
            all_healthy = False
        
        status = "healthy" if all_healthy else "degraded"
        
        return {
            "status": status,
            "components": components,
        }

    def config(self, key: Optional[str] = None, value: Optional[str] = None) -> Any:
        """Get or set configuration.
        
        Args:
            key: Configuration key to get or set
            value: Value to set (if setting)
            
        Returns:
            Configuration value or full config dict
        """
        if key is None and value is None:
            # Return full config
            return self.config_data
        elif key is not None and value is None:
            # Get specific value
            return self.config_data.get(key)
        elif key is not None and value is not None:
            # Set value
            # Type conversion for known types
            if key == "chunk_size" or key == "top_k" or key == "max_results":
                self.config_data[key] = int(value)
            elif key == "temperature":
                self.config_data[key] = float(value)
            elif key == "overlap":
                self.config_data[key] = int(value)
            else:
                self.config_data[key] = value
            return self.config_data[key]
        return None

    def _load_documents(self, path: Path, recursive: bool) -> List[Dict[str, Any]]:
        """Load documents from path.
        
        Args:
            path: Path to load documents from
            recursive: Whether to search subdirectories
            
        Returns:
            List of document dictionaries
        """
        documents = []
        
        if path.is_file():
            # Single file
            documents.append({
                "source": str(path),
                "content": path.read_text(),
            })
        else:
            # Directory
            pattern = "**/*" if recursive else "*"
            for file_path in path.glob(pattern):
                if file_path.is_file() and file_path.suffix in [
                    ".txt", ".md", ".pdf", ".docx", ".json"
                ]:
                    try:
                        documents.append({
                            "source": str(file_path),
                            "content": file_path.read_text(),
                        })
                    except Exception:
                        # Skip files that can't be read
                        pass
        
        return documents

    def _chunk_documents(
        self,
        documents: List[Dict[str, Any]],
        chunk_size: int,
        overlap: int,
    ) -> List[Dict[str, Any]]:
        """Split documents into chunks.
        
        Args:
            documents: List of documents
            chunk_size: Size of chunks
            overlap: Overlap between chunks
            
        Returns:
            List of document chunks
        """
        chunks = []
        
        for doc in documents:
            content = doc.get("content", "")
            source = doc.get("source", "")
            
            # Simple chunking by token count (word approximation)
            words = content.split()
            chunk_words = chunk_size
            overlap_words = overlap
            
            for i in range(0, len(words), chunk_words - overlap_words):
                chunk_text = " ".join(words[i : i + chunk_words])
                if chunk_text.strip():
                    chunks.append({
                        "source": source,
                        "content": chunk_text,
                        "chunk_index": len(chunks),
                    })
        
        return chunks

    def _generate_answer(
        self,
        question: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """Generate answer from retrieved results.
        
        Args:
            question: Original question
            results: Retrieved documents
            
        Returns:
            Generated answer
        """
        if not results:
            return "No information found."
        
        # Combine results into context
        context = "\n".join([r.get("content", "") for r in results[:3]])
        
        # Simple answer generation (in production would use LLM)
        if question.lower().startswith("what"):
            return f"Based on the retrieved documents, the answer relates to: {context[:200]}..."
        elif question.lower().startswith("how"):
            return f"Here's how it works: {context[:200]}..."
        else:
            return f"Regarding your question: {context[:200]}..."
