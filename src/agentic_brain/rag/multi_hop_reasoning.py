# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Multi-Hop Reasoning - Chain Multiple Retrieval Steps

Handles questions that require multiple retrieval steps where
each step's answer informs the next query.

Example:
    Question: "Who manages the project that fixed bug #123?"

    Hop 1: "What project fixed bug #123?" -> "Project Alpha"
    Hop 2: "Who manages Project Alpha?" -> "Sarah Chen"

    Final: "Sarah Chen manages Project Alpha, which fixed bug #123"

Use cases:
- Following relationships (who -> what -> when)
- Entity resolution (this name -> that ID -> related records)
- Temporal chains (what happened -> what caused it -> what was affected)
- Multi-level aggregation (individual -> team -> department)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from ..exceptions import RAGError

logger = logging.getLogger(__name__)


class HopType(Enum):
    """Types of reasoning hops."""

    ENTITY_LOOKUP = "entity"  # Find an entity (who, what)
    RELATIONSHIP = "relationship"  # Follow a relationship
    TEMPORAL = "temporal"  # Time-based reasoning
    CAUSAL = "causal"  # Cause-effect chain
    AGGREGATION = "aggregation"  # Combine multiple results


class LLMClient(Protocol):
    """Protocol for LLM used in reasoning."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt."""
        ...


class RetrieverProtocol(Protocol):
    """Protocol for retriever."""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve documents for query."""
        ...


@dataclass
class ReasoningHop:
    """A single hop in the reasoning chain."""

    query: str
    hop_type: HopType
    purpose: str  # Why this hop is needed
    answer: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class ReasoningChain:
    """Complete reasoning chain with all hops."""

    original_query: str
    hops: list[ReasoningHop]
    final_answer: str
    confidence: float
    explanation: str  # Human-readable explanation of reasoning
    citations: list[str] = field(default_factory=list)


class MultiHopReasoner:
    """
    Execute multi-hop reasoning for complex questions.

    Process:
    1. Analyze query to identify required hops
    2. Execute each hop, using previous answers as context
    3. Synthesize final answer with reasoning chain
    4. Provide citations and confidence

    Example:
        reasoner = MultiHopReasoner(llm, retriever)
        result = reasoner.reason(
            "What's the status of the server that hosts our main database?"
        )
        # Hop 1: What server hosts main database? -> db-server-01
        # Hop 2: What's the status of db-server-01? -> Running, 98% healthy
        print(result.final_answer)
    """

    # Patterns suggesting multi-hop is needed
    MULTI_HOP_PATTERNS = [
        "who.*that",
        "what.*that",
        "where.*which",
        ".*of the.*that",
        ".*managed by.*who",
        ".*responsible for.*what",
        ".*depends on.*status",
        ".*caused by.*what",
        ".*led to.*what happened",
        ".*before.*after",
        ".*then.*what",
    ]

    def __init__(
        self,
        llm: LLMClient,
        retriever: RetrieverProtocol,
        max_hops: int = 5,
        min_confidence: float = 0.5,
    ):
        """
        Initialize multi-hop reasoner.

        Args:
            llm: LLM for reasoning
            retriever: Retriever for each hop
            max_hops: Maximum reasoning depth
            min_confidence: Minimum confidence per hop to continue
        """
        self.llm = llm
        self.retriever = retriever
        self.max_hops = max_hops
        self.min_confidence = min_confidence

    def needs_multi_hop(self, query: str) -> bool:
        """Check if query requires multi-hop reasoning."""
        import re

        query_lower = query.lower()

        # Check patterns
        for pattern in self.MULTI_HOP_PATTERNS:
            if re.search(pattern, query_lower):
                return True

        # Ask LLM for complex cases
        prompt = f"""Does this question require multiple steps to answer?
(Finding one thing, then using that to find another)

Question: {query}

Answer YES or NO:"""

        response = self.llm.generate(prompt, max_tokens=10)
        return "yes" in response.lower()

    def plan_hops(self, query: str) -> list[ReasoningHop]:
        """
        Plan the reasoning chain before execution.

        Uses LLM to decompose question into logical hops.
        """
        prompt = f"""Plan a step-by-step reasoning chain to answer this question.
Each step should find information needed for the next step.

Question: {query}

Return as numbered steps:
1. [First thing to find] - [why needed]
2. [Next thing using step 1] - [why needed]
etc.

Maximum {self.max_hops} steps. If answerable directly, just one step.

