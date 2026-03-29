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
Query Decomposition for Complex Multi-Part Questions

Breaks complex questions into simpler sub-queries, retrieves answers
for each, then synthesizes a comprehensive response.

Example:
    query = "Compare our Q3 sales to Q2 and explain the difference"

    Decomposes to:
    - "What were our Q3 sales figures?"
    - "What were our Q2 sales figures?"
    - "What factors affected sales between Q2 and Q3?"

    Then synthesizes: "Q3 sales were $X vs Q2 $Y, a Z% change due to..."

Patterns supported:
- Comparison queries ("compare X to Y")
- Multi-step queries ("how did we get from A to B")
- Aggregation queries ("summarize all tickets from last week")
- Conditional queries ("if X then what happens to Y")
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from ..exceptions import RAGError


class LLMClient(Protocol):
    """Protocol for LLM client used in decomposition."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt."""
        ...


class RetrieverProtocol(Protocol):
    """Protocol for retriever used in sub-query execution."""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve relevant documents for query."""
        ...


@dataclass
class SubQuery:
    """A decomposed sub-query with its purpose and dependencies."""

    query: str
    purpose: str  # Why this sub-query is needed
    depends_on: list[int] = field(
        default_factory=list
    )  # Indices of queries this depends on
    answer: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DecompositionResult:
    """Result of query decomposition and synthesis."""

    original_query: str
    sub_queries: list[SubQuery]
    final_answer: str
    confidence: float
    reasoning: str  # How the answer was synthesized


class QueryDecomposer:
    """
    Decomposes complex queries into simpler sub-queries.

    Uses an LLM to:
    1. Detect if decomposition is needed
    2. Break query into sub-queries with dependencies
    3. Execute sub-queries in dependency order
    4. Synthesize final answer from sub-answers

    Example:
        decomposer = QueryDecomposer(llm_client, retriever)
        result = decomposer.decompose_and_answer(
            "Compare sales performance in Melbourne vs Sydney for Q3"
        )
        print(result.final_answer)
    """

    # Patterns that suggest decomposition is needed
    DECOMPOSITION_TRIGGERS = [
        "compare",
        "contrast",
        "difference between",
        "how does X relate to Y",
        "explain the connection",
        "summarize all",
        "list all",
        "what are the steps",
        "break down",
        "before and after",
        "if.*then",
        "both.*and",
        "as well as",
        "in addition to",
        "furthermore",
    ]

    def __init__(
        self,
        llm: LLMClient,
        retriever: RetrieverProtocol,
        max_sub_queries: int = 5,
        min_confidence: float = 0.6,
    ):
        """
        Initialize query decomposer.

        Args:
            llm: LLM client for decomposition and synthesis
            retriever: Retriever for executing sub-queries
            max_sub_queries: Maximum sub-queries to generate
            min_confidence: Minimum confidence for final answer
        """
        self.llm = llm
        self.retriever = retriever
        self.max_sub_queries = max_sub_queries
        self.min_confidence = min_confidence

    def needs_decomposition(self, query: str) -> bool:
        """
        Check if query is complex enough to need decomposition.

        Simple heuristics + LLM check for complex cases.
        """
        query_lower = query.lower()

        # Check trigger patterns
        for trigger in self.DECOMPOSITION_TRIGGERS:
            if trigger in query_lower:
                return True

        # Check for multiple question marks
        if query.count("?") > 1:
            return True

        # Check for conjunctions suggesting multiple parts
        conjunctions = ["and", "or", "but", "as well as", "in addition"]
        conj_count = sum(1 for c in conjunctions if f" {c} " in query_lower)
        return conj_count >= 2

    def decompose(self, query: str) -> list[SubQuery]:
        """
        Decompose a complex query into sub-queries.

        Uses LLM to identify components and their dependencies.
        """
        prompt = f"""Decompose this complex query into simpler sub-queries.
Each sub-query should be self-contained and answerable independently.
Identify dependencies between sub-queries (which ones need answers from others).

Query: {query}

Return as JSON array:
[
    {{"query": "sub-query text", "purpose": "why needed", "depends_on": []}}
]

Maximum {self.max_sub_queries} sub-queries.
If query is simple, return single sub-query matching original.

JSON:"""

        try:
            response = self.llm.generate(prompt, max_tokens=500)
            # Parse JSON from response
            import json

            # Find JSON in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                sub_queries_data = json.loads(response[start:end])
                return [
                    SubQuery(
                        query=sq.get("query", query),
                        purpose=sq.get("purpose", "Answer main query"),
                        depends_on=sq.get("depends_on", []),
                    )
                    for sq in sub_queries_data[: self.max_sub_queries]
                ]
        except Exception:
            pass

        # Fallback: return original as single sub-query
        return [SubQuery(query=query, purpose="Answer the question")]

    def execute_sub_queries(self, sub_queries: list[SubQuery]) -> list[SubQuery]:
        """
        Execute sub-queries in dependency order.

        Retrieves context for each and generates answers.
        """
        executed: dict[int, SubQuery] = {}

        # Topological sort by dependencies
        pending = list(range(len(sub_queries)))
        order: list[int] = []

        while pending:
            for i in pending[:]:
                deps = sub_queries[i].depends_on
                if all(d in order for d in deps):
                    order.append(i)
                    pending.remove(i)
                    break
            else:
                # Circular dependency - just process remaining
                order.extend(pending)
                break

        # Execute in order
        for idx in order:
            sq = sub_queries[idx]

            # Build context from dependencies
            dep_context = ""
            for dep_idx in sq.depends_on:
                if dep_idx < len(sub_queries) and sub_queries[dep_idx].answer:
                    dep_context += (
                        f"\nContext from related query: {sub_queries[dep_idx].answer}\n"
                    )

            # Retrieve relevant documents
            sources = self.retriever.retrieve(sq.query, top_k=3)
            sq.sources = sources

            source_text = "\n".join(
                doc.get("content", doc.get("text", str(doc)))[:500] for doc in sources
            )

            # Generate answer
            prompt = f"""Answer this question based on the context.

