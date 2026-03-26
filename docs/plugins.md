# Plugin System Guide

Agentic Brain has a powerful extensible plugin system that allows you to add functionality without modifying the core code.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Creating Custom Plugins](#creating-custom-plugins)
4. [Plugin Lifecycle](#plugin-lifecycle)
5. [Built-in Plugins](#built-in-plugins)
6. [Configuration](#configuration)
7. [Plugin Discovery](#plugin-discovery)
8. [Advanced Features](#advanced-features)
9. [Examples](#examples)

## Overview

The plugin system provides:

- **Lifecycle hooks**: `on_load`, `on_unload`, `on_message`, `on_response`
- **Dynamic loading**: Load plugins from files or register instances
- **Configuration**: YAML-based plugin configuration
- **Plugin discovery**: Auto-discover plugins from directories
- **Message interception**: Process messages before and after LLM
- **Analytics**: Track usage and metrics
- **Content moderation**: Filter and moderate content
- **Extensibility**: Create custom plugins easily

## Quick Start

### Using Built-in Plugins

```python
from agentic_brain.plugins import PluginManager
from agentic_brain.plugins.builtin.logging import LoggingPlugin
from agentic_brain.plugins.builtin.analytics import AnalyticsPlugin

# Create manager
manager = PluginManager()

# Load built-in plugins
manager.load_plugin(LoggingPlugin)
manager.load_plugin(AnalyticsPlugin)

# Trigger hooks
manager.trigger("on_message", "hello", session_id="123", user_id="user1")
manager.trigger("on_response", "response text", session_id="123")

# Check analytics
analytics = manager.get_plugin("AnalyticsPlugin")
print(analytics.get_stats())
```

### Creating a Simple Plugin

```python
from agentic_brain.plugins import Plugin

class MyPlugin(Plugin):
    """Simple plugin example."""
    
    def on_load(self):
        print(f"Loading {self.name}")
    
    def on_message(self, message: str, **kwargs):
        # Modify or process message
        print(f"Message: {message}")
        return message  # Return modified message or None
    
    def on_unload(self):
        print(f"Unloading {self.name}")
```

## Creating Custom Plugins

### Basic Plugin Structure

```python
from agentic_brain.plugins import Plugin, PluginConfig
from typing import Optional

class MyCustomPlugin(Plugin):
    """Custom plugin for Agentic Brain."""
    
    def __init__(self, config: Optional[PluginConfig] = None):
        if config is None:
            config = PluginConfig(
                name="MyCustomPlugin",
                description="Does something useful",
                config={"setting1": "value1"}
            )
        super().__init__(config)
        
        # Parse plugin-specific config
        self.my_setting = self.config.config.get("setting1", "default")
    
    def on_load(self):
        """Called when plugin is loaded."""
        print(f"Plugin {self.name} loaded with setting: {self.my_setting}")
    
    def on_unload(self):
        """Called when plugin is unloaded."""
        print(f"Plugin {self.name} unloaded")
    
    def on_message(self, message: str, **kwargs) -> Optional[str]:
        """
        Process incoming message.
        
        Args:
            message: The message text
            **kwargs: Context like session_id, user_id, etc.
        
        Returns:
            Modified message or None to pass unchanged
        """
        # Do something with the message
        return message  # or None to pass through
    
    def on_response(self, response: str, **kwargs) -> Optional[str]:
        """
        Process outgoing response.
        
        Returns:
            Modified response or None to pass unchanged
        """
        # Do something with the response
        return response  # or None to pass through
```

### Plugin Registration

```python
from agentic_brain.plugins import PluginManager

manager = PluginManager()

# Option 1: Load plugin class
plugin = manager.load_plugin(MyCustomPlugin)

# Option 2: Register plugin instance
my_plugin = MyCustomPlugin()
manager.register_plugin(my_plugin)

# Option 3: Discover plugins from directory
manager.load_plugins("./plugins/")
```

## Plugin Lifecycle

Plugins go through these lifecycle stages:

### 1. **Load Phase**

```python
def on_load(self):
    """Called when plugin is loaded.
    
    - Initialize resources
    - Setup logging
    - Validate configuration
    """
    self.logger = logging.getLogger(__name__)
    self.db_connection = self.connect_to_db()
```

### 2. **Message Processing Phase**

```python
def on_message(self, message: str, **kwargs) -> Optional[str]:
    """Called when a message is received.
    
    Args:
        message: The message text
        session_id: Session ID from kwargs
        user_id: User ID from kwargs
    
    Returns:
        Modified message or None
    """
    # Log the message
    # Apply filters
    # Modify content
    # Return modified message or None to pass through
    return message
```

### 3. **Response Processing Phase**

```python
def on_response(self, response: str, **kwargs) -> Optional[str]:
    """Called when a response is generated.
    
    Args:
        response: The response text
        message: Original message from kwargs
        session_id: Session ID from kwargs
    
    Returns:
        Modified response or None
    """
    # Post-process response
    # Add metadata
    # Format output
    return response
```

### 4. **Unload Phase**

```python
def on_unload(self):
    """Called when plugin is unloaded.
    
    - Cleanup resources
    - Close connections
    - Save state
    """
    self.db_connection.close()
    self.logger.info("Plugin unloaded")
```

## Built-in Plugins

### AddressValidationPlugin ⭐ NEW

Validates and formats Australian addresses with typo correction.

**Purpose:**
- Parse messy address input from customers
- Fix typos (ADELAID → Adelaide, SYDENY → Sydney)
- Normalize states (South Australia → SA)
- Format addresses consistently
- Calculate confidence scores

**Configuration:**

```yaml
plugins:
  AddressValidationPlugin:
    enabled: true
    config:
      auto_format: true
      include_corrections: true
      confidence_threshold: 0.5
```

**Usage:**

```python
from agentic_brain.plugins.address_validation import AddressValidationPlugin

plugin = AddressValidationPlugin()
result = plugin.validate_address("301/10 Bloduras Wya ADELAID SA 5000")

print(result)
# {
#     "original": "301/10 Bloduras Wya ADELAID SA 5000",
#     "formatted": "Unit 301/10 Bloduras Way, Adelaide SA 5000",
#     "confidence": 0.85,
#     "is_valid": True,
#     "corrections": [
#         {"field": "suburb", "from": "ADELAID", "to": "Adelaide"},
#         {"field": "street_type", "from": "Wya", "to": "Way"}
#     ]
# }
```

**Integration with Chatbots:**

```python
class CustomerServiceBot:
    def __init__(self):
        self.address_plugin = AddressValidationPlugin()
    
    def process_address(self, user_input: str) -> str:
        result = self.address_plugin.validate_address(user_input)
        
        if result["confidence"] < 0.5:
            return f"Sorry, I couldn't understand that address. Did you mean: {result['formatted']}?"
        
        return f"Got it! Delivering to: {result['formatted']}"
```

**Perfect for:**
- Customer service chatbots
- E-commerce delivery address collection
- CRM data entry validation
- Form pre-filling

### LoggingPlugin

Logs all messages and responses.

**Configuration:**

```yaml
plugins:
  LoggingPlugin:
    enabled: true
    config:
      log_level: INFO
      log_messages: true
      log_responses: true
      log_timestamps: true
      log_session_id: true
```

**Usage:**

```python
from agentic_brain.plugins.builtin.logging import LoggingPlugin

manager.load_plugin(LoggingPlugin)
```

### AnalyticsPlugin

Tracks usage statistics, message counts, user activity, etc.

**Configuration:**

```yaml
plugins:
  AnalyticsPlugin:
    enabled: true
    config:
      track_messages: true
      track_responses: true
      track_errors: true
      buffer_size: 100
```

**Usage:**

```python
from agentic_brain.plugins.builtin.analytics import AnalyticsPlugin

manager.load_plugin(AnalyticsPlugin)
analytics = manager.get_plugin("AnalyticsPlugin")
print(analytics.get_stats())
```

**Stats:**

```python
{
    "message_count": 100,
    "response_count": 100,
    "avg_message_length": 45.2,
    "avg_response_length": 120.5,
    "unique_sessions": 10,
    "unique_users": 5,
}
```

### ModerationPlugin

Filters content based on keywords, patterns, and rate limits.

**Configuration:**

```yaml
plugins:
  ModerationPlugin:
    enabled: true
    config:
      enabled_filters: [keyword, pattern, length, rate_limit]
      keywords: [badword1, badword2]
      patterns:
        - '(spam|phishing)'
        - 'credit.card'
      max_message_length: 10000
      rate_limit_messages: 60
      action: log  # or 'warn', 'block'
```

**Usage:**

```python
from agentic_brain.plugins.builtin.moderation import ModerationPlugin

manager.load_plugin(ModerationPlugin)
moderation = manager.get_plugin("ModerationPlugin")
violations = moderation.get_violations()
```

**Actions:**

- `log`: Log violations but allow message through
- `warn`: Warn about violations and allow message through
- `block`: Block the message (return None)

## Configuration

### YAML Configuration File

Create a `plugins.yaml` file:

```yaml
plugins:
  LoggingPlugin:
    enabled: true
    version: "1.0.0"
    description: "Logs all messages and responses"
    config:
      log_level: DEBUG
      log_messages: true
      log_responses: true

  AnalyticsPlugin:
    enabled: true
    description: "Tracks usage statistics"
    config:
      track_messages: true
      buffer_size: 100

  ModerationPlugin:
    enabled: false  # Disabled for now
    config:
      keywords: []
      max_message_length: 10000

  CustomPlugin:
    enabled: true
    description: "My custom plugin"
    config:
      custom_setting: "value"
      debug: true
```

### Loading Configuration

```python
manager = PluginManager(config_path="plugins.yaml")
```

The manager will:
1. Load YAML configuration
2. Use enabled/disabled status
3. Pass config to plugins
4. Validate configuration

## Plugin Discovery

### Auto-Discovery from Directory

Plugins are discovered by looking for Python files in a directory:

```
plugins/
  __init__.py
  logging.py      # Should define LoggingPlugin
  analytics.py    # Should define AnalyticsPlugin
  custom.py       # Should define CustomPlugin
```

Each file should define a `Plugin` subclass:

```python
# plugins/custom.py
from agentic_brain.plugins import Plugin

class CustomPlugin(Plugin):
    def on_load(self):
        print("Loaded!")
```

Load all plugins:

```python
manager.load_plugins("./plugins/")
```

### Loading Built-in Plugins

```python
manager = PluginManager()
manager.load_builtin_plugins()
```

## Advanced Features

### Message Modification Chain

Plugins can modify messages in a chain:

```python
class Plugin1(Plugin):
    def on_message(self, message: str, **kwargs):
        return message.upper()

class Plugin2(Plugin):
    def on_message(self, message: str, **kwargs):
        return message + "!"

# Chain: "hello" -> "HELLO" -> "HELLO!"
```

### Custom Event Hooks

Plugins can register custom event handlers:

```python
class MyPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)
        self.register_hook("custom_event", self.handle_custom)
    
    def handle_custom(self, *args, **kwargs):
        print(f"Custom event triggered: {args}, {kwargs}")
```

### Plugin State Management

```python
class StatefulPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)
        self.state = {}
    
    def on_message(self, message, **kwargs):
        # Update state based on message
        user_id = kwargs.get("user_id")
        if user_id not in self.state:
            self.state[user_id] = {"count": 0}
        self.state[user_id]["count"] += 1
        return message
```

### Error Handling

Errors in plugins are caught and logged, but don't break the plugin chain:

```python
class RobustPlugin(Plugin):
    def on_message(self, message: str, **kwargs):
        try:
            # Do something risky
            return self.process(message)
        except Exception as e:
            logger.error(f"Error processing: {e}")
            return None  # Pass through unchanged
```

### Plugin Communication

Plugins can access each other:

```python
class PluginA(Plugin):
    def on_message(self, message: str, **kwargs):
        # Access another plugin
        plugin_b = self.manager.get_plugin("PluginB")
        if plugin_b:
            # Use plugin_b
            pass
        return message
```

## Examples

### Example 1: Content Translation Plugin

```python
from agentic_brain.plugins import Plugin

class TranslationPlugin(Plugin):
    """Automatically translates messages to a target language."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.target_lang = self.config.config.get("target_language", "es")
    
    def on_message(self, message: str, **kwargs):
        # Skip translation for certain users
        if kwargs.get("user_id") == "admin":
            return None
        
        # Translate message (using external API)
        translated = self.translate(message, self.target_lang)
        return translated
    
    def translate(self, text, lang):
        # Integration with translation API
        return text  # Return translated text
```

### Example 2: Sentiment Analysis Plugin

```python
class SentimentPlugin(Plugin):
    """Analyzes sentiment and adjusts response tone."""
    
    def on_message(self, message: str, **kwargs):
        sentiment = self.analyze_sentiment(message)
        kwargs["sentiment"] = sentiment
        return None
    
    def on_response(self, response: str, **kwargs):
        sentiment = kwargs.get("sentiment")
        
        if sentiment == "negative":
            # Add empathetic response
            return "I understand your concern. " + response
        elif sentiment == "very_positive":
            # Match enthusiasm
            return response + " 🎉"
        
        return None
    
    def analyze_sentiment(self, text):
        # Use sentiment analysis library
        return "neutral"
```

### Example 3: Rate Limiting Plugin

```python
from collections import defaultdict
import time

class RateLimitPlugin(Plugin):
    """Rate limits messages per user."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.max_messages = self.config.config.get("max_messages", 10)
        self.window_seconds = self.config.config.get("window_seconds", 60)
        self.user_messages = defaultdict(list)
    
    def on_message(self, message: str, **kwargs):
        user_id = kwargs.get("user_id", "anonymous")
        now = time.time()
        
        # Remove old messages outside window
        self.user_messages[user_id] = [
            t for t in self.user_messages[user_id]
            if now - t < self.window_seconds
        ]
        
        # Check limit
        if len(self.user_messages[user_id]) >= self.max_messages:
            return None  # Block message
        
        # Track message
        self.user_messages[user_id].append(now)
        return None
```

### Example 4: Caching Plugin

```python
from hashlib import md5

class CachingPlugin(Plugin):
    """Caches responses to identical messages."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.cache = {}
        self.cache_hits = 0
    
    def on_message(self, message: str, **kwargs):
        msg_hash = md5(message.encode()).hexdigest()
        
        if msg_hash in self.cache:
            self.cache_hits += 1
            kwargs["cached"] = True
        
        kwargs["msg_hash"] = msg_hash
        return None
    
    def on_response(self, response: str, **kwargs):
        if not kwargs.get("cached"):
            # Cache the response
            msg_hash = kwargs.get("msg_hash")
            if msg_hash:
                self.cache[msg_hash] = response
        
        return None
```

## Integration with Agent

### Using Plugins in Agent

```python
from agentic_brain import Agent
from agentic_brain.plugins import PluginManager
from agentic_brain.plugins.builtin.logging import LoggingPlugin

# Create plugin manager
plugin_manager = PluginManager()
plugin_manager.load_plugin(LoggingPlugin)

# Create agent
agent = Agent(name="assistant")

# Integrate plugins
async def chat_with_plugins(message: str, session_id: str):
    # Trigger on_message hook
    processed_msg = plugin_manager.trigger(
        "on_message",
        message,
        session_id=session_id,
        user_id="user123"
    )
    
    # Get response from agent
    response = agent.chat(processed_msg or message)
    
    # Trigger on_response hook
    processed_response = plugin_manager.trigger(
        "on_response",
        response,
        session_id=session_id,
        message=message
    )
    
    return processed_response or response
```

## Testing Plugins

```python
import pytest
from agentic_brain.plugins import PluginManager

def test_my_plugin():
    manager = PluginManager()
    manager.load_plugin(MyPlugin)
    
    # Test message processing
    result = manager.trigger("on_message", "test message")
    assert result == "TEST MESSAGE"
```

## Best Practices

1. **Always handle errors**: Catch exceptions in plugin hooks
2. **Keep plugins focused**: Each plugin should do one thing well
3. **Document configuration**: Clearly document all config options
4. **Use logging**: Log important events and errors
5. **Avoid blocking**: Keep hooks fast to not slow down chat
6. **Version plugins**: Include version in plugin config
7. **Write tests**: Test your plugins thoroughly
8. **Clean up resources**: Unload properly in `on_unload`

## Troubleshooting

### Plugin not loading

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check if plugin was loaded
manager = PluginManager()
manager.load_plugins("./plugins/")
print(manager.list_plugins())
```

### Plugin not being triggered

```python
# Verify plugin is enabled
plugin = manager.get_plugin("MyPlugin")
print(f"Enabled: {plugin.enabled}")

# Manually trigger hook
manager.trigger("on_message", "test")
```

### Configuration not being loaded

```python
# Check if config file exists
import os
print(os.path.exists("plugins.yaml"))

# Reload configuration
manager = PluginManager(config_path="plugins.yaml")
print(manager.configs)
```
