# Agentic RAG Framework Documentation

## Overview

The Agentic RAG Framework provides a production-ready system for building AI agents with Retrieval-Augmented Generation (RAG), planning, tool use, and memory management.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    RAG Agent                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Planning (ReAct) → Execution → Reflection       │  │
│  └──────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│ Memory System        Tool Executor      Document Store  │
│ • Conversations      • Search           • RAG Index     │
│ • Context           • Calculate        • Retrieval     │
│ • Semantic          • Code Exec        • Scoring       │
│ • Episodic          • Web Lookup       • Ranking       │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. Base Agent Framework

**File**: `src/agentic_brain/agents/base.py`

Abstract base class for all agents with lifecycle management.

```python
from agentic_brain.agents import Agent, AgentConfig, AgentRole

class MyAgent(Agent):
    async def execute(self, task: str, **kwargs):
        # Implement task execution
        pass
    
    async def think(self, task: str, **kwargs):
        # Reasoning step
        pass
    
    async def observe(self, **kwargs):
        # Environment observation
        pass

# Usage
config = AgentConfig(name="my_agent", role=AgentRole.REASONER)
agent = MyAgent(config)
result = await agent.run("Complete this task")
```

**Key Classes**:
- `Agent`: Abstract base class with execute/think/observe
- `AgentConfig`: Configuration (name, role, timeouts, etc.)
- `AgentState`: Execution states (IDLE, PLANNING, EXECUTING, etc.)
- `AgentRole`: Agent roles (ORCHESTRATOR, EXECUTOR, PLANNER, RAG_AGENT, etc.)
- `AgentContext`: Execution context with metadata
- `AgentResult`: Result wrapper with success/error/metadata
- `MultiAgentOrchestrator`: Abstract orchestrator for multiple agents

### 2. Tool Framework

**File**: `src/agentic_brain/agents/tools.py`

Flexible tool system for agent actions.

```python
from agentic_brain.agents import (
    Tool, ToolRegistry, ToolParameter, ToolCategory,
    SearchTool, CalculatorTool, CodeExecutionTool, WebLookupTool
)

# Create custom tool
class CustomTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            category=ToolCategory.CUSTOM,
            parameters=[
                ToolParameter(name="input", type="string", required=True)
            ]
        )
    
    async def execute(self, **kwargs):
        input_val = kwargs.get("input")
        # Process and return result
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=result
        )

# Use registry
registry = ToolRegistry()
registry.register(CustomTool())
registry.register(SearchTool())

result = await registry.call_tool("search", query="Python")
```

**Built-in Tools**:
- `SearchTool`: Web search
- `CalculatorTool`: Math calculations
- `CodeExecutionTool`: Python code execution (sandboxed)
- `WebLookupTool`: Fetch and summarize URLs

**Key Classes**:
- `Tool`: Abstract base for tools
- `ToolRegistry`: Central tool management
- `ToolParameter`: Parameter definitions with validation
- `ToolResult`: Tool execution results
- `ToolCategory`: Tool organization

### 3. Memory System

**File**: `src/agentic_brain/agents/memory.py`

Conversation history and memory management.

```python
from agentic_brain.agents import (
    AgentMemory, MemoryConfig, MemoryType, ConversationTurn
)

# Create memory
config = MemoryConfig(max_items=1000, max_context_tokens=4000)
memory = AgentMemory(config)

# Add messages
turn = memory.add_message("user", "What is Python?")

# Add semantic memory
memory.add_memory(
    "Python is a programming language",
    memory_type=MemoryType.SEMANTIC,
    importance=0.9
)

# Recall
recent = memory.recall(limit=10)
important = memory.recall_memories(min_importance=0.7)

# Context management
memory.set_context("user_id", "user123")
memory.get_context("user_id")
```

**Memory Types**:
- `SHORT_TERM`: Immediate context
- `LONG_TERM`: Important facts
- `EPISODIC`: Events/experiences
- `SEMANTIC`: General knowledge
- `PROCEDURAL`: How-to knowledge

### 4. Planning System

**File**: `src/agentic_brain/agents/planner.py`

ReAct-style planning and decomposition.

