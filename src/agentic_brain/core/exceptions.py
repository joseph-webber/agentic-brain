# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Core exception types for Agentic Brain."""

from __future__ import annotations

from typing import Any


class AgenticBrainError(Exception):
    """Base error with structured troubleshooting context."""

    def __init__(
        self,
        message: str,
        *,
        cause: str | None = None,
        fix: str | None = None,
        context: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        self.message = message
        self.cause = cause
        self.fix = fix
        self.context = dict(context or {})
        self.retryable = retryable
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [f"❌ {self.message}"]
        if self.cause:
            parts.append(f"Cause: {self.cause}")
        if self.fix:
            parts.append(f"Fix: {self.fix}")
        if self.context:
            parts.append(f"Context: {self.context}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error for logging or APIs."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "cause": self.cause,
            "fix": self.fix,
            "context": dict(self.context),
            "retryable": self.retryable,
        }


class GraphConnectionError(AgenticBrainError):
    """Raised when a graph backend cannot be reached."""

    def __init__(
        self,
        backend: str,
        uri: str | None = None,
        *,
        operation: str = "connect",
        original_error: Exception | None = None,
    ) -> None:
        message = f"{backend} graph connection failed"
        cause = str(original_error) if original_error else "Connection unavailable"
        fix = "Check the graph service is running, reachable, and authenticated."
        context = {
            "backend": backend,
            "uri": uri,
            "operation": operation,
            "error_type": type(original_error).__name__ if original_error else None,
        }
        super().__init__(message, cause=cause, fix=fix, context=context, retryable=True)


class EmbeddingError(AgenticBrainError):
    """Raised when embeddings cannot be produced or validated."""

    def __init__(
        self,
        message: str = "Embedding operation failed",
        *,
        provider: str | None = None,
        model: str | None = None,
        operation: str | None = None,
        cause: str | None = None,
        original_error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        base_context = dict(context or {})
        if provider is not None:
            base_context["provider"] = provider
        if model is not None:
            base_context["model"] = model
        if operation is not None:
            base_context["operation"] = operation
        if original_error is not None:
            base_context["error_type"] = type(original_error).__name__
        super().__init__(
            message,
            cause=cause or (str(original_error) if original_error else None),
            fix="Check the embedding provider, model, and input text.",
            context=base_context,
            retryable=True,
        )


class LLMError(AgenticBrainError):
    """Raised when an LLM call or response fails."""

    def __init__(
        self,
        message: str = "LLM operation failed",
        *,
        provider: str | None = None,
        model: str | None = None,
        operation: str | None = None,
        status_code: int | None = None,
        cause: str | None = None,
        original_error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        base_context = dict(context or {})
        if provider is not None:
            base_context["provider"] = provider
        if model is not None:
            base_context["model"] = model
        if operation is not None:
            base_context["operation"] = operation
        if status_code is not None:
            base_context["status_code"] = status_code
        if original_error is not None:
            base_context["error_type"] = type(original_error).__name__
        super().__init__(
            message,
            cause=cause or (str(original_error) if original_error else None),
            fix="Check the model, API key, network, and provider status.",
            context=base_context,
            retryable=True,
        )


class RateLimitError(AgenticBrainError):
    """Raised when a provider throttles requests."""

    def __init__(
        self,
        limit: int = 0,
        window: str = "minute",
        retry_after: int | None = None,
        *,
        provider: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        retry_after = 60 if retry_after is None else retry_after
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        self.provider = provider
        self.original_error = original_error
        context = {
            "limit": limit,
            "window": window,
            "retry_after": retry_after,
            "provider": provider,
            "error_type": type(original_error).__name__ if original_error else None,
        }
        super().__init__(
            "Rate limit exceeded",
            cause=f"More than {limit} requests per {window}",
            fix=f"Wait {retry_after} seconds or use exponential backoff.",
            context=context,
            retryable=True,
        )


class ValidationError(AgenticBrainError):
    """Raised when input data does not meet validation requirements."""

    def __init__(
        self,
        field: str,
        expected: str,
        got: Any,
        reason: str | None = None,
    ) -> None:
        context = {"field": field, "expected": expected, "got": got}
        if reason:
            context["reason"] = reason
        super().__init__(
            f"Validation failed for '{field}'",
            cause=reason or f"Expected {expected}, got {got}",
            fix=f"Check {field} and provide a value matching {expected}.",
            context=context,
            retryable=False,
        )


__all__ = [
    "AgenticBrainError",
    "GraphConnectionError",
    "EmbeddingError",
    "LLMError",
    "RateLimitError",
    "ValidationError",
]
