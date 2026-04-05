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
Text2Cypher - Natural Language to Cypher Query Conversion.

This module provides LLM-powered conversion of natural language questions
into Cypher queries for Neo4j GraphRAG compatibility.

Features:
- Schema extraction from Neo4j (node labels, relationships, properties)
- Multi-backend LLM support (Claude, GPT, Ollama)
- Query validation before execution
- Query optimization (LIMIT, indexes, cartesian product prevention)
- Error recovery with refined prompts
- Few-shot domain examples
- Safety checks (prevents DELETE, DROP, destructive operations)

Usage:
    from agentic_brain.rag.text2cypher import Text2Cypher

    # Basic usage
    t2c = Text2Cypher(neo4j_uri="bolt://localhost:7687")
    result = await t2c.query("Find all users who bought products last week")

    # With specific LLM backend
    t2c = Text2Cypher(
        neo4j_uri="bolt://localhost:7687",
        llm_provider="claude",
        llm_model="claude-sonnet-4-20250514",
    )

    # Just generate query without execution
    cypher = await t2c.generate_cypher("Show me the top 10 customers by revenue")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class Text2CypherError(Exception):
    """Base exception for Text2Cypher errors."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.context = context or {}


class SchemaExtractionError(Text2CypherError):
    """Failed to extract schema from Neo4j."""


class CypherGenerationError(Text2CypherError):
    """Failed to generate Cypher from natural language."""


class CypherValidationError(Text2CypherError):
    """Generated Cypher failed validation."""


class CypherSafetyError(Text2CypherError):
    """Generated Cypher contains unsafe operations."""


class LLMProviderError(Text2CypherError):
    """LLM provider failed or is unavailable."""


# ---------------------------------------------------------------------------
# Enums and Types
# ---------------------------------------------------------------------------


class LLMProvider(Enum):
    """Supported LLM providers for query generation."""

    CLAUDE = "claude"
    OPENAI = "openai"
    OLLAMA = "ollama"
    GROQ = "groq"
    MOCK = "mock"  # For testing


class QueryComplexity(Enum):
    """Query complexity levels for optimization hints."""

    SIMPLE = "simple"  # Single node lookup
    MODERATE = "moderate"  # Single relationship traversal
    COMPLEX = "complex"  # Multi-hop, aggregations
    ADVANCED = "advanced"  # Subqueries, APOC, complex patterns


class SafetyLevel(Enum):
    """Safety levels for query execution."""

    STRICT = "strict"  # Read-only, no mutations
    NORMAL = "normal"  # Allow safe mutations (CREATE, MERGE)
    PERMISSIVE = "permissive"  # Allow all except DROP DATABASE


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class NodeLabel:
    """Schema information for a node label."""

    name: str
    count: int = 0
    properties: dict[str, str] = field(default_factory=dict)  # name -> type
    indexes: list[str] = field(default_factory=list)
    sample_values: dict[str, list[Any]] = field(default_factory=dict)


@dataclass
class RelationshipType:
    """Schema information for a relationship type."""

    name: str
    count: int = 0
    start_labels: list[str] = field(default_factory=list)
    end_labels: list[str] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class GraphSchema:
    """Complete Neo4j graph schema."""

    node_labels: dict[str, NodeLabel] = field(default_factory=dict)
    relationship_types: dict[str, RelationshipType] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def to_prompt_text(self) -> str:
        """Convert schema to text suitable for LLM prompt."""
        lines = ["## Graph Schema\n"]

        # Node labels
        lines.append("### Node Labels")
        for label, info in sorted(self.node_labels.items()):
            props = ", ".join(f"{k}: {v}" for k, v in info.properties.items())
            lines.append(f"- (:{label}) [{info.count} nodes] {{{props}}}")
            if info.indexes:
                lines.append(f"  Indexes: {', '.join(info.indexes)}")

        # Relationships
        lines.append("\n### Relationships")
        for rel_type, info in sorted(self.relationship_types.items()):
            starts = ", ".join(info.start_labels) or "Any"
            ends = ", ".join(info.end_labels) or "Any"
            props = ", ".join(f"{k}: {v}" for k, v in info.properties.items())
            lines.append(f"- (:{starts})-[:{rel_type}]->(:{ends}) [{info.count}] {{{props}}}")

        return "\n".join(lines)

    def get_property_type(self, label: str, prop: str) -> str | None:
        """Get property type for a node label."""
        if label in self.node_labels:
            return self.node_labels[label].properties.get(prop)
        return None


@dataclass
class FewShotExample:
    """A few-shot example for query generation."""

    question: str
    cypher: str
    explanation: str = ""
    complexity: QueryComplexity = QueryComplexity.SIMPLE


@dataclass
class GeneratedQuery:
    """Result of Cypher generation."""

    cypher: str
    natural_language: str
    explanation: str = ""
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    optimizations_applied: list[str] = field(default_factory=list)
    validation_passed: bool = True
    validation_errors: list[str] = field(default_factory=list)
    generation_time_ms: float = 0.0
    llm_provider: str = ""
    llm_model: str = ""
    retry_count: int = 0


@dataclass
class QueryResult:
    """Result of query execution."""

    query: GeneratedQuery
    records: list[dict[str, Any]] = field(default_factory=list)
    execution_time_ms: float = 0.0
    record_count: int = 0
    truncated: bool = False
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class Text2CypherConfig:
    """Configuration for Text2Cypher."""

    # Neo4j connection
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # LLM settings
    llm_provider: LLMProvider = LLMProvider.CLAUDE
    llm_model: str = ""  # Empty = use provider default
    llm_api_key: str = ""  # Empty = use environment variable
    llm_temperature: float = 0.0  # Deterministic for Cypher generation
    llm_timeout: float = 30.0

    # Query settings
    safety_level: SafetyLevel = SafetyLevel.STRICT
    max_results: int = 100
    default_limit: int = 25
    query_timeout: float = 30.0

    # Schema caching
    schema_cache_ttl: int = 3600  # 1 hour
    include_property_samples: bool = True
    max_sample_values: int = 5

    # Error recovery
    max_retries: int = 3
    retry_with_schema_refresh: bool = True

    # Optimization
    auto_add_limit: bool = True
    prefer_indexed_properties: bool = True
    prevent_cartesian_products: bool = True


# ---------------------------------------------------------------------------
# LLM Provider Protocol
# ---------------------------------------------------------------------------


class LLMBackend(Protocol):
    """Protocol for LLM backends."""

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text from prompt."""
        ...


