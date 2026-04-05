#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""WooCommerce quickstart example.

Real working example for common WooCommerce tasks:
- list products
- search products
- create a product
- update inventory
- create an order
- advance an order through its lifecycle

Usage examples:
    python3 examples/woocommerce_quickstart.py list-products --per-page 5
    python3 examples/woocommerce_quickstart.py search-products braille
    python3 examples/woocommerce_quickstart.py create-product \
        --name "Accessible Keyboard" \
        --sku AK-100 \
        --price 199.95 \
        --stock 10
    python3 examples/woocommerce_quickstart.py update-stock 101 --stock 3
    python3 examples/woocommerce_quickstart.py create-order --product-id 101 --email joseph@example.com
    python3 examples/woocommerce_quickstart.py complete-order 5001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_brain.commerce import WooCommerceAgent  # noqa: E402

REQUIRED_ENV_VARS = (
    "WOOCOMMERCE_URL",
    "WOOCOMMERCE_CONSUMER_KEY",
    "WOOCOMMERCE_CONSUMER_SECRET",
)


def build_agent() -> WooCommerceAgent:
    """Create a WooCommerce agent from environment configuration."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return WooCommerceAgent(
        url=os.environ["WOOCOMMERCE_URL"],
        consumer_key=os.environ["WOOCOMMERCE_CONSUMER_KEY"],
        consumer_secret=os.environ["WOOCOMMERCE_CONSUMER_SECRET"],
        verify_ssl=os.getenv("WOOCOMMERCE_VERIFY_SSL", "true").lower() != "false",
        timeout=int(os.getenv("WOOCOMMERCE_TIMEOUT", "30")),
    )


def pretty_print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


async def list_products(agent: WooCommerceAgent, per_page: int) -> None:
    products = await agent.sync_products({"per_page": per_page})
    pretty_print([product.model_dump(mode="json") for product in products])


async def search_products(agent: WooCommerceAgent, query: str) -> None:
    pretty_print(await agent.search_products(query))


async def create_product(
    agent: WooCommerceAgent,
    *,
    name: str,
    sku: str,
    price: str,
    stock: int,
    description: str,
) -> None:
    created = await agent.create_product(
        {
            "name": name,
            "type": "simple",
            "regular_price": price,
            "price": price,
            "description": description,
            "sku": sku,
            "stock": stock,
            "in_stock": stock > 0,
            "manage_stock": True,
        }
    )
    pretty_print(created)


async def update_stock(agent: WooCommerceAgent, product_id: int, stock: int) -> None:
    updated = await agent.update_inventory(product_id=product_id, stock=stock)
    pretty_print(updated)


async def create_order(agent: WooCommerceAgent, product_id: int, email: str) -> None:
    order = await agent.create_order(
        {
            "payment_method": "stripe",
            "payment_method_title": "Stripe",
            "billing": {
                "first_name": "TestUser",
                "last_name": "Webber",
                "email": email,
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "AU",
            },
            "shipping": {
                "first_name": "TestUser",
                "last_name": "Webber",
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "AU",
            },
            "line_items": [{"product_id": product_id, "quantity": 1}],
        }
    )
    pretty_print(order)


async def complete_order(agent: WooCommerceAgent, order_id: int) -> None:
    await agent.update_order(order_id, {"status": "processing", "set_paid": True})
    completed = await agent.update_order(order_id, {"status": "completed"})
    pretty_print(completed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WooCommerce quickstart example")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-products", help="List products")
    list_parser.add_argument("--per-page", type=int, default=10)

    search_parser = subparsers.add_parser("search-products", help="Search products")
    search_parser.add_argument("query")

    create_parser = subparsers.add_parser("create-product", help="Create a product")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--sku", required=True)
    create_parser.add_argument("--price", required=True)
    create_parser.add_argument("--stock", type=int, default=0)
    create_parser.add_argument(
        "--description",
        default="Accessible product created by the agentic-brain WooCommerce quickstart example.",
    )

    stock_parser = subparsers.add_parser("update-stock", help="Update inventory")
    stock_parser.add_argument("product_id", type=int)
    stock_parser.add_argument("--stock", type=int, required=True)

    order_parser = subparsers.add_parser("create-order", help="Create an order")
    order_parser.add_argument("--product-id", type=int, required=True)
    order_parser.add_argument("--email", required=True)

    complete_parser = subparsers.add_parser(
        "complete-order", help="Advance an order to completed"
    )
    complete_parser.add_argument("order_id", type=int)

    return parser


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    agent = build_agent()

    if args.command == "list-products":
        await list_products(agent, args.per_page)
    elif args.command == "search-products":
        await search_products(agent, args.query)
    elif args.command == "create-product":
        await create_product(
            agent,
            name=args.name,
            sku=args.sku,
            price=args.price,
            stock=args.stock,
            description=args.description,
        )
    elif args.command == "update-stock":
        await update_stock(agent, args.product_id, args.stock)
    elif args.command == "create-order":
        await create_order(agent, args.product_id, args.email)
    elif args.command == "complete-order":
        await complete_order(agent, args.order_id)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    asyncio.run(main())