```python
from agentic_brain.agents import (
    Planner, PlanningStrategy, ReActAgent, Action, ActionType
)

# Create planner
planner = Planner(strategy=PlanningStrategy.HIERARCHICAL)

# Create plan
plan = await planner.create_plan("Write a blog post about AI")

# Manual planning
plan = Plan(goal="Task")
plan.add_action(Action(
    type=ActionType.THINK,
    description="Analyze requirement",
    estimated_duration_seconds=1.0
))

# ReAct agent
agent = ReActAgent(planning_strategy=PlanningStrategy.HIERARCHICAL)
plan, results = await agent.think_and_act("Complete task")
```

**Planning Strategies**:
- `LINEAR`: Sequential steps
- `HIERARCHICAL`: Sub-goal decomposition
- `REACTIVE`: Adapt based on observations
- `TREE_SEARCH`: Search-based planning

**Action Types**:
- `THINK`: Reasoning
- `OBSERVE`: Gather information
- `ACT`: Execute action
- `CALL_TOOL`: Use a tool
- `REFLECT`: Evaluate results
- `REPORT`: Return output

### 5. Tool Executor

**File**: `src/agentic_brain/agents/executor.py`

Safe tool execution with error handling.

```python
from agentic_brain.agents import (
    ToolExecutor, ExecutionContext, ExecutionError, ExecutionTimeout
)

# Create executor
executor = ToolExecutor(
    tool_registry=registry,
    max_concurrent=10
)

# Single execution with retries
result = await executor.execute_tool(
    "search",
    timeout_seconds=30.0,
    max_retries=3,
    query="Python async"
)

# Batch execution
operations = [
    ("search", {"query": "Python"}),
    ("calculate", {"expression": "2 + 2"}),
]
results = await executor.execute_batch(operations)

# With fallback
result = await executor.execute_with_fallback(
    primary_tool="search",
    fallback_tool="web_lookup",
    query="information"
)

# With validation
def validator(result):
    return result.output is not None

result = await executor.execute_with_validation(
    "calculate",
    validator=validator,
    expression="2 + 2"
)
```

**Features**:
- Timeout handling
- Automatic retries
- Concurrent execution
- Fallback tools
- Result validation
- Error recovery

### 6. RAG Agent

**File**: `src/agentic_brain/agents/rag_agent.py`

Complete RAG implementation combining all components.

```python
from agentic_brain.agents import RAGAgent, RAGAgentConfig

# Create agent
config = RAGAgentConfig(
    name="research_assistant",
    max_iterations=10,
    max_context_docs=5,
    enable_planning=True,
    enable_reflection=True
)
agent = RAGAgent(config)

# Add documents
await agent.add_document("Python is a programming language")
await agent.add_documents([
    {"content": "Document 1"},
    {"content": "Document 2"}
])

# Execute tasks
result = await agent.execute("What is Python?")
print(result.output)

# Use tools
calculator = await agent.call_tool("calculate", expression="2 + 2")

# Get history
history = agent.get_conversation_history()
```

## Usage Examples

### Example 1: Simple Question Answering

```python
from agentic_brain.agents import RAGAgent, RAGAgentConfig

# Initialize
agent = RAGAgent(RAGAgentConfig(name="qa_agent"))

# Add knowledge
await agent.add_document("The Earth orbits the Sun")
await agent.add_document("The Moon orbits the Earth")

# Ask questions
result = await agent.execute("What does the Earth orbit?")
print(result.output)  # Uses RAG to find relevant documents
```

### Example 2: Complex Task with Planning

```python
from agentic_brain.agents import RAGAgent, RAGAgentConfig, PlanningStrategy

config = RAGAgentConfig(
    name="task_agent",
    enable_planning=True
)
agent = RAGAgent(config)

# Complex task
result = await agent.execute(
    "Research and summarize the latest trends in AI"
)
```

### Example 3: Custom Tool Integration

```python
from agentic_brain.agents import (
    RAGAgent, Tool, ToolCategory, ToolResult, ToolParameter
)

class WeatherTool(Tool):
    def __init__(self):
        super().__init__(
            name="weather",
            category=ToolCategory.CUSTOM,
            parameters=[
                ToolParameter(name="city", type="string", required=True)
            ]
        )
    
    async def execute(self, **kwargs):
        city = kwargs.get("city")
        # Fetch weather data
        return ToolResult(
            tool_name=self.name,
            success=True,
            output={"city": city, "temp": 72}
        )

# Use with agent
agent = RAGAgent(config)
agent.tool_registry.register(WeatherTool())

result = await agent.execute("What's the weather in London?")
```

