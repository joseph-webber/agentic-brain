#!/usr/bin/env python3
"""Simple real-time voice chat with Karen via faster-whisper, Redpanda, and Cartesia."""

from __future__ import annotations

import sys
import types

# Python 3.14 fix: when loaded via importlib.util.spec_from_file_location
# (e.g. from MicRequestApp.app), the module is not yet in sys.modules when
# @dataclass(frozen=True) runs, causing AttributeError in _is_type.
# Registering ourselves now fixes that.
if __name__ not in sys.modules:
    _self_mod = types.ModuleType(__name__)
    _self_mod.__file__ = __file__
    _self_mod.__spec__ = __spec__ if "__spec__" in dir() else None
    sys.modules[__name__] = _self_mod

import argparse
import json
import os
import queue
import time
from collections import deque
from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Any, Deque, List, Sequence
from uuid import uuid4

import numpy as np
import requests
import sounddevice as sd
from cartesia import Cartesia
from faster_whisper import WhisperModel
from scipy.signal import resample_poly

from tools.voice_event_bus import (
    VOICE_INPUT_TOPIC,
    VOICE_RESPONSE_TOPIC,
    ensure_voice_topics,
    mark_redpanda_ready,
    publish_progress,
    publish_voice_event,
    wait_for_voice_event,
)

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ENV = SCRIPT_DIR / ".env"
LOCAL_ENV = SCRIPT_DIR / ".env.local"
ROOT_ENV = SCRIPT_DIR.parent / ".env"
CACHE_DIR = SCRIPT_DIR / ".cache"
WHISPER_CACHE = CACHE_DIR / "whisper"

DEFAULT_CARTESIA_VOICE_ID = "a4a16c5e-5902-4732-b9b6-2a48efd2e11b"  # Grace, Australian female
DEFAULT_TTS_MODEL = "sonic-3"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-20250514"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GROK_MODEL = "grok-4-fast-non-reasoning"
DEFAULT_WHISPER_MODEL = "tiny.en"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_XAI_URL = "https://api.x.ai/v1"
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_GEMINI_MODEL = "google/gemini-2.0-flash-001"
DEFAULT_OPENROUTER_GROK_MODEL = "x-ai/grok-4-fast"
GEMINI_MODEL_CANDIDATES = (
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-pro",
)
CLAUDE_MODEL_CANDIDATES = (
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-latest",
)
GROK_MODEL_CANDIDATES = (
    "grok-4-fast-non-reasoning",
    "grok-4-1-fast-non-reasoning",
    "grok-4-fast-reasoning",
    "grok-4-1-fast-reasoning",
    "grok-4-0709",
    "grok-3-mini",
    "grok-3",
    "grok-beta",
)
REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
START_THRESHOLD = 0.015
END_THRESHOLD = 0.009
START_FRAMES = 2
MIN_SPEECH_SECONDS = 0.45
END_SILENCE_SECONDS = 0.9
MAX_UTTERANCE_SECONDS = 12.0
PREBUFFER_SECONDS = 0.35
EXIT_WORDS = {"stop", "goodbye", "exit", "quit", "bye karen", "thanks karen"}

VOICE_CURRENT_INPUT_KEY = "voice:current_input"
VOICE_CURRENT_REQUEST_KEY = "voice:current_request_id"
VOICE_CURRENT_RESPONSE_KEY = "voice:current_response"
VOICE_LLM_USED_KEY = "voice:llm_used"
VOICE_GPT_PROGRESS_KEY = "voice:gpt_progress"
VOICE_GPT_REDPANDA_PROGRESS_KEY = "voice:gpt_redpanda_progress"
VOICE_GROK_PROGRESS_KEY = "voice:grok_progress"
VOICE_GROK_READY_KEY = "voice:grok_ready"
VOICE_HISTORY_KEY = "voice:history"
VOICE_INTEGRATION_COMPLETE_KEY = "voice:integration_complete"
VOICE_ALL_LLMS_READY_KEY = "voice:all_llms_ready"
VOICE_HISTORY_MAX = 20

SIMPLE_MAX_WORDS = 8
COMPLEX_MIN_WORDS = 18

# ---------------------------------------------------------------------------
# World-class multi-LLM engine (v2 architecture)
# ---------------------------------------------------------------------------
try:
    from tools.voice.classifier import (
        classify_complexity as _canonical_classify,
    )
    from tools.voice.classifier import (
        classify_for_strategy,
    )
    from tools.voice.classifier import (
        wants_gpt as _canonical_wants_gpt,
    )
    from tools.voice.events import (
        publish as event_publish,
    )
    from tools.voice.events import (
        publish_metric,
    )
    from tools.voice.events import (
        set_progress as event_set_progress,
    )
    from tools.voice.health import health_check as voice_health_check
    from tools.voice.memory import (
        build_rag_context,
    )
    from tools.voice.memory import (
        push_message as memory_push,
    )
    from tools.voice.memory import (
        store_conversation as memory_store_neo4j,
    )
    from tools.voice.multi_llm import detect_task_type
    from tools.voice.multi_llm import query_llm as multi_llm_query
    _WORLD_CLASS = True
except ImportError:
    _WORLD_CLASS = False

