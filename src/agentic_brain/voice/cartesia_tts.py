# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Cartesia Sonic 3 cloud TTS backend.

Provides an optional cloud TTS backend using Cartesia's Sonic 3 model.
The backend is only active when the ``cartesia`` Python package is
installed and ``CARTESIA_API_KEY`` is set in the environment.

This module is intentionally lightweight and lazy-loading so that
importing :mod:`agentic_brain.voice` never blocks MCP startup.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


class CartesiaTTS:
    """Cartesia Sonic 3 - 40ms TTFA, state space model.

    The Cartesia client is created lazily on first use so that importing
    this module has effectively zero overhead when the backend is not
    configured.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        model_id: str = "sonic-3",
        default_voice_id: Optional[str] = None,
        sample_rate: int = 44100,
        container: str = "wav",
        encoding: str = "pcm_s16le",
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("CARTESIA_API_KEY")
        self.model_id = model_id
        self.default_voice_id = default_voice_id or os.getenv("CARTESIA_VOICE_ID")
        self.sample_rate = sample_rate
        self.container = container
        self.encoding = encoding
        self._client = None
        self._cache_dir = cache_dir or Path.home() / ".cache" / "agentic-brain" / "cartesia"
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Cache directory is an optimization only – never fail construction
            logger.debug(
                "CartesiaTTS: unable to create cache dir %s", self._cache_dir, exc_info=True
            )

    def _ensure_client(self):
        """Lazily construct the Cartesia client.

        Raises:
            RuntimeError: if the API key is missing or the SDK is not installed.
        """

        if self._client is not None:
            return self._client

        if not self.api_key:
            raise RuntimeError(
                "Cartesia API key is not configured. Set CARTESIA_API_KEY in the environment."
            )

        try:
            from cartesia import Cartesia
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Cartesia Python client is not installed. "
                "Install with `pip install 'cartesia[websockets]'`."
            ) from exc

        self._client = Cartesia(api_key=self.api_key)
        return self._client

    def _resolve_voice_id(self, voice_id: Optional[str]) -> str:
        """Resolve the effective voice id.

        Priority:
        1. Explicit ``voice_id`` argument (unless "default" or empty)
        2. ``CARTESIA_VOICE_ID`` from environment
        """

        effective = voice_id
        if not effective or effective == "default":
            effective = self.default_voice_id
        if not effective:
            raise RuntimeError(
                "Cartesia voice_id is not configured. "
                "Pass voice_id explicitly or set CARTESIA_VOICE_ID."
            )
        return effective

    def synthesize(self, text: str, voice_id: str = "default") -> bytes:
        """Synthesize speech using Cartesia API.

        Returns WAV bytes encoded as ``pcm_s16le`` at the configured sample rate.
        """

        if not text or not text.strip():
            return b""

        client = self._ensure_client()
        resolved_voice_id = self._resolve_voice_id(voice_id)

        output_format = {
            "container": self.container,
            "encoding": self.encoding,
            "sample_rate": self.sample_rate,
        }

        logger.debug(
            "CartesiaTTS.synthesize: model=%s voice_id=%s sample_rate=%d",
            self.model_id,
            resolved_voice_id,
            self.sample_rate,
        )

        response = client.tts.generate(
            model_id=self.model_id,
            transcript=text,
            voice={"mode": "id", "id": resolved_voice_id},
            output_format=output_format,
        )

        tmp_path = self._cache_dir / f"cartesia_{int(time.time() * 1000)}.wav"
        try:
            # Official SDK exposes write_to_file(path) for convenience.
            response.write_to_file(str(tmp_path))
            return tmp_path.read_bytes()
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                logger.debug(
                    "CartesiaTTS: failed to remove temp file %s", tmp_path, exc_info=True
                )

    def synthesize_streaming(self, text: str) -> Iterator[bytes]:
        """Stream audio chunks for ultra-low latency.

        Yields raw PCM chunks (``pcm_f32le``) from the Cartesia websocket API.
        Callers are responsible for framing/decoding.
        """

        if not text or not text.strip():
            return

        client = self._ensure_client()
        resolved_voice_id = self._resolve_voice_id("default")

        try:
            with client.tts.websocket_connect() as connection:
                ctx = connection.context(
                    model_id=self.model_id,
                    voice={"mode": "id", "id": resolved_voice_id},
                    output_format={
                        "container": "raw",
                        "encoding": "pcm_f32le",
                        "sample_rate": self.sample_rate,
                    },
                )

                ctx.push(text)
                ctx.no_more_inputs()

                for response in ctx.receive():
                    audio = getattr(response, "audio", None)
                    if getattr(response, "type", None) == "chunk" and audio:
                        yield audio
        except Exception:  # pragma: no cover - network/SDK errors
            logger.exception("CartesiaTTS streaming synthesis failed")
            return
