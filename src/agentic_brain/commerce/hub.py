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

"""CommerceHub — unified facade for all commerce subsystems.

Typical usage::

    from agentic_brain.commerce import CommerceHub, CommerceConfig

    config = CommerceConfig.from_env()
    hub = CommerceHub(config)

    # WooCommerce
    products = hub.woo.get_products_sync()

    # WordPress
    # posts = await hub.wp.list_posts()   (async)

    # Payments
    intent = hub.payments.charge(Decimal("99.95"), "AUD", "pm_test_xxx", order_id=42)

    # Shipping
    rates = hub.shipping.get_rates("3000", Dimensions(30, 20, 10, 1.5))

    # Inventory
    report = hub.inventory.get_low_stock_report()

    # Analytics
    sales = hub.analytics.sales_report()
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class WooCommerceConfig:
    """Connection settings for the WooCommerce REST API."""

    url: str = ""
    consumer_key: str = ""
    consumer_secret: str = ""
    verify_ssl: bool = True
    timeout: int = 30

    @classmethod
    def from_env(cls) -> WooCommerceConfig:
        return cls(
            url=os.environ.get("WOO_URL", ""),
            consumer_key=os.environ.get("WOO_CONSUMER_KEY", ""),
            consumer_secret=os.environ.get("WOO_CONSUMER_SECRET", ""),
            verify_ssl=os.environ.get("WOO_VERIFY_SSL", "true").lower() != "false",
            timeout=int(os.environ.get("WOO_TIMEOUT", "30")),
        )


@dataclass
class WordPressConfig:
    """Connection settings for the WordPress REST API."""

    url: str = ""
    username: str = ""
    password: str = ""
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> WordPressConfig:
        return cls(
            url=os.environ.get("WP_URL", ""),
            username=os.environ.get("WP_USERNAME", ""),
            password=os.environ.get("WP_PASSWORD", ""),
            timeout=float(os.environ.get("WP_TIMEOUT", "30")),
        )


@dataclass
class PaymentConfig:
    """Payment gateway API credentials."""

    stripe_secret_key: str = ""
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_sandbox: bool = True
    default_gateway: str = "cod"

    @classmethod
    def from_env(cls) -> PaymentConfig:
        return cls(
            stripe_secret_key=os.environ.get("STRIPE_SECRET_KEY", ""),
            paypal_client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
            paypal_client_secret=os.environ.get("PAYPAL_CLIENT_SECRET", ""),
            paypal_sandbox=os.environ.get("PAYPAL_SANDBOX", "true").lower() != "false",
            default_gateway=os.environ.get("PAYMENT_DEFAULT_GATEWAY", "cod"),
        )


@dataclass
class ShippingConfig:
    """Shipping carrier credentials."""

    auspost_api_key: str = ""
    default_from_postcode: str = "5000"

    @classmethod
    def from_env(cls) -> ShippingConfig:
        return cls(
            auspost_api_key=os.environ.get("AUSPOST_API_KEY", ""),
            default_from_postcode=os.environ.get("AUSPOST_FROM_POSTCODE", "5000"),
        )


@dataclass
class InventoryConfig:
    """Inventory management settings."""

    low_stock_threshold: int = 5

    @classmethod
    def from_env(cls) -> InventoryConfig:
        return cls(
            low_stock_threshold=int(
                os.environ.get("INVENTORY_LOW_STOCK_THRESHOLD", "5")
            ),
        )


@dataclass
class AnalyticsConfig:
    """Analytics settings."""

    default_granularity: str = "day"
    report_currency: str = ""

    @classmethod
    def from_env(cls) -> AnalyticsConfig:
        return cls(
            default_granularity=os.environ.get("ANALYTICS_GRANULARITY", "day"),
            report_currency=os.environ.get("ANALYTICS_CURRENCY", ""),
        )


@dataclass
class CommerceConfig:
    """Top-level configuration for :class:`CommerceHub`.

    Can be built manually or from environment variables via
    :meth:`from_env`.
    """

    woocommerce: WooCommerceConfig = field(default_factory=WooCommerceConfig)
    wordpress: WordPressConfig = field(default_factory=WordPressConfig)
    payments: PaymentConfig = field(default_factory=PaymentConfig)
    shipping: ShippingConfig = field(default_factory=ShippingConfig)
    inventory: InventoryConfig = field(default_factory=InventoryConfig)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)

    @classmethod
    def from_env(cls) -> CommerceConfig:
        """Build config entirely from environment variables."""
        return cls(
            woocommerce=WooCommerceConfig.from_env(),
            wordpress=WordPressConfig.from_env(),
            payments=PaymentConfig.from_env(),
            shipping=ShippingConfig.from_env(),
            inventory=InventoryConfig.from_env(),
            analytics=AnalyticsConfig.from_env(),
        )


# ---------------------------------------------------------------------------
# CommerceHub
# ---------------------------------------------------------------------------


class CommerceHub:
    """Unified facade for all commerce subsystems.

    Wires together :class:`~agentic_brain.commerce.WooCommerceAgent`,
    :class:`~agentic_brain.commerce.WordPressClient`,
    :class:`~agentic_brain.commerce.PaymentProcessor`,
    :class:`~agentic_brain.commerce.ShippingManager`,
    :class:`~agentic_brain.commerce.InventoryManager`, and
    :class:`~agentic_brain.commerce.analytics.WooCommerceAnalytics`
    into a single entry-point.

    Parameters
    ----------
    config:
        A :class:`CommerceConfig` instance.  When ``None`` the config is
        built from environment variables via :meth:`CommerceConfig.from_env`.

    Example::

        hub = CommerceHub(CommerceConfig.from_env())
        report = hub.analytics.sales_report()
        print(report.total_sales)
    """

    def __init__(self, config: Optional[CommerceConfig] = None) -> None:
        self.config = config or CommerceConfig.from_env()
        self._woo: Optional[Any] = None
        self._wp: Optional[Any] = None
        self._payments: Optional[Any] = None
        self._shipping: Optional[Any] = None
        self._inventory: Optional[Any] = None
        self._analytics: Optional[Any] = None
        logger.info("CommerceHub initialised (lazy subsystems)")

    # ------------------------------------------------------------------
    # Lazy subsystem properties — only instantiated when first accessed
    # ------------------------------------------------------------------

    @property
    def woo(self) -> Any:
        """WooCommerce agent (:class:`~agentic_brain.commerce.WooCommerceAgent`)."""
        if self._woo is None:
            from .woocommerce import WooCommerceAgent

            cfg = self.config.woocommerce
            self._woo = WooCommerceAgent(
                url=cfg.url or None,
                consumer_key=cfg.consumer_key or None,
                consumer_secret=cfg.consumer_secret or None,
                verify_ssl=cfg.verify_ssl,
                timeout=cfg.timeout,
            )
            logger.debug("WooCommerceAgent initialised for %s", cfg.url)
        return self._woo

    @property
    def wp(self) -> Any:
        """WordPress client (:class:`~agentic_brain.commerce.WordPressClient`)."""
        if self._wp is None:
            from .wordpress import WordPressClient, WPAuth

            cfg = self.config.wordpress
            auth = WPAuth(
                url=cfg.url or "http://localhost",  # type: ignore[arg-type]
                username=cfg.username,
                password=cfg.password,  # type: ignore[arg-type]
                timeout=cfg.timeout,
            )
            self._wp = WordPressClient(auth=auth)
            logger.debug("WordPressClient initialised for %s", cfg.url)
        return self._wp

    @property
    def payments(self) -> Any:
        """Payment processor (:class:`~agentic_brain.commerce.PaymentProcessor`).

        Gateways are wired from config.  Stripe and PayPal require their
        respective SDK clients to be provided via config; only configured
        gateways are registered.
        """
        if self._payments is None:
            from .payments import (
                PaymentProcessor,
                PayPalGateway,
                StripeGateway,
            )

            cfg = self.config.payments
            gateways: Dict[str, Any] = {}

            if cfg.stripe_secret_key:
                try:
                    import stripe as _stripe  # type: ignore[import]

                    _stripe.api_key = cfg.stripe_secret_key
                    gateways["stripe"] = StripeGateway(client=_stripe)
                except ImportError:
                    logger.warning(
                        "stripe package not installed; Stripe gateway disabled"
                    )

            if cfg.paypal_client_id:
                try:
                    import paypalrestsdk as _pp  # type: ignore[import]

                    _pp.configure(
                        {
                            "mode": "sandbox" if cfg.paypal_sandbox else "live",
                            "client_id": cfg.paypal_client_id,
                            "client_secret": cfg.paypal_client_secret,
                        }
                    )
                    gateways["paypal"] = PayPalGateway(client=_pp)
                except ImportError:
                    logger.warning(
                        "paypalrestsdk not installed; PayPal gateway disabled"
                    )

            if not gateways:
                # Always need at least one gateway; use a no-op stub so the
                # processor can be instantiated even in a test/dev environment.
                class _NullGateway(PaymentProcessor.__class__.__mro__[0]):  # type: ignore[misc]
                    pass

                from .payments import (  # type: ignore[no-redef]
                    PaymentGateway,
                    PaymentRequest,
                    PaymentResult,
                    RefundRequest,
                    RefundResult,
                )

                class _NoOpGateway(PaymentGateway):
                    @property
                    def name(self) -> str:
                        return "noop"

                    def create_payment(self, request: PaymentRequest) -> PaymentResult:
                        return PaymentResult(
                            gateway=self.name,
                            transaction_id="noop-0",
                            status="pending",
                            amount=request.amount,
                            currency=request.currency,
                        )

                    def refund_payment(self, request: RefundRequest) -> RefundResult:
                        return RefundResult(
                            gateway=self.name,
                            refund_id="noop-refund-0",
                            status="refunded",
                            transaction_id=request.transaction_id,
                        )

                gateways["noop"] = _NoOpGateway()
                logger.info(
                    "No payment credentials configured; using no-op gateway. "
                    "Set STRIPE_SECRET_KEY or PAYPAL_CLIENT_ID to enable real payments."
                )

            default = cfg.default_gateway or next(iter(gateways))
            if default not in gateways:
                default = next(iter(gateways))

            self._payments = PaymentProcessor(
                gateways=gateways, default_gateway=default
            )
            logger.debug(
                "PaymentProcessor initialised with gateways: %s", list(gateways)
            )
        return self._payments

    @property
    def shipping(self) -> Any:
        """Shipping manager (:class:`~agentic_brain.commerce.ShippingManager`)."""
        if self._shipping is None:
            from .shipping import ShippingManager

            cfg = self.config.shipping
            self._shipping = ShippingManager(
                auspost_api_key=cfg.auspost_api_key or None,
                default_from_postcode=cfg.default_from_postcode,
            )
            logger.debug(
                "ShippingManager initialised (from postcode %s)",
                cfg.default_from_postcode,
            )
        return self._shipping

    @property
    def inventory(self) -> Any:
        """Inventory manager (:class:`~agentic_brain.commerce.InventoryManager`)."""
        if self._inventory is None:
            from .inventory import InventoryManager

            self._inventory = InventoryManager(
                woo_agent=self.woo,
                low_stock_threshold=self.config.inventory.low_stock_threshold,
            )
            logger.debug(
                "InventoryManager initialised (threshold=%d)",
                self.config.inventory.low_stock_threshold,
            )
        return self._inventory

    @property
    def analytics(self) -> Any:
        """Sales analytics (:class:`~agentic_brain.commerce.analytics.WooCommerceAnalytics`)."""
        if self._analytics is None:
            from .analytics import RequestsWooCommerceAPI, WooCommerceAnalytics

            cfg = self.config.woocommerce
            api = RequestsWooCommerceAPI(
                store_url=cfg.url,
                consumer_key=cfg.consumer_key,
                consumer_secret=cfg.consumer_secret,
            )
            self._analytics = WooCommerceAnalytics(api=api)
            logger.debug("WooCommerceAnalytics initialised")
        return self._analytics

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return a dict summarising subsystem availability."""
        results: Dict[str, Any] = {}

        # WooCommerce ping — try a lightweight sync call
        try:
            _ = self.woo.get_products_sync(params={"per_page": 1})
            results["woocommerce"] = "ok"
        except Exception as exc:
            results["woocommerce"] = f"error: {exc}"

        try:
            results["payments"] = {
                "available_gateways": list(self.payments._gateways.keys())
            }
        except Exception as exc:
            results["payments"] = f"error: {exc}"
        results["shipping"] = {
            "default_from_postcode": self.config.shipping.default_from_postcode
        }
        results["inventory"] = {
            "low_stock_threshold": self.config.inventory.low_stock_threshold
        }
        return results

    def __repr__(self) -> str:
        woo_url = self.config.woocommerce.url or "<not configured>"
        return f"CommerceHub(store={woo_url!r})"
