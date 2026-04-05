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

"""Base transport interface."""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Available transport types."""

    WEBSOCKET = "websocket"
    FIREBASE = "firebase"
    FIRESTORE = "firestore"


@dataclass
class TransportConfig:
    """Transport configuration."""

    transport_type: TransportType = TransportType.WEBSOCKET
    # WebSocket settings
    websocket_url: Optional[str] = None
    # Firebase Realtime Database settings
    firebase_url: Optional[str] = None
    firebase_credentials: Optional[str] = None
    # Firestore settings
    firestore_project: Optional[str] = None
    firestore_credentials: Optional[str] = None
    # Common settings
    timeout: float = 30.0
    reconnect_attempts: int = 3
    heartbeat_interval: float = 30.0


@dataclass
class TransportMessage:
    """Message wrapper for transport."""

    content: str
    session_id: str
    message_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)


class BaseTransport(ABC):
    """Abstract base class for all transports."""

    def __init__(self, config: TransportConfig):
        self.config = config
        self.connected = False
        self._created_at = datetime.now(UTC)

    @property
    @abstractmethod
    def transport_type(self) -> TransportType:
        """Return the transport type."""
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection. Returns True if successful."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection gracefully."""
        pass

    @abstractmethod
    async def send(self, message: TransportMessage) -> bool:
        """Send a message. Returns True if successful."""
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[TransportMessage]:
        """Receive messages as async iterator."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        pass
