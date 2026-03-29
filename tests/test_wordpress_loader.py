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

from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, patch

from agentic_brain.rag.loaders.wordpress import WordPressLoader


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_wordpress_loader_auth_and_load_folder_preserves_acf():
    session = MagicMock()

    def get_side_effect(url, params=None, timeout=None):
        if url.endswith("/wp-json/wp/v2/types"):
            return _FakeResp({"post": {"name": "Posts"}})
        if url.endswith("/wp-json/wp/v2/posts"):
            page = int((params or {}).get("page", 1))
            if page > 1:
                return _FakeResp([])
            return _FakeResp(
                [
                    {
                        "id": 1,
                        "slug": "hello",
                        "status": "publish",
                        "link": "https://example.com/hello",
                        "title": {"rendered": "Hello"},
                        "excerpt": {"rendered": ""},
                        "content": {"rendered": "<p>Hello <b>world</b></p>"},
                        "modified_gmt": "2026-03-01T10:00:00",
                        "date_gmt": "2026-03-01T09:00:00",
                        "acf": {"hero": "Hi"},
                        "categories": [10],
                        "tags": [20],
                        "author": 5,
                        "featured_media": 9,
                    }
                ]
            )
        raise AssertionError(f"Unexpected URL: {url}")

    session.get.side_effect = get_side_effect

    with patch("requests.Session", return_value=session):
        loader = WordPressLoader(site_url="https://example.com")
        assert loader.authenticate() is True
        docs = loader.load_folder("posts")

    assert len(docs) == 1
    assert docs[0].source == "wordpress"
    assert docs[0].metadata["wordpress"]["acf"] == {"hero": "Hi"}
    assert "Hello" in docs[0].content


def test_wordpress_loader_load_since_uses_modified_after_param():
    session = MagicMock()

    def get_side_effect(url, params=None, timeout=None):
        if url.endswith("/wp-json/wp/v2/types"):
            return _FakeResp({"post": {"name": "Posts"}})
        if url.endswith("/wp-json/wp/v2/posts"):
            page = int((params or {}).get("page", 1))
            if page > 1:
                return _FakeResp([])
            # Return empty list; we only validate params.
            return _FakeResp([])
        raise AssertionError(f"Unexpected URL: {url}")

    session.get.side_effect = get_side_effect

    with patch("requests.Session", return_value=session):
        loader = WordPressLoader(site_url="https://example.com")
        assert loader.authenticate() is True
        since = datetime(2026, 3, 1, tzinfo=UTC)
        loader.load_since(since, endpoints=("posts",))

    # Find the call to /posts and assert modified_after was used.
    post_calls = [
        call for call in session.get.call_args_list if call.args[0].endswith("/posts")
    ]
    assert post_calls, "expected /posts call"

    params = post_calls[0].kwargs.get("params")
    assert params is not None
    assert "modified_after" in params
    assert params["modified_after"].startswith("2026-03-01")
