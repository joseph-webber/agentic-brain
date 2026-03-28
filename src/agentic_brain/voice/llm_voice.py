# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Local LLM Voice Integration for Agentic Brain.
#
# Uses Ollama local LLM for:
# 1. Generating conversational responses in voice style
# 2. Adding personality to voice messages
# 3. Real-time voice processing without external API limits

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx


@dataclass
class VoicePersonality:
    """Configuration for a voice personality.

    Attributes:
        name: Display name used in prompts.
        style: General style hint (friendly, professional, calm, excited).
        region: Region hint used in prompts (e.g. adelaide, uk, ireland).
        catchphrases: List of natural expressions this personality might use.
    """

    name: str
    style: str  # "friendly", "professional", "excited", "calm", etc.
    region: str  # "adelaide", "melbourne", etc.
    catchphrases: List[str]


VOICE_PERSONALITIES: Dict[str, VoicePersonality] = {
    "karen": VoicePersonality(
        name="Karen",
        style="friendly",
        region="adelaide",
        catchphrases=["heaps good!", "no worries", "she'll be right"],
    ),
    "daniel": VoicePersonality(
        name="Daniel",
        style="professional",
        region="uk",
        catchphrases=["brilliant!", "quite right", "indeed"],
    ),
    "moira": VoicePersonality(
        name="Moira",
        style="warm",
        region="ireland",
        catchphrases=["grand!", "lovely", "fair play"],
    ),
}


