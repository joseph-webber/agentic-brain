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
Firebase Cloud Messaging (FCM) support for push notifications.

This module provides:
- FCM integration for sending push notifications
- Topic messaging for broadcast notifications
- Device token management
- Message templating and scheduling
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .utils import utc_now as _utc_now

logger = logging.getLogger(__name__)

# Optional FCM import
try:
    import firebase_admin
    from firebase_admin import credentials, get_app, initialize_app, messaging

    FCM_AVAILABLE = True
except ImportError:
    FCM_AVAILABLE = False
    firebase_admin = None  # type: ignore[assignment]
    credentials = None  # type: ignore[assignment]
    get_app = None  # type: ignore[assignment]
    initialize_app = None  # type: ignore[assignment]
    messaging = None  # type: ignore[assignment]


class NotificationPriority(Enum):
    """FCM message priority levels."""

    NORMAL = "normal"
    HIGH = "high"


class NotificationType(Enum):
    """Types of notifications."""

    ALERT = "alert"  # Important alerts
    UPDATE = "update"  # Status updates
    MESSAGE = "message"  # Chat messages
    REMINDER = "reminder"  # Scheduled reminders
    SYSTEM = "system"  # System notifications


@dataclass
class NotificationPayload:
    """Notification message payload."""

    title: str
    body: str
    notification_type: NotificationType = NotificationType.MESSAGE
    icon: Optional[str] = None
    image: Optional[str] = None
    click_action: Optional[str] = None
    badge: Optional[int] = None
    sound: str = "default"
    data: dict[str, str] = field(default_factory=dict)

    def to_notification(self) -> "messaging.Notification":
        """Convert to FCM Notification object."""
        if not FCM_AVAILABLE:
            raise RuntimeError("Firebase Admin SDK not installed")

        return messaging.Notification(
            title=self.title, body=self.body, image=self.image
        )

    def to_android_config(
        self, priority: NotificationPriority = NotificationPriority.HIGH
    ) -> "messaging.AndroidConfig":
        """Generate Android-specific config."""
        if not FCM_AVAILABLE:
            raise RuntimeError("Firebase Admin SDK not installed")

        return messaging.AndroidConfig(
            priority=priority.value,
            notification=messaging.AndroidNotification(
                icon=self.icon, sound=self.sound, click_action=self.click_action
            ),
        )

    def to_apns_config(self) -> "messaging.APNSConfig":
        """Generate iOS-specific config."""
        if not FCM_AVAILABLE:
            raise RuntimeError("Firebase Admin SDK not installed")

        return messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(badge=self.badge, sound=self.sound)
            )
        )

    def to_web_config(self) -> "messaging.WebpushConfig":
        """Generate web push config."""
        if not FCM_AVAILABLE:
            raise RuntimeError("Firebase Admin SDK not installed")

        return messaging.WebpushConfig(
            notification=messaging.WebpushNotification(
                title=self.title, body=self.body, icon=self.icon
            )
        )


@dataclass
class DeviceToken:
    """Device token for FCM."""

    token: str
    device_type: str  # android, ios, web
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=_utc_now)
    last_used: datetime = field(default_factory=_utc_now)
    is_valid: bool = True
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "token": self.token,
            "device_type": self.device_type,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "is_valid": self.is_valid,
            "topics": self.topics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceToken":
        """Create from dictionary."""
        return cls(
            token=data["token"],
            device_type=data["device_type"],
            user_id=data.get("user_id"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else _utc_now()
            ),
            last_used=(
                datetime.fromisoformat(data["last_used"])
                if "last_used" in data
                else _utc_now()
            ),
            is_valid=data.get("is_valid", True),
            topics=data.get("topics", []),
        )