# ---------------------------------------------------------------------------
# Default Few-Shot Examples
# ---------------------------------------------------------------------------

DEFAULT_FEW_SHOT_EXAMPLES: list[FewShotExample] = [
    FewShotExample(
        question="Find all users",
        cypher="MATCH (u:User) RETURN u LIMIT 25",
        explanation="Simple node match with default limit",
        complexity=QueryComplexity.SIMPLE,
    ),
    FewShotExample(
        question="How many products are there?",
        cypher="MATCH (p:Product) RETURN count(p) AS product_count",
        explanation="Count aggregation on single label",
        complexity=QueryComplexity.SIMPLE,
    ),
    FewShotExample(
        question="Find users who bought products in the last week",
        cypher="""MATCH (u:User)-[p:PURCHASED]->(prod:Product)
WHERE p.date >= datetime() - duration('P7D')
RETURN u.name AS user, collect(prod.name) AS products
LIMIT 25""",
        explanation="Relationship traversal with date filter and aggregation",
        complexity=QueryComplexity.MODERATE,
    ),
    FewShotExample(
        question="What are the top 10 customers by total order value?",
        cypher="""MATCH (c:Customer)-[:PLACED]->(o:Order)
RETURN c.name AS customer, sum(o.total) AS total_spent
ORDER BY total_spent DESC
LIMIT 10""",
        explanation="Aggregation with ordering",
        complexity=QueryComplexity.MODERATE,
    ),
    FewShotExample(
        question="Find products that are frequently bought together",
        cypher="""MATCH (p1:Product)<-[:CONTAINS]-(o:Order)-[:CONTAINS]->(p2:Product)
WHERE id(p1) < id(p2)
RETURN p1.name AS product1, p2.name AS product2, count(o) AS times_bought_together
ORDER BY times_bought_together DESC
LIMIT 20""",
        explanation="Co-occurrence pattern with deduplication",
        complexity=QueryComplexity.COMPLEX,
    ),
    FewShotExample(
        question="Find the shortest path between two users",
        cypher="""MATCH path = shortestPath((u1:User {name: $user1})-[*..6]-(u2:User {name: $user2}))
RETURN path, length(path) AS distance""",
        explanation="Shortest path with variable length relationship",
        complexity=QueryComplexity.COMPLEX,
    ),
    FewShotExample(
        question="Get all nodes connected to a specific node within 2 hops",
        cypher="""MATCH (start:Entity {id: $id})-[*1..2]-(connected)
RETURN DISTINCT labels(connected) AS type, connected
LIMIT 50""",
        explanation="Multi-hop exploration with distinct",
        complexity=QueryComplexity.MODERATE,
    ),
    FewShotExample(
        question="Find users with no orders",
        cypher="""MATCH (u:User)
WHERE NOT (u)-[:PLACED]->(:Order)
RETURN u.name AS user_without_orders
LIMIT 25""",
        explanation="Negative pattern match",
        complexity=QueryComplexity.MODERATE,
    ),
]


# ---------------------------------------------------------------------------
# Unsafe Query Patterns
# ---------------------------------------------------------------------------

UNSAFE_PATTERNS_STRICT: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bDELETE\b", re.IGNORECASE), "DELETE operations not allowed"),
    (re.compile(r"\bDETACH\s+DELETE\b", re.IGNORECASE), "DETACH DELETE not allowed"),
    (re.compile(r"\bDROP\b", re.IGNORECASE), "DROP operations not allowed"),
    (re.compile(r"\bCREATE\b", re.IGNORECASE), "CREATE operations not allowed in strict mode"),
    (re.compile(r"\bMERGE\b", re.IGNORECASE), "MERGE operations not allowed in strict mode"),
    (re.compile(r"\bSET\b", re.IGNORECASE), "SET operations not allowed in strict mode"),
    (re.compile(r"\bREMOVE\b", re.IGNORECASE), "REMOVE operations not allowed"),
    (re.compile(r"\bCALL\s+\{", re.IGNORECASE), "Subqueries with CALL not allowed"),
    (re.compile(r"\bCALL\s+apoc\.", re.IGNORECASE), "APOC procedures not allowed"),
    (re.compile(r"\bCALL\s+dbms\.", re.IGNORECASE), "DBMS procedures not allowed"),
    (re.compile(r"\bCALL\s+db\.(index|constraint)", re.IGNORECASE), "Schema modifications not allowed"),
    (re.compile(r";\s*\w", re.IGNORECASE), "Multiple statements not allowed"),
]