class LocalLLMVoice:
    """Local LLM for voice-friendly text generation.

    This uses the local Ollama HTTP API by default, so it works offline and has
    no cloud rate limits. It is intentionally lightweight and independent from
    the main smart router.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: str = "llama3.2:3b",
        timeout: float = 30.0,
    ) -> None:
        # Allow override via environment while keeping a sensible default.
        env_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self._base_url = (base_url or env_host).rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(timeout=timeout)

    async def _post(self, path: str, payload: dict) -> dict:
        """Internal helper for POST requests with basic error handling.

        Returns parsed JSON dict or raises httpx.HTTPError.
        """

        url = f"{self._base_url}{path}"
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    async def generate_voice_response(
        self,
        prompt: str,
        personality: str = "karen",
        max_tokens: int = 100,
    ) -> str:
        """Generate a short, voice-friendly response using the local LLM.

        The response is tuned for text-to-speech: short (1-2 sentences),
        conversational, and free of markdown or emojis.
        """

        key = personality.lower()
        persona = VOICE_PERSONALITIES.get(key, VOICE_PERSONALITIES["karen"])

        system_prompt = (
            f"You are {persona.name}, a {persona.style} voice assistant from {persona.region}.\n"
            "Your responses are SHORT (1-2 sentences max) and sound natural when spoken aloud.\n"
            f"You sometimes use phrases like: {', '.join(persona.catchphrases)}\n"
            "Never use emojis, markdown, or special characters.\n"
            "Respond conversationally and clearly for a blind user listening with a screen reader."
        )

        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7,
            },
        }

        try:
            data = await self._post("/api/generate", payload)
            text = str(data.get("response", "")).strip()
            # Basic safety: never return empty string if we can avoid it.
            return text or "Sorry, I did not have anything to say just then."
        except httpx.HTTPError as e:
            return f"Sorry, I couldn't process that with the local model. {e}".strip()
        except Exception as e:  # pragma: no cover - defensive
            return (
                f"Sorry, something went wrong with the local voice engine. {e}".strip()
            )

    async def make_voice_friendly(self, text: str) -> str:
        """Convert arbitrary text to something natural when spoken aloud.

        This is useful for turning technical or verbose messages into a concise
        sentence that Joseph can listen to comfortably.
        """

        prompt = (
            "Convert this text to be more natural when spoken aloud. "
            "Remove any special characters, abbreviations, or technical jargon. "
            "Keep it SHORT (1-2 sentences). Input: "
            f"{text}"
        )

        return await self.generate_voice_response(prompt)

    async def add_regional_flavor(self, text: str, region: str) -> str:
        """Add regional expressions to text while keeping it natural.

        Example: add Adelaide / Australian expressions, but still sound clear
        and understandable for Joseph.
        """

        prompt = (
            f"Add natural {region} expressions to this text while keeping it clear "
            f"and easy to understand when spoken aloud:\n\n{text}\n\n"
            "Keep it SHORT and natural sounding."
        )

        return await self.generate_voice_response(prompt)


# Global singleton instance (lazy-initialized)
_llm_voice: Optional[LocalLLMVoice] = None


async def get_llm_voice() -> LocalLLMVoice:
    """Get a shared LocalLLMVoice instance.

    This avoids re-creating HTTP clients for every call while keeping the
    public API very simple.
    """

    global _llm_voice
    if _llm_voice is None:
        _llm_voice = LocalLLMVoice()
    return _llm_voice


# Convenience functions -----------------------------------------------------


async def speak_with_personality(text: str, personality: str = "karen") -> str:
    """Generate a personality-driven response for the given text.

    This returns the generated text; actual speaking is handled by the main
    voice subsystem so we never overlap with the queue.
    """

    llm = await get_llm_voice()
    return await llm.generate_voice_response(text, personality=personality)


async def regionalize_speech(text: str, region: str = "adelaide") -> str:
    """Add regional flavour to speech while keeping it accessible."""

    llm = await get_llm_voice()
    return await llm.add_regional_flavor(text, region)


# Streaming / real-time voice ----------------------------------------------


def _split_completed_sentences(buffer: str) -> Tuple[List[str], str]:
    """Split buffer into completed sentences and remainder.

    Sentences are split on '.', '!' or '?'. Returns (sentences, remainder).
    """

    sentences: List[str] = []
    start = 0
    while start < len(buffer):
        idxs = [buffer.find(p, start) for p in ".!?" if buffer.find(p, start) != -1]
        if not idxs:
            break
        end = min(idxs) + 1
        sentence = buffer[start:end].strip()
        if sentence:
            sentences.append(sentence)
        start = end
    remainder = buffer[start:].lstrip()
    return sentences, remainder


def _speak_sentence(text: str, voice: str) -> None:
    """Speak a single sentence using the main audio system when available.

    Falls back to macOS `say` via the global speech lock if the audio
    subsystem is not available. This ensures we never overlap voices.
    """

    try:
        from agentic_brain.audio import speak as audio_speak

        audio_speak(text, voice=voice)
        return
    except Exception:
        # Fall back to direct macOS TTS via global lock.
        try:
            import platform as _platform

            if _platform.system() == "Darwin":
                from agentic_brain.voice._speech_lock import global_speak

                global_speak(["say", "-v", voice, text], timeout=60)
        except Exception:
            return


async def stream_voice_response(prompt: str, voice: str = "Karen (Premium)") -> None:
    """Stream voice as it's generated from the local LLM.

    Tokens are streamed from Ollama and buffered until a sentence completes,
    then spoken immediately using the main audio system. This gives Joseph
    immediate feedback without waiting for the whole response.
    """

    llm = await get_llm_voice()

    payload = {
        "model": llm._model,  # type: ignore[attr-defined]
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.7,
        },
    }

    buffer = ""

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{llm._base_url}/api/generate",  # type: ignore[attr-defined]
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    chunk = data.get("response", "")
                    if not chunk:
                        continue

                    buffer += chunk
                    sentences, buffer = _split_completed_sentences(buffer)
                    for sentence in sentences:
                        _speak_sentence(sentence, voice)

        # Speak any remaining text.
        if buffer.strip():
            _speak_sentence(buffer.strip(), voice)

    except Exception:
        # Streaming is best-effort; failures should not crash the brain.
        return


# Voice fallback chain ------------------------------------------------------

VOICE_FALLBACK_CHAIN: List[Tuple[str, str]] = [
    ("cloud_llm", "Claude/GPT for complex responses"),
    ("local_llm", "Ollama for quick responses"),
    ("template", "Pre-built response templates"),
    ("echo", "Just speak the input as-is"),
]


async def smart_voice_response(prompt: str, personality: str = "karen") -> str:
    """Generate a voice response using a simple fallback chain.

    Currently prefers the local LLM first; cloud LLMs and templates are left as
    future extensions but kept in the chain for clarity.
    """

    last_error: Optional[Exception] = None

    for method, _ in VOICE_FALLBACK_CHAIN:
        try:
            if method == "cloud_llm":
                # Cloud LLM integration is handled elsewhere; skip for now.
                continue
            if method == "local_llm":
                llm = await get_llm_voice()
                return await llm.generate_voice_response(
                    prompt, personality=personality
                )
            if method == "template":
                # Simple template-based fallback.
                return prompt
            if method == "echo":
                return prompt
        except Exception as e:  # pragma: no cover - defensive
            last_error = e
            continue

    # If everything failed, return the original prompt so at least something
    # can be spoken by the caller.
    if last_error:
        return prompt
    return prompt
