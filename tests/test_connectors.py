# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Tests for connector abstractions and source connectors."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from agentic_brain.connectors import (
    ConfluenceConnector,
    Connector,
    ConnectorRecord,
    ConnectorSchedule,
    ConnectorSyncCursor,
    ConnectorSyncPage,
    GitHubConnector,
    GoogleDriveConnector,
    NotionConnector,
    SlackConnector,
)


def client_with(handler):
    return httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.test"
    )


class DummyConnector(Connector):
    def __init__(self, page=None, schedule=None):
        super().__init__(schedule=schedule, client=client_with(self._handle))
        self.page = page or ConnectorSyncPage(items=[])
        self.calls = []

    @property
    def source_name(self) -> str:
        return "dummy"

    def authenticate(self) -> bool:
        self.calls.append("auth")
        return True

    def list_changes(self, *, cursor=None, limit=None):
        self.calls.append(("list_changes", cursor, limit))
        return self.page

    def fetch_item(self, item_id: str):
        self.calls.append(("fetch_item", item_id))
        return ConnectorRecord(source="dummy", id=item_id, title=item_id)

    def _handle(self, request):
        return httpx.Response(200, json={})


def record(ts: str, source: str = "dummy", **metadata):
    parsed = datetime.fromisoformat(ts)
    return ConnectorRecord(
        source=source,
        id=f"{source}:{ts}",
        title="Title",
        content="Content",
        created_at=parsed,
        updated_at=parsed,
        metadata=metadata,
    )


def test_record_to_dict_serializes_timestamps():
    item = record("2026-01-15T12:00:00+00:00", key="value")
    data = item.to_dict()
    assert data["created_at"] == "2026-01-15T12:00:00+00:00"
    assert data["updated_at"] == "2026-01-15T12:00:00+00:00"
    assert data["metadata"] == {"key": "value"}


def test_cursor_roundtrip():
    cursor = ConnectorSyncCursor(
        updated_after=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        page_token="abc",
        etag="etag",
        state={"a": 1},
    )
    restored = ConnectorSyncCursor.from_dict(cursor.to_dict())
    assert restored.updated_after == cursor.updated_after
    assert restored.page_token == "abc"
    assert restored.state == {"a": 1}


def test_schedule_next_run_enabled():
    schedule = ConnectorSchedule(interval=timedelta(minutes=15))
    now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert schedule.next_run_at(now, now=now) == now + timedelta(minutes=15)


def test_schedule_immediate_returns_now():
    schedule = ConnectorSchedule(immediate=True)
    now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert schedule.next_run_at(None, now=now) == now


def test_schedule_disabled_returns_none():
    schedule = ConnectorSchedule(enabled=False)
    assert schedule.next_run_at(now=datetime(2026, 1, 15, 12, 0, tzinfo=UTC)) is None


def test_schedule_is_due_without_last_run():
    schedule = ConnectorSchedule()
    assert schedule.is_due(now=datetime(2026, 1, 15, 12, 0, tzinfo=UTC))


def test_connector_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Connector()  # type: ignore[abstract]


def test_dedupe_records():
    items = [
        ConnectorRecord(source="dummy", id="1"),
        ConnectorRecord(source="dummy", id="1"),
        ConnectorRecord(source="dummy", id="2"),
    ]
    assert len(Connector._dedupe(items)) == 2


def test_merge_cursor_prefers_latest_timestamp():
    conn = DummyConnector()
    page = ConnectorSyncPage(
        items=[
            record("2026-01-15T12:00:00+00:00"),
            record("2026-01-15T13:00:00+00:00"),
        ],
        next_cursor=ConnectorSyncCursor(page_token="next", state={"x": 1}),
        state={"y": 2},
    )
    merged = conn._merge_cursor(
        ConnectorSyncCursor(updated_after=datetime(2026, 1, 15, 11, 0, tzinfo=UTC)),
        page,
        page.items,
    )
    assert merged.updated_after == datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
    assert merged.page_token == "next"
    assert merged.state == {"y": 2}


def test_sync_uses_schedule_and_returns_result():
    page = ConnectorSyncPage(items=[record("2026-01-15T12:00:00+00:00")])
    conn = DummyConnector(
        page=page, schedule=ConnectorSchedule(interval=timedelta(minutes=5))
    )
    result = conn.sync()
    assert result.source == "dummy"
    assert result.changed_count == 1
    assert result.next_run_at > result.fetched_at
    assert conn.calls[0] == "auth"


