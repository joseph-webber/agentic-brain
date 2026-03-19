"""
Atmosphere-inspired multi-transport framework for Python/FastAPI

Handles WebSocket → SSE → Long-polling → Streaming → JSONP fallback
with automatic negotiation and transparent reconnection.

Production-ready implementation for agentic-brain.
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Set, Dict, Any, List
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

class TransportType(str, Enum):
    """Supported transport types in priority order"""
    WEBSOCKET = "websocket"      # Best: bidirectional, low-latency
    SSE = "sse"                  # Good: unidirectional, persistent
    LONG_POLLING = "long_polling"  # Fair: simulated bidirectional
    STREAMING = "streaming"      # Fair: chunked HTTP
    JSONP = "jsonp"              # Fallback: works everywhere


class ConnectionState(str, Enum):
    """Connection lifecycle states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADING = "degrading"      # Attempting fallback
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    CLOSED = "closed"


@dataclass
class TransportCapability:
    """What a transport can do"""
    name: TransportType
    bidirectional: bool           # Can send & receive?
    persistent: bool              # Connection stays alive?
    latency: float               # Approximate RTT (seconds)
    max_message_size: int        # Bytes
    browser_support: float       # % of browsers (0-1)
    requires_cors: bool          # Needs CORS?


# Standard capabilities for each transport
TRANSPORT_CAPABILITIES = {
    TransportType.WEBSOCKET: TransportCapability(
        name=TransportType.WEBSOCKET,
        bidirectional=True,
        persistent=True,
        latency=0.010,
        max_message_size=64 * 1024 * 1024,
        browser_support=0.98,
        requires_cors=False,
    ),
    TransportType.SSE: TransportCapability(
        name=TransportType.SSE,
        bidirectional=False,  # Server → Client only
        persistent=True,
        latency=0.050,
        max_message_size=64 * 1024,
        browser_support=0.95,
        requires_cors=True,
    ),
    TransportType.LONG_POLLING: TransportCapability(
        name=TransportType.LONG_POLLING,
        bidirectional=True,
        persistent=False,
        latency=0.5,
        max_message_size=256 * 1024,
        browser_support=0.99,
        requires_cors=True,
    ),
    TransportType.STREAMING: TransportCapability(
        name=TransportType.STREAMING,
        bidirectional=False,
        persistent=True,
        latency=0.1,
        max_message_size=64 * 1024,
        browser_support=0.99,
        requires_cors=True,
    ),
    TransportType.JSONP: TransportCapability(
        name=TransportType.JSONP,
        bidirectional=True,
        persistent=False,
        latency=1.0,
        max_message_size=4 * 1024,
        browser_support=1.0,
        requires_cors=False,
    ),
}


class AtmosphereMessage(BaseModel):
    """Standardized message format across all transports"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: float = Field(default_factory=time.time)
    transport: TransportType
    sender: str  # "client" or "server"
    data: Dict[str, Any]
    meta: Dict[str, Any] = Field(default_factory=dict)
    
    # Delivery tracking
    acked: bool = False
    retry_count: int = 0


@dataclass
class ConnectionMetrics:
    """Track connection health & performance"""
    created_at: float = field(default_factory=time.time)
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    transport_switches: int = 0
    last_activity: float = field(default_factory=time.time)
    
    @property
    def uptime(self) -> float:
        """Seconds since connection created"""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """Seconds since last activity"""
        return time.time() - self.last_activity
    
    def record_send(self, size: int):
        self.bytes_sent += size
        self.messages_sent += 1
        self.last_activity = time.time()
    
    def record_receive(self, size: int):
        self.bytes_received += size
        self.messages_received += 1
        self.last_activity = time.time()


# ============================================================================
# BASE TRANSPORT INTERFACE
# ============================================================================

class BaseTransport(ABC):
    """Abstract base for all transport implementations"""
    
    def __init__(self, connection_id: str, timeout: float = 30.0):
        self.connection_id = connection_id
        self.timeout = timeout
        self.capabilities = TRANSPORT_CAPABILITIES[self.transport_type]
        self.metrics = ConnectionMetrics()
        self._message_queue: asyncio.Queue[AtmosphereMessage] = asyncio.Queue()
        self._handlers: List[Callable[[AtmosphereMessage], None]] = []
        self._health_check_task: Optional[asyncio.Task] = None
    
    @property
    @abstractmethod
    def transport_type(self) -> TransportType:
        """Must be overridden by subclasses"""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection, return success status"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Clean shutdown"""
        pass
    
    @abstractmethod
    async def send_message(self, message: AtmosphereMessage) -> bool:
        """Send message, return success"""
        pass
    
    @abstractmethod
    async def receive_message(self) -> Optional[AtmosphereMessage]:
        """Receive next message, with timeout"""
        pass
    
    async def is_healthy(self) -> bool:
        """Check if transport is still viable"""
        # Default: check idle timeout
        return self.metrics.idle_time < self.timeout
    
    def add_message_handler(self, handler: Callable[[AtmosphereMessage], None]) -> None:
        """Register handler for incoming messages"""
        self._handlers.append(handler)
    
    async def _notify_handlers(self, message: AtmosphereMessage) -> None:
        """Call all registered handlers"""
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Handler error in {self.transport_type}: {e}")


