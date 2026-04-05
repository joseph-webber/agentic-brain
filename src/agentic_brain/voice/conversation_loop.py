# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# VoiceConversationLoop - Core orchestrator for real-time voice.
#
# Architecture:
#   MIC → Silero VAD → faster-whisper (streaming) → LLM → LiveVoiceMode → TTS → Speaker
#
# Target: sub-500ms round-trip latency.

"""
Voice Conversation Loop - Real-time bidirectional voice conversation.

This module provides the core orchestration layer for Project Aria's
real-time voice capability.  It connects:

1. **Audio Input** - PyAudio microphone capture
2. **VAD** - Silero Voice Activity Detection
3. **STT** - faster-whisper streaming transcription
4. **LLM** - Ollama (local/fast) or Claude (quality)
5. **Sentence Buffer** - LiveVoiceMode for sentence-boundary TTS
6. **TTS** - CartesiaTTS (streaming) or macOS say (fallback)
7. **Audio Output** - Via VoiceSerializer (no overlap)

Usage::

    from agentic_brain.voice.conversation_loop import (
        VoiceConversationLoop,
        ConversationConfig,
    )

    config = ConversationConfig(
        llm_backend="ollama",  # or "claude"
        voice="Karen",
        use_cartesia=False,  # fallback to macOS say
    )
    loop = VoiceConversationLoop(config)

    async def main():
        await loop.start()
        # ... runs until stop() or KeyboardInterrupt
        await loop.stop()

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Optional imports (graceful degradation) ──────────────────────────

_HAS_PYAUDIO = False
try:
    import pyaudio  # type: ignore[import-untyped]

    _HAS_PYAUDIO = True
except ImportError:
    pyaudio = None  # type: ignore[assignment]


# ── Constants ────────────────────────────────────────────────────────

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_CHANNELS = 1
DEFAULT_CHUNK_SIZE = 1024  # ~64ms at 16kHz
SILENCE_THRESHOLD_MS = 1500  # 1.5s of silence = end of utterance
INTERRUPT_THRESHOLD_MS = 300  # 300ms of speech = interrupt
MAX_UTTERANCE_SECONDS = 30.0


class ConversationState(Enum):
    """State machine for the conversation loop."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass
class ConversationConfig:
    """Configuration for the voice conversation loop.

    Attributes:
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels (1 = mono).
        chunk_size: Audio chunk size in samples.
        silence_ms: Silence duration to end utterance.
        interrupt_ms: Speech duration to trigger interrupt.
        vad_threshold: Silero VAD speech probability threshold.
        whisper_model: faster-whisper model name.
        llm_backend: "ollama" (fast, local) or "claude" (quality).
        ollama_model: Model name for Ollama.
        voice: TTS voice name.
        rate: TTS speech rate.
        use_cartesia: Use Cartesia TTS (requires API key).
        device_index: PyAudio device index (None = default).
        response_callback: Optional callback to override LLM.
    """

    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    chunk_size: int = DEFAULT_CHUNK_SIZE
    silence_ms: int = SILENCE_THRESHOLD_MS
    interrupt_ms: int = INTERRUPT_THRESHOLD_MS
    vad_threshold: float = 0.5
    whisper_model: str = "base.en"
    llm_backend: str = "ollama"  # "ollama" or "claude"
    ollama_model: str = "llama3.2:3b"
    voice: str = "Karen"
    rate: int = 160
    use_cartesia: bool = False
    device_index: Optional[int] = None
    response_callback: Optional[Callable[[str], str]] = None


@dataclass
class ConversationMetrics:
    """Performance metrics for the conversation loop."""

    utterances: int = 0
    responses: int = 0
    interruptions: int = 0
    transcription_errors: int = 0
    llm_errors: int = 0
    tts_errors: int = 0
    avg_latency_ms: float = 0.0
    _latencies: List[float] = field(default_factory=list)

    def record_latency(self, latency_ms: float) -> None:
        self._latencies.append(latency_ms)
        self.avg_latency_ms = sum(self._latencies) / len(self._latencies)

    def to_dict(self) -> dict:
        return {
            "utterances": self.utterances,
            "responses": self.responses,
            "interruptions": self.interruptions,
            "transcription_errors": self.transcription_errors,
            "llm_errors": self.llm_errors,
            "tts_errors": self.tts_errors,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }


