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

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from agentic_brain.commerce.wordpress import WPAuth
from agentic_brain.commerce.wordpress_cms import GutenbergParser, HeadlessCMS
from agentic_brain.rag.store import InMemoryDocumentStore


def test_gutenberg_parser_parses_nested_blocks():
    html = """
    <!-- wp:group {\"tagName\":\"section\"} -->
      <!-- wp:heading -->Title<!-- /wp:heading -->
      <!-- wp:paragraph -->Hello <strong>world</strong><!-- /wp:paragraph -->
      <!-- wp:image {\"id\":123} /-->
    <!-- /wp:group -->
    """.strip()

    blocks = GutenbergParser.parse(html)
    assert len(blocks) == 1

    group = blocks[0]
    assert group.name == "group"
    assert group.attrs["tagName"] == "section"
    assert len(group.inner_blocks) == 3

    assert group.inner_blocks[0].name == "heading"
    assert "Title" in group.inner_blocks[0].inner_text

    assert group.inner_blocks[1].name == "paragraph"
    assert "Hello" in group.inner_blocks[1].inner_text

    assert group.inner_blocks[2].name == "image"


@pytest.mark.asyncio
async def test_headlesscms_sync_to_document_store_adds_documents():
    auth = WPAuth(base_url="https://example.com")
    cms = HeadlessCMS(auth)

    store = InMemoryDocumentStore()

    post_payload = [
        {
            "id": 1,
            "slug": "hello",
            "status": "publish",
            "link": "https://example.com/hello",
            "title": {"rendered": "Hello"},
            "excerpt": {"rendered": ""},
            "content": {
                "rendered": "<!-- wp:paragraph -->Hello <b>world</b><!-- /wp:paragraph -->"
            },
            "modified_gmt": "2026-03-01T10:00:00",
            "acf": {"hero": "Hi"},
            "categories": [10],
            "tags": [20],
            "author": 5,
            "featured_media": 9,
            "_links": {"self": [{"href": "..."}]},
        }
    ]

    page_payload = [
        {
            "id": 2,
            "slug": "about",
            "status": "publish",
            "link": "https://example.com/about",
            "title": {"rendered": "About"},
            "excerpt": {"rendered": ""},
            "content": {"rendered": "<p>About us</p>"},
            "modified_gmt": "2026-03-02T10:00:00",
        }
    ]

    cms.rest_list_paginated = AsyncMock(side_effect=[post_payload, page_payload])

    ids = await cms.sync_to_document_store(store, endpoints=("posts", "pages"))
    assert len(ids) == 2
    assert store.count() == 2

    doc = store.get(ids[0])
    assert doc is not None
    assert "Hello" in doc.content
    assert doc.metadata["wordpress"]["site"] == "https://example.com"
    assert doc.metadata["wordpress"]["acf"] == {"hero": "Hi"}


@pytest.mark.asyncio
async def test_headlesscms_graphql_query_raises_on_errors():
    auth = WPAuth(base_url="https://example.com")
    cms = HeadlessCMS(auth)

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        async def json(self):
            return {"errors": [{"message": "boom"}]}

    class FakeSession:
        def post(self, url, json=None):
            return FakeResponse()

        @property
        def closed(self):
            return False

    cms._get_session = AsyncMock(return_value=FakeSession())

    with pytest.raises(RuntimeError, match="WPGraphQL returned errors"):
        await cms.graphql_query("query { posts { nodes { id } } }")
