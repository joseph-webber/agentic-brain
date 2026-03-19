"""Tests for the plugin system."""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Optional

from agentic_brain.plugins import Plugin, PluginManager, PluginConfig
from agentic_brain.plugins.builtin.logging import LoggingPlugin
from agentic_brain.plugins.builtin.analytics import AnalyticsPlugin
from agentic_brain.plugins.builtin.moderation import ModerationPlugin


class TestPluginConfig:
    """Tests for PluginConfig."""

    def test_create_config(self):
        """Test creating plugin config."""
        config = PluginConfig(
            name="TestPlugin",
            enabled=True,
            version="1.0.0",
            description="Test plugin",
        )
        assert config.name == "TestPlugin"
        assert config.enabled is True
        assert config.version == "1.0.0"

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "name": "TestPlugin",
            "enabled": True,
            "version": "1.0.0",
            "description": "Test",
        }
        config = PluginConfig.from_dict(data)
        assert config.name == "TestPlugin"
        assert config.enabled is True

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = PluginConfig(name="TestPlugin", enabled=True)
        data = config.to_dict()
        assert data["name"] == "TestPlugin"
        assert data["enabled"] is True


class TestPlugin:
    """Tests for Plugin base class."""

    def test_plugin_init(self):
        """Test plugin initialization."""

        class MyPlugin(Plugin):
            pass

        config = PluginConfig(name="MyPlugin")
        plugin = MyPlugin(config)
        assert plugin.name == "MyPlugin"
        assert plugin.enabled is True
        assert plugin.version == "0.1.0"

    def test_plugin_lifecycle(self):
        """Test plugin lifecycle hooks."""

        class MyPlugin(Plugin):
            def __init__(self, config=None):
                super().__init__(config)
                self.loaded = False
                self.unloaded = False

            def on_load(self):
                self.loaded = True

            def on_unload(self):
                self.unloaded = True

        plugin = MyPlugin()
        assert plugin.loaded is False

        plugin.on_load()
        assert plugin.loaded is True

        plugin.on_unload()
        assert plugin.unloaded is True

    def test_plugin_on_message(self):
        """Test on_message hook."""

        class MyPlugin(Plugin):
            def on_message(self, message: str, **kwargs) -> Optional[str]:
                # Uppercase the message
                return message.upper()

        plugin = MyPlugin()
        result = plugin.on_message("hello")
        assert result == "HELLO"

    def test_plugin_on_response(self):
        """Test on_response hook."""

        class MyPlugin(Plugin):
            def on_response(self, response: str, **kwargs) -> Optional[str]:
                # Add exclamation mark
                return response + "!"

        plugin = MyPlugin()
        result = plugin.on_response("hello")
        assert result == "hello!"

    def test_register_hook(self):
        """Test registering custom hooks."""

        class MyPlugin(Plugin):
            pass

        plugin = MyPlugin()

        called = []

        def handler(*args, **kwargs):
            called.append((args, kwargs))

        plugin.register_hook("custom_event", handler)
        plugin.trigger_hooks("custom_event", "arg1", key="value")

        assert len(called) == 1
        assert called[0] == (("arg1",), {"key": "value"})


