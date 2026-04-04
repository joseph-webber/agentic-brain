"""Core SDK client for Agentic Brain.

Provides the main AgenticBrain client and supporting orchestration classes
for multi-LLM layered responses, voice I/O, and autonomous agents.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Literal

logger = logging.getLogger("agentic_brain")


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------

class DeploymentMode(Enum):
    """SDK deployment modes controlling provider selection."""
    AIRLOCKED = "airlocked"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class LayerName(Enum):
    """LLM response layers ordered by latency."""
    INSTANT = "instant"      # 0-500ms   (Groq, Ollama)
    FAST = "fast"            # 500ms-2s  (Haiku, GPT-4o-mini)
    DEEP = "deep"            # 2-10s     (Opus, GPT-4, Gemini)
    CONSENSUS = "consensus"  # 10s+      (multi-LLM verification)


@dataclass
class LLMResponse:
    """Response from a single LLM provider."""
    text: str
    provider: str
    model: str
    layer: LayerName
    latency_ms: float
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayeredResponse:
    """Aggregated response from multiple LLM layers."""
    responses: list[LLMResponse] = field(default_factory=list)
    consensus_text: str | None = None
    total_latency_ms: float = 0.0

    @property
    def best(self) -> LLMResponse | None:
        """Return the highest-quality response available."""
        if self.consensus_text:
            return LLMResponse(
                text=self.consensus_text,
                provider="consensus",
                model="multi-llm",
                layer=LayerName.CONSENSUS,
                latency_ms=self.total_latency_ms,
            )
        return self.responses[-1] if self.responses else None

    @property
    def instant(self) -> LLMResponse | None:
        """Return the instant-layer response if available."""
        return next(
            (r for r in self.responses if r.layer == LayerName.INSTANT), None
        )

    @property
    def deep(self) -> LLMResponse | None:
        """Return the deep-layer response if available."""
        return next(
            (r for r in self.responses if r.layer == LayerName.DEEP), None
        )


@dataclass
class VoiceConfig:
    """Configuration for voice input/output."""
    stt_provider: str = "whisper-local"
    tts_provider: str = "piper"
    tts_voice: str = "karen"
    sample_rate: int = 16000
    vad_enabled: bool = True
    wake_word: str | None = None


@dataclass
class AgentConfig:
    """Configuration for an autonomous agent."""
    name: str
    task: str
    self_heal: bool = True
    max_retries: int = 3
    layers: list[str] = field(default_factory=lambda: ["instant", "deep"])
    interval_seconds: float | None = None


# ---------------------------------------------------------------------------
# Provider Interfaces
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstract base for LLM providers (Ollama, Groq, OpenAI, etc.)."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...


class STTProvider(ABC):
    """Abstract base for speech-to-text providers."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, *, language: str = "en") -> str:
        ...


class TTSProvider(ABC):
    """Abstract base for text-to-speech providers."""

    @abstractmethod
    async def synthesize(self, text: str, *, voice: str = "default") -> bytes:
        ...


# ---------------------------------------------------------------------------
# LLM Layer Orchestrator
# ---------------------------------------------------------------------------

