# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Workflow Signals for Agentic Brain

Signals allow external events to influence running workflows.
This provides durable signal semantics for AI workflows.

Features:
- Type-safe signal definitions
- Signal handlers with validation
- Signal buffering for offline workflows
- Signal history tracking
"""

import asyncio
import inspect
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SignalDeliveryStatus(Enum):
    """Status of signal delivery"""

    PENDING = "pending"
    DELIVERED = "delivered"
    BUFFERED = "buffered"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class SignalDefinition:
    """
    Definition of a signal type

    Signals are typed messages that can be sent to workflows.
    """

    name: str
    description: str = ""
    payload_type: Optional[Type] = None
    validator: Optional[Callable[[Any], bool]] = None

    def validate(self, payload: Any) -> bool:
        """Validate signal payload"""
        if self.validator:
            return self.validator(payload)
        if self.payload_type:
            return isinstance(payload, self.payload_type)
        return True


@dataclass
class Signal:
    """
    An instance of a signal sent to a workflow
    """

    signal_id: str
    signal_name: str
    workflow_id: str
    payload: Any

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None
    status: SignalDeliveryStatus = SignalDeliveryStatus.PENDING

    # Correlation
    sender_id: Optional[str] = None
    correlation_id: Optional[str] = None

    # TTL
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize signal to dictionary"""
        return {
            "signal_id": self.signal_id,
            "signal_name": self.signal_name,
            "workflow_id": self.workflow_id,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "delivered_at": (
                self.delivered_at.isoformat() if self.delivered_at else None
            ),
            "status": self.status.value,
            "sender_id": self.sender_id,
            "correlation_id": self.correlation_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        """Deserialize signal from dictionary"""
        return cls(
            signal_id=data["signal_id"],
            signal_name=data["signal_name"],
            workflow_id=data["workflow_id"],
            payload=data["payload"],
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(UTC)
            ),
            delivered_at=(
                datetime.fromisoformat(data["delivered_at"])
                if data.get("delivered_at")
                else None
            ),
            status=SignalDeliveryStatus(data.get("status", "pending")),
            sender_id=data.get("sender_id"),
            correlation_id=data.get("correlation_id"),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
        )

    @property
    def is_expired(self) -> bool:
        """Check if signal has expired"""
        if not self.expires_at:
            return False
        return datetime.now(UTC) > self.expires_at


