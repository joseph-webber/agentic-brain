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

"""Tests for hooks module."""

from datetime import UTC, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestHooksManager:
    def test_hooks_manager_exists(self):
        """Test HooksManager can be imported."""
        from agentic_brain.hooks import HooksManager

        assert HooksManager is not None

    def test_hooks_manager_creation(self):
        """Test HooksManager can be instantiated."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))
        assert manager is not None

    def test_register_hook(self):
        """Test registering a hook."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_message", callback)
        # Should not raise

    def test_fire_hook(self):
        """Test firing a hook calls callback."""
        from agentic_brain.hooks import HookContext, HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_message", callback)
        manager.fire("on_message", data={"key": "value"})

        callback.assert_called_once()
        # Verify the callback was called with HookContext
        call_args = callback.call_args
        assert call_args is not None
        context = call_args[0][0]
        assert isinstance(context, HookContext)
        assert context.event_type == "on_message"
        assert context.data == {"key": "value"}

    def test_fire_nonexistent_hook(self):
        """Test firing non-existent hook doesn't raise."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))
        # Should not raise
        manager.fire("nonexistent_event")

    def test_unregister_hook(self):
        """Test unregistering a hook."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_message", callback)
        manager.unregister("on_message", callback)
        manager.fire("on_message")

        callback.assert_not_called()

    def test_multiple_handlers_for_same_event(self):
        """Test multiple handlers can be registered for same event."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback1 = MagicMock(__name__="callback1")
        callback2 = MagicMock(__name__="callback2")
        manager.register("on_message", callback1)
        manager.register("on_message", callback2)
        manager.fire("on_message")

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_get_handlers(self):
        """Test getting list of handlers for event."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback1 = MagicMock(__name__="callback1")
        callback2 = MagicMock(__name__="callback2")
        manager.register("on_message", callback1)
        manager.register("on_message", callback2)

        handlers = manager.get_handlers("on_message")
        assert len(handlers) == 2

    def test_clear_specific_handlers(self):
        """Test clearing handlers for specific event."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_message", callback)
        manager.clear_handlers("on_message")
        manager.fire("on_message")

        callback.assert_not_called()

    def test_clear_all_handlers(self):
        """Test clearing all handlers."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback1 = MagicMock(__name__="callback1")
        callback2 = MagicMock(__name__="callback2")
        manager.register("on_message", callback1)
        manager.register("on_session_start", callback2)
        manager.clear_handlers()

        manager.fire("on_message")
        manager.fire("on_session_start")

        callback1.assert_not_called()
        callback2.assert_not_called()


class TestHookContext:
    def test_hook_context_exists(self):
        """Test HookContext can be imported."""
        from agentic_brain.hooks import HookContext

        assert HookContext is not None

    def test_hook_context_creation(self):
        """Test HookContext can be created."""
        from agentic_brain.hooks import HookContext

        now = datetime.now(UTC)
        context = HookContext(
            event_type="test_event",
            timestamp=now,
            data={"key": "value"},
        )
        assert context.event_type == "test_event"
        assert context.timestamp == now
        assert context.data == {"key": "value"}

    def test_hook_context_to_dict(self):
        """Test converting HookContext to dictionary."""
        from agentic_brain.hooks import HookContext

        now = datetime.now(UTC)
        context = HookContext(
            event_type="test_event",
            timestamp=now,
            data={"key": "value"},
        )
        result = context.to_dict()
        assert result["event_type"] == "test_event"
        assert result["timestamp"] == now.isoformat()
        assert result["data"] == {"key": "value"}


class TestBuiltInHooks:
    def test_on_session_start_hook(self):
        """Test on_session_start hook."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_session_start", callback)
        manager.on_session_start("session-123", user_id="user-456")

        callback.assert_called_once()
        context = callback.call_args[0][0]
        assert context.event_type == "on_session_start"
        assert context.data["session_id"] == "session-123"
        assert context.data["user_id"] == "user-456"

    def test_on_session_end_hook(self):
        """Test on_session_end hook."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_session_end", callback)
        manager.on_session_end("session-123", duration=100)

        callback.assert_called_once()
        context = callback.call_args[0][0]
        assert context.event_type == "on_session_end"
        assert context.data["session_id"] == "session-123"
        assert context.data["duration"] == 100

    def test_on_message_hook(self):
        """Test on_message hook."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_message", callback)
        manager.on_message("session-123", "Hello, world!", role="user")

        callback.assert_called_once()
        context = callback.call_args[0][0]
        assert context.event_type == "on_message"
        assert context.data["session_id"] == "session-123"
        assert context.data["message"] == "Hello, world!"
        assert context.data["role"] == "user"

    def test_on_response_hook(self):
        """Test on_response hook."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_response", callback)
        manager.on_response("session-123", "Response content", model="gpt-4")

        callback.assert_called_once()
        context = callback.call_args[0][0]
        assert context.event_type == "on_response"
        assert context.data["session_id"] == "session-123"
        assert context.data["response"] == "Response content"
        assert context.data["model"] == "gpt-4"

    def test_on_error_hook(self):
        """Test on_error hook."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("on_error", callback)
        error = ValueError("Test error")
        manager.on_error("session-123", error, context="test context")

        callback.assert_called_once()
        context = callback.call_args[0][0]
        assert context.event_type == "on_error"
        assert context.data["session_id"] == "session-123"
        assert "Test error" in context.data["error"]
        assert context.data["error_type"] == "ValueError"
        assert context.data["context"] == "test context"


class TestHooksManagerSettings:
    def test_get_setting(self):
        """Test getting a setting value."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        value = manager.get_setting("timezone")
        assert value == "UTC"

    def test_get_setting_with_default(self):
        """Test getting a setting with default value."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        value = manager.get_setting("nonexistent_key", "default_value")
        assert value == "default_value"

    def test_set_setting(self):
        """Test setting a value."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        manager.set_setting("custom_key", "custom_value")
        value = manager.get_setting("custom_key")
        assert value == "custom_value"

    def test_built_in_settings(self):
        """Test built-in settings exist."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        assert manager.get_setting("timezone") is not None
        assert manager.get_setting("capture_tools") is not None


class TestHandlerErrors:
    def test_handler_exception_logged_not_raised(self):
        """Test that handler exceptions are logged but not raised."""
        from agentic_brain.hooks import HooksManager

        def failing_handler(context):
            raise RuntimeError("Handler failed")

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))
        manager.register("on_message", failing_handler)

        # Should not raise
        manager.fire("on_message")

    def test_register_non_callable_raises(self):
        """Test that registering non-callable raises ValueError."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        with pytest.raises(ValueError):
            manager.register("on_message", "not_callable")

    def test_custom_hook_registration(self):
        """Test registering custom hook events."""
        from agentic_brain.hooks import HooksManager

        manager = HooksManager(config_path=Path("/nonexistent/hooks.json"))

        callback = MagicMock(__name__="test_callback")
        manager.register("custom_event", callback)
        manager.fire("custom_event", data={"custom": "data"})

        callback.assert_called_once()
        context = callback.call_args[0][0]
        assert context.event_type == "custom_event"
        assert context.data == {"custom": "data"}
