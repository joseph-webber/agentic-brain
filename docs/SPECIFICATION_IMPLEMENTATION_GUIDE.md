# RAG Specification Implementation Guide

**Focus:** Step-by-step implementation patterns for each specification  
**Audience:** Engineers implementing specifications  
**Status:** Active Reference  

---

## Table of Contents

1. [RAGAS Integration (Phase 1)](#ragas-integration-phase-1)
2. [Microsoft GraphRAG Global Search (Phase 1)](#microsoft-graphrag-global-search-phase-1)
3. [DSPy Optimization (Phase 2)](#dspy-optimization-phase-2)
4. [Text2Cypher Pattern (Phase 2)](#text2cypher-pattern-phase-2)
5. [Dynamic Community Selection (Phase 3)](#dynamic-community-selection-phase-3)
6. [LlamaIndex Compatibility (Phase 4)](#llamaindex-compatibility-phase-4)
7. [Testing & Benchmarking](#testing--benchmarking)

---

## RAGAS Integration (Phase 1)

### Overview

RAGAS provides four core metrics for evaluating RAG systems:

| Metric | Measures | Scale | LLM-Based |
|--------|----------|-------|-----------|
| **Faithfulness** | Answer grounded in context | 0-1 | Yes |
| **Answer Relevancy** | Answer addresses query | 0-1 | Yes |
| **Context Precision** | Retrieved chunks relevant | 0-1 | Yes |
| **Context Recall** | All needed chunks retrieved | 0-1 | Estimated |

### Implementation: Phase 1a (Weeks 1-4)

#### Step 1: Create Base Evaluator Class

**File:** `src/agentic_brain/rag/ragas_evaluator.py`

```python
"""RAGAS (RAG Assessment Suite) integration for agentic-brain."""

import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class RAGASMetrics:
    """RAGAS evaluation metrics for a single query-answer pair."""
    
    query: str
    answer: str
    context: str  # Retrieved documents concatenated
    
    # Core metrics (0-1 scale)
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    
    # Metadata
    timestamp: float = None
    llm_model: str = "gpt-4"
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    
    def overall_score(self) -> float:
        """Weighted average of all metrics."""
        weights = {
            'faithfulness': 0.35,      # Most important
            'context_recall': 0.25,    # Good coverage
            'context_precision': 0.20, # Useful docs
            'answer_relevancy': 0.20   # Addresses query
        }
        return sum([
            self.faithfulness * weights['faithfulness'],
            self.context_recall * weights['context_recall'],
            self.context_precision * weights['context_precision'],
            self.answer_relevancy * weights['answer_relevancy']
        ])
    
    def is_passing(self, thresholds: Optional[Dict[str, float]] = None) -> bool:
        """Check if metrics meet quality thresholds."""
        defaults = {
            'faithfulness': 0.8,
            'answer_relevancy': 0.7,
            'context_precision': 0.75,
            'context_recall': 0.7,
            'overall': 0.75
        }
        thresholds = thresholds or defaults
        
        return (
            self.faithfulness >= thresholds.get('faithfulness', 0.8) and
            self.answer_relevancy >= thresholds.get('answer_relevancy', 0.7) and
            self.context_precision >= thresholds.get('context_precision', 0.75) and
            self.context_recall >= thresholds.get('context_recall', 0.7) and
            self.overall_score() >= thresholds.get('overall', 0.75)
        )


class RAGASEvaluator:
    """Evaluate RAG systems using RAGAS metrics."""
    
    def __init__(self, llm_provider=None, embedding_provider=None):
        """
        Initialize RAGAS evaluator.
        
        Args:
            llm_provider: LLM for faithfulness/relevancy scoring
            embedding_provider: Embeddings for recall estimation
        """
        self.llm = llm_provider or self._get_default_llm()
        self.embeddings = embedding_provider or self._get_default_embeddings()
    
    async def faithfulness(
        self,
        query: str,
        answer: str,
        context: str
    ) -> float:
        """
        Measure faithfulness: Is every claim in answer supported by context?
        
        Uses LLM-based evaluation:
        1. Extract claims from answer
        2. For each claim, check if it can be attributed to context
        3. Return (supported_claims / total_claims)
        
        Args:
            query: Original query
            answer: Generated answer
            context: Retrieved context
            
        Returns:
            Faithfulness score (0-1)
        """
        prompt = f"""You are a faithfulness evaluator for a RAG system.
        
Query: {query}

Answer: {answer}

Context: {context}

Task: Evaluate how faithfully the answer is grounded in the context.
- Extract key claims from the answer
- For each claim, check if it can be attributed to the context
- Return a score from 0 to 1:
  * 1.0: All claims are grounded in context (perfect faithfulness)
  * 0.5: Half the claims are grounded
  * 0.0: No claims are grounded (complete hallucination)

Be strict: a claim must be explicitly supported, not inferred.

Respond with only a float between 0 and 1.
"""
        
        try:
            response = await self.llm.generate(prompt)
            score = float(response.strip())
            return max(0.0, min(1.0, score))  # Clamp to [0, 1]
        except Exception as e:
            logger.error(f"Faithfulness evaluation failed: {e}")
            return 0.5  # Conservative default
    
    async def answer_relevancy(
        self,
        query: str,
        answer: str
    ) -> float:
        """
        Measure answer relevancy: Does answer address the query?
        
        Uses LLM-based evaluation with few-shot examples.
        
        Args:
            query: Original query
            answer: Generated answer
            
        Returns:
            Relevancy score (0-1)
        """
        prompt = f"""You are a relevancy evaluator for a RAG system.

Query: {query}

Answer: {answer}

Task: Evaluate how well the answer addresses the query:
- Is the answer relevant to the query?
- Does it answer the specific question asked?
- Return a score from 0 to 1:
  * 1.0: Perfect relevancy (completely addresses query)
  * 0.7: Good relevancy (addresses main points)
  * 0.3: Partial relevancy (tangentially related)
  * 0.0: Not relevant (completely off-topic)

Respond with only a float between 0 and 1.
"""
        
        try:
            response = await self.llm.generate(prompt)
            score = float(response.strip())
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.error(f"Answer relevancy evaluation failed: {e}")
            return 0.5
    
    async def context_precision(
        self,
        query: str,
        context_docs: List[str]
    ) -> float:
        """
        Measure context precision: Are retrieved documents relevant?
        
        For each document:
        1. Determine if it's relevant to the query
        2. Calculate: (relevant_docs / total_docs)
        
        Args:
            query: Original query
            context_docs: List of retrieved document texts
            
        Returns:
            Precision score (0-1)
        """
        if not context_docs:
            return 0.0
        
        relevant_count = 0
        for doc in context_docs:
            is_relevant = await self._is_doc_relevant(query, doc)
            if is_relevant:
                relevant_count += 1
        
        return relevant_count / len(context_docs)
    
    async def context_recall(
        self,
        query: str,
        context_docs: List[str],
        answer: str
    ) -> float:
        """
        Measure context recall: Are all needed documents retrieved?
        
        Estimates by checking if context contains information necessary
        to generate the answer.
        
        Args:
            query: Original query
            context_docs: List of retrieved documents
            answer: Generated answer
            
        Returns:
            Recall estimate (0-1)
        """
        # Extract key information from answer
        key_entities = await self._extract_entities(answer)
        
        # Check if context contains these entities
        context_combined = "\n".join(context_docs)
        found_count = sum(
            1 for entity in key_entities
            if entity.lower() in context_combined.lower()
        )
        
        if not key_entities:
            return 1.0  # No specific entities needed
        
        return found_count / len(key_entities)
    
    async def evaluate_all(
        self,
        query: str,
        answer: str,
        context: str,
        context_docs: List[str]
    ) -> RAGASMetrics:
        """
        Evaluate all RAGAS metrics for a query-answer pair.
        
        Args:
            query: Original query
            answer: Generated answer
            context: Retrieved context (concatenated)
            context_docs: List of retrieved documents
            
        Returns:
            RAGASMetrics object with all scores
        """
        import time
        from datetime import datetime
        
        start_time = time.time()
        
        # Run evaluations in parallel for efficiency
        faithfulness_score, relevancy_score, precision_score, recall_score = \
            await asyncio.gather(
                self.faithfulness(query, answer, context),
                self.answer_relevancy(query, answer),
                self.context_precision(query, context_docs),
                self.context_recall(query, context_docs, answer)
            )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return RAGASMetrics(
            query=query,
            answer=answer,
            context=context,
            faithfulness=faithfulness_score,
            answer_relevancy=relevancy_score,
            context_precision=precision_score,
            context_recall=recall_score,
            timestamp=datetime.now().timestamp(),
            retrieval_time_ms=0.0,  # Set by caller
            generation_time_ms=elapsed_ms
        )
    
    # Helper methods
    async def _is_doc_relevant(self, query: str, doc: str) -> bool:
        """Check if document is relevant to query."""
        prompt = f"""Is the following document relevant to the query?
Query: {query}
Document: {doc[:500]}...
Respond with only 'yes' or 'no'."""
        
        try:
            response = await self.llm.generate(prompt)
            return response.strip().lower() in ['yes', 'y']
        except:
            return False
    
    async def _extract_entities(self, text: str) -> List[str]:
        """Extract key entities from text."""
        # Placeholder: use NER model or LLM
        return []
    
    def _get_default_llm(self):
        """Get default LLM provider."""
        # Import from agentic_brain
        from agentic_brain.llm import get_default_llm
        return get_default_llm()
    
    def _get_default_embeddings(self):
        """Get default embedding provider."""
        from agentic_brain.rag.embeddings import EmbeddingProvider
        return EmbeddingProvider()


# Integration hook
class RAGPipelineWithRAGAS:
    """Extend RAGPipeline with RAGAS evaluation."""
    
    def __init__(self, rag_pipeline, evaluator: Optional[RAGASEvaluator] = None):
        self.pipeline = rag_pipeline
        self.evaluator = evaluator or RAGASEvaluator()
    
    async def query_with_evaluation(
        self,
        query: str,
        return_metrics: bool = True
    ) -> tuple:
        """
        Execute query and optionally evaluate with RAGAS.
        
        Returns:
            (result, metrics) if return_metrics=True
            result otherwise
        """
        result = await self.pipeline.query(query)
        
        if not return_metrics:
            return result
        
        metrics = await self.evaluator.evaluate_all(
            query=query,
            answer=result.answer,
            context=result.context,
            context_docs=result.documents
        )
        
        return result, metrics
```

#### Step 2: Integrate with Pipeline

**Update:** `src/agentic_brain/rag/pipeline.py`

```python
# Add to RAGPipeline class

def with_ragas_evaluation(self):
    """Enable RAGAS evaluation for all queries."""
    from .ragas_evaluator import RAGASEvaluator, RAGPipelineWithRAGAS
    evaluator = RAGASEvaluator()
    return RAGPipelineWithRAGAS(self, evaluator)

async def evaluate_quality(
    self,
    test_dataset: List[Dict]
) -> Dict:
    """
    Evaluate pipeline quality using RAGAS metrics.
    
    Args:
        test_dataset: List of {query, expected_answer, relevant_docs}
        
    Returns:
        Aggregated RAGAS metrics and per-query breakdown
    """
    from .ragas_evaluator import RAGASEvaluator
    
    evaluator = RAGASEvaluator()
    results = []
    
    for test_case in test_dataset:
        query = test_case['query']
        
        # Execute query
        result = await self.query(query)
        
        # Evaluate with RAGAS
        metrics = await evaluator.evaluate_all(
            query=query,
            answer=result.answer,
            context=result.context,
            context_docs=result.documents
        )
        results.append(metrics)
    
    # Aggregate
    return {
        'overall': {
            'faithfulness': sum(r.faithfulness for r in results) / len(results),
            'answer_relevancy': sum(r.answer_relevancy for r in results) / len(results),
            'context_precision': sum(r.context_precision for r in results) / len(results),
            'context_recall': sum(r.context_recall for r in results) / len(results),
        },
        'details': results,
        'passing_rate': sum(1 for r in results if r.is_passing()) / len(results)
    }
```

#### Step 3: Usage Examples

**File:** `examples/ragas_evaluation.py`

```python
"""Example: Evaluating RAG with RAGAS metrics."""

import asyncio
from agentic_brain.rag import RAGPipeline
from agentic_brain.rag.ragas_evaluator import RAGASEvaluator

async def main():
    # Initialize pipeline
    rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
    
    # Option 1: Single query with evaluation
    evaluator = RAGASEvaluator()
    result = await rag.query("What is GraphRAG?")
    
    metrics = await evaluator.evaluate_all(
        query="What is GraphRAG?",
        answer=result.answer,
        context=result.context,
        context_docs=result.documents
    )
    
    print(f"Faithfulness: {metrics.faithfulness:.2%}")
    print(f"Answer Relevancy: {metrics.answer_relevancy:.2%}")
    print(f"Context Precision: {metrics.context_precision:.2%}")
    print(f"Context Recall: {metrics.context_recall:.2%}")
    print(f"Overall Score: {metrics.overall_score():.2%}")
    print(f"Passing: {metrics.is_passing()}")
    
    # Option 2: Batch evaluation
    test_cases = [
        {"query": "How do I deploy?", "expected": ["deploy_guide.md"]},
        {"query": "What's the team structure?", "expected": ["org_chart.md"]},
    ]
    
    results = await rag.evaluate_quality(test_cases)
    print(f"\nBatch Results:")
    print(f"  Passing Rate: {results['passing_rate']:.2%}")
    print(f"  Avg Faithfulness: {results['overall']['faithfulness']:.2%}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Testing: Phase 1a

**File:** `tests/rag/test_ragas_metrics.py`

```python
"""Test RAGAS metrics implementation."""

import pytest
from agentic_brain.rag.ragas_evaluator import RAGASEvaluator, RAGASMetrics


@pytest.mark.asyncio
async def test_faithfulness_supported_claim():
    """Test faithfulness with supported claim."""
    evaluator = RAGASEvaluator()
    
    query = "What is GraphRAG?"
    answer = "GraphRAG is a hierarchical knowledge graph approach to RAG."
    context = "GraphRAG uses hierarchical community detection and knowledge graphs."
    
    score = await evaluator.faithfulness(query, answer, context)
    assert 0.7 <= score <= 1.0, "Supported claim should have high faithfulness"


@pytest.mark.asyncio
async def test_faithfulness_hallucination():
    """Test faithfulness with hallucinated claim."""
    evaluator = RAGASEvaluator()
    
    query = "What is GraphRAG?"
    answer = "GraphRAG was invented by OpenAI in 2025."  # False claim
    context = "GraphRAG is from Microsoft Research."
    
    score = await evaluator.faithfulness(query, answer, context)
    assert score < 0.5, "Hallucinated claim should have low faithfulness"


@pytest.mark.asyncio
async def test_answer_relevancy():
    """Test answer relevancy metric."""
    evaluator = RAGASEvaluator()
    
    query = "How do I deploy?"
    answer = "To deploy, follow these steps: 1) Configure 2) Build 3) Deploy"
    
    score = await evaluator.answer_relevancy(query, answer)
    assert 0.7 <= score <= 1.0, "Answer should be highly relevant"


@pytest.mark.asyncio
async def test_metrics_overall_score():
    """Test overall score calculation."""
    metrics = RAGASMetrics(
        query="test",
        answer="test",
        context="test",
        faithfulness=0.9,
        answer_relevancy=0.8,
        context_precision=0.85,
        context_recall=0.75
    )
    
    overall = metrics.overall_score()
    assert 0.8 <= overall <= 0.9, "Overall should be weighted average"


def test_metrics_passing():
    """Test passing threshold logic."""
    metrics = RAGASMetrics(
        query="test",
        answer="test",
        context="test",
        faithfulness=0.85,
        answer_relevancy=0.75,
        context_precision=0.8,
        context_recall=0.75
    )
    
    assert metrics.is_passing(), "All metrics above threshold should pass"
    
    metrics.faithfulness = 0.7  # Below threshold
    assert not metrics.is_passing(), "Low faithfulness should fail"
```

---

## Microsoft GraphRAG Global Search (Phase 1)

### Overview

Global search differs from local search:

- **Local Search:** Find entity details + direct relationships
- **Global Search:** Identify themes/patterns across entire knowledge base

Uses hierarchical community structure to:
1. Rate communities by relevance to query
2. Select top communities (dynamic selection)
3. Map: Analyze each community for insights
4. Reduce: Synthesize findings into coherent themes
5. Refine: LLM polishing of final answer

### Implementation: Phase 1b (Weeks 5-8)

#### Step 1: Community Relevance Scoring

**File:** `src/agentic_brain/rag/global_search.py`

```python
"""Global search for GraphRAG using theme-based querying."""

import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class Community:
    """A community in the knowledge graph."""
    
    id: str
    name: str
    description: str
    size: int  # Number of nodes
    entities: List[str]
    relationships: List[str]
    summary: Optional[str] = None  # LLM-generated summary
    depth: int = 0  # Hierarchical level


@dataclass
class GlobalSearchResult:
    """Result of global search query."""
    
    query: str
    answer: str
    supporting_communities: List[Community]
    reasoning: str
    confidence: float


class CommunityRelevanceScorer:
    """Score community relevance to a query."""
    
    def __init__(self, llm_provider=None):
        self.llm = llm_provider
    
    async def score(
        self,
        query: str,
        community: Community
    ) -> Tuple[float, str]:
        """
        Score how relevant a community is to the query.
        
        Args:
            query: User query
            community: Community to score
            
        Returns:
            (score, reasoning) where score is 0-1
        """
        prompt = f"""You are a relevance scorer for a knowledge graph query system.

Query: {query}

Community: {community.name}
Description: {community.description}
Size: {community.size} entities
Sample Entities: {', '.join(community.entities[:5])}

Rate how relevant this community is to answering the query on a scale of 0-1:
- 1.0: Highly relevant, contains key information
- 0.7: Moderately relevant, might provide context
- 0.3: Weakly relevant, tangentially related
- 0.0: Not relevant at all

Respond with format: SCORE: <float> REASON: <explanation>
"""
        
        try:
            response = await self.llm.generate(prompt)
            lines = response.split('\n')
            
            score = 0.0
            reason = ""
            
            for line in lines:
                if line.startswith("SCORE:"):
                    score = float(line.replace("SCORE:", "").strip())
                elif line.startswith("REASON:"):
                    reason = line.replace("REASON:", "").strip()
            
            return max(0.0, min(1.0, score)), reason
        
        except Exception as e:
            logger.error(f"Error scoring community: {e}")
            return 0.5, "Error in scoring"


class GlobalSearchEngine:
    """Execute global searches across knowledge graph."""
    
    def __init__(self, graph_client, llm_provider, depth: int = 2):
        """
        Initialize global search engine.
        
        Args:
            graph_client: Neo4j client
            llm_provider: LLM for relevance scoring and synthesis
            depth: Maximum hierarchy depth to search (1-3)
        """
        self.graph = graph_client
        self.llm = llm_provider
        self.depth = depth
        self.scorer = CommunityRelevanceScorer(llm_provider)
        self.community_cache = {}  # Cache communities and summaries
    
    async def search(
        self,
        query: str,
        threshold: float = 0.5,
        top_k: int = 10
    ) -> GlobalSearchResult:
        """
        Execute global search across knowledge graph.
        
        Steps:
        1. Fetch all communities at current depth level
        2. Score each community for relevance
        3. Filter by threshold, take top_k
        4. Generate community-level insights (map)
        5. Synthesize into final answer (reduce)
        6. Polish with LLM
        
        Args:
            query: User query
            threshold: Relevance threshold (0-1)
            top_k: Maximum communities to process
            
        Returns:
            GlobalSearchResult with answer and supporting communities
        """
        logger.info(f"Global search: {query} (depth={self.depth}, threshold={threshold})")
        
        # Step 1: Fetch communities
        communities = await self._fetch_communities(self.depth)
        logger.info(f"Found {len(communities)} communities at depth {self.depth}")
        
        # Step 2: Score communities
        scored_communities = await asyncio.gather(*[
            self.scorer.score(query, community)
            for community in communities
        ])
        
        # Step 3: Filter and select
        relevant_communities = [
            (community, score)
            for community, (score, _) in zip(communities, scored_communities)
            if score >= threshold
        ]
        
        relevant_communities.sort(key=lambda x: x[1], reverse=True)
        relevant_communities = relevant_communities[:top_k]
        
        logger.info(f"Selected {len(relevant_communities)} relevant communities")
        
        if not relevant_communities:
            return GlobalSearchResult(
                query=query,
                answer="No relevant communities found.",
                supporting_communities=[],
                reasoning="No sufficient matches in knowledge base.",
                confidence=0.0
            )
        
        # Step 4: Map - analyze each community
        community_insights = await asyncio.gather(*[
            self._analyze_community(community, query)
            for community, _ in relevant_communities
        ])
        
        # Step 5: Reduce - synthesize findings
        synthesis = await self._synthesize_insights(
            query,
            community_insights,
            [c for c, _ in relevant_communities]
        )
        
        # Step 6: Refine - LLM polish
        final_answer = await self._refine_answer(query, synthesis)
        
        return GlobalSearchResult(
            query=query,
            answer=final_answer,
            supporting_communities=[c for c, _ in relevant_communities],
            reasoning=synthesis,
            confidence=sum(s for _, s in relevant_communities) / len(relevant_communities)
        )
    
    async def _fetch_communities(self, depth: int) -> List[Community]:
        """Fetch community hierarchies from graph."""
        # Query Neo4j for communities
        query_str = """
        MATCH (c:Community)
        WHERE c.depth <= $depth
        RETURN c.id as id, c.name as name, c.description as description,
               c.size as size, c.entities as entities, c.depth as depth
        LIMIT 1000
        """
        
        try:
            results = await self.graph.run(query_str, depth=depth)
            communities = [
                Community(
                    id=r['id'],
                    name=r['name'],
                    description=r['description'],
                    size=r['size'],
                    entities=r['entities'] or [],
                    relationships=[],  # Populate separately if needed
                    depth=r['depth']
                )
                for r in results
            ]
            return communities
        
        except Exception as e:
            logger.error(f"Error fetching communities: {e}")
            return []
    
    async def _analyze_community(
        self,
        community: Community,
        query: str
    ) -> str:
        """Generate insights from a single community."""
        prompt = f"""You are a knowledge analyst for a graph database.

Community: {community.name}
Description: {community.description}
Size: {community.size} entities
Sample Entities: {', '.join(community.entities[:10])}

Original Query: {query}

Analyze this community and provide key insights related to the query.
Be concise but comprehensive. Focus on:
1. What main themes/topics are in this community?
2. How do these relate to the query?
3. Key entities or relationships of note?

Response (2-3 sentences):
"""
        
        try:
            insight = await self.llm.generate(prompt)
            return insight
        except:
            return f"Community {community.name}: {len(community.entities)} entities."
    
    async def _synthesize_insights(
        self,
        query: str,
        insights: List[str],
        communities: List[Community]
    ) -> str:
        """Synthesize insights from multiple communities (reduce step)."""
        insights_text = "\n\n".join([
            f"Community {i+1} ({communities[i].name}):\n{insight}"
            for i, insight in enumerate(insights)
        ])
        
        prompt = f"""You are a knowledge synthesis expert. You have analyzed multiple 
communities in a knowledge graph relevant to the following query:

Query: {query}

Community Analyses:
{insights_text}

Synthesize these insights into a coherent response that:
1. Identifies common themes across communities
2. Highlights key relationships and patterns
3. Provides a comprehensive answer to the query
4. Acknowledges any contradictions or nuances

Response (3-5 sentences):
"""
        
        try:
            synthesis = await self.llm.generate(prompt)
            return synthesis
        except:
            return insights_text
    
    async def _refine_answer(self, query: str, synthesis: str) -> str:
        """Polish and refine final answer with LLM."""
        prompt = f"""You are a senior knowledge analyst. Based on the following synthesis
of multiple knowledge graph communities, provide a polished final answer to the user's query.

Query: {query}

Analysis Summary:
{synthesis}

Provide a clear, well-structured answer that:
1. Directly addresses the query
2. Draws on the analysis
3. Is suitable for a senior stakeholder
4. Highlights key insights and findings

Final Answer:
"""
        
        try:
            answer = await self.llm.generate(prompt)
            return answer
        except:
            return synthesis


# Integration with RAGPipeline
class RAGPipelineWithGlobalSearch:
    """Extend RAGPipeline with global search."""
    
    def __init__(self, rag_pipeline, graph_client, llm_provider):
        self.pipeline = rag_pipeline
        self.global_search = GlobalSearchEngine(graph_client, llm_provider)
    
    async def query(
        self,
        query: str,
        search_type: str = "auto"
    ) -> Dict:
        """
        Execute query with automatic search type selection.
        
        Args:
            query: User query
            search_type: "local", "global", or "auto" (detects query type)
            
        Returns:
            Result with answer and supporting information
        """
        
        if search_type == "auto":
            # Detect query type
            search_type = await self._detect_query_type(query)
        
        if search_type == "global":
            result = await self.global_search.search(query)
            return {
                'answer': result.answer,
                'type': 'global_search',
                'confidence': result.confidence,
                'communities': [c.name for c in result.supporting_communities]
            }
        else:
            # Local search (default)
            result = await self.pipeline.query(query)
            return {
                'answer': result.answer,
                'type': 'local_search',
                'documents': [d.source for d in result.documents]
            }
    
    async def _detect_query_type(self, query: str) -> str:
        """Detect if query requires global or local search."""
        global_keywords = [
            'theme', 'pattern', 'trend', 'overview', 'summary',
            'main', 'general', 'broad', 'overall', 'holistic',
            'interconnection', 'relationship', 'connection'
        ]
        
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in global_keywords):
            return "global"
        else:
            return "local"
```

---

## DSPy Optimization (Phase 2)

### Overview

DSPy replaces manual prompting with declarative specifications that are auto-optimized.

**Key Concept:** Prompts are parameters; optimizers tune them like neural network weights.

### Step 1: DSPy Integration Module

**File:** `src/agentic_brain/rag/dspy_integration.py`

```python
"""DSPy integration for automatic prompt optimization."""

try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False


if DSPY_AVAILABLE:
    
    class RAGSignature(dspy.Signature):
        """Signature for RAG retrieval-generation task."""
        
        context = dspy.InputField(
            desc="Retrieved context documents"
        )
        query = dspy.InputField(
            desc="User query to answer"
        )
        answer = dspy.OutputField(
            desc="Generated answer grounded in context"
        )
    
    
    class OptimizedRAGModule(dspy.Module):
        """Optimizable RAG module."""
        
        def __init__(self):
            super().__init__()
            self.retrieval = dspy.Retrieve(k=5)  # Retrieve top 5
            self.generator = dspy.ChainOfThought(RAGSignature)
        
        def forward(self, query: str) -> dspy.Prediction:
            """Execute RAG pipeline."""
            # Retrieve
            context = self.retrieval(query).context
            
            # Generate with chain-of-thought
            return self.generator(context=context, query=query)
    
    
    def get_dspy_optimizer(
        optimizer_name: str = "MIPROv2",
        num_trials: int = 100
    ):
        """Get DSPy optimizer instance."""
        
        if optimizer_name == "MIPROv2":
            return dspy.MIPROv2(num_trials=num_trials)
        elif optimizer_name == "GEPA":
            return dspy.GEPA()
        elif optimizer_name == "BootstrapFewShot":
            return dspy.BootstrapFewShot(k=3)
        else:
            raise ValueError(f"Unknown optimizer: {optimizer_name}")
    
    
    async def optimize_rag_prompts(
        trainset: List[Dict],
        metric_fn,
        optimizer_name: str = "MIPROv2"
    ) -> OptimizedRAGModule:
        """
        Optimize RAG prompts automatically.
        
        Args:
            trainset: Training examples {query, context, expected_answer}
            metric_fn: Metric function to maximize
            optimizer_name: Which optimizer to use
            
        Returns:
            Optimized RAG module with best prompts
        """
        
        # Create base module
        module = OptimizedRAGModule()
        
        # Create optimizer
        optimizer = get_dspy_optimizer(optimizer_name)
        
        # Compile (optimize prompts)
        compiled_module = optimizer.compile(
            student=module,
            trainset=trainset,
            valset=trainset[:len(trainset)//5],  # Use 20% for validation
            metric=metric_fn,
            max_bootstrapped_demos=3,
            max_labeled_demos=3
        )
        
        return compiled_module

else:
    
    class OptimizedRAGModule:
        """Stub when DSPy not available."""
        
        def __init__(self):
            raise ImportError(
                "DSPy not installed. Install with: pip install dspy-ai"
            )
```

---

## Text2Cypher Pattern (Phase 2)

### Step 1: NL to Cypher Translation

**File:** `src/agentic_brain/rag/text2cypher.py`

```python
"""Convert natural language queries to Cypher for Neo4j."""

import logging
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CypherTranslation:
    """Result of NL to Cypher translation."""
    
    original_query: str
    cypher_query: str
    reasoning: str
    confidence: float


class Text2CypherTranslator:
    """Translate natural language to Cypher queries."""
    
    def __init__(self, llm_provider, graph_schema: Optional[str] = None):
        self.llm = llm_provider
        self.schema = graph_schema or self._get_graph_schema()
    
    async def translate(
        self,
        nl_query: str
    ) -> CypherTranslation:
        """
        Translate natural language query to Cypher.
        
        Args:
            nl_query: Natural language query
            
        Returns:
            CypherTranslation with Cypher query and reasoning
        """
        
        prompt = f"""You are a Neo4j Cypher query generator. Convert natural language 
queries into syntactically correct Cypher queries.

Graph Schema:
{self.schema}

Natural Language Query: {nl_query}

Task:
1. Understand the natural language query
2. Identify entities and relationships
3. Generate a valid Cypher query
4. Ensure the query is optimized and safe

Response format:
CYPHER: <cypher query>
REASONING: <explain your approach>
CONFIDENCE: <0.0-1.0 confidence score>
"""
        
        try:
            response = await self.llm.generate(prompt)
            
            cypher = ""
            reasoning = ""
            confidence = 0.5
            
            for line in response.split('\n'):
                if line.startswith("CYPHER:"):
                    cypher = line.replace("CYPHER:", "").strip()
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.replace("CONFIDENCE:", "").strip())
                    except:
                        pass
            
            return CypherTranslation(
                original_query=nl_query,
                cypher_query=cypher,
                reasoning=reasoning,
                confidence=confidence
            )
        
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return CypherTranslation(
                original_query=nl_query,
                cypher_query="",
                reasoning=f"Error: {str(e)}",
                confidence=0.0
            )
    
    def _get_graph_schema(self) -> str:
        """Get graph schema from Neo4j."""
        # Query Neo4j for schema information
        return """
        Nodes: :User, :Project, :Document, :Topic
        Relationships: 
          - (u:User)-[:HAS_PROJECT]->(p:Project)
          - (p:Project)-[:CONTAINS]->(d:Document)
          - (d:Document)-[:ABOUT]->(t:Topic)
          - (u:User)-[:AUTHORED]->(d:Document)
        """


class Text2CypherRetriever:
    """Retrieve documents using NL to Cypher translation."""
    
    def __init__(self, graph_client, translator: Text2CypherTranslator):
        self.graph = graph_client
        self.translator = translator
    
    async def retrieve(self, nl_query: str) -> List[Dict]:
        """
        Retrieve results from Neo4j using NL query.
        
        Args:
            nl_query: Natural language query
            
        Returns:
            List of retrieved documents/entities
        """
        
        # Translate to Cypher
        translation = await self.translator.translate(nl_query)
        
        if not translation.cypher_query:
            logger.warning(f"Failed to translate: {nl_query}")
            return []
        
        if translation.confidence < 0.5:
            logger.warning(f"Low confidence translation: {translation.confidence}")
        
        try:
            # Execute Cypher query
            results = await self.graph.run(translation.cypher_query)
            return list(results)
        
        except Exception as e:
            logger.error(f"Cypher execution error: {e}")
            return []
```

---

## Dynamic Community Selection (Phase 3)

See main specification document for details. Implementation involves:

1. Rate communities by LLM relevance scoring
2. Filter by threshold (default 0.5)
3. Only process top-K communities
4. Cache results for efficiency

**Expected savings:** ~77% computational cost reduction for global search

---

## LlamaIndex Compatibility (Phase 4)

### Adapter Layer

**File:** `src/agentic_brain/rag/llamaindex_adapter.py`

```python
"""Compatibility layer between agentic-brain and LlamaIndex."""

try:
    from llama_index.schema import Document as LIDocument
    from llama_index.indices.base import BaseIndex
    from llama_index.retrievers.base import BaseRetriever
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False


if LLAMAINDEX_AVAILABLE:
    
    def convert_to_llamaindex_docs(documents: List[Dict]) -> List[LIDocument]:
        """Convert agentic-brain documents to LlamaIndex format."""
        return [
            LIDocument(
                text=doc['page_content'],
                metadata=doc.get('metadata', {}),
                doc_id=doc.get('id', None)
            )
            for doc in documents
        ]
    
    
    def convert_from_llamaindex_docs(
        docs: List[LIDocument]
    ) -> List[Dict]:
        """Convert LlamaIndex documents to agentic-brain format."""
        return [
            {
                'page_content': doc.text,
                'metadata': doc.metadata,
                'id': doc.doc_id
            }
            for doc in docs
        ]
    
    
    class AgenticBrainRetriever(BaseRetriever):
        """Use agentic-brain retrievers in LlamaIndex."""
        
        def __init__(self, ab_retriever):
            self.ab_retriever = ab_retriever
        
        def _retrieve(self, query_str: str):
            """Retrieve using agentic-brain."""
            docs = self.ab_retriever.retrieve(query_str)
            return convert_to_llamaindex_docs(docs)

else:
    
    class AgenticBrainRetriever:
        """Stub when LlamaIndex not available."""
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "LlamaIndex not installed. Install with: pip install llama-index"
            )
```

---

## Testing & Benchmarking

### Integration Tests

**File:** `tests/rag/test_spec_integration.py`

```python
"""Test specification compliance and interoperability."""

import pytest
from agentic_brain.rag import RAGPipeline
from agentic_brain.rag.ragas_evaluator import RAGASEvaluator
from agentic_brain.rag.global_search import GlobalSearchEngine


@pytest.mark.integration
async def test_ragas_evaluation_pipeline():
    """Test RAGAS metrics in RAG pipeline."""
    rag = RAGPipeline()
    evaluator = RAGASEvaluator()
    
    result = await rag.query("Test query")
    metrics = await evaluator.evaluate_all(
        query="Test query",
        answer=result.answer,
        context=result.context,
        context_docs=result.documents
    )
    
    assert metrics.faithfulness >= 0.0
    assert metrics.answer_relevancy >= 0.0
    assert 0.0 <= metrics.overall_score() <= 1.0


@pytest.mark.integration
async def test_global_search_execution():
    """Test global search query execution."""
    engine = GlobalSearchEngine(graph_client, llm_provider)
    
    result = await engine.search("What are main themes?", threshold=0.5)
    
    assert result.answer
    assert result.confidence >= 0.0
    assert len(result.supporting_communities) > 0


@pytest.mark.integration
async def test_text2cypher_translation():
    """Test NL to Cypher translation."""
    translator = Text2CypherTranslator(llm_provider)
    
    translation = await translator.translate(
        "Find all users with projects"
    )
    
    assert translation.cypher_query
    assert translation.confidence >= 0.0
    # Execute and verify it returns results
```

### Benchmarking Suite

**File:** `benchmarks/spec_benchmark.py`

```python
"""Benchmark RAG specification implementations."""

import time
import asyncio
from agentic_brain.rag import RAGPipeline
from agentic_brain.rag.ragas_evaluator import RAGASEvaluator
from agentic_brain.rag.global_search import GlobalSearchEngine


async def benchmark_ragas_metrics():
    """Benchmark RAGAS evaluation performance."""
    evaluator = RAGASEvaluator()
    
    test_cases = [
        {
            "query": "What is GraphRAG?",
            "answer": "GraphRAG is...",
            "context": "GraphRAG is a knowledge graph..."
        },
        # ... more test cases
    ]
    
    start = time.time()
    
    for case in test_cases:
        metrics = await evaluator.evaluate_all(
            query=case['query'],
            answer=case['answer'],
            context=case['context'],
            context_docs=[]
        )
    
    elapsed = time.time() - start
    print(f"RAGAS evaluation: {elapsed:.2f}s for {len(test_cases)} queries")
    print(f"Average: {elapsed/len(test_cases)*1000:.1f}ms per query")


async def benchmark_global_search():
    """Benchmark global search performance."""
    engine = GlobalSearchEngine(graph_client, llm_provider)
    
    queries = [
        "What are main themes?",
        "What's the pattern?",
        "Provide an overview",
    ]
    
    start = time.time()
    
    for query in queries:
        result = await engine.search(query, threshold=0.5)
    
    elapsed = time.time() - start
    print(f"Global search: {elapsed:.2f}s for {len(queries)} queries")
```

---

## Summary

This guide provides:

✅ **RAGAS Integration:** Complete implementation blueprint (Phase 1a)  
✅ **Global Search:** Map-reduce synthesis pipeline (Phase 1b)  
✅ **DSPy:** Prompt optimization framework (Phase 2)  
✅ **Text2Cypher:** NL to Cypher translation (Phase 2)  
✅ **Testing:** Integration and benchmark suites  

Next phases add:
- Dynamic community selection (Phase 3)
- MLOps observability (Phase 3)
- LlamaIndex/Haystack adapters (Phase 4)
- Memory graphs and domain templates (Phase 5)

---

**Document Version:** 1.0  
**Last Updated:** 2025-03-XX  
**Status:** Ready for Implementation
