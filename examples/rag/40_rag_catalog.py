#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 40: RAG Product Catalog Search

An AI-powered product catalog search system:
- Product attribute extraction
- Faceted search (price, category, specs)
- Similar product recommendations
- Comparison tables
- Natural language product queries

Key RAG features demonstrated:
- Structured data extraction
- Multi-attribute filtering
- Semantic + faceted hybrid search
- Product embedding clustering
- Comparison generation
- Evaluation metrics

Demo: Electronics catalog (monitors, keyboards, etc.)

Usage:
    python examples/40_rag_catalog.py
    python examples/40_rag_catalog.py --demo

Requirements:
    pip install agentic-brain sentence-transformers
"""

import asyncio
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class CatalogRAGConfig:
    """Configuration for catalog RAG pipeline."""

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Search
    top_k: int = 10
    rerank_top_k: int = 5
    semantic_weight: float = 0.6
    attribute_weight: float = 0.4

    # Recommendations
    similar_products_k: int = 5

    # Comparison
    max_comparison_products: int = 4


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS AND DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class ProductCategory(Enum):
    """Product categories."""

    MONITORS = "monitors"
    KEYBOARDS = "keyboards"
    MICE = "mice"
    HEADPHONES = "headphones"
    LAPTOPS = "laptops"
    DESKTOPS = "desktops"
    WEBCAMS = "webcams"
    SPEAKERS = "speakers"
    STORAGE = "storage"
    ACCESSORIES = "accessories"


class SortOrder(Enum):
    """Sort order options."""

    RELEVANCE = "relevance"
    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"
    RATING = "rating"
    NEWEST = "newest"
    POPULAR = "popular"


@dataclass
class ProductSpec:
    """A product specification."""

    name: str
    value: str
    unit: str = ""
    numeric_value: Optional[float] = None

    @property
    def display_value(self) -> str:
        if self.unit:
            return f"{self.value} {self.unit}"
        return self.value


@dataclass
class ProductReview:
    """A product review."""

    rating: float
    title: str
    text: str
    author: str = ""
    date: datetime = field(default_factory=datetime.now)
    verified: bool = False


@dataclass
class Product:
    """A product in the catalog."""

    id: str
    name: str
    category: ProductCategory
    brand: str
    price: float
    description: str

    # Specifications
    specs: list[ProductSpec] = field(default_factory=list)

    # Metadata
    sku: str = ""
    upc: str = ""
    images: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Ratings
    rating: float = 0.0
    review_count: int = 0
    reviews: list[ProductReview] = field(default_factory=list)

    # Availability
    in_stock: bool = True
    stock_quantity: int = 0

    # Dates
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Computed
    embedding: Optional[list[float]] = None

    def get_spec(self, name: str) -> Optional[ProductSpec]:
        """Get spec by name."""
        name_lower = name.lower()
        for spec in self.specs:
            if spec.name.lower() == name_lower:
                return spec
        return None

    @property
    def price_display(self) -> str:
        return f"${self.price:.2f}"

    @property
    def rating_display(self) -> str:
        return f"{self.rating:.1f}/5.0 ({self.review_count} reviews)"

    def to_search_text(self) -> str:
        """Generate text for semantic search."""
        parts = [
            self.name,
            self.brand,
            self.description,
            self.category.value,
            " ".join(self.tags),
        ]

        # Add specs
        for spec in self.specs:
            parts.append(f"{spec.name}: {spec.display_value}")

        return " ".join(filter(None, parts))


@dataclass
class FacetValue:
    """A facet value with count."""

    value: str
    count: int
    selected: bool = False


@dataclass
class Facet:
    """A facet for filtering."""

    name: str
    field: str
    values: list[FacetValue] = field(default_factory=list)
    facet_type: str = "term"  # term, range, boolean


@dataclass
class SearchFilters:
    """Search filters."""

    category: Optional[ProductCategory] = None
    brands: list[str] = field(default_factory=list)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    in_stock_only: bool = False
    min_rating: Optional[float] = None
    specs: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Search result with product and metadata."""

    product: Product
    score: float
    rank: int
    match_type: str
    highlights: list[str] = field(default_factory=list)


@dataclass
class SearchResponse:
    """Complete search response."""

    query: str
    results: list[SearchResult]
    total_count: int
    facets: list[Facet]
    filters_applied: SearchFilters
    latency_ms: float


@dataclass
class ComparisonTable:
    """Product comparison table."""

    products: list[Product]
    attributes: list[str]
    values: dict[str, dict[str, str]]  # product_id -> {attr -> value}
    winner_by_attr: dict[str, str]  # attr -> product_id


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING AND SEARCH
# ══════════════════════════════════════════════════════════════════════════════