def test_incremental_sync_uses_since_timestamp():
    page = ConnectorSyncPage(items=[record("2026-01-15T12:00:00+00:00")])
    conn = DummyConnector(page=page)
    since = datetime(2026, 1, 15, 11, 0, tzinfo=UTC)
    result = conn.incremental_sync(since=since)
    assert result.cursor.updated_after == datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def test_next_run_at_with_disabled_schedule():
    conn = DummyConnector(schedule=ConnectorSchedule(enabled=False))
    assert conn.next_run_at(now=datetime(2026, 1, 15, 12, 0, tzinfo=UTC)) is None


def test_notion_headers_include_version():
    connector = NotionConnector(
        "secret", client=client_with(lambda request: httpx.Response(200, json={}))
    )
    assert connector._headers["Authorization"] == "Bearer secret"
    assert connector._headers["Notion-Version"] == "2022-06-28"


def test_notion_list_changes_database_filters_since():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "object": "page",
                        "id": "page-1",
                        "properties": {
                            "Name": {
                                "type": "title",
                                "title": [{"plain_text": "Alpha"}],
                            }
                        },
                        "last_edited_time": "2026-01-15T12:00:00+00:00",
                        "created_time": "2026-01-15T11:00:00+00:00",
                    }
                ],
                "has_more": False,
                "next_cursor": "cursor-1",
            },
        )

    connector = NotionConnector(
        "secret",
        database_id="db-1",
        client=client_with(handler),
    )
    cursor = ConnectorSyncCursor(updated_after=datetime(2026, 1, 1, tzinfo=UTC))
    page = connector.list_changes(cursor=cursor, limit=5)
    assert seen["path"] == "/v1/databases/db-1/query"
    assert page.items[0].title == "Alpha"
    assert seen["body"]["filter"]["last_edited_time"]["after"].startswith("2026-01-01")


def test_notion_search_fallback_filters_pages():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "object": "page",
                        "id": "page-2",
                        "properties": {
                            "Name": {"type": "title", "title": [{"plain_text": "Beta"}]}
                        },
                        "last_edited_time": "2026-01-16T12:00:00+00:00",
                    },
                    {
                        "object": "database",
                        "id": "db-ignored",
                    },
                ],
                "has_more": False,
            },
        )

    connector = NotionConnector("secret", client=client_with(handler))
    page = connector.list_changes(
        cursor=ConnectorSyncCursor(updated_after=datetime(2026, 1, 15, tzinfo=UTC))
    )
    assert len(page.items) == 1
    assert page.items[0].title == "Beta"


def test_notion_fetch_item_loads_blocks():
    def handler(request):
        if request.url.path.endswith("/pages/page-1"):
            return httpx.Response(
                200,
                json={
                    "id": "page-1",
                    "object": "page",
                    "url": "https://notion.so/page-1",
                    "created_time": "2026-01-15T10:00:00+00:00",
                    "last_edited_time": "2026-01-15T12:00:00+00:00",
                    "properties": {
                        "Name": {
                            "type": "title",
                            "title": [{"plain_text": "Page One"}],
                        }
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "block-1",
                        "type": "paragraph",
                        "has_children": False,
                        "paragraph": {"rich_text": [{"plain_text": "Hello world"}]},
                    },
                    {
                        "id": "block-2",
                        "type": "heading_1",
                        "has_children": False,
                        "heading_1": {"rich_text": [{"plain_text": "section"}]},
                    },
                ]
            },
        )

    connector = NotionConnector("secret", client=client_with(handler))
    item = connector.fetch_item("page-1")
    assert item is not None
    assert "Hello world" in item.content
    assert item.title == "Page One"


def test_notion_fetch_item_returns_none_on_error():
    connector = NotionConnector(
        "secret",
        client=client_with(
            lambda request: httpx.Response(404, json={"error": "missing"})
        ),
    )
    assert connector.fetch_item("missing") is None


def test_notion_cursor_updates_latest_edited_time():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "object": "page",
                        "id": "page-1",
                        "properties": {
                            "Name": {"type": "title", "title": [{"plain_text": "One"}]}
                        },
                        "last_edited_time": "2026-01-15T12:00:00+00:00",
                    },
                    {
                        "object": "page",
                        "id": "page-2",
                        "properties": {
                            "Name": {"type": "title", "title": [{"plain_text": "Two"}]}
                        },
                        "last_edited_time": "2026-01-15T13:00:00+00:00",
                    },
                ],
                "has_more": False,
            },
        )

    connector = NotionConnector("secret", client=client_with(handler))
    page = connector.list_changes()
    assert page.next_cursor.updated_after == datetime(2026, 1, 15, 13, 0, tzinfo=UTC)


