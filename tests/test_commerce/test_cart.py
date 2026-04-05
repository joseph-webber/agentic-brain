from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from agentic_brain.commerce.chatbot.cart_assistant import CartAssistant, CartLine
from agentic_brain.commerce.models import WooCategory, WooCoupon, WooProduct


def test_cartline_line_total_is_quantity_times_unit_price():
    line = CartLine(product_id=1, name="Test", quantity=3, unit_price=Decimal("2.50"))
    assert line.line_total == Decimal("7.50")


def test_build_summary_subtotal_and_total_match_lines(cart_assistant: CartAssistant):
    lines = [
        CartLine(product_id=1, name="A", quantity=2, unit_price=Decimal("10.00")),
        CartLine(product_id=2, name="B", quantity=1, unit_price=Decimal("5.00")),
    ]
    summary = cart_assistant.build_summary(lines)
    assert summary.subtotal == Decimal("25.00")
    assert summary.total == Decimal("25.00")


def test_build_summary_applies_shipping_and_tax(cart_assistant: CartAssistant):
    lines = [CartLine(product_id=1, name="A", quantity=1, unit_price=Decimal("10.00"))]
    summary = cart_assistant.build_summary(
        lines, shipping_total=Decimal("3.00"), tax_total=Decimal("1.00")
    )
    assert summary.total == Decimal("14.00")


def test_build_summary_negative_discount_is_clamped_to_zero(cart_assistant: CartAssistant):
    lines = [CartLine(product_id=1, name="A", quantity=1, unit_price=Decimal("10.00"))]
    summary = cart_assistant.build_summary(lines, discount_total=Decimal("-2.00"))
    assert summary.discount_total == Decimal("0")
    assert summary.total == Decimal("10.00")


def test_build_summary_total_never_goes_negative(cart_assistant: CartAssistant):
    lines = [CartLine(product_id=1, name="A", quantity=1, unit_price=Decimal("10.00"))]
    summary = cart_assistant.build_summary(lines, discount_total=Decimal("1000.00"))
    assert summary.total == Decimal("0")


def test_apply_coupon_percent_adds_discount(cart_assistant: CartAssistant, cart_summary, coupon_percent):
    updated = cart_assistant.apply_coupon(cart_summary, coupon_percent)
    assert updated.discount_total == cart_summary.subtotal * Decimal("0.10")
    assert "SAVE10" in updated.applied_coupons
    assert updated.total == cart_summary.subtotal - updated.discount_total


def test_apply_coupon_fixed_adds_discount(cart_assistant: CartAssistant, cart_summary, coupon_fixed):
    updated = cart_assistant.apply_coupon(cart_summary, coupon_fixed)
    assert updated.discount_total == coupon_fixed.amount
    assert updated.total == cart_summary.subtotal - coupon_fixed.amount


def test_apply_coupon_string_falls_back_to_ten_percent(cart_assistant: CartAssistant, cart_summary):
    updated = cart_assistant.apply_coupon(cart_summary, "SAVE")
    assert updated.discount_total == cart_summary.subtotal * Decimal("0.10")
    assert "SAVE" in updated.applied_coupons


def test_parse_add_to_cart_intent_extracts_quantity(cart_assistant: CartAssistant):
    intent = cart_assistant.parse_add_to_cart_intent("add 3 cable")
    assert intent["quantity"] == 3
    assert "cable" in intent["query"]


def test_parse_add_to_cart_intent_defaults_to_one(cart_assistant: CartAssistant):
    intent = cart_assistant.parse_add_to_cart_intent("please add adapter")
    assert intent["quantity"] == 1
    assert "adapter" in intent["query"]


def test_suggest_upsells_excludes_cart_items_and_out_of_stock(products):
    assistant = CartAssistant(currency="USD")
    # put product 1 in cart
    cart_products = [products[0]]
    suggestions = assistant.suggest_upsells(cart_products, products, limit=10)
    assert all(p.id != products[0].id for p in suggestions)
    assert all(p.in_stock for p in suggestions)


def test_suggest_upsells_prefers_shared_categories():
    assistant = CartAssistant(currency="USD")
    cat = WooCategory(id=1, name="Cat")
    cart_product = WooProduct(
        id=10, name="Cart", price=Decimal("1"), stock=1, categories=[cat]
    )
    matches = [
        WooProduct(id=11, name="Match", price=Decimal("9"), stock=1, categories=[cat]),
        WooProduct(id=12, name="Other", price=Decimal("10"), stock=1, categories=[]),
    ]
    suggestions = assistant.suggest_upsells([cart_product], matches, limit=5)
    assert [p.id for p in suggestions] == [11]


def test_build_checkout_prompt_includes_totals_and_url(cart_assistant: CartAssistant, cart_summary):
    prompt = cart_assistant.build_checkout_prompt(cart_summary, checkout_url="https://x")
    assert "Subtotal" in prompt
    assert "Checkout link" in prompt


def test_plan_abandonment_recovery_includes_coupon_expiry(cart_assistant: CartAssistant, cart_summary, coupon_fixed):
    plan = cart_assistant.plan_abandonment_recovery(cart_summary, 120, coupon=coupon_fixed)
    assert plan.coupon_code == coupon_fixed.code
    assert plan.expires_at is not None
    assert plan.expires_at > datetime.now(UTC) + timedelta(hours=23)


def test_add_and_remove_items_changes_totals(cart_assistant: CartAssistant):
    lines: list[CartLine] = []
    summary0 = cart_assistant.build_summary(lines)
    assert summary0.total == 0

    lines.append(CartLine(product_id=1, name="A", quantity=1, unit_price=Decimal("10")))
    summary1 = cart_assistant.build_summary(lines)
    assert summary1.total == Decimal("10")

    lines.pop(0)
    summary2 = cart_assistant.build_summary(lines)
    assert summary2.total == 0
