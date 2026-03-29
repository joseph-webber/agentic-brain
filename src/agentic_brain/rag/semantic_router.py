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

"""Semantic Router for intelligent query routing.

Routes queries to appropriate handlers based on semantic understanding,
not just keywords. Uses embeddings to match query intent to routes.

Example:
    from agentic_brain.rag.semantic_router import SemanticRouter, Route

    router = SemanticRouter()

    # Define routes with example utterances
    router.add_route(Route(
        name="technical",
        description="Technical coding questions",
        examples=[
            "How do I fix this bug?",
            "What's the best way to implement X?",
            "Why is this code failing?",
        ],
        handler=handle_technical_query,
    ))

    router.add_route(Route(
        name="business",
        description="Business and project questions",
        examples=[
            "What's the status of project X?",
            "When is the deadline?",
            "Who is working on this?",
        ],
        handler=handle_business_query,
    ))

    # Route a query
    result = router.route("How do I connect to the database?")
    # -> Routes to 'technical' handler based on semantic similarity
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A semantic route definition."""

    name: str
    description: str
    examples: list[str]
    handler: Optional[Callable[[str], Any]] = None
    threshold: float = 0.5  # Minimum similarity to match
    metadata: dict[str, Any] = field(default_factory=dict)

    # Cached embeddings (set by router)
    _embeddings: Optional[np.ndarray] = field(default=None, repr=False)


@dataclass
class RouteMatch:
    """Result of routing a query."""

    route: Route
    query: str
    similarity: float
    matched_example: str
    confidence: str  # "high", "medium", "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.name,
            "query": self.query,
            "similarity": self.similarity,
            "matched_example": self.matched_example,
            "confidence": self.confidence,
        }


class SemanticRouter:
    """Routes queries to handlers based on semantic similarity.

    Uses embeddings to understand query intent and match to the most
    appropriate route, even when exact keywords don't match.

    Features:
    - Semantic matching using embeddings
    - Fallback route for unmatched queries
    - Confidence scoring (high/medium/low)
    - Multiple embedding provider support
    """

    def __init__(
        self,
        embedding_provider: Optional[Any] = None,
        fallback_route: Optional[Route] = None,
        default_threshold: float = 0.5,
    ):
        """Initialize semantic router.

        Args:
            embedding_provider: Embedding provider (auto-detects if None)
            fallback_route: Route to use when no match found
            default_threshold: Default similarity threshold for routes
        """
        self.routes: list[Route] = []
        self.fallback_route = fallback_route
        self.default_threshold = default_threshold
        self._embedding_provider = embedding_provider
        self._initialized = False

    def _get_embeddings(self) -> Any:
        """Get or create embedding provider."""
        if self._embedding_provider is None:
            # Auto-detect best available
            try:
                from .embeddings import get_embeddings

                self._embedding_provider = get_embeddings()
            except ImportError:
                raise RuntimeError(
                    "No embedding provider available. "
                    "Install sentence-transformers or configure Ollama."
                )
        return self._embedding_provider

    def _embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts."""
        provider = self._get_embeddings()
        if hasattr(provider, "embed_batch"):
            embeddings = provider.embed_batch(texts)
        else:
            embeddings = [provider.embed(text) for text in texts]
        return np.array(embeddings)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def add_route(self, route: Route) -> None:
        """Add a route to the router.

        Args:
            route: Route definition with examples
        """
        if route.threshold == 0.5:  # Default
            route.threshold = self.default_threshold

        # Pre-compute embeddings for examples
        route._embeddings = self._embed(route.examples)
        self.routes.append(route)
        self._initialized = True
        logger.debug(f"Added route '{route.name}' with {len(route.examples)} examples")

    def remove_route(self, name: str) -> bool:
        """Remove a route by name.

        Args:
            name: Route name to remove

        Returns:
            True if route was found and removed
        """
        for i, route in enumerate(self.routes):
            if route.name == name:
                self.routes.pop(i)
                return True
        return False

    def route(self, query: str) -> Optional[RouteMatch]:
        """Route a query to the best matching handler.

        Args:
            query: User query to route

        Returns:
            RouteMatch with matched route, or None if no match
        """
        if not self.routes:
            logger.warning("No routes configured")
            return None

        # Embed the query
        query_embedding = self._embed([query])[0]

        best_match: Optional[RouteMatch] = None
        best_similarity = -1.0

        # Find best matching route
        for route in self.routes:
            if route._embeddings is None:
                continue

            # Compare to all examples
            for i, example_embedding in enumerate(route._embeddings):
                similarity = self._cosine_similarity(query_embedding, example_embedding)

                if similarity > best_similarity and similarity >= route.threshold:
                    best_similarity = similarity
                    best_match = RouteMatch(
                        route=route,
                        query=query,
                        similarity=similarity,
                        matched_example=route.examples[i],
                        confidence=self._get_confidence(similarity),
                    )

        if best_match:
            logger.info(
                f"Routed '{query[:50]}...' to '{best_match.route.name}' "
                f"(similarity={best_match.similarity:.3f})"
            )
            return best_match

        # Use fallback if available
        if self.fallback_route:
            return RouteMatch(
                route=self.fallback_route,
                query=query,
                similarity=0.0,
                matched_example="[fallback]",
                confidence="low",
            )

        logger.debug(f"No route matched for query: {query[:100]}")
        return None

    def _get_confidence(self, similarity: float) -> str:
        """Convert similarity score to confidence level."""
        if similarity >= 0.8:
            return "high"
        elif similarity >= 0.6:
            return "medium"
        else:
            return "low"

    def route_and_handle(self, query: str) -> Any:
        """Route query and execute the matched handler.

        Args:
            query: User query

        Returns:
            Result from handler, or None if no match/handler
        """
        match = self.route(query)
        if match and match.route.handler:
            return match.route.handler(query)
        return None

    def get_routes(self) -> list[dict[str, Any]]:
        """Get list of configured routes.

        Returns:
            List of route info dicts
        """
        return [
            {
                "name": r.name,
                "description": r.description,
                "examples": r.examples,
                "threshold": r.threshold,
                "has_handler": r.handler is not None,
            }
            for r in self.routes
        ]


# Pre-built routes for common use cases
def create_default_routes() -> list[Route]:
    """Create default routes for common query types.

    Returns:
        List of Route objects for technical, business, and general queries
    """
    return [
        Route(
            name="technical",
            description="Technical and coding questions",
            examples=[
                "How do I fix this bug?",
                "What's the best way to implement this?",
                "Why is this code failing?",
                "How do I connect to the database?",
                "What's the API endpoint for X?",
                "How do I deploy this?",
                "What dependencies do I need?",
                "How do I write a test for this?",
            ],
            threshold=0.5,
        ),
        Route(
            name="business",
            description="Business, project, and team questions",
            examples=[
                "What's the status of the project?",
                "When is the deadline?",
                "Who is working on this?",
                "What are the requirements?",
                "What's the priority?",
                "Who approved this?",
                "What's the budget?",
                "When was the last meeting?",
            ],
            threshold=0.5,
        ),
        Route(
            name="documentation",
            description="Documentation and help requests",
            examples=[
                "Where is the documentation?",
                "How do I get started?",
                "What does this feature do?",
                "Is there a guide for this?",
                "Show me an example",
                "What are the options?",
                "Explain how this works",
            ],
            threshold=0.5,
        ),
    ]


__all__ = [
    "SemanticRouter",
    "Route",
    "RouteMatch",
    "create_default_routes",
]
