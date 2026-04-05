# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WebSocket API for real-time voice streaming.

This module provides a lightweight WebSocket server that can be used by the
future web portal (or other clients) to stream raw audio bytes to the brain
and receive incremental transcription results.

Design goals
------------
* **Optional dependency** – only active when ``websockets`` is installed.
* **Side‑effect free import** – no sockets opened at import time.
* **Simple integration hook** – a pluggable transcriber callback that can be
  wired to whatever speech recognition backend we choose.
* **Safe default behaviour** – if no transcriber is configured, we simply
  echo basic metadata so clients can still exercise the transport layer.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Set

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StreamingAPIConfig:
    """Configuration for :class:`VoiceStreamingAPI`.

    Attributes:
        host: Interface to bind to.
        port: TCP port for the WebSocket server.
        sample_rate: Expected audio sample rate in Hz.
        chunk_size: Recommended audio chunk size in bytes.
    """

    host: str = "localhost"
    port: int = 8765
    sample_rate: int = 16_000
    chunk_size: int = 4096


TranscriberFn = Callable[
    [bytes], Awaitable[dict[str, Any] | str | None] | dict[str, Any] | str | None
]


class VoiceStreamingAPI:
    """WebSocket server for voice streaming.

    The server is intentionally small and framework‑agnostic so that higher
    layers (FastAPI, Starlette, Django, etc.) can embed or wrap it as needed.

    Typical usage::

        api = VoiceStreamingAPI()
        api.set_transcriber(my_async_transcriber)
        await api.start()
        await api.wait_closed()

    A *transcriber* is an optional callable that receives raw audio bytes and
    returns either a transcription ``str`` or a result ``dict`` which will be
    JSON‑encoded and sent back to the client.
    """

    def __init__(self, config: Optional[StreamingAPIConfig] = None) -> None:
        self.config = config or StreamingAPIConfig()
        self._server: Any = None
        self._clients: Set[Any] = set()
        self._transcriber: Optional[TranscriberFn] = None
        self._running: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket server.

        This method is a no‑op when the optional :mod:`websockets` dependency
        is not installed.  Callers can check :pyattr:`running` afterwards.
        """

        if self._running:
            return

        try:
            import websockets  # type: ignore[import]
        except ImportError:  # pragma: no cover - exercised via log message
            logger.warning("websockets not installed - streaming API unavailable")
            return

        self._server = await websockets.serve(  # type: ignore[call-arg]
            self._handle_client,
            self.config.host,
            self.config.port,
        )
        self._running = True
        logger.info(
            "Voice streaming API started on ws://%s:%s",
            self.config.host,
            self.config.port,
        )

    async def stop(self) -> None:
        """Stop the WebSocket server and disconnect clients."""

        if not self._server:
            return

        self._server.close()
        await self._server.wait_closed()
        self._server = None
        self._running = False

        # Best‑effort close of any lingering client connections
        for client in list(self._clients):
            try:
                await client.close()
            except Exception:  # pragma: no cover - defensive
                logger.debug("Error closing client websocket", exc_info=True)
        self._clients.clear()

    @property
    def running(self) -> bool:
        """Return ``True`` if the server is currently running."""

        return self._running

    # ------------------------------------------------------------------
    # Transcriber configuration
    # ------------------------------------------------------------------

    def set_transcriber(self, transcriber: Optional[TranscriberFn]) -> None:
        """Configure the transcriber callback.

        The callable may be synchronous or asynchronous.  It receives a single
        ``bytes`` argument containing raw audio data and should return either
        ``None`` (no result), a transcription ``str`` or a JSON‑serialisable
        ``dict``.
        """

        self._transcriber = transcriber

    # ------------------------------------------------------------------
    # Client handling
    # ------------------------------------------------------------------

    async def _handle_client(
        self, websocket: Any, path: str
    ) -> None:  # pragma: no cover -
        """Handle a client connection.

        The handler accepts two message types:

        * ``bytes`` – raw audio frames which are forwarded to the transcriber.
        * ``str``   – JSON control messages (``{"type": "ping"}``, etc.).
        """

        self._clients.add(websocket)
        logger.debug("Voice streaming client connected: path=%s", path)

        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    result = await self._process_audio(message)
                    if result is not None:
                        await websocket.send(json.dumps(result))
                else:
                    try:
                        payload = json.loads(message)
                    except json.JSONDecodeError:
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "error",
                                    "error": "invalid_json",
                                    "message": "Control messages must be valid JSON.",
                                }
                            )
                        )
                        continue
                    await self._handle_control(websocket, payload)
        except Exception:  # Broad catch – connection errors, etc.
            logger.debug("Voice streaming client error", exc_info=True)
        finally:
            self._clients.discard(websocket)
            logger.debug("Voice streaming client disconnected")

    async def _process_audio(self, data: bytes) -> Optional[dict[str, Any]]:
        """Process incoming audio and return a JSON‑serialisable result.

        If a transcriber is configured it is invoked and its result is
        normalised to a dict.  When no transcriber is set we simply echo basic
        metadata so that clients can verify the transport path.
        """

        if self._transcriber is None:
            return {
                "type": "audio",
                "bytes": len(data),
                "sample_rate": self.config.sample_rate,
                "chunk_size": self.config.chunk_size,
            }

        try:
            maybe_coro = self._transcriber(data)
            if asyncio.iscoroutine(maybe_coro):  # type: ignore[arg-type]
                result = await maybe_coro  # type: ignore[assignment]
            else:
                result = maybe_coro
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Transcriber error: %s", exc, exc_info=True)
            return {"type": "error", "error": "transcriber_failure"}

        if result is None:
            return None
        if isinstance(result, str):
            return {"type": "transcription", "text": result, "is_final": False}
        if isinstance(result, dict):
            # Ensure a type for downstream consumers
            result.setdefault("type", "transcription")
            return result

        # Fallback – unexpected return type
        return {
            "type": "error",
            "error": "invalid_transcriber_result",
            "detail_type": type(result).__name__,
        }

    async def _handle_control(self, websocket: Any, payload: dict[str, Any]) -> None:
        """Handle a JSON control message from a client."""

        msg_type = payload.get("type")

        if msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
            return

        if msg_type == "config_request":
            await websocket.send(
                json.dumps(
                    {
                        "type": "config",
                        "host": self.config.host,
                        "port": self.config.port,
                        "sample_rate": self.config.sample_rate,
                        "chunk_size": self.config.chunk_size,
                    }
                )
            )
            return

        # Unknown control message – echo back for debugging.
        await websocket.send(
            json.dumps(
                {
                    "type": "error",
                    "error": "unknown_control_message",
                    "payload": payload,
                }
            )
        )

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    async def broadcast_transcription(self, text: str, is_final: bool = False) -> None:
        """Broadcast a transcription message to all connected clients.

        This is useful when transcription is performed elsewhere (for example
        by a Redpanda consumer) and the results need to be pushed to any
        active WebSocket listeners.
        """

        if not self._clients:
            return

        message = json.dumps(
            {"type": "transcription", "text": text, "is_final": is_final}
        )

        # Iterate over a copy so we can safely remove closed clients
        for client in list(self._clients):
            try:
                await client.send(message)
            except Exception:  # pragma: no cover - network glitches
                self._clients.discard(client)
                logger.debug(
                    "Failed to broadcast to client; removed from set", exc_info=True
                )

    async def wait_closed(self) -> None:
        """Wait until the underlying server is closed.

        This is a small convenience wrapper for embedding the API in
        top‑level ``asyncio.run`` entry points.
        """

        if self._server is None:
            return
        await self._server.wait_closed()
