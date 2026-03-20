"""
Transport Layer - Multiple real-time communication options.

Supports:
- Native WebSocket (fast, direct)
- Firebase Realtime Database (scalable, persistent)
- Both together (WebSocket for speed, Firebase for sync)
"""

from .base import BaseTransport, TransportConfig, TransportType, TransportMessage
from .websocket import WebSocketTransport
from .manager import TransportManager, TransportMode, TransportStatus

# Firebase is optional - only import if available
try:
    from .firebase import FirebaseTransport
except ImportError:
    FirebaseTransport = None

__all__ = [
    "BaseTransport",
    "TransportConfig", 
    "TransportType",
    "TransportMessage",
    "WebSocketTransport",
    "TransportManager",
    "TransportMode",
    "TransportStatus",
    "FirebaseTransport",
]