def test_confluence_headers_use_basic_auth():
    connector = ConfluenceConnector(
        "https://example.atlassian.net/wiki",
        username="user",
        api_token="token",
        client=client_with(lambda request: httpx.Response(200, json={})),
    )
    assert connector._headers["Authorization"].startswith("Basic ")


def test_confluence_list_changes_builds_cql():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "1",
                        "title": "Guide",
                        "body": {"storage": {"value": "<p>Hello <b>world</b></p>"}},
                        "version": {"when": "2026-01-15T12:00:00+00:00", "number": 3},
                        "space": {"key": "ENG"},
                    }
                ],
                "_links": {"next": "/next"},
                "size": 1,
            },
        )

    connector = ConfluenceConnector(
        "https://example.atlassian.net/wiki",
        username="user",
        api_token="token",
        space_key="ENG",
        client=client_with(handler),
    )
    page = connector.list_changes(
        cursor=ConnectorSyncCursor(updated_after=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert "type = page" in seen["params"]["cql"]
    assert 'space = "ENG"' in seen["params"]["cql"]
    assert page.items[0].title == "Guide"


def test_confluence_fetch_item_strips_html():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "42",
                "title": "Spec",
                "body": {
                    "storage": {"value": "<p>Hello <strong>Confluence</strong></p>"}
                },
                "version": {"when": "2026-01-15T12:00:00+00:00", "number": 1},
                "space": {"key": "ENG"},
            },
        )

    connector = ConfluenceConnector(
        "https://example.atlassian.net/wiki",
        username="user",
        api_token="token",
        client=client_with(handler),
    )
    item = connector.fetch_item("42")
    assert item is not None
    assert item.content == "Hello Confluence"


def test_confluence_search_returns_records():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "7",
                        "title": "Runbook",
                        "body": {"storage": {"value": "<p>Run</p>"}},
                        "version": {"when": "2026-01-15T12:00:00+00:00", "number": 2},
                        "space": {"key": "OPS"},
                    }
                ]
            },
        )

    connector = ConfluenceConnector(
        "https://example.atlassian.net/wiki",
        username="user",
        api_token="token",
        client=client_with(handler),
    )
    results = connector.search("type = page")
    assert results[0].title == "Runbook"


def test_confluence_next_cursor_tracks_latest_update():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "1",
                        "title": "A",
                        "body": {"storage": {"value": "<p>A</p>"}},
                        "version": {"when": "2026-01-15T12:00:00+00:00", "number": 1},
                    },
                    {
                        "id": "2",
                        "title": "B",
                        "body": {"storage": {"value": "<p>B</p>"}},
                        "version": {"when": "2026-01-15T13:00:00+00:00", "number": 1},
                    },
                ],
                "_links": {},
                "size": 2,
            },
        )

    connector = ConfluenceConnector(
        "https://example.atlassian.net/wiki",
        username="user",
        api_token="token",
        client=client_with(handler),
    )
    page = connector.list_changes()
    assert page.next_cursor.updated_after == datetime(2026, 1, 15, 13, 0, tzinfo=UTC)


def test_github_headers_include_token():
    connector = GitHubConnector(
        "octo",
        "brain",
        token="secret",
        client=client_with(lambda request: httpx.Response(200, json={})),
    )
    assert connector._headers["Authorization"] == "Bearer secret"


def test_github_list_changes_returns_empty_when_tree_unchanged():
    def handler(request):
        if request.url.path == "/repos/octo/brain":
            return httpx.Response(200, json={"default_branch": "main"})
        if request.url.path == "/repos/octo/brain/git/trees/main":
            return httpx.Response(200, json={"sha": "tree-sha", "tree": []})
        raise AssertionError(request.url.path)

    connector = GitHubConnector("octo", "brain", client=client_with(handler))
    page = connector.list_changes(
        cursor=ConnectorSyncCursor(state={"tree_sha": "tree-sha"})
    )
    assert page.items == []


