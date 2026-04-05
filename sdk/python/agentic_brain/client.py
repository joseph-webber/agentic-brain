"""
Agentic Brain SDK - Universal AI Orchestration

Usage:
    from agentic_brain import AgenticBrain

    brain = AgenticBrain(mode="hybrid")
    response = await brain.chat("Hello!")
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

import httpx


class DeploymentMode(str, Enum):
    AIRLOCKED = "airlocked"  # 100% local
    CLOUD = "cloud"  # Remote APIs only
    HYBRID = "hybrid"  # Local + cloud fallback


class ResponseLayer(str, Enum):
    INSTANT = "instant"  # 0-500ms (Groq)
    FAST = "fast"  # 500ms-2s (Ollama)
    DEEP = "deep"  # 2-10s (Claude/GPT)
    CONSENSUS = "consensus"  # 10s+ (multi-LLM)


@dataclass
class LayeredResponse:
    instant: Optional[str] = None
    fast: Optional[str] = None
    deep: Optional[str] = None
    consensus: Optional[str] = None
    final: str = ""
    elapsed_ms: float = 0.0


class AgenticBrain:
    """Main SDK client for agentic-brain."""

    def __init__(
        self,
        mode: DeploymentMode | str = DeploymentMode.HYBRID,
        groq_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        ollama_url: str = "http://localhost:11434",
        instant_model: str = "llama-3.1-8b-instant",
        fast_model: str = "llama3.2:3b",
        deep_model: str = "claude-3-5-sonnet-latest",
        openai_model: str = "gpt-4o-mini",
        consensus_model: str = "claude-3-5-sonnet-latest",
        timeout: float = 60.0,
    ):
        self.mode = self._coerce_mode(mode)
        self._groq_key = groq_key or os.getenv("GROQ_API_KEY")
        self._openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self._anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        self._ollama_url = ollama_url.rstrip("/")
        self._instant_model = instant_model
        self._fast_model = fast_model
        self._deep_model = deep_model
        self._openai_model = openai_model
        self._consensus_model = consensus_model
        self._timeout = timeout
        self._llm_router = None
        self._voice_manager = None
        self._history: list[dict[str, str]] = []

    async def chat(
        self,
        message: str,
        layers: Optional[list[ResponseLayer | str]] = None,
        stream: bool = False,
    ) -> LayeredResponse:
        """Send a chat message and get layered responses."""
        normalized_layers = self._normalize_layers(layers)
        response = LayeredResponse()
        started = time.perf_counter()

        self._history.append({"role": "user", "content": message})

        async for layer, text in self._run_layers(message, normalized_layers):
            self._assign_layer(response, layer, text)
            if stream:
                await asyncio.sleep(0)

        response.final = self._pick_final(response)
        response.elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        if response.final:
            self._history.append({"role": "assistant", "content": response.final})
        return response

    async def chat_stream(
        self,
        message: str,
        layers: Optional[list[ResponseLayer | str]] = None,
    ) -> AsyncIterator[str]:
        """Stream chat responses as they arrive."""
        normalized_layers = self._normalize_layers(layers)
        response = LayeredResponse()
        self._history.append({"role": "user", "content": message})

        async for layer, text in self._run_layers(message, normalized_layers):
            self._assign_layer(response, layer, text)
            yield text

        response.final = self._pick_final(response)
        if response.final:
            self._history.append({"role": "assistant", "content": response.final})

    async def _run_layers(
        self,
        message: str,
        layers: list[ResponseLayer],
    ) -> AsyncIterator[tuple[ResponseLayer, str]]:
        tasks = [
            asyncio.create_task(self._execute_layer(layer, message)) for layer in layers
        ]

        for completed in asyncio.as_completed(tasks):
            layer, text = await completed
            if text:
                yield layer, text

    async def _execute_layer(
        self,
        layer: ResponseLayer,
        message: str,
    ) -> tuple[ResponseLayer, str]:
        layer_map = {
            ResponseLayer.INSTANT: self._get_instant,
            ResponseLayer.FAST: self._get_fast,
            ResponseLayer.DEEP: self._get_deep,
            ResponseLayer.CONSENSUS: self._get_consensus,
        }
        return layer, await layer_map[layer](message)

    async def _get_instant(self, message: str) -> str:
        """Get instant response from Groq or local."""
        if self.mode != DeploymentMode.AIRLOCKED and self._groq_key:
            return await self._call_groq(model=self._instant_model, message=message)
        return await self._get_fast(message)

    async def _get_fast(self, message: str) -> str:
        """Get fast response from Ollama."""
        if self.mode == DeploymentMode.CLOUD:
            if self._groq_key:
                return await self._call_groq(model=self._instant_model, message=message)
            if self._openai_key:
                return await self._call_openai(
                    model=self._openai_model, message=message
                )
            if self._anthropic_key:
                return await self._call_anthropic(
                    model="claude-3-5-haiku-latest",
                    message=message,
                )
            return ""
        return await self._call_ollama(model=self._fast_model, message=message)

    async def _get_deep(self, message: str) -> str:
        """Get deep response from Claude/GPT."""
        if self.mode == DeploymentMode.AIRLOCKED:
            return await self._get_fast(message)
        if self._anthropic_key:
            return await self._call_anthropic(model=self._deep_model, message=message)
        if self._openai_key:
            return await self._call_openai(model=self._openai_model, message=message)
        if self._groq_key:
            return await self._call_groq(
                model="llama-3.3-70b-versatile",
                message=message,
            )
        return (
            await self._get_fast(message) if self.mode == DeploymentMode.HYBRID else ""
        )

    async def _get_consensus(self, message: str) -> str:
        """Get a synthesized consensus response from multiple layers."""
        fast, deep = await self._gather_for_consensus(message)
        if not deep:
            return fast
        if not fast or fast == deep:
            return deep

        synthesis_prompt = (
            "Combine the following two answers into one concise, accurate response. "
            "Prefer the more correct detail when they disagree.\n\n"
            f"Fast answer:\n{fast}\n\n"
            f"Deep answer:\n{deep}"
        )

        if self.mode != DeploymentMode.AIRLOCKED and self._anthropic_key:
            return await self._call_anthropic(
                model=self._consensus_model,
                message=synthesis_prompt,
            )
        if self.mode != DeploymentMode.AIRLOCKED and self._openai_key:
            return await self._call_openai(
                model=self._openai_model,
                message=synthesis_prompt,
            )
        return deep

    async def _gather_for_consensus(self, message: str) -> tuple[str, str]:
        fast_task = asyncio.create_task(self._get_fast(message))
        deep_task = asyncio.create_task(self._get_deep(message))
        return await asyncio.gather(fast_task, deep_task)

    async def _call_ollama(self, model: str, message: str) -> str:
        return await self._post_json(
            f"{self._ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": message,
                "stream": False,
            },
            extractor=lambda data: data.get("response", ""),
        )

    async def _call_groq(self, model: str, message: str) -> str:
        return await self._post_json(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._groq_key}"},
            json={
                "model": model,
                "messages": self._messages(message),
                "temperature": 0.2,
            },
            extractor=self._extract_chat_completion,
        )

    async def _call_openai(self, model: str, message: str) -> str:
        return await self._post_json(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._openai_key}"},
            json={
                "model": model,
                "messages": self._messages(message),
                "temperature": 0.2,
            },
            extractor=self._extract_chat_completion,
        )

    async def _call_anthropic(self, model: str, message: str) -> str:
        return await self._post_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._anthropic_key or "",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "messages": self._anthropic_messages(message),
            },
            extractor=self._extract_anthropic_message,
        )

    async def _post_json(
        self,
        url: str,
        *,
        json: dict[str, Any],
        extractor: Callable[[dict[str, Any]], str],
        headers: Optional[dict[str, str]] = None,
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=json, headers=headers)
                response.raise_for_status()
                return extractor(response.json())
        except httpx.HTTPError:
            return ""

    def clear_history(self) -> None:
        """Clear stored conversation history."""
        self._history.clear()

    def _messages(self, message: str) -> list[dict[str, str]]:
        messages = [
            {"role": entry["role"], "content": entry["content"]}
            for entry in self._history[-10:]
            if entry["role"] in {"user", "assistant"}
        ]
        if messages and messages[-1] == {"role": "user", "content": message}:
            return messages
        messages.append({"role": "user", "content": message})
        return messages

    def _anthropic_messages(self, message: str) -> list[dict[str, str]]:
        return self._messages(message)

    def _normalize_layers(
        self,
        layers: Optional[list[ResponseLayer | str]],
    ) -> list[ResponseLayer]:
        if layers is None:
            return [ResponseLayer.INSTANT, ResponseLayer.DEEP]
        return [
            layer if isinstance(layer, ResponseLayer) else ResponseLayer(layer)
            for layer in layers
        ]

    @staticmethod
    def _pick_final(response: LayeredResponse) -> str:
        return (
            response.consensus
            or response.deep
            or response.fast
            or response.instant
            or ""
        )

    @staticmethod
    def _assign_layer(
        response: LayeredResponse,
        layer: ResponseLayer,
        text: str,
    ) -> None:
        if layer == ResponseLayer.INSTANT:
            response.instant = text
        elif layer == ResponseLayer.FAST:
            response.fast = text
        elif layer == ResponseLayer.DEEP:
            response.deep = text
        elif layer == ResponseLayer.CONSENSUS:
            response.consensus = text
        if text:
            response.final = text

    @staticmethod
    def _coerce_mode(mode: DeploymentMode | str) -> DeploymentMode:
        return mode if isinstance(mode, DeploymentMode) else DeploymentMode(mode)

    @staticmethod
    def _extract_chat_completion(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content", ""))

    @staticmethod
    def _extract_anthropic_message(data: dict[str, Any]) -> str:
        content = data.get("content") or []
        if not content:
            return ""
        first = content[0] or {}
        return str(first.get("text", ""))
