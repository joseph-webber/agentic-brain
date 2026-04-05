# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Async Activity Completion for Agentic Brain

Async completion allows activities to be completed by external systems
via a callback mechanism. The activity returns immediately with a token,
and the external system uses that token to complete the activity later.

Features:
- Activity tokens for external completion
- Token validation and expiration
- Completion via callback
- Failure reporting
- Token persistence for durability

Use Cases:
- Human-in-the-loop approvals
- External system callbacks (webhooks)
- Long-running external processes
- Manual review steps

Usage:
    @activity(completion_type="async")
    async def wait_for_approval(request_id: str) -> str:
        token = get_activity_token()

        # Send approval request to external system
        send_approval_email(request_id, token)

        # Activity returns immediately, completes when external system calls back
        # The caller will wait for async_complete() to be called

    # External system calls back via HTTP
    POST /api/complete-activity
    {
        "token": "act_...",
        "result": "approved"
    }

    # Or programmatically
    await async_complete(token, result="approved")
"""

import asyncio
import hashlib
import hmac
import inspect
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncCompletionStatus(Enum):
    """Status of async completion"""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ActivityToken:
    """
    Token for async activity completion

    Contains all information needed to complete an activity externally.
    """

    token_id: str
    workflow_id: str
    activity_id: str
    activity_type: str

    # Security
    secret: str  # Used for HMAC validation

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    # State
    status: AsyncCompletionStatus = AsyncCompletionStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.expires_at is None:
            # Default 24 hour expiration
            self.expires_at = self.created_at + timedelta(hours=24)

    @property
    def token_string(self) -> str:
        """Generate the token string to give to external systems"""
        # Format: act_{token_id}_{signature}
        signature = self._generate_signature()
        return f"act_{self.token_id}_{signature[:16]}"

    def _generate_signature(self) -> str:
        """Generate HMAC signature for token validation"""
        message = f"{self.token_id}:{self.workflow_id}:{self.activity_id}"
        return hmac.new(
            self.secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    def validate_signature(self, provided_signature: str) -> bool:
        """Validate a provided signature"""
        expected = self._generate_signature()[:16]
        return hmac.compare_digest(expected, provided_signature)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired"""
        if not self.expires_at:
            return False
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid for completion"""
        return self.status == AsyncCompletionStatus.PENDING and not self.is_expired

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_id": self.token_id,
            "workflow_id": self.workflow_id,
            "activity_id": self.activity_id,
            "activity_type": self.activity_type,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], secret: str) -> "ActivityToken":
        return cls(
            token_id=data["token_id"],
            workflow_id=data["workflow_id"],
            activity_id=data["activity_id"],
            activity_type=data["activity_type"],
            secret=secret,
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(UTC)
            ),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            status=AsyncCompletionStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
        )


class AsyncCompletionError(Exception):
    """Base error for async completion"""

    pass


class TokenNotFoundError(AsyncCompletionError):
    """Token not found in registry"""

    def __init__(self, token_string: str):
        super().__init__(f"Token not found: {token_string}")
        self.token_string = token_string


class TokenExpiredError(AsyncCompletionError):
    """Token has expired"""

    def __init__(self, token_id: str):
        super().__init__(f"Token expired: {token_id}")
        self.token_id = token_id


class TokenInvalidError(AsyncCompletionError):
    """Token validation failed"""

    def __init__(self, reason: str):
        super().__init__(f"Invalid token: {reason}")
        self.reason = reason


class TokenAlreadyCompletedError(AsyncCompletionError):
    """Token has already been completed"""

    def __init__(self, token_id: str, status: AsyncCompletionStatus):
        super().__init__(f"Token {token_id} already {status.value}")
        self.token_id = token_id
        self.status = status


class AsyncCompletionManager:
    """
    Manager for async activity completion

    Handles token creation, storage, validation, and completion.
    """

    def __init__(self, secret_key: Optional[str] = None):
        # Secret key for token signing
        self._secret_key = secret_key or secrets.token_hex(32)

        # Token storage: token_id -> ActivityToken
        self._tokens: Dict[str, ActivityToken] = {}

        # Completion waiters: token_id -> Future
        self._waiters: Dict[str, asyncio.Future] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Callbacks for completion events
        self._on_complete_callbacks: List[Callable] = []

    def create_token(
        self,
        workflow_id: str,
        activity_id: str,
        activity_type: str,
        ttl_hours: float = 24.0,
    ) -> ActivityToken:
        """
        Create a new activity token for async completion

        Args:
            workflow_id: Parent workflow ID
            activity_id: Activity instance ID
            activity_type: Type of activity
            ttl_hours: Token time-to-live in hours

        Returns:
            ActivityToken that can be given to external system
        """
        token = ActivityToken(
            token_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            activity_id=activity_id,
            activity_type=activity_type,
            secret=self._secret_key,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        )

        self._tokens[token.token_id] = token
        logger.info(
            f"Created async completion token for activity {activity_id} "
            f"(expires in {ttl_hours}h)"
        )

        return token

    def parse_token_string(self, token_string: str) -> tuple[str, str]:
        """
        Parse a token string into token_id and signature

        Args:
            token_string: Token in format "act_{id}_{signature}"

        Returns:
            Tuple of (token_id, signature)
        """
        if not token_string.startswith("act_"):
            raise TokenInvalidError("Token must start with 'act_'")

        parts = token_string[4:].split("_", 1)
        if len(parts) != 2:
            raise TokenInvalidError("Invalid token format")

        return parts[0], parts[1]

    def get_token(self, token_string: str) -> ActivityToken:
        """
        Get and validate a token from its string representation

        Args:
            token_string: Token string from external system

        Returns:
            The validated ActivityToken

        Raises:
            TokenNotFoundError: Token not in registry
            TokenExpiredError: Token has expired
            TokenInvalidError: Signature validation failed
        """
        token_id, signature = self.parse_token_string(token_string)

        token = self._tokens.get(token_id)
        if not token:
            raise TokenNotFoundError(token_string)

        if token.is_expired:
            token.status = AsyncCompletionStatus.EXPIRED
            raise TokenExpiredError(token_id)

        if not token.validate_signature(signature):
            raise TokenInvalidError("Signature mismatch")

        return token

    async def complete(
        self,
        token_string: str,
        result: Any = None,
    ) -> ActivityToken:
        """
        Complete an activity with a result

        Args:
            token_string: Token string from external system
            result: Result to return to the activity caller

        Returns:
            The completed ActivityToken
        """
        async with self._lock:
            token = self.get_token(token_string)

            if token.status != AsyncCompletionStatus.PENDING:
                raise TokenAlreadyCompletedError(token.token_id, token.status)

            token.status = AsyncCompletionStatus.COMPLETED
            token.result = result
            token.completed_at = datetime.now(UTC)

            # Notify waiter if any
            if token.token_id in self._waiters:
                future = self._waiters.pop(token.token_id)
                if not future.done():
                    future.set_result(result)

            # Run callbacks
            for callback in self._on_complete_callbacks:
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(token, result)
                    else:
                        callback(token, result)
                except Exception as e:
                    logger.error(f"Completion callback error: {e}")

            logger.info(f"Activity {token.activity_id} completed via async token")
            return token

    async def fail(
        self,
        token_string: str,
        error: str,
    ) -> ActivityToken:
        """
        Fail an activity with an error

        Args:
            token_string: Token string from external system
            error: Error message

        Returns:
            The failed ActivityToken
        """
        async with self._lock:
            token = self.get_token(token_string)

            if token.status != AsyncCompletionStatus.PENDING:
                raise TokenAlreadyCompletedError(token.token_id, token.status)

            token.status = AsyncCompletionStatus.FAILED
            token.error = error
            token.completed_at = datetime.now(UTC)

            # Notify waiter if any
            if token.token_id in self._waiters:
                future = self._waiters.pop(token.token_id)
                if not future.done():
                    future.set_exception(AsyncCompletionError(error))

            logger.warning(
                f"Activity {token.activity_id} failed via async token: {error}"
            )
            return token

    async def wait_for_completion(
        self,
        token: ActivityToken,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Wait for an activity to be completed externally

        Args:
            token: The activity token
            timeout: Optional timeout in seconds

        Returns:
            The result provided by the external system

        Raises:
            asyncio.TimeoutError: If timeout expires
            AsyncCompletionError: If activity fails
        """
        if token.status == AsyncCompletionStatus.COMPLETED:
            return token.result

        if token.status == AsyncCompletionStatus.FAILED:
            raise AsyncCompletionError(token.error or "Activity failed")

        if token.is_expired:
            raise TokenExpiredError(token.token_id)

        # Create future and wait
        future = asyncio.get_event_loop().create_future()
        self._waiters[token.token_id] = future

        try:
            if timeout:
                return await asyncio.wait_for(future, timeout)
            return await future
        except TimeoutError:
            # Clean up waiter
            self._waiters.pop(token.token_id, None)
            token.status = AsyncCompletionStatus.EXPIRED
            raise

    def cancel(self, token_string: str) -> ActivityToken:
        """
        Cancel a pending async completion

        Args:
            token_string: Token string

        Returns:
            The cancelled ActivityToken
        """
        token = self.get_token(token_string)

        if token.status != AsyncCompletionStatus.PENDING:
            raise TokenAlreadyCompletedError(token.token_id, token.status)

        token.status = AsyncCompletionStatus.CANCELLED
        token.completed_at = datetime.now(UTC)

        # Cancel waiter if any
        if token.token_id in self._waiters:
            future = self._waiters.pop(token.token_id)
            if not future.done():
                future.cancel()

        logger.info(f"Async completion cancelled for activity {token.activity_id}")
        return token

    def on_complete(self, callback: Callable) -> None:
        """Register a callback for completion events"""
        self._on_complete_callbacks.append(callback)

    def get_pending_tokens(
        self,
        workflow_id: Optional[str] = None,
    ) -> List[ActivityToken]:
        """Get all pending tokens, optionally filtered by workflow"""
        tokens = [
            t
            for t in self._tokens.values()
            if t.status == AsyncCompletionStatus.PENDING
        ]

        if workflow_id:
            tokens = [t for t in tokens if t.workflow_id == workflow_id]

        return tokens

    def cleanup_expired(self) -> int:
        """
        Clean up expired tokens

        Returns number of tokens cleaned up
        """
        expired = [
            token_id for token_id, token in self._tokens.items() if token.is_expired
        ]

        for token_id in expired:
            token = self._tokens[token_id]
            token.status = AsyncCompletionStatus.EXPIRED

            # Cancel waiter if any
            if token_id in self._waiters:
                future = self._waiters.pop(token_id)
                if not future.done():
                    future.set_exception(TokenExpiredError(token_id))

        return len(expired)


