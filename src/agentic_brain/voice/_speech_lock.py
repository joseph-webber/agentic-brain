# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
GLOBAL Speech Lock - Prevents ALL voice overlap.

CRITICAL ACCESSIBILITY MODULE for Joseph (blind user).

This module provides a process-wide lock that EVERY voice module must
acquire before producing audio output. Without this, multiple modules
(queue.py, resilient.py, conversation.py, voiceover.py, audio.py)
can call macOS `say` simultaneously, producing overlapping speech
that a blind user cannot understand.

Architecture:
    Every speech path ultimately calls _global_speak() which:
    1. Acquires the global threading lock
    2. Waits for any in-flight subprocess to finish
    3. Runs the new `say` command synchronously
    4. Pauses briefly (0.3s) for auditory clarity
    5. Releases the lock

    This guarantees ONE voice at a time across the entire process.

.. warning::

    Prefer ``VoiceSerializer.speak()`` or ``speak_serialized()`` from
    ``agentic_brain.voice.serializer`` instead of calling ``global_speak``
    directly.  The serializer adds queue management, async support, and
    overlap auditing on top of the raw lock.
"""

import logging
import subprocess
import threading
import time
import warnings
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Process-wide singleton lock ──────────────────────────────────────
_speech_lock = threading.Lock()
_current_process: Optional[subprocess.Popen] = None

# Gap between consecutive utterances (seconds).
INTER_UTTERANCE_GAP = 0.3


def global_speak(
    cmd: List[str],
    *,
    timeout: int = 60,
    inter_gap: float = INTER_UTTERANCE_GAP,
) -> bool:
    """Run a speech command under the global lock.

    .. deprecated::
        New code should route through ``speak_serialized()`` from
        ``agentic_brain.voice.serializer`` which wraps this lock with
        queue management and overlap auditing.

    Args:
        cmd: Full subprocess command, e.g. ``["say", "-v", "Karen", "Hello"]``.
        timeout: Maximum seconds to wait for the process.
        inter_gap: Seconds to pause after speech finishes for clarity.

    Returns:
        True if the command completed successfully.
    """
    warnings.warn(
        "global_speak() is a low-level primitive.  Prefer "
        "speak_serialized() from agentic_brain.voice.serializer "
        "to get queue management and overlap auditing.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _global_speak_inner(cmd, timeout=timeout, inter_gap=inter_gap)


def _global_speak_inner(
    cmd: List[str],
    *,
    timeout: int = 60,
    inter_gap: float = INTER_UTTERANCE_GAP,
) -> bool:
    """Internal implementation – no deprecation warning.

    Called by the serializer's own executor when it needs the raw lock.
    """
    global _current_process

    with _speech_lock:
        # If a previous process is somehow still alive, wait for it.
        if _current_process is not None and _current_process.poll() is None:
            try:
                _current_process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Previous speech process timed out, terminating")
                _current_process.terminate()
            except Exception:
                pass
            finally:
                _current_process = None

        try:
            _current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _current_process.wait(timeout=timeout)
            success = _current_process.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Speech command timed out: %s", " ".join(cmd[:4]))
            if _current_process:
                _current_process.terminate()
            success = False
        except FileNotFoundError:
            logger.error("Speech command not found: %s", cmd[0])
            success = False
        except Exception as e:
            logger.error("Speech command error: %s", e)
            success = False
        finally:
            _current_process = None

        # Brief pause between utterances for auditory clarity.
        if inter_gap > 0:
            time.sleep(inter_gap)

        return success


def get_global_lock() -> threading.Lock:
    """Return the process-wide speech lock.

    Other modules (e.g. ``VoiceSerializer``) **must** use this lock when
    spawning ``say`` sub-processes so that every speech path in the
    process is gated by the same mutex.
    """
    return _speech_lock


def is_speech_active() -> bool:
    """Check if a speech process is currently running."""
    return _current_process is not None and _current_process.poll() is None


def interrupt_speech() -> None:
    """Terminate any in-flight speech immediately."""
    global _current_process
    if _current_process is not None and _current_process.poll() is None:
        try:
            _current_process.terminate()
        except Exception:
            pass
        _current_process = None
