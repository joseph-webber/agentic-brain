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
"""Product advice helpers for conversational commerce.

The :class:`ProductAdvisor` works with validated WooCommerce models and
returns lightweight structures that are easy for the chatbot layer to
turn into messages such as:

- "This one is cheaper but has less storage"
- "You usually buy size Large; want to stick with that?"
- "That item is out of stock, but here are three similar options."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from ..models import WooOrder, WooOrderItem, WooProduct


@dataclass(frozen=True)
class RecommendationReason:
    """Why a suggestion was made."""

    kind: str
    detail: str


@dataclass(frozen=True)
class ProductComparison:
    """Comparison between a base product and one alternative."""

    base_product_id: int
    other_product_id: int
    headline: str
    advantages_for_other: List[str] = field(default_factory=list)
    disadvantages_for_other: List[str] = field(default_factory=list)


class ProductAdvisor:
    """High-level product advice and comparison engine."""

    def compare_products(
        self,
        base: WooProduct,
        others: Iterable[WooProduct],
    ) -> List[ProductComparison]:
        """Generate quick comparison summaries.

        The heuristics here are intentionally simple – the LLM can
        always elaborate, but we want deterministic bullets we can test.
        """

        results: List[ProductComparison] = []
        for other in others:
            if other.id == base.id:
                continue

            advantages: List[str] = []
            disadvantages: List[str] = []

            if other.price < base.price:
                advantages.append("Lower price")
            elif other.price > base.price:
                disadvantages.append("Higher price")

            if other.in_stock and not base.in_stock:
                advantages.append("In stock while the other option is not")
            if base.in_stock and not other.in_stock:
                disadvantages.append("Currently out of stock")

            if len(other.images) > len(base.images):
                advantages.append("More photos available")

            headline_parts: List[str] = []
            if advantages:
                headline_parts.append("Good alternative")
            if other.price < base.price:
                headline_parts.append("cheaper")
            if not headline_parts:
                headline_parts.append("Similar option")

            results.append(
                ProductComparison(
                    base_product_id=base.id,
                    other_product_id=other.id,
                    headline=" ".join(headline_parts),
                    advantages_for_other=advantages,
                    disadvantages_for_other=disadvantages,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Size / fit suggestions
    # ------------------------------------------------------------------

    def recommend_size(
        self,
        previous_size: Optional[str],
        available_sizes: Iterable[str],
        *,
        fit_preference: str | None = None,
    ) -> str:
        """Return a concise size recommendation string.

        ``previous_size`` typically comes from past orders or
        user profile; ``available_sizes`` are strings such as
        ``["S", "M", "L", "XL"]``.
        """

        sizes = [s.upper() for s in available_sizes]
        if not sizes:
            return "No size information available."

        if previous_size and previous_size.upper() in sizes:
            base = previous_size.upper()
        else:
            base = sizes[-1] if fit_preference == "loose" else sizes[len(sizes) // 2]

        if fit_preference == "tight" and base in sizes and sizes.index(base) > 0:
            base = sizes[sizes.index(base) - 1]
        elif (
            fit_preference == "loose"
            and base in sizes
            and sizes.index(base) < len(sizes) - 1
        ):
            base = sizes[sizes.index(base) + 1]

        return f"We recommend size {base}."

    # ------------------------------------------------------------------
    # Availability & alternatives
    # ------------------------------------------------------------------

    def availability_message(self, product: WooProduct, quantity: int = 1) -> str:
        """Return a short availability message."""

        if not product.in_stock or product.stock <= 0:
            return "This item is currently out of stock."
        if product.stock < quantity:
            return f"Only {product.stock} left in stock."
        if product.stock <= 3:
            return f"Hurry, only {product.stock} left in stock."
        return "This item is in stock."

    def suggest_alternatives(
        self,
        product: WooProduct,
        candidates: Iterable[WooProduct],
        *,
        limit: int = 3,
    ) -> List[WooProduct]:
        """Return alternative products when the requested one is not available."""

        base_category_ids = {c.id for c in product.categories or []}

        results: List[WooProduct] = []
        for cand in candidates:
            if cand.id == product.id:
                continue
            if not cand.in_stock:
                continue
            cand_category_ids = {c.id for c in cand.categories or []}
            if base_category_ids and not (base_category_ids & cand_category_ids):
                continue
            results.append(cand)

        # Prefer cheaper but still relevant options
        results.sort(key=lambda p: p.price)
        return results[:limit]

    # ------------------------------------------------------------------
    # "Similar to what you bought before"
    # ------------------------------------------------------------------

    def recommend_from_history(
        self,
        orders: Iterable[WooOrder],
        catalog: Iterable[WooProduct],
        *,
        limit: int = 5,
    ) -> List[WooProduct]:
        """Suggest products similar to a customer's previous purchases."""

        purchased_ids: set[int] = set()
        purchased_category_ids: set[int] = set()

        for order in orders:
            for item in order.items or []:
                if isinstance(item, WooOrderItem) and item.product_id is not None:
                    purchased_ids.add(int(item.product_id))
            for item in order.items or []:
                # We don't always have product categories on the order
                # itself, so we infer later from the catalogue.
                if isinstance(item, WooOrderItem) and item.product_id is not None:
                    purchased_ids.add(int(item.product_id))

        id_to_product = {p.id: p for p in catalog}
        for pid in purchased_ids:
            product = id_to_product.get(pid)
            if product is None:
                continue
            for c in product.categories or []:
                purchased_category_ids.add(c.id)

        suggestions: List[WooProduct] = []
        for product in catalog:
            if product.id in purchased_ids:
                continue
            if not product.in_stock:
                continue
            if not (purchased_category_ids & {c.id for c in product.categories or []}):
                continue
            suggestions.append(product)

        suggestions.sort(key=lambda p: p.price)
        return suggestions[:limit]
