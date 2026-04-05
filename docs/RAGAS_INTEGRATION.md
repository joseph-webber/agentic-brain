# RAGAS Integration Guide

**RAGAS** (Retrieval-Augmented Generation Assessment) is the 2026 industry standard for evaluating RAG systems. This guide covers integration with Agentic Brain's GraphRAG implementation.

## Overview

RAGAS evaluates RAG quality using 4 core metrics plus advanced checks:

| Metric | Description | What it Measures |
|--------|-------------|------------------|
| **Faithfulness** | Are claims in the answer grounded in context? | Prevents hallucination |
| **Answer Relevancy** | Does the answer address the question? | Response quality |
| **Context Precision** | Are relevant contexts ranked higher? | Retrieval ranking |
| **Context Recall** | Does context cover required information? | Retrieval completeness |

### Advanced Evaluation Suite

| Metric | Description |
|--------|-------------|
| **Aspect Critique** | Harmfulness, coherence, and conciseness checks |
| **Answer Correctness** | Compare answer against ground truth |
| **Context Entity Recall** | Verify entities from ground truth appear in context |
| **Noise Robustness** | Stress-test with typos, paraphrases, and adversarial queries |
| **Multi-turn Evaluation** | Measure conversation quality over turns |

### Quality Bar

- **0.8+** = Production ready ✅
- **0.7-0.8** = Staging/Testing
- **0.6-0.7** = Development (needs improvement)
- **<0.6** = Failing ❌

## Quick Start

```python
from agentic_brain.rag.ragas_eval import (
    AdvancedRAGASEvaluator,
    RAGASEvaluator,
    RAGASDataset,
    quick_evaluate,
)

# Quick single-sample evaluation
result = quick_evaluate(
    question="How do I deploy to production?",
    answer="Run kubectl apply -f deployment.yaml to deploy your application.",
    contexts=[
        "Deployment Guide: Use kubectl apply -f deployment.yaml to deploy.",
        "Configuration: Set replicas in deployment.yaml for scaling."
    ],
    ground_truth="Use kubectl apply -f deployment.yaml"
)

print(f"Overall Score: {result.overall_score:.2f}")
print(f"Faithfulness: {result.faithfulness.score:.2f}")
print(f"Answer Relevancy: {result.answer_relevancy.score:.2f}")
print(f"Context Precision: {result.context_precision.score:.2f}")
print(f"Context Recall: {result.context_recall.score:.2f}")
```

```python
# Advanced evaluation
advanced = AdvancedRAGASEvaluator()
report = advanced.full_evaluation(sample, include_noise=True)

print(report["answer_quality"]["correctness"]["score"])
print(report["entity_recall"]["score"])
print(report["noise_robustness"]["score"])
```

## Full Evaluation Workflow

### 1. Create Evaluation Dataset

```python
from agentic_brain.rag.ragas_eval import RAGASDataset, RAGASSample

dataset = RAGASDataset()

# Add samples with ground truth
dataset.add_sample(
    question="How do I configure logging?",
    answer="Set LOG_LEVEL=DEBUG in your environment variables.",
    contexts=[
        "Logging: Configure LOG_LEVEL environment variable...",
        "Debug mode: Set LOG_LEVEL=DEBUG for verbose logging."
    ],
    ground_truth="Set LOG_LEVEL environment variable to configure logging level."
)

dataset.add_sample(
    question="What database does the system use?",
    answer="The system uses Neo4j graph database for knowledge storage.",
    contexts=[
        "Architecture: Neo4j graph database stores entities and relationships.",
        "Storage: Vector embeddings stored in Neo4j with HNSW index."
    ],
    ground_truth="Neo4j graph database"
)

# Save dataset for reuse
dataset.save(Path("evaluation/test_dataset.json"))
```

### 2. Run Evaluation

```python
from agentic_brain.rag.ragas_eval import RAGASEvaluator

evaluator = RAGASEvaluator()
results = evaluator.evaluate(dataset)

print(results)
# 📊 RAGAS Evaluation Results (2 samples) ✅ PASS
# Overall Score: 0.850 (PRODUCTION)
# Faithfulness: 0.900
# Answer Relevancy: 0.820
# Context Precision: 0.850
# Context Recall: 0.830

# Check quality bar
if results.meets_quality_bar:
    print("✅ Production ready!")
else:
    print(f"❌ Needs improvement: {results.overall_score:.2f}")
```