class LLMLayer:
    """Orchestrates multi-layer LLM responses with cascading fallback.

    Each layer has a latency budget and preferred providers. Layers fire
    concurrently and results stream back as they arrive.

    Example::

        layer = LLMLayer(mode=DeploymentMode.HYBRID)
        response = await layer.query(
            "Explain quantum computing",
            layers=[LayerName.INSTANT, LayerName.DEEP],
        )
        # response.instant -> fast Groq answer (< 500ms)
        # response.deep    -> detailed Claude answer (< 10s)
    """

    LAYER_DEFAULTS: dict[LayerName, dict[str, Any]] = {
        LayerName.INSTANT: {
            "timeout_ms": 500,
            "providers_cloud": ["groq"],
            "providers_local": ["ollama"],
        },
        LayerName.FAST: {
            "timeout_ms": 2000,
            "providers_cloud": ["claude-haiku", "gpt-4o-mini"],
            "providers_local": ["ollama"],
        },
        LayerName.DEEP: {
            "timeout_ms": 10000,
            "providers_cloud": ["claude-opus", "gpt-4", "gemini-pro"],
            "providers_local": ["ollama"],
        },
        LayerName.CONSENSUS: {
            "timeout_ms": 30000,
            "min_providers": 3,
            "agreement_threshold": 0.8,
        },
    }

    def __init__(
        self,
        mode: DeploymentMode = DeploymentMode.HYBRID,
        providers: dict[str, LLMProvider] | None = None,
    ) -> None:
        self.mode = mode
        self._providers: dict[str, LLMProvider] = providers or {}
        self._layer_config = dict(self.LAYER_DEFAULTS)

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        """Register an LLM provider by name."""
        self._providers[name] = provider

    async def query(
        self,
        prompt: str,
        *,
        layers: list[LayerName] | None = None,
        system: str | None = None,
    ) -> LayeredResponse:
        """Send a prompt through the requested layers concurrently."""
        layers = layers or [LayerName.INSTANT]
        result = LayeredResponse()
        start = time.monotonic()

        tasks = [
            self._query_layer(prompt, layer, system=system) for layer in layers
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, LLMResponse):
                result.responses.append(resp)
            elif isinstance(resp, Exception):
                logger.warning("Layer query failed: %s", resp)

        result.responses.sort(key=lambda r: r.latency_ms)
        result.total_latency_ms = (time.monotonic() - start) * 1000

        if LayerName.CONSENSUS in layers and len(result.responses) >= 2:
            result.consensus_text = self._build_consensus(result.responses)

        return result

    async def _query_layer(
        self,
        prompt: str,
        layer: LayerName,
        *,
        system: str | None = None,
    ) -> LLMResponse:
        """Query a single layer, trying providers in priority order."""
        config = self._layer_config[layer]
        timeout = config["timeout_ms"] / 1000.0
        provider_names = self._resolve_providers(layer)

        for name in provider_names:
            provider = self._providers.get(name)
            if provider is None:
                continue
            try:
                return await asyncio.wait_for(
                    provider.complete(prompt, system=system),
                    timeout=timeout,
                )
            except (TimeoutError, asyncio.TimeoutError):
                logger.debug("Provider %s timed out for layer %s", name, layer.value)
            except Exception:
                logger.debug(
                    "Provider %s failed for layer %s", name, layer.value, exc_info=True
                )

        raise RuntimeError(f"All providers exhausted for layer {layer.value}")

    def _resolve_providers(self, layer: LayerName) -> list[str]:
        """Return provider names for the layer based on deployment mode."""
        config = self._layer_config[layer]
        if self.mode == DeploymentMode.AIRLOCKED:
            return config.get("providers_local", [])
        if self.mode == DeploymentMode.CLOUD:
            return config.get("providers_cloud", [])
        # Hybrid: local first, then cloud
        return config.get("providers_local", []) + config.get("providers_cloud", [])

    @staticmethod
    def _build_consensus(responses: list[LLMResponse]) -> str:
        """Merge multiple responses into a consensus answer (placeholder)."""
        texts = [r.text for r in responses]
        return max(texts, key=len)


# ---------------------------------------------------------------------------
# Voice Manager
# ---------------------------------------------------------------------------

class VoiceManager:
    """Manages speech-to-text and text-to-speech with provider fallback.

    Supports airlocked (whisper.cpp + Piper), cloud (Groq + Cartesia),
    and hybrid modes.

    Example::

        voice = VoiceManager(mode=DeploymentMode.HYBRID)
        text = await voice.listen()           # STT
        await voice.speak("Hello Joseph")     # TTS
    """

    def __init__(
        self,
        mode: DeploymentMode = DeploymentMode.HYBRID,
        config: VoiceConfig | None = None,
        stt_providers: dict[str, STTProvider] | None = None,
        tts_providers: dict[str, TTSProvider] | None = None,
    ) -> None:
        self.mode = mode
        self.config = config or VoiceConfig()
        self._stt: dict[str, STTProvider] = stt_providers or {}
        self._tts: dict[str, TTSProvider] = tts_providers or {}
        self._listening = False

    def register_stt(self, name: str, provider: STTProvider) -> None:
        self._stt[name] = provider

    def register_tts(self, name: str, provider: TTSProvider) -> None:
        self._tts[name] = provider

    async def listen(self, *, audio_bytes: bytes | None = None) -> str:
        """Transcribe speech to text using the configured STT provider chain."""
        if audio_bytes is None:
            audio_bytes = await self._capture_audio()

        for name, provider in self._stt.items():
            try:
                return await provider.transcribe(audio_bytes)
            except Exception:
                logger.warning("STT provider %s failed, trying next", name)

        raise RuntimeError("All STT providers failed")

    async def speak(self, text: str, *, voice: str | None = None) -> bytes:
        """Synthesize text to speech using the configured TTS provider chain."""
        voice = voice or self.config.tts_voice

        for name, provider in self._tts.items():
            try:
                return await provider.synthesize(text, voice=voice)
            except Exception:
                logger.warning("TTS provider %s failed, trying next", name)

        raise RuntimeError("All TTS providers failed")

    async def _capture_audio(self) -> bytes:
        """Capture audio from the default input device (platform-specific)."""
        raise NotImplementedError(
            "Audio capture requires a platform-specific implementation. "
            "Pass audio_bytes directly or register a capture plugin."
        )