UNSAFE_PATTERNS_NORMAL: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bDELETE\b", re.IGNORECASE), "DELETE operations not allowed"),
    (re.compile(r"\bDETACH\s+DELETE\b", re.IGNORECASE), "DETACH DELETE not allowed"),
    (re.compile(r"\bDROP\b", re.IGNORECASE), "DROP operations not allowed"),
    (re.compile(r"\bREMOVE\b", re.IGNORECASE), "REMOVE operations not allowed"),
    (re.compile(r"\bCALL\s+dbms\.", re.IGNORECASE), "DBMS procedures not allowed"),
    (re.compile(r"\bCALL\s+db\.(index|constraint)", re.IGNORECASE), "Schema modifications not allowed"),
    (re.compile(r";\s*\w", re.IGNORECASE), "Multiple statements not allowed"),
]

UNSAFE_PATTERNS_PERMISSIVE: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "DROP DATABASE not allowed"),
    (re.compile(r"\bCALL\s+dbms\.security", re.IGNORECASE), "Security procedures not allowed"),
    (re.compile(r";\s*\w", re.IGNORECASE), "Multiple statements not allowed"),
]


# ---------------------------------------------------------------------------
# Cypher Validation
# ---------------------------------------------------------------------------


def validate_cypher_syntax(cypher: str) -> tuple[bool, list[str]]:
    """
    Basic Cypher syntax validation without Neo4j connection.

    Returns (is_valid, list of errors).
    """
    errors: list[str] = []

    # Check for balanced parentheses and brackets
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}

    for i, char in enumerate(cypher):
        if char in pairs:
            stack.append(char)
        elif char in pairs.values():
            if not stack:
                errors.append(f"Unmatched closing '{char}' at position {i}")
            elif pairs.get(stack[-1]) != char:
                errors.append(f"Mismatched bracket at position {i}")
            else:
                stack.pop()

    if stack:
        errors.append(f"Unclosed brackets: {stack}")

    # Check for common syntax issues
    if re.search(r"\bMATCH\b.*\bMATCH\b", cypher, re.IGNORECASE) and not re.search(
        r"\b(WITH|OPTIONAL|UNION)\b", cypher, re.IGNORECASE
    ):
        errors.append("Multiple MATCH clauses should be connected with WITH or OPTIONAL MATCH")

    # Check RETURN clause exists (unless it's a write-only query)
    if not re.search(r"\bRETURN\b", cypher, re.IGNORECASE):
        if not any(
            re.search(rf"\b{kw}\b", cypher, re.IGNORECASE)
            for kw in ["CREATE", "DELETE", "MERGE", "SET", "REMOVE"]
        ):
            errors.append("Query must have a RETURN clause")

    # Check for incomplete patterns
    if re.search(r"\(\s*\)", cypher):
        errors.append("Empty node pattern () should specify a label or variable")

    # Check relationship patterns
    if re.search(r"\[\s*\]", cypher) and not re.search(r"\[\s*\*", cypher):
        errors.append("Empty relationship pattern [] should specify a type or variable")

    return len(errors) == 0, errors


def validate_cypher_semantics(cypher: str, schema: GraphSchema) -> tuple[bool, list[str]]:
    """
    Semantic validation against schema.

    Returns (is_valid, list of errors).
    """
    errors: list[str] = []

    # Extract node labels from query
    label_pattern = re.compile(r"\(:(\w+)(?:\s*\{[^}]*\})?\)")
    query_labels = set(label_pattern.findall(cypher))

    # Check if labels exist in schema
    for label in query_labels:
        if label not in schema.node_labels:
            errors.append(f"Unknown node label: {label}")

    # Extract relationship types from query
    rel_pattern = re.compile(r"\[:(\w+)(?:\s*\{[^}]*\})?\]")
    query_rels = set(rel_pattern.findall(cypher))

    # Check if relationship types exist
    for rel in query_rels:
        if rel not in schema.relationship_types:
            errors.append(f"Unknown relationship type: {rel}")

    # Check property access
    prop_pattern = re.compile(r"(\w+)\.(\w+)")
    for var, prop in prop_pattern.findall(cypher):
        # We can't easily validate without knowing variable types
        # This would require more sophisticated parsing
        pass

    return len(errors) == 0, errors


def check_cartesian_product(cypher: str) -> tuple[bool, str]:
    """
    Check if query might produce a cartesian product.

    Returns (has_cartesian, warning message).
    """
    # Count distinct node patterns
    node_patterns = re.findall(r"\((\w+):\w+\)", cypher)

    # Check if there are multiple unconnected MATCH clauses
    matches = re.findall(r"\bMATCH\b\s*(.+?)(?=\bMATCH\b|\bWHERE\b|\bRETURN\b|\bWITH\b|$)", cypher, re.IGNORECASE | re.DOTALL)

    if len(matches) > 1:
        # Check if patterns are connected via relationships or WHERE clauses
        for match in matches:
            if not re.search(r"[\-\<\>]", match):  # No relationship syntax
                return True, "Multiple MATCH clauses without relationships may cause cartesian product"

    return False, ""


# ---------------------------------------------------------------------------
# Query Optimization
# ---------------------------------------------------------------------------


