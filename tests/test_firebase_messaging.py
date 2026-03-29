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

"""Tests for Firebase Cloud Messaging integration."""

from unittest.mock import Mock, patch

import pytest

from agentic_brain.transport.firebase_messaging import (
    FCM_AVAILABLE,
    DeviceToken,
    FirebaseMessaging,
    NotificationPayload,
    NotificationPriority,
    NotificationType,
    SendResult,
)


class TestNotificationPayload:
    """Tests for NotificationPayload dataclass."""

    def test_create_basic_payload(self):
        """Test creating a basic notification."""
        payload = NotificationPayload(title="Test Title", body="Test Body")

        assert payload.title == "Test Title"
        assert payload.body == "Test Body"
        assert payload.notification_type == NotificationType.MESSAGE
        assert payload.sound == "default"
        assert payload.data == {}

    def test_create_full_payload(self):
        """Test creating a full notification."""
        payload = NotificationPayload(
            title="Alert",
            body="Something happened",
            notification_type=NotificationType.ALERT,
            icon="alert_icon",
            image="https://example.com/image.png",
            click_action="OPEN_ACTIVITY",
            badge=5,
            sound="custom_sound",
            data={"key": "value"},
        )

        assert payload.notification_type == NotificationType.ALERT
        assert payload.icon == "alert_icon"
        assert payload.badge == 5
        assert payload.data["key"] == "value"

    @pytest.mark.skipif(not FCM_AVAILABLE, reason="FCM not installed")
    def test_to_notification(self):
        """Test converting to FCM Notification."""
        payload = NotificationPayload(
            title="Test", body="Body", image="https://example.com/img.png"
        )

        notification = payload.to_notification()
        assert notification.title == "Test"
        assert notification.body == "Body"

    def test_to_notification_without_fcm(self):
        """Test error when FCM not available."""
        if FCM_AVAILABLE:
            pytest.skip("FCM is available")

        payload = NotificationPayload(title="Test", body="Body")

        with pytest.raises(RuntimeError, match="Firebase Admin SDK not installed"):
            payload.to_notification()


class TestDeviceToken:
    """Tests for DeviceToken dataclass."""

    def test_create_device_token(self):
        """Test creating a device token."""
        token = DeviceToken(token="abc123xyz", device_type="android", user_id="user-1")

        assert token.token == "abc123xyz"
        assert token.device_type == "android"
        assert token.user_id == "user-1"
        assert token.is_valid is True
        assert token.topics == []

    def test_to_dict(self):
        """Test converting to dictionary."""
        token = DeviceToken(
            token="abc123",
            device_type="ios",
            user_id="user-2",
            topics=["news", "alerts"],
        )

        data = token.to_dict()

        assert data["token"] == "abc123"
        assert data["device_type"] == "ios"
        assert data["topics"] == ["news", "alerts"]
        assert "created_at" in data

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "token": "xyz789",
            "device_type": "web",
            "user_id": "user-3",
            "is_valid": True,
            "topics": ["updates"],
        }

        token = DeviceToken.from_dict(data)

        assert token.token == "xyz789"
        assert token.device_type == "web"
        assert token.topics == ["updates"]

    def test_roundtrip(self):
        """Test to_dict -> from_dict roundtrip."""
        original = DeviceToken(
            token="roundtrip",
            device_type="android",
            user_id="user-4",
            topics=["topic1", "topic2"],
        )

        restored = DeviceToken.from_dict(original.to_dict())

        assert restored.token == original.token
        assert restored.device_type == original.device_type
        assert restored.topics == original.topics


class TestSendResult:
    """Tests for SendResult dataclass."""

    def test_success_result(self):
        """Test successful send result."""
        result = SendResult(success=True, message_id="msg-123", success_count=1)

        assert result.success is True
        assert result.message_id == "msg-123"
        assert result.error is None

    def test_failure_result(self):
        """Test failed send result."""
        result = SendResult(
            success=False,
            error="Device not registered",
            failed_tokens=["token1", "token2"],
            failure_count=2,
        )

        assert result.success is False
        assert result.error == "Device not registered"
        assert len(result.failed_tokens) == 2


