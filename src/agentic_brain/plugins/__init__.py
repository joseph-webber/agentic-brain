"""
Plugin system for Agentic Brain
================================

Provides extensible plugin architecture for adding functionality without modifying core code.

Example:
    >>> from agentic_brain.plugins import PluginManager, Plugin
    >>> plugin_mgr = PluginManager()
    >>> plugin_mgr.load_plugins('plugins/')
    >>> plugin_mgr.trigger('on_message', message='hello')
"""

from agentic_brain.plugins.base import Plugin, PluginManager, PluginConfig

__all__ = [
    "Plugin",
    "PluginManager",
    "PluginConfig",
]
