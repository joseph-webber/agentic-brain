# Plugin Development Guide

This document describes how to create plugins for agentic-brain.

Overview
- Plugins subclass PluginBase from agentic_brain.plugins.base
- Plugins should set `name`, optional `version` and `dependencies` (list of plugin names)
- Lifecycle: async init(), start(), stop()
- Use manager.register(plugin_instance) to register plugins with a manager
- Use hooks via plugin.hooks.register(event, handler) or plugin.register_hook(event, handler)

Discovery & Loading
- The loader provides functions to load from a directory or packaging entry points:
  - agentic_brain.plugins.loader.load_plugins_from_directory(path)
  - agentic_brain.plugins.loader.load_plugins_from_entry_points(group)
  - resolve_dependencies(mapping) to topologically sort plugins

Best Practices
- Keep init() lightweight; prefer I/O in start()
- Declare dependencies to ensure proper startup order
- Use the manager-level hooks to broadcast events across plugins

Example
See src/agentic_brain/plugins/examples/example_plugin.py for a minimal plugin.

