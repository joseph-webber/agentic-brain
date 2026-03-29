# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Phase 3 voice integration facade.

This module wires together the Phase 3 voice improvements behind a single,
lazy-loaded API. Every optional subsystem degrades gracefully when its module
or dependencies are absent, so the existing voice stack keeps working.
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from agentic_brain.voice.resilient import VoiceDaemon, get_daemon

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ComponentSpec:
    """Declarative loader for an optional Phase 3 component."""

    module: str
    attr: str | None = None
    instantiate: bool = False
    factory: bool = False
    optional: bool = True


_COMPONENT_SPECS: dict[str, _ComponentSpec] = {
    "neural_router": _ComponentSpec(
        "agentic_brain.voice.neural_router",
        "NeuralVoiceRouter",
        instantiate=True,
        optional=False,
    ),
    "kokoro": _ComponentSpec(
        "agentic_brain.voice.kokoro_tts",
        "KokoroVoice",
        instantiate=True,
    ),
    "speed_manager": _ComponentSpec(
        "agentic_brain.voice.speed_profiles",
        "get_speed_manager",
        factory=True,
        optional=False,
    ),
    "adaptive_tracker": _ComponentSpec(
        "agentic_brain.voice.speed_profiles",
        "get_adaptive_tracker",
        factory=True,
    ),
    "earcon_player": _ComponentSpec(
        "agentic_brain.audio",
        "get_earcon_player",
        factory=True,
    ),
    "lady_voices": _ComponentSpec("agentic_brain.voice.lady_voices"),
    "content_classifier": _ComponentSpec(
        "agentic_brain.voice.content_classifier",
        "get_content_classifier",
        factory=True,
    ),
    "voice_cloning": _ComponentSpec(
        "agentic_brain.voice.voice_cloning",
        "VoiceCloner",
        instantiate=True,
    ),
    "voice_library": _ComponentSpec(
        "agentic_brain.voice.voice_library",
        "VoiceLibrary",
        instantiate=True,
    ),
    "quality_analyzer": _ComponentSpec(
        "agentic_brain.audio.quality_analyzer",
        "VoiceQualityAnalyzer",
        instantiate=True,
    ),
    "quality_gate": _ComponentSpec(
        "agentic_brain.voice.quality_gate",
        "get_quality_gate",
        factory=True,
    ),
    "emotions": _ComponentSpec(
        "agentic_brain.voice.emotions",
        "EmotionDetector",
        instantiate=True,
    ),
    "expression": _ComponentSpec(
        "agentic_brain.voice.expression",
        "ExpressionEngine",
        instantiate=True,
    ),
    "conversation_memory": _ComponentSpec(
        "agentic_brain.voice.conversation_memory",
        "get_conversation_memory",
        factory=True,
    ),
    "repeat_detector": _ComponentSpec(
        "agentic_brain.voice.repeat_detector",
        "get_repeat_detector",
        factory=True,
    ),
}


