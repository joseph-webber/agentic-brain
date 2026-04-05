# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Prompt chaining utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .template import PromptTemplate


@dataclass(frozen=True)
class PromptChainStep:
    """One step in a prompt chain."""

    name: str
    template: PromptTemplate
    output_key: str | None = None
    transform: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None

    def render(self, context: Mapping[str, Any]) -> str:
        """Render the step using the given context."""
        return self.template.render(**dict(context))


@dataclass(frozen=True)
class PromptChainResult:
    """Result of executing a prompt chain."""

    final_output: str
    step_outputs: dict[str, str] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptChain:
    """Sequentially render templates while passing outputs forward."""

    steps: list[PromptChainStep] = field(default_factory=list)
    name: str = "prompt-chain"

    def add_step(self, step: PromptChainStep) -> PromptChain:
        """Append a step and return self."""
        self.steps.append(step)
        return self

    def extend(self, steps: list[PromptChainStep]) -> PromptChain:
        """Append multiple steps and return self."""
        self.steps.extend(steps)
        return self

    def run(self, context: Mapping[str, Any]) -> PromptChainResult:
        """Run the prompt chain."""
        working_context = dict(context)
        outputs: dict[str, str] = {}
        final_output = ""

        for step in self.steps:
            rendered = step.render(working_context)
            outputs[step.name] = rendered
            final_output = rendered
            key = step.output_key or step.name
            working_context[key] = rendered
            if step.transform is not None:
                working_context.update(step.transform(rendered, dict(working_context)))

        return PromptChainResult(
            final_output=final_output,
            step_outputs=outputs,
            context=working_context,
        )

    def render(self, context: Mapping[str, Any]) -> str:
        """Return the final chain output."""
        return self.run(context).final_output

    def __len__(self) -> int:
        return len(self.steps)