SIMPLE_SIGNALS = frozenset(
    {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
        "yes", "no", "what time", "how are you", "what day", "stop", "bye", "goodbye",
    }
)
COMPLEX_SIGNALS = frozenset(
    {
        "explain", "how does", "why does", "compare", "difference between",
        "step by step", "walk me through", "in detail", "summarise", "summarize",
        "analyse", "analyze", "what would happen", "pros and cons",
    }
)
GPT_SIGNALS = frozenset(
    {
        "use gpt", "use openai", "openai", "gpt", "write code",
        "python", "javascript", "typescript", "json", "regex", "refactor", "debug",
    }
)
GROK_SIGNALS = frozenset(
    {
        "creative", "fun", "joke", "jokes", "witty", "humour", "humor",
        "story", "poem", "brainstorm", "playful", "edgy", "funny",
        "make me laugh", "roast", "banter", "meme", "snark", "silly",
    }
)
GEMINI_SIGNALS = frozenset(
    {
        "research", "facts", "fact check", "look up", "find out", "search",
        "verify", "latest", "current", "news", "accurate", "reference",
    }
)

SYSTEM_PROMPT = (
    "You are Karen, Joseph's warm and witty Australian voice companion living in Adelaide. "
    "Joseph is blind and relies entirely on audio – every response will be spoken aloud. "
    "Rules:\n"
    "1. ALWAYS reply in 2–3 short, punchy sentences – never more.\n"
    "2. Sound natural and conversational, like a mate having a chat.\n"
    "3. Occasionally use relaxed Australian expressions (no worries, heaps good, "
    "she'll be right, fair dinkum) but don't overdo it.\n"
    "4. If you don't know something, say so briefly and offer a practical suggestion.\n"
    "5. Never use bullet points, markdown, or lists – plain spoken sentences only.\n"
    "6. Be warm and caring; Joseph's independence and confidence matter to you."
)


@dataclass(frozen=True)
class RouteDecision:
    provider: str
    model: str
    complexity: str
    reason: str


@dataclass(frozen=True)
class ProviderStatus:
    ollama_available: bool
    claude_available: bool
    openai_available: bool
    gemini_available: bool
    grok_available: bool


class RedisBridge:
    def __init__(self, url: str) -> None:
        self._client = None
        try:
            import redis  # type: ignore

            client = redis.from_url(url, decode_responses=True)
            client.ping()
            self._client = client
        except Exception:
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def set(self, key: str, value: str, *, publish: bool = False) -> None:
        if not self._client:
            return
        try:
            self._client.set(key, value)
            if publish:
                self._client.publish(key, value)
        except Exception:
            pass

    def push_history(self, role: str, content: str) -> None:
        if not self._client:
            return
        entry = json.dumps({"role": role, "content": content, "ts": time.time()})
        try:
            self._client.lpush(VOICE_HISTORY_KEY, entry)
            self._client.ltrim(VOICE_HISTORY_KEY, 0, VOICE_HISTORY_MAX - 1)
        except Exception:
            pass


class ClaudeClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def reply(self, messages: Sequence[dict[str, str]], model: str) -> str:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            json={
                "model": model,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": item["role"], "content": item["content"]}
                    for item in messages
                    if item["role"] != "system"
                ],
                "max_tokens": 180,
                "temperature": 0.6,
            },
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        text_parts = [
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        ]
        return "".join(text_parts).strip()


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        from openai import OpenAI  # type: ignore

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers
        self._client = OpenAI(**client_kwargs)

    def reply(self, messages: Sequence[dict[str, str]], model: str) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=list(messages),
            temperature=0.6,
            max_tokens=180,
        )
        content = response.choices[0].message.content or ""
        if isinstance(content, str):
            return content.strip()
        return str(content).strip()


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def reply(self, messages: Sequence[dict[str, str]], model: str) -> str:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        contents: list[dict[str, Any]] = []
        for item in messages:
            role = item["role"]
            if role == "system":
                continue
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": item["content"]}],
                }
            )

        response = requests.post(
            endpoint,
            params={"key": self._api_key},
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.6,
                    "maxOutputTokens": 180,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts).strip()


