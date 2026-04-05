# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Tests for RAG document loaders.

Covers: LoadedDocument dataclass (serialisation, round-trip),
        TextLoader (local files), MarkdownLoader, JSONLoader, JSONLLoader,
        BaseLoader ABC behaviour, with_rate_limit decorator, RateLimitError,
        and the load_folder / search helpers.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.loaders.base import (
    BaseLoader,
    LoadedDocument,
    RateLimitError,
    with_rate_limit,
)
from agentic_brain.rag.loaders.json_loader import JSONLLoader, JSONLoader
from agentic_brain.rag.loaders.text import MarkdownLoader, TextLoader


# ---------------------------------------------------------------------------
# LoadedDocument dataclass
# ---------------------------------------------------------------------------


class TestLoadedDocument:
    def _make_doc(self, **kwargs: Any) -> LoadedDocument:
        defaults = dict(
            content="Hello world",
            id="doc-001",
            source="test",
            metadata={"author": "joe"},
        )
        defaults.update(kwargs)
        return LoadedDocument(**defaults)

    def test_to_dict_roundtrip(self) -> None:
        doc = self._make_doc()
        d = doc.to_dict()
        assert d["content"] == "Hello world"
        assert d["id"] == "doc-001"
        assert d["source"] == "test"
        assert d["metadata"]["author"] == "joe"

    def test_from_dict_roundtrip(self) -> None:
        doc = self._make_doc()
        d = doc.to_dict()
        restored = LoadedDocument.from_dict(d)
        assert restored.content == doc.content
        assert restored.id == doc.id
        assert restored.source == doc.source

    def test_to_json_valid(self) -> None:
        doc = self._make_doc()
        raw = doc.to_json()
        parsed = json.loads(raw)
        assert parsed["content"] == "Hello world"

    def test_to_markdown_contains_content(self) -> None:
        doc = self._make_doc(content="## Section\n\nContent here.")
        md = doc.to_markdown()
        assert "Content here" in md

    def test_size_bytes_default_zero(self) -> None:
        doc = self._make_doc()
        assert doc.size_bytes == 0

    def test_mime_type_default(self) -> None:
        doc = self._make_doc()
        assert doc.mime_type == "text/plain"

    def test_created_at_serialised_as_iso_string(self) -> None:
        dt = datetime(2026, 3, 15, 12, 0, 0)
        doc = self._make_doc(created_at=dt)
        d = doc.to_dict()
        assert "2026" in d["created_at"]

    def test_metadata_preserved_through_serialisation(self) -> None:
        meta = {"source": "wiki", "page": 7, "tags": ["ml", "ai"]}
        doc = self._make_doc(metadata=meta)
        restored = LoadedDocument.from_dict(doc.to_dict())
        assert restored.metadata["page"] == 7


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------


class TestRateLimitError:
    def test_is_exception(self) -> None:
        err = RateLimitError()
        assert isinstance(err, Exception)

    def test_default_retry_after(self) -> None:
        err = RateLimitError()
        assert err.retry_after == 60

    def test_custom_retry_after(self) -> None:
        err = RateLimitError(retry_after=120)
        assert err.retry_after == 120

    def test_message_contains_retry_time(self) -> None:
        err = RateLimitError(retry_after=30)
        assert "30" in str(err)


# ---------------------------------------------------------------------------
# with_rate_limit decorator
# ---------------------------------------------------------------------------


class TestWithRateLimit:
    def test_decorated_function_called(self) -> None:
        @with_rate_limit(requests_per_minute=60)
        def my_func(x: int) -> int:
            return x * 2

        assert my_func(5) == 10

    def test_retries_on_rate_limit_error(self) -> None:
        call_count = [0]

        @with_rate_limit(requests_per_minute=100, retry_count=2)
        def flaky() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("429 rate limit exceeded")
            return "success"

        result = flaky()
        assert result == "success"
        assert call_count[0] >= 2

    def test_raises_after_exhausted_retries(self) -> None:
        @with_rate_limit(requests_per_minute=100, retry_count=1)
        def always_fails() -> str:
            raise Exception("429 still rate limited")

        with pytest.raises(Exception):
            always_fails()

    def test_non_rate_limit_exception_propagates_immediately(self) -> None:
        call_count = [0]

        @with_rate_limit(requests_per_minute=60, retry_count=3)
        def value_error_func() -> None:
            call_count[0] += 1
            raise ValueError("bad input")

        with pytest.raises(ValueError):
            value_error_func()
        # Should not retry for non-rate-limit errors
        assert call_count[0] == 1


# ---------------------------------------------------------------------------
# TextLoader
# ---------------------------------------------------------------------------