class Phase3VoiceSystem:
    """Unified facade for Phase 3 voice improvements.

    The facade intentionally does not import heavy or optional modules until a
    method needs them. Missing Phase 3 modules are treated as degraded-but-safe,
    allowing the existing serializer and live voice stack to continue working.
    """

    def __init__(self) -> None:
        self._created_at = time.time()
        self._lock = threading.RLock()
        self._components: dict[str, Any] = {}
        self._load_errors: dict[str, str] = {}
        self._speak_count = 0
        self._earcon_count = 0
        self._remembered_turns = 0

    # ── Public API ────────────────────────────────────────────────────

    def speak(
        self,
        text: str,
        *,
        lady: str = "Karen",
        category: str | None = None,
        rate: int | None = None,
        wait: bool = True,
        remember: bool = True,
        use_neural: bool = True,
    ) -> bool:
        """Speak with the best available Phase 3 pipeline."""
        if not text or not text.strip():
            return False

        resolved_category = category or self.classify_content(text)
        resolved_rate = rate if rate is not None else self.get_current_rate()
        prepared = self.apply_expression(text, lady=lady, category=resolved_category)

        if self.detect_repeat(prepared, speaker=lady):
            logger.debug("Skipping repeated utterance for %s", lady)
            return False

        router = self._get_component("neural_router") if use_neural else None
        result = False

        if router is not None:
            try:
                result = bool(
                    router.speak(
                        prepared,
                        lady=lady,
                        rate=resolved_rate,
                        category=resolved_category,
                        wait=wait,
                    )
                )
            except Exception:
                logger.debug(
                    "Neural router failed, falling back to serializer", exc_info=True
                )

        if not result:
            result = self._speak_via_serializer(
                prepared,
                voice=lady,
                rate=resolved_rate,
                wait=wait,
            )

        if result:
            with self._lock:
                self._speak_count += 1
            repeat_detector = self._get_component("repeat_detector")
            if repeat_detector is not None and hasattr(repeat_detector, "record"):
                try:
                    repeat_detector.record(prepared)
                except Exception:
                    logger.debug("Repeat detector record failed", exc_info=True)
            if remember:
                self.remember_turn(
                    text=prepared,
                    speaker=lady,
                    category=resolved_category,
                )

        return result

    def speak_system(
        self,
        text: str,
        *,
        rate: int | None = None,
        wait: bool = True,
    ) -> bool:
        """Speak a system/navigation utterance."""
        return self.speak(
            text,
            lady="Karen",
            category="system",
            rate=rate,
            wait=wait,
        )

    def play_earcon(self, name: str, *, blocking: bool = False) -> bool:
        """Play a named earcon if the subsystem is available."""
        player = self._get_component("earcon_player")
        if player is None:
            return False
        try:
            ok = bool(player.play(name, blocking=blocking))
        except Exception:
            logger.debug("Earcon playback failed", exc_info=True)
            return False
        if ok:
            with self._lock:
                self._earcon_count += 1
        return ok

    def get_current_rate(self) -> int:
        """Return the active speech rate, defaulting safely when unavailable."""
        manager = self._get_component("speed_manager")
        return (
            int(getattr(manager, "current_rate", 155)) if manager is not None else 155
        )

    def get_speed_profile(self) -> str:
        """Return the current speed profile name."""
        manager = self._get_component("speed_manager")
        profile = getattr(manager, "current_profile", None)
        return getattr(profile, "value", "relaxed")

    def set_speed_profile(self, profile: str) -> str:
        """Set the active speech speed profile."""
        manager = self._get_component("speed_manager")
        if manager is None:
            raise RuntimeError("speed profile subsystem unavailable")

        speed_module = self._import_module("agentic_brain.voice.speed_profiles")
        if speed_module is None:
            raise RuntimeError("speed profile module unavailable")

        SpeedProfile = getattr(speed_module, "SpeedProfile")
        enum_value = SpeedProfile(profile.lower())
        manager.set_profile(enum_value)
        return enum_value.value

    def classify_content(self, text: str) -> str:
        """Classify content type, falling back to simple heuristics."""
        classifier = self._get_component("content_classifier")
        if classifier is not None:
            result = self._call_first_available(
                classifier,
                (
                    ("classify", (text,), {}),
                    ("classify_text", (text,), {}),
                ),
            )
            if result is not None and hasattr(result, "content_type"):
                content_type = getattr(result, "content_type", None)
                value = getattr(content_type, "value", None)
                if isinstance(value, str) and value.strip():
                    return value
            if isinstance(result, str) and result.strip():
                return result

            if result is None and hasattr(classifier, "__class__"):
                cls = classifier.__class__
                result = self._call_static_first_available(
                    cls,
                    (
                        ("classify", (text,), {}),
                        ("classify_text", (text,), {}),
                    ),
                )
                if isinstance(result, str) and result.strip():
                    return result

        lowered = text.strip().lower()
        if any(token in lowered for token in ("error", "failed", "failure")):
            return "error"
        if len(lowered.split()) <= 3:
            return "notification"
        return "conversation"

    def resolve_emotion(self, text: str, *, default: str = "neutral") -> str:
        """Return the best available emotion tag for a line."""
        emotions = self._get_component("emotions")
        if emotions is not None:
            result = self._call_first_available(
                emotions,
                (
                    ("detect", (text,), {}),
                    ("classify", (text,), {}),
                    ("emotion_for_text", (text,), {}),
                ),
            )
            if result is not None and hasattr(result, "value"):
                value = getattr(result, "value", None)
                if isinstance(value, str) and value.strip():
                    return value
            if isinstance(result, str) and result.strip():
                return result

        lowered = text.lower()
        if "!" in text:
            return "excited"
        if any(token in lowered for token in ("sorry", "sad", "unfortunately")):
            return "empathetic"
        return default

    def apply_expression(
        self,
        text: str,
        *,
        lady: str = "Karen",
        category: str = "conversation",
    ) -> str:
        """Optionally add expression/emotion markup before speaking."""
        expression = self._get_component("expression")
        emotion = self.resolve_emotion(text)
        if expression is not None:
            result = self._call_first_available(
                expression,
                (
                    (
                        "apply",
                        (text,),
                        {"lady": lady, "emotion": emotion, "category": category},
                    ),
                    (
                        "express",
                        (text,),
                        {"lady": lady, "emotion": emotion, "category": category},
                    ),
                    (
                        "render",
                        (text,),
                        {"lady": lady, "emotion": emotion, "category": category},
                    ),
                ),
            )
            if isinstance(result, str) and result.strip():
                return result
        return text

    def remember_turn(
        self,
        *,
        text: str,
        speaker: str,
        category: str = "conversation",
    ) -> bool:
        """Record a conversation turn when memory support is available."""
        memory = self._get_component("conversation_memory")
        if memory is None:
            return False

        stored = self._call_first_available(
            memory,
            (
                (
                    "record",
                    (speaker, text),
                    {"voice": speaker, "rate": self.get_current_rate()},
                ),
                (
                    "remember",
                    (),
                    {"text": text, "speaker": speaker, "category": category},
                ),
                (
                    "add_turn",
                    (),
                    {"text": text, "speaker": speaker, "category": category},
                ),
                ("store", (), {"text": text, "speaker": speaker, "category": category}),
                (
                    "append",
                    (),
                    {"text": text, "speaker": speaker, "category": category},
                ),
            ),
        )
        ok = bool(stored) if stored is not None else False
        if ok:
            with self._lock:
                self._remembered_turns += 1
        return ok

    def get_recent_turns(self, limit: int = 10) -> list[Any]:
        """Return recent remembered turns, or an empty list when unavailable."""
        memory = self._get_component("conversation_memory")
        if memory is None:
            return []
        turns = self._call_first_available(
            memory,
            (
                ("get_recent", (), {"count": limit}),
                ("recent", (), {"limit": limit}),
                ("get_recent", (), {"limit": limit}),
                ("list_recent", (), {"limit": limit}),
            ),
        )
        if turns is None:
            return []
        return list(turns)

    def detect_repeat(self, text: str, *, speaker: str = "assistant") -> bool:
        """Detect repeated output if the optional repeat detector is present."""
        detector = self._get_component("repeat_detector")
        if detector is None:
            return False
        result = self._call_first_available(
            detector,
            (
                ("is_repeat", (text,), {}),
                ("seen_recently", (text,), {"speaker": speaker}),
                ("check", (text,), {}),
            ),
        )
        if result is not None and hasattr(result, "is_repeat"):
            return bool(result.is_repeat)
        return bool(result) if result is not None else False

    def analyze_quality(self, audio_source: str | None = None) -> dict[str, Any]:
        """Run optional quality analysis and gate checks."""
        analyzer = self._get_component("quality_analyzer")
        gate = self._get_component("quality_gate")
        result: dict[str, Any] = {
            "available": analyzer is not None or gate is not None,
            "analysis": None,
            "gate": None,
        }

        if analyzer is not None:
            result["analysis"] = self._call_first_available(
                analyzer,
                (
                    ("analyze_audio", (audio_source,), {}),
                    ("analyze", (), {"audio_source": audio_source}),
                    ("analyze", (audio_source,), {}),
                    ("summary", (), {"audio_source": audio_source}),
                ),
            )

        if gate is not None:
            result["gate"] = self._call_first_available(
                gate,
                (
                    ("check", (audio_source,), {}),
                    ("evaluate", (), {"audio_source": audio_source}),
                    ("check", (), {"audio_source": audio_source}),
                    ("evaluate", (audio_source,), {}),
                ),
            )

        return result

    def clone_voice(self, source: str, *, name: str | None = None) -> dict[str, Any]:
        """Invoke optional voice cloning and library registration hooks."""
        cloning = self._get_component("voice_cloning")
        library = self._get_component("voice_library")
        result: dict[str, Any] = {
            "available": cloning is not None,
            "clone": None,
            "library": None,
        }

        if cloning is None:
            return result

        clone = self._call_first_available(
            cloning,
            (
                ("clone_voice", (source,), {"name": name}),
                ("clone", (), {"source": source, "name": name}),
                ("create_clone", (), {"source": source, "name": name}),
                ("clone_voice", (), {"source": source, "name": name}),
            ),
        )
        result["clone"] = clone

        if library is not None and clone is not None:
            result["library"] = self._call_first_available(
                library,
                (
                    ("register", (clone,), {"name": name}),
                    ("add", (clone,), {"name": name}),
                    ("store", (clone,), {"name": name}),
                ),
            )

        return result

    def list_ladies(self) -> list[str]:
        """Return the lady roster from the best available source."""
        lady_voices = self._get_component("lady_voices")
        if lady_voices is not None:
            for attr in ("LADY_ORDER", "LADY_VOICES", "LADIES", "VOICE_MAP"):
                value = getattr(lady_voices, attr, None)
                if isinstance(value, dict):
                    return sorted(str(name) for name in value.keys())
                if isinstance(value, (list, tuple, set)):
                    return sorted(str(name) for name in value)

            result = self._call_static_first_available(
                lady_voices,
                (
                    ("list_ladies", (), {}),
                    ("get_ladies", (), {}),
                ),
            )
            if result is not None:
                return sorted(str(name) for name in result)

        kokoro = self._get_component("kokoro")
        if kokoro is not None and hasattr(kokoro, "list_ladies"):
            return sorted(str(name) for name in kokoro.list_ladies())

        kokoro_module = self._import_module("agentic_brain.voice.kokoro_tts")
        voice_map = getattr(kokoro_module, "LADY_VOICES", {}) if kokoro_module else {}
        if isinstance(voice_map, dict):
            return sorted(str(name) for name in voice_map.keys())
        return ["Karen"]

    async def start_live_daemon(self) -> VoiceDaemon:
        """Start or get the global voice daemon.

        Uses the centralized daemon from resilient.py to prevent
        multiple daemons from speaking simultaneously.
        """
        daemon = await get_daemon()
        return daemon

    async def stop_live_daemon(self) -> dict[str, Any]:
        """Stop the global voice daemon if running."""
        try:
            import agentic_brain.voice.resilient as resilient_voice

            daemon = getattr(resilient_voice, "_daemon_instance", None)
            if daemon is None:
                return {"ok": True, "message": "not running"}

            await daemon.stop()
            resilient_voice._daemon_instance = None
            return {"ok": True, "stopped": True}
        except Exception as exc:
            logger.debug("Stopping global voice daemon failed", exc_info=True)
            return {"ok": False, "error": str(exc)}

    def live_daemon_status(self) -> dict[str, Any]:
        """Return global voice daemon status."""
        return self._live_daemon_status()

    def health(self) -> dict[str, Any]:
        """Run a health check across Phase 3 subsystems."""
        subsystems = {
            "speech_path": self._speech_path_status(),
            "kokoro": self._kokoro_status(),
            "lady_voices": self._optional_module_status("lady_voices"),
            "live_daemon": self._live_daemon_status(),
            "earcons": self._earcon_status(),
            "speed_profiles": self._speed_status(),
            "content_classifier": self._optional_module_status("content_classifier"),
            "voice_cloning": self._optional_module_status("voice_cloning"),
            "voice_library": self._optional_module_status("voice_library"),
            "quality_analyzer": self._optional_module_status("quality_analyzer"),
            "quality_gate": self._optional_module_status("quality_gate"),
            "emotions": self._optional_module_status("emotions"),
            "expression": self._optional_module_status("expression"),
            "conversation_memory": self._optional_module_status("conversation_memory"),
            "repeat_detector": self._optional_module_status("repeat_detector"),
        }

        healthy = (
            subsystems["speech_path"]["available"]
            and subsystems["speed_profiles"]["available"]
        )
        all_available = all(status["available"] for status in subsystems.values())

        return {
            "healthy": healthy,
            "all_subsystems_available": all_available,
            "uptime_s": round(time.time() - self._created_at, 1),
            "speak_count": self._speak_count,
            "earcon_count": self._earcon_count,
            "remembered_turns": self._remembered_turns,
            "subsystems": subsystems,
            "load_errors": dict(self._load_errors),
        }

    def status(self) -> dict[str, Any]:
        """Return a concise human-friendly status snapshot."""
        health = self.health()
        lines = [
            f"Phase 3 Voice: {'HEALTHY' if health['healthy'] else 'DEGRADED'}",
            f"Uptime: {health['uptime_s']}s | Speaks: {health['speak_count']} | Earcons: {health['earcon_count']}",
        ]
        for name, info in health["subsystems"].items():
            state = "OK" if info.get("available") else "MISSING"
            detail = info.get("detail", "")
            if detail:
                lines.append(f"  {name}: [{state}] {detail}")
            else:
                lines.append(f"  {name}: [{state}]")
        return {"summary": "\n".join(lines), "health": health}

    # ── Internal helpers ───────────────────────────────────────────────

    def _get_component(self, name: str) -> Any:
        with self._lock:
            if name in self._components:
                return self._components[name]

            spec = _COMPONENT_SPECS[name]
            try:
                module = importlib.import_module(spec.module)
                value: Any = module
                if spec.attr:
                    value = getattr(module, spec.attr)
                if spec.factory or spec.instantiate:
                    value = value()
                self._components[name] = value
                self._load_errors.pop(name, None)
                return value
            except Exception as exc:
                logger.debug("Phase3 component %s unavailable", name, exc_info=True)
                self._components[name] = None
                self._load_errors[name] = str(exc)
                return None

    def _import_module(self, module_name: str) -> Any:
        try:
            return importlib.import_module(module_name)
        except Exception:
            logger.debug("Could not import module %s", module_name, exc_info=True)
            return None

    def _speak_via_serializer(
        self,
        text: str,
        *,
        voice: str,
        rate: int,
        wait: bool,
    ) -> bool:
        try:
            from agentic_brain.voice.serializer import get_voice_serializer

            serializer = get_voice_serializer()
            return bool(serializer.speak(text, voice=voice, rate=rate, wait=wait))
        except Exception:
            logger.debug("Serializer speak failed", exc_info=True)
            return False

    def _speech_path_status(self) -> dict[str, Any]:
        router = self._get_component("neural_router")
        if router is not None:
            info = {
                "available": True,
                "detail": "neural router ready",
            }
            stats = getattr(router, "stats", None)
            if isinstance(stats, dict):
                info["stats"] = dict(stats)
            return info

        return {
            "available": True,
            "detail": "serializer fallback available",
            "degraded": True,
        }

    def _kokoro_status(self) -> dict[str, Any]:
        kokoro = self._get_component("kokoro")
        if kokoro is None:
            return {
                "available": False,
                "detail": self._load_errors.get("kokoro", "not installed"),
            }

        backend = getattr(kokoro, "backend", None)
        is_initialized = bool(getattr(kokoro, "is_initialized", False))
        available_fn = getattr(
            self._import_module("agentic_brain.voice.kokoro_tts"),
            "kokoro_available",
            None,
        )
        installed = bool(available_fn()) if callable(available_fn) else False
        return {
            "available": True,
            "detail": f"backend={backend or 'lazy'} | initialized={is_initialized} | installed={installed}",
            "backend": backend,
            "initialized": is_initialized,
            "installed": installed,
        }

    def _earcon_status(self) -> dict[str, Any]:
        player = self._get_component("earcon_player")
        if player is None:
            return {
                "available": False,
                "detail": self._load_errors.get("earcon_player", "earcons unavailable"),
            }

        earcon_dir = getattr(player, "earcon_dir", None)
        return {
            "available": True,
            "detail": f"dir={earcon_dir}",
        }

    def _speed_status(self) -> dict[str, Any]:
        manager = self._get_component("speed_manager")
        tracker = self._get_component("adaptive_tracker")
        if manager is None:
            return {
                "available": False,
                "detail": self._load_errors.get(
                    "speed_manager", "speed profiles unavailable"
                ),
            }

        profile = getattr(getattr(manager, "current_profile", None), "value", "relaxed")
        rate = getattr(manager, "current_rate", 155)
        stats = getattr(tracker, "stats", None) if tracker is not None else None
        return {
            "available": True,
            "detail": f"profile={profile} | rate={rate}",
            "profile": profile,
            "rate": rate,
            "adaptive": stats,
        }

    def _live_daemon_status(self) -> dict[str, Any]:
        try:
            import agentic_brain.voice.resilient as resilient_voice
        except Exception as exc:
            return {
                "available": False,
                "detail": f"resilient voice unavailable: {exc}",
            }

        daemon = getattr(resilient_voice, "_daemon_instance", None)
        if daemon is None:
            return {
                "available": True,
                "daemon_running": False,
                "detail": "running=False",
            }

        try:
            stats = dict(daemon.get_stats())
        except Exception:
            logger.debug("Voice daemon status failed", exc_info=True)
            return {"available": False, "detail": "voice daemon status failed"}

        stats["available"] = True
        stats["daemon_running"] = bool(stats.get("running", False))
        stats["detail"] = f"running={stats['daemon_running']}"
        return stats

    def _optional_module_status(self, component_name: str) -> dict[str, Any]:
        value = self._get_component(component_name)
        if value is None:
            return {
                "available": False,
                "detail": self._load_errors.get(component_name, "module unavailable"),
            }
        return {
            "available": True,
            "detail": f"loaded from {_COMPONENT_SPECS[component_name].module}",
        }

    @staticmethod
    def _call_first_available(
        target: Any,
        attempts: tuple[tuple[str, tuple[Any, ...], dict[str, Any]], ...],
    ) -> Any:
        for name, args, kwargs in attempts:
            func = getattr(target, name, None)
            if callable(func):
                return func(*args, **kwargs)
        return None

    @staticmethod
    def _call_static_first_available(
        target: Any,
        attempts: tuple[tuple[str, tuple[Any, ...], dict[str, Any]], ...],
    ) -> Any:
        for name, args, kwargs in attempts:
            func = getattr(target, name, None)
            if callable(func):
                return func(*args, **kwargs)
        return None


_phase3_system: Phase3VoiceSystem | None = None
_phase3_lock = threading.Lock()


def get_phase3_voice_system() -> Phase3VoiceSystem:
    """Return the process-wide Phase 3 voice facade."""
    global _phase3_system
    if _phase3_system is None:
        with _phase3_lock:
            if _phase3_system is None:
                _phase3_system = Phase3VoiceSystem()
    return _phase3_system


def _set_phase3_voice_system_for_testing(system: Phase3VoiceSystem | None) -> None:
    """Replace the singleton for tests."""
    global _phase3_system
    _phase3_system = system
