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

"""Intent detection and context helpers for the WooCommerce chatbot."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum, StrEnum
from typing import Any


class CommerceUserType(StrEnum):
    """Supported WooCommerce chatbot audiences."""

    ADMIN = "admin"
    CUSTOMER = "customer"
    GUEST = "guest"


class CommerceIntent(StrEnum):
    """Commerce-specific intents understood by the chatbot."""

    SHOW_SALES = "show_sales"
    LOW_STOCK = "low_stock"
    PROCESS_REFUND = "process_refund"
    UPDATE_PRICE = "update_price"
    TRACK_ORDER = "track_order"
    RETURN_ITEM = "return_item"
    PURCHASE_HISTORY = "purchase_history"
    RECOMMEND_PRODUCTS = "recommend_products"
    PRODUCT_AVAILABILITY = "product_availability"
    RETURN_POLICY = "return_policy"
    GIFT_SEARCH = "gift_search"
    COMPARE_PRODUCTS = "compare_products"
    FALLBACK = "fallback"


ORDER_ID_RE = re.compile(r"(?:order\s*#?|#)(\d{2,})", re.IGNORECASE)
MONEY_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
UNDER_PRICE_RE = re.compile(
    r"(?:under|below|less than|budget of)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
TO_PRICE_RE = re.compile(
    r"(?:price to|price at|set .* price to|update .* price to)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
COMPARE_RE = re.compile(
    r"compare\s+(?P<left>.+?)\s+(?:and|vs\.?|versus)\s+(?P<right>.+)",
    re.IGNORECASE,
)
PRODUCT_NAME_RE = re.compile(
    r"(?:product|item|price of|price for|like|similar to|find|gift for)\s+['\"]?(?P<name>[A-Za-z0-9][A-Za-z0-9 \-']*[A-Za-z0-9])['\"]?",
    re.IGNORECASE,
)
UPDATE_PRODUCT_RE = re.compile(
    r"(?:update|change|set)\s+(?:product\s+)?(?P<name>.+?)\s+price\s+(?:to|at)\s*\$?\d",
    re.IGNORECASE,
)
QUOTED_NAME_RE = re.compile(r"['\"]([^'\"]{2,})['\"]")
COLOR_RE = re.compile(
    r"\b(black|blue|gold|green|grey|gray|orange|pink|purple|red|silver|white|yellow)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"\b(\d{1,3})\b")


@dataclass(slots=True)
class CommerceEntities:
    """Structured entities extracted from a commerce query."""

    order_ids: list[int] = field(default_factory=list)
    product_names: list[str] = field(default_factory=list)
    price: Decimal | None = None
    max_price: Decimal | None = None
    color: str | None = None
    stock_threshold: int | None = None
    raw_message: str = ""


@dataclass(slots=True)
class CommerceContext:
    """Conversation state carried between chatbot turns."""

    user_type: CommerceUserType
    customer_id: int | None = None
    customer_email: str | None = None
    cart_product_ids: list[int] = field(default_factory=list)
    browsing_history: list[str] = field(default_factory=list)
    last_order_id: int | None = None
    last_product_names: list[str] = field(default_factory=list)
    last_intent: CommerceIntent | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def remember_products(self, product_names: list[str]) -> None:
        """Persist recently discussed products in recency order."""
        for product_name in product_names:
            if not product_name:
                continue
            if product_name in self.last_product_names:
                self.last_product_names.remove(product_name)
            self.last_product_names.insert(0, product_name)
        del self.last_product_names[5:]

    def remember_browse(self, product_names: list[str]) -> None:
        """Persist browsing history with a small bounded history."""
        for product_name in product_names:
            if not product_name:
                continue
            if product_name in self.browsing_history:
                self.browsing_history.remove(product_name)
            self.browsing_history.insert(0, product_name)
        del self.browsing_history[10:]


@dataclass(slots=True)
class IntentMatch:
    """Detected intent with confidence and extracted entities."""

    intent: CommerceIntent
    user_type: CommerceUserType
    confidence: float
    entities: CommerceEntities


class CommerceIntentDetector:
    """Rule-based commerce intent detector for admin, customer, and guest flows."""

    _KEYWORDS: dict[CommerceIntent, tuple[str, ...]] = {
        CommerceIntent.SHOW_SALES: (
            "sales",
            "revenue",
            "orders today",
            "today's sales",
            "todays sales",
        ),
        CommerceIntent.LOW_STOCK: (
            "low stock",
            "low on stock",
            "running low",
            "inventory",
            "stock alert",
        ),
        CommerceIntent.PROCESS_REFUND: (
            "refund",
            "money back",
            "cancel order",
            "refund order",
        ),
        CommerceIntent.UPDATE_PRICE: (
            "update price",
            "change price",
            "price to",
            "set price",
        ),
        CommerceIntent.TRACK_ORDER: (
            "where's my order",
            "wheres my order",
            "track",
            "order status",
            "shipping status",
        ),
        CommerceIntent.RETURN_ITEM: (
            "return this",
            "return item",
            "exchange",
            "send it back",
        ),
        CommerceIntent.PURCHASE_HISTORY: (
            "purchase history",
            "order history",
            "my orders",
            "what have i bought",
        ),
        CommerceIntent.RECOMMEND_PRODUCTS: (
            "recommend",
            "like my last purchase",
            "similar products",
            "you suggest",
        ),
        CommerceIntent.PRODUCT_AVAILABILITY: (
            "do you have",
            "in stock",
            "available",
            "have this in",
        ),
        CommerceIntent.RETURN_POLICY: (
            "return policy",
            "refund policy",
            "returns",
            "exchange policy",
        ),
        CommerceIntent.GIFT_SEARCH: ("gift", "present", "under $", "budget"),
        CommerceIntent.COMPARE_PRODUCTS: (
            "compare",
            "vs",
            "versus",
            "difference between",
        ),
    }

    _USER_HINTS: dict[CommerceUserType, tuple[CommerceIntent, ...]] = {
        CommerceUserType.ADMIN: (
            CommerceIntent.SHOW_SALES,
            CommerceIntent.LOW_STOCK,
            CommerceIntent.PROCESS_REFUND,
            CommerceIntent.UPDATE_PRICE,
        ),
        CommerceUserType.CUSTOMER: (
            CommerceIntent.TRACK_ORDER,
            CommerceIntent.RETURN_ITEM,
            CommerceIntent.PURCHASE_HISTORY,
            CommerceIntent.RECOMMEND_PRODUCTS,
        ),
        CommerceUserType.GUEST: (
            CommerceIntent.PRODUCT_AVAILABILITY,
            CommerceIntent.RETURN_POLICY,
            CommerceIntent.GIFT_SEARCH,
            CommerceIntent.COMPARE_PRODUCTS,
        ),
    }

    def detect(
        self,
        message: str,
        user_type: CommerceUserType,
        context: CommerceContext | None = None,
    ) -> IntentMatch:
        """Detect the most likely commerce intent for the given message."""
        normalized = " ".join(message.lower().split())
        entities = self.extract_entities(message, context=context)
        scores: dict[CommerceIntent, float] = {
            intent: self._score_intent(normalized, intent, entities)
            for intent in CommerceIntent
            if intent is not CommerceIntent.FALLBACK
        }

        for hinted_intent in self._USER_HINTS.get(user_type, ()):
            scores[hinted_intent] += 0.08

        if (
            context
            and context.last_intent is not None
            and normalized.startswith(("and ", "what about", "how about", "also "))
        ):
            scores[context.last_intent] = scores.get(context.last_intent, 0.0) + 0.12

        best_intent = max(scores, key=scores.get, default=CommerceIntent.FALLBACK)
        confidence = max(scores.get(best_intent, 0.0), 0.0)
        if confidence < 0.24:
            best_intent = CommerceIntent.FALLBACK
            confidence = 0.2

        return IntentMatch(
            intent=best_intent,
            user_type=user_type,
            confidence=round(min(confidence, 0.99), 2),
            entities=entities,
        )

    def extract_entities(
        self,
        message: str,
        *,
        context: CommerceContext | None = None,
    ) -> CommerceEntities:
        """Extract order ids, prices, colours, and product references from a query."""
        order_ids = [int(match) for match in ORDER_ID_RE.findall(message)]
        if (
            not order_ids
            and context
            and context.last_order_id is not None
            and any(
                token in message.lower()
                for token in ("that order", "my order", "this order")
            )
        ):
            order_ids = [context.last_order_id]

        quoted_names = [match.strip() for match in QUOTED_NAME_RE.findall(message)]
        update_match = UPDATE_PRODUCT_RE.search(message)
        inline_names = []
        if update_match:
            inline_names.append(update_match.group("name").strip(" ?.!'\""))
        inline_names.extend(
            match.group("name").strip(" ?.!'")
            for match in PRODUCT_NAME_RE.finditer(message)
        )
        compare_match = COMPARE_RE.search(message)
        compared_names: list[str] = []
        if compare_match:
            if len(quoted_names) >= 2:
                compared_names = quoted_names[:2]
            else:
                compared_names = [
                    self._clean_compare_name(compare_match.group("left")),
                    self._clean_compare_name(compare_match.group("right")),
                ]
            inline_names = []
        elif quoted_names:
            inline_names = []

        product_names = self._unique_preserve_order(
            [*quoted_names, *compared_names, *inline_names]
        )
        if (
            not product_names
            and context
            and any(
                token in message.lower() for token in ("this", "that", "it", "them")
            )
        ):
            product_names = list(context.last_product_names[:2])

        color_match = COLOR_RE.search(message)
        color = color_match.group(1).lower() if color_match else None

        price = self._first_decimal(TO_PRICE_RE, message) or self._first_decimal(
            MONEY_RE,
            message,
        )
        max_price = self._first_decimal(UNDER_PRICE_RE, message)
        if max_price is None and any(
            word in message.lower() for word in ("gift", "budget", "under")
        ):
            max_price = price
        if (
            max_price is not None
            and price == max_price
            and not TO_PRICE_RE.search(message)
        ):
            price = None

        stock_threshold = None
        if any(
            token in message.lower()
            for token in ("low stock", "running low", "inventory")
        ):
            numeric_values = [int(match) for match in NUMBER_RE.findall(message)]
            if numeric_values:
                stock_threshold = numeric_values[0]

        return CommerceEntities(
            order_ids=order_ids,
            product_names=product_names,
            price=price,
            max_price=max_price,
            color=color,
            stock_threshold=stock_threshold,
            raw_message=message,
        )

    def _score_intent(
        self,
        normalized_message: str,
        intent: CommerceIntent,
        entities: CommerceEntities,
    ) -> float:
        score = 0.0
        for keyword in self._KEYWORDS.get(intent, ()):
            if keyword in normalized_message:
                score += 0.34

        if intent is CommerceIntent.PROCESS_REFUND and entities.order_ids:
            score += 0.2
        if intent is CommerceIntent.UPDATE_PRICE and entities.price is not None:
            score += 0.25
        if intent is CommerceIntent.TRACK_ORDER and entities.order_ids:
            score += 0.25
        if (
            intent
            in {
                CommerceIntent.PRODUCT_AVAILABILITY,
                CommerceIntent.COMPARE_PRODUCTS,
                CommerceIntent.RECOMMEND_PRODUCTS,
            }
            and entities.product_names
        ):
            score += 0.2
        if (
            intent is CommerceIntent.COMPARE_PRODUCTS
            and len(entities.product_names) >= 2
        ):
            score += 0.35
        if intent is CommerceIntent.GIFT_SEARCH and entities.max_price is not None:
            score += 0.25
        if intent is CommerceIntent.PRODUCT_AVAILABILITY and entities.color:
            score += 0.18
        return score

    @staticmethod
    def _first_decimal(pattern: re.Pattern[str], message: str) -> Decimal | None:
        match = pattern.search(message)
        if not match:
            return None
        try:
            return Decimal(match.group(1))
        except (IndexError, InvalidOperation):
            return None

    @staticmethod
    def _unique_preserve_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = value.strip()
            lowered = normalized.lower()
            if not normalized or lowered in seen:
                continue
            ordered.append(normalized)
            seen.add(lowered)
        return ordered

    @staticmethod
    def _clean_compare_name(value: str) -> str:
        normalized = re.split(
            r"\b(?:under|below|less than|budget of)\b",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        return normalized.strip(" ?.!'\"")


__all__ = [
    "CommerceContext",
    "CommerceEntities",
    "CommerceIntent",
    "CommerceIntentDetector",
    "CommerceUserType",
    "IntentMatch",
]
