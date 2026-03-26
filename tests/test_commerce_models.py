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

"""Integration tests for WooCommerce commerce models and WordPress client."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from agentic_brain import WooCustomer, WooOrder, WooProduct, WordPressClient, WPAuth
from agentic_brain.commerce import WPMedia, WPPage, WPPost


def test_woocommerce_product_and_order_validation():
    product = WooProduct.model_validate(
        {
            "id": 101,
            "name": "Braille Keyboard",
            "price": "199.95",
            "description": "Accessible mechanical keyboard",
            "sku": "BK-101",
            "stock": 3,
            "categories": [{"id": 1, "name": "Accessibility", "slug": "accessibility"}],
            "images": [
                {
                    "id": 55,
                    "src": "https://example.com/images/braille-keyboard.jpg",
                    "alt": "Braille keyboard on a desk",
                }
            ],
        }
    )

    assert product.price == Decimal("199.95")
    assert product.in_stock is True
    assert product.categories[0].name == "Accessibility"

    customer = WooCustomer.model_validate(
        {
            "id": 9,
            "email": "customer@example.com",
            "name": "Joseph Webber",
            "billing_address": {
                "first_name": "Joseph",
                "last_name": "Webber",
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "au",
            },
            "shipping_address": {
                "first_name": "Joseph",
                "last_name": "Webber",
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "AU",
            },
        }
    )

    order = WooOrder.model_validate(
        {
            "id": 5001,
            "status": "processing",
            "customer": customer.model_dump(),
            "items": [
                {
                    "id": 1,
                    "product_id": product.id,
                    "name": product.name,
                    "quantity": 2,
                    "price": "199.95",
                    "total": "399.90",
                }
            ],
            "totals": {
                "subtotal": "399.90",
                "discount_total": "10.00",
                "shipping_total": "15.00",
                "tax_total": "5.10",
                "total": "410.00",
                "currency": "aud",
            },
            "billing": customer.billing_address.model_dump(),
            "shipping": customer.shipping_address.model_dump(),
        }
    )

    assert order.totals.currency == "AUD"
    assert order.billing.email == "customer@example.com"


def test_woocommerce_validation_rejects_invalid_values():
    with pytest.raises(ValidationError):
        WooProduct.model_validate(
            {
                "id": 1,
                "name": "Invalid Product",
                "price": "10.00",
                "stock": 2,
                "in_stock": False,
                "description": "Bad stock state",
                "categories": [],
                "images": [],
            }
        )

    with pytest.raises(ValidationError):
        WooCustomer.model_validate(
            {
                "id": 3,
                "email": "not-an-email",
                "name": "Broken Customer",
                "billing_address": {"country": "AU"},
                "shipping_address": {"country": "AU"},
            }
        )


@pytest.mark.asyncio
async def test_wordpress_client_validates_posts_pages_and_media():
    auth = WPAuth(
        base_url="https://example.com/",
        username="editor",
        application_password="app-password",
    )
    requests: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            (request.method, str(request.url), request.headers.get("authorization", ""))
        )
        if request.url.path.endswith("/posts"):
            assert request.url.params.get("search") == "hello"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 10,
                        "slug": "hello-world",
                        "status": "publish",
                        "link": "https://example.com/hello-world",
                        "title": {"rendered": "Hello World"},
                        "content": {"rendered": "<p>Hello</p>"},
                        "excerpt": {"rendered": "Excerpt"},
                    }
                ],
            )
        if request.url.path.endswith("/pages"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 11,
                        "slug": "about",
                        "status": "publish",
                        "link": "https://example.com/about",
                        "title": {"rendered": "About"},
                        "content": {"rendered": "<p>About page</p>"},
                        "excerpt": {"rendered": "About excerpt"},
                    }
                ],
            )
        if request.url.path.endswith("/media"):
            assert request.url.params.get("per_page") == "5"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 12,
                        "slug": "hero-image",
                        "status": "inherit",
                        "link": "https://example.com/media/hero-image",
                        "title": {"rendered": "Hero Image"},
                        "media_type": "image",
                        "mime_type": "image/jpeg",
                        "source_url": "https://example.com/uploads/hero-image.jpg",
                    }
                ],
            )
        raise AssertionError(f"Unexpected URL {request.url}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WordPressClient(config=auth, client=http_client)
        posts = await client.posts(search="hello")
        pages = await client.pages()
        media = await client.media(per_page=5)

    assert isinstance(posts[0], WPPost)
    assert isinstance(pages[0], WPPage)
    assert isinstance(media[0], WPMedia)
    assert posts[0].title.rendered == "Hello World"
    assert auth.rest_base_url == "https://example.com/wp-json/wp/v2"
    assert auth.basic_auth() is not None
    assert [req[:2] for req in requests] == [
        ("GET", "https://example.com/wp-json/wp/v2/posts?search=hello"),
        ("GET", "https://example.com/wp-json/wp/v2/pages"),
        ("GET", "https://example.com/wp-json/wp/v2/media?per_page=5"),
    ]
    assert requests[0][2].startswith("Basic ")


def test_wordpress_auth_validates_credentials():
    with pytest.raises(ValidationError):
        WPAuth(base_url="example.com")

    with pytest.raises(ValidationError):
        WPAuth(base_url="https://example.com", application_password="secret-app")