@dataclass
class SendResult:
    """Result of sending a notification."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    failed_tokens: list[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0


class FirebaseMessaging:
    """
    Firebase Cloud Messaging integration.

    Provides methods for:
    - Sending to individual devices
    - Sending to topics
    - Managing device tokens
    - Batch notifications

    Usage:
        fcm = FirebaseMessaging(credentials_path="service-account.json")

        # Send to device
        result = fcm.send_to_device(
            token="device_token",
            payload=NotificationPayload(
                title="Hello",
                body="World"
            )
        )

        # Send to topic
        result = fcm.send_to_topic(
            topic="news",
            payload=NotificationPayload(title="Breaking News", body="...")
        )
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
        app_name: str = "agentic-brain-fcm",
    ):
        """
        Initialize FCM client.

        Args:
            credentials_path: Path to service account JSON
            project_id: Firebase project ID
            app_name: Name for Firebase app instance
        """
        self._app = None
        self._app_name = app_name
        self._initialized = False
        self._device_tokens: dict[str, DeviceToken] = {}

        if not FCM_AVAILABLE:
            logger.warning("Firebase Admin SDK not installed. FCM features disabled.")
            return

        try:
            # Try to get existing app
            self._app = get_app(app_name)
            self._initialized = True
        except ValueError:
            # Initialize new app
            if credentials_path:
                cred = credentials.Certificate(credentials_path)
                self._app = initialize_app(cred, name=app_name)
                self._initialized = True
            else:
                logger.warning("No credentials provided. FCM will not work.")

    @property
    def is_available(self) -> bool:
        """Check if FCM is available and initialized."""
        return FCM_AVAILABLE and self._initialized

    def register_token(
        self,
        token: str,
        device_type: str = "web",
        user_id: Optional[str] = None,
        topics: Optional[list[str]] = None,
    ) -> DeviceToken:
        """
        Register a device token.

        Args:
            token: FCM device token
            device_type: Type of device (android, ios, web)
            user_id: Optional user ID association
            topics: Topics to subscribe to

        Returns:
            DeviceToken instance
        """
        device = DeviceToken(
            token=token, device_type=device_type, user_id=user_id, topics=topics or []
        )

        self._device_tokens[token] = device

        # Subscribe to topics
        if topics and self.is_available:
            for topic in topics:
                self.subscribe_to_topic(token, topic)

        logger.info(f"Registered device token: {token[:20]}... for user {user_id}")
        return device

    def unregister_token(self, token: str) -> bool:
        """
        Unregister a device token.

        Args:
            token: Token to unregister

        Returns:
            True if unregistered
        """
        if token in self._device_tokens:
            device = self._device_tokens[token]

            # Unsubscribe from topics
            if self.is_available:
                for topic in device.topics:
                    self.unsubscribe_from_topic(token, topic)

            del self._device_tokens[token]
            logger.info(f"Unregistered device token: {token[:20]}...")
            return True
        return False

    def get_user_tokens(self, user_id: str) -> list[DeviceToken]:
        """Get all tokens for a user."""
        return [
            device
            for device in self._device_tokens.values()
            if device.user_id == user_id and device.is_valid
        ]

    def send_to_device(
        self,
        token: str,
        payload: NotificationPayload,
        priority: NotificationPriority = NotificationPriority.HIGH,
        dry_run: bool = False,
    ) -> SendResult:
        """
        Send notification to a specific device.

        Args:
            token: Device FCM token
            payload: Notification payload
            priority: Message priority
            dry_run: If True, validate without sending

        Returns:
            SendResult with outcome
        """
        if not self.is_available:
            return SendResult(success=False, error="FCM not available")

        try:
            message = messaging.Message(
                notification=payload.to_notification(),
                android=payload.to_android_config(priority),
                apns=payload.to_apns_config(),
                webpush=payload.to_web_config(),
                data=payload.data,
                token=token,
            )

            response = messaging.send(message, dry_run=dry_run, app=self._app)

            # Update last used
            if token in self._device_tokens:
                self._device_tokens[token].last_used = _utc_now()

            logger.info(f"Sent notification to device: {token[:20]}...")
            return SendResult(success=True, message_id=response, success_count=1)

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

            # Mark token as invalid if it's unregistered
            if "not registered" in str(e).lower():
                if token in self._device_tokens:
                    self._device_tokens[token].is_valid = False

            return SendResult(
                success=False, error=str(e), failed_tokens=[token], failure_count=1
            )

    def send_to_user(
        self,
        user_id: str,
        payload: NotificationPayload,
        priority: NotificationPriority = NotificationPriority.HIGH,
    ) -> SendResult:
        """
        Send notification to all devices of a user.

        Args:
            user_id: User ID
            payload: Notification payload
            priority: Message priority

        Returns:
            Combined SendResult
        """
        tokens = self.get_user_tokens(user_id)

        if not tokens:
            return SendResult(
                success=False, error=f"No valid tokens for user {user_id}"
            )

        # Send to all user devices
        success_count = 0
        failure_count = 0
        failed_tokens = []

        for device in tokens:
            result = self.send_to_device(device.token, payload, priority)
            if result.success:
                success_count += 1
            else:
                failure_count += 1
                failed_tokens.append(device.token)

        return SendResult(
            success=success_count > 0,
            success_count=success_count,
            failure_count=failure_count,
            failed_tokens=failed_tokens,
        )

    def send_to_topic(
        self,
        topic: str,
        payload: NotificationPayload,
        priority: NotificationPriority = NotificationPriority.HIGH,
        condition: Optional[str] = None,
    ) -> SendResult:
        """
        Send notification to a topic.

        Args:
            topic: Topic name
            payload: Notification payload
            priority: Message priority
            condition: Optional condition expression

        Returns:
            SendResult
        """
        if not self.is_available:
            return SendResult(success=False, error="FCM not available")

        try:
            message_kwargs = {
                "notification": payload.to_notification(),
                "android": payload.to_android_config(priority),
                "apns": payload.to_apns_config(),
                "webpush": payload.to_web_config(),
                "data": payload.data,
            }

            if condition:
                message_kwargs["condition"] = condition
            else:
                message_kwargs["topic"] = topic

            message = messaging.Message(**message_kwargs)
            response = messaging.send(message, app=self._app)

            logger.info(f"Sent notification to topic: {topic}")
            return SendResult(success=True, message_id=response)

        except Exception as e:
            logger.error(f"Failed to send to topic: {e}")
            return SendResult(success=False, error=str(e))

    def send_multicast(
        self,
        tokens: list[str],
        payload: NotificationPayload,
        priority: NotificationPriority = NotificationPriority.HIGH,
    ) -> SendResult:
        """
        Send notification to multiple devices efficiently.

        Args:
            tokens: List of device tokens (max 500)
            payload: Notification payload
            priority: Message priority

        Returns:
            SendResult with batch results
        """
        if not self.is_available:
            return SendResult(success=False, error="FCM not available")

        if len(tokens) > 500:
            # FCM limit is 500 per multicast
            logger.warning("Token list exceeds 500, truncating")
            tokens = tokens[:500]

        try:
            message = messaging.MulticastMessage(
                notification=payload.to_notification(),
                android=payload.to_android_config(priority),
                apns=payload.to_apns_config(),
                webpush=payload.to_web_config(),
                data=payload.data,
                tokens=tokens,
            )

            response = messaging.send_each_for_multicast(message, app=self._app)

            # Process results
            failed_tokens = []
            for idx, result in enumerate(response.responses):
                if not result.success:
                    failed_tokens.append(tokens[idx])
                    # Mark invalid tokens
                    if tokens[idx] in self._device_tokens:
                        if "not registered" in str(result.exception).lower():
                            self._device_tokens[tokens[idx]].is_valid = False

            logger.info(
                f"Multicast sent: {response.success_count} success, "
                f"{response.failure_count} failed"
            )

            return SendResult(
                success=response.success_count > 0,
                success_count=response.success_count,
                failure_count=response.failure_count,
                failed_tokens=failed_tokens,
            )

        except Exception as e:
            logger.error(f"Failed multicast send: {e}")
            return SendResult(
                success=False,
                error=str(e),
                failed_tokens=tokens,
                failure_count=len(tokens),
            )

    def subscribe_to_topic(self, token: str, topic: str) -> bool:
        """
        Subscribe a device to a topic.

        Args:
            token: Device token
            topic: Topic name

        Returns:
            True if subscribed
        """
        if not self.is_available:
            return False

        try:
            response = messaging.subscribe_to_topic([token], topic, app=self._app)

            if response.success_count > 0:
                if token in self._device_tokens:
                    if topic not in self._device_tokens[token].topics:
                        self._device_tokens[token].topics.append(topic)
                logger.info(f"Subscribed {token[:20]}... to topic: {topic}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to subscribe to topic: {e}")
            return False

    def unsubscribe_from_topic(self, token: str, topic: str) -> bool:
        """
        Unsubscribe a device from a topic.

        Args:
            token: Device token
            topic: Topic name

        Returns:
            True if unsubscribed
        """
        if not self.is_available:
            return False

        try:
            response = messaging.unsubscribe_from_topic([token], topic, app=self._app)

            if response.success_count > 0:
                if token in self._device_tokens:
                    if topic in self._device_tokens[token].topics:
                        self._device_tokens[token].topics.remove(topic)
                logger.info(f"Unsubscribed {token[:20]}... from topic: {topic}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to unsubscribe from topic: {e}")
            return False

    def cleanup_invalid_tokens(self) -> int:
        """
        Remove all invalid tokens.

        Returns:
            Number of tokens removed
        """
        invalid = [
            token
            for token, device in self._device_tokens.items()
            if not device.is_valid
        ]

        for token in invalid:
            del self._device_tokens[token]

        logger.info(f"Cleaned up {len(invalid)} invalid tokens")
        return len(invalid)

    def get_stats(self) -> dict[str, Any]:
        """Get messaging statistics."""
        devices = list(self._device_tokens.values())

        return {
            "available": self.is_available,
            "total_tokens": len(devices),
            "valid_tokens": sum(1 for d in devices if d.is_valid),
            "invalid_tokens": sum(1 for d in devices if not d.is_valid),
            "by_device_type": {
                "android": sum(1 for d in devices if d.device_type == "android"),
                "ios": sum(1 for d in devices if d.device_type == "ios"),
                "web": sum(1 for d in devices if d.device_type == "web"),
            },
            "unique_users": len({d.user_id for d in devices if d.user_id}),
            "topics": list({t for d in devices for t in d.topics}),
        }


# Convenience functions
def send_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
    credentials_path: Optional[str] = None,
) -> SendResult:
    """
    Quick send a notification.

    Args:
        token: Device token
        title: Notification title
        body: Notification body
        data: Optional data payload
        credentials_path: Firebase credentials

    Returns:
        SendResult
    """
    fcm = FirebaseMessaging(credentials_path=credentials_path)
    payload = NotificationPayload(title=title, body=body, data=data or {})
    return fcm.send_to_device(token, payload)


def send_topic_notification(
    topic: str,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
    credentials_path: Optional[str] = None,
) -> SendResult:
    """
    Quick send to a topic.

    Args:
        topic: Topic name
        title: Notification title
        body: Notification body
        data: Optional data payload
        credentials_path: Firebase credentials

    Returns:
        SendResult
    """
    fcm = FirebaseMessaging(credentials_path=credentials_path)
    payload = NotificationPayload(title=title, body=body, data=data or {})
    return fcm.send_to_topic(topic, payload)
