# SPDX-License-Identifier: Apache-2.0
"""Lightweight LLM router exports.

The :mod:`agentic_brain.llm` package exposes the **minimal** routing core used
throughout the project.  Import :class:`LLMRouterCore` when you need a tiny,
dependency-light dispatcher for a handful of providers and do not want the full
provider registry that :mod:`agentic_brain.router` pulls in.
"""

from __future__ import annotations

from .router import LLMRouterCore as _LLMRouterCore, ModelRoute

LLMRouterCore = _LLMRouterCore
LLMRouterCore.__doc__ = (
    "Lightweight router core with normalised messages, alias resolution and\n"
    "provider-aware retries.  Use this when you only need fast, local routing\n"
    "behaviour without the full SmartRouter stack."
)

__all__ = ["LLMRouterCore", "ModelRoute"]