def optimize_query(
    cypher: str,
    schema: GraphSchema,
    config: Text2CypherConfig,
) -> tuple[str, list[str]]:
    """
    Optimize a Cypher query.

    Returns (optimized_query, list of optimizations applied).
    """
    optimizations: list[str] = []
    result = cypher

    # Add LIMIT if missing and configured
    if config.auto_add_limit and not re.search(r"\bLIMIT\b", result, re.IGNORECASE):
        # Don't add LIMIT to count() queries
        if not re.search(r"\bcount\s*\(", result, re.IGNORECASE):
            result = result.rstrip().rstrip(";") + f"\nLIMIT {config.default_limit}"
            optimizations.append(f"Added LIMIT {config.default_limit}")

    # Check for indexed property usage
    if config.prefer_indexed_properties:
        # Find WHERE clauses with property comparisons
        where_match = re.search(r"\bWHERE\b(.+?)(?=\bRETURN\b|\bWITH\b|\bORDER\b|$)", result, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            # Check if using indexed properties
            prop_comparisons = re.findall(r"(\w+)\.(\w+)\s*=", where_clause)
            for var, prop in prop_comparisons:
                for label_info in schema.node_labels.values():
                    if prop in label_info.indexes:
                        optimizations.append(f"Query uses indexed property: {prop}")
                        break

    # Prevent cartesian products
    if config.prevent_cartesian_products:
        has_cartesian, warning = check_cartesian_product(result)
        if has_cartesian:
            optimizations.append(f"WARNING: {warning}")

    # Add USING INDEX hint for known indexes
    # This is a more advanced optimization we could add

    return result, optimizations


# ---------------------------------------------------------------------------
# LLM Backends
# ---------------------------------------------------------------------------


class ClaudeLLMBackend:
    """Claude LLM backend using Anthropic API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise LLMProviderError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        client = await self._get_client()

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system or "You are a Cypher query expert for Neo4j.",
                    messages=messages,
                ),
                timeout=self.timeout,
            )
            return response.content[0].text
        except asyncio.TimeoutError:
            raise LLMProviderError(f"Claude request timed out after {self.timeout}s")
        except Exception as e:
            raise LLMProviderError(f"Claude API error: {e}", context={"error": str(e)})


class OpenAILLMBackend:
    """OpenAI LLM backend."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise LLMProviderError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        client = await self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self.timeout,
            )
            return response.choices[0].message.content or ""
        except asyncio.TimeoutError:
            raise LLMProviderError(f"OpenAI request timed out after {self.timeout}s")
        except Exception as e:
            raise LLMProviderError(f"OpenAI API error: {e}", context={"error": str(e)})


class OllamaLLMBackend:
    """Ollama local LLM backend."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: float = 60.0,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        try:
            import aiohttp
        except ImportError:
            raise LLMProviderError("aiohttp package not installed. Run: pip install aiohttp")

        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.host}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise LLMProviderError(f"Ollama error {response.status}: {text}")
                    data = await response.json()
                    return data.get("response", "")
        except asyncio.TimeoutError:
            raise LLMProviderError(f"Ollama request timed out after {self.timeout}s")
        except aiohttp.ClientError as e:
            raise LLMProviderError(f"Ollama connection error: {e}")


class GroqLLMBackend:
    """Groq LLM backend (ultra-fast inference)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        try:
            import aiohttp
        except ImportError:
            raise LLMProviderError("aiohttp package not installed")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise LLMProviderError(f"Groq error {response.status}: {text}")
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
        except asyncio.TimeoutError:
            raise LLMProviderError(f"Groq request timed out after {self.timeout}s")


class MockLLMBackend:
    """Mock LLM backend for testing."""

    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        self.calls.append({
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })

        # Check for matching response
        for key, response in self.responses.items():
            if key.lower() in prompt.lower():
                return response

        # Default response
        return "MATCH (n) RETURN n LIMIT 10"


# ---------------------------------------------------------------------------
# Schema Extractor
# ---------------------------------------------------------------------------


