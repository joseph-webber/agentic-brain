RAG Evaluation Framework

This document describes the RAG evaluation framework added to agentic-brain.

Components:
- src/agentic_brain/evaluation/metrics.py: metric implementations (faithfulness, relevancy, context precision/recall, answer similarity)
- src/agentic_brain/evaluation/datasets.py: Dataset and Example helpers for test data
- src/agentic_brain/evaluation/evaluator.py: RAGEvaluator orchestrator
- src/agentic_brain/evaluation/report.py: EvaluationReport for summaries and markdown export
- src/agentic_brain/evaluation/comparison.py: A/B testing utilities using paired t-tests

Usage:

Create a Dataset from a list of examples, run RAGEvaluator.evaluate with retrievals, retrieved_scores and generated_answers and inspect the EvaluationReport.
