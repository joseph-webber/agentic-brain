"""Transport Manager - orchestrates multiple transports."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import AsyncIterator, Optional, List
from fastapi import WebSocket

from .base import BaseTransport, TransportConfig, TransportMessage, TransportType
from .websocket import WebSocketTransport

logger = logging.getLogger(__name__)


class TransportMode(Enum):
    """How transports are used together."""
    WEBSOCKET_ONLY = "websocket_only"      # Just WebSocket
    FIREBASE_ONLY = "firebase_only"        # Just Firebase
    WEBSOCKET_PRIMARY = "websocket_primary" # WebSocket + Firebase backup
    FIREBASE_PRIMARY = "firebase_primary"   # Firebase + WebSocket for speed
    DUAL_WRITE = "dual_write"              # Write to both, read from WebSocket


@dataclass
class TransportStatus:
    """Status of all transports."""
    websocket_connected: bool = False
    firebase_connected: bool = False
    active_transport: Optional[TransportType] = None
    mode: TransportMode = TransportMode.WEBSOCKET_ONLY
    last_message_at: Optional[datetime] = None


class TransportManager:
    """Manages multiple transports with fallback and dual-write support.
    
    Usage:
    ```python
    # WebSocket only (default, fastest)
    manager = TransportManager(mode=TransportMode.WEBSOCKET_ONLY)
    
    # Firebase only (persistent, scalable)
    manager = TransportManager(mode=TransportMode.FIREBASE_ONLY)
    
    # Both - WebSocket for speed, Firebase for persistence
    manager = TransportManager(mode=TransportMode.DUAL_WRITE)
    ```
    """
    
    def __init__(
        self,
        config: Optional[TransportConfig] = None,
        mode: TransportMode = TransportMode.WEBSOCKET_ONLY,
    ) -> None:
        self.config = config or TransportConfig()
        self.mode = mode
        self._websocket: Optional[WebSocketTransport] = None
        self._firebase: Optional[BaseTransport] = None  # Lazy import
        self._status = TransportStatus(mode=mode)
    
    async def connect(
        self,
        websocket: Optional[WebSocket] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """Connect transports based on mode."""
        logger.info(f"Transport connecting: mode={self.mode.value}")
        success = False
        
        # Connect WebSocket if needed
        if self.mode in (
            TransportMode.WEBSOCKET_ONLY,
            TransportMode.WEBSOCKET_PRIMARY,
            TransportMode.FIREBASE_PRIMARY,
            TransportMode.DUAL_WRITE,
        ):
            if websocket:
                self._websocket = WebSocketTransport(self.config, websocket)
                ws_ok = await self._websocket.connect()
                self._status.websocket_connected = ws_ok
                if ws_ok:
                    success = True
                    self._status.active_transport = TransportType.WEBSOCKET
                logger.debug(f"WebSocket connection: ok={ws_ok}")
        
        # Connect Firebase if needed
        if self.mode in (
            TransportMode.FIREBASE_ONLY,
            TransportMode.WEBSOCKET_PRIMARY,
            TransportMode.FIREBASE_PRIMARY,
            TransportMode.DUAL_WRITE,
        ):
            # Lazy import Firebase to avoid requiring it when not used
            try:
                from .firebase import FirebaseTransport
                if FirebaseTransport.is_available():
                    self._firebase = FirebaseTransport(self.config, session_id)
                    fb_ok = await self._firebase.connect()
                    self._status.firebase_connected = fb_ok
                    if fb_ok:
                        success = True
                        if self.mode == TransportMode.FIREBASE_ONLY:
                            self._status.active_transport = TransportType.FIREBASE
                    logger.debug(f"Firebase connection: ok={fb_ok}")
                else:
                    logger.warning("Firebase SDK not available, falling back to WebSocket")
            except ImportError:
                logger.warning("Firebase transport not available")
        
        logger.info(f"Transport connected: websocket={self._status.websocket_connected}, firebase={self._status.firebase_connected}")
        return success
    
    async def disconnect(self) -> None:
        """Disconnect all transports."""
        if self._websocket:
            await self._websocket.disconnect()
            self._status.websocket_connected = False
        if self._firebase:
            await self._firebase.disconnect()
            self._status.firebase_connected = False
        self._status.active_transport = None
    
    async def send(self, message: TransportMessage) -> bool:
        """Send message via configured transports."""
        self._status.last_message_at = datetime.now(timezone.utc)
        results = []
        
        # Dual write - send to both
        if self.mode == TransportMode.DUAL_WRITE:
            if self._websocket and self._status.websocket_connected:
                logger.debug(f"Message sent: transport=websocket, session={getattr(message, 'session_id', 'unknown')}")
                results.append(await self._websocket.send(message))
            if self._firebase and self._status.firebase_connected:
                logger.debug(f"Message sent: transport=firebase, session={getattr(message, 'session_id', 'unknown')}")
                results.append(await self._firebase.send(message))
            return any(results)  # Success if either worked
        
        # Primary/fallback logic
        primary = self._get_primary_transport()
        if primary:
            ok = await primary.send(message)
            if ok:
                logger.debug(f"Message sent: transport={primary.transport_type.value}, session={getattr(message, 'session_id', 'unknown')}")
                return True
            # Try fallback
            fallback = self._get_fallback_transport()
            if fallback:
                logger.warning(f"Transport send failed, trying fallback: transport={primary.transport_type.value}")
                ok = await fallback.send(message)
                if ok:
                    logger.debug(f"Message sent via fallback: transport={fallback.transport_type.value}")
                return ok
        
        return False
    
    async def receive(self) -> AsyncIterator[TransportMessage]:
        """Receive from primary transport."""
        transport = self._get_primary_transport()
        if transport:
            async for message in transport.receive():
                self._status.last_message_at = datetime.now(timezone.utc)
                yield message
    
    async def send_token(self, token: str, is_end: bool = False) -> bool:
        """Send streaming token (WebSocket only for low latency)."""
        if self._websocket and self._status.websocket_connected:
            return await self._websocket.send_token(token, is_end)
        return False
    
    def _get_primary_transport(self) -> Optional[BaseTransport]:
        """Get primary transport based on mode."""
        if self.mode in (TransportMode.WEBSOCKET_ONLY, TransportMode.WEBSOCKET_PRIMARY, TransportMode.DUAL_WRITE):
            if self._websocket and self._status.websocket_connected:
                return self._websocket
        if self.mode in (TransportMode.FIREBASE_ONLY, TransportMode.FIREBASE_PRIMARY):
            if self._firebase and self._status.firebase_connected:
                return self._firebase
        # Fallback to whatever is connected
        if self._websocket and self._status.websocket_connected:
            return self._websocket
        if self._firebase and self._status.firebase_connected:
            return self._firebase
        return None
    
    def _get_fallback_transport(self) -> Optional[BaseTransport]:
        """Get fallback transport."""
        primary = self._get_primary_transport()
        if primary and primary.transport_type == TransportType.WEBSOCKET:
            if self._firebase and self._status.firebase_connected:
                return self._firebase
        if primary and primary.transport_type == TransportType.FIREBASE:
            if self._websocket and self._status.websocket_connected:
                return self._websocket
        return None
    
    @property
    def status(self) -> TransportStatus:
        """Get current transport status."""
        return self._status
    
    async def health_check(self) -> dict:
        """Check health of all transports."""
        return {
            "websocket": await self._websocket.is_healthy() if self._websocket else False,
            "firebase": await self._firebase.is_healthy() if self._firebase else False,
            "active_transport": self._status.active_transport.value if self._status.active_transport else None,
            "mode": self.mode.value,
        }
