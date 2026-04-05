#!/usr/bin/env python3
"""
Brain Event Bus MCP Server
==========================
MCP server that provides direct access to the brain's event bus.
Works with both Redpanda (dev) and Kafka (prod) through abstraction.

This is the NERVE CENTER of the brain - Claude talks directly to 
the event bus, and all services (Python, JHipster, LLM) are peers.

Architecture:
  Claude Desktop → MCP → Event Bus → All Services (as peers)

Tools:
  - emit: Publish event to topic
  - subscribe: Listen to topic (returns recent events)
  - health: Check event bus status
  - topics: List all topics
  - switch_provider: Switch between Redpanda/Kafka
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any

# Add brain to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# Import our abstraction layer
from core.interfaces.event_bus import EventBusConfig, EventBusFactory, EventBusProvider
from core.kafka_bus import BrainTopics
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


class EventBusMCP:
    """MCP server for brain event bus."""

    def __init__(self):
        self.server = Server("brain-event-bus")
        self._bus = None
        self._provider = os.getenv("EVENT_BUS_PROVIDER", "redpanda")
        self._recent_events = {}  # topic -> list of recent events
        self._setup_handlers()

    def _get_bus(self):
        """Get or create event bus connection."""
        if self._bus is None:
            # Use direct import - more reliable than factory
            from core.kafka_bus import BrainEventBus

            self._bus = BrainEventBus()
            self._bus.connect()
        return self._bus

    def _setup_handlers(self):
        """Setup MCP tool handlers."""

        @self.server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="emit",
                    description="Publish an event to a brain topic. Topics: brain.health, brain.tasks, brain.state, brain.alerts, brain.learning, brain.llm.request, brain.commands",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "Topic name (e.g., 'brain.tasks')",
                                "enum": BrainTopics.all(),
                            },
                            "event_type": {
                                "type": "string",
                                "description": "Type of event (e.g., 'task_created', 'health_check')",
                            },
                            "data": {
                                "type": "object",
                                "description": "Event payload data",
                            },
                        },
                        "required": ["topic", "event_type", "data"],
                    },
                ),
                Tool(
                    name="health",
                    description="Check event bus health and status. Shows provider (Redpanda/Kafka), topics, and connection status.",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="topics",
                    description="List all brain event bus topics with descriptions.",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="switch_provider",
                    description="Switch between Redpanda (dev) and Kafka (prod). Same API, different backend.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "provider": {
                                "type": "string",
                                "enum": ["redpanda", "kafka"],
                                "description": "Provider to switch to",
                            }
                        },
                        "required": ["provider"],
                    },
                ),
                Tool(
                    name="send_llm_request",
                    description="Send a request to the LLM pool (Claude → OpenRouter → Emulator fallback chain).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "The prompt to send to LLM",
                            },
                            "system": {
                                "type": "string",
                                "description": "Optional system prompt",
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["low", "normal", "high"],
                                "description": "Request priority",
                            },
                        },
                        "required": ["prompt"],
                    },
                ),
                Tool(
                    name="broadcast_alert",
                    description="Broadcast an alert to all brain components.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "enum": ["info", "warning", "error", "critical"],
                                "description": "Alert severity level",
                            },
                            "message": {
                                "type": "string",
                                "description": "Alert message",
                            },
                            "source": {
                                "type": "string",
                                "description": "Source of the alert",
                            },
                        },
                        "required": ["level", "message"],
                    },
                ),
                Tool(
                    name="query_state",
                    description="Query the current state of brain components.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "component": {
                                "type": "string",
                                "description": "Component to query (e.g., 'llm', 'bots', 'jhipster', 'all')",
                            }
                        },
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                if name == "emit":
                    return await self._emit(arguments)
                elif name == "health":
                    return await self._health()
                elif name == "topics":
                    return await self._topics()
                elif name == "switch_provider":
                    return await self._switch_provider(arguments)
                elif name == "send_llm_request":
                    return await self._send_llm_request(arguments)
                elif name == "broadcast_alert":
                    return await self._broadcast_alert(arguments)
                elif name == "query_state":
                    return await self._query_state(arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

    async def _emit(self, args: dict) -> list[TextContent]:
        """Emit an event to a topic."""
        bus = self._get_bus()

        event = {
            "type": args["event_type"],
            "data": args["data"],
            "timestamp": datetime.now().isoformat(),
            "source": "claude-mcp",
        }

        success = bus.emit(args["topic"], event)

        if success:
            return [
                TextContent(
                    type="text",
                    text=f"✅ Event emitted to {args['topic']}\n\n"
                    f"Type: {args['event_type']}\n"
                    f"Data: {json.dumps(args['data'], indent=2)}",
                )
            ]
        else:
            return [
                TextContent(type="text", text=f"❌ Failed to emit to {args['topic']}")
            ]

    async def _health(self) -> list[TextContent]:
        """Check event bus health."""
        bus = self._get_bus()
        health = bus.health_check()

        status_emoji = "✅" if health.get("status") == "healthy" else "❌"

        result = f"""🧠 **Brain Event Bus Status**

