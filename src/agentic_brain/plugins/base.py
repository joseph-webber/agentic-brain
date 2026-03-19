"""
Base plugin system and plugin manager
======================================

Provides the core plugin architecture for extending Agentic Brain functionality.
"""

import importlib
import inspect
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
import yaml

logger = logging.getLogger(__name__)


@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    name: str
    enabled: bool = True
    version: str = "0.1.0"
    description: str = ""
    config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginConfig":
        """Create config from dictionary."""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


class Plugin(ABC):
    """
    Base class for all plugins.

    Subclass this to create custom plugins. Implement lifecycle hooks:
    - on_load: Called when plugin is loaded
    - on_unload: Called when plugin is unloaded
    - on_message: Called when a message is received
    - on_response: Called when a response is generated

    Example:
        >>> class MyPlugin(Plugin):
        ...     def on_load(self):
        ...         print("Loading MyPlugin")
        ...
        ...     def on_message(self, message: str, **kwargs) -> Optional[str]:
        ...         # Process message, optionally return modified message
        ...         return message
    """

    def __init__(self, config: Optional[PluginConfig] = None) -> None:
        """
        Initialize plugin.

        Args:
            config: Optional plugin configuration
        """
        self.config = config or PluginConfig(name=self.__class__.__name__)
        self.enabled = self.config.enabled
        self._hooks: Dict[str, List[Callable]] = {
            "on_load": [],
            "on_unload": [],
            "on_message": [],
            "on_response": [],
        }

    @property
    def name(self) -> str:
        """Get plugin name."""
        return self.config.name

    @property
    def version(self) -> str:
        """Get plugin version."""
        return self.config.version

    def on_load(self) -> None:
        """Called when plugin is loaded. Override to initialize plugin."""
        pass

    def on_unload(self) -> None:
        """Called when plugin is unloaded. Override to cleanup resources."""
        pass

    def on_message(self, message: str, **kwargs) -> Optional[str]:
        """
        Called when a message is received.

        Args:
            message: The message text
            **kwargs: Additional context (session_id, user_id, etc.)

        Returns:
            Modified message or None to pass through unchanged
        """
        return None

    def on_response(self, response: str, **kwargs) -> Optional[str]:
        """
        Called when a response is generated.

        Args:
            response: The response text
            **kwargs: Additional context (session_id, message, etc.)

        Returns:
            Modified response or None to pass through unchanged
        """
        return None

    def register_hook(self, event: str, handler: Callable) -> None:
        """
        Register a custom hook handler.

        Args:
            event: Event name
            handler: Callable to handle event
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)

    def trigger_hooks(self, event: str, *args, **kwargs) -> None:
        """Trigger all registered hooks for an event."""
        if event in self._hooks:
            for handler in self._hooks[event]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in {self.name} hook {event}: {e}", exc_info=True)


class PluginManager:
    """
    Manages plugin lifecycle and coordination.

    Responsibilities:
    - Load/unload plugins from files or packages
    - Trigger lifecycle hooks
    - Handle plugin configuration
    - Plugin discovery from directories
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize plugin manager.

        Args:
            config_path: Optional path to plugins.yaml config file
        """
        self.plugins: Dict[str, Plugin] = {}
        self.config_path = config_path
        self.configs: Dict[str, PluginConfig] = {}
        self._load_configs()
        logger.info("PluginManager initialized")

    def _load_configs(self) -> None:
        """Load plugin configurations from YAML file."""
        if not self.config_path:
            return

        if not os.path.exists(self.config_path):
            logger.warning(f"Plugin config file not found: {self.config_path}")
            return

        try:
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f) or {}
            for plugin_name, plugin_data in data.get("plugins", {}).items():
                self.configs[plugin_name] = PluginConfig.from_dict(plugin_data)
            logger.info(f"Loaded {len(self.configs)} plugin configs from {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading plugin config: {e}", exc_info=True)

    def register_plugin(self, plugin: Plugin) -> None:
        """
        Register a plugin instance.

        Args:
            plugin: Plugin instance to register
        """
        if plugin.name in self.plugins:
            logger.warning(f"Plugin {plugin.name} already registered, replacing")
        self.plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin.name}")

    def load_plugin(self, plugin_class: Type[Plugin], config: Optional[PluginConfig] = None) -> Plugin:
        """
        Load and initialize a plugin class.

        Args:
            plugin_class: Plugin class to instantiate
            config: Optional plugin configuration

        Returns:
            Initialized plugin instance

        Raises:
            ValueError: If plugin_class is not a Plugin subclass
        """
        if not issubclass(plugin_class, Plugin):
            raise ValueError(f"{plugin_class} must be a Plugin subclass")

        # Get config from manager or create new
        if config is None:
            name = plugin_class.__name__
            config = self.configs.get(name, PluginConfig(name=name))

        # Skip disabled plugins
        if not config.enabled:
            logger.info(f"Plugin {config.name} is disabled, skipping")
            return None

        # Instantiate and register
        plugin = plugin_class(config)
        self.register_plugin(plugin)

        # Call on_load hook
        try:
            plugin.on_load()
            logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")
        except Exception as e:
            logger.error(f"Error loading plugin {plugin.name}: {e}", exc_info=True)
            self.plugins.pop(plugin.name, None)
            raise

        return plugin

    def load_plugins(self, directory: str) -> Dict[str, Plugin]:
        """
        Discover and load all plugins from a directory.

        Expects Python modules in format: plugin_name.py
        Each module should define a Plugin subclass.

        Args:
            directory: Path to plugins directory

        Returns:
            Dictionary of loaded plugins

        Example:
            Directory structure:
                plugins/
                  logging.py       # defines LoggingPlugin
                  analytics.py     # defines AnalyticsPlugin
        """
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Plugin directory not found: {directory}")
            return {}

        # Add directory to sys.path for imports
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))

        loaded = {}
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    # Find Plugin subclasses in module
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, Plugin)
                            and obj is not Plugin
                        ):
                            plugin = self.load_plugin(obj)
                            if plugin:
                                loaded[plugin.name] = plugin
                                logger.info(f"Discovered and loaded plugin: {plugin.name}")
            except Exception as e:
                logger.error(f"Error loading plugin from {py_file}: {e}", exc_info=True)

        logger.info(f"Loaded {len(loaded)} plugins from {directory}")
        return loaded

    def load_builtin_plugins(self) -> Dict[str, Plugin]:
        """
        Load all built-in plugins.

        Returns:
            Dictionary of loaded built-in plugins
        """
        from agentic_brain.plugins import builtin

        builtin_dir = Path(builtin.__file__).parent
        return self.load_plugins(str(builtin_dir))

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if plugin was unloaded, False if not found
        """
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin {plugin_name} not found")
            return False

        plugin = self.plugins[plugin_name]
        try:
            plugin.on_unload()
            del self.plugins[plugin_name]
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}", exc_info=True)
            return False

    def unload_all_plugins(self) -> None:
        """Unload all plugins."""
        plugin_names = list(self.plugins.keys())
        for name in plugin_names:
            self.unload_plugin(name)
        logger.info("Unloaded all plugins")

    def enable_plugin(self, plugin_name: str) -> bool:
        """
        Enable a plugin.

        Args:
            plugin_name: Name of plugin to enable

        Returns:
            True if plugin was enabled
        """
        if plugin_name not in self.plugins:
            return False
        self.plugins[plugin_name].enabled = True
        logger.info(f"Enabled plugin: {plugin_name}")
        return True

    def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable a plugin.

        Args:
            plugin_name: Name of plugin to disable

        Returns:
            True if plugin was disabled
        """
        if plugin_name not in self.plugins:
            return False
        self.plugins[plugin_name].enabled = False
        logger.info(f"Disabled plugin: {plugin_name}")
        return True

    def trigger(
        self,
        hook_name: str,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        Trigger a lifecycle hook on all enabled plugins.

        Hooks are triggered in registration order. For on_message and on_response,
        the return value from one plugin is passed to the next.

        Args:
            hook_name: Name of hook to trigger ('on_message', 'on_response', etc.)
            *args: Positional arguments to pass to hook
            **kwargs: Keyword arguments to pass to hook

        Returns:
            Final value after all plugins have processed it (for message/response hooks)
        """
        result = args[0] if args else None

        for plugin in self.plugins.values():
            if not plugin.enabled:
                continue

            try:
                # Get the hook method
                hook = getattr(plugin, hook_name, None)
                if not hook or not callable(hook):
                    continue

                # Call hook
                if hook_name in ("on_message", "on_response"):
                    # These hooks can modify and return values
                    modified = hook(result, **kwargs)
                    if modified is not None:
                        result = modified
                else:
                    # Other hooks are just called for side effects
                    hook(*args, **kwargs)

            except Exception as e:
                logger.error(
                    f"Error triggering {hook_name} on {plugin.name}: {e}",
                    exc_info=True,
                )

        return result

    def list_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all loaded plugins.

        Returns:
            Dictionary of plugin info
        """
        return {
            name: {
                "name": plugin.name,
                "version": plugin.version,
                "enabled": plugin.enabled,
                "description": plugin.config.description,
            }
            for name, plugin in self.plugins.items()
        }

    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """
        Get a plugin by name.

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(plugin_name)

    def get_plugin_config(self, plugin_name: str) -> Optional[PluginConfig]:
        """
        Get a plugin's configuration.

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin config or None if not found
        """
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin.config
        return None
