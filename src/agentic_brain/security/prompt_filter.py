# SPDX-License-Identifier: Apache-2.0
"""Prompt filtering for role-based LLM access."""

from __future__ import annotations

import re
from dataclasses import dataclass


class PromptFilterError(PermissionError):
    """Raised when a prompt violates the current role policy."""


@dataclass(frozen=True, slots=True)
class PromptRule:
    """Pattern + error pair for blocked prompt content."""

    pattern: re.Pattern[str]
    message: str


class PromptFilter:
    """Filter dangerous prompts for non-admin LLM usage."""

    SYSTEM_PROMPT_RULES = (
        PromptRule(
            re.compile(
                r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b"
                r"(previous|prior|system|developer|hidden|safety|instructions?|rules?)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            "System prompt injection is not allowed for this role.",
        ),
        PromptRule(
            re.compile(
                r"\b(reveal|show|print|dump|expose)\b.{0,30}\b"
                r"(system|developer|hidden)\b.{0,20}\b(prompt|instructions?)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            "Revealing hidden prompts or instructions is not allowed.",
        ),
        PromptRule(
            re.compile(
                r"(<\s*system\s*>|role\s*:\s*system|\byou are now\b.{0,20}\b(system|developer|root|admin)\b)",
                re.IGNORECASE | re.DOTALL,
            ),
            "System-role impersonation is not allowed.",
        ),
        PromptRule(
            re.compile(
                r"(\bact as\b.{0,20}\b(admin|developer|system|root)\b|\bwithout\s+filters?\b)",
                re.IGNORECASE | re.DOTALL,
            ),
            "Privilege escalation prompts are not allowed.",
        ),
    )

    EXECUTION_RULES = (
        PromptRule(
            re.compile(
                r"\b(run|execute|launch)\b.{0,30}\b(code|script|command|shell|bash|python|terminal)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            "Direct code execution requests are not allowed for this role.",
        ),
        PromptRule(
            re.compile(
                r"\b(eval|exec)\s*\(|\bos\.system\s*\(|\bsubprocess\.(run|call|popen)\b",
                re.IGNORECASE,
            ),
            "Prompts that request dangerous execution primitives are not allowed.",
        ),
        PromptRule(
            re.compile(
                r"\b(rm\s+-rf|chmod\s+777|curl\b.+\|\s*(sh|bash)|wget\b.+\|\s*(sh|bash))",
                re.IGNORECASE | re.DOTALL,
            ),
            "Dangerous shell execution requests are blocked.",
        ),
    )

    FILE_MODIFICATION_RULES = (
        PromptRule(
            re.compile(
                r"\b(modify|edit|rewrite|delete|create|overwrite|append|save|apply patch|change)\b"
                r".{0,40}\b(file|files|repository|repo|codebase|source|project)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            "File modification instructions are not allowed for this role.",
        ),
    )

    GUEST_CODE_RULES = (
        PromptRule(
            re.compile(
                r"\b(code|coding|program|programming|function|class|script|debug|refactor|compile|stack trace|terminal|shell|regex)\b",
                re.IGNORECASE,
            ),
            "Code features are not available in guest mode.",
        ),
    )

    def __init__(self, level: str = "none") -> None:
        self.level = level

    def filter(self, prompt: str) -> str:
        """Validate and normalize a prompt for the current restriction level."""
        cleaned = prompt.replace("\x00", "").strip()
        if not cleaned or self.level == "none":
            return cleaned

        self._raise_on_match(cleaned, self.SYSTEM_PROMPT_RULES)
        self._raise_on_match(cleaned, self.EXECUTION_RULES)

        if self.level in {"standard", "strict"}:
            self._raise_on_match(cleaned, self.FILE_MODIFICATION_RULES)

        if self.level == "strict":
            self._raise_on_match(cleaned, self.GUEST_CODE_RULES)

        return cleaned

    @staticmethod
    def _raise_on_match(prompt: str, rules: tuple[PromptRule, ...]) -> None:
        for rule in rules:
            if rule.pattern.search(prompt):
                raise PromptFilterError(rule.message)
