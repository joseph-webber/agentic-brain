# Agentic RAG Framework - Quick Reference

## Quick Start

```python
from agentic_brain.agents import RAGAgent, RAGAgentConfig

# Create agent
agent = RAGAgent(RAGAgentConfig(name="assistant"))

# Add knowledge
await agent.add_document("Python is a programming language")

# Ask question
result = await agent.execute("What is Python?")
print(result.output)
```

## Key Classes

| Class | Purpose |
|-------|---------|
| `Agent` | Base class for all agents |
| `RAGAgent` | Complete RAG implementation |
| `Tool` | Base class for tools |
| `ToolRegistry` | Central tool management |
| `AgentMemory` | Conversation & memory tracking |
| `Planner` | Task planning engine |
| `ToolExecutor` | Safe tool execution |

## Built-in Tools

- `SearchTool` - Web search
- `CalculatorTool` - Math operations  
- `CodeExecutionTool` - Safe Python execution
- `WebLookupTool` - URL content fetching

## Create Custom Tool

```python
from agentic_brain.agents import Tool, ToolResult, ToolCategory

class MyTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            category=ToolCategory.CUSTOM,
            description="My custom tool"
        )
    
    async def execute(self, **kwargs):
        result = kwargs.get("input")
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=result
        )

agent.tool_registry.register(MyTool())
```

## Agent Configuration

```python
from agentic_brain.agents import RAGAgentConfig

config = RAGAgentConfig(
    name="assistant",
    max_iterations=10,
    max_context_docs=5,
    enable_planning=True,
    enable_reflection=True,
)
agent = RAGAgent(config)
```

## Execute with Tools

```python
# Search
result = await agent.call_tool("search", query="Python")

# Calculate
result = await agent.call_tool("calculate", expression="2 + 2")

# Execute code
result = await agent.call_tool("execute_code", code="x = 5 + 3")

# Web lookup
result = await agent.call_tool("web_lookup", url="https://example.com")
```

## Memory Management

```python
# Add conversation
turn = agent.memory.add_message("user", "Hello")

# Add semantic memory
agent.memory.add_memory(
    "Important fact",
    memory_type=MemoryType.SEMANTIC,
    importance=0.9
)

# Recall
recent = agent.memory.recall(limit=10)
important = agent.memory.recall_memories(min_importance=0.7)
```

## Planning & ReAct

```python
from agentic_brain.agents import Planner, PlanningStrategy

planner = Planner(PlanningStrategy.HIERARCHICAL)
plan = await planner.create_plan("Complex task")

# Or use agent with built-in planning
result = await agent.execute("Task that needs planning")
```

## Batch Execution

```python
executor = ToolExecutor(tool_registry=registry)

operations = [
    ("search", {"query": "Python"}),
    ("calculate", {"expression": "2 + 2"}),
]

results = await executor.execute_batch(operations)
```

## Error Handling

```python
try:
    result = await agent.execute("task")
    if not result.success:
        print(f"Error: {result.error}")
except Exception as e:
    print(f"Exception: {e}")
```

## Agent States

- `IDLE` - Ready for work
- `PLANNING` - Creating plan
- `EXECUTING` - Running tasks
- `THINKING` - Reasoning
- `OBSERVING` - Gathering info
- `ERROR` - Error occurred
- `COMPLETE` - Task complete

## Planning Strategies

- `LINEAR` - Sequential steps
- `HIERARCHICAL` - Sub-goal decomposition
- `REACTIVE` - Adapt based on observations
- `TREE_SEARCH` - Search-based planning

## Memory Types

- `SHORT_TERM` - Immediate context
- `LONG_TERM` - Important facts
- `EPISODIC` - Events/experiences
- `SEMANTIC` - General knowledge
- `PROCEDURAL` - How-to knowledge

## Testing

```bash
# Run all tests
pytest tests/agents/ -v

# Run with coverage
pytest tests/agents/ --cov=agentic_brain.agents

# Run specific test
pytest tests/agents/test_rag_agent.py -v
```

## Documentation

- Full docs: `docs/AGENTS.md`
- Implementation: `AGENTS_IMPLEMENTATION_SUMMARY.md`
- Verification: `AGENTS_FRAMEWORK_VERIFICATION.txt`

## Performance Tips

1. **Use concurrent execution** for multiple tools
   ```python
   results = await executor.execute_batch(operations)
   ```

2. **Set appropriate timeouts**
   ```python
   result = await executor.execute_tool("tool", timeout_seconds=30.0)
   ```

3. **Use planning for complex tasks**
   ```python
   config = RAGAgentConfig(enable_planning=True)
   ```

4. **Manage memory size**
   ```python
   config = MemoryConfig(max_items=1000)
   memory = AgentMemory(config)
   ```

## Common Patterns

### Question Answering
```python
agent = RAGAgent(config)
await agent.add_document("Knowledge base")
result = await agent.execute("Question")
```

### Task Decomposition
```python
agent = RAGAgent(RAGAgentConfig(enable_planning=True))
result = await agent.execute("Complex task")
```

### Tool Chaining
```python
result1 = await agent.call_tool("search", query="info")
result2 = await agent.call_tool("calculate", expression="2+2")
```

### Multi-Agent Workflow
```python
orchestrator = SequentialOrchestrator([agent1, agent2])
results = await orchestrator.orchestrate("task")
```

## Version Info

- Framework: agentic-brain.agents
- Python: 3.11+
- Tests: 134 (100% passing)
- Coverage: 91%

## Support

See `docs/AGENTS.md` for comprehensive guide and examples.