class SignalHandler:
    """
    Handler for workflow signals

    Manages signal reception and handler dispatch.
    """

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id

        # Registered signal handlers
        self._handlers: Dict[str, Callable] = {}

        # Signal definitions
        self._definitions: Dict[str, SignalDefinition] = {}

        # Buffered signals (for offline workflows)
        self._buffer: List[Signal] = []

        # Signal history
        self._history: List[Signal] = []

        # Waiting futures (for wait_for_signal)
        self._waiters: Dict[str, List[asyncio.Future]] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

    def define_signal(
        self,
        name: str,
        description: str = "",
        payload_type: Optional[Type] = None,
        validator: Optional[Callable[[Any], bool]] = None,
    ) -> SignalDefinition:
        """Define a new signal type"""
        definition = SignalDefinition(
            name=name,
            description=description,
            payload_type=payload_type,
            validator=validator,
        )
        self._definitions[name] = definition
        return definition

    def register_handler(
        self,
        signal_name: str,
        handler: Callable,
    ) -> None:
        """Register a handler for a signal type"""
        self._handlers[signal_name] = handler
        logger.debug(f"Registered signal handler for '{signal_name}'")

    async def receive(self, signal: Signal) -> bool:
        """
        Receive and process a signal

        Returns True if signal was handled, False if buffered
        """
        async with self._lock:
            # Check expiration
            if signal.is_expired:
                signal.status = SignalDeliveryStatus.EXPIRED
                self._history.append(signal)
                logger.warning(f"Signal {signal.signal_id} expired")
                return False

            # Validate payload
            definition = self._definitions.get(signal.signal_name)
            if definition and not definition.validate(signal.payload):
                signal.status = SignalDeliveryStatus.FAILED
                self._history.append(signal)
                logger.error(f"Signal {signal.signal_id} validation failed")
                return False

            # Check for waiting futures
            if (
                signal.signal_name in self._waiters
                and self._waiters[signal.signal_name]
            ):
                future = self._waiters[signal.signal_name].pop(0)
                if not future.done():
                    future.set_result(signal)
                    signal.status = SignalDeliveryStatus.DELIVERED
                    signal.delivered_at = datetime.now(UTC)
                    self._history.append(signal)
                    logger.debug(f"Signal {signal.signal_id} delivered to waiter")
                    return True

            # Try to invoke handler
            handler = self._handlers.get(signal.signal_name)
            if handler:
                try:
                    if inspect.iscoroutinefunction(handler):
                        await handler(signal.payload)
                    else:
                        handler(signal.payload)

                    signal.status = SignalDeliveryStatus.DELIVERED
                    signal.delivered_at = datetime.now(UTC)
                    self._history.append(signal)
                    logger.debug(f"Signal {signal.signal_id} handled")
                    return True

                except Exception as e:
                    signal.status = SignalDeliveryStatus.FAILED
                    self._history.append(signal)
                    logger.error(f"Signal handler error: {e}")
                    return False

            # No handler, buffer the signal
            signal.status = SignalDeliveryStatus.BUFFERED
            self._buffer.append(signal)
            logger.debug(f"Signal {signal.signal_id} buffered")
            return False

    async def wait_for_signal(
        self,
        signal_name: str,
        timeout: Optional[float] = None,
    ) -> Optional[Signal]:
        """
        Wait for a signal to be received

        Args:
            signal_name: Name of signal to wait for
            timeout: Optional timeout in seconds

        Returns:
            The received signal, or None if timeout
        """
        # Check buffer first
        for i, signal in enumerate(self._buffer):
            if signal.signal_name == signal_name:
                signal = self._buffer.pop(i)
                signal.status = SignalDeliveryStatus.DELIVERED
                signal.delivered_at = datetime.now(UTC)
                self._history.append(signal)
                return signal

        # Create future and wait
        future = asyncio.get_event_loop().create_future()

        if signal_name not in self._waiters:
            self._waiters[signal_name] = []
        self._waiters[signal_name].append(future)

        try:
            if timeout:
                return await asyncio.wait_for(future, timeout)
            return await future
        except TimeoutError:
            # Remove future from waiters
            if signal_name in self._waiters:
                try:
                    self._waiters[signal_name].remove(future)
                except ValueError:
                    pass
            return None

    def process_buffered(self) -> int:
        """
        Process any buffered signals

        Call this when a workflow resumes to handle signals
        received while offline.

        Returns number of signals processed
        """
        processed = 0
        remaining = []

        for signal in self._buffer:
            handler = self._handlers.get(signal.signal_name)
            if handler:
                try:
                    # Sync handler only for buffered processing
                    if not inspect.iscoroutinefunction(handler):
                        handler(signal.payload)
                        signal.status = SignalDeliveryStatus.DELIVERED
                        signal.delivered_at = datetime.now(UTC)
                        self._history.append(signal)
                        processed += 1
                    else:
                        remaining.append(signal)
                except Exception as e:
                    logger.error(f"Buffered signal handler error: {e}")
                    remaining.append(signal)
            else:
                remaining.append(signal)

        self._buffer = remaining
        return processed

    def get_history(
        self,
        signal_name: Optional[str] = None,
        status: Optional[SignalDeliveryStatus] = None,
    ) -> List[Signal]:
        """Get signal history with optional filters"""
        history = self._history

        if signal_name:
            history = [s for s in history if s.signal_name == signal_name]

        if status:
            history = [s for s in history if s.status == status]

        return history

    def get_buffered(self) -> List[Signal]:
        """Get buffered signals"""
        return list(self._buffer)

    def clear_buffer(self) -> int:
        """Clear signal buffer, returns count cleared"""
        count = len(self._buffer)
        self._buffer.clear()
        return count


