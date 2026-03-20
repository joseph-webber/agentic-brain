"""Base transport interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional
import logging

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Available transport types."""
    WEBSOCKET = "websocket"
    FIREBASE = "firebase"


@dataclass
class TransportConfig:
    """Transport configuration."""
    transport_type: TransportType = TransportType.WEBSOCKET
    # WebSocket settings
    websocket_url: Optional[str] = None
    # Firebase settings  
    firebase_url: Optional[str] = None
    firebase_credentials: Optional[str] = None
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
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


class BaseTransport(ABC):
    """Abstract base class for all transports."""
    
    def __init__(self, config: TransportConfig):
        self.config = config
        self.connected = False
        self._created_at = datetime.now(timezone.utc)
    
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
