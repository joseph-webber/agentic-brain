# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
RAG evaluation and testing framework.

Provides tools to measure RAG system quality:
- Metrics: Precision, Recall, NDCG, MRR, MAP
- A/B testing for comparing retrieval strategies
- Evaluation datasets management
- Continuous monitoring

Usage:
    from agentic_brain.rag.evaluation import RAGEvaluator, EvalDataset
    
    # Create evaluation dataset
    dataset = EvalDataset()
    dataset.add_query("How do I deploy?", ["deploy_guide.md", "devops_docs.md"])
    
    # Evaluate RAG system
    evaluator = RAGEvaluator()
    results = evaluator.evaluate(rag_pipeline, dataset)
    print(f"Precision@5: {results.precision_at_k(5)}")
    print(f"NDCG: {results.ndcg}")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Callable
import json
from pathlib import Path
from datetime import datetime
import statistics
import math

from .retriever import RetrievedChunk


@dataclass
class EvalQuery:
    """A query for evaluation with relevant documents."""
    query: str
    relevant_docs: List[str]  # Document IDs or sources that are relevant
    retrieval_level: str = "retrieval"  # retrieval, generation, ranking
    difficulty: str = "medium"  # easy, medium, hard
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalMetrics:
    """Evaluation metrics for a single query."""
    query: str
    precision_scores: Dict[int, float]  # precision@1, @3, @5, @10
    recall_scores: Dict[int, float]
    mrr: float  # Mean Reciprocal Rank
    ndcg: float  # Normalized Discounted Cumulative Gain
    map_score: float  # Mean Average Precision
    
    def __repr__(self) -> str:
        lines = [
            f"Query: {self.query[:50]}...",
            f"P@5: {self.precision_scores.get(5, 0):.3f}",
            f"R@5: {self.recall_scores.get(5, 0):.3f}",
            f"MRR: {self.mrr:.3f}",
            f"NDCG: {self.ndcg:.3f}",
            f"MAP: {self.map_score:.3f}"
        ]
        return "\n".join(lines)


@dataclass
class EvalResults:
    """Aggregated evaluation results."""
    query_metrics: List[EvalMetrics]
    avg_precision_at_k: Dict[int, float]
    avg_recall_at_k: Dict[int, float]
    avg_mrr: float
    avg_ndcg: float
    avg_map: float
    num_queries: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def precision_at_k(self, k: int) -> float:
        """Get average precision@k."""
        return self.avg_precision_at_k.get(k, 0.0)
    
    def recall_at_k(self, k: int) -> float:
        """Get average recall@k."""
        return self.avg_recall_at_k.get(k, 0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "num_queries": self.num_queries,
            "timestamp": self.timestamp,
            "precision_at_k": self.avg_precision_at_k,
            "recall_at_k": self.avg_recall_at_k,
            "mrr": self.avg_mrr,
            "ndcg": self.avg_ndcg,
            "map": self.avg_map,
        }
    
    def __repr__(self) -> str:
        lines = [
            f"📊 RAG Evaluation Results ({self.num_queries} queries)",
            f"Precision@5: {self.precision_at_k(5):.3f}",
            f"Recall@5: {self.recall_at_k(5):.3f}",
            f"MRR: {self.avg_mrr:.3f}",
            f"NDCG: {self.avg_ndcg:.3f}",
            f"MAP: {self.avg_map:.3f}"
        ]
        return "\n".join(lines)