### 3. Evaluate GraphRAG Pipeline

```python
from agentic_brain.rag import GraphRAG
from agentic_brain.rag.ragas_eval import create_graphrag_evaluator

# Initialize GraphRAG
graphrag = GraphRAG(neo4j_uri="bolt://localhost:7687")

# Create evaluator with GraphRAG integration
evaluator, rag_func = create_graphrag_evaluator(graphrag)

# Evaluate pipeline directly
results = evaluator.evaluate_rag_pipeline(
    rag_func,
    questions=[
        "How do I deploy to production?",
        "What are the security requirements?",
        "How do I configure the database?",
    ],
    ground_truths=[
        "Use kubectl apply -f deployment.yaml",
        "Enable TLS and set API_KEY environment variable",
        "Set NEO4J_URI and NEO4J_PASSWORD environment variables",
    ]
)

print(f"GraphRAG Quality: {results.overall_score:.3f}")
```

## A/B Testing RAG Configurations

```python
# Compare two retrieval strategies
results_comparison = evaluator.compare(
    dataset_strategy_a,
    dataset_strategy_b,
    names=("Vector Search", "Hybrid Search")
)

print(f"Winner: {results_comparison['winner']}")
print(f"Improvement in Context Precision: {results_comparison['improvements']['context_precision']:.3f}")
```

## Benchmarking

```python
# Run multiple iterations for statistical significance
benchmark = evaluator.benchmark(
    rag_func,
    dataset,
    n_iterations=5
)

print(f"Mean Overall: {benchmark['metrics']['overall']['mean']:.3f}")
print(f"Std Dev: {benchmark['metrics']['overall']['std']:.3f}")
print(f"Production Ready: {benchmark['meets_quality_bar']}")
```

## Custom LLM Judge

For production accuracy, replace `SimpleLLMJudge` with an LLM-based judge:

```python
from agentic_brain.rag.ragas_eval import RAGASEvaluator, LLMJudge

class ClaudeLLMJudge:
    """LLM judge using Claude for faithful evaluation."""
    
    def __init__(self, client):
        self.client = client
    
    def judge_faithfulness(self, answer: str, contexts: list[str]) -> tuple[float, list[dict]]:
        prompt = f"""
        Evaluate if each claim in the answer is supported by the contexts.
        
        Answer: {answer}
        
        Contexts:
        {chr(10).join(f'{i+1}. {c}' for i, c in enumerate(contexts))}
        
        For each claim, respond with:
        - claim: the claim text
        - supported: true/false
        - evidence: which context supports it (if any)
        
        Return JSON array.
        """
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": prompt}]
        )
        
        verifications = json.loads(response.content[0].text)
        supported = sum(1 for v in verifications if v["supported"])
        score = supported / len(verifications) if verifications else 1.0
        
        return score, verifications
    
    def generate_synthetic_questions(self, answer: str, n: int = 3) -> list[str]:
        # Use LLM to generate questions that would lead to this answer
        ...
    
    def extract_statements(self, text: str) -> list[str]:
        # Use LLM to extract factual statements
        ...

# Use custom judge
claude_judge = ClaudeLLMJudge(anthropic_client)
evaluator = RAGASEvaluator(judge=claude_judge)
```

## Custom Embeddings

```python
from agentic_brain.rag import get_embedding

# Use production embeddings
evaluator = RAGASEvaluator(
    embed_func=lambda text: get_embedding(text)  # Uses MLX/CUDA acceleration
)
```

## Metric Details

### Faithfulness

Measures whether claims in the generated answer are supported by retrieved context.

```python
# Low faithfulness = hallucination risk
if result.faithfulness.score < 0.7:
    print("⚠️ Warning: Answer may contain unsupported claims")
    for v in result.faithfulness.details["verifications"]:
        if not v["supported"]:
            print(f"  Unsupported: {v['claim']}")
```

### Answer Relevancy

Measures how well the answer addresses the original question.

```python
# Check if answer is on-topic
if result.answer_relevancy.score < 0.7:
    print("⚠️ Answer may not directly address the question")
```

### Context Precision

Measures if the most relevant contexts are ranked at the top.

