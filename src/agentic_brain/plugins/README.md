# Plugins

Extensible plugin architecture for adding functionality without modifying core code.

## Components

- **base.py** - Base `Plugin` class and `PluginManager` for plugin lifecycle
- **builtin/logging.py** - Built-in logging plugin for message tracking
- **builtin/analytics.py** - Built-in analytics plugin for usage metrics
- **builtin/moderation.py** - Built-in content moderation plugin

## Key Features

- Easy plugin development through inheritance
- Lifecycle hooks (on_load, on_unload, on_message, on_response)
- Configuration-based plugin management
- Built-in plugins for common tasks
- Plugin enable/disable without restarting
- Extensible event system

## Quick Start

```python
from agentic_brain.plugins import PluginManager, Plugin, PluginConfig

# Initialize manager
plugin_mgr = PluginManager()

# Load plugins from directory
plugin_mgr.load_plugins('plugins/')

# Trigger events
plugin_mgr.trigger('on_message', message='hello', user_id='user1')
plugin_mgr.trigger('on_response', response='world', user_id='user1')

# Custom plugin
class MyPlugin(Plugin):
    def on_message(self, context):
        print(f"Message received: {context.data}")
        
plugin_mgr.register_plugin(MyPlugin())
```

## Creating Custom Plugins

```python
from agentic_brain.plugins import Plugin, PluginConfig

class MetricsPlugin(Plugin):
    def on_load(self):
        """Called when plugin is loaded."""
        self.count = 0
    
    def on_message(self, context):
        """Called for each message."""
        self.count += 1
        print(f"Total messages: {self.count}")
    
    def on_unload(self):
        """Called when plugin is unloaded."""
        print(f"Final count: {self.count}")
```

## See Also

- [Chat Module](../chat/README.md) - Plugins integrate with chatbot
- [Hooks System](../hooks/README.md) - Advanced lifecycle management