class EvalDataset:
    """Dataset for RAG evaluation."""
    
    def __init__(self):
        self.queries: List[EvalQuery] = []
    
    def add_query(
        self,
        query: str,
        relevant_docs: List[str],
        difficulty: str = "medium",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add query with relevant documents."""
        self.queries.append(EvalQuery(
            query=query,
            relevant_docs=relevant_docs,
            difficulty=difficulty,
            metadata=metadata or {}
        ))
    
    def add_queries_from_file(self, path: Path) -> None:
        """Load queries from JSON file."""
        with open(path) as f:
            data = json.load(f)
        
        for item in data:
            self.add_query(
                query=item["query"],
                relevant_docs=item["relevant_docs"],
                difficulty=item.get("difficulty", "medium"),
                metadata=item.get("metadata", {})
            )
    
    def save(self, path: Path) -> None:
        """Save dataset to JSON."""
        data = [
            {
                "query": q.query,
                "relevant_docs": q.relevant_docs,
                "difficulty": q.difficulty,
                "metadata": q.metadata
            }
            for q in self.queries
        ]
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def __len__(self) -> int:
        return len(self.queries)


class RAGEvaluator:
    """Evaluate RAG retrieval quality."""
    
    def __init__(self):
        self.results_history: List[EvalResults] = []
    
    def evaluate(
        self,
        retriever_func: Callable,
        dataset: EvalDataset,
        k_values: Optional[List[int]] = None
    ) -> EvalResults:
        """
        Evaluate retrieval function on dataset.
        
        Args:
            retriever_func: Function that takes query and returns List[RetrievedChunk]
            dataset: EvalDataset with queries and relevant docs
            k_values: K values for precision/recall (default: [1, 3, 5, 10])
        
        Returns:
            EvalResults with aggregated metrics
        """
        k_values = k_values or [1, 3, 5, 10]
        query_metrics = []
        
        for eval_query in dataset.queries:
            # Get retrieval results
            results = retriever_func(eval_query.query)
            
            # Calculate metrics
            metrics = self._compute_metrics(
                eval_query.query,
                eval_query.relevant_docs,
                results,
                k_values
            )
            query_metrics.append(metrics)
        
        # Aggregate results
        results = self._aggregate_metrics(query_metrics, k_values)
        self.results_history.append(results)
        
        return results
    
    def _compute_metrics(
        self,
        query: str,
        relevant_docs: List[str],
        retrieved: List[RetrievedChunk],
        k_values: List[int]
    ) -> EvalMetrics:
        """Compute metrics for single query."""
        # Extract sources from retrieved chunks
        retrieved_docs = [chunk.source for chunk in retrieved]
        
        # Convert relevant_docs to set for faster lookup
        relevant_set = set(relevant_docs)
        num_relevant = len(relevant_set)
        
        # Precision and Recall at K
        precision_scores = {}
        recall_scores = {}
        
        for k in k_values:
            retrieved_k = retrieved_docs[:k]
            relevant_retrieved = sum(1 for doc in retrieved_k if doc in relevant_set)
            
            # Precision@k: relevant / retrieved
            precision_scores[k] = (
                relevant_retrieved / k if k > 0 else 0.0
            )
            
            # Recall@k: relevant / total_relevant
            recall_scores[k] = (
                relevant_retrieved / num_relevant if num_relevant > 0 else 0.0
            )
        
        # Mean Reciprocal Rank (MRR)
        mrr = self._compute_mrr(retrieved_docs, relevant_set)
        
        # Normalized Discounted Cumulative Gain (NDCG)
        ndcg = self._compute_ndcg(retrieved_docs, relevant_set)
        
        # Mean Average Precision (MAP)
        map_score = self._compute_map(retrieved_docs, relevant_set)
        
        return EvalMetrics(
            query=query,
            precision_scores=precision_scores,
            recall_scores=recall_scores,
            mrr=mrr,
            ndcg=ndcg,
            map_score=map_score
        )
    
    def _compute_mrr(self, retrieved: List[str], relevant: set) -> float:
        """Mean Reciprocal Rank - position of first relevant result."""
        for i, doc in enumerate(retrieved):
            if doc in relevant:
                return 1.0 / (i + 1)
        return 0.0
    
    def _compute_ndcg(self, retrieved: List[str], relevant: set, k: int = 10) -> float:
        """Normalized Discounted Cumulative Gain."""
        # DCG: sum(relevance / log2(position + 1))
        dcg = 0.0
        for i in range(min(k, len(retrieved))):
            if retrieved[i] in relevant:
                if i > 0:
                    dcg += 1.0 / math.log2(i + 1)
                else:
                    dcg += 1.0
        
        # IDCG: best possible DCG (all relevant docs first)
        idcg = 0.0
        for i in range(min(k, len(relevant))):
            if i > 0:
                idcg += 1.0 / math.log2(i + 1)
            else:
                idcg += 1.0
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def _compute_map(self, retrieved: List[str], relevant: set, k: int = 10) -> float:
        """Mean Average Precision."""
        precision_sum = 0.0
        num_relevant_found = 0
        
        for i in range(min(k, len(retrieved))):
            if retrieved[i] in relevant:
                num_relevant_found += 1
                # Precision at this position
                precision_sum += num_relevant_found / (i + 1)
        
        return (
            precision_sum / len(relevant) if len(relevant) > 0 else 0.0
        )
    
    def _aggregate_metrics(
        self,
        query_metrics: List[EvalMetrics],
        k_values: List[int]
    ) -> EvalResults:
        """Aggregate metrics across queries."""
        # Average precision at K
        avg_precision_at_k = {}
        for k in k_values:
            scores = [m.precision_scores.get(k, 0.0) for m in query_metrics]
            avg_precision_at_k[k] = statistics.mean(scores) if scores else 0.0
        
        # Average recall at K
        avg_recall_at_k = {}
        for k in k_values:
            scores = [m.recall_scores.get(k, 0.0) for m in query_metrics]
            avg_recall_at_k[k] = statistics.mean(scores) if scores else 0.0
        
        # Average MRR, NDCG, MAP
        avg_mrr = statistics.mean([m.mrr for m in query_metrics]) if query_metrics else 0.0
        avg_ndcg = statistics.mean([m.ndcg for m in query_metrics]) if query_metrics else 0.0
        avg_map = statistics.mean([m.map_score for m in query_metrics]) if query_metrics else 0.0
        
        return EvalResults(
            query_metrics=query_metrics,
            avg_precision_at_k=avg_precision_at_k,
            avg_recall_at_k=avg_recall_at_k,
            avg_mrr=avg_mrr,
            avg_ndcg=avg_ndcg,
            avg_map=avg_map,
            num_queries=len(query_metrics)
        )
    
    def ab_test(
        self,
        retriever_a: Callable,
        retriever_b: Callable,
        dataset: EvalDataset,
        k_values: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        A/B test two retrieval strategies.
        
        Returns:
            Dictionary with results for both strategies and statistical comparison
        """
        results_a = self.evaluate(retriever_a, dataset, k_values)
        results_b = self.evaluate(retriever_b, dataset, k_values)
        
        # Compare metrics
        comparison = {
            "strategy_a": results_a.to_dict(),
            "strategy_b": results_b.to_dict(),
            "improvements": {
                "ndcg": results_b.avg_ndcg - results_a.avg_ndcg,
                "mrr": results_b.avg_mrr - results_a.avg_mrr,
                "map": results_b.avg_map - results_a.avg_map,
                "precision_at_5": results_b.precision_at_k(5) - results_a.precision_at_k(5),
                "recall_at_5": results_b.recall_at_k(5) - results_a.recall_at_k(5),
            },
            "winner": "B" if results_b.avg_ndcg > results_a.avg_ndcg else "A"
        }
        
        return comparison
    
    def save_results(self, path: Path) -> None:
        """Save evaluation results to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = [r.to_dict() for r in self.results_history]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
