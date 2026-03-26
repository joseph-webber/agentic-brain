# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import httpx
import pytest

from agentic_brain.commerce.wordpress import WordPressConfig
from agentic_brain.commerce.wp_api import WPAPIClient


@pytest.mark.asyncio
async def test_wp_api_client_graphql_and_acf_endpoints():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    config = WordPressConfig(base_url="https://example.com")

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = WPAPIClient(config, client=http_client)
        await client.graphql_query("query { viewer }")
        await client.custom_post_types.get_acf_fields("products", 10)

    assert "/graphql" in calls
    assert "/wp-json/acf/v3/products/10" in calls
