# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

sys.modules.setdefault("cartesia", types.SimpleNamespace(Cartesia=object))
sys.modules.setdefault("faster_whisper", types.SimpleNamespace(WhisperModel=object))
sys.modules.setdefault(
    "sounddevice",
    types.SimpleNamespace(
        default=types.SimpleNamespace(device=(0, 0)),
        query_devices=lambda: [],
    ),
)

scipy_module = types.ModuleType("scipy")
scipy_signal_module = types.ModuleType("scipy.signal")
scipy_signal_module.resample_poly = lambda audio, up, down: audio
scipy_module.signal = scipy_signal_module
sys.modules.setdefault("scipy", scipy_module)
sys.modules.setdefault("scipy.signal", scipy_signal_module)

MODULE_PATH = Path(__file__).resolve().parents[1] / "talk_to_karen.py"
if not MODULE_PATH.exists():
    pytest.skip("talk_to_karen.py not found in project root", allow_module_level=True)
spec = importlib.util.spec_from_file_location("talk_to_karen", MODULE_PATH)
talk_to_karen = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = talk_to_karen
assert spec.loader is not None
spec.loader.exec_module(talk_to_karen)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.history: list[tuple[str, str]] = []

    def set(self, key: str, value: str, *, publish: bool = False) -> None:
        self.store[key] = value
        if publish:
            self.store[f"published:{key}"] = value

    def push_history(self, role: str, content: str) -> None:
        self.history.append((role, content))


def make_chat() -> talk_to_karen.KarenVoiceChat:
    talk_to_karen._WORLD_CLASS = False
    chat = talk_to_karen.KarenVoiceChat.__new__(talk_to_karen.KarenVoiceChat)
    chat.ollama_model = "llama3.2:3b"
    chat.claude_model = "claude-test"
    chat.openai_model = "gpt-test"
    chat.gemini_model = "gemini-test"
    chat.grok_model = "grok-test"
    chat.openrouter_gemini_model = "openrouter/gemini-test"
    chat.openrouter_grok_model = "openrouter/grok-test"
    chat.claude_client = object()
    chat.openai_client = object()
    chat.gemini_client = object()
    chat.grok_client = object()
    chat.openrouter_client = None
    chat.redis = FakeRedis()
    chat._grok_models_cache = ()
    chat.xai_api_key = "xai-test"
    chat.history = []
    chat.ollama_url = "http://localhost:11434"
    return chat


def test_select_route_prefers_ollama_for_simple_queries() -> None:
    chat = make_chat()
    chat.provider_status = lambda: talk_to_karen.ProviderStatus(
        True, True, True, True, True
    )

    route = chat.select_route("Hi Karen")

    assert route.provider == "ollama"
    assert route.model == "llama3.2:3b"
    assert route.complexity == "simple"


def test_select_route_prefers_claude_for_complex_queries() -> None:
    chat = make_chat()
    chat.provider_status = lambda: talk_to_karen.ProviderStatus(
        True, True, True, True, True
    )

    route = chat.select_route(
        "Explain how Redis coordination helps multiple voice agents work together in detail."
    )

    assert route.provider == "claude"
    assert route.model == "claude-test"
    assert route.complexity == "complex"


def test_select_route_supports_explicit_gpt_requests() -> None:
    chat = make_chat()
    chat.provider_status = lambda: talk_to_karen.ProviderStatus(
        True, True, True, True, True
    )

    route = chat.select_route("Use GPT to help me write a Python loop.")

    assert route.provider == "gpt"
    assert route.model == "gpt-test"


def test_select_route_prefers_gemini_for_research_queries() -> None:
    chat = make_chat()
    chat.provider_status = lambda: talk_to_karen.ProviderStatus(
        True, True, True, True, True
    )

    route = chat.select_route("Please research the latest facts about Redis failover.")

    assert route.provider == "gemini"
    assert route.model == "gemini-test"


def test_select_route_prefers_grok_for_creative_queries() -> None:
    chat = make_chat()
    chat.provider_status = lambda: talk_to_karen.ProviderStatus(
        True, True, True, True, True
    )

    route = chat.select_route("Tell me a witty joke about programmers.")

    assert route.provider == "grok"
    assert route.model == "grok-test"


def test_select_route_prefers_grok_for_funny_queries() -> None:
    chat = make_chat()
    chat.provider_status = lambda: talk_to_karen.ProviderStatus(
        True, True, True, True, True
    )

    route = chat.select_route("Make me laugh with a funny robot banter line.")

    assert route.provider == "grok"
    assert route.model == "grok-test"


def test_get_reply_publishes_redis_state_and_falls_back_from_claude_to_ollama() -> None:
    chat = make_chat()
    chat.provider_status = lambda: talk_to_karen.ProviderStatus(
        True, True, True, True, True
    )
    progress_messages: list[str] = []
    chat._set_progress = progress_messages.append

    def fake_call_provider(decision, messages):
        if decision.provider == "claude":
            raise RuntimeError("claude unavailable")
        if decision.provider == "ollama":
            return "Ollama fallback reply"
        raise AssertionError("Unexpected provider")

    chat._call_provider = fake_call_provider

    reply = chat.get_reply("Explain why fallback routing matters for voice chat.")

    assert reply == "Ollama fallback reply"
    assert (
        chat.redis.store[talk_to_karen.VOICE_CURRENT_INPUT_KEY]
        == "Explain why fallback routing matters for voice chat."
    )

    llm_used = json.loads(chat.redis.store[talk_to_karen.VOICE_LLM_USED_KEY])
    assert llm_used["provider"] == "ollama"
    assert llm_used["status"] == "success"
    assert chat.history[-2:] == [
        {
            "role": "user",
            "content": "Explain why fallback routing matters for voice chat.",
        },
        {"role": "assistant", "content": "Ollama fallback reply"},
    ]
    assert (
        "user",
        "Explain why fallback routing matters for voice chat.",
    ) in chat.redis.history
    assert ("assistant", "Ollama fallback reply") in chat.redis.history
    assert any("claude failed" in message for message in progress_messages)


def test_call_grok_discovers_current_models_and_sets_ready_state() -> None:
    chat = make_chat()
    chat.xai_api_key = "xai-test"
    chat.grok_model = "grok-2"
    seen_models: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "data": [
                    {"id": "grok-4-fast-non-reasoning"},
                    {"id": "grok-3-mini"},
                    {"id": "grok-imagine-image"},
                ]
            }

    original_get = talk_to_karen.requests.get
    talk_to_karen.requests.get = lambda *args, **kwargs: FakeResponse()
    try:

        def fake_reply(messages, model):
            seen_models.append(model)
            return f"reply from {model}"

        chat.grok_client = type(
            "FakeGrokClient", (), {"reply": staticmethod(fake_reply)}
        )()

        reply = chat._call_grok(
            [{"role": "user", "content": "Tell me something witty."}],
            chat.grok_model,
        )
    finally:
        talk_to_karen.requests.get = original_get

    assert reply == "reply from grok-4-fast-non-reasoning"
    assert seen_models == ["grok-4-fast-non-reasoning"]
    assert chat.grok_model == "grok-4-fast-non-reasoning"
    assert chat.redis.store[talk_to_karen.VOICE_GROK_READY_KEY] == "true"
    assert (
        "xAI reply succeeded" in chat.redis.store[talk_to_karen.VOICE_GROK_PROGRESS_KEY]
    )