class TestPluginManager:
    """Tests for PluginManager."""

    def test_manager_init(self):
        """Test PluginManager initialization."""
        manager = PluginManager()
        assert len(manager.plugins) == 0

    def test_register_plugin(self):
        """Test registering a plugin."""

        class MyPlugin(Plugin):
            pass

        manager = PluginManager()
        plugin = MyPlugin()
        manager.register_plugin(plugin)

        assert "MyPlugin" in manager.plugins
        assert manager.get_plugin("MyPlugin") == plugin

    def test_load_plugin(self):
        """Test loading a plugin."""

        class MyPlugin(Plugin):
            def on_load(self):
                self.loaded = True

        manager = PluginManager()
        plugin = manager.load_plugin(MyPlugin)

        assert plugin is not None
        assert plugin.loaded is True
        assert plugin.name in manager.plugins

    def test_load_plugin_with_config(self):
        """Test loading plugin with custom config."""

        class MyPlugin(Plugin):
            pass

        manager = PluginManager()
        config = PluginConfig(
            name="CustomName",
            config={"setting": "value"},
        )
        plugin = manager.load_plugin(MyPlugin, config)

        assert plugin.config == config
        assert plugin.config.config["setting"] == "value"

    def test_unload_plugin(self):
        """Test unloading a plugin."""

        class MyPlugin(Plugin):
            def on_unload(self):
                self.unloaded = True

        manager = PluginManager()
        plugin = manager.load_plugin(MyPlugin)

        assert "MyPlugin" in manager.plugins

        manager.unload_plugin("MyPlugin")
        assert "MyPlugin" not in manager.plugins
        assert plugin.unloaded is True

    def test_enable_disable_plugin(self):
        """Test enabling/disabling plugins."""

        class MyPlugin(Plugin):
            pass

        manager = PluginManager()
        plugin = manager.load_plugin(MyPlugin)

        assert plugin.enabled is True

        manager.disable_plugin("MyPlugin")
        assert plugin.enabled is False

        manager.enable_plugin("MyPlugin")
        assert plugin.enabled is True

    def test_trigger_lifecycle_hooks(self):
        """Test triggering lifecycle hooks."""

        class MyPlugin(Plugin):
            def __init__(self, config=None):
                super().__init__(config)
                self.on_load_called = False
                self.message = None

            def on_load(self):
                self.on_load_called = True

            def on_message(self, msg, **kwargs):
                self.message = msg
                return None

        manager = PluginManager()
        manager.load_plugin(MyPlugin)

        # Trigger hooks
        manager.trigger("on_message", "test message", session_id="123")
        plugin = manager.get_plugin("MyPlugin")
        assert plugin.message == "test message"

    def test_trigger_with_message_modification(self):
        """Test message modification through plugin chain."""

        class Plugin1(Plugin):
            def on_message(self, message: str, **kwargs) -> Optional[str]:
                return message.upper()

        class Plugin2(Plugin):
            def on_message(self, message: str, **kwargs) -> Optional[str]:
                return message + "!"

        manager = PluginManager()
        manager.load_plugin(Plugin1)
        manager.load_plugin(Plugin2)

        result = manager.trigger("on_message", "hello")
        assert result == "HELLO!"

    def test_trigger_skips_disabled_plugins(self):
        """Test that disabled plugins are skipped."""

        class MyPlugin(Plugin):
            def __init__(self, config=None):
                super().__init__(config)
                self.called = False

            def on_message(self, message: str, **kwargs) -> Optional[str]:
                self.called = True
                return message

        manager = PluginManager()
        manager.load_plugin(MyPlugin)
        manager.disable_plugin("MyPlugin")

        manager.trigger("on_message", "hello")
        plugin = manager.get_plugin("MyPlugin")
        assert plugin.called is False

    def test_list_plugins(self):
        """Test listing plugins."""

        class MyPlugin(Plugin):
            pass

        manager = PluginManager()
        manager.load_plugin(MyPlugin)

        plugins = manager.list_plugins()
        assert "MyPlugin" in plugins
        assert plugins["MyPlugin"]["enabled"] is True

    def test_load_plugins_from_directory(self):
        """Test discovering and loading plugins from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test plugin file
            plugin_code = '''
from agentic_brain.plugins.base import Plugin

class TestPlugin(Plugin):
    def on_load(self):
        self.loaded = True
'''
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text(plugin_code)

            manager = PluginManager()
            loaded = manager.load_plugins(tmpdir)

            assert "TestPlugin" in loaded
            assert loaded["TestPlugin"].loaded is True

    def test_load_plugins_skips_underscored_files(self):
        """Test that plugins starting with _ are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file starting with underscore
            plugin_file = Path(tmpdir) / "_skip_me.py"
            plugin_file.write_text("# This should be skipped")

            manager = PluginManager()
            loaded = manager.load_plugins(tmpdir)

            assert len(loaded) == 0

    def test_get_plugin_config(self):
        """Test getting plugin configuration."""

        class MyPlugin(Plugin):
            pass

        manager = PluginManager()
        config = PluginConfig(name="MyPlugin", config={"key": "value"})
        manager.load_plugin(MyPlugin, config)

        retrieved_config = manager.get_plugin_config("MyPlugin")
        assert retrieved_config.config["key"] == "value"