class WebSocketTransport(BaseTransport):
    """WebSocket implementation - BEST transport"""
    
    def __init__(self, connection_id: str, websocket):
        super().__init__(connection_id)
        self.websocket = websocket
        self._connect_time: Optional[float] = None
    
    @property
    def transport_type(self) -> TransportType:
        return TransportType.WEBSOCKET
    
    async def connect(self) -> bool:
        """WebSocket connection already established by FastAPI"""
        self._connect_time = time.time()
        logger.info(f"[{self.connection_id}] WebSocket connected")
        return True
    
    async def disconnect(self) -> None:
        try:
            await self.websocket.close()
            logger.info(f"[{self.connection_id}] WebSocket closed")
        except Exception as e:
            logger.warning(f"[{self.connection_id}] Error closing WebSocket: {e}")
    
    async def send_message(self, message: AtmosphereMessage) -> bool:
        try:
            data = json.dumps(message.model_dump())
            await self.websocket.send_text(data)
            self.metrics.record_send(len(data))
            return True
        except Exception as e:
            logger.error(f"[{self.connection_id}] WebSocket send error: {e}")
            return False
    
    async def receive_message(self) -> Optional[AtmosphereMessage]:
        try:
            data = await asyncio.wait_for(self.websocket.receive_text(), timeout=self.timeout)
            self.metrics.record_receive(len(data))
            return AtmosphereMessage(**json.loads(data))
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"[{self.connection_id}] WebSocket receive error: {e}")
            return None
    
    async def is_healthy(self) -> bool:
        """Check connection state"""
        try:
            # If we can't access the websocket, it's dead
            return self.websocket is not None and not self.websocket.client_state.name.startswith("DISCONNECTED")
        except Exception:
            return False


class SSETransport(BaseTransport):
    """Server-Sent Events - GOOD for unidirectional server→client"""
    
    def __init__(self, connection_id: str, timeout: float = 30.0):
        super().__init__(connection_id, timeout)
        self.client_queue: asyncio.Queue[AtmosphereMessage] = asyncio.Queue()
        self._sse_task: Optional[asyncio.Task] = None
    
    @property
    def transport_type(self) -> TransportType:
        return TransportType.SSE
    
    async def connect(self) -> bool:
        logger.info(f"[{self.connection_id}] SSE connected")
        return True
    
    async def disconnect(self) -> None:
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()
        logger.info(f"[{self.connection_id}] SSE disconnected")
    
    async def send_message(self, message: AtmosphereMessage) -> bool:
        """Queue message for SSE transmission (unidirectional server→client)"""
        try:
            await asyncio.wait_for(self.client_queue.put(message), timeout=5.0)
            self.metrics.record_send(len(message.model_dump_json()))
            return True
        except asyncio.TimeoutError:
            logger.warning(f"[{self.connection_id}] SSE queue full")
            return False
    
    async def receive_message(self) -> Optional[AtmosphereMessage]:
        """SSE is unidirectional, so this receives client responses via polling endpoint"""
        try:
            msg = await asyncio.wait_for(self._message_queue.get(), timeout=self.timeout)
            self.metrics.record_receive(len(msg.model_dump_json()))
            return msg
        except asyncio.TimeoutError:
            return None
    
    async def sse_stream(self):
        """Generator for FastAPI StreamingResponse"""
        try:
            while True:
                try:
                    message = await asyncio.wait_for(self.client_queue.get(), timeout=self.timeout)
                    yield f"data: {message.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            logger.info(f"[{self.connection_id}] SSE stream closed")
        except Exception as e:
            logger.error(f"[{self.connection_id}] SSE stream error: {e}")