Steps:"""

        response = self.llm.generate(prompt, max_tokens=400)

        hops = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or not line[0].isdigit():
                continue

            # Parse "1. [query] - [purpose]"
            parts = line.split(".", 1)
            if len(parts) < 2:
                continue

            content = parts[1].strip()
            if " - " in content:
                query_part, purpose = content.split(" - ", 1)
            else:
                query_part = content
                purpose = "Answer part of the question"

            # Detect hop type
            hop_type = self._detect_hop_type(query_part.lower())

            hops.append(
                ReasoningHop(
                    query=query_part.strip(),
                    hop_type=hop_type,
                    purpose=purpose.strip(),
                )
            )

        # Fallback: single hop with original query
        if not hops:
            hops = [
                ReasoningHop(
                    query=query,
                    hop_type=HopType.ENTITY_LOOKUP,
                    purpose="Answer the question",
                )
            ]

        return hops[: self.max_hops]

    def _detect_hop_type(self, query: str) -> HopType:
        """Detect the type of reasoning hop from query."""
        if any(w in query for w in ["who", "what person", "which team"]):
            return HopType.ENTITY_LOOKUP
        elif any(w in query for w in ["manages", "owns", "related", "connected"]):
            return HopType.RELATIONSHIP
        elif any(w in query for w in ["when", "before", "after", "during"]):
            return HopType.TEMPORAL
        elif any(w in query for w in ["caused", "because", "result", "led to"]):
            return HopType.CAUSAL
        elif any(w in query for w in ["all", "total", "summary", "count"]):
            return HopType.AGGREGATION
        return HopType.ENTITY_LOOKUP

    def execute_hop(
        self, hop: ReasoningHop, previous_answers: list[str]
    ) -> ReasoningHop:
        """
        Execute a single reasoning hop.

        Uses previous answers as context for the query.
        """
        # Enhance query with context from previous hops
        context = ""
        if previous_answers:
            context = "\n\nContext from previous steps:\n"
            for i, ans in enumerate(previous_answers, 1):
                context += f"- Step {i}: {ans}\n"

        # Retrieve relevant documents
        enhanced_query = hop.query
        if previous_answers:
            enhanced_query = f"{hop.query} (given: {previous_answers[-1]})"

        sources = self.retriever.retrieve(enhanced_query, top_k=3)
        hop.sources = sources

        source_text = "\n".join(
            doc.get("content", doc.get("text", str(doc)))[:400] for doc in sources
        )

        # Generate answer for this hop
        prompt = f"""Answer this specific question using the context.
Be concise - this is one step in a reasoning chain.

Question: {hop.query}
Purpose: {hop.purpose}
{context}
Retrieved Context:
{source_text}

Answer (be specific and brief):"""

        try:
            response = self.llm.generate(prompt, max_tokens=200)
            hop.answer = response.strip()

            # Assess confidence
            conf_prompt = f"""Rate confidence (0.0-1.0) that this answer is correct:
Q: {hop.query}
A: {hop.answer}

Just the number:"""
            conf_response = self.llm.generate(conf_prompt, max_tokens=10)
            try:
                hop.confidence = float(conf_response.strip())
            except ValueError:
                hop.confidence = 0.7

            hop.reasoning = f"Found via {hop.hop_type.value} search"

        except Exception as e:
            hop.answer = f"Could not determine: {e}"
            hop.confidence = 0.0

        return hop

    def synthesize_chain(self, query: str, hops: list[ReasoningHop]) -> ReasoningChain:
        """
        Synthesize final answer from reasoning chain.
        """
        # Build chain summary
        chain_summary = ""
        for i, hop in enumerate(hops, 1):
            chain_summary += f"Step {i}: {hop.query}\n"
            chain_summary += f"  Found: {hop.answer}\n"
            chain_summary += f"  Confidence: {hop.confidence:.0%}\n\n"

        prompt = f"""Synthesize a final answer based on this reasoning chain.

Original Question: {query}

Reasoning Chain:
{chain_summary}

Provide:
1. A clear final answer
2. A brief explanation of the reasoning
3. Overall confidence (0.0-1.0)

