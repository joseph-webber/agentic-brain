# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Tests for WooCommerceAgent."""

import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from agentic_brain.commerce.woocommerce import WooCommerceAgent


class TestWooCommerceAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.url = "https://example.com"
        self.key = "ck_test"
        self.secret = "cs_test"
        self.agent = WooCommerceAgent(self.url, self.key, self.secret)

    def test_init(self):
        self.assertEqual(self.agent.url, "https://example.com")
        self.assertEqual(self.agent.consumer_key, "ck_test")
        self.assertEqual(self.agent.consumer_secret, "cs_test")

    @patch("agentic_brain.commerce.woocommerce.requests.Session")
    async def test_get_products(self, mock_session):
        # Mock the session instance
        mock_instance = mock_session.return_value
        # Mock the request method on the instance
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "name": "Test Product"}]
        mock_response.status_code = 200
        mock_instance.request.return_value = mock_response

        # Need to patch the session created in __init__?
        # No, __init__ creates it. So we should patch where it is used or inject it.
        # Easier to mock _session attribute directly.
        self.agent._session = mock_instance

        products = await self.agent.get_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Test Product")

        mock_instance.request.assert_called_with(
            "GET",
            "https://example.com/wp-json/wc/v3/products",
            verify=True,
            timeout=30,
            params=None,
        )

    @patch("agentic_brain.commerce.woocommerce.requests.Session")
    async def test_create_product(self, mock_session):
        mock_instance = mock_session.return_value
        self.agent._session = mock_instance

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 2, "name": "New Product"}
        mock_response.status_code = 201
        mock_instance.request.return_value = mock_response

        data = {"name": "New Product", "regular_price": "10.00"}
        product = await self.agent.create_product(data)

        self.assertEqual(product["id"], 2)
        mock_instance.request.assert_called_with(
            "POST",
            "https://example.com/wp-json/wc/v3/products",
            verify=True,
            timeout=30,
            json=data,
        )


if __name__ == "__main__":
    unittest.main()