### Example 4: Multi-Agent Orchestration

```python
from agentic_brain.agents import (
    RAGAgent, MultiAgentOrchestrator
)

# Create specialized agents
research_agent = RAGAgent(config=RAGAgentConfig(name="researcher"))
analyzer_agent = RAGAgent(config=RAGAgentConfig(name="analyzer"))

# Custom orchestrator
class SequentialOrchestrator(MultiAgentOrchestrator):
    async def orchestrate(self, task: str, **kwargs):
        results = []
        
        # Research phase
        research_result = await self.agents[0].execute(task)
        results.append(research_result)
        
        # Analysis phase
        analysis_result = await self.agents[1].execute(
            f"Analyze: {research_result.output}"
        )
        results.append(analysis_result)
        
        return results

# Use
orchestrator = SequentialOrchestrator([research_agent, analyzer_agent])
results = await orchestrator.orchestrate("Explain quantum computing")
```

## Testing

All components are thoroughly tested. Run tests with:

```bash
# All agent tests
pytest tests/agents/ -v

# Specific test file
pytest tests/agents/test_rag_agent.py -v

# With coverage
pytest tests/agents/ --cov=agentic_brain.agents --cov-report=html
```

**Test Coverage**:
- Base agent framework (8 tests)
- Tool system (15 tests)
- Memory management (12 tests)
- Planning and execution (10 tests)
- RAG agent (15 tests)

**Total**: 40+ tests covering all major functionality

## Performance Considerations

### Memory
- Default context window: 4000 tokens
- Automatic summarization/compression available
- Configurable maximum items

### Execution
- Concurrent tool execution (default: 10 concurrent)
- Configurable timeouts per tool
- Automatic retries with exponential backoff

### Optimization
```python
# Increase concurrency
executor = ToolExecutor(max_concurrent=50)

# Shorter timeouts for quick operations
result = await executor.execute_tool(
    "calculate",
    timeout_seconds=5.0
)

# Parallel batch execution
results = await executor.execute_batch(operations)
```

## Error Handling

All components include comprehensive error handling:

```python
from agentic_brain.agents import ExecutionError, ExecutionTimeout

try:
    result = await agent.execute("task")
    if not result.success:
        print(f"Error: {result.error}")
except ExecutionTimeout:
    print("Execution timed out")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Best Practices

1. **Memory Management**: Regularly clear old memories
   ```python
   memory.clear()  # Full clear
   ```

2. **Tool Registry**: Create once, share across agents
   ```python
   registry = create_default_registry()
   agent1 = RAGAgent(config, tool_registry=registry)
   agent2 = RAGAgent(config, tool_registry=registry)
   ```

3. **Planning**: Use hierarchical planning for complex tasks
   ```python
   config = RAGAgentConfig(
       name="complex_agent",
       enable_planning=True
   )
   ```

4. **Error Recovery**: Implement fallbacks
   ```python
   result = await executor.execute_with_fallback(
       "primary_tool",
       "fallback_tool",
       **params
   )
   ```

## Configuration

### RAGAgentConfig Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | str | "rag_agent" | Agent name |
| `role` | AgentRole | RAG_AGENT | Agent role |
| `max_iterations` | int | 10 | Max planning iterations |
| `timeout_seconds` | float | 300.0 | Execution timeout |
| `embedding_model` | str | "all-MiniLM-L6-v2" | Embedding model |
| `max_context_docs` | int | 5 | Max retrieved documents |
| `enable_planning` | bool | True | Enable ReAct planning |
| `enable_reflection` | bool | True | Enable reflection step |

## Security

- Code execution is sandboxed
- Tool parameters are validated
- Memory is isolated per agent/session
- Timeout protection against infinite loops

## Future Enhancements

- Vector database integration
- Distributed execution
- Multi-modal tool support
- Custom planning strategies
- Persistent memory backends
- Advanced caching

## License

Apache 2.0 - See LICENSE file