class TestLoggingPlugin:
    """Tests for LoggingPlugin."""

    def test_logging_plugin_init(self):
        """Test LoggingPlugin initialization."""
        plugin = LoggingPlugin()
        assert plugin.name == "LoggingPlugin"
        assert plugin.log_messages is True
        assert plugin.log_responses is True

    def test_logging_plugin_on_message(self):
        """Test LoggingPlugin on_message."""
        plugin = LoggingPlugin()
        result = plugin.on_message("hello", session_id="123", user_id="user1")
        # Should return None (no modification)
        assert result is None

    def test_logging_plugin_on_response(self):
        """Test LoggingPlugin on_response."""
        plugin = LoggingPlugin()
        result = plugin.on_response("response", session_id="123")
        assert result is None

    def test_logging_plugin_with_config(self):
        """Test LoggingPlugin with custom config."""
        config = PluginConfig(
            name="LoggingPlugin",
            config={"log_level": "DEBUG", "log_messages": False},
        )
        plugin = LoggingPlugin(config)
        assert plugin.log_level == "DEBUG"
        assert plugin.log_messages is False


class TestAnalyticsPlugin:
    """Tests for AnalyticsPlugin."""

    def test_analytics_plugin_init(self):
        """Test AnalyticsPlugin initialization."""
        plugin = AnalyticsPlugin()
        assert plugin.name == "AnalyticsPlugin"
        assert plugin.track_messages is True

    def test_analytics_plugin_track_message(self):
        """Test message tracking."""
        plugin = AnalyticsPlugin()
        plugin.on_message("hello", session_id="123", user_id="user1")

        stats = plugin.get_stats()
        assert stats["message_count"] == 1
        assert stats["unique_sessions"] == 1
        assert stats["unique_users"] == 1

    def test_analytics_plugin_track_response(self):
        """Test response tracking."""
        plugin = AnalyticsPlugin()
        plugin.on_response("response text")

        stats = plugin.get_stats()
        assert stats["response_count"] == 1

    def test_analytics_plugin_avg_length(self):
        """Test average length calculation."""
        plugin = AnalyticsPlugin()
        plugin.on_message("hello")  # 5 chars
        plugin.on_message("world")  # 5 chars

        stats = plugin.get_stats()
        assert stats["message_count"] == 2
        assert stats["avg_message_length"] == 5.0

    def test_analytics_plugin_reset(self):
        """Test resetting statistics."""
        plugin = AnalyticsPlugin()
        plugin.on_message("hello")
        assert plugin.get_stats()["message_count"] == 1

        plugin.reset_stats()
        assert plugin.get_stats()["message_count"] == 0


