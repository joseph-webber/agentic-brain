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
"""

import logging
import subprocess
import threading
import time
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

    This is the ONLY function that should ever start an audio subprocess.
    All voice modules must route through here.

    Args:
        cmd: Full subprocess command, e.g. ``["say", "-v", "Karen", "Hello"]``.
        timeout: Maximum seconds to wait for the process.
        inter_gap: Seconds to pause after speech finishes for clarity.

    Returns:
        True if the command completed successfully.
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