def list_input_devices() -> None:
    """Print all available input devices."""
    print("\nAvailable input devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            marker = " <-- default" if i == sd.default.device[0] else ""
            print(f"  [{i}] {d['name']}  (ch={d['max_input_channels']}, rate={int(d['default_samplerate'])}){marker}")
    print()


def find_input_device(name_hint: str | None = None) -> tuple[int | None, int]:
    """
    Find the best input device index and its native sample rate.

    Priority:
      1. Exact device index if name_hint is numeric
      2. Device whose name contains name_hint (case-insensitive)
      3. AirPods (any model) if name_hint is None
      4. System default input device

    Returns (device_index_or_None_for_default, native_sample_rate).
    None means "use sounddevice default".
    """
    devices = sd.query_devices()

    if name_hint is not None:
        if name_hint.isdigit():
            idx = int(name_hint)
            return idx, int(devices[idx]["default_samplerate"])
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0 and name_hint.lower() in d["name"].lower():
                print(f"[audio] Using input device [{i}]: {d['name']}  @ {int(d['default_samplerate'])} Hz")
                return i, int(d["default_samplerate"])
        print(f"[audio] WARNING: device '{name_hint}' not found, falling back to default.")

    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0 and "airpods" in d["name"].lower():
            print(f"[audio] Auto-detected AirPods input [{i}]: {d['name']}  @ {int(d['default_samplerate'])} Hz")
            return i, int(d["default_samplerate"])

    default_idx = sd.default.device[0]
    if default_idx is not None and default_idx >= 0:
        rate = int(devices[default_idx]["default_samplerate"])
        print(f"[audio] Using default input device [{default_idx}]: {devices[default_idx]['name']}  @ {rate} Hz")
        return None, rate

    return None, SAMPLE_RATE


def resample_to(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample mono float32 audio from src_rate to dst_rate using polyphase filter."""
    if src_rate == dst_rate:
        return audio
    g = gcd(src_rate, dst_rate)
    up, down = dst_rate // g, src_rate // g
    return resample_poly(audio, up, down).astype(np.float32)


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_env_files(*paths: Path) -> None:
    for path in paths:
        load_local_env(path)


def classify_complexity(text: str) -> str:
    lower = text.lower().strip()
    words = lower.split()
    word_count = len(words)

    if word_count <= SIMPLE_MAX_WORDS:
        for signal in SIMPLE_SIGNALS:
            if lower == signal or lower.startswith(signal):
                return "simple"

    if any(signal in lower for signal in COMPLEX_SIGNALS):
        return "complex"

    if word_count <= SIMPLE_MAX_WORDS:
        return "simple"
    if word_count >= COMPLEX_MIN_WORDS:
        return "complex"
    return "medium"


def wants_gpt(text: str) -> bool:
    lower = text.lower().strip()
    return any(signal in lower for signal in GPT_SIGNALS)


def wants_grok(text: str) -> bool:
    lower = text.lower().strip()
    return any(signal in lower for signal in GROK_SIGNALS)


def wants_gemini(text: str) -> bool:
    lower = text.lower().strip()
    return any(signal in lower for signal in GEMINI_SIGNALS)


def grok_response(
    text: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str = DEFAULT_XAI_URL,
    max_tokens: int = 200,
) -> str:
    load_env_files(ROOT_ENV, APP_ENV, LOCAL_ENV)
    key = api_key or os.getenv("XAI_API_KEY")
    if not key:
        raise RuntimeError("Missing XAI_API_KEY")

    chosen_model = model or os.getenv("GROK_MODEL", DEFAULT_GROK_MODEL)
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": chosen_model,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return (
        ((payload.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
    )


class KarenVoiceChat:
    def __init__(self, whisper_model: str = DEFAULT_WHISPER_MODEL, input_device: str | None = None) -> None:
        load_env_files(ROOT_ENV, APP_ENV, LOCAL_ENV)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        WHISPER_CACHE.mkdir(parents=True, exist_ok=True)

        self.cartesia_api_key = os.getenv("CARTESIA_API_KEY")
        if not self.cartesia_api_key:
            raise RuntimeError(
                f"Missing CARTESIA_API_KEY. Add it to {LOCAL_ENV} or export it in your shell."
            )

        self.voice_id = os.getenv("CARTESIA_VOICE_ID", DEFAULT_CARTESIA_VOICE_ID)
        self.tts_model = os.getenv("CARTESIA_TTS_MODEL", DEFAULT_TTS_MODEL)
        self.ollama_model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.ollama_url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
        self.claude_api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.claude_model = os.getenv("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.xai_api_key = os.getenv("XAI_API_KEY")
        self.grok_model = os.getenv("GROK_MODEL", DEFAULT_GROK_MODEL)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_url = os.getenv("OPENROUTER_URL", DEFAULT_OPENROUTER_URL)
        self.openrouter_gemini_model = os.getenv(
            "OPENROUTER_GEMINI_MODEL", DEFAULT_OPENROUTER_GEMINI_MODEL
        )
        self.openrouter_grok_model = os.getenv(
            "OPENROUTER_GROK_MODEL", DEFAULT_OPENROUTER_GROK_MODEL
        )
        self.redis = RedisBridge(REDIS_URL)
        self._grok_models_cache: tuple[str, ...] = ()
        self.session_id = f"karen-{uuid4().hex[:12]}"
        self.response_timeout = float(os.getenv("KAREN_RESPONSE_TIMEOUT", "45"))
        self.allow_local_fallback = os.getenv(
            "KAREN_LOCAL_RESPONSE_FALLBACK", "0"
        ).lower() in {"1", "true", "yes", "on"}
        self.redis.set(VOICE_INTEGRATION_COMPLETE_KEY, "false")
        self.redis.set(VOICE_ALL_LLMS_READY_KEY, "false")
        self.redis.set(VOICE_GROK_READY_KEY, "false", publish=True)
        self.redis.set(VOICE_GPT_REDPANDA_PROGRESS_KEY, "initialising Karen voice chat")
        mark_redpanda_ready("false")
        self._set_progress("initialising Karen voice chat")

        self.input_device, self.capture_rate = find_input_device(input_device)

        self.cartesia = Cartesia(api_key=self.cartesia_api_key)
        self.whisper = WhisperModel(
            whisper_model,
            device="cpu",
            compute_type="int8",
            download_root=str(WHISPER_CACHE),
        )
        self.claude_client = ClaudeClient(self.claude_api_key) if self.claude_api_key else None
        self.openai_client = OpenAIClient(self.openai_api_key) if self.openai_api_key else None
        self.gemini_client = GeminiClient(self.gemini_api_key) if self.gemini_api_key else None
        self.grok_client = (
            OpenAIClient(
                self.xai_api_key,
                base_url=os.getenv("XAI_BASE_URL", DEFAULT_XAI_URL),
            )
            if self.xai_api_key
            else None
        )
        self.openrouter_client = (
            OpenAIClient(
                self.openrouter_api_key,
                base_url=self.openrouter_url,
                default_headers={
                    "HTTP-Referer": "https://github.com/joseph-webber/brain",
                    "X-Title": "talk_to_karen",
                },
            )
            if self.openrouter_api_key
            else None
        )
        self.history: List[dict[str, str]] = []
        self.speaking = False

    def _set_progress(self, text: str) -> None:
        self.redis.set(VOICE_GPT_PROGRESS_KEY, text)
        self.redis.set(VOICE_GPT_REDPANDA_PROGRESS_KEY, text)
        try:
            publish_progress(
                text,
                {"source": "talk_to_karen", "session_id": self.session_id},
            )
        except Exception:
            pass

    def _set_grok_progress(self, text: str) -> None:
        self.redis.set(VOICE_GROK_PROGRESS_KEY, text, publish=True)

    def _set_grok_ready(self, ready: bool) -> None:
        self.redis.set(VOICE_GROK_READY_KEY, "true" if ready else "false", publish=True)

    def _publish_current_input(self, text: str) -> None:
        self.redis.set(VOICE_CURRENT_INPUT_KEY, text, publish=True)
        self.redis.push_history("user", text)

    def publish_input_event(self, text: str) -> str:
        request_id = uuid4().hex
        payload = {
            "request_id": request_id,
            "session_id": self.session_id,
            "text": text,
            "source": "talk_to_karen",
            "timestamp": time.time(),
        }
        self.redis.set(VOICE_CURRENT_INPUT_KEY, text, publish=True)
        self.redis.set(VOICE_CURRENT_REQUEST_KEY, request_id, publish=True)
        publish_voice_event(VOICE_INPUT_TOPIC, payload)
        self._set_progress(f"published input event {request_id[:8]}")
        return request_id

    def _publish_llm_used(self, decision: RouteDecision, *, status: str) -> None:
        payload = json.dumps(
            {
                "provider": decision.provider,
                "model": decision.model,
                "complexity": decision.complexity,
                "reason": decision.reason,
                "status": status,
                "timestamp": time.time(),
            }
        )
        self.redis.set(VOICE_LLM_USED_KEY, payload, publish=True)

    def _record_assistant_reply(self, text: str) -> None:
        self.redis.push_history("assistant", text)

    def _record_response_event(self, payload: dict[str, Any]) -> None:
        self.redis.set(VOICE_CURRENT_RESPONSE_KEY, json.dumps(payload), publish=True)

    def _discover_grok_models(self, *, force: bool = False) -> tuple[str, ...]:
        if self._grok_models_cache and not force:
            return self._grok_models_cache
        if not self.xai_api_key:
            self._set_grok_progress("xAI API key missing")
            self._set_grok_ready(False)
            return ()

        self._set_grok_progress("checking xAI model availability")
        response = requests.get(
            f"{os.getenv('XAI_BASE_URL', DEFAULT_XAI_URL).rstrip('/')}/models",
            headers={"Authorization": f"Bearer {self.xai_api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        model_ids = [
            item.get("id", "")
            for item in payload.get("data", [])
            if isinstance(item, dict)
        ]
        text_models = tuple(
            model_id
            for model_id in model_ids
            if model_id.startswith("grok") and "imagine" not in model_id
        )
        ordered = tuple(
            candidate for candidate in GROK_MODEL_CANDIDATES if candidate in text_models
        )
        extras = tuple(model_id for model_id in text_models if model_id not in ordered)
        self._grok_models_cache = ordered + extras
        if self._grok_models_cache:
            if self.grok_model not in self._grok_models_cache:
                self.grok_model = self._grok_models_cache[0]
            self._set_grok_progress(
                f"xAI ready with {len(self._grok_models_cache)} Grok models; defaulting to {self.grok_model}"
            )
            self._set_grok_ready(True)
        else:
            self._set_grok_progress("xAI responded but no Grok text models were available")
            self._set_grok_ready(False)
        return self._grok_models_cache

    def _available_ollama_models(self) -> tuple[str, ...]:
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            response.raise_for_status()
            payload = response.json()
            return tuple(
                item.get("name", "")
                for item in payload.get("models", [])
                if isinstance(item, dict) and item.get("name")
            )
        except Exception:
            return ()

    def _wait_for_bus_response(self, request_id: str) -> dict[str, Any] | None:
        payload = wait_for_voice_event(
            VOICE_RESPONSE_TOPIC,
            predicate=lambda event: event.get("request_id") == request_id,
            timeout=self.response_timeout,
            group_id=f"karen-response-{self.session_id}-{request_id[:8]}",
            auto_offset_reset="earliest",
        )
        if payload:
            self._record_response_event(payload)
            self._set_progress(f"received response event {request_id[:8]}")
        return payload

    def get_reply_from_bus(self, user_text: str) -> str:
        request_id = self.publish_input_event(user_text)
        payload = self._wait_for_bus_response(request_id)
        if payload:
            reply = str(payload.get("text") or "").strip()
            if reply:
                self.history.extend(
                    [
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": reply},
                    ]
                )
                self.history = self.history[-10:]
                self._record_assistant_reply(reply)
                return reply

        if self.allow_local_fallback:
            self._set_progress(f"response timeout for {request_id[:8]}, using local fallback")
            reply = self.get_reply(user_text)
            fallback_payload = {
                "request_id": request_id,
                "session_id": self.session_id,
                "text": reply,
                "source": "talk_to_karen.local_fallback",
                "timestamp": time.time(),
                "fallback": True,
            }
            publish_voice_event(VOICE_RESPONSE_TOPIC, fallback_payload)
            self._record_response_event(fallback_payload)
            return reply

        raise TimeoutError(
            "Still waiting for brain.voice.response. Start the response generator or enable KAREN_LOCAL_RESPONSE_FALLBACK=1."
        )

    def provider_status(self) -> ProviderStatus:
        return ProviderStatus(
            ollama_available=self._ollama_available(),
            claude_available=self.claude_client is not None,
            openai_available=self.openai_client is not None,
            gemini_available=self.gemini_client is not None or self.openrouter_client is not None,
            grok_available=self.grok_client is not None or self.openrouter_client is not None,
        )

    def _ollama_available(self) -> bool:
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def check_services(self) -> None:
        ensure_voice_topics()
        if self.grok_client:
            try:
                self._discover_grok_models()
            except Exception as exc:
                self._set_grok_progress(f"xAI model discovery failed: {exc}")
                self._set_grok_ready(False)
        status = self.provider_status()
        providers = []
        if status.ollama_available:
            providers.append(f"Ollama({self.ollama_model})")
        if status.claude_available:
            providers.append(f"Claude({self.claude_model})")
        if status.openai_available:
            providers.append(f"GPT({self.openai_model})")
        if status.gemini_available:
            model = self.gemini_model if self.gemini_client else self.openrouter_gemini_model
            providers.append(f"Gemini({model})")
        if status.grok_available:
            model = self.grok_model if self.grok_client else self.openrouter_grok_model
            providers.append(f"Grok({model})")

        if self.allow_local_fallback and not providers:
            raise RuntimeError("No LLM providers available for local fallback. Check Ollama or API keys.")

        provider_summary = ", ".join(providers) if providers else "event-driven mode only"
        self._set_progress(f"voice bus ready; providers: {provider_summary}")
        mark_redpanda_ready("true")

    def speak(self, text: str) -> None:
        """Speak text through Cartesia TTS, with macOS `say` as emergency fallback."""
        text = text.strip()
        if not text:
            return
        self.speaking = True
        try:
            self._speak_cartesia(text)
        except Exception as exc:
            # Emergency fallback: macOS say command (NEVER leaves Joseph in silence)
            print(f"[tts] Cartesia failed ({exc}), using macOS say fallback", flush=True)
            try:
                import subprocess
                subprocess.run(
                    ["say", "-v", "Karen (Premium)", "-r", "160", text],
                    timeout=30, check=False,
                )
            except Exception:
                pass
        finally:
            self.speaking = False

    def _speak_cartesia(self, text: str) -> None:
        """Core Cartesia TTS via WebSocket."""
        with self.cartesia.tts.websocket_connect() as conn:
            ctx = conn.context(
                model_id=self.tts_model,
                voice={"mode": "id", "id": self.voice_id},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_f32le",
                    "sample_rate": TTS_SAMPLE_RATE,
                },
                language="en",
            )
            ctx.push(text)
            ctx.no_more_inputs()
            with sd.RawOutputStream(
                samplerate=TTS_SAMPLE_RATE,
                channels=1,
                dtype="float32",
            ) as stream:
                for event in ctx.receive():
                    if getattr(event, "type", None) == "chunk" and getattr(event, "audio", None):
                        stream.write(event.audio)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        segments, _ = self.whisper.transcribe(
            audio.astype(np.float32),
            language="en",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            without_timestamps=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _build_messages(self, user_text: str) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history[-8:])
        messages.append({"role": "user", "content": user_text})
        return messages

    def select_route(self, user_text: str) -> RouteDecision:
        complexity = classify_complexity(user_text)
        status = self.provider_status()

        if wants_gpt(user_text) and status.openai_available:
            return RouteDecision(
                provider="gpt",
                model=self.openai_model,
                complexity=complexity,
                reason="GPT-style or coding request detected; using OpenAI model.",
            )

        if wants_grok(user_text) and status.grok_available:
            return RouteDecision(
                provider="grok",
                model=self._model_for_provider("grok"),
                complexity=complexity,
                reason="Creative or playful request detected; using Grok for a witty response.",
            )

        if wants_gemini(user_text) and status.gemini_available:
            return RouteDecision(
                provider="gemini",
                model=self._model_for_provider("gemini"),
                complexity=complexity,
                reason="Research or factual request detected; using Gemini for retrieval-friendly answers.",
            )

        if complexity == "simple":
            return RouteDecision(
                provider="ollama",
                model=self.ollama_model,
                complexity=complexity,
                reason="Short/simple voice query routed to the fast local Ollama model.",
            )

        if status.claude_available:
            return RouteDecision(
                provider="claude",
                model=self.claude_model,
                complexity=complexity,
                reason="Complex query routed to Claude for stronger reasoning.",
            )

        if status.openai_available:
            return RouteDecision(
                provider="gpt",
                model=self.openai_model,
                complexity=complexity,
                reason="Claude is unavailable, so the complex query is routed to GPT.",
            )

        if status.gemini_available:
            return RouteDecision(
                provider="gemini",
                model=self._model_for_provider("gemini"),
                complexity=complexity,
                reason="Claude and GPT are unavailable, so the query is routed to Gemini.",
            )

        if status.grok_available:
            return RouteDecision(
                provider="grok",
                model=self._model_for_provider("grok"),
                complexity=complexity,
                reason="Claude, GPT, and Gemini are unavailable, so the query is routed to Grok.",
            )

        return RouteDecision(
            provider="ollama",
            model=self.ollama_model,
            complexity=complexity,
            reason="Cloud models unavailable, falling back to local Ollama.",
        )

    def _provider_label(self, provider: str) -> str:
        labels = {
            "ollama": "Ollama",
            "claude": "Claude",
            "gpt": "GPT",
            "gemini": "Gemini",
            "grok": "Grok",
        }
        return labels.get(provider, provider.title())

    def _provider_available(self, status: ProviderStatus, provider: str) -> bool:
        return {
            "ollama": status.ollama_available,
            "claude": status.claude_available,
            "gpt": status.openai_available,
            "gemini": status.gemini_available,
            "grok": status.grok_available,
        }.get(provider, False)

    def _model_for_provider(self, provider: str) -> str:
        if provider == "claude":
            return self.claude_model
        if provider == "gpt":
            return self.openai_model
        if provider == "gemini":
            return self.gemini_model if self.gemini_client else self.openrouter_gemini_model
        if provider == "grok":
            return self.grok_model if self.grok_client else self.openrouter_grok_model
        return self.ollama_model

    def _fallback_chain(self, primary: RouteDecision) -> list[RouteDecision]:
        status = self.provider_status()
        fallback_order = {
            "ollama": ["ollama", "claude", "gpt", "gemini", "grok"],
            "claude": ["claude", "gpt", "gemini", "grok", "ollama"],
            "gpt": ["gpt", "claude", "gemini", "grok", "ollama"],
            "gemini": ["gemini", "claude", "gpt", "grok", "ollama"],
            "grok": ["grok", "gemini", "claude", "gpt", "ollama"],
        }
        decisions: list[RouteDecision] = []
        unique: list[RouteDecision] = []
        seen: set[tuple[str, str]] = set()
        for provider in fallback_order.get(primary.provider, ["ollama", "claude", "gpt", "gemini", "grok"]):
            if provider == primary.provider:
                decisions.append(primary)
                continue
            if not self._provider_available(status, provider):
                continue
            decisions.append(
                RouteDecision(
                    provider,
                    self._model_for_provider(provider),
                    primary.complexity,
                    f"{self._provider_label(primary.provider)} fallback → {self._provider_label(provider)}.",
                )
            )

        for decision in decisions:
            key = (decision.provider, decision.model)
            if key in seen:
                continue
            seen.add(key)
            unique.append(decision)
        return unique

    def _call_ollama(self, messages: Sequence[dict[str, str]], model: str) -> str:
        candidates = [model]
        for local_model in self._available_ollama_models():
            if local_model not in candidates:
                candidates.append(local_model)

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                response = requests.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": candidate,
                        "messages": list(messages),
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 120,
                        },
                    },
                    timeout=180,
                )
                response.raise_for_status()
                payload = response.json()
                reply = payload.get("message", {}).get("content", "").strip()
                if reply:
                    self.ollama_model = candidate
                    return reply
                last_error = RuntimeError(f"Ollama returned an empty response for {candidate}")
            except Exception as exc:
                last_error = exc

        raise last_error or RuntimeError("Ollama client is not configured")

    def _call_claude(self, messages: Sequence[dict[str, str]], model: str) -> str:
        if not self.claude_client:
            raise RuntimeError("Claude client is not configured")
        candidates = [model]
        for fallback_model in CLAUDE_MODEL_CANDIDATES:
            if fallback_model not in candidates:
                candidates.append(fallback_model)

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                reply = self.claude_client.reply(messages, candidate)
                self.claude_model = candidate
                return reply
            except Exception as exc:
                last_error = exc

        raise last_error or RuntimeError("Claude client is not configured")

    def _call_openai(self, messages: Sequence[dict[str, str]], model: str) -> str:
        if not self.openai_client:
            raise RuntimeError("OpenAI client is not configured")
        return self.openai_client.reply(messages, model)

    def _call_gemini(self, messages: Sequence[dict[str, str]], model: str) -> str:
        if self.gemini_client:
            candidates = [model]
            for fallback_model in GEMINI_MODEL_CANDIDATES:
                if fallback_model not in candidates:
                    candidates.append(fallback_model)
            last_error: Exception | None = None
            for candidate in candidates:
                try:
                    reply = self.gemini_client.reply(messages, candidate)
                    self.gemini_model = candidate
                    return reply
                except Exception as exc:
                    last_error = exc
            if not self.openrouter_client and last_error:
                raise last_error
        if self.openrouter_client:
            return self.openrouter_client.reply(messages, self.openrouter_gemini_model)
        raise RuntimeError("Gemini client is not configured")

    def _call_grok(self, messages: Sequence[dict[str, str]], model: str) -> str:
        if self.grok_client:
            discovered_models = self._discover_grok_models()
            preferred_models = list(discovered_models or GROK_MODEL_CANDIDATES)
            if model in preferred_models:
                candidates = [model]
                candidates.extend(fallback_model for fallback_model in preferred_models if fallback_model != model)
            else:
                candidates = preferred_models[:]
                if model:
                    candidates.append(model)
            for fallback_model in GROK_MODEL_CANDIDATES:
                if fallback_model not in candidates:
                    candidates.append(fallback_model)
            last_error: Exception | None = None
            for candidate in candidates:
                self._set_grok_progress(f"trying xAI model {candidate}")
                try:
                    reply = self.grok_client.reply(messages, candidate)
                    self.grok_model = candidate
                    self._set_grok_progress(f"xAI reply succeeded with {candidate}")
                    self._set_grok_ready(True)
                    return reply
                except Exception as exc:
                    last_error = exc
                    self._set_grok_progress(f"xAI model {candidate} failed: {exc}")
            if not self.openrouter_client and last_error:
                self._set_grok_ready(False)
                raise last_error
        if self.openrouter_client:
            self._set_grok_progress(
                f"xAI unavailable, falling back to OpenRouter model {self.openrouter_grok_model}"
            )
            return self.openrouter_client.reply(messages, self.openrouter_grok_model)
        raise RuntimeError("Grok client is not configured")

    def grok_response(self, text: str) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
        return self._call_grok(messages, self._model_for_provider("grok"))

    def _call_provider(self, decision: RouteDecision, messages: Sequence[dict[str, str]]) -> str:
        if decision.provider == "claude":
            return self._call_claude(messages, decision.model)
        if decision.provider == "gpt":
            return self._call_openai(messages, decision.model)
        if decision.provider == "gemini":
            return self._call_gemini(messages, decision.model)
        if decision.provider == "grok":
            return self._call_grok(messages, decision.model)
        return self._call_ollama(messages, decision.model)

    def get_reply(self, user_text: str) -> str:
        user_text = user_text.strip()
        self._publish_current_input(user_text)

        # --- World-class multi-LLM engine (v2) ---
        if _WORLD_CLASS:
            return self._get_reply_world_class(user_text)

        # --- Legacy fallback chain ---
        return self._get_reply_legacy(user_text)

    def _get_reply_world_class(self, user_text: str) -> str:
        """Use the multi-LLM orchestration engine with circuit breakers, RAG, and metrics."""
        # Build context with RAG (session history + Neo4j long-term memory)
        try:
            rag_context = build_rag_context(user_text)
        except Exception:
            rag_context = []

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(rag_context)
        messages.extend(self.history[-8:])
        messages.append({"role": "user", "content": user_text})

        # Determine strategy from complexity
        try:
            routing = classify_for_strategy(user_text)
        except Exception:
            routing = {"complexity": "medium", "strategy": "smartest"}

        complexity = routing["complexity"]
        strategy = routing["strategy"]
        self._set_progress(f"v2 engine: {strategy}/{complexity} for '{user_text[:40]}'")

        try:
            result = multi_llm_query(
                messages,
                strategy=strategy,
                max_tokens=200,
                temperature=0.7,
            )

            reply = result.get("text", "").strip()
            provider = result.get("provider", "unknown")
            latency_ms = result.get("latency_ms", 0)

            if reply:
                # Update local history
                self.history.extend([
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": reply},
                ])
                self.history = self.history[-10:]
                self._record_assistant_reply(reply)

                # Store to Redis and Neo4j
                try:
                    memory_push("user", user_text)
                    memory_push("assistant", reply, metadata={"provider": provider})
                    memory_store_neo4j(
                        self.session_id, "user", user_text,
                    )
                    memory_store_neo4j(
                        self.session_id, "assistant", reply,
                        provider=provider, complexity=complexity,
                        latency_ms=latency_ms, strategy=strategy,
                    )
                except Exception:
                    pass

                # Publish metrics
                try:
                    publish_metric(
                        "voice_response",
                        provider=provider,
                        latency_ms=latency_ms,
                        strategy=strategy,
                        complexity=complexity,
                    )
                except Exception:
                    pass

                decision = RouteDecision(provider, result.get("model", ""), complexity, strategy)
                self._publish_llm_used(decision, status="success")
                self._set_progress(f"v2 completed: {provider} in {latency_ms:.0f}ms")
                return reply

        except Exception as exc:
            self._set_progress(f"v2 engine error: {exc}, falling back to legacy")

        # Fall back to legacy if world-class engine fails
        return self._get_reply_legacy(user_text)

    def _get_reply_legacy(self, user_text: str) -> str:
        """Original fallback chain — reliable even without the v2 package."""
        messages = self._build_messages(user_text)
        primary = self.select_route(user_text)
        self._set_progress(f"legacy routing {primary.complexity} to {primary.provider}:{primary.model}")

        errors: list[str] = []
        for decision in self._fallback_chain(primary):
            self._publish_llm_used(decision, status="attempting")
            self._set_progress(f"query='{user_text[:48]}' using {decision.provider}:{decision.model}")
            try:
                reply = self._call_provider(decision, messages)
                if reply:
                    self._publish_llm_used(decision, status="success")
                    self.history.extend(
                        [
                            {"role": "user", "content": user_text},
                            {"role": "assistant", "content": reply},
                        ]
                    )
                    self.history = self.history[-10:]
                    self._record_assistant_reply(reply)
                    self._set_progress(f"completed with {decision.provider}:{decision.model}")
                    return reply
                raise RuntimeError(f"{decision.provider} returned an empty response")
            except Exception as exc:
                errors.append(f"{decision.provider}: {exc}")
                self._publish_llm_used(decision, status="failed")
                self._set_progress(f"{decision.provider} failed, trying fallback")

        detail = errors[-1] if errors else "No provider returned a response"
        return f"Sorry love, the language models are having a wobble right now. {detail}"

    def listen_once(self) -> np.ndarray:
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        prebuffer: Deque[np.ndarray] = deque(
            maxlen=max(1, int(PREBUFFER_SECONDS * SAMPLE_RATE / BLOCK_SIZE))
        )

        def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            if status:
                print(f"[audio] {status}", flush=True)
            audio_queue.put(indata[:, 0].copy())

        print("\n🎤 Listening... speak naturally.", flush=True)
        started = False
        start_hits = 0
        silence_seconds = 0.0
        collected: List[np.ndarray] = []
        speech_seconds = 0.0

        with sd.InputStream(
            samplerate=self.capture_rate,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            device=self.input_device,
            callback=callback,
        ):
            while True:
                chunk = audio_queue.get()
                if self.speaking:
                    continue

                rms = float(np.sqrt(np.mean(np.square(chunk)) + 1e-12))
                chunk_seconds = len(chunk) / SAMPLE_RATE

                if not started:
                    prebuffer.append(chunk)
                    if rms >= START_THRESHOLD:
                        start_hits += 1
                        if start_hits >= START_FRAMES:
                            started = True
                            collected.extend(list(prebuffer))
                            speech_seconds = sum(len(part) for part in collected) / SAMPLE_RATE
                            print("📝 Heard you, transcribing when you pause...", flush=True)
                    else:
                        start_hits = 0
                    continue

                collected.append(chunk)
                speech_seconds += chunk_seconds
                if rms < END_THRESHOLD:
                    silence_seconds += chunk_seconds
                else:
                    silence_seconds = 0.0

                if speech_seconds >= MAX_UTTERANCE_SECONDS:
                    break
                if speech_seconds >= MIN_SPEECH_SECONDS and silence_seconds >= END_SILENCE_SECONDS:
                    break

        if not collected:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(collected).astype(np.float32)
        trim_samples = int(max(0.0, silence_seconds - 0.15) * self.capture_rate)
        if trim_samples and trim_samples < audio.size:
            audio = audio[:-trim_samples]

        return resample_to(audio, self.capture_rate, SAMPLE_RATE)

    def run(self) -> None:
        self.check_services()
        self.speak(
            "Hey Joseph, Karen here. I'm ready now. Just start talking, and say stop any time to finish."
        )
        print("✅ Karen is live. Say 'stop' to end.", flush=True)

        while True:
            audio = self.listen_once()
            transcript = self.transcribe(audio)
            if not transcript:
                print("… I didn't catch that. Try again.", flush=True)
                continue

            print(f"\nYou: {transcript}", flush=True)
            if transcript.lower().strip() in EXIT_WORDS:
                goodbye = "No worries, Joseph. I'll be here when you want another chat."
                print(f"Karen: {goodbye}", flush=True)
                self.speak(goodbye)
                break

            reply = self.get_reply_from_bus(transcript)
            print(f"Karen: {reply}", flush=True)
            self.speak(reply)

    def demo(self, text: str) -> None:
        self.check_services()
        print(f"Demo input: {text}")
        reply = self.get_reply_from_bus(text)
        print(f"Karen: {reply}")
        self.speak(reply)

    def self_test(self) -> None:
        self.check_services()
        status = self.provider_status()
        print(
            "Provider status:",
            {
                "ollama": status.ollama_available,
                "claude": status.claude_available,
                "gpt": status.openai_available,
                "gemini": status.gemini_available,
                "grok": status.grok_available,
            },
        )

        print("Testing Cartesia TTS...")
        self.speak("Hello Joseph, Karen is online and ready for a chat.")

        print("Testing faster-whisper with synthetic audio...")
        response = self.cartesia.tts.generate(
            model_id=self.tts_model,
            transcript="Testing faster whisper transcription now.",
            voice={"mode": "id", "id": self.voice_id},
            output_format={"container": "wav", "encoding": "pcm_f32le", "sample_rate": TTS_SAMPLE_RATE},
            language="en",
        )
        wav_path = CACHE_DIR / "self_test.wav"
        response.write_to_file(str(wav_path))
        try:
            segments, _ = self.whisper.transcribe(str(wav_path), language="en", beam_size=1)
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            print(f"Whisper transcript: {transcript}")
            if "testing faster whisper" not in transcript.lower():
                raise RuntimeError("faster-whisper self-test transcript mismatch")
        finally:
            wav_path.unlink(missing_ok=True)

        print("Testing Redpanda voice response flow...", flush=True)
        request_id = self.publish_input_event("Voice bus self-test request.")
        publish_voice_event(
            VOICE_RESPONSE_TOPIC,
            {
                "request_id": request_id,
                "session_id": self.session_id,
                "text": "Hello Joseph, Redpanda is wired up and ready.",
                "source": "talk_to_karen.self_test",
                "timestamp": time.time(),
            },
        )
        response_payload = self._wait_for_bus_response(request_id)
        if not response_payload or "ready" not in str(response_payload.get("text", "")).lower():
            raise RuntimeError("Redpanda response self-test failed")
        print(f"Voice bus reply: {response_payload['text']}")

        if (
            status.ollama_available
            or status.claude_available
            or status.openai_available
            or status.gemini_available
            or status.grok_available
        ):
            route_simple = self.select_route("Hi Karen")
            route_complex = self.select_route(
                "Explain how Redis coordination helps multiple voice agents work together in detail."
            )
            route_gpt = self.select_route("Use GPT to help me write a tiny Python loop.")
            route_gemini = self.select_route("Please research the latest facts about Redis replication.")
            route_grok = self.select_route("Tell me a witty joke about voice assistants.")
            print(f"Simple route: {route_simple}")
            print(f"Complex route: {route_complex}")
            print(f"GPT route: {route_gpt}")
            print(f"Gemini route: {route_gemini}")
            print(f"Grok route: {route_grok}")

        self.redis.set(VOICE_INTEGRATION_COMPLETE_KEY, "true")
        self.redis.set(VOICE_ALL_LLMS_READY_KEY, "true")
        self._set_progress("self-test passed; integration complete")
        print("Self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Talk to Karen with mic -> Whisper -> smart LLM routing -> Cartesia")
    parser.add_argument("--demo", help="Skip microphone and send one text message")
    parser.add_argument("--self-test", action="store_true", help="Run integration checks and exit")
    parser.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL, help="faster-whisper model name")
    parser.add_argument(
        "--device",
        default=None,
        help="Input device index or name substring (e.g. 'AirPods' or '0'). Auto-detects AirPods if omitted.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio input devices and exit.",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
        return 0

    try:
        app = KarenVoiceChat(whisper_model=args.whisper_model, input_device=args.device)
        if args.self_test:
            app.self_test()
        elif args.demo:
            app.demo(args.demo)
        else:
            app.run()
        return 0
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
