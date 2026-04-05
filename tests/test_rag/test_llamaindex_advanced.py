# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Advanced tests for the LlamaIndex compatibility layer.

Focus areas:
- ServiceContext + global service configuration
- Node parsers (sentence + token splitting, overlap, prev/next rels)
- Response synthesizer modes (compact/refine/tree_summarize)
- Streaming responses (sync + async generators)
- Metadata extraction patterns (TitleExtractor, SummaryExtractor)
- IngestionPipeline + AgenticIndex integration

Run with:
    pytest agentic-brain/tests/test_rag/test_llamaindex_advanced.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any, List

import pytest

import agentic_brain.rag.llamaindex_compat as lic
from agentic_brain.rag.llamaindex_compat import (
    AgenticIndex,
    AgenticQueryEngine,
    AgenticSynthesizer,
    CompactSynthesizer,
    IngestionPipeline,
    RefineSynthesizer,
    ResponseMode,
    SentenceSplitter,
    ServiceContext,
    Settings,
    StreamingResponse,
    StreamingSynthesizer,
    SummaryExtractor,
    TitleExtractor,
    TokenTextSplitter,
    TreeSummarizeSynthesizer,
    get_response_synthesizer,
)


@pytest.fixture(autouse=True)
def _reset_globals() -> None:
    """Reset global Settings + global ServiceContext between tests."""
    prev_ctx = lic.get_global_service_context()
    prev_settings = (
        Settings.llm,
        Settings.embed_model,
        Settings.chunk_size,
        Settings.chunk_overlap,
    )
    try:
        yield
    finally:
        lic._GLOBAL_SERVICE_CONTEXT.set(prev_ctx)  # type: ignore[attr-defined]
        Settings.set_llm(prev_settings[0])
        Settings.set_embed_model(prev_settings[1])
        Settings.set_chunk_size(prev_settings[2])
        Settings.set_chunk_overlap(prev_settings[3])


