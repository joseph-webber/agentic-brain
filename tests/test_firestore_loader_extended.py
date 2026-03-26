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

"""Tests for the enhanced Firestore RAG loader."""

from datetime import UTC, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import agentic_brain.rag.loaders.firestore as firestore_module
from agentic_brain.rag.loaders.base import LoadedDocument
from agentic_brain.rag.loaders.firestore import FirestoreLoader, FirestoreOfflineCache


class FakeSnapshot:
    def __init__(self, doc_id, data, path="articles/doc-1"):
        self.id = doc_id
        self._data = data
        self.exists = True
        self.reference = SimpleNamespace(path=path)
        self.create_time = datetime.now(UTC)
        self.update_time = datetime.now(UTC)

    def to_dict(self):
        return self._data


class FakeDocumentRef:
    def __init__(self, doc_id="doc-1"):
        self.id = doc_id
        self.set_calls = []
        self.deleted = False
        self._snapshot = FakeSnapshot(doc_id, {"content": "hello", "title": "Hello"})
        self._subcollections = []

    def get(self):
        return self._snapshot

    def set(self, data, merge=False):
        self.set_calls.append((data, merge))

    def delete(self):
        self.deleted = True

    def collections(self):
        return self._subcollections


class FakeCollectionRef:
    def __init__(self, name, snapshots=None):
        self.id = name
        self._snapshots = snapshots or []
        self.document_calls = []

    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def stream(self):
        return iter(self._snapshots)

    def document(self, doc_id=None):
        ref = FakeDocumentRef(doc_id or f"generated-{len(self.document_calls)+1}")
        self.document_calls.append(ref)
        return ref

    def on_snapshot(self, callback):
        self._callback = callback
        return lambda: None


class FakeBatch:
    def __init__(self):
        self.operations = []
        self.committed = False

    def set(self, ref, payload, merge=False):
        self.operations.append(("set", ref.id, payload, merge))

    def delete(self, ref):
        self.operations.append(("delete", ref.id))

    def commit(self):
        self.committed = True


class FakeDB:
    def __init__(self):
        self.collections_map = {}
        self.batch_instance = FakeBatch()

    def collection(self, name):
        return self.collections_map.setdefault(name, FakeCollectionRef(name))

    def collection_group(self, name):
        return self.collections_map.setdefault(f"group:{name}", FakeCollectionRef(name))

    def collections(self):
        return self.collections_map.values()

    def batch(self):
        return self.batch_instance


def build_loader(tmp_path: Path) -> FirestoreLoader:
    firestore_module.FIREBASE_AVAILABLE = True
    firestore_module.firestore = MagicMock()
    firestore_module.firestore.SERVER_TIMESTAMP = "SERVER_TIMESTAMP"
    firestore_module.firestore.Query.DESCENDING = "DESCENDING"
    loader = FirestoreLoader(
        project_id="demo",
        enable_offline_persistence=True,
        cache_path=str(tmp_path / "cache.json"),
    )
    loader._authenticated = True
    loader._app = MagicMock()
    loader._db = FakeDB()
    return loader


class TestFirestoreLoaderExtended:
    def test_collection_group_query(self, tmp_path):
        loader = build_loader(tmp_path)
        snapshot = FakeSnapshot(
            "doc-1",
            {"content": "policy", "title": "Policy"},
            path="teams/a/messages/doc-1",
        )
        loader._db.collections_map["group:messages"] = FakeCollectionRef(
            "messages", [snapshot]
        )
        docs = loader.load_collection_group("messages")
        assert len(docs) == 1
        assert docs[0].content == "policy"
        assert docs[0].metadata["path"] == "teams/a/messages/doc-1"

    def test_load_subcollections(self, tmp_path):
        loader = build_loader(tmp_path)
        parent = FakeDocumentRef("parent")
        child_snapshot = FakeSnapshot(
            "child-1",
            {"content": "nested", "title": "Nested"},
            path="articles/parent/comments/child-1",
        )
        parent._subcollections = [FakeCollectionRef("comments", [child_snapshot])]
        loader._document_path_to_ref = MagicMock(return_value=parent)
        docs = loader.load_subcollections("articles/parent")
        assert len(docs) == 1
        assert docs[0].metadata["collection"] == "articles/parent/comments"

    def test_batch_save_documents(self, tmp_path):
        loader = build_loader(tmp_path)
        saved = loader.batch_save_documents(
            "articles",
            [
                {"document_id": "one", "content": "First", "title": "One"},
                LoadedDocument(
                    content="Second",
                    filename="Two",
                    metadata={"document_id": "two", "topic": "firebase"},
                    source="firestore",
                    source_id="articles/two",
                ),
            ],
        )
        assert saved == ["one", "two"]
        assert loader._db.batch_instance.committed is True
        assert len(loader._db.batch_instance.operations) == 2

    def test_batch_delete_documents(self, tmp_path):
        loader = build_loader(tmp_path)
        loader._document_path_to_ref = MagicMock(
            side_effect=[FakeDocumentRef("one"), FakeDocumentRef("two")]
        )
        deleted = loader.batch_delete_documents(["articles/one", "articles/two"])
        assert deleted == 2
        assert loader._db.batch_instance.committed is True

    def test_offline_cache_roundtrip(self, tmp_path):
        cache = FirestoreOfflineCache(str(tmp_path / "firestore-cache.json"))
        original = [
            LoadedDocument(content="Cached", filename="doc.txt", metadata={"v": 1})
        ]
        cache.save_collection("articles", original)
        restored = cache.load_collection("articles")
        assert len(restored) == 1
        assert restored[0].content == "Cached"
