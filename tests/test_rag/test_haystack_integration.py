# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Haystack compatibility integration tests."""

from __future__ import annotations

from typing import Any

import pytest

from agentic_brain.rag.haystack_compat import (
    BM25Retriever,
    Document,
    EmbeddingRetriever,
    InMemoryDocumentStore,
    Pipeline,
    PipelineConnectionError,
    PipelineRuntimeError,
    PipelineValidationError,
    PromptBuilder,
    component,
)


@component
class LowercaseComponent:
    @component.output_types(text=str)
    def run(self, text: str) -> dict[str, str]:
        return {"text": text.lower()}


@component
class EchoText:
    @component.output_types(text=str)
    def run(self, text: str) -> dict[str, str]:
        return {"text": text}


@component
class CountWords:
    @component.output_types(count=int)
    def run(self, text: str) -> dict[str, int]:
        return {"count": len(text.split())}


@component
class JoinPrompt:
    @component.output_types(prompt=str)
    def run(self, text: str, count: int) -> dict[str, str]:
        return {"prompt": f"{text} ({count})"}


class BrokenComponent:
    pass


class ReturnRawValue:
    def run(self, text: str) -> str:
        return text


class Explodes:
    def run(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError("boom")


class TestComponentDecorator:
    def test_component_decorator_registers_metadata(self) -> None:
        meta = LowercaseComponent.__haystack_component__
        assert meta.name == "LowercaseComponent"
        assert meta.input_types["text"] is str
        assert meta.output_types["text"] is str

    def test_component_without_run_fails(self) -> None:
        with pytest.raises(TypeError):
            component(BrokenComponent)

    def test_output_types_decorator_attached(self) -> None:
        assert hasattr(component, "output_types")
        assert callable(component.output_types)


class TestPipeline:
    def test_add_component_duplicate_name_fails(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        with pytest.raises(ValueError):
            pipe.add_component("echo", EchoText())

    def test_add_component_requires_run_method(self) -> None:
        pipe = Pipeline()
        with pytest.raises(ValueError):
            pipe.add_component("bad", object())

    def test_connect_simple_syntax_uses_default_ports(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.add_component("count", CountWords())
        pipe.connect("echo", "count")
        assert pipe._connections[0].sender_output == "text"
        assert pipe._connections[0].receiver_input == "text"

    def test_connect_detailed_syntax_works(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.add_component("count", CountWords())
        pipe.connect("echo.text", "count.text")
        assert len(pipe._connections) == 1

    def test_connect_missing_sender_fails(self) -> None:
        pipe = Pipeline()
        pipe.add_component("count", CountWords())
        with pytest.raises(PipelineConnectionError):
            pipe.connect("missing.text", "count.text")

    def test_connect_missing_receiver_fails(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        with pytest.raises(PipelineConnectionError):
            pipe.connect("echo.text", "missing.text")

    def test_connect_cycle_fails(self) -> None:
        pipe = Pipeline()
        pipe.add_component("a", EchoText())
        pipe.add_component("b", CountWords())
        pipe.connect("a.text", "b.text")
        with pytest.raises(PipelineConnectionError):
            pipe.connect("b.count", "a.text")

    def test_connect_port_validation_fails(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.add_component("count", CountWords())
        with pytest.raises(PipelineConnectionError):
            pipe.connect("echo.missing", "count.text")

    def test_connect_type_validation_fails(self) -> None:
        pipe = Pipeline()
        pipe.add_component("count", CountWords())
        pipe.add_component("echo", EchoText())
        with pytest.raises(PipelineConnectionError):
            pipe.connect("count.count", "echo.text")

    def test_topological_sort_order(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.add_component("count", CountWords())
        pipe.add_component("join", JoinPrompt())
        pipe.connect("echo.text", "count.text")
        pipe.connect("echo.text", "join.text")
        pipe.connect("count.count", "join.count")
        assert pipe.get_component_names() == ["echo", "count", "join"]

    def test_run_pipeline_executes_and_passes_outputs(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.add_component("count", CountWords())
        pipe.add_component("join", JoinPrompt())
        pipe.connect("echo.text", "count.text")
        pipe.connect("echo.text", "join.text")
        pipe.connect("count.count", "join.count")
        result = pipe.run({"echo": {"text": "hello world"}})
        assert result["join"]["prompt"] == "hello world (2)"

    def test_run_wraps_non_dict_component_result(self) -> None:
        pipe = Pipeline()
        pipe.add_component("raw", ReturnRawValue())
        result = pipe.run({"raw": {"text": "x"}})
        assert result["raw"]["output"] == "x"

    def test_run_pipeline_component_error_is_wrapped(self) -> None:
        pipe = Pipeline()
        pipe.add_component("bad", Explodes())
        with pytest.raises(PipelineRuntimeError):
            pipe.run({"bad": {}})

    def test_run_empty_pipeline_fails(self) -> None:
        with pytest.raises(PipelineRuntimeError):
            Pipeline().run({})

    def test_run_include_outputs_from_filters_results(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.add_component("count", CountWords())
        pipe.connect("echo.text", "count.text")
        result = pipe.run(
            {"echo": {"text": "one two"}},
            include_outputs_from={"count"},
        )
        assert set(result.keys()) == {"count"}

    def test_remove_component_without_incoming_edges(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.remove_component("echo")
        assert pipe.get_component_names() == []

    def test_remove_component_removes_connections(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        pipe.add_component("count", CountWords())
        pipe.connect("echo.text", "count.text")
        pipe.remove_component("echo")
        assert pipe._connections == []

    def test_get_component_missing_raises(self) -> None:
        with pytest.raises(KeyError):
            Pipeline().get_component("missing")

    def test_walk_returns_topological_order(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        names = [name for name, _ in pipe.walk()]
        assert names == ["echo"]

    def test_inputs_outputs_include_decorated_metadata(self) -> None:
        pipe = Pipeline()
        pipe.add_component("echo", EchoText())
        assert pipe.inputs()["echo"]["text"] is str
        assert pipe.outputs()["echo"]["text"] is str

    def test_to_dict_contains_components_connections_and_metadata(self) -> None:
        pipe = Pipeline(metadata={"name": "test"})
        pipe.add_component("echo", EchoText())
        data = pipe.to_dict()
        assert data["metadata"]["name"] == "test"
        assert "echo" in data["components"]
        assert data["connections"] == []

    def test_dumps_and_loads_round_trip_with_registry_component(self) -> None:
        pipe = Pipeline(metadata={"name": "roundtrip"})
        pipe.add_component("echo", EchoText())
        raw = pipe.dumps()
        loaded = Pipeline.loads(raw)
        assert loaded.metadata["name"] == "roundtrip"
        assert loaded.get_component_names() == ["echo"]

    def test_from_dict_with_invalid_component_type_fails(self) -> None:
        with pytest.raises(PipelineValidationError):
            Pipeline.from_dict(
                {
                    "components": {"x": {"type": "no.such.Component"}},
                    "connections": [],
                }
            )

    def test_from_dict_with_callback_factory(self) -> None:
        data = {
            "components": {"lower": {"type": "custom.Lower"}},
            "connections": [],
        }
        pipe = Pipeline.from_dict(data, callbacks={"custom.Lower": lambda: LowercaseComponent()})
        assert pipe.get_component_names() == ["lower"]


class TestInMemoryDocumentStore:
    def _store_with_docs(self) -> InMemoryDocumentStore:
        store = InMemoryDocumentStore()
        store.write_documents(
            [
                Document(
                    content="GraphRAG uses graph context for better retrieval",
                    id="d1",
                    meta={"topic": "rag", "tier": 1},
                    embedding=[1.0, 0.0, 0.0],
                ),
                Document(
                    content="BM25 keyword search is useful for exact terms",
                    id="d2",
                    meta={"topic": "search", "tier": 2},
                    embedding=[0.8, 0.2, 0.0],
                ),
                Document(
                    content="Prompt templates help structure LLM requests",
                    id="d3",
                    meta={"topic": "prompt", "tier": 3},
                    embedding=[0.0, 1.0, 0.0],
                ),
            ]
        )
        return store

    def test_write_and_count_documents(self) -> None:
        store = InMemoryDocumentStore()
        written = store.write_documents([Document(content="x"), Document(content="y")])
        assert written == 2
        assert store.count_documents() == 2

    def test_duplicate_policy_skip(self) -> None:
        store = InMemoryDocumentStore()
        store.write_documents([Document(content="x", id="same")])
        written = store.write_documents([Document(content="y", id="same")], policy="skip")
        assert written == 0
        assert store.count_documents() == 1

    def test_duplicate_policy_fail(self) -> None:
        store = InMemoryDocumentStore()
        store.write_documents([Document(content="x", id="same")])
        with pytest.raises(ValueError):
            store.write_documents([Document(content="y", id="same")], policy="fail")

    def test_duplicate_policy_overwrite(self) -> None:
        store = InMemoryDocumentStore()
        store.write_documents([Document(content="x", id="same")])
        store.write_documents([Document(content="y", id="same")], policy="overwrite")
        docs = [d for d in store.filter_documents() if d.id == "same"]
        assert len(docs) == 1
        assert docs[0].content == "y"

    def test_filter_simple_key_value(self) -> None:
        store = self._store_with_docs()
        docs = store.filter_documents({"topic": "rag"})
        assert [d.id for d in docs] == ["d1"]

    def test_filter_complex_and_condition(self) -> None:
        store = self._store_with_docs()
        docs = store.filter_documents(
            {
                "operator": "AND",
                "conditions": [
                    {"field": "meta.tier", "operator": ">=", "value": 2},
                    {"field": "content", "operator": "contains", "value": "search"},
                ],
            }
        )
        assert [d.id for d in docs] == ["d2"]

    def test_filter_complex_or_condition(self) -> None:
        store = self._store_with_docs()
        docs = store.filter_documents(
            {
                "operator": "OR",
                "conditions": [
                    {"field": "meta.topic", "operator": "==", "value": "rag"},
                    {"field": "meta.topic", "operator": "==", "value": "prompt"},
                ],
            }
        )
        assert {d.id for d in docs} == {"d1", "d3"}

    def test_delete_documents(self) -> None:
        store = self._store_with_docs()
        store.delete_documents(["d2"])
        assert store.count_documents() == 2
        assert {d.id for d in store.filter_documents()} == {"d1", "d3"}

    def test_embedding_retrieval_sorted(self) -> None:
        store = self._store_with_docs()
        docs = store.embedding_retrieval([1.0, 0.0, 0.0], top_k=2)
        assert [d.id for d in docs] == ["d1", "d2"]

    def test_embedding_retrieval_return_embedding(self) -> None:
        store = self._store_with_docs()
        docs = store.embedding_retrieval([1.0, 0.0, 0.0], top_k=1, return_embedding=True)
        assert docs[0].embedding is not None

    def test_bm25_retrieval_top_k(self) -> None:
        store = self._store_with_docs()
        docs = store.bm25_retrieval("search graph", top_k=1)
        assert len(docs) == 1


class TestRetrieversAndPromptBuilder:
    def test_embedding_retriever_runs(self) -> None:
        store = InMemoryDocumentStore()
        store.write_documents([Document(content="x", embedding=[1.0, 0.0, 0.0])])
        retriever = EmbeddingRetriever(document_store=store, top_k=3)
        out = retriever.run(query_embedding=[1.0, 0.0, 0.0])
        assert "documents" in out
        assert len(out["documents"]) == 1

    def test_bm25_retriever_runs(self) -> None:
        store = InMemoryDocumentStore()
        store.write_documents([Document(content="haystack bm25 retriever test")])
        retriever = BM25Retriever(document_store=store, top_k=2)
        out = retriever.run(query="bm25")
        assert len(out["documents"]) == 1

    def test_prompt_builder_replaces_brace_and_jinja_variables(self) -> None:
        pb = PromptBuilder("Q: {{query}}\nC: {context}")
        out = pb.run(query="What?", context="Some context")
        assert "What?" in out["prompt"]
        assert "Some context" in out["prompt"]

    def test_prompt_builder_missing_required_variables_fails(self) -> None:
        pb = PromptBuilder("Q: {query}", required_variables=["query", "documents"])
        with pytest.raises(ValueError):
            pb.run(query="x")

    def test_prompt_builder_formats_documents_list(self) -> None:
        pb = PromptBuilder("Context:\n{documents}")
        docs = [Document(content="Doc A"), Document(content="Doc B")]
        out = pb.run(documents=docs)
        assert "Document 1" in out["prompt"]
        assert "Doc B" in out["prompt"]
