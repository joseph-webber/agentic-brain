"""RAGEvaluator: orchestrates evaluation using datasets and metrics."""
from typing import List, Optional
from .metrics import (
    faithfulness_score,
    relevancy_score,
    context_precision,
    context_recall,
    answer_similarity,
)
from .datasets import Dataset
from .report import EvaluationReport


class RAGEvaluator:
    """Evaluate RAG outputs against a Dataset.

    The evaluator accepts either:
      - retrievals: List[List[str]] of retrieved context ids per example
      - retrieved_scores: List[List[float]] per doc relevancy scores
      - generated_answers: List[str] generated answers per example

    For each example it computes: answer_similarity, faithfulness, context_precision, context_recall, relevancy
    """

    def evaluate(
        self,
        dataset: Dataset,
        retrievals: Optional[List[List[str]]] = None,
        retrieved_scores: Optional[List[List[float]]] = None,
        generated_answers: Optional[List[str]] = None,
    ) -> EvaluationReport:
        report = EvaluationReport()
        for idx, ex in enumerate(dataset):
            retrieved = retrievals[idx] if retrievals and idx < len(retrievals) else []
            scores = retrieved_scores[idx] if retrieved_scores and idx < len(retrieved_scores) else []
            gen = generated_answers[idx] if generated_answers and idx < len(generated_answers) else ""

            ans_sim = answer_similarity(gen, ex.gold_answer)
            prec = context_precision(retrieved, ex.gold_context_ids)
            rec = context_recall(retrieved, ex.gold_context_ids)
            rel = relevancy_score(scores)
            faith = faithfulness_score(gen, retrieved, ex.gold_answer if ex.gold_answer else None)

            item_result = {
                "id": ex.id,
                "answer_similarity": ans_sim,
                "context_precision": prec,
                "context_recall": rec,
                "relevancy": rel,
                "faithfulness": faith,
            }
            report.add_item(item_result)
        return report