class SchemaExtractor:
    """Extracts schema information from Neo4j."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver: Any = None

    async def _get_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import AsyncGraphDatabase

                self._driver = AsyncGraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                )
            except ImportError:
                raise SchemaExtractionError(
                    "neo4j package not installed. Run: pip install neo4j"
                )
        return self._driver

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def extract_schema(
        self,
        include_samples: bool = True,
        max_samples: int = 5,
    ) -> GraphSchema:
        """Extract complete schema from Neo4j."""
        driver = await self._get_driver()

        schema = GraphSchema()

        async with driver.session(database=self.database) as session:
            # Get node labels with counts
            result = await session.run(
                "CALL db.labels() YIELD label "
                "CALL { WITH label MATCH (n) WHERE label IN labels(n) RETURN count(n) AS cnt } "
                "RETURN label, cnt"
            )
            records = [record async for record in result]

            for record in records:
                label = record["label"]
                count = record["cnt"]
                schema.node_labels[label] = NodeLabel(name=label, count=count)

            # Get properties for each label
            for label in schema.node_labels:
                try:
                    result = await session.run(
                        f"MATCH (n:{label}) "
                        "UNWIND keys(n) AS key "
                        "WITH key, n[key] AS value "
                        "RETURN DISTINCT key, "
                        "CASE "
                        "  WHEN value IS NULL THEN 'null' "
                        "  WHEN toInteger(value) = value THEN 'integer' "
                        "  WHEN toFloat(value) = value THEN 'float' "
                        "  WHEN value = true OR value = false THEN 'boolean' "
                        "  WHEN datetime(value) IS NOT NULL THEN 'datetime' "
                        "  ELSE 'string' "
                        "END AS type "
                        "LIMIT 100"
                    )
                    records = [record async for record in result]

                    for record in records:
                        schema.node_labels[label].properties[record["key"]] = record["type"]

                    # Get sample values if requested
                    if include_samples:
                        for prop in list(schema.node_labels[label].properties.keys())[:3]:
                            try:
                                result = await session.run(
                                    f"MATCH (n:{label}) "
                                    f"WHERE n.{prop} IS NOT NULL "
                                    f"RETURN DISTINCT n.{prop} AS value "
                                    f"LIMIT {max_samples}"
                                )
                                samples = [record["value"] async for record in result]
                                schema.node_labels[label].sample_values[prop] = samples
                            except Exception:
                                pass  # Skip on error

                except Exception as e:
                    logger.warning(f"Failed to get properties for {label}: {e}")

            # Get relationship types with counts
            result = await session.run(
                "CALL db.relationshipTypes() YIELD relationshipType "
                "CALL { WITH relationshipType "
                "  MATCH ()-[r]->() WHERE type(r) = relationshipType "
                "  RETURN count(r) AS cnt "
                "} "
                "RETURN relationshipType, cnt"
            )
            records = [record async for record in result]

            for record in records:
                rel_type = record["relationshipType"]
                count = record["cnt"]
                schema.relationship_types[rel_type] = RelationshipType(
                    name=rel_type, count=count
                )

            # Get relationship endpoints
            for rel_type in schema.relationship_types:
                try:
                    result = await session.run(
                        f"MATCH (s)-[r:{rel_type}]->(e) "
                        "RETURN DISTINCT labels(s) AS start_labels, labels(e) AS end_labels "
                        "LIMIT 10"
                    )
                    records = [record async for record in result]

                    start_labels: set[str] = set()
                    end_labels: set[str] = set()

                    for record in records:
                        start_labels.update(record["start_labels"])
                        end_labels.update(record["end_labels"])

                    schema.relationship_types[rel_type].start_labels = list(start_labels)
                    schema.relationship_types[rel_type].end_labels = list(end_labels)

                except Exception as e:
                    logger.warning(f"Failed to get endpoints for {rel_type}: {e}")

            # Get indexes
            try:
                result = await session.run("SHOW INDEXES")
                records = [record async for record in result]

                for record in records:
                    idx_name = record.get("name", "")
                    labels = record.get("labelsOrTypes", [])
                    properties = record.get("properties", [])

                    schema.indexes.append(f"{idx_name}: {labels} on {properties}")

                    # Track which properties are indexed
                    for label in labels:
                        if label in schema.node_labels:
                            schema.node_labels[label].indexes.extend(properties)

            except Exception as e:
                logger.warning(f"Failed to get indexes: {e}")

            # Get constraints
            try:
                result = await session.run("SHOW CONSTRAINTS")
                records = [record async for record in result]

                for record in records:
                    constraint_name = record.get("name", "")
                    schema.constraints.append(constraint_name)

            except Exception as e:
                logger.warning(f"Failed to get constraints: {e}")

        schema.extracted_at = datetime.utcnow()
        return schema


# ---------------------------------------------------------------------------
# Text2Cypher Main Class
# ---------------------------------------------------------------------------


class Text2Cypher:
    """
    Natural Language to Cypher Query Converter.

    Converts natural language questions into Cypher queries using LLMs,
    with schema awareness, validation, optimization, and safety checks.
    """

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str | None = None,
        neo4j_database: str = "neo4j",
        llm_provider: str | LLMProvider = LLMProvider.CLAUDE,
        llm_model: str = "",
        llm_api_key: str = "",
        safety_level: str | SafetyLevel = SafetyLevel.STRICT,
        config: Text2CypherConfig | None = None,
    ):
        """
        Initialize Text2Cypher.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password (or from NEO4J_PASSWORD env)
            neo4j_database: Neo4j database name
            llm_provider: LLM provider to use (claude, openai, ollama, groq)
            llm_model: Specific model to use (empty = provider default)
            llm_api_key: API key (or from environment)
            safety_level: Safety level for query validation
            config: Full configuration object (overrides other params)
        """
        if config:
            self.config = config
        else:
            self.config = Text2CypherConfig(
                neo4j_uri=neo4j_uri,
                neo4j_user=neo4j_user,
                neo4j_password=neo4j_password or os.getenv("NEO4J_PASSWORD", ""),
                neo4j_database=neo4j_database,
                llm_provider=LLMProvider(llm_provider) if isinstance(llm_provider, str) else llm_provider,
                llm_model=llm_model,
                llm_api_key=llm_api_key,
                safety_level=SafetyLevel(safety_level) if isinstance(safety_level, str) else safety_level,
            )

        # Initialize components
        self._schema_extractor = SchemaExtractor(
            uri=self.config.neo4j_uri,
            user=self.config.neo4j_user,
            password=self.config.neo4j_password,
            database=self.config.neo4j_database,
        )
        self._llm: LLMBackend | None = None
        self._schema: GraphSchema | None = None
        self._schema_cache_time: datetime | None = None
        self._few_shot_examples: list[FewShotExample] = list(DEFAULT_FEW_SHOT_EXAMPLES)
        self._driver: Any = None

    def _get_llm_backend(self) -> LLMBackend:
        """Get or create LLM backend."""
        if self._llm is not None:
            return self._llm

        provider = self.config.llm_provider
        api_key = self.config.llm_api_key
        model = self.config.llm_model
        timeout = self.config.llm_timeout

        if provider == LLMProvider.CLAUDE:
            self._llm = ClaudeLLMBackend(
                api_key=api_key or None,
                model=model or "claude-sonnet-4-20250514",
                timeout=timeout,
            )
        elif provider == LLMProvider.OPENAI:
            self._llm = OpenAILLMBackend(
                api_key=api_key or None,
                model=model or "gpt-4o",
                timeout=timeout,
            )
        elif provider == LLMProvider.OLLAMA:
            self._llm = OllamaLLMBackend(
                model=model or "llama3.2",
                timeout=timeout,
            )
        elif provider == LLMProvider.GROQ:
            self._llm = GroqLLMBackend(
                api_key=api_key or None,
                model=model or "llama-3.3-70b-versatile",
                timeout=timeout,
            )
        elif provider == LLMProvider.MOCK:
            self._llm = MockLLMBackend()
        else:
            raise LLMProviderError(f"Unknown LLM provider: {provider}")

        return self._llm

    def set_llm_backend(self, backend: LLMBackend) -> None:
        """Set a custom LLM backend (useful for testing)."""
        self._llm = backend

    async def _get_driver(self) -> Any:
        """Get Neo4j driver for query execution."""
        if self._driver is None:
            try:
                from neo4j import AsyncGraphDatabase

                self._driver = AsyncGraphDatabase.driver(
                    self.config.neo4j_uri,
                    auth=(self.config.neo4j_user, self.config.neo4j_password),
                )
            except ImportError:
                raise Text2CypherError("neo4j package not installed")
        return self._driver

    async def close(self) -> None:
        """Close all connections."""
        await self._schema_extractor.close()
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def get_schema(self, force_refresh: bool = False) -> GraphSchema:
        """
        Get graph schema (cached).

        Args:
            force_refresh: Force schema re-extraction

        Returns:
            GraphSchema object
        """
        now = datetime.utcnow()

        if (
            not force_refresh
            and self._schema is not None
            and self._schema_cache_time is not None
        ):
            age = (now - self._schema_cache_time).total_seconds()
            if age < self.config.schema_cache_ttl:
                return self._schema

        self._schema = await self._schema_extractor.extract_schema(
            include_samples=self.config.include_property_samples,
            max_samples=self.config.max_sample_values,
        )
        self._schema_cache_time = now
        return self._schema

    def add_few_shot_example(self, example: FewShotExample) -> None:
        """Add a domain-specific few-shot example."""
        self._few_shot_examples.append(example)

    def add_few_shot_examples(self, examples: list[FewShotExample]) -> None:
        """Add multiple domain-specific few-shot examples."""
        self._few_shot_examples.extend(examples)

    def clear_few_shot_examples(self) -> None:
        """Clear all few-shot examples (including defaults)."""
        self._few_shot_examples.clear()

    def reset_few_shot_examples(self) -> None:
        """Reset to default few-shot examples."""
        self._few_shot_examples = list(DEFAULT_FEW_SHOT_EXAMPLES)

    def _build_prompt(
        self,
        question: str,
        schema: GraphSchema,
        error_context: str | None = None,
    ) -> str:
        """Build the LLM prompt for Cypher generation."""
        parts: list[str] = []

        # Schema section
        parts.append(schema.to_prompt_text())

        # Few-shot examples
        parts.append("\n## Examples\n")
        for example in self._few_shot_examples[:8]:  # Limit to 8 examples
            parts.append(f"Question: {example.question}")
            parts.append(f"Cypher: {example.cypher}")
            if example.explanation:
                parts.append(f"Explanation: {example.explanation}")
            parts.append("")

        # Error context for retry
        if error_context:
            parts.append(f"\n## Previous Attempt Failed\n{error_context}\nPlease fix the query.\n")

        # The actual question
        parts.append(f"\n## Question\n{question}")

        # Instructions
        parts.append("""