def test_github_list_changes_loads_file_content_and_updates_cursor():
    def handler(request):
        if request.url.path == "/repos/octo/brain":
            return httpx.Response(200, json={"default_branch": "main"})
        if request.url.path == "/repos/octo/brain/git/trees/main":
            return httpx.Response(
                200,
                json={
                    "sha": "new-tree",
                    "tree": [
                        {"type": "blob", "path": "README.md", "size": 12},
                        {"type": "blob", "path": "src/app.py", "size": 42},
                    ],
                },
            )
        if request.url.path == "/repos/octo/brain/contents/README.md":
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": "README.md",
                    "name": "README.md",
                    "encoding": "base64",
                    "content": base64.b64encode(b"hello repo").decode(),
                    "html_url": "https://github.com/octo/brain/blob/main/README.md",
                    "sha": "abc",
                    "updated_at": "2026-01-15T12:00:00+00:00",
                },
            )
        if request.url.path == "/repos/octo/brain/contents/src/app.py":
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": "src/app.py",
                    "name": "app.py",
                    "encoding": "base64",
                    "content": base64.b64encode(b"print('hi')").decode(),
                    "html_url": "https://github.com/octo/brain/blob/main/src/app.py",
                    "sha": "def",
                    "updated_at": "2026-01-15T13:00:00+00:00",
                },
            )
        raise AssertionError(request.url.path)

    connector = GitHubConnector("octo", "brain", client=client_with(handler))
    page = connector.list_changes()
    assert len(page.items) == 2
    assert page.next_cursor.state["tree_sha"] == "new-tree"
    assert page.items[0].content == "hello repo"


def test_github_fetch_item_decodes_base64():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "type": "file",
                "path": "src/app.py",
                "name": "app.py",
                "encoding": "base64",
                "content": base64.b64encode(b"print('hello')").decode(),
                "html_url": "https://github.com/octo/brain/blob/main/src/app.py",
                "sha": "123",
                "updated_at": "2026-01-15T13:00:00+00:00",
            },
        )

    connector = GitHubConnector("octo", "brain", client=client_with(handler))
    item = connector.fetch_item("src/app.py")
    assert item is not None
    assert "print('hello')" in item.content


def test_github_fetch_item_returns_none_for_directory():
    connector = GitHubConnector(
        "octo",
        "brain",
        client=client_with(lambda request: httpx.Response(200, json=[{"type": "dir"}])),
    )
    assert connector.fetch_item("docs") is None


def test_github_list_changes_respects_path_filter():
    def handler(request):
        if request.url.path == "/repos/octo/brain":
            return httpx.Response(200, json={"default_branch": "main"})
        if request.url.path == "/repos/octo/brain/git/trees/main":
            return httpx.Response(
                200,
                json={
                    "sha": "tree",
                    "tree": [
                        {"type": "blob", "path": "src/app.py", "size": 1},
                        {"type": "blob", "path": "docs/guide.md", "size": 1},
                    ],
                },
            )
        if request.url.path == "/repos/octo/brain/contents/src/app.py":
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": "src/app.py",
                    "name": "app.py",
                    "encoding": "base64",
                    "content": base64.b64encode(b"print('hi')").decode(),
                    "html_url": "",
                    "sha": "a",
                },
            )
        raise AssertionError(request.url.path)

    connector = GitHubConnector(
        "octo", "brain", path="src", client=client_with(handler)
    )
    page = connector.list_changes()
    assert len(page.items) == 1
    assert page.items[0].id == "src/app.py"


def test_slack_headers_include_bearer_token():
    connector = SlackConnector(
        "secret", client=client_with(lambda request: httpx.Response(200, json={}))
    )
    assert connector._headers["Authorization"] == "Bearer secret"


def test_slack_list_changes_loads_channel_messages():
    def handler(request):
        if request.url.path.endswith("/conversations.history"):
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {"ts": "1736940000.0", "user": "U1", "text": "later"},
                        {"ts": "1736936400.0", "user": "U2", "text": "earlier"},
                    ]
                },
            )
        raise AssertionError(request.url.path)

    connector = SlackConnector("secret", channels=["C1"], client=client_with(handler))
    page = connector.list_changes()
    assert page.items[0].content.endswith("earlier")
    assert page.next_cursor.state["channels"]["C1"]


def test_slack_list_changes_includes_thread_replies():
    seen = {"replies": 0}

    def handler(request):
        if request.url.path.endswith("/conversations.history"):
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "ts": "1736936400.0",
                            "user": "U1",
                            "text": "thread",
                            "reply_count": 1,
                        }
                    ]
                },
            )
        if request.url.path.endswith("/conversations.replies"):
            seen["replies"] += 1
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {"ts": "1736936400.0", "user": "U1", "text": "thread"},
                        {"ts": "1736936401.0", "user": "U2", "text": "reply"},
                    ]
                },
            )
        raise AssertionError(request.url.path)

    connector = SlackConnector("secret", channels=["C1"], client=client_with(handler))
    page = connector.list_changes()
    assert seen["replies"] == 1
    assert any("reply" in item.content for item in page.items)


def test_slack_fetch_item_loads_single_message():
    def handler(request):
        return httpx.Response(
            200,
            json={"messages": [{"ts": "1736936400.0", "user": "U1", "text": "hello"}]},
        )

    connector = SlackConnector("secret", channels=["C1"], client=client_with(handler))
    item = connector.fetch_item("C1:1736936400.0")
    assert item is not None
    assert item.id == "C1:1736936400.0"


