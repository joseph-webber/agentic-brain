# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Prompt management utilities for Agentic Brain."""

from __future__ import annotations

from .chain import PromptChain, PromptChainResult, PromptChainStep
from .few_shot import FewShotCollection, FewShotExample
from .library import PromptLibrary, get_default_prompt_library, get_rag_prompts
from .optimizer import PromptOptimizationResult, PromptOptimizer
from .template import PromptTemplate

__all__ = [
    "FewShotCollection",
    "FewShotExample",
    "PromptChain",
    "PromptChainResult",
    "PromptChainStep",
    "PromptLibrary",
    "PromptOptimizationResult",
    "PromptOptimizer",
    "PromptTemplate",
    "get_default_prompt_library",
    "get_rag_prompts",
]
