# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for integration tests."""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from agentic_brain.rag.embeddings import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 384) -> None:
        self._dimensions = dim
        self.embed_call_count = 0

    @property
    def dimensions(self) -> int:  # type: ignore[override]
        return self._dimensions

    @property
    def dimensionality(self) -> int:  # type: ignore[override]
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        self.embed_call_count += 1
        seed = sum(ord(char) for char in text) % 97
        return [((seed + index) % 29) / 29.0 for index in range(self._dimensions)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


@dataclass
class MockLLMState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    failures: dict[str, int] = field(default_factory=dict)

    def record(self, method: str, path: str, payload: dict[str, Any] | None) -> None:
        self.requests.append({"method": method, "path": path, "payload": payload or {}})

    def fail_once(self, path: str) -> None:
        self.failures[path] = self.failures.get(path, 0) + 1

    def should_fail(self, path: str) -> bool:
        remaining = self.failures.get(path, 0)
        if remaining <= 0:
            return False
        self.failures[path] = remaining - 1
        return True


class MockLLMHandler(BaseHTTPRequestHandler):
    server_version = "MockLLM/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return None

    @property
    def state(self) -> MockLLMState:
        return self.server.state  # type: ignore[attr-defined]

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_stream(self, chunks: list[str]) -> None:
        body = "\n".join(chunks).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = self.path.split("?", 1)[0]
        self.state.record("GET", parsed, None)
        if parsed == "/api/tags":
            self._send_json(200, {"models": [{"name": "llama3.1:8b"}]})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = self.path.split("?", 1)[0]
        payload = self._read_json()
        self.state.record("POST", parsed, payload)

        if self.state.should_fail(parsed):
            self._send_json(
                429, {"error": {"message": "rate limited", "retry_after": 0}}
            )
            return

        if parsed == "/api/generate":
            prompt = payload.get("prompt", "")
            text = f"Mock answer: {prompt[:80]}".strip()
            if payload.get("stream"):
                self._send_stream(
                    [
                        json.dumps({"response": text[:12], "done": False}),
                        json.dumps({"response": text[12:], "done": True}),
                    ]
                )
            else:
                self._send_json(
                    200,
                    {
                        "response": text,
                        "prompt_eval_count": 18,
                        "eval_count": 12,
                    },
                )
            return

        if parsed == "/api/chat":
            self._send_json(
                200,
                {
                    "message": {"content": "Mock Ollama reply"},
                    "prompt_eval_count": 7,
                    "eval_count": 11,
                },
            )
            return

        if parsed == "/v1/chat/completions":
            user = next(
                (
                    msg.get("content", "")
                    for msg in payload.get("messages", [])
                    if msg.get("role") == "user"
                ),
                "",
            )
            self._send_json(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": f"OpenAI mock: {user or 'ok'}",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 13},
                },
            )
            return

        if parsed == "/v1/messages":
            user = next(
                (
                    msg.get("content", "")
                    for msg in payload.get("messages", [])
                    if msg.get("role") == "user"
                ),
                "",
            )
            self._send_json(
                200,
                {
                    "content": [{"text": f"Anthropic mock: {user or 'ok'}"}],
                    "stop_reason": "stop",
                    "usage": {"input_tokens": 8, "output_tokens": 10},
                },
            )
            return

        self._send_json(404, {"error": "not found"})


