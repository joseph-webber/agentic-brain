# Agentic Brain Plugin System

## Overview

The plugin system is a powerful extensibility mechanism for Agentic Brain that allows you to add functionality without modifying core code. Plugins can:

- **Intercept and modify messages** before they reach the LLM
- **Intercept and modify responses** after the LLM generates them
- **Track analytics and metrics** about usage
- **Filter and moderate content** for safety
- **Integrate external services** like translation, sentiment analysis, etc.
- **Manage plugin lifecycle** with load/unload hooks

## Quick Start

### 1. Create Plugin

```python
from agentic_brain.plugins import Plugin

class MyPlugin(Plugin):
    def on_load(self):
        print("Plugin loaded!")
    
    def on_message(self, message: str, **kwargs):
        # Modify message
        return message.upper()
```

### 2. Load and Use

```python
from agentic_brain.plugins import PluginManager

manager = PluginManager()
manager.load_plugin(MyPlugin)

# Process message through plugins
result = manager.trigger("on_message", "hello")
# Result: "HELLO"
```

## Files Created

### Core Plugin System

1. **`src/agentic_brain/plugins/__init__.py`**
   - Main plugin module exports
   - Exports: `Plugin`, `PluginManager`, `PluginConfig`

2. **`src/agentic_brain/plugins/base.py`**
   - `Plugin` base class with lifecycle hooks
   - `PluginManager` for loading/unloading plugins
   - `PluginConfig` dataclass for configuration
   - Plugin discovery from directories
   - YAML configuration support

### Built-in Plugins

3. **`src/agentic_brain/plugins/builtin/__init__.py`**
   - Exports built-in plugins

4. **`src/agentic_brain/plugins/builtin/logging.py`**
   - `LoggingPlugin`: Logs all messages and responses
   - Configurable log level and output
   - Timestamp and session tracking

5. **`src/agentic_brain/plugins/builtin/analytics.py`**
   - `AnalyticsPlugin`: Tracks usage statistics
   - Message/response counts
   - Average message length
   - User and session tracking

6. **`src/agentic_brain/plugins/builtin/moderation.py`**
   - `ModerationPlugin`: Content filtering
   - Keyword blacklist filtering
   - Regex pattern matching
   - Message length limits
   - User rate limiting
   - Configurable actions (log, warn, block)

### Documentation & Examples

7. **`docs/plugins.md`**
   - Comprehensive plugin system guide
   - How to create custom plugins
   - Built-in plugin documentation
   - Configuration examples
   - Advanced features and patterns

8. **`examples/custom_plugin_example.py`**
   - Example custom plugin implementations
   - Context tracking plugin
   - Translation plugin
   - Running example

9. **`plugins.yaml.example`**
   - Example plugin configuration file
   - All built-in plugins configured
   - Keyword and pattern examples

### Tests

10. **`tests/test_plugins.py`**
    - 40 comprehensive tests
    - Test plugin base class
    - Test plugin manager
    - Test all built-in plugins
    - Integration tests
    - All tests passing ✓

## Architecture

```
┌─────────────────────────────────────────┐
│   Application Code (Agent, Chat)        │
└────────────────┬────────────────────────┘
                 │ trigger()
                 ▼
┌─────────────────────────────────────────┐
│        PluginManager                    │
│  ┌──────────────────────────────────┐  │
│  │ trigger()                        │  │
│  │ load_plugins()                   │  │
│  │ unload_plugins()                 │  │
│  │ enable/disable                   │  │
│  └──────────────────────────────────┘  │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐
│Plugin 1│ │Plugin 2│ │Plugin N│
└────────┘ └────────┘ └────────┘

Hook Chain:
message -> on_message(Plugin1) -> on_message(Plugin2) -> on_message(PluginN) -> result
```

## Plugin Lifecycle

1. **Load Phase**: `on_load()` - Initialize resources
2. **Message Phase**: `on_message()` - Process incoming messages
3. **Response Phase**: `on_response()` - Process outgoing responses
4. **Unload Phase**: `on_unload()` - Cleanup resources

## Key Features

### 1. Plugin Discovery
Automatically discover plugins from a directory:

```python
manager.load_plugins("./plugins/")
```

### 2. YAML Configuration
Configure plugins via YAML:

```yaml
plugins:
  MyPlugin:
    enabled: true
    config:
      setting1: value1
```

```python
manager = PluginManager(config_path="plugins.yaml")
```

### 3. Message Modification Chain
Plugins can modify messages as they pass through:

```
"hello" -> uppercase -> "HELLO" -> add_exclamation -> "HELLO!"
```