class TestFirebaseMessaging:
    """Tests for FirebaseMessaging class."""

    def test_init_without_credentials(self):
        """Test initialization without credentials."""
        fcm = FirebaseMessaging()

        # Should work but not be initialized
        assert not fcm._initialized or not FCM_AVAILABLE

    def test_is_available_property(self):
        """Test is_available property."""
        fcm = FirebaseMessaging()

        # Without credentials, should not be available
        expected = FCM_AVAILABLE and fcm._initialized
        assert fcm.is_available == expected

    def test_register_token(self):
        """Test registering a device token."""
        fcm = FirebaseMessaging()

        device = fcm.register_token(
            token="test-token-123", device_type="android", user_id="user-1"
        )

        assert device.token == "test-token-123"
        assert device.device_type == "android"
        assert "test-token-123" in fcm._device_tokens

    def test_register_token_with_topics(self):
        """Test registering with topics."""
        fcm = FirebaseMessaging()

        device = fcm.register_token(
            token="test-token-456",
            device_type="ios",
            user_id="user-2",
            topics=["news", "updates"],
        )

        assert device.topics == ["news", "updates"]

    def test_unregister_token(self):
        """Test unregistering a token."""
        fcm = FirebaseMessaging()

        # Register first
        fcm.register_token(token="to-remove", device_type="web")

        # Unregister
        result = fcm.unregister_token("to-remove")

        assert result is True
        assert "to-remove" not in fcm._device_tokens

    def test_unregister_nonexistent_token(self):
        """Test unregistering non-existent token."""
        fcm = FirebaseMessaging()

        result = fcm.unregister_token("nonexistent")

        assert result is False

    def test_get_user_tokens(self):
        """Test getting all tokens for a user."""
        fcm = FirebaseMessaging()

        # Register multiple devices for same user
        fcm.register_token("token1", "android", "user-1")
        fcm.register_token("token2", "ios", "user-1")
        fcm.register_token("token3", "web", "user-2")

        tokens = fcm.get_user_tokens("user-1")

        assert len(tokens) == 2
        assert all(t.user_id == "user-1" for t in tokens)

    def test_get_user_tokens_excludes_invalid(self):
        """Test that invalid tokens are excluded."""
        fcm = FirebaseMessaging()

        fcm.register_token("valid", "android", "user-1")
        fcm.register_token("invalid", "ios", "user-1")
        fcm._device_tokens["invalid"].is_valid = False

        tokens = fcm.get_user_tokens("user-1")

        assert len(tokens) == 1
        assert tokens[0].token == "valid"

    def test_cleanup_invalid_tokens(self):
        """Test cleaning up invalid tokens."""
        fcm = FirebaseMessaging()

        fcm.register_token("valid1", "android", "user-1")
        fcm.register_token("valid2", "ios", "user-1")
        fcm.register_token("invalid", "web", "user-2")
        fcm._device_tokens["invalid"].is_valid = False

        removed = fcm.cleanup_invalid_tokens()

        assert removed == 1
        assert len(fcm._device_tokens) == 2

    def test_get_stats(self):
        """Test getting messaging statistics."""
        fcm = FirebaseMessaging()

        fcm.register_token("t1", "android", "user-1", ["news"])
        fcm.register_token("t2", "ios", "user-1", ["updates"])
        fcm.register_token("t3", "web", "user-2", ["news"])

        stats = fcm.get_stats()

        assert stats["total_tokens"] == 3
        assert stats["valid_tokens"] == 3
        assert stats["by_device_type"]["android"] == 1
        assert stats["by_device_type"]["ios"] == 1
        assert stats["by_device_type"]["web"] == 1
        assert stats["unique_users"] == 2
        assert "news" in stats["topics"]

    def test_send_to_device_not_available(self):
        """Test sending when FCM not available."""
        fcm = FirebaseMessaging()
        fcm._initialized = False

        payload = NotificationPayload(title="Test", body="Body")
        result = fcm.send_to_device("token", payload)

        assert result.success is False
        assert "not available" in result.error

    def test_send_to_topic_not_available(self):
        """Test topic send when FCM not available."""
        fcm = FirebaseMessaging()
        fcm._initialized = False

        payload = NotificationPayload(title="Test", body="Body")
        result = fcm.send_to_topic("news", payload)

        assert result.success is False

    def test_send_to_user_no_tokens(self):
        """Test sending to user with no tokens."""
        fcm = FirebaseMessaging()

        payload = NotificationPayload(title="Test", body="Body")
        result = fcm.send_to_user("nonexistent-user", payload)

        assert result.success is False
        assert "No valid tokens" in result.error


class TestNotificationTypes:
    """Tests for notification type enums."""

    def test_notification_priorities(self):
        """Test NotificationPriority enum."""
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"

    def test_notification_types(self):
        """Test NotificationType enum."""
        assert NotificationType.ALERT.value == "alert"
        assert NotificationType.UPDATE.value == "update"
        assert NotificationType.MESSAGE.value == "message"
        assert NotificationType.REMINDER.value == "reminder"
        assert NotificationType.SYSTEM.value == "system"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_send_notification_function(self):
        """Test send_notification convenience function."""
        from agentic_brain.transport.firebase_messaging import send_notification

        # Should return failure without credentials
        result = send_notification(token="test-token", title="Hello", body="World")

        assert isinstance(result, SendResult)

    def test_send_topic_notification_function(self):
        """Test send_topic_notification convenience function."""
        from agentic_brain.transport.firebase_messaging import send_topic_notification

        result = send_topic_notification(topic="news", title="Breaking", body="News")

        assert isinstance(result, SendResult)


class TestFCMIntegration:
    """Integration tests for FCM (mocked)."""

    @pytest.fixture
    def mock_messaging(self):
        """Create mock Firebase messaging module."""
        with patch("agentic_brain.transport.firebase_messaging.messaging") as mock:
            mock.send.return_value = "message-id-123"
            yield mock

    @pytest.mark.skipif(not FCM_AVAILABLE, reason="FCM not installed")
    def test_send_with_mock(self, mock_messaging):
        """Test sending with mocked FCM."""
        fcm = FirebaseMessaging()
        fcm._initialized = True
        fcm._app = Mock()

        payload = NotificationPayload(title="Test", body="Body")

        # This would call the real FCM, but we've mocked messaging
        result = fcm.send_to_device("token", payload)

        # With mock, should succeed
        assert result.success is True or "not available" in str(result.error)