class LongPollingTransport(BaseTransport):
    """Long-polling - FAIR, simulated bidirectional"""
    
    def __init__(self, connection_id: str, timeout: float = 25.0):
        super().__init__(connection_id, timeout)
        self.response_queue: asyncio.Queue[List[AtmosphereMessage]] = asyncio.Queue()
    
    @property
    def transport_type(self) -> TransportType:
        return TransportType.LONG_POLLING
    
    async def connect(self) -> bool:
        logger.info(f"[{self.connection_id}] Long-polling connected")
        return True
    
    async def disconnect(self) -> None:
        logger.info(f"[{self.connection_id}] Long-polling disconnected")
    
    async def send_message(self, message: AtmosphereMessage) -> bool:
        """Queue server messages for next poll"""
        try:
            await self.response_queue.put([message])
            self.metrics.record_send(len(message.model_dump_json()))
            return True
        except Exception as e:
            logger.error(f"[{self.connection_id}] Long-polling send error: {e}")
            return False
    
    async def receive_message(self) -> Optional[AtmosphereMessage]:
        """In long-polling, we wait for client POST"""
        try:
            msg = await asyncio.wait_for(self._message_queue.get(), timeout=self.timeout)
            self.metrics.record_receive(len(msg.model_dump_json()))
            return msg
        except asyncio.TimeoutError:
            return None
    
    async def poll(self) -> List[AtmosphereMessage]:
        """Client calls this to get pending messages"""
        try:
            # Wait up to timeout for messages, return empty list if none
            messages = await asyncio.wait_for(self.response_queue.get(), timeout=self.timeout)
            return messages
        except asyncio.TimeoutError:
            # Return empty array to keep connection alive
            return []


class StreamingTransport(BaseTransport):
    """HTTP Chunked Streaming - FAIR, unidirectional"""
    
    def __init__(self, connection_id: str):
        super().__init__(connection_id)
        self.stream_queue: asyncio.Queue[AtmosphereMessage] = asyncio.Queue()
    
    @property
    def transport_type(self) -> TransportType:
        return TransportType.STREAMING
    
    async def connect(self) -> bool:
        logger.info(f"[{self.connection_id}] Streaming connected")
        return True
    
    async def disconnect(self) -> None:
        logger.info(f"[{self.connection_id}] Streaming disconnected")
    
    async def send_message(self, message: AtmosphereMessage) -> bool:
        try:
            await self.stream_queue.put(message)
            self.metrics.record_send(len(message.model_dump_json()))
            return True
        except Exception as e:
            logger.error(f"[{self.connection_id}] Streaming send error: {e}")
            return False
    
    async def receive_message(self) -> Optional[AtmosphereMessage]:
        try:
            msg = await asyncio.wait_for(self._message_queue.get(), timeout=self.timeout)
            self.metrics.record_receive(len(msg.model_dump_json()))
            return msg
        except asyncio.TimeoutError:
            return None
    
    async def stream_generator(self):
        """Generator for FastAPI StreamingResponse"""
        try:
            while True:
                try:
                    message = await asyncio.wait_for(self.stream_queue.get(), timeout=30)
                    yield message.model_dump_json().encode() + b"\n"
                except asyncio.TimeoutError:
                    yield b"\n"  # Keep connection alive
        except GeneratorExit:
            logger.info(f"[{self.connection_id}] Stream closed")


