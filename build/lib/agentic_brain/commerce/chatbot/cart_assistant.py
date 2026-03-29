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
"""High-level cart helpers for conversational shopping.

This module does **not** talk to WooCommerce directly; instead it accepts
already-fetched products, coupons and cart items and turns them into
chat-friendly primitives. The LLM can then turn those primitives into
natural language responses.

Design goals
------------
- Stateless, pure functions where possible (easy to test)
- Deterministic outputs from simple inputs (good for unit tests)
- No network or database access
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, List, Optional

from ..models import WooCoupon, WooProduct

Money = Decimal


@dataclass(frozen=True)
class CartLine:
    """Single line in a cart.

    The chatbot layer should resolve WooProduct objects first and then
    construct CartLine records from them.
    """

    product_id: int
    name: str
    quantity: int
    unit_price: Money

    @property
    def line_total(self) -> Money:
        return (self.unit_price or Decimal("0")) * self.quantity


@dataclass(frozen=True)
class CartSummary:
    """Computed view of a cart that is easy to verbalise."""

    lines: List[CartLine] = field(default_factory=list)
    subtotal: Money = Decimal("0")
    discount_total: Money = Decimal("0")
    shipping_total: Money = Decimal("0")
    tax_total: Money = Decimal("0")
    total: Money = Decimal("0")
    currency: str = "USD"
    applied_coupons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CartRecoveryPlan:
    """Plan for recovering an abandoned cart.

    The LLM can turn this into one or more persuasive messages.
    """

    message: str
    incentive: Optional[str] = None
    coupon_code: Optional[str] = None
    expires_at: Optional[datetime] = None


class CartAssistant:
    """Pure-python helper for cart-related chatbot flows.

    This class intentionally does not depend on any HTTP clients so it
    can run both in unit tests and inside LLM tools.
    """

    def __init__(self, currency: str = "USD") -> None:
        self.currency = currency.upper() if currency else "USD"

    # ------------------------------------------------------------------
    # Cart summaries
    # ------------------------------------------------------------------

    def build_summary(
        self,
        lines: Iterable[CartLine],
        *,
        discount_total: Money | None = None,
        shipping_total: Money | None = None,
        tax_total: Money | None = None,
        applied_coupons: Optional[Iterable[str]] = None,
    ) -> CartSummary:
        """Compute a :class:`CartSummary` from raw lines.

        All monetary maths happen here so the LLM only has to narrate
        the result.
        """

        line_list = list(lines)
        subtotal = sum((l.line_total for l in line_list), start=Decimal("0"))
        discount = discount_total if discount_total is not None else Decimal("0")
        shipping = shipping_total if shipping_total is not None else Decimal("0")
        tax = tax_total if tax_total is not None else Decimal("0")

        if discount < 0:
            discount = Decimal("0")

        total = subtotal - discount + shipping + tax
        if total < 0:
            total = Decimal("0")

        coupons = [c.upper() for c in (applied_coupons or [])]

        return CartSummary(
            lines=line_list,
            subtotal=subtotal,
            discount_total=discount,
            shipping_total=shipping,
            tax_total=tax,
            total=total,
            currency=self.currency,
            applied_coupons=coupons,
        )

    # ------------------------------------------------------------------
    # Upsell / cross-sell
    # ------------------------------------------------------------------

    def suggest_upsells(
        self,
        cart_products: Iterable[WooProduct],
        catalog_products: Iterable[WooProduct],
        *,
        limit: int = 3,
    ) -> List[WooProduct]:
        """Return simple upsell candidates.

        Strategy:
        - Exclude products already in the cart
        - Prefer products that share at least one category with the cart
        - Filter to in-stock products only
        - Return up to ``limit`` suggestions ordered by price descending
        """

        cart_ids = {p.id for p in cart_products}
        cart_category_ids = {c.id for p in cart_products for c in (p.categories or [])}

        candidates: List[WooProduct] = []
        for product in catalog_products:
            if product.id in cart_ids:
                continue
            if not product.in_stock:
                continue
            product_category_ids = {c.id for c in product.categories or []}
            if cart_category_ids and not (product_category_ids & cart_category_ids):
                continue
            candidates.append(product)

        candidates.sort(key=lambda p: p.price, reverse=True)
        return candidates[:limit]

    # ------------------------------------------------------------------
    # Discounts
    # ------------------------------------------------------------------

    def apply_coupon(
        self,
        summary: CartSummary,
        coupon: WooCoupon | str,
    ) -> CartSummary:
        """Return a new :class:`CartSummary` with coupon applied.

        This is a *simulation* only – it does not talk to WooCommerce
        and therefore cannot enforce all rules. The goal is to give the
        chatbot something deterministic it can explain to the customer.
        """

        if isinstance(coupon, WooCoupon):
            code = coupon.code.upper()
            if coupon.discount_type == "percent":
                discount_amount = (summary.subtotal * coupon.amount) / Decimal("100")
            else:
                discount_amount = coupon.amount
        else:
            code = str(coupon).upper()
            # Fallback: 10% preview so the chatbot can say
            # "around 10% off" even without full metadata.
            discount_amount = (summary.subtotal * Decimal("10")) / Decimal("100")

        new_discount = summary.discount_total + discount_amount
        return self.build_summary(
            summary.lines,
            discount_total=new_discount,
            shipping_total=summary.shipping_total,
            tax_total=summary.tax_total,
            applied_coupons=list(summary.applied_coupons) + [code],
        )

    # ------------------------------------------------------------------
    # Add to cart via chat (intent parsing)
    # ------------------------------------------------------------------

    def parse_add_to_cart_intent(self, message: str) -> dict:
        """Parse a free-text message into a structured intent.

        The LLM can refine this, but having a deterministic baseline
        makes it easy to write tests and debug behaviour.

        Returns a dictionary with keys:
        - ``query``: product search query
        - ``quantity``: integer quantity (default 1)
        """

        text = (message or "").strip()
        if not text:
            return {"query": "", "quantity": 1}

        lower = text.lower()
        quantity = 1
        tokens = lower.split()
        for i, tok in enumerate(tokens):
            if tok.isdigit():
                quantity = int(tok)
                # Remove quantity token from the query
                tokens.pop(i)
                break

        for prefix in ("add ", "i want ", "please add ", "put "):
            if lower.startswith(prefix):
                lower = lower[len(prefix) :]
                break

        query = lower.strip()
        if not query:
            query = text

        return {"query": query, "quantity": max(quantity, 1)}

    # ------------------------------------------------------------------
    # Cart abandonment / checkout
    # ------------------------------------------------------------------

    def build_checkout_prompt(
        self, summary: CartSummary, checkout_url: str | None = None
    ) -> str:
        """Return a brief human-readable summary suitable for voice."""

        parts = [
            f"You have {len(summary.lines)} item(s) in your cart.",
            f"Subtotal is {summary.currency} {summary.subtotal:.2f}.",
        ]
        if summary.discount_total > 0:
            parts.append(
                f"Discounts of {summary.currency} {summary.discount_total:.2f} are applied."
            )
        if summary.shipping_total > 0:
            parts.append(
                f"Estimated shipping is {summary.currency} {summary.shipping_total:.2f}."
            )
        parts.append(f"Total is {summary.currency} {summary.total:.2f}.")
        if checkout_url:
            parts.append(f"Checkout link: {checkout_url}.")
        return " ".join(parts)

    def plan_abandonment_recovery(
        self,
        summary: CartSummary,
        minutes_since_last_activity: int,
        coupon: WooCoupon | None = None,
    ) -> CartRecoveryPlan:
        """Create a simple recovery plan for an abandoned cart."""

        base_msg = "You left items in your cart."
        if minutes_since_last_activity > 60:
            base_msg = "It's been a while since you looked at your cart."

        incentive = None
        coupon_code: Optional[str] = None
        expires_at: Optional[datetime] = None

        if coupon is not None:
            incentive = f"Apply coupon {coupon.code} for a discount."
            coupon_code = coupon.code
            expires_at = datetime.now(UTC) + timedelta(hours=24)

        total_str = f"Your cart total is {summary.currency} {summary.total:.2f}."
        message = f"{base_msg} {total_str}"

        return CartRecoveryPlan(
            message=message,
            incentive=incentive,
            coupon_code=coupon_code,
            expires_at=expires_at,
        )