# Global manager instance
_manager: Optional[AsyncCompletionManager] = None


def get_async_completion_manager() -> AsyncCompletionManager:
    """Get the global async completion manager"""
    global _manager
    if _manager is None:
        _manager = AsyncCompletionManager()
    return _manager


# Convenience functions
async def async_complete(token_string: str, result: Any = None) -> ActivityToken:
    """Complete an activity via its token"""
    manager = get_async_completion_manager()
    return await manager.complete(token_string, result)


async def async_fail(token_string: str, error: str) -> ActivityToken:
    """Fail an activity via its token"""
    manager = get_async_completion_manager()
    return await manager.fail(token_string, error)


def get_activity_token(
    workflow_id: str,
    activity_id: str,
    activity_type: str,
    ttl_hours: float = 24.0,
) -> str:
    """
    Create a new activity token and return its string representation

    This is the function activities call to get a token for external completion.
    """
    manager = get_async_completion_manager()
    token = manager.create_token(
        workflow_id=workflow_id,
        activity_id=activity_id,
        activity_type=activity_type,
        ttl_hours=ttl_hours,
    )
    return token.token_string


# Context for activities to access their token info
@dataclass
class AsyncActivityContext:
    """Context provided to async activities"""

    workflow_id: str
    activity_id: str
    activity_type: str

    def get_token(self, ttl_hours: float = 24.0) -> str:
        """Get a token for async completion"""
        return get_activity_token(
            workflow_id=self.workflow_id,
            activity_id=self.activity_id,
            activity_type=self.activity_type,
            ttl_hours=ttl_hours,
        )


# Thread-local context storage
_current_context: Optional[AsyncActivityContext] = None


def get_current_async_context() -> Optional[AsyncActivityContext]:
    """Get the current async activity context"""
    return _current_context


def set_current_async_context(context: Optional[AsyncActivityContext]) -> None:
    """Set the current async activity context"""
    global _current_context
    _current_context = context


# Decorator for async completion activities
def async_activity(
    name: Optional[str] = None,
    ttl_hours: float = 24.0,
):
    """
    Decorator to mark an activity for async completion

    Usage:
        @async_activity("wait_for_approval")
        async def wait_for_approval(request: dict) -> str:
            ctx = get_current_async_context()
            token = ctx.get_token()
            send_approval_email(request["email"], token)
            # Returns None immediately, caller will wait for async_complete()
    """

    def decorator(func: Callable) -> Callable:
        func._activity_name = name or func.__name__
        func._is_async_activity = True
        func._async_ttl_hours = ttl_hours
        return func

    return decorator