## Instructions
Generate a valid Cypher query for the question above.
- Use only labels and relationships from the schema
- Include LIMIT clause for result control
- Use parameterized values where appropriate (e.g., $param_name)
- Return only the Cypher query, no explanation
- Do NOT include any markdown code blocks
""")

        return "\n".join(parts)

    def _extract_cypher(self, llm_response: str) -> str:
        """Extract Cypher query from LLM response."""
        response = llm_response.strip()

        # Remove markdown code blocks
        if "```" in response:
            # Find cypher or generic code block
            patterns = [
                r"```cypher\s*(.*?)\s*```",
                r"```sql\s*(.*?)\s*```",
                r"```\s*(.*?)\s*```",
            ]
            for pattern in patterns:
                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip()

        # If no code blocks, assume the whole response is the query
        # But remove any leading/trailing explanation
        lines = response.split("\n")
        cypher_lines: list[str] = []
        in_cypher = False

        for line in lines:
            stripped = line.strip()
            # Start of Cypher (common keywords)
            if any(
                stripped.upper().startswith(kw)
                for kw in ["MATCH", "OPTIONAL", "CREATE", "MERGE", "WITH", "CALL", "RETURN", "UNWIND"]
            ):
                in_cypher = True

            if in_cypher:
                # End of Cypher (explanatory text)
                if stripped.startswith(("//", "#", "Note:", "Explanation:", "This query")):
                    break
                cypher_lines.append(line)

        if cypher_lines:
            return "\n".join(cypher_lines).strip()

        return response

    def _check_safety(self, cypher: str) -> tuple[bool, list[str]]:
        """
        Check query against safety rules.

        Returns (is_safe, list of violations).
        """
        violations: list[str] = []

        if self.config.safety_level == SafetyLevel.STRICT:
            patterns = UNSAFE_PATTERNS_STRICT
        elif self.config.safety_level == SafetyLevel.NORMAL:
            patterns = UNSAFE_PATTERNS_NORMAL
        else:
            patterns = UNSAFE_PATTERNS_PERMISSIVE

        for pattern, message in patterns:
            if pattern.search(cypher):
                violations.append(message)

        return len(violations) == 0, violations

    async def generate_cypher(
        self,
        question: str,
        *,
        validate: bool = True,
        optimize: bool = True,
    ) -> GeneratedQuery:
        """
        Generate Cypher query from natural language.

        Args:
            question: Natural language question
            validate: Whether to validate the generated query
            optimize: Whether to optimize the query

        Returns:
            GeneratedQuery object with the generated Cypher

        Raises:
            CypherGenerationError: If generation fails after retries
            CypherSafetyError: If generated query violates safety rules
        """
        import time

        start_time = time.time()

        # Get schema
        schema = await self.get_schema()

        # Get LLM backend
        llm = self._get_llm_backend()

        # Generate with retries
        last_error: str | None = None
        generated_cypher: str = ""

        for attempt in range(self.config.max_retries):
            try:
                # Build prompt
                prompt = self._build_prompt(question, schema, last_error)

                # Generate
                system_prompt = (
                    "You are a Neo4j Cypher expert. Generate precise, efficient Cypher queries. "
                    "Output only the Cypher query without explanation or markdown."
                )

                response = await llm.generate(
                    prompt,
                    system=system_prompt,
                    temperature=self.config.llm_temperature,
                )

                # Extract Cypher
                generated_cypher = self._extract_cypher(response)

                if not generated_cypher:
                    last_error = "Empty query generated"
                    continue

                # Safety check
                is_safe, violations = self._check_safety(generated_cypher)
                if not is_safe:
                    raise CypherSafetyError(
                        f"Query violates safety rules: {', '.join(violations)}",
                        context={"cypher": generated_cypher, "violations": violations},
                    )

                # Validate
                validation_errors: list[str] = []
                if validate:
                    syntax_ok, syntax_errors = validate_cypher_syntax(generated_cypher)
                    if not syntax_ok:
                        validation_errors.extend(syntax_errors)
                        last_error = f"Syntax errors: {', '.join(syntax_errors)}"
                        continue

                    semantic_ok, semantic_errors = validate_cypher_semantics(generated_cypher, schema)
                    if not semantic_ok:
                        validation_errors.extend(semantic_errors)
                        # Semantic errors are warnings, not failures

                # Optimize
                optimizations: list[str] = []
                if optimize:
                    generated_cypher, optimizations = optimize_query(
                        generated_cypher, schema, self.config
                    )

                # Success
                elapsed = (time.time() - start_time) * 1000

                return GeneratedQuery(
                    cypher=generated_cypher,
                    natural_language=question,
                    explanation="",
                    complexity=self._estimate_complexity(generated_cypher),
                    optimizations_applied=optimizations,
                    validation_passed=len(validation_errors) == 0,
                    validation_errors=validation_errors,
                    generation_time_ms=elapsed,
                    llm_provider=self.config.llm_provider.value,
                    llm_model=self.config.llm_model or "default",
                    retry_count=attempt,
                )

            except CypherSafetyError:
                raise
            except Exception as e:
                last_error = str(e)
                if attempt == self.config.max_retries - 1:
                    raise CypherGenerationError(
                        f"Failed to generate Cypher after {self.config.max_retries} attempts: {last_error}",
                        context={"question": question, "last_error": last_error},
                    )

                # Refresh schema on retry if configured
                if self.config.retry_with_schema_refresh:
                    schema = await self.get_schema(force_refresh=True)

        # Should not reach here
        raise CypherGenerationError("Unexpected generation failure")

    def _estimate_complexity(self, cypher: str) -> QueryComplexity:
        """Estimate query complexity."""
        cypher_upper = cypher.upper()

        # Count complexity indicators
        score = 0

        # Multiple MATCH clauses
        score += cypher_upper.count("MATCH") - 1

        # Variable length paths
        if re.search(r"\[\*", cypher):
            score += 2

        # Subqueries
        if "CALL {" in cypher_upper:
            score += 2

        # Aggregations
        if any(agg in cypher_upper for agg in ["COUNT(", "SUM(", "AVG(", "COLLECT("]):
            score += 1

        # ORDER BY + LIMIT (not complex, but worth noting)
        if "ORDER BY" in cypher_upper:
            score += 0.5

        # APOC calls
        if "APOC." in cypher_upper:
            score += 2

        # Shortest path
        if "SHORTESTPATH" in cypher_upper:
            score += 2

        # WHERE with multiple conditions
        where_match = re.search(r"\bWHERE\b(.+?)(?=\bRETURN\b|\bWITH\b|\bORDER\b|$)", cypher, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            score += where_clause.count(" AND ") * 0.5
            score += where_clause.count(" OR ") * 0.5

        if score <= 0:
            return QueryComplexity.SIMPLE
        elif score <= 2:
            return QueryComplexity.MODERATE
        elif score <= 4:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED

    async def query(
        self,
        question: str,
        *,
        params: dict[str, Any] | None = None,
        validate: bool = True,
        optimize: bool = True,
    ) -> QueryResult:
        """
        Generate and execute Cypher query from natural language.

        Args:
            question: Natural language question
            params: Optional query parameters
            validate: Whether to validate the generated query
            optimize: Whether to optimize the query

        Returns:
            QueryResult with records and metadata
        """
        import time

        # Generate query
        generated = await self.generate_cypher(question, validate=validate, optimize=optimize)

        # Execute
        driver = await self._get_driver()
        start_time = time.time()

        try:
            async with driver.session(database=self.config.neo4j_database) as session:
                result = await session.run(
                    generated.cypher,
                    params or {},
                )
                records = [dict(record) async for record in result]

                elapsed = (time.time() - start_time) * 1000

                # Check if truncated
                truncated = len(records) >= self.config.max_results

                return QueryResult(
                    query=generated,
                    records=records[: self.config.max_results],
                    execution_time_ms=elapsed,
                    record_count=len(records),
                    truncated=truncated,
                )

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return QueryResult(
                query=generated,
                execution_time_ms=elapsed,
                error=str(e),
            )

    async def explain_query(self, question: str) -> str:
        """
        Generate and explain the Cypher query.

        Returns natural language explanation of what the query does.
        """
        generated = await self.generate_cypher(question)

        llm = self._get_llm_backend()

        prompt = f"""Explain this Cypher query in plain English:

```cypher
{generated.cypher}
```

Provide a brief, clear explanation of:
1. What data the query retrieves
2. How it traverses the graph
3. Any filtering or aggregation applied
"""

        explanation = await llm.generate(
            prompt,
            system="You are a helpful assistant explaining database queries to non-technical users.",
            temperature=0.3,
        )

        return explanation

    async def suggest_queries(
        self,
        context: str = "",
        num_suggestions: int = 5,
    ) -> list[str]:
        """
        Suggest natural language queries based on the schema.

        Args:
            context: Optional context to guide suggestions
            num_suggestions: Number of suggestions to generate

        Returns:
            List of suggested questions
        """
        schema = await self.get_schema()
        llm = self._get_llm_backend()

        prompt = f"""{schema.to_prompt_text()}

Based on this graph schema, suggest {num_suggestions} useful natural language questions
that could be answered by querying this graph.

{f"Context: {context}" if context else ""}

Return only the questions, one per line, without numbering.
"""

        response = await llm.generate(
            prompt,
            system="You are a data analyst suggesting useful queries for a graph database.",
            temperature=0.7,
        )

        # Parse suggestions
        lines = response.strip().split("\n")
        suggestions = [
            line.strip().lstrip("0123456789.-) ")
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]

        return suggestions[:num_suggestions]


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------


async def text_to_cypher(
    question: str,
    *,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str | None = None,
    llm_provider: str = "claude",
) -> str:
    """
    Quick conversion of natural language to Cypher.

    Args:
        question: Natural language question
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        llm_provider: LLM provider (claude, openai, ollama, groq)

    Returns:
        Generated Cypher query string
    """
    t2c = Text2Cypher(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        llm_provider=llm_provider,
    )

    try:
        result = await t2c.generate_cypher(question)
        return result.cypher
    finally:
        await t2c.close()


async def ask_graph(
    question: str,
    *,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str | None = None,
    llm_provider: str = "claude",
) -> list[dict[str, Any]]:
    """
    Ask a question and get results from the graph.

    Args:
        question: Natural language question
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        llm_provider: LLM provider

    Returns:
        List of result records
    """
    t2c = Text2Cypher(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        llm_provider=llm_provider,
    )

    try:
        result = await t2c.query(question)
        if result.error:
            raise Text2CypherError(result.error)
        return result.records
    finally:
        await t2c.close()


__all__ = [
    # Main class
    "Text2Cypher",
    "Text2CypherConfig",
    # Data classes
    "GraphSchema",
    "NodeLabel",
    "RelationshipType",
    "FewShotExample",
    "GeneratedQuery",
    "QueryResult",
    # Enums
    "LLMProvider",
    "QueryComplexity",
    "SafetyLevel",
    # Exceptions
    "Text2CypherError",
    "SchemaExtractionError",
    "CypherGenerationError",
    "CypherValidationError",
    "CypherSafetyError",
    "LLMProviderError",
    # Validation functions
    "validate_cypher_syntax",
    "validate_cypher_semantics",
    "check_cartesian_product",
    "optimize_query",
    # LLM backends
    "ClaudeLLMBackend",
    "OpenAILLMBackend",
    "OllamaLLMBackend",
    "GroqLLMBackend",
    "MockLLMBackend",
    # Schema extraction
    "SchemaExtractor",
    # Convenience functions
    "text_to_cypher",
    "ask_graph",
    # Default examples
    "DEFAULT_FEW_SHOT_EXAMPLES",
]