def test_slack_search_returns_matches():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "messages": {
                    "matches": [
                        {
                            "channel": {"id": "C1", "name": "general"},
                            "ts": "1736936400.0",
                            "user": "U1",
                            "text": "hello",
                        }
                    ]
                }
            },
        )

    connector = SlackConnector("secret", client=client_with(handler))
    results = connector.search("hello")
    assert results[0].title == "general"


def test_slack_fetch_item_invalid_id_returns_none():
    connector = SlackConnector(
        "secret", client=client_with(lambda request: httpx.Response(200, json={}))
    )
    assert connector.fetch_item("broken") is None


def test_google_drive_headers_include_bearer_token():
    connector = GoogleDriveConnector(
        "secret", client=client_with(lambda request: httpx.Response(200, json={}))
    )
    assert connector._headers["Authorization"] == "Bearer secret"


def test_google_drive_list_changes_builds_query():
    seen = {}

    def handler(request):
        if request.url.path.endswith("/files"):
            seen["params"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "id": "1",
                            "name": "notes.txt",
                            "mimeType": "text/plain",
                            "createdTime": "2026-01-15T11:00:00+00:00",
                            "modifiedTime": "2026-01-15T12:00:00+00:00",
                            "parents": ["folder-1"],
                            "webViewLink": "https://drive.google.com/file/d/1/view",
                        }
                    ],
                    "nextPageToken": "token-1",
                },
            )
        return httpx.Response(200, text="hello")

    connector = GoogleDriveConnector(
        "secret",
        folder_id="folder-1",
        client=client_with(handler),
    )
    page = connector.list_changes(
        cursor=ConnectorSyncCursor(updated_after=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert "'folder-1' in parents" in seen["params"]["q"]
    assert "modifiedTime >" in seen["params"]["q"]
    assert page.items[0].title == "notes.txt"


def test_google_drive_exports_google_docs():
    def handler(request):
        if request.url.path.endswith("/files"):
            return httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "id": "doc-1",
                            "name": "Doc",
                            "mimeType": "application/vnd.google-apps.document",
                            "createdTime": "2026-01-15T11:00:00+00:00",
                            "modifiedTime": "2026-01-15T12:00:00+00:00",
                        }
                    ]
                },
            )
        if request.url.path.endswith("/files/doc-1/export"):
            return httpx.Response(200, text="exported text")
        raise AssertionError(request.url.path)

    connector = GoogleDriveConnector("secret", client=client_with(handler))
    page = connector.list_changes()
    assert page.items[0].content == "exported text"


def test_google_drive_downloads_media_file():
    def handler(request):
        if request.url.path.endswith("/files/file-1"):
            if request.url.params.get("alt") == "media":
                return httpx.Response(200, text="raw bytes")
            return httpx.Response(
                200,
                json={
                    "id": "file-1",
                    "name": "Plain",
                    "mimeType": "text/plain",
                    "createdTime": "2026-01-15T11:00:00+00:00",
                    "modifiedTime": "2026-01-15T12:00:00+00:00",
                },
            )
        raise AssertionError(request.url.path)

    connector = GoogleDriveConnector("secret", client=client_with(handler))
    item = connector.fetch_item("file-1")
    assert item is not None
    assert item.content == "raw bytes"


def test_google_drive_fetch_item_uses_metadata():
    def handler(request):
        if request.url.path.endswith("/files/file-2"):
            if request.url.params.get("alt") == "media":
                return httpx.Response(200, text="body")
            return httpx.Response(
                200,
                json={
                    "id": "file-2",
                    "name": "Meta",
                    "mimeType": "text/plain",
                    "createdTime": "2026-01-15T11:00:00+00:00",
                    "modifiedTime": "2026-01-15T12:00:00+00:00",
                    "parents": ["folder-2"],
                    "webViewLink": "https://drive.google.com/file/d/file-2/view",
                },
            )
        raise AssertionError(request.url.path)

    connector = GoogleDriveConnector("secret", client=client_with(handler))
    item = connector.fetch_item("file-2")
    assert item is not None
    assert item.metadata["parents"] == ["folder-2"]
    assert item.url.endswith("/view")


def test_google_drive_fetch_item_returns_none_on_error():
    connector = GoogleDriveConnector(
        "secret",
        client=client_with(
            lambda request: httpx.Response(404, json={"error": "missing"})
        ),
    )
    assert connector.fetch_item("missing") is None
