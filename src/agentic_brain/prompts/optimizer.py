# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Prompt optimization helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .template import PromptTemplate


@dataclass(frozen=True)
class PromptOptimizationResult:
    """Result of an optimization run."""

    original: str
    optimized: str
    changes: tuple[str, ...] = ()

    @property
    def original_length(self) -> int:
        return len(self.original)

    @property
    def optimized_length(self) -> int:
        return len(self.optimized)

    @property
    def savings(self) -> int:
        return self.original_length - self.optimized_length


@dataclass
class PromptOptimizer:
    """Normalize prompts for size and readability."""

    max_length: int | None = None
    dedupe_consecutive_lines: bool = True
    collapse_blank_lines: bool = True
    strip_trailing_whitespace: bool = True

    def optimize(self, prompt: str) -> PromptOptimizationResult:
        """Optimize prompt text."""
        original = prompt
        text = prompt
        changes: list[str] = []

        if self.strip_trailing_whitespace:
            stripped = "\n".join(line.rstrip() for line in text.splitlines())
            if stripped != text:
                changes.append("stripped trailing whitespace")
            text = stripped

        if self.dedupe_consecutive_lines:
            deduped_lines: list[str] = []
            previous: str | None = None
            for line in text.splitlines():
                if line == previous:
                    continue
                deduped_lines.append(line)
                previous = line
            deduped = "\n".join(deduped_lines)
            if deduped != text:
                changes.append("removed consecutive duplicate lines")
            text = deduped

        if self.collapse_blank_lines:
            collapsed_lines: list[str] = []
            blank_seen = False
            for line in text.splitlines():
                if not line.strip():
                    if blank_seen:
                        continue
                    blank_seen = True
                    collapsed_lines.append("")
                else:
                    blank_seen = False
                    collapsed_lines.append(line)
            collapsed = "\n".join(collapsed_lines)
            if collapsed != text:
                changes.append("collapsed blank lines")
            text = collapsed

        text = text.strip()

        if self.max_length is not None and len(text) > self.max_length:
            trimmed = self._truncate(text, self.max_length)
            if trimmed != text:
                changes.append(f"truncated to {self.max_length} characters")
            text = trimmed

        return PromptOptimizationResult(
            original=original,
            optimized=text,
            changes=tuple(changes),
        )

    def optimize_template(self, template: PromptTemplate) -> PromptTemplate:
        """Optimize a PromptTemplate and return a new template."""
        result = self.optimize(template.template)
        return replace(template, template=result.optimized)

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        if max_length <= 3:
            return text[:max_length]
        head = max(1, (max_length - 3) // 2)
        tail = max_length - head - 3
        return f"{text[:head]}...{text[-tail:]}"