### 4. Error Isolation
Errors in one plugin don't break the chain:

```python
# If Plugin1 throws, Plugin2 still runs
```

### 5. Enable/Disable at Runtime
```python
manager.disable_plugin("MyPlugin")
manager.enable_plugin("MyPlugin")
```

## Built-in Plugins

### LoggingPlugin
- Logs all messages and responses
- Configurable log level
- Timestamp and session tracking

### AnalyticsPlugin
- Tracks message/response counts
- Calculates average lengths
- Tracks unique users and sessions
- Provides statistics API

### ModerationPlugin
- Keyword-based filtering
- Regex pattern matching
- Message length validation
- User rate limiting
- Three action modes: log, warn, block

## Usage Examples

### Basic Usage
```python
from agentic_brain.plugins import PluginManager
from agentic_brain.plugins.builtin.logging import LoggingPlugin

manager = PluginManager()
manager.load_plugin(LoggingPlugin)
manager.trigger("on_message", "hello")
```

### Custom Plugin
```python
from agentic_brain.plugins import Plugin

class MyPlugin(Plugin):
    def on_message(self, message, **kwargs):
        return message.upper()

manager.load_plugin(MyPlugin)
result = manager.trigger("on_message", "hello")
assert result == "HELLO"
```

### Integration with Agent
```python
from agentic_brain import Agent
from agentic_brain.plugins import PluginManager

agent = Agent(name="assistant")
plugin_mgr = PluginManager()
plugin_mgr.load_builtin_plugins()

# Process message through plugins
msg = plugin_mgr.trigger("on_message", user_input)
response = agent.chat(msg)
response = plugin_mgr.trigger("on_response", response)
```

## Testing

All 40 tests pass:

```bash
cd agentic-brain
pytest tests/test_plugins.py -v
```

Test coverage includes:
- Plugin base class
- Plugin manager operations
- Built-in plugins
- Message modification chains
- Error handling
- Plugin discovery
- Configuration loading

## Configuration

Create `plugins.yaml`:

```yaml
plugins:
  LoggingPlugin:
    enabled: true
    config:
      log_level: DEBUG
      log_messages: true
  
  AnalyticsPlugin:
    enabled: true
    config:
      track_messages: true
  
  ModerationPlugin:
    enabled: true
    config:
      keywords: [bad, word]
      action: log
```

See `plugins.yaml.example` for a complete example.

## Documentation

See `docs/plugins.md` for:
- Complete API reference
- Plugin lifecycle details
- Built-in plugin documentation
- Creating custom plugins
- Configuration examples
- Advanced patterns and techniques
- Troubleshooting guide

## Best Practices

1. **Keep plugins focused** - One plugin, one responsibility
2. **Handle errors gracefully** - Catch and log exceptions
3. **Avoid blocking operations** - Keep hooks fast
4. **Document configuration** - Clear config options
5. **Version your plugins** - Include version in config
6. **Write tests** - Test your plugins
7. **Clean up resources** - Implement on_unload
8. **Log important events** - Use logging for debugging

## Example Plugin

See `examples/custom_plugin_example.py` for:
- Context tracking plugin
- Translation plugin
- Running examples
- Best practices

## Integration Patterns

### 1. Message Preprocessing
```python
manager.trigger("on_message", user_input, session_id=sid)
```

### 2. Response Postprocessing
```python
response = manager.trigger("on_response", response, session_id=sid)
```

### 3. Analytics Tracking
```python
analytics = manager.get_plugin("AnalyticsPlugin")
stats = analytics.get_stats()
```

### 4. Content Moderation
```python
moderation = manager.get_plugin("ModerationPlugin")
violations = moderation.get_violations()
```

## Architecture Highlights

- **Minimal dependencies**: Only uses `yaml` for configuration
- **Type hints**: Full type annotations for IDE support
- **Extensible**: Easy to create custom plugins
- **Configurable**: YAML-based configuration
- **Testable**: 40 comprehensive tests
- **Error resilient**: Errors don't break plugin chain
- **Performance**: Efficient message processing

## Next Steps

1. **Read the docs**: See `docs/plugins.md`
2. **Try built-in plugins**: Use LoggingPlugin, AnalyticsPlugin, ModerationPlugin
3. **Create custom plugin**: Copy `examples/custom_plugin_example.py`
4. **Configure via YAML**: Use `plugins.yaml.example`
5. **Run tests**: `pytest tests/test_plugins.py -v`

---

**Author**: Joseph Webber  
**License**: GPL-2.0-or-later  
**Version**: 1.0.0