class TestModerationPlugin:
    """Tests for ModerationPlugin."""

    def test_moderation_plugin_init(self):
        """Test ModerationPlugin initialization."""
        plugin = ModerationPlugin()
        assert plugin.name == "ModerationPlugin"
        assert plugin.action == "log"

    def test_moderation_plugin_keyword_filter(self):
        """Test keyword filtering."""
        config = PluginConfig(
            name="ModerationPlugin",
            config={
                "enabled_filters": ["keyword"],
                "keywords": ["badword"],
                "action": "log",
            },
        )
        plugin = ModerationPlugin(config)

        result = plugin.on_message("this is a badword", user_id="user1")
        # Message passes through, but violation is tracked
        assert "user1" in plugin.get_violations()

    def test_moderation_plugin_pattern_filter(self):
        """Test pattern filtering."""
        config = PluginConfig(
            name="ModerationPlugin",
            config={
                "enabled_filters": ["pattern"],
                "patterns": [r"spam.*spam"],
                "action": "log",
            },
        )
        plugin = ModerationPlugin(config)

        result = plugin.on_message("spam spam spam", user_id="user1")
        assert "user1" in plugin.get_violations()

    def test_moderation_plugin_length_filter(self):
        """Test length filtering."""
        config = PluginConfig(
            name="ModerationPlugin",
            config={
                "enabled_filters": ["length"],
                "max_message_length": 10,
                "action": "log",
            },
        )
        plugin = ModerationPlugin(config)

        result = plugin.on_message("this is a very long message", user_id="user1")
        assert "user1" in plugin.get_violations()

    def test_moderation_plugin_rate_limit(self):
        """Test rate limiting."""
        config = PluginConfig(
            name="ModerationPlugin",
            config={
                "enabled_filters": ["rate_limit"],
                "rate_limit_messages": 2,
                "action": "log",
            },
        )
        plugin = ModerationPlugin(config)

        # First two messages should pass
        plugin.on_message("msg1", user_id="user1")
        plugin.on_message("msg2", user_id="user1")

        # Third message should trigger rate limit
        plugin.on_message("msg3", user_id="user1")
        assert "user1" in plugin.get_violations()

    def test_moderation_plugin_reset_violations(self):
        """Test resetting violations."""
        config = PluginConfig(
            name="ModerationPlugin",
            config={
                "enabled_filters": ["keyword"],
                "keywords": ["badword"],
            },
        )
        plugin = ModerationPlugin(config)

        plugin.on_message("badword", user_id="user1")
        assert "user1" in plugin.get_violations()

        plugin.reset_violations()
        assert len(plugin.get_violations()) == 0


class TestPluginIntegration:
    """Integration tests for plugin system."""

    def test_multiple_plugins_processing_message(self):
        """Test multiple plugins processing the same message."""

        class UppercasePlugin(Plugin):
            def on_message(self, message: str, **kwargs) -> Optional[str]:
                return message.upper()

        class AddExclamation(Plugin):
            def on_message(self, message: str, **kwargs) -> Optional[str]:
                return message + "!"

        manager = PluginManager()
        manager.load_plugin(UppercasePlugin)
        manager.load_plugin(AddExclamation)

        result = manager.trigger("on_message", "hello")
        assert result == "HELLO!"

    def test_plugins_with_built_ins(self):
        """Test using built-in plugins together."""
        manager = PluginManager()
        manager.load_plugin(LoggingPlugin)
        manager.load_plugin(AnalyticsPlugin)
        manager.load_plugin(ModerationPlugin)

        # Trigger messages
        manager.trigger("on_message", "hello", session_id="123", user_id="user1")
        manager.trigger("on_response", "response", session_id="123")

        # Check that all plugins are loaded
        assert len(manager.plugins) == 3

        # Check analytics
        analytics = manager.get_plugin("AnalyticsPlugin")
        stats = analytics.get_stats()
        assert stats["message_count"] == 1
        assert stats["response_count"] == 1

    def test_unload_all_plugins(self):
        """Test unloading all plugins."""

        class MyPlugin1(Plugin):
            pass

        class MyPlugin2(Plugin):
            pass

        manager = PluginManager()
        manager.load_plugin(MyPlugin1)
        manager.load_plugin(MyPlugin2)

        assert len(manager.plugins) == 2

        manager.unload_all_plugins()
        assert len(manager.plugins) == 0

    def test_error_handling_in_plugin_hooks(self):
        """Test that errors in plugins don't break the chain."""

        class BrokenPlugin(Plugin):
            def on_message(self, message: str, **kwargs) -> Optional[str]:
                raise ValueError("Plugin error")

        class WorkingPlugin(Plugin):
            def on_message(self, message: str, **kwargs) -> Optional[str]:
                return message.upper()

        manager = PluginManager()
        manager.load_plugin(BrokenPlugin)
        manager.load_plugin(WorkingPlugin)

        # This should not raise, just log the error
        result = manager.trigger("on_message", "hello")
        # WorkingPlugin should still work
        assert result == "HELLO"