class JSONPTransport(BaseTransport):
    """JSONP polling - WORST but works everywhere (cross-domain)"""
    
    def __init__(self, connection_id: str, timeout: float = 25.0):
        super().__init__(connection_id, timeout)
    
    @property
    def transport_type(self) -> TransportType:
        return TransportType.JSONP
    
    async def connect(self) -> bool:
        logger.info(f"[{self.connection_id}] JSONP connected")
        return True
    
    async def disconnect(self) -> None:
        logger.info(f"[{self.connection_id}] JSONP disconnected")
    
    async def send_message(self, message: AtmosphereMessage) -> bool:
        try:
            await self._message_queue.put(message)
            self.metrics.record_send(len(message.model_dump_json()))
            return True
        except Exception as e:
            logger.error(f"[{self.connection_id}] JSONP send error: {e}")
            return False
    
    async def receive_message(self) -> Optional[AtmosphereMessage]:
        try:
            msg = await asyncio.wait_for(self._message_queue.get(), timeout=self.timeout)
            self.metrics.record_receive(len(msg.model_dump_json()))
            return msg
        except asyncio.TimeoutError:
            return None


# ============================================================================
# TRANSPORT MANAGER (CORE ORCHESTRATOR)
# ============================================================================

class TransportManager:
    """
    Orchestrates transport negotiation, fallback, and connection management.
    
    Core responsibilities:
    1. Negotiate best transport from client capabilities
    2. Manage connection lifecycle
    3. Handle transparent fallback
    4. Buffer messages during degradation
    5. Track metrics and health
    
    Usage:
        manager = TransportManager()
        transport = await manager.negotiate(
            client_preferences=[TransportType.WEBSOCKET, TransportType.SSE],
            server_capabilities=all_transports
        )
        await transport.connect()
        msg = AtmosphereMessage(...)
        await transport.send_message(msg)
    """
    
    def __init__(self, max_buffer_size: int = 1000):
        self.max_buffer_size = max_buffer_size
        self.connections: Dict[str, BaseTransport] = {}
        self.message_buffer: Dict[str, asyncio.Queue] = {}
        self.connection_states: Dict[str, ConnectionState] = {}
        self.logger = logger
    
    async def negotiate(
        self,
        connection_id: str,
        client_preferences: List[TransportType],
        websocket=None,
    ) -> Optional[BaseTransport]:
        """
        Negotiate best transport with client.
        
        Returns: Selected transport instance, or None if negotiation fails
        """
        self.logger.info(
            f"[{connection_id}] Negotiating transport. "
            f"Client preferences: {client_preferences}"
        )
        
        # Filter by client preferences and create instances
        for transport_type in client_preferences:
            try:
                if transport_type == TransportType.WEBSOCKET and websocket:
                    transport = WebSocketTransport(connection_id, websocket)
                elif transport_type == TransportType.SSE:
                    transport = SSETransport(connection_id)
                elif transport_type == TransportType.LONG_POLLING:
                    transport = LongPollingTransport(connection_id)
                elif transport_type == TransportType.STREAMING:
                    transport = StreamingTransport(connection_id)
                elif transport_type == TransportType.JSONP:
                    transport = JSONPTransport(connection_id)
                else:
                    continue
                
                # Try to connect
                if await transport.connect():
                    self.connections[connection_id] = transport
                    self.message_buffer[connection_id] = asyncio.Queue(self.max_buffer_size)
                    self.connection_states[connection_id] = ConnectionState.CONNECTED
                    
                    self.logger.info(
                        f"[{connection_id}] Selected {transport_type} transport"
                    )
                    return transport
            
            except Exception as e:
                self.logger.warning(
                    f"[{connection_id}] {transport_type} negotiation failed: {e}"
                )
                continue
        
        self.logger.error(f"[{connection_id}] All transports failed")
        return None
    
    async def handle_fallback(self, connection_id: str) -> bool:
        """
        Attempt fallback to next transport when current one fails.
        
        Returns: True if fallback successful
        """
        current_transport = self.connections.get(connection_id)
        if not current_transport:
            return False
        
        self.connection_states[connection_id] = ConnectionState.DEGRADING
        
        # Try next transport in priority order
        fallback_order = [
            t for t in TransportType
            if t != current_transport.transport_type
        ]
        
        self.logger.warning(
            f"[{connection_id}] Attempting fallback from {current_transport.transport_type}"
        )
        
        for next_transport_type in fallback_order:
            try:
                await current_transport.disconnect()
                
                # Negotiate next transport
                new_transport = await self.negotiate(
                    connection_id,
                    [next_transport_type],
                    websocket=None
                )
                
                if new_transport:
                    current_transport.metrics.transport_switches += 1
                    self.connection_states[connection_id] = ConnectionState.CONNECTED
                    
                    self.logger.info(
                        f"[{connection_id}] Fallback to {next_transport_type} successful"
                    )
                    return True
            
            except Exception as e:
                self.logger.debug(f"[{connection_id}] Fallback attempt failed: {e}")
                continue
        
        self.connection_states[connection_id] = ConnectionState.DISCONNECTED
        return False
    
    def get_transport(self, connection_id: str) -> Optional[BaseTransport]:
        """Get current transport for connection"""
        return self.connections.get(connection_id)
    
    def get_state(self, connection_id: str) -> ConnectionState:
        """Get connection state"""
        return self.connection_states.get(connection_id, ConnectionState.DISCONNECTED)
    
    def get_metrics(self, connection_id: str) -> Optional[ConnectionMetrics]:
        """Get connection metrics"""
        transport = self.get_transport(connection_id)
        return transport.metrics if transport else None
    
    async def buffer_message(self, connection_id: str, message: AtmosphereMessage) -> bool:
        """Buffer message for delivery (handles disconnection)"""
        try:
            buffer = self.message_buffer.get(connection_id)
            if buffer:
                await asyncio.wait_for(buffer.put(message), timeout=1.0)
                return True
        except asyncio.TimeoutError:
            self.logger.warning(f"[{connection_id}] Message buffer full, dropping message")
        except Exception as e:
            self.logger.error(f"[{connection_id}] Buffer error: {e}")
        
        return False
    
    async def flush_buffer(self, connection_id: str, transport: BaseTransport) -> int:
        """Flush buffered messages through transport"""
        count = 0
        buffer = self.message_buffer.get(connection_id)
        
        if not buffer:
            return 0
        
        while not buffer.empty():
            try:
                message = buffer.get_nowait()
                if await transport.send_message(message):
                    count += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                self.logger.error(f"[{connection_id}] Flush error: {e}")
                break
        
        return count
    
    async def cleanup(self, connection_id: str) -> None:
        """Clean up connection"""
        transport = self.connections.pop(connection_id, None)
        if transport:
            await transport.disconnect()
        
        self.message_buffer.pop(connection_id, None)
        self.connection_states[connection_id] = ConnectionState.CLOSED
        
        self.logger.info(f"[{connection_id}] Connection cleaned up")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    async def example():
        """Simple example"""
        manager = TransportManager()
        
        # Simulate client preferences (would come from client handshake)
        client_prefs = [
            TransportType.WEBSOCKET,
            TransportType.SSE,
            TransportType.LONG_POLLING,
        ]
        
        # Negotiate transport
        transport = await manager.negotiate(
            connection_id="test-conn-1",
            client_preferences=client_prefs,
            websocket=None
        )
        
        if transport:
            print(f"✓ Selected: {transport.transport_type}")
            print(f"  Capabilities: bidirectional={transport.capabilities.bidirectional}")
            print(f"  Metrics: {transport.metrics}")
    
    asyncio.run(example())