@dataclass
class MockGraphStore:
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    document_entities: dict[str, set[str]] = field(default_factory=dict)
    chunk_entities: dict[str, set[str]] = field(default_factory=dict)

    def _cosine(self, left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right, strict=False))
        norm_left = math.sqrt(sum(value * value for value in left))
        norm_right = math.sqrt(sum(value * value for value in right))
        if not norm_left or not norm_right:
            return 0.0
        return dot / (norm_left * norm_right)

    def _chunk_entities_for_doc(self, doc_id: str) -> list[str]:
        chunk_ids = [
            chunk_id
            for chunk_id, chunk in self.chunks.items()
            if chunk["document_id"] == doc_id
        ]
        entity_ids: set[str] = set()
        for chunk_id in chunk_ids:
            entity_ids.update(self.chunk_entities.get(chunk_id, set()))
        return sorted(entity_ids)

    def _vector_results(
        self, embedding: list[float], top_k: int
    ) -> list[dict[str, Any]]:
        results = []
        for chunk_id, chunk in self.chunks.items():
            score = self._cosine(embedding, chunk["embedding"])
            results.append(
                {
                    "chunk_id": chunk_id,
                    "content": chunk["content"],
                    "position": chunk["position"],
                    "doc_id": chunk["document_id"],
                    "metadata": chunk["metadata"],
                    "score": score,
                    "strategy": "vector",
                }
            )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def _graph_results(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_words = {word.strip(".,!?;:").lower() for word in query.split()}
        results = []
        for entity_id, entity in self.entities.items():
            if entity["name"].lower() not in query_words and not any(
                token in entity["name"].lower() for token in query_words if token
            ):
                continue
            for chunk_id, linked_entities in self.chunk_entities.items():
                if entity_id not in linked_entities:
                    continue
                chunk = self.chunks[chunk_id]
                distance = 0
                importance = entity.get("mention_count", 1)
                score = ((1.0 / (distance + 1)) + min(importance / 10.0, 1.0)) / 2
                results.append(
                    {
                        "chunk_id": chunk_id,
                        "content": chunk["content"],
                        "position": chunk["position"],
                        "doc_id": chunk["document_id"],
                        "metadata": chunk["metadata"],
                        "distance": distance,
                        "entity_importance": importance,
                        "entities": [entity["name"]],
                        "score": score,
                        "strategy": "graph",
                    }
                )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def execute(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        normalized = " ".join(query.split())
        if "MERGE (d:Document" in normalized:
            doc_id = params["doc_id"]
            self.documents[doc_id] = {
                "id": doc_id,
                "content": params["content"],
                "timestamp": params["timestamp"],
                "metadata": params.get("metadata", {}),
                "char_count": params.get("char_count", 0),
            }
            return []

        if "UNWIND $entities AS ent" in normalized:
            doc_id = params["doc_id"]
            self.document_entities.setdefault(doc_id, set())
            for entity in params.get("entities", []):
                entity_id = entity["entity_id"]
                self.entities[entity_id] = {
                    "id": entity_id,
                    "name": entity["name"],
                    "type": entity["type"],
                    "mention_count": self.entities.get(entity_id, {}).get(
                        "mention_count", 0
                    )
                    + entity.get("count", 1),
                    "positions": entity.get("positions", []),
                }
                self.document_entities[doc_id].add(entity_id)
            return []

        if "UNWIND $chunks AS ch" in normalized:
            doc_id = params["doc_id"]
            for chunk in params.get("chunks", []):
                self.chunks[chunk["chunk_id"]] = {
                    "id": chunk["chunk_id"],
                    "content": chunk["text"],
                    "position": chunk["position"],
                    "document_id": doc_id,
                    "embedding": chunk["embedding"],
                    "metadata": self.documents.get(doc_id, {}).get("metadata", {}),
                }
            return []

        if "UNWIND $links AS link" in normalized:
            for link in params.get("links", []):
                self.chunk_entities.setdefault(link["chunk_id"], set()).add(
                    link["entity_id"]
                )
            return []

        if (
            "db.index.vector.queryNodes" in normalized
            and "YIELD node, score" in normalized
        ):
            embedding = params.get("embedding", [])
            top_k = int(params.get("k", 5))
            results = []
            for chunk_id, chunk in self.chunks.items():
                score = self._cosine(embedding, chunk["embedding"])
                if score >= float(params.get("min_score", 0.0)):
                    results.append(
                        {
                            "node": {
                                "content": chunk["content"],
                                "text": chunk["content"],
                                **chunk,
                            },
                            "score": score,
                            "labels": ["Chunk"],
                        }
                    )
            results.sort(key=lambda item: item["score"], reverse=True)
            return results[:top_k]

        if "db.index.vector.queryNodes" in normalized:
            embedding = params.get("embedding", [])
            top_k = int(params.get("top_k", 5))
            return self._vector_results(embedding, top_k)

        if "MATCH (e:Entity)" in normalized and "RETURN DISTINCT" in normalized:
            pattern = params.get("pattern", "").lower()
            top_k = int(params.get("top_k", 5))
            results = []
            for entity_id, entity in self.entities.items():
                if (
                    not pattern
                    or entity["name"].lower() in pattern
                    or any(
                        token and token in entity["name"].lower()
                        for token in pattern.split("|")
                    )
                ):
                    for chunk_id, linked_entities in self.chunk_entities.items():
                        if entity_id not in linked_entities:
                            continue
                        chunk = self.chunks[chunk_id]
                        results.append(
                            {
                                "chunk_id": chunk_id,
                                "content": chunk["content"],
                                "position": chunk["position"],
                                "doc_id": chunk["document_id"],
                                "metadata": chunk["metadata"],
                                "distance": 0,
                                "entity_importance": entity.get("mention_count", 1),
                                "entities": [entity["name"]],
                            }
                        )
            return results[:top_k]

        if "MATCH (n:" in normalized and "n.embedding IS NOT NULL" in normalized:
            label = normalized.split("MATCH (n:", 1)[1].split(")", 1)[0]
            rows = []
            for chunk in self.chunks.values():
                if label.lower() == "chunk":
                    rows.append(
                        {
                            "n": {
                                "content": chunk["content"],
                                "text": chunk["content"],
                            },
                            "embedding": chunk["embedding"],
                        }
                    )
            return rows

        return []


class FakeRecordList:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def data(self) -> list[dict[str, Any]]:
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    def __init__(self, store: MockGraphStore) -> None:
        self.store = store

    def run(self, query: str, **params: Any) -> FakeRecordList:
        return FakeRecordList(self.store.execute(query, params))

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeDriver:
    def __init__(self, store: MockGraphStore) -> None:
        self.store = store

    def session(self) -> FakeSession:
        return FakeSession(self.store)


@pytest.fixture()
def mock_embeddings() -> MockEmbeddingProvider:
    return MockEmbeddingProvider(dim=384)


@pytest.fixture()
def llm_server():
    state = MockLLMState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockLLMHandler)
    server.state = state  # type: ignore[attr-defined]
    server.daemon_threads = True  # type: ignore[attr-defined]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield {"base_url": base_url, "state": state}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def graph_store() -> MockGraphStore:
    return MockGraphStore()


@pytest.fixture()
def fake_graph_driver(graph_store: MockGraphStore) -> FakeDriver:
    return FakeDriver(graph_store)


@pytest.fixture()
def temp_cache_dir(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "rag-cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture()
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home