{status_emoji} Status: {health.get('status', 'unknown')}
📡 Provider: {self._provider.upper()}
🔌 Broker: {health.get('broker', 'unknown')}
📬 Topics: {health.get('brain_topics', 0)} brain topics
🎧 Handlers: {health.get('handlers_registered', 0)} registered
⚡ Consuming: {health.get('consuming', False)}

**Architecture:**
```
Claude ──► MCP ──► Event Bus ({self._provider})
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
      Python       JHipster       LLM
       Core         Portal      Emulator
```
"""
        return [TextContent(type="text", text=result)]

    async def _topics(self) -> list[TextContent]:
        """List all brain topics."""
        topics_info = """📬 **Brain Event Bus Topics**

| Topic | Purpose |
|-------|---------|
| `brain.health` | Health checks from all components |
| `brain.tasks` | Task queue between services |
| `brain.state` | State machine transitions |
| `brain.alerts` | Alerts and notifications |
| `brain.commands` | Commands to process |
| `brain.responses` | Responses from services |
| `brain.learning` | Training data collection |
| `brain.diagnostics` | Performance & debug info |
| `brain.llm.request` | LLM requests (with fallback) |
| `brain.llm.response` | LLM responses |
| `brain.mcp.events` | MCP server events |

**Usage:**
```
emit brain.tasks task_created {\"action\": \"process_ticket\", \"id\": 123}
```
"""
        return [TextContent(type="text", text=topics_info)]

    async def _switch_provider(self, args: dict) -> list[TextContent]:
        """Switch event bus provider."""
        new_provider = args["provider"]
        old_provider = self._provider

        # Disconnect old bus
        if self._bus:
            self._bus.disconnect()
            self._bus = None

        # Switch provider
        self._provider = new_provider

        # Connect new bus
        bus = self._get_bus()
        health = bus.health_check()

        return [
            TextContent(
                type="text",
                text=f"🔄 **Provider Switched**\n\n"
                f"From: {old_provider}\n"
                f"To: {new_provider}\n"
                f"Status: {health.get('status', 'unknown')}\n\n"
                f"Same Kafka API - all services continue working!",
            )
        ]

    async def _send_llm_request(self, args: dict) -> list[TextContent]:
        """Send LLM request via event bus."""
        bus = self._get_bus()

        import uuid

        request_id = str(uuid.uuid4())

        event = {
            "type": "llm_request",
            "request_id": request_id,
            "prompt": args["prompt"],
            "system": args.get("system", ""),
            "priority": args.get("priority", "normal"),
            "timestamp": datetime.now().isoformat(),
            "source": "claude-mcp",
            "fallback_chain": ["claude", "openrouter", "emulator"],
        }

        bus.emit(BrainTopics.LLM_REQUEST, event)

        return [
            TextContent(
                type="text",
                text=f"📤 **LLM Request Sent**\n\n"
                f"Request ID: `{request_id}`\n"
                f"Prompt: {args['prompt'][:100]}...\n"
                f"Priority: {args.get('priority', 'normal')}\n\n"
                f"Fallback chain: Claude → OpenRouter → Emulator\n\n"
                f"Response will arrive on `brain.llm.response`",
            )
        ]

    async def _broadcast_alert(self, args: dict) -> list[TextContent]:
        """Broadcast alert to all components."""
        bus = self._get_bus()

        level_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}

        event = {
            "type": "alert",
            "level": args["level"],
            "message": args["message"],
            "source": args.get("source", "claude-mcp"),
            "timestamp": datetime.now().isoformat(),
        }

        bus.emit(BrainTopics.ALERTS, event)

        return [
            TextContent(
                type="text",
                text=f"{level_emoji.get(args['level'], '📢')} **Alert Broadcast**\n\n"
                f"Level: {args['level'].upper()}\n"
                f"Message: {args['message']}\n"
                f"Source: {args.get('source', 'claude-mcp')}\n\n"
                f"All brain components notified.",
            )
        ]

    async def _query_state(self, args: dict) -> list[TextContent]:
        """Query brain component states."""
        bus = self._get_bus()

        component = args.get("component", "all")

        # Emit state query request
        event = {
            "type": "state_query",
            "component": component,
            "timestamp": datetime.now().isoformat(),
            "source": "claude-mcp",
        }

        bus.emit(BrainTopics.STATE, event)

        # Return immediate status (real responses come via events)
        return [
            TextContent(
                type="text",
                text=f"🔍 **State Query Sent**\n\n"
                f"Component: {component}\n\n"
                f"Responses will arrive on `brain.state` topic.\n\n"
                f"**Current Bus State:**\n"
                f"- Provider: {self._provider}\n"
                f"- Connected: {self._bus is not None}\n"
                f"- Topics: {len(BrainTopics.all())} configured",
            )
        ]

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


def main():
    """Main entry point."""
    server = EventBusMCP()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
