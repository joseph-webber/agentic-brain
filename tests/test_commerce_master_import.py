# SPDX-License-Identifier: Apache-2.0
"""Master smoke tests for the commerce surface area.

These tests act as a coordination gate for the WooCommerce / WordPress
commerce stack. They verify that all core modules import correctly and that
key public symbols are available from the documented import paths.
"""

from __future__ import annotations

import importlib
from typing import Iterable

COMMERCE_MODULE_PATHS: list[str] = [
    "agentic_brain.commerce",
    "agentic_brain.commerce.analytics",
    "agentic_brain.commerce.chatbot",
    "agentic_brain.commerce.chatbot.chatbot",
    "agentic_brain.commerce.hub",
    "agentic_brain.commerce.inventory",
    "agentic_brain.commerce.models",
    "agentic_brain.commerce.payments",
    "agentic_brain.commerce.shipping",
    "agentic_brain.commerce.webhooks",
    "agentic_brain.commerce.wordpress",
    "agentic_brain.commerce.wordpress_cms",
    "agentic_brain.commerce.woocommerce",
]

# Core exports we expect to be present on the commerce namespace
CORE_COMMERCE_EXPORTS: list[str] = [
    # Agents & hub
    "WooCommerceAgent",
    "CommerceHub",
    "CommerceConfig",
    "WooCommerceConfig",
    "WordPressConfig",
    # Chatbot
    "WooCommerceChatbot",
    "ChatWidgetConfig",
    "ChatbotReply",
    "CommerceContext",
    "CommerceEntities",
    "CommerceIntent",
    "CommerceIntentDetector",
    "CommerceUserType",
    "IntentMatch",
    "ResponseTemplates",
    # Analytics facade
    "WooCommerceAnalytics",
]

# All Pydantic models that should be exported from commerce.__init__
MODEL_EXPORTS: list[str] = [
    "WooAddress",
    "WooBaseModel",
    "WooCategory",
    "WooCoupon",
    "WooCustomer",
    "WooOrder",
    "WooOrderItem",
    "WooOrderTotals",
    "WooProduct",
    "WooProductImage",
    "WooTag",
]

# Convenience exports that must resolve from the top-level package via
# agentic_brain.<Name>. These are wired through _LAZY_EXPORTS.
TOP_LEVEL_COMMERCE_EXPORTS: list[str] = [
    # Core agent & hub
    "WooCommerceAgent",
    "CommerceHub",
    "CommerceConfig",
    # WordPress client
    "WordPressClient",
    "WPAuth",
    "WPMedia",
    "WPPage",
    "WPPost",
    "WPRenderedText",
    # Woo models
    "WooBaseModel",
    "WooProduct",
    "WooOrder",
    "WooOrderItem",
    "WooOrderTotals",
    "WooCustomer",
    "WooCoupon",
    "WooProductImage",
    "WooTag",
    "WooAddress",
    # Payments
    "PaymentGateway",
    "PaymentIntent",
    "PaymentProcessor",
    "PaymentRequest",
    "PaymentResult",
    "RefundRequest",
    "RefundResult",
    "SubscriptionRequest",
    "TransactionRecord",
    "PaymentError",
    "PaymentSecurityError",
    "PaymentOperationNotSupported",
    "FraudRejectedError",
    "GatewayType",
    "PaymentStatus",
    "CashOnDeliveryGateway",
    "StripeGateway",
    "PayPalGateway",
    "SquareGateway",
    "WebhookEvent",
]


def _assert_has_attrs(obj: object, names: Iterable[str]) -> None:
    for name in names:
        assert hasattr(obj, name), f"Missing expected attribute {name!r} on {obj!r}"


def test_commerce_modules_are_importable() -> None:
    """Every commerce submodule should import cleanly.

    This catches missing dependencies or circular import regressions early.
    """

    for module_path in COMMERCE_MODULE_PATHS:
        mod = importlib.import_module(module_path)
        assert mod is not None


def test_commerce_namespace_core_exports() -> None:
    """agentic_brain.commerce must expose the documented core exports."""

    commerce = importlib.import_module("agentic_brain.commerce")

    _assert_has_attrs(commerce, CORE_COMMERCE_EXPORTS)
    _assert_has_attrs(commerce, MODEL_EXPORTS)


def test_from_commerce_imports_work() -> None:
    """Ensure the common from-import patterns are valid.

    These mirror the examples used in README.md and CHANGELOG.md.
    """

    from agentic_brain.commerce import (  # noqa: F401
        CommerceConfig,
        CommerceHub,
        WooBaseModel,
        WooCommerceAgent,
        WooCommerceAnalytics,
        WooCommerceChatbot,
        WooCommerceConfig,
        WooCoupon,
        WooCustomer,
        WooOrder,
        WooProduct,
        WordPressClient,
        WordPressConfig,
    )

    # The import above is the assertion; if it fails, pytest will error.


def test_top_level_lazy_commerce_exports() -> None:
    """agentic_brain package must expose the key commerce shortcuts.

    This verifies the lazily-loaded exports wired in _LAZY_EXPORTS.
    """

    brain = importlib.import_module("agentic_brain")

    _assert_has_attrs(brain, TOP_LEVEL_COMMERCE_EXPORTS)

    # Spot-check a couple of attribute types still line up with commerce
    # namespace exports.
    commerce = importlib.import_module("agentic_brain.commerce")
    assert brain.WooCommerceAgent is commerce.WooCommerceAgent
    assert brain.WooProduct is commerce.WooProduct
    assert brain.WordPressClient is commerce.WordPressClient