FINAL_ANSWER: [answer]
EXPLANATION: [reasoning]
CONFIDENCE: [0.0-1.0]"""

        response = self.llm.generate(prompt, max_tokens=400)

        # Parse response
        final_answer = ""
        explanation = ""
        confidence = 0.0

        for line in response.split("\n"):
            if line.startswith("FINAL_ANSWER:"):
                final_answer = line[13:].strip()
            elif line.startswith("EXPLANATION:"):
                explanation = line[12:].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line[11:].strip())
                except ValueError:
                    confidence = sum(h.confidence for h in hops) / max(len(hops), 1)

        # Fallback parsing
        if not final_answer:
            final_answer = response.split("\n")[0]

        # Collect citations
        citations = []
        for hop in hops:
            for src in hop.sources[:1]:  # Top source per hop
                title = src.get("title") or src.get("source") or "Unknown"
                citations.append(f"{title} (Hop: {hop.purpose})")

        return ReasoningChain(
            original_query=query,
            hops=hops,
            final_answer=final_answer,
            confidence=confidence,
            explanation=explanation,
            citations=citations,
        )

    def reason(self, query: str) -> ReasoningChain:
        """
        Execute full multi-hop reasoning pipeline.

        This is the main entry point.

        Args:
            query: Complex question requiring multi-hop reasoning

        Returns:
            ReasoningChain with final answer and all hops
        """
        # Check if multi-hop needed
        if not self.needs_multi_hop(query):
            # Simple single-hop retrieval
            sources = self.retriever.retrieve(query, top_k=5)
            source_text = "\n".join(
                doc.get("content", doc.get("text", str(doc)))[:500] for doc in sources
            )

            prompt = f"Answer based on context:\nQ: {query}\nContext: {source_text}\n\nAnswer:"
            answer = self.llm.generate(prompt, max_tokens=300)

            single_hop = ReasoningHop(
                query=query,
                hop_type=HopType.ENTITY_LOOKUP,
                purpose="Direct answer",
                answer=answer,
                sources=sources,
                confidence=0.8,
            )

            return ReasoningChain(
                original_query=query,
                hops=[single_hop],
                final_answer=answer,
                confidence=0.8,
                explanation="Answered directly without multi-hop reasoning",
            )

        # Plan reasoning chain
        hops = self.plan_hops(query)

        # Execute each hop
        previous_answers: list[str] = []
        for hop in hops:
            hop = self.execute_hop(hop, previous_answers)

            if hop.answer and hop.confidence >= self.min_confidence:
                previous_answers.append(hop.answer)
            else:
                # Low confidence - stop chain
                logger.warning(
                    f"Stopping at hop '{hop.query}' due to low confidence: {hop.confidence}"
                )
                break

        # Synthesize final answer
        return self.synthesize_chain(query, hops)


class GraphMultiHopReasoner(MultiHopReasoner):
    """
    Multi-hop reasoner optimized for graph databases (Neo4j).

    Uses graph traversal for relationship following,
    which is more efficient than repeated text retrieval.
    """

    def __init__(
        self,
        llm: LLMClient,
        retriever: RetrieverProtocol,
        neo4j_driver: Any | None = None,
        **kwargs: Any,
    ):
        super().__init__(llm, retriever, **kwargs)
        self.neo4j_driver = neo4j_driver

    def execute_hop(
        self, hop: ReasoningHop, previous_answers: list[str]
    ) -> ReasoningHop:
        """
        Execute hop with graph traversal for relationships.
        """
        # Use graph for relationship hops if Neo4j available
        if (
            hop.hop_type == HopType.RELATIONSHIP
            and self.neo4j_driver
            and previous_answers
        ):
            try:
                hop = self._graph_traverse(hop, previous_answers[-1])
                return hop
            except Exception as e:
                logger.warning(f"Graph traversal failed, falling back to text: {e}")

        # Fall back to text retrieval
        return super().execute_hop(hop, previous_answers)

    def _graph_traverse(self, hop: ReasoningHop, entity: str) -> ReasoningHop:
        """
        Use Neo4j to follow relationships.
        """
        # Generate Cypher based on hop
        cypher_prompt = f"""Generate a Cypher query to find: {hop.query}
Starting from entity: {entity}

Return just the Cypher, no explanation.
Query should RETURN relevant properties.

Cypher:"""

        cypher = self.llm.generate(cypher_prompt, max_tokens=150)

        # Clean up Cypher
        cypher = cypher.strip()
        if cypher.startswith("```"):
            cypher = cypher.split("\n", 1)[1].rsplit("```", 1)[0]

        # Execute
        if not self.neo4j_driver:
            return []
        with self.neo4j_driver.session() as session:
            result = session.run(cypher)
            records = list(result)

        if records:
            # Format results as answer
            hop.answer = str([dict(r) for r in records[:3]])
            hop.sources = [{"source": "Neo4j", "cypher": cypher}]
            hop.confidence = 0.85
            hop.reasoning = f"Found via graph traversal: {cypher[:100]}..."
        else:
            hop.answer = "No results found in graph"
            hop.confidence = 0.3

        return hop
