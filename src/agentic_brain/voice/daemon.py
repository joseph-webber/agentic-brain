"""Voice daemon compatibility module.

Centralizes imports for the background voice daemon so callers have a
stable module path while the implementation lives in ``resilient.py``.
"""

from agentic_brain.voice.resilient import VoiceDaemon, get_daemon, speak_via_daemon

__all__ = ["VoiceDaemon", "get_daemon", "speak_via_daemon"]
