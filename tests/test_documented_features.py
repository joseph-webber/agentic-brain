# SPDX-License-Identifier: Apache-2.0

"""
Regression tests for core features documented in README.md.

Each test targets a headline feature that customers rely on:
- LLM Router smart routing and fallback behaviour
- GraphRAG pipeline retrieval + generation flow
- Persona catalog (default + industry personas)
- Ethics Guard & Quarantine safety nets
- Event streaming loaders for Kafka / Redpanda
- Hardware acceleration detection (MLX preference)
- CLI ergonomics for `chat` / `serve` plus utility helpers
"""

from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic_brain.cli import commands as cli_commands
from agentic_brain.cli import create_parser
from agentic_brain.ethics.guard import EthicsGuard
from agentic_brain.ethics.quarantine import Quarantine
from agentic_brain.personas import PersonaManager, get_persona
from agentic_brain.rag import embeddings as embeddings_module
from agentic_brain.rag.loaders import event_stream
from agentic_brain.rag.pipeline import RAGPipeline
from agentic_brain.rag.retriever import RetrievedChunk
from agentic_brain.router import LLMRouter, Provider, Response

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_personas():
    """PersonaManager is a singleton, so reset between tests."""
    PersonaManager._instance = None
    yield
    PersonaManager._instance = None


@pytest.fixture
def mock_retriever(monkeypatch):
    """Provide a mocked retriever for RAG pipeline tests."""
    retriever = MagicMock()
    retriever.search.return_value = [
        RetrievedChunk(
            content="Deployments require all tests to pass.",
            source="Document",
            score=0.92,
            metadata={"title": "Deployment SOP"},
        ),
        RetrievedChunk(
            content="This chunk is below the minimum signal threshold.",
            source="Memory",
            score=0.2,
            metadata={},
        ),
    ]
    monkeypatch.setattr(
        "agentic_brain.rag.pipeline.Retriever",
        lambda *args, **kwargs: retriever,
    )
    return retriever


# ---------------------------------------------------------------------------
# LLM Router
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_router_fallbacks_when_primary_fails(monkeypatch):
    """Router should cascade through the documented fallback chain."""

    router = LLMRouter()
    router.config.default_provider = Provider.OLLAMA

    monkeypatch.setattr(
        router,
        "_chat_ollama",
        AsyncMock(side_effect=RuntimeError("ollama offline")),
    )

    fallback_response = Response(
        content="Handled by OpenRouter fallback",
        model="meta-llama/llama-3-8b-instruct:free",
        provider=Provider.OPENROUTER,
    )
    monkeypatch.setattr(
        router,
        "_chat_openrouter",
        AsyncMock(return_value=fallback_response),
    )

    # Keep fallback chain short for the test run
    router.FALLBACK_CHAIN = [
        (Provider.OLLAMA, "llama3.1:8b"),
        (Provider.OPENROUTER, "meta-llama/llama-3-8b-instruct:free"),
    ]

    result = await router.chat("Need a reliable answer", use_cache=False)

    assert result.provider == Provider.OPENROUTER
    assert result.content.startswith("Handled by OpenRouter")


# ---------------------------------------------------------------------------
# GraphRAG Pipeline
# ---------------------------------------------------------------------------


def test_rag_pipeline_filters_chunks_and_generates_answer(
    mock_retriever, monkeypatch, tmp_path
):
    """GraphRAG pipeline should respect scoring + call generation once."""

    cache_dir = tmp_path / "rag_cache"
    cache_dir.mkdir()
    monkeypatch.setattr("agentic_brain.rag.pipeline.CACHE_DIR", cache_dir)

    pipeline = RAGPipeline(embedding_provider=MagicMock(), llm_provider="ollama")
    generated_answer = "Follow the documented deployment procedure."
    pipeline._generate = MagicMock(return_value=generated_answer)

    result = pipeline.query("How do I deploy?", min_score=0.5, use_cache=False)

    assert result.answer == generated_answer
    assert len(result.sources) == 1  # low-score chunk filtered out
    assert all(chunk.score >= 0.5 for chunk in result.sources)
    pipeline._generate.assert_called_once()
    pipeline.close()


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------


def test_persona_manager_includes_industry_personas():
    """Default + industry personas should be loaded ready for routing."""
    PersonaManager.get_instance()

    default = get_persona("default")
    defense = get_persona("defense")

    assert default is not None
    assert "helpful" in default.system_prompt.lower()

    assert defense is not None
    assert defense.safety_level == "high"
    assert "BLUF" in defense.format_system_prompt()


# ---------------------------------------------------------------------------
# Ethics Guard and Quarantine
# ---------------------------------------------------------------------------


def test_ethics_guard_blocks_credentials_in_strict_mode():
    """Strict guard must block leaked credentials before sending."""
    guard = EthicsGuard(strict_mode=True)
    text = "Here is the AWS access key AKIA1234567890123456 you requested."

    result = guard.check(text, channel="email")

    assert not result.safe
    assert any("AWS access key" in reason for reason in result.blocked_reasons)


