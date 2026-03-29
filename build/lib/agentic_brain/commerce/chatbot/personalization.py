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
"""Personalization primitives for commerce chatbot experiences."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping

from ..models import WooOrder, WooProduct


@dataclass(frozen=True)
class PersonaProfile:
    persona: str
    confidence: float
    signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PurchaseHistoryInsights:
    total_orders: int
    total_spend: Decimal
    average_order_value: Decimal
    favorite_categories: list[int] = field(default_factory=list)
    favorite_product_ids: list[int] = field(default_factory=list)
    recency_segment: str = "new"


@dataclass(frozen=True)
class BrowsingProfile:
    top_categories: list[int] = field(default_factory=list)
    top_product_ids: list[int] = field(default_factory=list)
    preferred_price_band: str = "mid"
    engagement_score: float = 0.0
    intent_stage: str = "discovery"


@dataclass(frozen=True)
class PersonalizedProductRecommendation:
    product_id: int
    product_name: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DynamicPricingSuggestion:
    strategy: str
    suggested_discount_percent: Decimal
    suggested_price: Decimal | None
    rationale: list[str] = field(default_factory=list)
    urgency: str = "normal"


class ChatbotPersonalization:
    """Deterministic personalization engine for store assistants."""

    def detect_persona(
        self,
        *,
        customer: Mapping[str, object] | None = None,
        purchase_history: PurchaseHistoryInsights | None = None,
        browsing_profile: BrowsingProfile | None = None,
    ) -> PersonaProfile:
        signals: list[str] = []
        scores: defaultdict[str, int] = defaultdict(int)

        if purchase_history:
            if purchase_history.total_orders >= 5:
                scores["loyal_repeat_buyer"] += 3
                signals.append("Multiple completed orders")
            if purchase_history.average_order_value >= Decimal("200"):
                scores["premium_buyer"] += 3
                signals.append("High average order value")
            if purchase_history.total_spend >= Decimal("1000"):
                scores["vip"] += 4
                signals.append("High lifetime value")
            if purchase_history.total_orders <= 1:
                scores["new_customer"] += 2
                signals.append("Limited purchase history")

        if browsing_profile:
            if browsing_profile.intent_stage == "decision":
                scores["researcher"] += 2
                signals.append("Near-purchase browsing behavior")
            if browsing_profile.preferred_price_band == "budget":
                scores["bargain_hunter"] += 3
                signals.append("Budget-oriented browsing")
            if browsing_profile.engagement_score < 1.5:
                scores["window_shopper"] += 2
                signals.append("Low engagement depth")
            if len(browsing_profile.top_product_ids) >= 3:
                scores["researcher"] += 1
                signals.append("Repeated product comparisons")

        if customer:
            raw_tags = customer.get("tags", [])
            tags = (
                {str(tag).lower() for tag in raw_tags}
                if isinstance(raw_tags, list)
                else set()
            )
            if {"vip", "wholesale", "enterprise"} & tags:
                scores["vip"] += 4
                signals.append("Account tagged for priority treatment")

        if not scores:
            return PersonaProfile(
                persona="general_shopper",
                confidence=0.35,
                signals=["No strong persona signals yet"],
            )

        persona, top_score = max(scores.items(), key=lambda item: item[1])
        confidence = min(0.45 + (top_score * 0.1), 0.97)
        return PersonaProfile(
            persona=persona, confidence=round(confidence, 2), signals=signals
        )

    def analyze_purchase_history(
        self, orders: Iterable[WooOrder]
    ) -> PurchaseHistoryInsights:
        order_list = list(orders)
        total_orders = len(order_list)
        total_spend = sum(
            (order.totals.total for order in order_list), start=Decimal("0")
        )
        average_order_value = (
            (total_spend / total_orders) if total_orders else Decimal("0")
        )

        product_counter: Counter[int] = Counter()
        for order in order_list:
            for item in order.items:
                if item.product_id is not None:
                    product_counter[int(item.product_id)] += item.quantity

        if total_orders >= 6:
            recency_segment = "established"
        elif total_orders >= 2:
            recency_segment = "active"
        elif total_orders == 1:
            recency_segment = "new"
        else:
            recency_segment = "prospect"

        return PurchaseHistoryInsights(
            total_orders=total_orders,
            total_spend=total_spend.quantize(Decimal("0.01")),
            average_order_value=average_order_value.quantize(Decimal("0.01")),
            favorite_categories=[],
            favorite_product_ids=[
                product_id for product_id, _ in product_counter.most_common(5)
            ],
            recency_segment=recency_segment,
        )

    def track_browsing_behavior(
        self, events: Iterable[Mapping[str, object]]
    ) -> BrowsingProfile:
        category_counter: Counter[int] = Counter()
        product_counter: Counter[int] = Counter()
        price_points: list[Decimal] = []
        engagement = 0.0
        stage = "discovery"

        for event in events:
            event_type = str(event.get("event", "")).lower()
            category_id = event.get("category_id")
            product_id = event.get("product_id")
            if isinstance(category_id, int):
                category_counter[category_id] += 1
            if isinstance(product_id, int):
                product_counter[product_id] += 1
            if event.get("price") is not None:
                price_points.append(Decimal(str(event["price"])))
            if event_type in {"view_product", "search", "view_category"}:
                engagement += 0.5
            elif event_type in {"compare", "wishlist", "add_to_cart"}:
                engagement += 1.25
                stage = "evaluation"
            elif event_type in {"checkout_start", "payment_attempt"}:
                engagement += 2.0
                stage = "decision"

        preferred_price_band = "mid"
        if price_points:
            avg_price = sum(price_points, start=Decimal("0")) / len(price_points)
            if avg_price < Decimal("50"):
                preferred_price_band = "budget"
            elif avg_price > Decimal("200"):
                preferred_price_band = "premium"

        return BrowsingProfile(
            top_categories=[
                category_id for category_id, _ in category_counter.most_common(5)
            ],
            top_product_ids=[
                product_id for product_id, _ in product_counter.most_common(5)
            ],
            preferred_price_band=preferred_price_band,
            engagement_score=round(engagement, 2),
            intent_stage=stage,
        )

    def personalized_recommendations(
        self,
        *,
        catalog: Iterable[WooProduct],
        purchase_history: PurchaseHistoryInsights | None = None,
        browsing_profile: BrowsingProfile | None = None,
        persona: PersonaProfile | None = None,
        limit: int = 5,
    ) -> list[PersonalizedProductRecommendation]:
        history_products = set(
            purchase_history.favorite_product_ids if purchase_history else []
        )
        browsing_products = set(
            browsing_profile.top_product_ids if browsing_profile else []
        )
        browsing_categories = set(
            browsing_profile.top_categories if browsing_profile else []
        )

        recommendations: list[PersonalizedProductRecommendation] = []
        for product in catalog:
            if not product.in_stock:
                continue
            score = Decimal("0")
            reasons: list[str] = []
            product_categories = {category.id for category in product.categories}

            if purchase_history and product.id in history_products:
                continue
            if browsing_categories and product_categories & browsing_categories:
                score += Decimal("2.0")
                reasons.append("Aligned with recent browsing behavior")
            if browsing_profile and product.id in browsing_products:
                score += Decimal("3.0")
                reasons.append("Customer revisited this item recently")
            if (
                persona
                and persona.persona == "bargain_hunter"
                and product.price <= Decimal("50")
            ):
                score += Decimal("1.5")
                reasons.append("Fits a value-focused shopper profile")
            if (
                persona
                and persona.persona in {"premium_buyer", "vip"}
                and product.price >= Decimal("150")
            ):
                score += Decimal("1.5")
                reasons.append("Fits premium purchase behavior")
            if not reasons:
                score += Decimal("0.5")
                reasons.append("General in-stock recommendation")

            recommendations.append(
                PersonalizedProductRecommendation(
                    product_id=product.id,
                    product_name=product.name,
                    score=float(score),
                    reasons=reasons,
                )
            )

        recommendations.sort(key=lambda rec: rec.score, reverse=True)
        return recommendations[:limit]

    def dynamic_pricing_suggestions(
        self,
        *,
        product: WooProduct,
        persona: PersonaProfile | None = None,
        purchase_history: PurchaseHistoryInsights | None = None,
        cart_total: Decimal | None = None,
        inventory_pressure: float = 0.0,
    ) -> DynamicPricingSuggestion:
        discount = Decimal("0")
        rationale: list[str] = []
        strategy = "hold_price"
        urgency = "normal"

        if persona and persona.persona in {"vip", "loyal_repeat_buyer"}:
            discount += Decimal("5")
            rationale.append("Reward loyalty with a retention offer")
            strategy = "loyalty_offer"
        if persona and persona.persona == "bargain_hunter":
            discount += Decimal("7")
            rationale.append("Price-sensitive persona detected")
            strategy = "conversion_offer"
        if purchase_history and purchase_history.total_orders == 0:
            discount += Decimal("3")
            rationale.append("Welcome incentive for first purchase")
            strategy = "welcome_offer"
        if cart_total is not None and cart_total >= Decimal("150"):
            discount += Decimal("2")
            rationale.append("Encourage checkout completion on a high-value cart")
        if inventory_pressure >= 0.8:
            discount += Decimal("4")
            rationale.append("Inventory pressure suggests a faster sell-through")
            urgency = "elevated"
            strategy = "inventory_clearance"

        if product.price < Decimal("20"):
            discount = min(discount, Decimal("5"))
            rationale.append("Protect margin on low-priced items")

        if discount == 0:
            suggested_price = product.price
            rationale.append("Current list price is appropriate")
        else:
            suggested_price = (
                product.price * (Decimal("100") - discount) / Decimal("100")
            ).quantize(Decimal("0.01"))

        return DynamicPricingSuggestion(
            strategy=strategy,
            suggested_discount_percent=discount,
            suggested_price=suggested_price,
            rationale=rationale,
            urgency=urgency,
        )


__all__ = [
    "BrowsingProfile",
    "ChatbotPersonalization",
    "DynamicPricingSuggestion",
    "PersonaProfile",
    "PersonalizedProductRecommendation",
    "PurchaseHistoryInsights",
]