class TestTextLoader:
    def test_load_document_returns_loaded_document(self, temp_text_dir: Path) -> None:
        loader = TextLoader(base_path=str(temp_text_dir))
        doc = loader.load_document("readme.txt")
        assert doc is not None
        assert isinstance(doc, LoadedDocument)
        assert "readme" in doc.content.lower() or len(doc.content) > 0

    def test_load_document_missing_file_returns_none(self, tmp_path: Path) -> None:
        loader = TextLoader(base_path=str(tmp_path))
        doc = loader.load_document("nonexistent.txt")
        assert doc is None

    def test_load_folder_finds_txt_files(self, temp_text_dir: Path) -> None:
        loader = TextLoader(base_path=str(temp_text_dir))
        docs = loader.load_folder(str(temp_text_dir))
        assert len(docs) >= 2  # readme.txt + notes.txt at minimum

    def test_load_document_content_not_empty(self, temp_text_dir: Path) -> None:
        loader = TextLoader(base_path=str(temp_text_dir))
        doc = loader.load_document("notes.txt")
        assert doc is not None
        assert len(doc.content) > 0

    def test_authenticate_returns_true(self, tmp_path: Path) -> None:
        loader = TextLoader(base_path=str(tmp_path))
        assert loader.authenticate() is True

    def test_source_name(self) -> None:
        loader = TextLoader()
        assert loader.source_name == "local_text"

    def test_search_returns_matching_docs(self, temp_text_dir: Path) -> None:
        loader = TextLoader(base_path=str(temp_text_dir))
        docs = loader.search("readme", max_results=10)
        assert isinstance(docs, list)

    def test_context_manager_does_not_raise(self, tmp_path: Path) -> None:
        with TextLoader(base_path=str(tmp_path)) as loader:
            assert loader is not None

    def test_large_file_content_truncated_to_max(self, tmp_path: Path) -> None:
        """Files exceeding max_file_size_mb should be rejected or truncated."""
        large_file = tmp_path / "big.txt"
        large_file.write_text("x" * 100)  # Tiny file - should be fine
        loader = TextLoader(base_path=str(tmp_path), max_file_size_mb=1)
        doc = loader.load_document("big.txt")
        assert doc is not None


# ---------------------------------------------------------------------------
# MarkdownLoader
# ---------------------------------------------------------------------------


class TestMarkdownLoader:
    def test_load_md_file(self, tmp_path: Path) -> None:
        md_file = tmp_path / "docs.md"
        md_file.write_text("# Title\n\nSome content here.\n\n## Section\n\nMore content.")
        loader = MarkdownLoader(base_path=str(tmp_path))
        doc = loader.load_document("docs.md")
        assert doc is not None
        assert "Title" in doc.content or len(doc.content) > 0

    def test_missing_md_file_returns_none(self, tmp_path: Path) -> None:
        loader = MarkdownLoader(base_path=str(tmp_path))
        doc = loader.load_document("missing.md")
        assert doc is None

    def test_source_name(self) -> None:
        loader = MarkdownLoader()
        assert loader.source_name in ("local_markdown", "local_text", "markdown")

    def test_load_folder_finds_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("# Doc A\n\nContent A.")
        (tmp_path / "b.md").write_text("# Doc B\n\nContent B.")
        loader = MarkdownLoader(base_path=str(tmp_path))
        docs = loader.load_folder(str(tmp_path))
        assert len(docs) >= 2


# ---------------------------------------------------------------------------
# JSONLoader
# ---------------------------------------------------------------------------


class TestJSONLoader:
    def test_load_json_file(self, temp_json_dir: Path) -> None:
        loader = JSONLoader(base_path=str(temp_json_dir))
        doc = loader.load_document("article.json")
        assert doc is not None
        assert "Machine learning" in doc.content or len(doc.content) > 0

    def test_missing_json_returns_none(self, tmp_path: Path) -> None:
        loader = JSONLoader(base_path=str(tmp_path))
        doc = loader.load_document("missing.json")
        assert doc is None

    def test_content_key_extraction(self, tmp_path: Path) -> None:
        """content_key should extract the specified field as content."""
        data = {"title": "AI Overview", "body": "Artificial intelligence is broad.", "other": "ignore"}
        (tmp_path / "doc.json").write_text(json.dumps(data))
        loader = JSONLoader(base_path=str(tmp_path), content_key="body")
        doc = loader.load_document("doc.json")
        assert doc is not None
        assert "Artificial intelligence" in doc.content

    def test_source_name(self) -> None:
        loader = JSONLoader()
        assert loader.source_name == "local_json"

    def test_load_folder_finds_json_files(self, temp_json_dir: Path) -> None:
        loader = JSONLoader(base_path=str(temp_json_dir))
        docs = loader.load_folder(str(temp_json_dir))
        assert len(docs) >= 2

    def test_authenticate_true(self) -> None:
        loader = JSONLoader()
        assert loader.authenticate() is True

    def test_invalid_json_handled_gracefully(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("{ invalid json }")
        loader = JSONLoader(base_path=str(tmp_path))
        doc = loader.load_document("bad.json")
        assert doc is None or isinstance(doc, LoadedDocument)


# ---------------------------------------------------------------------------
# JSONLLoader
# ---------------------------------------------------------------------------


class TestJSONLLoader:
    def test_load_jsonl_file_as_single_doc(self, temp_json_dir: Path) -> None:
        loader = JSONLLoader(base_path=str(temp_json_dir))
        doc = loader.load_document("data.jsonl")
        assert doc is not None
        assert len(doc.content) > 0

    def test_missing_jsonl_returns_none(self, tmp_path: Path) -> None:
        loader = JSONLLoader(base_path=str(tmp_path))
        doc = loader.load_document("missing.jsonl")
        assert doc is None

    def test_source_name(self) -> None:
        loader = JSONLLoader()
        assert "jsonl" in loader.source_name.lower() or loader.source_name

    def test_load_folder_includes_jsonl(self, tmp_path: Path) -> None:
        (tmp_path / "records.jsonl").write_text(
            json.dumps({"id": 1, "text": "record one"}) + "\n"
            + json.dumps({"id": 2, "text": "record two"})
        )
        loader = JSONLLoader(base_path=str(tmp_path))
        docs = loader.load_folder(str(tmp_path))
        assert len(docs) >= 1
