# SPDX-License-Identifier: Apache-2.0
"""Role-based access control for LLM features."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, ClassVar

from agentic_brain.auth.context import (
    current_user,
    get_current_login,
    get_current_user_id,
    is_authenticated,
)

from .prompt_filter import PromptFilter
from .roles import SecurityRole


@dataclass(frozen=True, slots=True)
class LLMRolePermissions:
    """Permissions granted to a specific LLM security role."""

    allowed_providers: frozenset[str]
    can_execute_code: bool
    can_modify_files: bool
    can_use_consensus: bool
    can_use_yolo: bool
    prompt_filter_level: str
    requests_per_minute: int | None = None


ROLE_PERMISSIONS: dict[SecurityRole, LLMRolePermissions] = {
    SecurityRole.FULL_ADMIN: LLMRolePermissions(
        allowed_providers=frozenset(
            {
                "anthropic",
                "azure_openai",
                "google",
                "groq",
                "ollama",
                "openai",
                "openrouter",
                "together",
                "xai",
            }
        ),
        can_execute_code=True,
        can_modify_files=True,
        can_use_consensus=True,
        can_use_yolo=True,
        prompt_filter_level="none",
        requests_per_minute=None,
    ),
    SecurityRole.SAFE_ADMIN: LLMRolePermissions(
        allowed_providers=frozenset(
            {
                "anthropic",
                "azure_openai",
                "google",
                "groq",
                "ollama",
                "openai",
                "openrouter",
                "together",
                "xai",
            }
        ),
        can_execute_code=True,
        can_modify_files=True,
        can_use_consensus=True,
        can_use_yolo=True,
        prompt_filter_level="none",
        requests_per_minute=1000,
    ),
    SecurityRole.USER: LLMRolePermissions(
        allowed_providers=frozenset(
            {
                "anthropic",
                "azure_openai",
                "google",
                "groq",
                "ollama",
                "openai",
                "openrouter",
                "together",
                "xai",
            }
        ),
        can_execute_code=False,
        can_modify_files=False,
        can_use_consensus=False,
        can_use_yolo=False,
        prompt_filter_level="standard",
        requests_per_minute=60,
    ),
    SecurityRole.GUEST: LLMRolePermissions(
        allowed_providers=frozenset({"groq", "ollama", "openrouter"}),
        can_execute_code=False,
        can_modify_files=False,
        can_use_consensus=False,
        can_use_yolo=False,
        prompt_filter_level="strict",
        requests_per_minute=10,
    ),
}


PROVIDER_ALIASES: dict[str, str] = {
    "anthropic": "anthropic",
    "azure_openai": "azure_openai",
    "azure-openai": "azure_openai",
    "claude": "anthropic",
    "gemini": "google",
    "google": "google",
    "gpt": "openai",
    "grok": "xai",
    "groq": "groq",
    "local": "ollama",
    "ollama": "ollama",
    "openai": "openai",
    "openrouter": "openrouter",
    "together": "together",
    "xai": "xai",
}


class LLMSecurityGuard:
    """Controls LLM access based on security role."""

    _rate_limit_state: ClassVar[
        dict[tuple[SecurityRole, str], deque[float]]
    ] = defaultdict(deque)
    _window_seconds: ClassVar[float] = 60.0

    def __init__(self, role: SecurityRole | str | None = None):
        self.role = self._resolve_role(role)
        self.permissions = ROLE_PERMISSIONS[self.role]
        self._prompt_filter = PromptFilter(self.permissions.prompt_filter_level)
        self._last_retry_after_seconds = 0

    @classmethod
    def _resolve_role(cls, role: SecurityRole | str | None) -> SecurityRole:
        if isinstance(role, SecurityRole):
            return role
        if isinstance(role, str) and role.strip():
            normalized = role.strip().lower()
            for candidate in SecurityRole:
                if candidate.value == normalized:
                    return candidate
            raise ValueError(f"Unsupported LLM security role: {role}")
        return cls.infer_role_from_context()

    @classmethod
    def infer_role_from_context(cls) -> SecurityRole:
        """Infer the current role from auth context or environment."""
        user = current_user()
        if user is None:
            fallback = os.getenv("AGENTIC_BRAIN_DEFAULT_LLM_ROLE")
            return cls._resolve_role(fallback) if fallback else SecurityRole.GUEST

        if user.has_role("ADMIN") or user.has_any_authority("ADMIN", "SYSTEM_ADMIN"):
            return SecurityRole.FULL_ADMIN
        if user.has_role("ANONYMOUS") or not is_authenticated():
            return SecurityRole.GUEST
        return SecurityRole.USER

    @classmethod
    def clear_rate_limits(cls) -> None:
        """Reset shared rate-limit state. Useful for tests."""
        cls._rate_limit_state.clear()

    @staticmethod
    def normalize_provider(provider: str) -> str:
        """Normalize provider aliases to canonical provider names."""
        normalized = provider.strip().lower().replace("-", "_")
        return PROVIDER_ALIASES.get(normalized, normalized)

    def can_use_provider(self, provider: str) -> bool:
        """Check if role can use this LLM provider."""
        return self.normalize_provider(provider) in self.permissions.allowed_providers

    def filter_prompt(self, prompt: str) -> str:
        """Filter prompt based on role restrictions."""
        return self._prompt_filter.filter(prompt)

    def filter_messages(
        self, messages: list[dict[str, Any]] | tuple[dict[str, Any], ...]
    ) -> list[dict[str, str]]:
        """Filter user-controlled message content for the active role."""
        filtered: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            if role in {"system", "user"}:
                content = self.filter_prompt(content)
            else:
                content = content.replace("\x00", "").strip()
            filtered.append({"role": role, "content": content})
        return filtered

    def can_execute_code(self) -> bool:
        """Check if role allows code execution."""
        return self.permissions.can_execute_code

    def can_modify_files(self) -> bool:
        """Check if role allows instructing the LLM to modify files."""
        return self.permissions.can_modify_files

    def can_use_consensus(self) -> bool:
        """Check if role allows consensus or multi-LLM features."""
        return self.permissions.can_use_consensus

    def can_use_yolo(self) -> bool:
        """Check if role allows YOLO-mode actions."""
        return self.permissions.can_use_yolo

    def default_user_id(self) -> str:
        """Resolve a stable user identifier for rate limiting."""
        return get_current_user_id() or get_current_login() or "anonymous"

    @property
    def last_retry_after_seconds(self) -> int:
        """Return retry-after seconds from the last rate-limit check."""
        return self._last_retry_after_seconds

    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits."""
        limit = self.permissions.requests_per_minute
        if limit is None:
            self._last_retry_after_seconds = 0
            return True

        key = (self.role, user_id or "anonymous")
        now = time.monotonic()
        history = self._rate_limit_state[key]

        while history and (now - history[0]) >= self._window_seconds:
            history.popleft()

        if len(history) >= limit:
            self._last_retry_after_seconds = max(
                1, int(self._window_seconds - (now - history[0]))
            )
            return False

        history.append(now)
        self._last_retry_after_seconds = 0
        return True