def test_quarantine_review_process(tmp_path):
    """Quarantine should capture, list, and approve flagged content."""
    quarantine = Quarantine(base_path=tmp_path)
    item = quarantine.add(
        content="Sensitive incident details",
        channel="teams",
        reason="Contains PII",
        context="on-call report",
    )

    pending = quarantine.get_pending()
    assert pending and pending[0].id == item.id

    assert quarantine.approve(item.id, reviewer="secops")
    assert not (quarantine.pending_path / f"{item.id}.json").exists()
    assert (quarantine.approved_path / f"{item.id}.json").exists()


# ---------------------------------------------------------------------------
# Event Streaming (Kafka / Redpanda)
# ---------------------------------------------------------------------------


def _install_fake_kafka(monkeypatch, source_name: str):
    """Install a fake KafkaConsumer compatible with both loaders."""

    class FakeKafkaConsumer:
        def __init__(self, *args, **kwargs):
            self._messages = [
                SimpleNamespace(
                    value=json.dumps({"message": "one"}),
                    topic="events",
                    partition=0,
                    offset=1,
                    timestamp=1700000000000,
                ),
                SimpleNamespace(
                    value="raw text fallback",
                    topic="events",
                    partition=0,
                    offset=2,
                    timestamp=1700000000500,
                ),
            ]

        def subscribe(self, topics):
            self.subscribed = topics

        def __iter__(self):
            return iter(self._messages)

        def close(self):
            self.closed = True

        def unsubscribe(self):
            self.unsubscribed = True

    monkeypatch.setattr(event_stream, "KafkaConsumer", FakeKafkaConsumer)
    if source_name == "kafka":
        monkeypatch.setattr(event_stream, "KAFKA_AVAILABLE", True)
    else:
        monkeypatch.setattr(event_stream, "REDPANDA_AVAILABLE", True)


def test_kafka_loader_reads_messages(monkeypatch):
    """Kafka loader should convert events into LoadedDocument entries."""
    _install_fake_kafka(monkeypatch, "kafka")
    loader = event_stream.KafkaLoader(
        bootstrap_servers="localhost:9092",
        topic="events",
        max_messages=2,
    )

    assert loader.authenticate() is True
    docs = loader.load_folder("events")

    assert len(docs) == 2
    assert all(doc.source == "kafka" for doc in docs)
    assert docs[0].metadata["topic"] == "events"


def test_redpanda_loader_reads_messages(monkeypatch):
    """Redpanda loader reuses Kafka protocol but reports correct source."""
    _install_fake_kafka(monkeypatch, "redpanda")
    loader = event_stream.RedpandaLoader(
        bootstrap_servers="localhost:9092",
        topic="events",
        max_messages=2,
    )

    assert loader.authenticate() is True
    docs = loader.load_folder("events")

    assert len(docs) == 2
    assert all(doc.source == "redpanda" for doc in docs)


# ---------------------------------------------------------------------------
# Hardware Acceleration (MLX detection)
# ---------------------------------------------------------------------------


def test_detect_hardware_prefers_mlx_when_available(monkeypatch):
    """If MLX is importable on Apple Silicon, it should be chosen."""
    monkeypatch.setattr(embeddings_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(embeddings_module.platform, "machine", lambda: "arm64")

    fake_mlx = types.ModuleType("mlx")
    fake_core = types.ModuleType("mlx.core")
    fake_mlx.core = fake_core
    monkeypatch.setitem(sys.modules, "mlx", fake_mlx)
    monkeypatch.setitem(sys.modules, "mlx.core", fake_core)

    monkeypatch.setattr(embeddings_module, "_HARDWARE_CACHE", None, raising=False)

    device, info = embeddings_module.detect_hardware()

    assert device == "mlx"
    assert info["apple_silicon"] is True
    assert info["mlx"] is True


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------


def test_cli_parser_registers_chat_and_serve_commands():
    """Ensure CLI exposes documented chat & serve entrypoints."""
    parser = create_parser()

    chat_args = parser.parse_args(["chat"])
    assert chat_args.command == "chat"
    assert callable(chat_args.func)

    serve_args = parser.parse_args(["serve", "--port", "8123"])
    assert serve_args.command == "serve"
    assert callable(serve_args.func)
    assert serve_args.port == 8123


def test_find_available_port_skips_in_use(monkeypatch):
    """Utility helper should scan until it finds an unused port."""
    attempts: list[int] = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def bind(self, address):
            port = address[1]
            attempts.append(port)
            if port == 8000:
                raise OSError("in use")

    monkeypatch.setattr(
        cli_commands.socket, "socket", lambda *args, **kwargs: FakeSocket()
    )

    port = cli_commands.find_available_port(8000, max_attempts=3)

    assert port == 8001
    assert attempts == [8000, 8001]