class SignalDispatcher:
    """
    Central dispatcher for workflow signals

    Routes signals to appropriate workflow signal handlers.
    """

    def __init__(self):
        self._handlers: Dict[str, SignalHandler] = {}
        self._pending: Dict[str, List[Signal]] = {}  # workflow_id -> signals

    def register_workflow(self, workflow_id: str) -> SignalHandler:
        """Register a workflow for signal handling"""
        if workflow_id not in self._handlers:
            handler = SignalHandler(workflow_id)
            self._handlers[workflow_id] = handler

            # Deliver any pending signals
            if workflow_id in self._pending:
                for signal in self._pending[workflow_id]:
                    asyncio.create_task(handler.receive(signal))
                del self._pending[workflow_id]

        return self._handlers[workflow_id]

    def unregister_workflow(self, workflow_id: str) -> None:
        """Unregister a workflow"""
        self._handlers.pop(workflow_id, None)

    async def send_signal(
        self,
        workflow_id: str,
        signal_name: str,
        payload: Any = None,
        sender_id: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
    ) -> Signal:
        """
        Send a signal to a workflow

        Args:
            workflow_id: Target workflow ID
            signal_name: Name of the signal
            payload: Signal payload data
            sender_id: Optional sender identifier
            ttl_seconds: Optional time-to-live in seconds

        Returns:
            The created Signal instance
        """
        signal = Signal(
            signal_id=str(uuid.uuid4()),
            signal_name=signal_name,
            workflow_id=workflow_id,
            payload=payload,
            sender_id=sender_id,
            expires_at=(
                datetime.now(UTC).replace(
                    second=datetime.now(UTC).second + int(ttl_seconds)
                )
                if ttl_seconds
                else None
            ),
        )

        # Try to deliver immediately
        handler = self._handlers.get(workflow_id)
        if handler:
            await handler.receive(signal)
        else:
            # Buffer for when workflow registers
            if workflow_id not in self._pending:
                self._pending[workflow_id] = []
            self._pending[workflow_id].append(signal)
            signal.status = SignalDeliveryStatus.BUFFERED
            logger.debug(
                f"Signal {signal.signal_id} buffered for offline workflow {workflow_id}"
            )

        return signal

    def get_handler(self, workflow_id: str) -> Optional[SignalHandler]:
        """Get signal handler for a workflow"""
        return self._handlers.get(workflow_id)

    def get_pending_count(self, workflow_id: str) -> int:
        """Get count of pending signals for a workflow"""
        return len(self._pending.get(workflow_id, []))


# Global signal dispatcher
_dispatcher: Optional[SignalDispatcher] = None


def get_signal_dispatcher() -> SignalDispatcher:
    """Get the global signal dispatcher"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = SignalDispatcher()
    return _dispatcher


# Decorator for signal handlers
def signal_handler(signal_name: str):
    """
    Decorator to mark a method as a signal handler

    Usage:
        class MyWorkflow(DurableWorkflow):
            @signal_handler("approval")
            async def handle_approval(self, payload):
                self.approved = payload["approved"]
    """

    def decorator(func: Callable) -> Callable:
        func._signal_name = signal_name
        func._is_signal_handler = True
        return func

    return decorator


def extract_signal_handlers(obj: Any) -> Dict[str, Callable]:
    """
    Extract all signal handlers from an object

    Returns dict of signal_name -> handler method
    """
    handlers = {}
    for name in dir(obj):
        method = getattr(obj, name)
        if callable(method) and hasattr(method, "_is_signal_handler"):
            handlers[method._signal_name] = method
    return handlers


# Common signal definitions for AI workflows
CANCEL_SIGNAL = SignalDefinition(
    name="cancel",
    description="Request workflow cancellation",
    payload_type=dict,
)

PAUSE_SIGNAL = SignalDefinition(
    name="pause",
    description="Pause workflow execution",
    payload_type=dict,
)

RESUME_SIGNAL = SignalDefinition(
    name="resume",
    description="Resume paused workflow",
    payload_type=dict,
)

UPDATE_SIGNAL = SignalDefinition(
    name="update",
    description="Update workflow parameters",
    payload_type=dict,
)

APPROVAL_SIGNAL = SignalDefinition(
    name="approval",
    description="Human approval/rejection",
    payload_type=dict,
    validator=lambda p: "approved" in p and isinstance(p["approved"], bool),
)

FEEDBACK_SIGNAL = SignalDefinition(
    name="feedback",
    description="User feedback on LLM output",
    payload_type=dict,
)

ESCALATION_SIGNAL = SignalDefinition(
    name="escalation",
    description="Escalate to human operator",
    payload_type=dict,
)