# ---------------------------------------------------------------------------
# Agent Orchestrator
# ---------------------------------------------------------------------------

class AgentOrchestrator:
    """Manages autonomous agents with self-healing and event-driven execution.

    Agents can run on schedules, respond to events, or execute one-shot tasks.
    Failed agents are automatically retried with exponential backoff.

    Example::

        orchestrator = AgentOrchestrator(llm_layer=layer)
        agent_id = await orchestrator.spawn(AgentConfig(
            name="code-reviewer",
            task="Review the latest PR for security issues",
            layers=["instant", "deep"],
        ))
        result = await orchestrator.wait(agent_id)
    """

    def __init__(self, llm_layer: LLMLayer) -> None:
        self._llm = llm_layer
        self._agents: dict[str, _RunningAgent] = {}
        self._event_handlers: dict[str, list[Callable[..., Any]]] = {}

    async def spawn(self, config: AgentConfig) -> str:
        """Spawn an autonomous agent and return its ID."""
        agent_id = f"agent-{config.name}-{int(time.time() * 1000)}"
        agent = _RunningAgent(
            id=agent_id,
            config=config,
            llm=self._llm,
        )
        self._agents[agent_id] = agent
        asyncio.create_task(agent.run())
        logger.info("Spawned agent %s: %s", agent_id, config.task)
        return agent_id

    async def wait(self, agent_id: str, *, timeout: float = 60.0) -> str:
        """Wait for an agent to complete and return its result."""
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        return await asyncio.wait_for(agent.result_future, timeout=timeout)

    async def cancel(self, agent_id: str) -> None:
        """Cancel a running agent."""
        agent = self._agents.get(agent_id)
        if agent and agent.task:
            agent.task.cancel()
            logger.info("Cancelled agent %s", agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        """Return status of all agents."""
        return [
            {
                "id": a.id,
                "name": a.config.name,
                "status": a.status,
                "retries": a.retries,
            }
            for a in self._agents.values()
        ]

    def on(self, event: str) -> Callable:
        """Decorator to register an event handler."""
        def decorator(fn: Callable) -> Callable:
            self._event_handlers.setdefault(event, []).append(fn)
            return fn
        return decorator

    async def emit(self, event: str, data: Any = None) -> None:
        """Emit an event to all registered handlers."""
        for handler in self._event_handlers.get(event, []):
            try:
                result = handler(data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Event handler failed for %s", event)


@dataclass
class _RunningAgent:
    """Internal representation of a running agent."""
    id: str
    config: AgentConfig
    llm: LLMLayer
    status: str = "pending"
    retries: int = 0
    task: asyncio.Task[str] | None = None
    result_future: asyncio.Future[str] = field(
        default_factory=lambda: asyncio.get_event_loop().create_future()
    )

    async def run(self) -> None:
        self.status = "running"
        layers = [LayerName(name) for name in self.config.layers]

        while self.retries <= self.config.max_retries:
            try:
                response = await self.llm.query(self.config.task, layers=layers)
                best = response.best
                result = best.text if best else ""
                self.status = "completed"
                if not self.result_future.done():
                    self.result_future.set_result(result)
                return
            except Exception as exc:
                self.retries += 1
                logger.warning(
                    "Agent %s failed (attempt %d/%d): %s",
                    self.id, self.retries, self.config.max_retries, exc,
                )
                if self.retries > self.config.max_retries:
                    self.status = "failed"
                    if not self.result_future.done():
                        self.result_future.set_exception(exc)
                    return
                backoff = min(2 ** self.retries, 30)
                await asyncio.sleep(backoff)


# ---------------------------------------------------------------------------
# Main Client
# ---------------------------------------------------------------------------

class AgenticBrain:
    """Top-level SDK client -- the single entry point for all brain features.

    Wraps LLM orchestration, voice I/O, and autonomous agents behind a
    unified, mode-aware interface.

    Args:
        mode: Deployment mode ("airlocked", "cloud", "hybrid").
        voice_config: Optional voice I/O settings.

    Example::

        brain = AgenticBrain(mode="hybrid")

        # Simple chat
        response = await brain.chat("What is the weather?")

        # Multi-layer chat
        layered = await brain.chat(
            "Explain relativity",
            layers=["instant", "deep"],
        )
        print(layered.instant.text)   # fast answer
        print(layered.deep.text)      # thorough answer

        # Voice conversation
        text = await brain.listen()
        await brain.speak("I heard you say: " + text)

        # Spawn an autonomous agent
        agent_id = await brain.spawn_agent(AgentConfig(
            name="researcher",
            task="Find the top 5 AI papers this week",
        ))
        result = await brain.wait_agent(agent_id)
    """

    def __init__(
        self,
        mode: Literal["airlocked", "cloud", "hybrid"] = "hybrid",
        voice_config: VoiceConfig | None = None,
    ) -> None:
        self.mode = DeploymentMode(mode)
        self.llm = LLMLayer(mode=self.mode)
        self.voice = VoiceManager(mode=self.mode, config=voice_config)
        self.agents = AgentOrchestrator(llm_layer=self.llm)
        logger.info("AgenticBrain initialised in %s mode", self.mode.value)

    # -- LLM shortcuts -----------------------------------------------------

    async def chat(
        self,
        prompt: str,
        *,
        layers: list[str] | None = None,
        system: str | None = None,
    ) -> LayeredResponse:
        """Send a chat message through the requested LLM layers."""
        layer_enums = [LayerName(name) for name in (layers or ["instant"])]
        return await self.llm.query(prompt, layers=layer_enums, system=system)

    async def stream_chat(
        self,
        prompt: str,
        *,
        provider: str | None = None,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response token-by-token from a single provider."""
        name = provider or next(iter(self.llm._providers), None)
        if name is None or name not in self.llm._providers:
            raise RuntimeError("No LLM providers registered")
        async for token in self.llm._providers[name].stream(prompt, system=system):
            yield token

    # -- Voice shortcuts ---------------------------------------------------

    async def listen(self, *, audio_bytes: bytes | None = None) -> str:
        """Listen for speech and return transcribed text."""
        return await self.voice.listen(audio_bytes=audio_bytes)

    async def speak(self, text: str, *, voice: str | None = None) -> bytes:
        """Speak text aloud and return the audio bytes."""
        return await self.voice.speak(text, voice=voice)

    # -- Agent shortcuts ---------------------------------------------------

    async def spawn_agent(self, config: AgentConfig) -> str:
        """Spawn an autonomous agent."""
        return await self.agents.spawn(config)

    async def wait_agent(self, agent_id: str, *, timeout: float = 60.0) -> str:
        """Wait for an agent to finish."""
        return await self.agents.wait(agent_id, timeout=timeout)

    # -- Event system ------------------------------------------------------

    def on(self, event: str) -> Callable:
        """Register an event handler."""
        return self.agents.on(event)

    async def emit(self, event: str, data: Any = None) -> None:
        """Emit an event."""
        await self.agents.emit(event, data)

    # -- Provider registration ---------------------------------------------

    def register_llm(self, name: str, provider: LLMProvider) -> None:
        """Register an LLM provider."""
        self.llm.register_provider(name, provider)

    def register_stt(self, name: str, provider: STTProvider) -> None:
        """Register a speech-to-text provider."""
        self.voice.register_stt(name, provider)

    def register_tts(self, name: str, provider: TTSProvider) -> None:
        """Register a text-to-speech provider."""
        self.voice.register_tts(name, provider)