```python
# Optimize retrieval ranking
if result.context_precision.score < 0.7:
    print("⚠️ Consider improving reranking strategy")
    print(f"  Relevant contexts: {result.context_precision.details['relevant_contexts']}")
```

### Context Recall

Measures if retrieved context covers the information needed.

```python
# Check coverage
if result.context_recall.score < 0.7:
    print("⚠️ Context may be missing key information")
    for s in result.context_recall.details["statement_coverage"]:
        if not s["covered"]:
            print(f"  Missing: {s['statement']}")
```

### Advanced Metrics

```python
from agentic_brain.rag.ragas_eval import (
    AdvancedRAGASEvaluator,
    AspectType,
    ConversationSample,
    ConversationTurn,
)

advanced = AdvancedRAGASEvaluator()

aspect_results = advanced.evaluate_with_aspects(
    sample,
    aspects=[AspectType.HARMFULNESS, AspectType.COHERENCE, AspectType.CONCISENESS],
)

conversation = ConversationSample(
    conversation_id="demo",
    turns=[
        ConversationTurn(
            question="What is Neo4j?",
            answer="Neo4j is a graph database.",
            contexts=["Neo4j stores relationships."],
            ground_truth="Neo4j is a graph database.",
            turn_number=1,
        )
    ],
)

multi_turn = advanced.evaluate_conversation(conversation)
```

## CI/CD Integration

```python
# pytest test for RAG quality
import pytest
from agentic_brain.rag.ragas_eval import RAGASEvaluator, RAGASDataset

def test_rag_quality_bar():
    """Ensure RAG meets production quality threshold."""
    dataset = RAGASDataset()
    dataset.add_samples_from_file(Path("tests/data/eval_dataset.json"))
    
    evaluator = RAGASEvaluator()
    results = evaluator.evaluate(dataset)
    
    assert results.meets_quality_bar, (
        f"RAG quality below threshold: {results.overall_score:.3f} < 0.8\n"
        f"Faithfulness: {results.avg_faithfulness:.3f}\n"
        f"Answer Relevancy: {results.avg_answer_relevancy:.3f}\n"
        f"Context Precision: {results.avg_context_precision:.3f}\n"
        f"Context Recall: {results.avg_context_recall:.3f}"
    )

def test_no_faithfulness_regression():
    """Ensure faithfulness doesn't regress."""
    # Load baseline
    with open("tests/data/baseline_metrics.json") as f:
        baseline = json.load(f)
    
    evaluator = RAGASEvaluator()
    results = evaluator.evaluate(dataset)
    
    assert results.avg_faithfulness >= baseline["faithfulness"] - 0.05, (
        f"Faithfulness regression: {results.avg_faithfulness:.3f} < {baseline['faithfulness']:.3f}"
    )
```

## Saving and Loading Results

```python
from pathlib import Path

# Save results
evaluator.save_results(Path("evaluation/results_2026-01-15.json"))

# Load dataset for reproducibility
dataset = RAGASDataset()
dataset.add_samples_from_file(Path("evaluation/test_dataset.json"))
```

## Best Practices

1. **Ground Truth Quality**: Ensure ground truth answers are accurate and complete
2. **Representative Samples**: Include diverse question types (factual, analytical, procedural)
3. **Regular Evaluation**: Run RAGAS in CI/CD pipeline on every PR
4. **Track Regressions**: Compare against baseline metrics
5. **Production Monitoring**: Sample live queries for ongoing evaluation

## Troubleshooting

### Low Faithfulness
- Check if contexts are being retrieved correctly
- Verify LLM isn't hallucinating beyond context
- Consider stricter context filtering

### Low Answer Relevancy
- Improve query understanding
- Check if answer generation follows instructions
- Verify context contains relevant information

### Low Context Precision
- Improve retrieval ranking (reranking, MMR)
- Check embedding quality
- Consider hybrid search (vector + keyword)

### Low Context Recall
- Increase number of retrieved chunks
- Improve chunking strategy
- Check if relevant documents are indexed

## References

- [RAGAS Paper (2023)](https://arxiv.org/abs/2309.15217)
- [RAGAS Documentation](https://docs.ragas.io/)
- [Agentic Brain GraphRAG Guide](./GRAPHRAG.md)
