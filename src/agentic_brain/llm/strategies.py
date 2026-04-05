# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""Retry and back-off strategies for the lightweight LLM router."""

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, Sequence

import aiohttp

from agentic_brain.exceptions import APIError, LLMProviderError, RateLimitError

if TYPE_CHECKING:
    from agentic_brain.llm.router import ModelRoute
    from agentic_brain.router.config import Response


class RetryStrategyMixin:
    """Mixin that adds retry / back-off behaviour to LLMRouterCore.

    The methods here assume ``self`` provides:
    - ``self.config``  (RouterConfig) with ``max_retries``,
      ``backoff_base_seconds``, ``backoff_max_seconds``
    - ``self.RETRYABLE_STATUS_CODES``
    - ``self._dispatch_request(route, *, messages, temperature, max_tokens)``
    """

    async def _sleep(self, seconds: float) -> None:
        """Thin wrapper kept overridable for tests."""
        await asyncio.sleep(seconds)

    def _retry_after_seconds(
        self,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | str | None = None,
    ) -> int | None:
        retry_after = None
        if headers:
            for key, value in headers.items():
                if key.lower() == "retry-after":
                    retry_after = value
                    break

        if retry_after:
            if retry_after.isdigit():
                return int(retry_after)
            try:
                retry_dt = parsedate_to_datetime(retry_after)
                if retry_dt.tzinfo is None:
                    retry_dt = retry_dt.replace(tzinfo=UTC)
                return max(0, int((retry_dt - datetime.now(UTC)).total_seconds()))
            except Exception:
                return None

        if isinstance(body, dict):
            for key in ("retry_after", "retryAfter"):
                value = body.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
            error_body = body.get("error")
            if isinstance(error_body, dict):
                value = error_body.get("retry_after") or error_body.get("retryAfter")
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return None

    def _backoff_seconds(self, attempt: int, retry_after: int | None = None) -> float:
        """Calculate retry delay for the current attempt."""
        if retry_after is not None:
            return float(retry_after)
        return min(
            self.config.backoff_base_seconds * (2 ** (attempt - 1)),  # type: ignore[attr-defined]
            self.config.backoff_max_seconds,  # type: ignore[attr-defined]
        )

    async def _call_with_backoff(
        self,
        route: ModelRoute,
        *,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int | None = None,
    ) -> Response:
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):  # type: ignore[attr-defined]
            try:
                return await self._dispatch_request(  # type: ignore[attr-defined]
                    route,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except RateLimitError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:  # type: ignore[attr-defined]
                    raise
                retry_after = (
                    exc.debug_info.get("retry_after")
                    if hasattr(exc, "debug_info")
                    else None
                )
                await self._sleep(self._backoff_seconds(attempt, retry_after))
            except APIError as exc:
                last_error = exc
                status = (
                    exc.debug_info.get("status_code")
                    if hasattr(exc, "debug_info")
                    else None
                )
                if (
                    status not in self.RETRYABLE_STATUS_CODES  # type: ignore[attr-defined]
                    or attempt >= self.config.max_retries  # type: ignore[attr-defined]
                ):
                    raise
                await self._sleep(self._backoff_seconds(attempt))
            except aiohttp.ClientError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:  # type: ignore[attr-defined]
                    raise LLMProviderError(route.provider.value, route.model, exc)
                await self._sleep(self._backoff_seconds(attempt))

        raise LLMProviderError(route.provider.value, route.model, last_error)