class ProductEmbedder:
    """Generate embeddings for products."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._dimension = 384

    def _load_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.model_name)
                self._dimension = self.model.get_sentence_embedding_dimension()
            except ImportError:
                self.model = "mock"

    def embed_product(self, product: Product) -> list[float]:
        """Generate embedding for a product."""
        text = product.to_search_text()
        return self.embed(text)

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        self._load_model()

        if self.model == "mock":
            return self._mock_embedding(text)

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def _mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic mock embedding."""
        hash_val = hashlib.md5(text.encode()).hexdigest()

        embedding = []
        for i in range(0, self._dimension):
            idx = i % len(hash_val)
            val = int(hash_val[idx : idx + 2], 16) / 255.0 - 0.5
            embedding.append(val)

        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    @property
    def dimension(self) -> int:
        return self._dimension


class ProductVectorStore:
    """Vector store for products."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: dict[str, list[float]] = {}

    def add(self, product_id: str, vector: list[float]):
        """Add product vector."""
        self.vectors[product_id] = vector

    def search(
        self, query_vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Search for similar products."""
        if not self.vectors:
            return []

        similarities = []
        for pid, vec in self.vectors.items():
            sim = self._cosine_similarity(query_vector, vec)
            similarities.append((pid, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def find_similar(self, product_id: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Find products similar to a given product."""
        if product_id not in self.vectors:
            return []

        product_vec = self.vectors[product_id]
        results = self.search(product_vec, top_k + 1)

        # Filter out the product itself
        return [(pid, score) for pid, score in results if pid != product_id][:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity."""
        dot_product = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class ProductKeywordIndex:
    """Keyword index for product search."""

    def __init__(self):
        self.products: dict[str, Product] = {}
        self.name_index: dict[str, list[str]] = {}
        self.brand_index: dict[str, list[str]] = {}
        self.category_index: dict[str, list[str]] = {}
        self.tag_index: dict[str, list[str]] = {}

    def add(self, product: Product):
        """Add product to index."""
        self.products[product.id] = product

        # Index name words
        for word in self._tokenize(product.name):
            if word not in self.name_index:
                self.name_index[word] = []
            self.name_index[word].append(product.id)

        # Index brand
        brand_lower = product.brand.lower()
        if brand_lower not in self.brand_index:
            self.brand_index[brand_lower] = []
        self.brand_index[brand_lower].append(product.id)

        # Index category
        cat_key = product.category.value
        if cat_key not in self.category_index:
            self.category_index[cat_key] = []
        self.category_index[cat_key].append(product.id)

        # Index tags
        for tag in product.tags:
            tag_lower = tag.lower()
            if tag_lower not in self.tag_index:
                self.tag_index[tag_lower] = []
            self.tag_index[tag_lower].append(product.id)

    def search(self, query: str) -> list[tuple[str, float]]:
        """Keyword search."""
        tokens = self._tokenize(query)
        scores: dict[str, float] = {}

        for token in tokens:
            # Name matches (highest weight)
            if token in self.name_index:
                for pid in self.name_index[token]:
                    scores[pid] = scores.get(pid, 0) + 3.0

            # Brand matches
            if token in self.brand_index:
                for pid in self.brand_index[token]:
                    scores[pid] = scores.get(pid, 0) + 2.0

            # Tag matches
            if token in self.tag_index:
                for pid in self.tag_index[token]:
                    scores[pid] = scores.get(pid, 0) + 1.0

            # Partial name matches
            for name_word, pids in self.name_index.items():
                if token in name_word or name_word in token:
                    for pid in pids:
                        scores[pid] = scores.get(pid, 0) + 0.5

        results = list(scores.items())
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text."""
        return [w.lower() for w in re.findall(r"\b\w+\b", text) if len(w) > 2]


# ══════════════════════════════════════════════════════════════════════════════
# CATALOG RAG PIPELINE
# ══════════════════════════════════════════════════════════════════════════════


class CatalogRAGPipeline:
    """Complete RAG pipeline for product catalog."""

    def __init__(self, config: CatalogRAGConfig = None):
        self.config = config or CatalogRAGConfig()

        # Components
        self.embedder = ProductEmbedder(self.config.embedding_model)
        self.vector_store = ProductVectorStore(self.config.embedding_dimension)
        self.keyword_index = ProductKeywordIndex()

        # Storage
        self.products: dict[str, Product] = {}

    def add_product(self, product: Product) -> Product:
        """Add a product to the catalog."""
        # Generate embedding
        product.embedding = self.embedder.embed_product(product)

        # Add to stores
        self.vector_store.add(product.id, product.embedding)
        self.keyword_index.add(product)

        self.products[product.id] = product
        return product

    def search(
        self,
        query: str,
        filters: SearchFilters = None,
        sort: SortOrder = SortOrder.RELEVANCE,
        top_k: int = None,
    ) -> SearchResponse:
        """Search for products."""
        import time

        start_time = time.time()

        filters = filters or SearchFilters()
        top_k = top_k or self.config.top_k

        # Semantic search
        query_embedding = self.embedder.embed(query)
        semantic_results = self.vector_store.search(query_embedding, top_k * 2)

        # Keyword search
        keyword_results = self.keyword_index.search(query)

        # Merge results
        product_scores: dict[str, tuple[float, str]] = {}

        # Normalize semantic scores
        if semantic_results:
            max_sem = max(r[1] for r in semantic_results)
            for pid, score in semantic_results:
                normalized = score / max_sem if max_sem > 0 else 0
                weighted = normalized * self.config.semantic_weight
                product_scores[pid] = (weighted, "semantic")

        # Add keyword scores
        if keyword_results:
            max_kw = max(r[1] for r in keyword_results) if keyword_results else 1
            for pid, score in keyword_results:
                normalized = score / max_kw if max_kw > 0 else 0
                weighted = normalized * self.config.attribute_weight

                if pid in product_scores:
                    old_score, _ = product_scores[pid]
                    product_scores[pid] = (old_score + weighted, "hybrid")
                else:
                    product_scores[pid] = (weighted, "keyword")

        # Apply filters and build results
        results = []

        for pid, (score, match_type) in product_scores.items():
            if pid not in self.products:
                continue

            product = self.products[pid]

            # Apply filters
            if not self._matches_filters(product, filters):
                continue

            # Generate highlights
            highlights = self._generate_highlights(product, query)

            results.append(
                SearchResult(
                    product=product,
                    score=score,
                    rank=0,
                    match_type=match_type,
                    highlights=highlights,
                )
            )

        # Sort results
        results = self._sort_results(results, sort)

        # Assign ranks
        for i, r in enumerate(results, 1):
            r.rank = i

        # Generate facets from filtered results
        facets = self._generate_facets(results, filters)

        latency = (time.time() - start_time) * 1000

        return SearchResponse(
            query=query,
            results=results[:top_k],
            total_count=len(results),
            facets=facets,
            filters_applied=filters,
            latency_ms=latency,
        )

    def _matches_filters(self, product: Product, filters: SearchFilters) -> bool:
        """Check if product matches filters."""
        # Category filter
        if filters.category and product.category != filters.category:
            return False

        # Brand filter
        if filters.brands and product.brand.lower() not in [
            b.lower() for b in filters.brands
        ]:
            return False

        # Price range
        if filters.price_min is not None and product.price < filters.price_min:
            return False
        if filters.price_max is not None and product.price > filters.price_max:
            return False

        # In stock
        if filters.in_stock_only and not product.in_stock:
            return False

        # Rating
        if filters.min_rating is not None and product.rating < filters.min_rating:
            return False

        # Spec filters
        for spec_name, spec_value in filters.specs.items():
            product_spec = product.get_spec(spec_name)
            if not product_spec:
                return False

            if isinstance(spec_value, dict):
                # Range filter
                if "min" in spec_value:
                    if (
                        product_spec.numeric_value is None
                        or product_spec.numeric_value < spec_value["min"]
                    ):
                        return False
                if "max" in spec_value:
                    if (
                        product_spec.numeric_value is None
                        or product_spec.numeric_value > spec_value["max"]
                    ):
                        return False
            else:
                # Exact match
                if product_spec.value.lower() != str(spec_value).lower():
                    return False

        return True

    def _sort_results(
        self, results: list[SearchResult], sort: SortOrder
    ) -> list[SearchResult]:
        """Sort results."""
        if sort == SortOrder.RELEVANCE:
            results.sort(key=lambda r: r.score, reverse=True)
        elif sort == SortOrder.PRICE_LOW:
            results.sort(key=lambda r: r.product.price)
        elif sort == SortOrder.PRICE_HIGH:
            results.sort(key=lambda r: r.product.price, reverse=True)
        elif sort == SortOrder.RATING:
            results.sort(key=lambda r: r.product.rating, reverse=True)
        elif sort == SortOrder.NEWEST:
            results.sort(key=lambda r: r.product.created_at, reverse=True)
        elif sort == SortOrder.POPULAR:
            results.sort(key=lambda r: r.product.review_count, reverse=True)

        return results

    def _generate_highlights(self, product: Product, query: str) -> list[str]:
        """Generate search highlights."""
        highlights = []
        query_words = set(re.findall(r"\b\w+\b", query.lower()))

        # Check name
        name_words = set(re.findall(r"\b\w+\b", product.name.lower()))
        name_matches = query_words & name_words
        if name_matches:
            highlights.append(f"Name: {', '.join(name_matches)}")

        # Check description
        desc_words = set(re.findall(r"\b\w+\b", product.description.lower()))
        desc_matches = query_words & desc_words
        if desc_matches:
            highlights.append(f"Description: {', '.join(list(desc_matches)[:3])}")

        # Check specs
        for spec in product.specs:
            spec_words = set(
                re.findall(r"\b\w+\b", f"{spec.name} {spec.value}".lower())
            )
            spec_matches = query_words & spec_words
            if spec_matches:
                highlights.append(f"{spec.name}: {spec.value}")
                break

        return highlights[:3]

    def _generate_facets(
        self, results: list[SearchResult], filters: SearchFilters
    ) -> list[Facet]:
        """Generate facets from results."""
        facets = []

        # Category facet
        category_counts: Counter = Counter()
        for r in results:
            category_counts[r.product.category.value] += 1

        category_values = [
            FacetValue(
                value=cat,
                count=count,
                selected=(filters.category and filters.category.value == cat),
            )
            for cat, count in category_counts.most_common()
        ]

        if category_values:
            facets.append(
                Facet(name="Category", field="category", values=category_values)
            )

        # Brand facet
        brand_counts: Counter = Counter()
        for r in results:
            brand_counts[r.product.brand] += 1

        brand_values = [
            FacetValue(
                value=brand,
                count=count,
                selected=(brand.lower() in [b.lower() for b in filters.brands]),
            )
            for brand, count in brand_counts.most_common(10)
        ]

        if brand_values:
            facets.append(Facet(name="Brand", field="brand", values=brand_values))

        # Price range facet
        prices = [r.product.price for r in results]
        if prices:
            price_ranges = [
                ("Under $50", 0, 50),
                ("$50 - $100", 50, 100),
                ("$100 - $200", 100, 200),
                ("$200 - $500", 200, 500),
                ("$500+", 500, float("inf")),
            ]

            price_values = []
            for label, min_p, max_p in price_ranges:
                count = sum(1 for p in prices if min_p <= p < max_p)
                if count > 0:
                    selected = filters.price_min == min_p and (
                        filters.price_max == max_p
                        or (max_p == float("inf") and filters.price_max is None)
                    )
                    price_values.append(
                        FacetValue(value=label, count=count, selected=selected)
                    )

            if price_values:
                facets.append(
                    Facet(
                        name="Price",
                        field="price",
                        values=price_values,
                        facet_type="range",
                    )
                )

        # Rating facet
        rating_values = []
        for min_rating in [4.0, 3.0, 2.0]:
            count = sum(1 for r in results if r.product.rating >= min_rating)
            if count > 0:
                selected = filters.min_rating == min_rating
                rating_values.append(
                    FacetValue(
                        value=f"{min_rating}+ stars", count=count, selected=selected
                    )
                )

        if rating_values:
            facets.append(
                Facet(
                    name="Rating",
                    field="rating",
                    values=rating_values,
                    facet_type="range",
                )
            )

        # In Stock facet
        in_stock_count = sum(1 for r in results if r.product.in_stock)
        facets.append(
            Facet(
                name="Availability",
                field="in_stock",
                values=[
                    FacetValue(
                        value="In Stock",
                        count=in_stock_count,
                        selected=filters.in_stock_only,
                    ),
                    FacetValue(
                        value="All",
                        count=len(results),
                        selected=not filters.in_stock_only,
                    ),
                ],
                facet_type="boolean",
            )
        )

        return facets

    def get_similar_products(
        self, product_id: str, top_k: int = None
    ) -> list[SearchResult]:
        """Find products similar to a given product."""
        top_k = top_k or self.config.similar_products_k

        if product_id not in self.products:
            return []

        similar = self.vector_store.find_similar(product_id, top_k)

        results = []
        for i, (pid, score) in enumerate(similar, 1):
            if pid in self.products:
                results.append(
                    SearchResult(
                        product=self.products[pid],
                        score=score,
                        rank=i,
                        match_type="similar",
                    )
                )

        return results

    def compare_products(self, product_ids: list[str]) -> ComparisonTable:
        """Generate comparison table for products."""
        products = [self.products[pid] for pid in product_ids if pid in self.products]

        if len(products) < 2:
            return ComparisonTable(
                products=products, attributes=[], values={}, winner_by_attr={}
            )

        # Limit number of products
        products = products[: self.config.max_comparison_products]

        # Collect all spec names
        all_specs = set()
        for p in products:
            for spec in p.specs:
                all_specs.add(spec.name)

        # Define comparison attributes
        base_attributes = ["Price", "Rating", "Brand"]
        spec_attributes = sorted(all_specs)
        attributes = base_attributes + spec_attributes

        # Build values dict
        values: dict[str, dict[str, str]] = {}

        for p in products:
            values[p.id] = {
                "Price": p.price_display,
                "Rating": p.rating_display,
                "Brand": p.brand,
            }

            for attr in spec_attributes:
                spec = p.get_spec(attr)
                values[p.id][attr] = spec.display_value if spec else "-"

        # Determine winners
        winner_by_attr: dict[str, str] = {}

        # Price - lowest wins
        prices = [(p.id, p.price) for p in products]
        prices.sort(key=lambda x: x[1])
        winner_by_attr["Price"] = prices[0][0]

        # Rating - highest wins
        ratings = [(p.id, p.rating) for p in products]
        ratings.sort(key=lambda x: x[1], reverse=True)
        winner_by_attr["Rating"] = ratings[0][0]

        # Numeric specs - try to determine winner
        for attr in spec_attributes:
            numeric_values = []
            for p in products:
                spec = p.get_spec(attr)
                if spec and spec.numeric_value is not None:
                    numeric_values.append((p.id, spec.numeric_value))

            if numeric_values:
                # Higher is usually better (RAM, resolution, etc.)
                numeric_values.sort(key=lambda x: x[1], reverse=True)
                winner_by_attr[attr] = numeric_values[0][0]

        return ComparisonTable(
            products=products,
            attributes=attributes,
            values=values,
            winner_by_attr=winner_by_attr,
        )

    def get_recommendations_for_user(
        self, viewed_product_ids: list[str], purchased_product_ids: list[str] = None
    ) -> list[SearchResult]:
        """Get product recommendations based on user history."""
        purchased_product_ids = purchased_product_ids or []

        # Combine viewed and purchased for finding similar
        all_ids = list(set(viewed_product_ids + purchased_product_ids))

        if not all_ids:
            # Return popular products
            products = list(self.products.values())
            products.sort(key=lambda p: p.review_count, reverse=True)
            return [
                SearchResult(
                    product=p, score=p.rating / 5, rank=i, match_type="popular"
                )
                for i, p in enumerate(products[:5], 1)
            ]

        # Aggregate similar products
        all_similar: dict[str, float] = {}

        for pid in all_ids:
            similar = self.vector_store.find_similar(pid, 5)
            for sim_pid, score in similar:
                if sim_pid not in all_ids:  # Don't recommend already viewed
                    all_similar[sim_pid] = all_similar.get(sim_pid, 0) + score

        # Sort by aggregate score
        sorted_similar = sorted(all_similar.items(), key=lambda x: x[1], reverse=True)

        results = []
        for i, (pid, score) in enumerate(sorted_similar[:10], 1):
            if pid in self.products:
                results.append(
                    SearchResult(
                        product=self.products[pid],
                        score=score,
                        rank=i,
                        match_type="recommended",
                    )
                )

        return results

    def answer_question(self, question: str) -> str:
        """Answer natural language product question."""
        # Parse question type
        question_lower = question.lower()

        # Price questions
        if "cheapest" in question_lower or "least expensive" in question_lower:
            results = self.search(question, sort=SortOrder.PRICE_LOW)
            if results.results:
                p = results.results[0].product
                return (
                    f"The most affordable option is the {p.name} at {p.price_display}."
                )

        if "most expensive" in question_lower or "premium" in question_lower:
            results = self.search(question, sort=SortOrder.PRICE_HIGH)
            if results.results:
                p = results.results[0].product
                return f"The premium option is the {p.name} at {p.price_display}."

        # Best rated questions
        if (
            "best" in question_lower
            or "top rated" in question_lower
            or "highest rated" in question_lower
        ):
            results = self.search(question, sort=SortOrder.RATING)
            if results.results:
                p = results.results[0].product
                return f"The top-rated option is the {p.name} with {p.rating_display}."

        # Comparison questions
        if "difference between" in question_lower or "compare" in question_lower:
            results = self.search(question)
            if len(results.results) >= 2:
                p1, p2 = results.results[0].product, results.results[1].product
                return (
                    f"Comparing {p1.name} ({p1.price_display}) and {p2.name} ({p2.price_display}):\n"
                    f"- {p1.name}: {p1.rating_display}\n"
                    f"- {p2.name}: {p2.rating_display}"
                )

        # General search
        results = self.search(question)

        if not results.results:
            return f"I couldn't find products matching '{question}'."

        answer_parts = [f"Found {results.total_count} products matching your query:"]

        for r in results.results[:3]:
            p = r.product
            answer_parts.append(f"\n• {p.name}")
            answer_parts.append(f"  {p.price_display} | {p.rating_display}")
            if r.highlights:
                answer_parts.append(f"  Matches: {', '.join(r.highlights)}")

        return "\n".join(answer_parts)

    def get_stats(self) -> dict:
        """Get catalog statistics."""
        categories = Counter(p.category.value for p in self.products.values())
        brands = Counter(p.brand for p in self.products.values())

        prices = [p.price for p in self.products.values()]

        return {
            "total_products": len(self.products),
            "categories": dict(categories),
            "brands": dict(brands.most_common(10)),
            "price_range": {
                "min": min(prices) if prices else 0,
                "max": max(prices) if prices else 0,
                "avg": sum(prices) / len(prices) if prices else 0,
            },
            "avg_rating": (
                sum(p.rating for p in self.products.values()) / len(self.products)
                if self.products
                else 0
            ),
        }


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE PRODUCTS FOR DEMO
# ══════════════════════════════════════════════════════════════════════════════


def create_sample_products() -> list[Product]:
    """Create sample electronics products."""
    products = [
        # Monitors
        Product(
            id="mon001",
            name='UltraView Pro 27" 4K Monitor',
            category=ProductCategory.MONITORS,
            brand="TechVision",
            price=449.99,
            description="Professional 27-inch 4K UHD monitor with IPS panel, 99% sRGB color accuracy, and USB-C connectivity. Perfect for creative professionals and productivity.",
            specs=[
                ProductSpec("Screen Size", "27", "inches", 27),
                ProductSpec("Resolution", "3840x2160", "", None),
                ProductSpec("Panel Type", "IPS", "", None),
                ProductSpec("Refresh Rate", "60", "Hz", 60),
                ProductSpec("Response Time", "5", "ms", 5),
                ProductSpec("HDR", "HDR10", "", None),
            ],
            tags=["4K", "IPS", "USB-C", "professional", "design"],
            rating=4.7,
            review_count=523,
            in_stock=True,
            stock_quantity=45,
        ),
        Product(
            id="mon002",
            name='GameMaster 32" Curved Gaming Monitor',
            category=ProductCategory.MONITORS,
            brand="VelocityGear",
            price=379.99,
            description="Immersive 32-inch curved gaming monitor with 165Hz refresh rate, 1ms response time, and AMD FreeSync Premium support. Dominate your games.",
            specs=[
                ProductSpec("Screen Size", "32", "inches", 32),
                ProductSpec("Resolution", "2560x1440", "", None),
                ProductSpec("Panel Type", "VA", "", None),
                ProductSpec("Refresh Rate", "165", "Hz", 165),
                ProductSpec("Response Time", "1", "ms", 1),
                ProductSpec("Adaptive Sync", "FreeSync Premium", "", None),
            ],
            tags=["gaming", "curved", "165Hz", "FreeSync", "QHD"],
            rating=4.5,
            review_count=892,
            in_stock=True,
            stock_quantity=62,
        ),
        Product(
            id="mon003",
            name='EcoView 24" Budget Monitor',
            category=ProductCategory.MONITORS,
            brand="ValueTech",
            price=149.99,
            description="Affordable 24-inch Full HD monitor with thin bezels and VESA mount compatibility. Great for everyday computing and basic productivity.",
            specs=[
                ProductSpec("Screen Size", "24", "inches", 24),
                ProductSpec("Resolution", "1920x1080", "", None),
                ProductSpec("Panel Type", "IPS", "", None),
                ProductSpec("Refresh Rate", "75", "Hz", 75),
                ProductSpec("Response Time", "5", "ms", 5),
            ],
            tags=["budget", "Full HD", "office", "basic"],
            rating=4.2,
            review_count=1247,
            in_stock=True,
            stock_quantity=150,
        ),
        # Keyboards
        Product(
            id="kb001",
            name="MechMaster Pro Mechanical Keyboard",
            category=ProductCategory.KEYBOARDS,
            brand="KeyCraft",
            price=149.99,
            description="Premium mechanical keyboard with hot-swappable Cherry MX switches, per-key RGB lighting, and aircraft-grade aluminum frame.",
            specs=[
                ProductSpec("Switch Type", "Cherry MX Red", "", None),
                ProductSpec("Layout", "Full Size", "", None),
                ProductSpec("Backlighting", "Per-key RGB", "", None),
                ProductSpec("Connection", "USB-C", "", None),
                ProductSpec("Hot-Swappable", "Yes", "", None),
            ],
            tags=["mechanical", "RGB", "Cherry MX", "aluminum", "gaming"],
            rating=4.8,
            review_count=634,
            in_stock=True,
            stock_quantity=78,
        ),
        Product(
            id="kb002",
            name="SlimType Wireless Keyboard",
            category=ProductCategory.KEYBOARDS,
            brand="ErgoPro",
            price=79.99,
            description="Ultra-slim wireless keyboard with quiet scissor switches, multi-device Bluetooth, and 3-month battery life. Perfect for Mac and Windows.",
            specs=[
                ProductSpec("Switch Type", "Scissor", "", None),
                ProductSpec("Layout", "Compact", "", None),
                ProductSpec("Connection", "Bluetooth 5.0", "", None),
                ProductSpec("Battery Life", "3", "months", 3),
                ProductSpec("Multi-Device", "3 devices", "", None),
            ],
            tags=["wireless", "Bluetooth", "slim", "quiet", "portable"],
            rating=4.4,
            review_count=412,
            in_stock=True,
            stock_quantity=95,
        ),
        # Mice
        Product(
            id="mouse001",
            name="PrecisionPro Gaming Mouse",
            category=ProductCategory.MICE,
            brand="VelocityGear",
            price=69.99,
            description="High-performance gaming mouse with 25,000 DPI sensor, 8 programmable buttons, and PTFE feet for smooth gliding.",
            specs=[
                ProductSpec("DPI", "25000", "", 25000),
                ProductSpec("Buttons", "8", "", 8),
                ProductSpec("Connection", "Wired USB", "", None),
                ProductSpec("Weight", "85", "g", 85),
                ProductSpec("RGB", "16.8M colors", "", None),
            ],
            tags=["gaming", "RGB", "programmable", "high DPI"],
            rating=4.6,
            review_count=789,
            in_stock=True,
            stock_quantity=120,
        ),
        Product(
            id="mouse002",
            name="ErgoGlide Vertical Mouse",
            category=ProductCategory.MICE,
            brand="ErgoPro",
            price=49.99,
            description="Ergonomic vertical mouse designed to reduce wrist strain. Wireless with long battery life and adjustable DPI.",
            specs=[
                ProductSpec("DPI", "4000", "", 4000),
                ProductSpec("Buttons", "6", "", 6),
                ProductSpec("Connection", "2.4GHz Wireless", "", None),
                ProductSpec("Battery", "AA", "", None),
                ProductSpec("Ergonomic", "Vertical", "", None),
            ],
            tags=["ergonomic", "vertical", "wireless", "comfort", "health"],
            rating=4.3,
            review_count=356,
            in_stock=True,
            stock_quantity=67,
        ),
        # Headphones
        Product(
            id="hp001",
            name="StudioPro Noise-Canceling Headphones",
            category=ProductCategory.HEADPHONES,
            brand="AudioMax",
            price=299.99,
            description="Premium over-ear headphones with active noise cancellation, 30-hour battery life, and high-resolution audio support.",
            specs=[
                ProductSpec("Driver Size", "40", "mm", 40),
                ProductSpec("Battery Life", "30", "hours", 30),
                ProductSpec("ANC", "Active", "", None),
                ProductSpec("Bluetooth", "5.2", "", None),
                ProductSpec("Hi-Res Audio", "Yes", "", None),
            ],
            tags=["noise canceling", "wireless", "hi-res", "premium", "ANC"],
            rating=4.7,
            review_count=1023,
            in_stock=True,
            stock_quantity=34,
        ),
        Product(
            id="hp002",
            name="GameSound Pro 7.1 Headset",
            category=ProductCategory.HEADPHONES,
            brand="VelocityGear",
            price=89.99,
            description="Gaming headset with virtual 7.1 surround sound, detachable microphone, and memory foam ear cushions.",
            specs=[
                ProductSpec("Driver Size", "50", "mm", 50),
                ProductSpec("Surround", "7.1 Virtual", "", None),
                ProductSpec("Microphone", "Detachable Boom", "", None),
                ProductSpec("Connection", "USB/3.5mm", "", None),
                ProductSpec("Weight", "280", "g", 280),
            ],
            tags=["gaming", "7.1 surround", "microphone", "comfortable"],
            rating=4.4,
            review_count=567,
            in_stock=True,
            stock_quantity=89,
        ),
        # Webcams
        Product(
            id="wc001",
            name="ClearView 4K Webcam",
            category=ProductCategory.WEBCAMS,
            brand="TechVision",
            price=129.99,
            description="Professional 4K webcam with auto-focus, built-in ring light, and privacy cover. Perfect for streaming and video calls.",
            specs=[
                ProductSpec("Resolution", "4K", "", None),
                ProductSpec("Frame Rate", "30", "fps", 30),
                ProductSpec("Autofocus", "Yes", "", None),
                ProductSpec("Microphone", "Dual stereo", "", None),
                ProductSpec("Ring Light", "Adjustable", "", None),
            ],
            tags=["4K", "streaming", "video calls", "ring light", "autofocus"],
            rating=4.5,
            review_count=234,
            in_stock=True,
            stock_quantity=56,
        ),
    ]

    return products


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run interactive catalog search demo."""
    print("=" * 70)
    print("🛒 Product Catalog Search - RAG Demo")
    print("=" * 70)

    # Create pipeline
    config = CatalogRAGConfig(top_k=5)
    pipeline = CatalogRAGPipeline(config)

    # Load sample products
    print("\n📦 Loading product catalog...")
    products = create_sample_products()

    for product in products:
        pipeline.add_product(product)
        print(f"  ✅ {product.name}")

    # Show stats
    stats = pipeline.get_stats()
    print("\n📊 Catalog Stats:")
    print(f"   Products: {stats['total_products']}")
    print(f"   Categories: {list(stats['categories'].keys())}")
    print(
        f"   Price Range: ${stats['price_range']['min']:.2f} - ${stats['price_range']['max']:.2f}"
    )
    print(f"   Avg Rating: {stats['avg_rating']:.2f}/5.0")

    # Sample queries
    sample_queries = [
        "gaming monitor with high refresh rate",
        "wireless keyboard for Mac",
        "best noise canceling headphones",
        "ergonomic mouse under $60",
        "4K webcam for streaming",
    ]

    print("\n" + "=" * 70)
    print("💡 Sample searches:")
    for q in sample_queries:
        print(f"   • {q}")

    # Interactive loop
    print("\n" + "=" * 70)
    print("💬 Search products (type 'quit' to exit)")
    print("   Commands:")
    print("   • 'similar <id>' - find similar products")
    print("   • 'compare <id1> <id2>' - compare products")
    print("   • 'ask <question>' - ask about products")
    print("   • 'filter category:monitors' - apply filter")
    print("=" * 70)

    while True:
        try:
            query = input("\n🔍 Search: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query:
            continue

        if query.lower() == "quit":
            break

        if query.lower().startswith("similar "):
            product_id = query[8:].strip()
            results = pipeline.get_similar_products(product_id)

            if results:
                print(
                    f"\n📦 Products similar to {pipeline.products.get(product_id, Product(id='', name='Unknown', category=ProductCategory.ACCESSORIES, brand='', price=0, description='')).name}:"
                )
                for r in results:
                    print(f"   {r.rank}. {r.product.name} ({r.score:.2f})")
                    print(
                        f"      {r.product.price_display} | {r.product.rating_display}"
                    )
            else:
                print(f"❌ Product not found: {product_id}")
            continue

        if query.lower().startswith("compare "):
            ids = query[8:].strip().split()
            if len(ids) >= 2:
                comparison = pipeline.compare_products(ids)

                if comparison.products:
                    print("\n📊 Product Comparison:")
                    print("-" * 70)

                    # Header
                    headers = ["Attribute"] + [p.name[:20] for p in comparison.products]
                    print(" | ".join(f"{h:20}" for h in headers))
                    print("-" * 70)

                    # Values
                    for attr in comparison.attributes:
                        row = [attr]
                        for p in comparison.products:
                            val = comparison.values.get(p.id, {}).get(attr, "-")
                            winner = comparison.winner_by_attr.get(attr) == p.id
                            row.append(f"{'✓ ' if winner else ''}{val[:18]}")
                        print(" | ".join(f"{v:20}" for v in row))
            else:
                print("❌ Please provide at least 2 product IDs")
            continue

        if query.lower().startswith("ask "):
            question = query[4:].strip()
            answer = pipeline.answer_question(question)
            print(f"\n🤖 {answer}")
            continue

        # Parse filters
        filters = SearchFilters()
        search_query = query

        if "category:" in query.lower():
            match = re.search(r"category:(\w+)", query, re.IGNORECASE)
            if match:
                try:
                    filters.category = ProductCategory(match.group(1).lower())
                    search_query = query[: match.start()] + query[match.end() :]
                except ValueError:
                    pass

        if "brand:" in query.lower():
            match = re.search(r"brand:(\w+)", query, re.IGNORECASE)
            if match:
                filters.brands = [match.group(1)]
                search_query = query[: match.start()] + query[match.end() :]

        if "under $" in query.lower():
            match = re.search(r"under \$?(\d+)", query, re.IGNORECASE)
            if match:
                filters.price_max = float(match.group(1))
                search_query = query[: match.start()] + query[match.end() :]

        # Search
        response = pipeline.search(search_query.strip(), filters)

        if not response.results:
            print("\n❌ No products found")
            continue

        print(
            f"\n🔎 Found {response.total_count} products ({response.latency_ms:.0f}ms):\n"
        )

        for r in response.results:
            p = r.product
            print(f"  {r.rank}. {p.name}")
            print(f"     {p.price_display} | {p.rating_display}")
            print(f"     ID: {p.id} | Category: {p.category.value}")

            if r.highlights:
                print(f"     Matches: {', '.join(r.highlights)}")
            print()

        # Show facets
        if response.facets:
            print("📌 Filters:")
            for facet in response.facets[:3]:
                values_str = ", ".join(
                    [f"{v.value} ({v.count})" for v in facet.values[:3]]
                )
                print(f"   {facet.name}: {values_str}")

    print("\n👋 Goodbye!")


def main():
    """Main entry point."""
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    run_demo()


if __name__ == "__main__":
    main()
