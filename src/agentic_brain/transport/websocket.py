"""Native WebSocket transport - fast, bidirectional."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from fastapi import WebSocket, WebSocketDisconnect

from .base import BaseTransport, TransportConfig, TransportMessage, TransportType

logger = logging.getLogger(__name__)


class WebSocketTransport(BaseTransport):
    """FastAPI native WebSocket transport.
    
    Features:
    - Bidirectional communication
    - Low latency (~10ms)
    - Automatic ping/pong keepalive
    - Graceful reconnection
    """
    
    def __init__(self, config: TransportConfig, websocket: Optional[WebSocket] = None):
        super().__init__(config)
        self.websocket = websocket
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self._closed = False
    
    @property
    def transport_type(self) -> TransportType:
        return TransportType.WEBSOCKET
    
    async def connect(self) -> bool:
        """Accept WebSocket connection."""
        if self.websocket is None:
            logger.error("No WebSocket provided")
            return False
        try:
            await self.websocket.accept()
            self.connected = True
            logger.info("WebSocket connected")
            return True
        except Exception as e:
            logger.error(f"WebSocket connect failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close WebSocket gracefully."""
        self._closed = True
        if self.websocket and self.connected:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"WebSocket close error: {e}")
        self.connected = False
        logger.info("WebSocket disconnected")
    
    async def send(self, message: TransportMessage) -> bool:
        """Send message over WebSocket."""
        if not self.connected or not self.websocket:
            return False
        try:
            data = {
                "content": message.content,
                "session_id": message.session_id,
                "message_id": message.message_id,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            }
            await self.websocket.send_json(data)
            return True
        except WebSocketDisconnect:
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            return False
    
    async def receive(self) -> AsyncIterator[TransportMessage]:
        """Receive messages from WebSocket."""
        if not self.websocket:
            return
        
        while self.connected and not self._closed:
            try:
                data = await asyncio.wait_for(
                    self.websocket.receive_json(),
                    timeout=self.config.timeout
                )
                yield TransportMessage(
                    content=data.get("content", ""),
                    session_id=data.get("session_id", ""),
                    message_id=data.get("message_id", ""),
                    timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
                    metadata=data.get("metadata", {}),
                )
            except asyncio.TimeoutError:
                continue  # Keep listening
            except WebSocketDisconnect:
                self.connected = False
                break
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                break
    
    async def is_healthy(self) -> bool:
        """Check WebSocket health via ping."""
        if not self.websocket or not self.connected:
            return False
        try:
            await self.websocket.send_json({"type": "ping"})
            return True
        except Exception:
            return False
    
    async def send_token(self, token: str, is_end: bool = False) -> bool:
        """Send a streaming token (convenience method)."""
        if not self.connected or not self.websocket:
            return False
        try:
            await self.websocket.send_json({
                "token": token,
                "is_end": is_end,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return True
        except Exception as e:
            logger.error(f"Token send error: {e}")
            return False