Question: {sq.query}
Purpose: {sq.purpose}
{dep_context}
Context:
{source_text}

Answer concisely:"""

            try:
                sq.answer = self.llm.generate(prompt, max_tokens=300)
            except Exception as e:
                sq.answer = f"Unable to answer: {e}"

            executed[idx] = sq

        return sub_queries

    def synthesize(
        self, query: str, sub_queries: list[SubQuery]
    ) -> DecompositionResult:
        """
        Synthesize final answer from sub-query answers.
        """
        # Build sub-answer context
        sub_answers = "\n".join(
            f"- {sq.purpose}: {sq.answer}" for sq in sub_queries if sq.answer
        )

        prompt = f"""Synthesize a comprehensive answer to the original question
using these sub-answers.

Original Question: {query}

Sub-Answers:
{sub_answers}

Provide:
1. A clear, comprehensive answer
2. Your confidence (0.0-1.0)
3. Brief reasoning for your synthesis

Format:
ANSWER: [your synthesized answer]
CONFIDENCE: [0.0-1.0]
REASONING: [how you combined the sub-answers]"""

        response = self.llm.generate(prompt, max_tokens=500)

        # Parse response
        final_answer = query  # Default
        confidence = 0.7
        reasoning = "Combined sub-query answers"

        for line in response.split("\n"):
            if line.startswith("ANSWER:"):
                final_answer = line[7:].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line[11:].strip())
                except ValueError:
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line[10:].strip()

        # If we didn't parse structured output, use whole response as answer
        if final_answer == query:
            final_answer = response.strip()

        return DecompositionResult(
            original_query=query,
            sub_queries=sub_queries,
            final_answer=final_answer,
            confidence=confidence,
            reasoning=reasoning,
        )

    def decompose_and_answer(self, query: str) -> DecompositionResult:
        """
        Full pipeline: decompose, execute, synthesize.

        This is the main entry point.

        Args:
            query: Complex question to answer

        Returns:
            DecompositionResult with final synthesized answer
        """
        # Check if decomposition needed
        if not self.needs_decomposition(query):
            # Simple query - direct retrieval
            sources = self.retriever.retrieve(query, top_k=5)
            source_text = "\n".join(
                doc.get("content", doc.get("text", str(doc)))[:500] for doc in sources
            )

            prompt = f"""Answer this question based on the context.

Question: {query}
Context:
{source_text}

Answer:"""

            answer = self.llm.generate(prompt, max_tokens=300)

            return DecompositionResult(
                original_query=query,
                sub_queries=[
                    SubQuery(
                        query=query,
                        purpose="Direct answer",
                        answer=answer,
                        sources=sources,
                    )
                ],
                final_answer=answer,
                confidence=0.8,
                reasoning="Simple query - direct retrieval without decomposition",
            )

        # Complex query - full decomposition
        sub_queries = self.decompose(query)
        sub_queries = self.execute_sub_queries(sub_queries)
        return self.synthesize(query, sub_queries)


class ParallelQueryDecomposer(QueryDecomposer):
    """
    Query decomposer that executes independent sub-queries in parallel.

    For sub-queries without dependencies, executes them concurrently
    using asyncio or thread pool.
    """

    def __init__(
        self,
        llm: LLMClient,
        retriever: RetrieverProtocol,
        max_sub_queries: int = 5,
        min_confidence: float = 0.6,
        max_workers: int = 3,
    ):
        super().__init__(llm, retriever, max_sub_queries, min_confidence)
        self.max_workers = max_workers

    def execute_sub_queries(self, sub_queries: list[SubQuery]) -> list[SubQuery]:
        """Execute sub-queries with parallelism for independent queries."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Group by dependency level
        levels: list[list[int]] = []
        remaining = set(range(len(sub_queries)))
        processed: set[int] = set()

        while remaining:
            # Find queries whose dependencies are all processed
            ready = [
                i
                for i in remaining
                if all(d in processed for d in sub_queries[i].depends_on)
            ]
            if not ready:
                ready = list(remaining)  # Break cycles

            levels.append(ready)
            processed.update(ready)
            remaining -= set(ready)

        def execute_one(idx: int) -> SubQuery:
            """Execute a single sub-query."""
            sq = sub_queries[idx]

            # Build context from dependencies
            dep_context = ""
            for dep_idx in sq.depends_on:
                if dep_idx < len(sub_queries) and sub_queries[dep_idx].answer:
                    dep_context += f"\nContext: {sub_queries[dep_idx].answer}\n"

            sources = self.retriever.retrieve(sq.query, top_k=3)
            sq.sources = sources

            source_text = "\n".join(
                doc.get("content", doc.get("text", str(doc)))[:500] for doc in sources
            )

            prompt = f"""Answer concisely:
Question: {sq.query}
{dep_context}
Context: {source_text}

Answer:"""

            try:
                sq.answer = self.llm.generate(prompt, max_tokens=300)
            except Exception as e:
                sq.answer = f"Error: {e}"

            return sq

        # Execute level by level (parallel within level)
        for level in levels:
            with ThreadPoolExecutor(
                max_workers=min(self.max_workers, len(level))
            ) as executor:
                futures = {executor.submit(execute_one, idx): idx for idx in level}
                for future in as_completed(futures):
                    idx = futures[future]
                    sub_queries[idx] = future.result()

        return sub_queries