class VoiceConversationLoop:
    """Core orchestrator for real-time voice conversation.

    This class ties together all voice components into a single
    asyncio-based conversation loop with interruption support.
    """

    def __init__(self, config: Optional[ConversationConfig] = None) -> None:
        self.config = config or ConversationConfig()
        self._state = ConversationState.IDLE
        self._state_lock = threading.Lock()
        self._metrics = ConversationMetrics()
        self._stop_event = asyncio.Event()
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._pa: Any = None
        self._stream: Any = None
        self._audio_thread: Optional[threading.Thread] = None

        # Lazy-loaded components
        self._vad: Any = None
        self._transcriber: Any = None
        self._live_mode: Any = None
        self._cartesia: Any = None
        self._llm_client: Any = None

        # Callbacks
        self._on_state_change: Optional[Callable[[ConversationState], None]] = None
        self._on_transcript: Optional[Callable[[str], None]] = None
        self._on_response: Optional[Callable[[str], None]] = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def state(self) -> ConversationState:
        with self._state_lock:
            return self._state

    @property
    def metrics(self) -> ConversationMetrics:
        return self._metrics

    @property
    def is_running(self) -> bool:
        return self.state not in (ConversationState.IDLE, ConversationState.ERROR)

    # ── Event hooks ──────────────────────────────────────────────────

    def on_state_change(self, callback: Callable[[ConversationState], None]) -> None:
        """Register a callback fired on every state transition."""
        self._on_state_change = callback

    def on_transcript(self, callback: Callable[[str], None]) -> None:
        """Register a callback fired when transcript is ready."""
        self._on_transcript = callback

    def on_response(self, callback: Callable[[str], None]) -> None:
        """Register a callback fired when LLM response starts."""
        self._on_response = callback

    # ── State machine ────────────────────────────────────────────────

    def _set_state(self, new_state: ConversationState) -> None:
        with self._state_lock:
            old = self._state
            self._state = new_state
        if old != new_state:
            logger.info("ConversationLoop: %s -> %s", old.value, new_state.value)
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception:
                    logger.debug("State change callback error", exc_info=True)

    # ── Initialization ───────────────────────────────────────────────

    def _init_vad(self) -> None:
        """Initialize Silero VAD."""
        try:
            from agentic_brain.voice.vad import SileroVAD, VADConfig

            vad_config = VADConfig(
                threshold=self.config.vad_threshold,
                sample_rate=self.config.sample_rate,
            )
            self._vad = SileroVAD(config=vad_config)
            if self._vad.ensure_model():
                logger.info("ConversationLoop: Silero VAD initialized")
            else:
                logger.warning("ConversationLoop: Silero VAD model failed to load")
                self._vad = None
        except Exception as exc:
            logger.warning("ConversationLoop: VAD init failed: %s", exc)
            self._vad = None

    def _init_transcriber(self) -> None:
        """Initialize faster-whisper transcriber."""
        try:
            from agentic_brain.voice.transcription import get_streaming_transcriber

            self._transcriber = get_streaming_transcriber(
                model_name=self.config.whisper_model,
                window_secs=2.0,
                overlap_secs=0.5,
                prefer_faster_whisper=True,
            )
            logger.info(
                "ConversationLoop: Transcriber initialized (model=%s)",
                self.config.whisper_model,
            )
        except Exception as exc:
            logger.warning("ConversationLoop: Transcriber init failed: %s", exc)
            self._transcriber = None

    def _init_live_mode(self) -> None:
        """Initialize LiveVoiceMode for sentence buffering."""
        try:
            from agentic_brain.voice.live_mode import LiveVoiceMode

            self._live_mode = LiveVoiceMode(
                voice=self.config.voice,
                rate=self.config.rate,
            )
            logger.info("ConversationLoop: LiveVoiceMode initialized")
        except Exception as exc:
            logger.warning("ConversationLoop: LiveVoiceMode init failed: %s", exc)
            self._live_mode = None

    def _init_cartesia(self) -> None:
        """Initialize Cartesia TTS if configured."""
        if not self.config.use_cartesia:
            return
        try:
            from agentic_brain.voice.cartesia_tts import CartesiaTTS

            self._cartesia = CartesiaTTS()
            logger.info("ConversationLoop: Cartesia TTS initialized")
        except Exception as exc:
            logger.warning("ConversationLoop: Cartesia TTS init failed: %s", exc)
            self._cartesia = None

    async def _init_llm(self) -> None:
        """Initialize LLM client based on config."""
        if self.config.llm_backend == "ollama":
            try:
                from agentic_brain.voice.llm_voice import LocalLLMVoice

                self._llm_client = LocalLLMVoice(model=self.config.ollama_model)
                logger.info(
                    "ConversationLoop: Ollama LLM initialized (model=%s)",
                    self.config.ollama_model,
                )
            except Exception as exc:
                logger.warning("ConversationLoop: Ollama init failed: %s", exc)
        # Claude backend would go here if needed

    def _init_audio(self) -> bool:
        """Initialize PyAudio stream."""
        if not _HAS_PYAUDIO:
            logger.error("ConversationLoop: PyAudio not available")
            return False

        try:
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                input_device_index=self.config.device_index,
                frames_per_buffer=self.config.chunk_size,
            )
            logger.info("ConversationLoop: Audio stream opened")
            return True
        except Exception as exc:
            logger.error("ConversationLoop: Audio init failed: %s", exc)
            return False

    def _close_audio(self) -> None:
        """Close PyAudio resources."""
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    # ── Audio capture thread ─────────────────────────────────────────

    def _audio_capture_loop(self) -> None:
        """Background thread that captures audio and queues it."""
        while not self._stop_event.is_set():
            if self._stream is None:
                time.sleep(0.01)
                continue
            try:
                chunk = self._stream.read(
                    self.config.chunk_size,
                    exception_on_overflow=False,
                )
                # Put into async queue from sync thread
                try:
                    self._audio_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass  # Drop oldest if queue is full
            except Exception:
                time.sleep(0.01)

    # ── Core async loop ──────────────────────────────────────────────

    async def start(self) -> None:
        """Start the conversation loop.

        This method initializes all components and begins listening.
        It runs until stop() is called or an error occurs.
        """
        if self.is_running:
            logger.warning("ConversationLoop: Already running")
            return

        # Initialize components
        self._init_vad()
        self._init_transcriber()
        self._init_live_mode()
        self._init_cartesia()
        await self._init_llm()

        if not self._init_audio():
            self._set_state(ConversationState.ERROR)
            return

        # Start audio capture thread
        self._stop_event.clear()
        self._audio_queue = asyncio.Queue(maxsize=100)
        self._audio_thread = threading.Thread(
            target=self._audio_capture_loop,
            name="conversation-audio",
            daemon=True,
        )
        self._audio_thread.start()

        self._set_state(ConversationState.LISTENING)
        logger.info("ConversationLoop: Started")

        try:
            await self._main_loop()
        except asyncio.CancelledError:
            logger.info("ConversationLoop: Cancelled")
        except Exception as exc:
            logger.exception("ConversationLoop: Error in main loop: %s", exc)
            self._set_state(ConversationState.ERROR)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the conversation loop."""
        self._stop_event.set()

        # Wait for audio thread
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=1.0)

        self._close_audio()

        # Stop live mode if active
        if self._live_mode and self._live_mode.is_active:
            self._live_mode.stop()

        self._set_state(ConversationState.IDLE)
        logger.info("ConversationLoop: Stopped (metrics=%s)", self._metrics.to_dict())

    async def _main_loop(self) -> None:
        """Main async loop: VAD → transcribe → LLM → speak."""
        audio_buffer: List[bytes] = []
        silence_start: Optional[float] = None
        speech_active = False

        while not self._stop_event.is_set():
            # Get audio chunk (non-blocking with timeout)
            try:
                chunk = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=0.1,
                )
            except TimeoutError:
                continue

            # Check for speech using VAD
            is_speech = self._detect_speech(chunk)

            if is_speech:
                silence_start = None
                speech_active = True
                audio_buffer.append(chunk)

                # Check for interrupt while speaking
                if self.state == ConversationState.SPEAKING:
                    await self._handle_interrupt()
            else:
                if speech_active:
                    if silence_start is None:
                        silence_start = time.monotonic()
                    elif (
                        time.monotonic() - silence_start
                    ) * 1000 >= self.config.silence_ms:
                        # End of utterance detected
                        if audio_buffer:
                            await self._process_utterance(audio_buffer)
                        audio_buffer = []
                        silence_start = None
                        speech_active = False

    def _detect_speech(self, chunk: bytes) -> bool:
        """Detect speech in audio chunk using VAD."""
        if self._vad is None:
            # Fallback: simple energy-based detection
            samples = np.frombuffer(chunk, dtype=np.int16)
            energy = np.abs(samples).mean()
            return energy > 500

        try:
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            segments = list(self._vad.detect_speech(samples))
            return len(segments) > 0
        except Exception:
            return False

    async def _handle_interrupt(self) -> None:
        """Handle user interruption during TTS."""
        logger.info("ConversationLoop: Interrupt detected")
        self._metrics.interruptions += 1

        # Stop current TTS
        if self._live_mode and self._live_mode.is_active:
            self._live_mode.interrupt()

        # Kill any macOS say process
        try:
            from agentic_brain.voice.serializer import get_voice_serializer

            serializer = get_voice_serializer()
            serializer.reset()
        except Exception:
            pass

        self._set_state(ConversationState.INTERRUPTED)
        await asyncio.sleep(0.1)
        self._set_state(ConversationState.LISTENING)

    async def _process_utterance(self, audio_chunks: List[bytes]) -> None:
        """Process a complete utterance: transcribe → LLM → speak."""
        self._set_state(ConversationState.PROCESSING)
        self._metrics.utterances += 1
        t0 = time.monotonic()

        # Transcribe
        transcript = await self._transcribe(audio_chunks)
        if not transcript:
            self._metrics.transcription_errors += 1
            self._set_state(ConversationState.LISTENING)
            return

        logger.info("ConversationLoop: Transcript: %s", transcript)
        if self._on_transcript:
            try:
                self._on_transcript(transcript)
            except Exception:
                pass

        # Get LLM response
        response = await self._get_llm_response(transcript)
        if not response:
            self._metrics.llm_errors += 1
            self._set_state(ConversationState.LISTENING)
            return

        logger.info("ConversationLoop: Response: %s", response[:100])
        if self._on_response:
            try:
                self._on_response(response)
            except Exception:
                pass

        # Speak response
        self._set_state(ConversationState.SPEAKING)
        await self._speak_response(response)

        # Record latency
        latency_ms = (time.monotonic() - t0) * 1000
        self._metrics.record_latency(latency_ms)
        self._metrics.responses += 1
        logger.info("ConversationLoop: Round-trip latency: %.0fms", latency_ms)

        self._set_state(ConversationState.LISTENING)

    async def _transcribe(self, audio_chunks: List[bytes]) -> Optional[str]:
        """Transcribe audio chunks to text."""
        if not self._transcriber:
            return None

        audio_data = b"".join(audio_chunks)

        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._transcriber.transcribe_bytes(
                    audio_data,
                    sample_rate=self.config.sample_rate,
                ),
            )
            if result and result.text.strip():
                return result.text.strip()
        except Exception as exc:
            logger.warning("ConversationLoop: Transcription error: %s", exc)

        return None

    async def _get_llm_response(self, transcript: str) -> Optional[str]:
        """Get response from LLM (Ollama or callback)."""
        # Check for custom callback first
        if self.config.response_callback:
            try:
                return self.config.response_callback(transcript)
            except Exception as exc:
                logger.warning("ConversationLoop: Callback error: %s", exc)
                return None

        # Use LLM
        if self._llm_client is None:
            return f"I heard: {transcript}"

        try:
            response = await self._llm_client.generate_voice_response(
                prompt=transcript,
                personality="karen",
                max_tokens=100,
            )
            return response
        except Exception as exc:
            logger.warning("ConversationLoop: LLM error: %s", exc)
            return None

    async def _speak_response(self, text: str) -> None:
        """Speak response using LiveVoiceMode and TTS."""
        try:
            if self._live_mode:
                self._live_mode.start(
                    voice=self.config.voice,
                    rate=self.config.rate,
                )

                # Feed text to live mode (sentence buffering)
                self._live_mode.feed(text)
                self._live_mode.flush()
                self._live_mode.stop()
            else:
                # Fallback to direct serializer
                await self._speak_direct(text)
        except Exception as exc:
            logger.warning("ConversationLoop: TTS error: %s", exc)
            self._metrics.tts_errors += 1

    async def _speak_direct(self, text: str) -> None:
        """Direct speech via serializer (fallback)."""
        try:
            from agentic_brain.voice.serializer import get_voice_serializer

            serializer = get_voice_serializer()
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: serializer.speak(
                    text,
                    voice=self.config.voice,
                    rate=self.config.rate,
                    wait=True,
                ),
            )
        except Exception as exc:
            logger.warning("ConversationLoop: Direct speech failed: %s", exc)
            # Ultimate fallback: macOS say
            await self._speak_macos_fallback(text)

    async def _speak_macos_fallback(self, text: str) -> None:
        """Ultimate fallback: macOS say command."""
        import subprocess

        try:
            proc = await asyncio.create_subprocess_exec(
                "say",
                "-v",
                self.config.voice,
                "-r",
                str(self.config.rate),
                text,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception as exc:
            logger.error("ConversationLoop: macOS say failed: %s", exc)


# ── Module-level convenience ─────────────────────────────────────────

_conversation_loop: Optional[VoiceConversationLoop] = None
_loop_lock = threading.Lock()


def get_conversation_loop(
    config: Optional[ConversationConfig] = None,
) -> VoiceConversationLoop:
    """Get or create the singleton conversation loop."""
    global _conversation_loop
    with _loop_lock:
        if _conversation_loop is None:
            _conversation_loop = VoiceConversationLoop(config)
        return _conversation_loop


async def start_conversation(
    config: Optional[ConversationConfig] = None,
    on_transcript: Optional[Callable[[str], None]] = None,
    on_response: Optional[Callable[[str], None]] = None,
) -> VoiceConversationLoop:
    """Start a conversation loop with optional callbacks.

    This is the simplest way to start real-time voice conversation.

    Args:
        config: Optional configuration.
        on_transcript: Called when user speech is transcribed.
        on_response: Called when LLM response is generated.

    Returns:
        The running VoiceConversationLoop instance.

    Example::

        async def main():
            loop = await start_conversation(
                on_transcript=lambda t: print(f"User: {t}"),
                on_response=lambda r: print(f"Brain: {r}"),
            )
            # Runs until Ctrl+C
            try:
                while loop.is_running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                await loop.stop()

        asyncio.run(main())
    """
    loop = get_conversation_loop(config)

    if on_transcript:
        loop.on_transcript(on_transcript)
    if on_response:
        loop.on_response(on_response)

    # Start in background task
    asyncio.create_task(loop.start())

    # Wait for it to actually start
    for _ in range(50):  # 5 seconds max
        if loop.is_running:
            break
        await asyncio.sleep(0.1)

    return loop


# ── CLI entry point ──────────────────────────────────────────────────


async def _cli_main() -> None:
    """Simple CLI for testing the conversation loop."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 60)
    print("VoiceConversationLoop - Real-time Voice Conversation")
    print("=" * 60)
    print("Speak into your microphone. Press Ctrl+C to stop.")
    print()

    config = ConversationConfig(
        llm_backend="ollama",
        ollama_model="llama3.2:3b",
        voice="Karen",
        rate=160,
    )

    loop = VoiceConversationLoop(config)
    loop.on_transcript(lambda t: print(f"\n👤 You: {t}"))
    loop.on_response(lambda r: print(f"🧠 Brain: {r}\n"))

    try:
        await loop.start()
    except KeyboardInterrupt:
        print("\nStopping...")
        await loop.stop()

    print(f"\nMetrics: {loop.metrics.to_dict()}")


if __name__ == "__main__":
    asyncio.run(_cli_main())
