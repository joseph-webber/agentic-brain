# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import asyncio
import os
import sys
import unittest

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from agentic_brain.api.server import create_app
from agentic_brain.personas.manager import Persona, PersonaManager
from agentic_brain.rag.pipeline import RAGPipeline
from agentic_brain.rag.retriever import RetrievedChunk
from agentic_brain.rag.store import InMemoryDocumentStore
from agentic_brain.router import LLMRouter, Provider, RouterConfig
from agentic_brain.router.config import Response


class DummyRetriever:
    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = 0

    def retrieve(self, query, top_k=5, sources=None):
        self.calls += 1
        return self._chunks[:top_k]


class LocalRAGPipeline(RAGPipeline):
    def _generate(self, prompt: str, context: str) -> str:
        summary = context.splitlines()[0] if context else "no-context"
        return f"Answered '{prompt}' using {summary}"


class PersonaAwareRouter(LLMRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_system_prompt = None

    async def _chat_openai(
        self, message: str, system: str | None, model: str, temperature: float
    ) -> Response:
        self.last_system_prompt = system
        return Response(
            content=f"[openai] {message}",
            model=model,
            provider=Provider.OPENAI,
            tokens_used=0,
        )


class TestEcosystemIntegration(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("NEO4J_PASSWORD", "test-password")

    def test_rag_end_to_end(self):
        store = InMemoryDocumentStore()
        pipeline = LocalRAGPipeline(
            document_store=store,
            neo4j_password=os.environ["NEO4J_PASSWORD"],
            llm_provider="openai",
        )

        document = pipeline.add_document(
            "RAG augments LLMs with retrieval.", metadata={"source": "unit-test"}
        )
        self.assertGreaterEqual(len(document.chunks), 1)

        chunk = RetrievedChunk(
            content=document.content,
            source="Document",
            score=0.95,
            metadata={"doc_id": document.id},
        )

        dummy_retriever = DummyRetriever([chunk])
        pipeline.retriever = dummy_retriever

        result = pipeline.query("What does RAG do?", use_cache=False)

        self.assertIn("What does RAG do?", result.answer)
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(dummy_retriever.calls, 1)

    def test_router_with_persona(self):
        persona_manager = PersonaManager.get_instance()
        persona_name = "doctor_integration"
        if persona_manager.get(persona_name) is None:
            persona_manager.register(
                Persona(
                    name=persona_name,
                    description="Medical assistant persona",
                    system_prompt="You are a calm and thorough medical professional.",
                    style_guidelines=[
                        "Ask clarifying questions",
                        "Use accessible language",
                    ],
                )
            )

        router = PersonaAwareRouter(
            config=RouterConfig(
                default_provider=Provider.OPENAI,
                default_model="gpt-4o-mini",
                fallback_enabled=False,
                cache_enabled=False,
                use_http_pool=False,
            )
        )

        loop = asyncio.new_event_loop()
        self.addCleanup(loop.close)

        response = loop.run_until_complete(
            router.chat(
                "I have a headache.",
                persona=persona_name,
                provider=Provider.OPENAI,
                model="gpt-4o-mini",
                use_cache=False,
            )
        )

        self.assertIn("headache", response.content)
        self.assertIsNotNone(router.last_system_prompt)
        self.assertIn("medical professional", router.last_system_prompt)

    def test_api_full_flow(self):
        app = create_app()
        with TestClient(app) as client:
            initial_health = client.get("/health")
            self.assertEqual(initial_health.status_code, 200)
            initial_sessions = initial_health.json()["sessions_active"]

            response = client.post(
                "/chat",
                json={
                    "message": "Hello API",
                    "session_id": "test-session-123",
                    "user_id": "test-user",
                },
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["response"], "Echo: Hello API")
            self.assertEqual(body["session_id"], "test-session-123")

            after_health = client.get("/health")
            self.assertEqual(after_health.status_code, 200)
            self.assertGreaterEqual(
                after_health.json()["sessions_active"], initial_sessions
            )

            clear_response = client.delete("/sessions")
            self.assertEqual(clear_response.status_code, 204)

    def test_cli_commands(self):
        from agentic_brain.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["check"])
        self.assertEqual(args.command, "check")
        self.assertTrue(hasattr(args, "func"))

        args = parser.parse_args(["serve", "--port", "9000"])
        self.assertEqual(args.command, "serve")
        self.assertEqual(args.port, 9000)

        args = parser.parse_args(["chat", "--model", "gpt-5"])
        self.assertEqual(args.command, "chat")
        self.assertEqual(args.model, "gpt-5")

        args = parser.parse_args(["init", "--name", "myproject"])
        self.assertEqual(args.command, "init")
        self.assertEqual(args.name, "myproject")


if __name__ == "__main__":
    unittest.main()
