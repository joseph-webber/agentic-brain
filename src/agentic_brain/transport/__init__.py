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
Transport Layer - Multiple real-time communication options.

Supports:
- Native WebSocket (fast, direct)
- Firebase Realtime Database (scalable, persistent, cross-device sync)
- Firebase Firestore (document-based, complex queries)
- Firebase Authentication (token verification, user management)
- Firebase Cloud Messaging (push notifications)
- Firebase Emulator Suite (local development)
- Both together (WebSocket for speed, Firebase for sync)

Firebase Transport Features:
- Real-time message streaming via listeners
- Session state sync across devices
- Offline support with local SQLite persistence
- Automatic reconnection with exponential backoff
- Message history retrieval
- Connection state monitoring
- Push notifications via FCM
- Local development with emulators

Usage:
    from agentic_brain.transport import FirebaseTransport, TransportConfig

    config = TransportConfig(
        firebase_url="https://my-project.firebaseio.com",
        firebase_credentials="/path/to/service-account.json",
    )

    async with FirebaseTransport(config, session_id="my-session") as transport:
        # Send message (syncs to all connected clients)
        await transport.send(message)

        # Listen for responses
        async for response in transport.listen():
            print(response)
"""

from .base import BaseTransport, TransportConfig, TransportMessage, TransportType
from .manager import TransportManager, TransportMode, TransportStatus
from .utils import utc_now
from .websocket import (
    ConnectionState as WebSocketConnectionState,
)
from .websocket import (
    ReconnectConfig,
    WebSocketAuthConfig,
    WebSocketTransport,
)

# Firebase is optional - only import if SDK available
try:
    from .firebase import (
        ConnectionState,
        FirebaseStats,
        FirebaseTransport,
        OfflineMessage,
        OfflineQueue,
    )

    FIREBASE_AVAILABLE = True
except ImportError:
    FirebaseTransport = None  # type: ignore
    ConnectionState = None  # type: ignore
    FirebaseStats = None  # type: ignore
    OfflineQueue = None  # type: ignore
    OfflineMessage = None  # type: ignore
    FIREBASE_AVAILABLE = False

# Firebase config is always available
try:
    from .firebase_config import (
        FirebaseConfig,
        load_firebase_config,
        validate_credentials_file,
    )
except ImportError:
    FirebaseConfig = None  # type: ignore
    load_firebase_config = None  # type: ignore
    validate_credentials_file = None  # type: ignore

# Firestore is optional
try:
    from .firestore import (
        FirestoreQueries,
        FirestoreStats,
        FirestoreTransport,
    )

    FIRESTORE_AVAILABLE = True
except ImportError:
    FirestoreTransport = None  # type: ignore
    FirestoreStats = None  # type: ignore
    FirestoreQueries = None  # type: ignore
    FIRESTORE_AVAILABLE = False

# Firebase Auth is optional
try:
    from .firebase_auth import (
        FirebaseAuth,
        FirebaseAuthMiddleware,
        FirebaseUser,
        TokenInfo,
    )

    FIREBASE_AUTH_AVAILABLE = True
except ImportError:
    FirebaseAuth = None  # type: ignore
    FirebaseUser = None  # type: ignore
    TokenInfo = None  # type: ignore
    FirebaseAuthMiddleware = None  # type: ignore
    FIREBASE_AUTH_AVAILABLE = False

# Firebase Cloud Messaging is optional
try:
    from .firebase_messaging import (
        DeviceToken,
        FirebaseMessaging,
        NotificationPayload,
        NotificationPriority,
        NotificationType,
        SendResult,
        send_notification,
        send_topic_notification,
    )

    FCM_AVAILABLE = True
except ImportError:
    FirebaseMessaging = None  # type: ignore
    NotificationPayload = None  # type: ignore
    NotificationPriority = None  # type: ignore
    NotificationType = None  # type: ignore
    DeviceToken = None  # type: ignore
    SendResult = None  # type: ignore
    send_notification = None  # type: ignore
    send_topic_notification = None  # type: ignore
    FCM_AVAILABLE = False

# Firebase Emulator support (always available)
# Unified chat features interface
from .chat_features import ChatFeatures
from .firebase_emulator import (
    EmulatorConfig,
    EmulatorStatus,
    FirebaseEmulator,
    get_emulator,
    is_port_open,
    setup_emulators,
    use_emulators,
)

# Presence and read receipts (always available)
from .firebase_presence import (
    FirebasePresence,
    PresenceManager,
    PresenceStatus,
    TypingIndicator,
    TypingStatus,
    UserPresence,
)
from .firebase_receipts import (
    FirebaseReadReceipts,
    MessageReadInfo,
    MessageStatus,
    ReadReceipt,
    ReadReceiptManager,
)

# WebSocket presence and receipts
from .websocket_presence import WebSocketPresence
from .websocket_receipts import WebSocketReadReceipts

# Transport registry for factory pattern
TRANSPORT_REGISTRY = {
    TransportType.WEBSOCKET: WebSocketTransport,
}

if FIREBASE_AVAILABLE and FirebaseTransport is not None:
    TRANSPORT_REGISTRY[TransportType.FIREBASE] = FirebaseTransport


def get_transport(transport_type: TransportType, config: TransportConfig, **kwargs):
    """Factory function to get transport instance.

    Args:
        transport_type: Type of transport to create
        config: Transport configuration
        **kwargs: Additional transport-specific arguments

    Returns:
        Transport instance

    Raises:
        ValueError: If transport type is not available
    """
    if transport_type not in TRANSPORT_REGISTRY:
        available = list(TRANSPORT_REGISTRY.keys())
        raise ValueError(
            f"Transport {transport_type} not available. "
            f"Available: {available}. "
            f"Install firebase-admin for Firebase support."
        )

    transport_class = TRANSPORT_REGISTRY[transport_type]
    return transport_class(config, **kwargs)


__all__ = [
    # Base classes
    "BaseTransport",
    "TransportConfig",
    "TransportType",
    "TransportMessage",
    # Utilities
    "utc_now",
    # WebSocket
    "WebSocketTransport",
    "WebSocketAuthConfig",
    "WebSocketConnectionState",
    "ReconnectConfig",
    # Firebase Realtime Database
    "FirebaseTransport",
    "ConnectionState",
    "FirebaseStats",
    "OfflineQueue",
    "OfflineMessage",
    "FIREBASE_AVAILABLE",
    # Firebase Firestore
    "FirestoreTransport",
    "FirestoreStats",
    "FirestoreQueries",
    "FIRESTORE_AVAILABLE",
    # Firebase Auth
    "FirebaseAuth",
    "FirebaseUser",
    "TokenInfo",
    "FirebaseAuthMiddleware",
    "FIREBASE_AUTH_AVAILABLE",
    # Firebase Cloud Messaging
    "FirebaseMessaging",
    "NotificationPayload",
    "NotificationPriority",
    "NotificationType",
    "DeviceToken",
    "SendResult",
    "send_notification",
    "send_topic_notification",
    "FCM_AVAILABLE",
    # Firebase Emulator
    "FirebaseEmulator",
    "EmulatorConfig",
    "EmulatorStatus",
    "get_emulator",
    "use_emulators",
    "setup_emulators",
    "is_port_open",
    # Firebase Presence
    "PresenceManager",
    "PresenceStatus",
    "TypingStatus",
    "UserPresence",
    "TypingIndicator",
    "FirebasePresence",
    # Firebase Read Receipts
    "ReadReceiptManager",
    "MessageStatus",
    "ReadReceipt",
    "MessageReadInfo",
    "FirebaseReadReceipts",
    # WebSocket presence and receipts
    "WebSocketPresence",
    "WebSocketReadReceipts",
    # Unified interface
    "ChatFeatures",
    # Firebase config
    "FirebaseConfig",
    "load_firebase_config",
    "validate_credentials_file",
    # Manager
    "TransportManager",
    "TransportMode",
    "TransportStatus",
    # Factory
    "TRANSPORT_REGISTRY",
    "get_transport",
]
