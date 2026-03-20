"""Firebase Realtime Database transport - scalable, persistent."""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Optional
import uuid

from .base import BaseTransport, TransportConfig, TransportMessage, TransportType

logger = logging.getLogger(__name__)

# Firebase is optional - graceful fallback if not installed
try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    credentials = None
    db = None


class FirebaseTransport(BaseTransport):
    """Firebase Realtime Database transport.
    
    Features:
    - Persistent message storage
    - Cross-device synchronization
    - Offline support with sync on reconnect
    - Scalable to millions of connections
    
    Requires:
    - pip install firebase-admin
    - Firebase project with Realtime Database
    - Service account credentials JSON
    """
    
    def __init__(self, config: TransportConfig, session_id: Optional[str] = None):
        super().__init__(config)
        self.session_id = session_id or str(uuid.uuid4())
        self._app: Optional[Any] = None
        self._ref: Optional[Any] = None
        self._listener: Optional[Any] = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._closed = False
    
    @property
    def transport_type(self) -> TransportType:
        return TransportType.FIREBASE
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if Firebase SDK is installed."""
        return FIREBASE_AVAILABLE
    
    async def connect(self) -> bool:
        """Initialize Firebase connection."""
        if not FIREBASE_AVAILABLE:
            logger.error("Firebase SDK not installed. Run: pip install firebase-admin")
            return False
        
        try:
            # Get credentials path from config or environment
            cred_path = self.config.firebase_credentials or os.getenv("FIREBASE_CREDENTIALS")
            if not cred_path:
                logger.error("Firebase credentials not configured")
                return False
            
            # Initialize Firebase app (only once)
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                self._app = firebase_admin.initialize_app(cred, {
                    "databaseURL": self.config.firebase_url or os.getenv("FIREBASE_DATABASE_URL")
                })
            
            # Get reference to session messages
            self._ref = db.reference(f"sessions/{self.session_id}/messages")
            
            # Set up listener for incoming messages
            def on_message(event):
                if event.data and not self._closed:
                    try:
                        asyncio.get_event_loop().call_soon_threadsafe(
                            self._message_queue.put_nowait,
                            event.data
                        )
                    except Exception as e:
                        logger.error(f"Firebase listener error: {e}")
            
            self._listener = self._ref.listen(on_message)
            self.connected = True
            logger.info(f"Firebase connected: session={self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Firebase connect failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close Firebase connection."""
        self._closed = True
        if self._listener:
            try:
                self._listener.close()
            except Exception as e:
                logger.warning(f"Firebase listener close error: {e}")
        self.connected = False
        logger.info("Firebase disconnected")
    
    async def send(self, message: TransportMessage) -> bool:
        """Send message to Firebase."""
        if not self.connected or not self._ref:
            return False
        try:
            data = {
                "content": message.content,
                "session_id": message.session_id,
                "message_id": message.message_id,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            }
            # Push creates unique key, set overwrites
            self._ref.push(data)
            return True
        except Exception as e:
            logger.error(f"Firebase send error: {e}")
            return False
    
    async def receive(self) -> AsyncIterator[TransportMessage]:
        """Receive messages from Firebase listener."""
        while self.connected and not self._closed:
            try:
                data = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=self.config.timeout
                )
                if isinstance(data, dict):
                    yield TransportMessage(
                        content=data.get("content", ""),
                        session_id=data.get("session_id", self.session_id),
                        message_id=data.get("message_id", ""),
                        timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
                        metadata=data.get("metadata", {}),
                    )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Firebase receive error: {e}")
                break
    
    async def is_healthy(self) -> bool:
        """Check Firebase connection health."""
        if not self.connected or not self._ref:
            return False
        try:
            # Try a simple read to verify connection
            self._ref.parent.child("_health").set({"timestamp": datetime.now(timezone.utc).isoformat()})
            return True
        except Exception:
            return False
    
    async def get_history(self, limit: int = 50) -> list[TransportMessage]:
        """Get message history from Firebase (unique to Firebase transport)."""
        if not self._ref:
            return []
        try:
            snapshot = self._ref.order_by_child("timestamp").limit_to_last(limit).get()
            messages = []
            if snapshot:
                for key, data in snapshot.items():
                    messages.append(TransportMessage(
                        content=data.get("content", ""),
                        session_id=data.get("session_id", self.session_id),
                        message_id=data.get("message_id", key),
                        timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
                        metadata=data.get("metadata", {}),
                    ))
            return messages
        except Exception as e:
            logger.error(f"Firebase history error: {e}")
            return []
