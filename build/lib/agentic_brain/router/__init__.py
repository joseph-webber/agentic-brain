# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""
High-level LLM router exports.

The router package exposes a three-tier hierarchy:

1. :class:`agentic_brain.llm.LLMRouterCore` – lightweight, dependency-light core
2. :class:`LLMRouter` – the default production router most users need
3. :class:`SmartRouter` – an autonomous supervisor with security postures

Import :class:`LLMRouter` for everyday use, upgrade to :class:`SmartRouter`
when you need compliance postures or multi-brain orchestration, and fall back
to :mod:`agentic_brain.llm` only when you explicitly want the minimalist core.
"""

import importlib
import warnings
from types import MappingProxyType

from .config import Message, Model, Provider, Response, RouterConfig
from .provider_checker import (
    ProviderChecker,
    ProviderStatus,
    format_error_message,
    format_provider_status_report,
    get_setup_help,
)

_LAZY_EXPORTS = MappingProxyType(
    {
        "LLMRouter": "agentic_brain.router.routing",
        "chat": "agentic_brain.router.routing",
        "chat_async": "agentic_brain.router.routing",
        "get_router": "agentic_brain.router.routing",
        "SmartRouter": "agentic_brain.router.smart_router",
        "SmashMode": "agentic_brain.router.smart_router",
        "SmashResult": "agentic_brain.router.smart_router",
        "SecurityPosture": "agentic_brain.router.smart_router",
        "PostureMode": "agentic_brain.router.smart_router",
    }
)

__all__ = [
    # Primary routers
    "LLMRouter",
    "SmartRouter",
    # Convenience helpers
    "chat",
    "chat_async",
    "get_router",
    # Configuration + models
    "RouterConfig",
    "Provider",
    "Response",
    "Message",
    "Model",
    # Smart router posture enums
    "SmashMode",
    "SmashResult",
    "SecurityPosture",
    "PostureMode",
    # Diagnostics
    "ProviderChecker",
    "ProviderStatus",
    "format_error_message",
    "format_provider_status_report",
    "get_setup_help",
]

_DEPRECATED_EXPORTS = MappingProxyType(
    {
        # Old lightweight import path
        "LLMRouterCore": "agentic_brain.llm",
        # Provider-specific helpers (prefer direct module imports)
        "chat_openai": "agentic_brain.router.openai",
        "stream_openai": "agentic_brain.router.openai",
        "chat_azure_openai": "agentic_brain.router.azure_openai",
        "stream_azure_openai": "agentic_brain.router.azure_openai",
        "chat_anthropic": "agentic_brain.router.anthropic",
        "stream_anthropic": "agentic_brain.router.anthropic",
        "chat_google": "agentic_brain.router.google",
        "stream_google": "agentic_brain.router.google",
        "chat_groq": "agentic_brain.router.groq",
        "stream_groq": "agentic_brain.router.groq",
        "chat_openrouter": "agentic_brain.router.openrouter",
        "stream_openrouter": "agentic_brain.router.openrouter",
        "chat_together": "agentic_brain.router.together",
        "stream_together": "agentic_brain.router.together",
        "chat_xai": "agentic_brain.router.xai",
        "stream_xai": "agentic_brain.router.xai",
        "chat_ollama": "agentic_brain.router.ollama",
        "stream_ollama": "agentic_brain.router.ollama",
        "check_ollama_available": "agentic_brain.router.ollama",
        "check_ollama_sync": "agentic_brain.router.ollama",
        "list_models_async": "agentic_brain.router.ollama",
        "list_models_sync": "agentic_brain.router.ollama",
    }
)

# Keep deprecated names discoverable via `from agentic_brain.router import *`
__all__ += list(_DEPRECATED_EXPORTS.keys())

_DEPRECATION_TEMPLATE = (
    "`agentic_brain.router.{name}` is deprecated. Import it from `{target}` instead."
)


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name])
        attr = getattr(module, name)
        if name == "LLMRouter":
            attr.__doc__ = (
                "Main production router that balances local and cloud providers, "
                "handles telemetry, caching, and fallbacks, and should be imported "
                "via ``from agentic_brain.router import LLMRouter`` for most workloads."
            )
        elif name == "SmartRouter":
            attr.__doc__ = (
                "Advanced routing supervisor that layers posture modes, compliance "
                "rules, and proactive heuristics on top of :class:`LLMRouter`. Use "
                "this when you need adaptive routing decisions beyond the default router."
            )
        globals()[name] = attr
        return attr
    if name in _DEPRECATED_EXPORTS:
        module_path = _DEPRECATED_EXPORTS[name]
        warnings.warn(
            _DEPRECATION_TEMPLATE.format(name=name, target=f"{module_path}.{name}"),
            DeprecationWarning,
            stacklevel=2,
        )
        module = importlib.import_module(module_path)
        attr = getattr(module, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