@pytest.fixture()
def patch_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make RAGPipeline._generate deterministic (no network)."""

    def _fake_generate(self: Any, prompt: str, context: str) -> str:  # noqa: ANN401
        # Keep short but include both args for assertions.
        return f"PROMPT={prompt} | CONTEXT={context[:80]}"

    monkeypatch.setattr(lic.RAGPipeline, "_generate", _fake_generate, raising=True)


class TestServiceContext:
    def test_from_defaults_uses_settings(self) -> None:
        Settings.set_llm("llm-a")
        Settings.set_embed_model("embed-a")
        Settings.set_chunk_size(111)
        Settings.set_chunk_overlap(22)

        ctx = ServiceContext.from_defaults()
        assert ctx.llm == "llm-a"
        assert ctx.embed_model == "embed-a"
        assert ctx.chunk_size == 111
        assert ctx.chunk_overlap == 22

    def test_to_settings_applies_values(self) -> None:
        ctx = ServiceContext.from_defaults(
            llm="llm-b", embed_model="embed-b", chunk_size=333, chunk_overlap=44
        )
        ctx.to_settings()
        assert Settings.llm == "llm-b"
        assert Settings.embed_model == "embed-b"
        assert Settings.chunk_size == 333
        assert Settings.chunk_overlap == 44

    def test_set_and_get_global_service_context(self) -> None:
        ctx = ServiceContext.from_defaults(llm="llm-g", chunk_size=123)
        lic.set_global_service_context(ctx)
        assert lic.get_global_service_context() is ctx
        assert Settings.llm == "llm-g"
        assert Settings.chunk_size == 123

    def test_global_service_context_used_by_index_when_has_node_parser(self) -> None:
        splitter = SentenceSplitter(chunk_size=20, chunk_overlap=0)
        ctx = ServiceContext.from_defaults(node_parser=splitter)
        lic.set_global_service_context(ctx)

        docs = [lic.TextNode(text="Sentence one. Sentence two. Sentence three.")]
        index = AgenticIndex.from_documents(docs, show_progress=False)
        # With node_parser in the global service context, chunking should occur.
        assert index._store.count() > 1


class TestNodeParsers:
    def test_sentence_splitter_returns_multiple_nodes(self) -> None:
        splitter = SentenceSplitter(chunk_size=6, chunk_overlap=0)
        docs = [lic.TextNode(text="A. B. C. D. E. F.")]
        nodes = splitter.get_nodes_from_documents(docs)
        assert len(nodes) >= 2
        assert all(isinstance(n, lic.TextNode) for n in nodes)

    def test_sentence_splitter_overlap_carries_tail_forward(self) -> None:
        text = "One. Two. Three. Four."
        splitter = SentenceSplitter(chunk_size=12, chunk_overlap=6, separator=" ")
        nodes = splitter.get_nodes_from_documents([lic.TextNode(text=text)])
        assert len(nodes) >= 2
        # The last sentence from the previous chunk should appear in the next chunk.
        assert "Two" in nodes[0].text
        assert "Two" in nodes[1].text or "Three" in nodes[1].text

    def test_sentence_splitter_prev_next_relationships(self) -> None:
        splitter = SentenceSplitter(chunk_size=6, chunk_overlap=0)
        nodes = splitter.get_nodes_from_documents([lic.TextNode(text="A. B. C.")])
        assert len(nodes) >= 2
        assert nodes[0].relationships.get("next") == nodes[1].node_id
        assert nodes[1].relationships.get("prev") == nodes[0].node_id

    def test_sentence_splitter_metadata_contains_chunk_index(self) -> None:
        splitter = SentenceSplitter(chunk_size=10, chunk_overlap=0)
        nodes = splitter.get_nodes_from_documents(
            [lic.TextNode(text="A. B. C.", metadata={"source": "x"})]
        )
        assert all("chunk_index" in n.metadata for n in nodes)
        assert all(n.metadata.get("source") == "x" for n in nodes)

    def test_token_text_splitter_returns_nodes(self) -> None:
        splitter = TokenTextSplitter(chunk_size=5, chunk_overlap=1, separator=" ")
        nodes = splitter.get_nodes_from_documents(
            [lic.TextNode(text="one two three four five six seven")]
        )
        assert len(nodes) >= 2

    def test_token_text_splitter_overlap(self) -> None:
        splitter = TokenTextSplitter(chunk_size=5, chunk_overlap=2, separator=" ")
        nodes = splitter.get_nodes_from_documents(
            [lic.TextNode(text="one two three four five six seven")]
        )
        assert len(nodes) >= 2
        # Some word should be shared between adjacent nodes.
        first_words = set(nodes[0].text.split())
        second_words = set(nodes[1].text.split())
        assert len(first_words.intersection(second_words)) >= 1


class TestSynthesizerModes:
    def test_factory_accepts_string_mode(self) -> None:
        synth = get_response_synthesizer("compact")
        assert isinstance(synth, CompactSynthesizer)

    def test_compact_mode_calls_generate_with_prompt_and_context(
        self, patch_generate: None
    ) -> None:
        synth = CompactSynthesizer()
        nodes = [lic.NodeWithScore(node=lic.TextNode(text="ctx"), score=0.5)]
        resp = synth.synthesize("Q?", nodes)
        assert "PROMPT=Q?" in resp.response
        assert "CONTEXT=[1] ctx" in resp.response

    def test_refine_mode_runs_multiple_steps(self, patch_generate: None) -> None:
        synth = RefineSynthesizer()
        nodes = [
            lic.NodeWithScore(node=lic.TextNode(text="ctx1"), score=0.9),
            lic.NodeWithScore(node=lic.TextNode(text="ctx2"), score=0.8),
        ]
        resp = synth.synthesize("Q?", nodes)
        assert resp.metadata["mode"] == "refine"
        assert resp.metadata["refinement_steps"] == 2
        assert "ctx2" in resp.response  # last step context

    def test_tree_summarize_returns_levels(self, patch_generate: None) -> None:
        synth = TreeSummarizeSynthesizer(num_children=2)
        nodes = [
            lic.NodeWithScore(node=lic.TextNode(text=f"ctx{i}"), score=0.1)
            for i in range(5)
        ]
        resp = synth.synthesize("Q?", nodes)
        assert resp.metadata["mode"] == "tree_summarize"
        assert resp.metadata["levels"] >= 1

    def test_agentic_synthesizer_delegates_to_mode(self, patch_generate: None) -> None:
        synth = AgenticSynthesizer(response_mode=ResponseMode.COMPACT)
        nodes = [lic.NodeWithScore(node=lic.TextNode(text="ctx"), score=0.5)]
        resp = synth.synthesize("Q?", nodes)
        assert resp.metadata["mode"] == "compact"


class TestStreaming:
    def test_streaming_synthesizer_returns_streaming_response(
        self, patch_generate: None
    ) -> None:
        synth = StreamingSynthesizer()
        nodes = [lic.NodeWithScore(node=lic.TextNode(text="ctx"), score=0.5)]
        resp = synth.synthesize_stream("Q?", nodes)
        assert isinstance(resp, StreamingResponse)
        assert resp.metadata["streaming"] is True

    def test_streaming_response_get_response_concatenates_tokens(
        self, patch_generate: None
    ) -> None:
        synth = StreamingSynthesizer()
        nodes = [lic.NodeWithScore(node=lic.TextNode(text="ctx"), score=0.5)]
        resp = synth.synthesize_stream("Q?", nodes)
        full = resp.get_response()
        assert isinstance(full, str)
        assert "PROMPT=Q?" in full

    @pytest.mark.asyncio
    async def test_streaming_response_aget_response_uses_async_gen(
        self, patch_generate: None
    ) -> None:
        synth = StreamingSynthesizer()
        nodes = [lic.NodeWithScore(node=lic.TextNode(text="ctx"), score=0.5)]
        resp = synth.synthesize_stream("Q?", nodes)
        full = await resp.aget_response()
        assert "PROMPT=Q?" in full

    @pytest.mark.asyncio
    async def test_async_response_gen_yields_tokens(self, patch_generate: None) -> None:
        synth = StreamingSynthesizer()
        nodes = [lic.NodeWithScore(node=lic.TextNode(text="ctx"), score=0.5)]
        resp = synth.synthesize_stream("Q?", nodes)
        tokens: List[str] = []
        async for t in resp.async_response_gen():
            tokens.append(t)
            if len(tokens) > 5:
                break
        assert tokens

    def test_query_engine_streaming_returns_streaming_response(
        self, patch_generate: None
    ) -> None:
        engine = AgenticQueryEngine(
            retriever=lic.AgenticRetriever(similarity_top_k=1),
            synthesizer=AgenticSynthesizer(),
        )
        # Use a retriever with an empty store -> no nodes -> still returns streaming response.
        resp = engine.query("Q?", streaming=True)
        assert isinstance(resp, StreamingResponse)


class TestMetadataExtractors:
    def test_title_extractor_applies_same_title_to_all_nodes(self) -> None:
        nodes = [
            lic.TextNode(text="# My Title\n\nBody one"),
            lic.TextNode(text="Body two"),
        ]
        metas = TitleExtractor(nodes=1).extract(nodes)
        assert len(metas) == len(nodes)
        assert metas[0]["document_title"] == "My Title"
        assert metas[1]["document_title"] == "My Title"

    def test_title_extractor_empty_nodes(self) -> None:
        assert TitleExtractor().extract([]) == []

    def test_summary_extractor_self_summary(self) -> None:
        nodes = [lic.TextNode(text="one two three four five six seven eight")]
        metas = SummaryExtractor(summaries=["self"]).extract(nodes)
        assert "section_summary" in metas[0]

    def test_summary_extractor_prev_next(self) -> None:
        nodes = [
            lic.TextNode(text="alpha"),
            lic.TextNode(text="beta"),
            lic.TextNode(text="gamma"),
        ]
        metas = SummaryExtractor(summaries=["prev", "next"]).extract(nodes)
        assert "prev_section_summary" not in metas[0]
        assert "next_section_summary" in metas[0]
        assert "prev_section_summary" in metas[1]
        assert "next_section_summary" in metas[1]
        assert "next_section_summary" not in metas[2]


class TestIngestionAndIndexIntegration:
    def test_ingestion_pipeline_runs_split_and_title(self) -> None:
        docs = [
            lic.TextNode(text="# DocTitle\n\nA. B. C. D.", metadata={"source": "x"})
        ]
        pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(chunk_size=10, chunk_overlap=0),
                TitleExtractor(nodes=1),
            ]
        )
        nodes = pipeline.run(docs, show_progress=False)
        assert len(nodes) >= 2
        assert all(n.metadata.get("document_title") == "DocTitle" for n in nodes)

    def test_agentic_index_from_documents_with_transformations_chunks(self) -> None:
        docs = [lic.TextNode(text="A. B. C. D. E. F.")]
        index = AgenticIndex.from_documents(
            docs,
            show_progress=False,
            transformations=[SentenceSplitter(chunk_size=10, chunk_overlap=0)],
        )
        assert index._store.count() > 1

    def test_agentic_index_from_documents_without_transformations_preserves_count(
        self,
    ) -> None:
        docs = [lic.TextNode(text="A. B. C.")]
        index = AgenticIndex.from_documents(docs, show_progress=False)
        assert index._store.count() == 1

    def test_agentic_index_from_documents_chunk_size_convenience(self) -> None:
        docs = [lic.TextNode(text="A. B. C. D. E. F.")]
        index = AgenticIndex.from_documents(
            docs, show_progress=False, chunk_size=10, chunk_overlap=0
        )
        assert index._store.count() > 1


class TestPublicApi:
    def test_all_exports_include_new_features(self) -> None:
        required = {
            "ServiceContext",
            "set_global_service_context",
            "SentenceSplitter",
            "TokenTextSplitter",
            "StreamingResponse",
            "TitleExtractor",
            "SummaryExtractor",
            "IngestionPipeline",
        }
        assert required.issubset(set(lic.__all__))

    def test_settings_properties_accessible(self) -> None:
        # Properties should be readable (compat pattern)
        assert isinstance(Settings.llm, str)
        assert isinstance(Settings.embed_model, str)
        assert isinstance(Settings.chunk_size, int)
        assert isinstance(Settings.chunk_overlap, int)


# ---------------------------------------------------------------------------
# A few extra edge-case tests to push coverage > 30
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_get_response_synthesizer_unknown_mode_defaults_to_compact(self) -> None:
        synth = get_response_synthesizer(ResponseMode.NO_TEXT)
        assert isinstance(synth, CompactSynthesizer)

    def test_streaming_synthesizer_no_nodes(self, patch_generate: None) -> None:
        synth = StreamingSynthesizer()
        resp = synth.synthesize_stream("Q?", [])
        assert "don't have enough information" in resp.get_response().lower()

    def test_sentence_splitter_include_metadata_false(self) -> None:
        splitter = SentenceSplitter(
            chunk_size=10, chunk_overlap=0, include_metadata=False
        )
        nodes = splitter.get_nodes_from_documents(
            [lic.TextNode(text="A. B.", metadata={"x": 1})]
        )
        assert all("x" not in n.metadata for n in nodes)

    def test_token_splitter_empty_text_returns_empty(self) -> None:
        splitter = TokenTextSplitter(chunk_size=10, chunk_overlap=0)
        assert splitter.get_nodes_from_documents([lic.TextNode(text="")]) == []

    def test_service_context_without_global_returns_none(self) -> None:
        assert lic.get_global_service_context() is None

    def test_agentic_query_engine_response_mode_override(
        self, patch_generate: None
    ) -> None:
        engine = AgenticQueryEngine(
            retriever=lic.AgenticRetriever(similarity_top_k=1),
            synthesizer=AgenticSynthesizer(response_mode=ResponseMode.COMPACT),
        )
        resp = engine.query("Q?", response_mode="refine")
        assert resp.metadata["mode"] == "refine"
