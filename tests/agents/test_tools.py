# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tests for agent tools framework.
"""

import pytest

from agentic_brain.agents import (
    Tool,
    ToolCategory,
    ToolParameter,
    ToolRegistry,
    ToolResult,
    SearchTool,
    CalculatorTool,
    CodeExecutionTool,
    WebLookupTool,
    create_default_registry,
)


class CustomTool(Tool):
    """Custom tool for testing."""

    def __init__(self):
        super().__init__(
            name="custom",
            category=ToolCategory.CUSTOM,
            description="Custom test tool",
            parameters=[
                ToolParameter(
                    name="input",
                    type="string",
                    required=True,
                )
            ],
        )

    async def execute(self, **kwargs):
        """Execute custom tool."""
        input_val = kwargs.get("input", "")
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=f"Processed: {input_val}",
        )


class TestToolParameter:
    """Test ToolParameter."""

    def test_parameter_creation(self):
        """Test parameter creation."""
        param = ToolParameter(
            name="query",
            type="string",
            description="Search query",
            required=True,
        )
        assert param.name == "query"
        assert param.type == "string"
        assert param.required is True

    def test_parameter_validation_required(self):
        """Test validation of required parameter."""
        param = ToolParameter(name="query", required=True)
        is_valid, error = param.validate(None)
        assert is_valid is False
        assert "required" in error.lower()

    def test_parameter_validation_type(self):
        """Test type validation."""
        param = ToolParameter(name="age", type="int", required=True)
        is_valid, error = param.validate("not_an_int")
        assert is_valid is False

    def test_parameter_validation_choices(self):
        """Test choice validation."""
        param = ToolParameter(
            name="mode",
            type="string",
            choices=["a", "b", "c"],
        )
        is_valid, error = param.validate("d")
        assert is_valid is False

    def test_parameter_validation_success(self):
        """Test successful validation."""
        param = ToolParameter(name="query", type="string")
        is_valid, error = param.validate("valid query")
        assert is_valid is True
        assert error == ""


class TestToolBase:
    """Test Tool base class."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = CustomTool()
        assert tool.name == "custom"
        assert tool.category == ToolCategory.CUSTOM
        assert len(tool.parameters) == 1

    def test_tool_schema(self):
        """Test tool schema generation."""
        tool = CustomTool()
        schema = tool.get_schema()
        assert schema["name"] == "custom"
        assert schema["category"] == "custom"
        assert len(schema["parameters"]) == 1

    def test_tool_repr(self):
        """Test tool representation."""
        tool = CustomTool()
        repr_str = repr(tool)
        assert "custom" in repr_str

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Test tool execution."""
        tool = CustomTool()
        result = await tool.execute(input="test")
        assert result.success is True
        assert "Processed" in result.output


class TestSearchTool:
    """Test SearchTool."""

    @pytest.mark.asyncio
    async def test_search_basic(self):
        """Test basic search."""
        tool = SearchTool()
        result = await tool.execute(query="Python")
        assert result.success is True
        assert isinstance(result.output, list)
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_search_with_max_results(self):
        """Test search with max results."""
        tool = SearchTool()
        result = await tool.execute(query="Python", max_results=3)
        assert result.success is True
        assert len(result.output) <= 3

    @pytest.mark.asyncio
    async def test_search_missing_query(self):
        """Test search without query."""
        tool = SearchTool()
        result = await tool.execute()
        assert result.success is False


class TestCalculatorTool:
    """Test CalculatorTool."""

    @pytest.mark.asyncio
    async def test_calculator_simple(self):
        """Test simple calculation."""
        tool = CalculatorTool()
        result = await tool.execute(expression="2 + 2")
        assert result.success is True
        assert result.output["result"] == 4

    @pytest.mark.asyncio
    async def test_calculator_complex(self):
        """Test complex calculation."""
        tool = CalculatorTool()
        result = await tool.execute(expression="(10 + 5) * 2")
        assert result.success is True
        assert result.output["result"] == 30

    @pytest.mark.asyncio
    async def test_calculator_division(self):
        """Test division."""
        tool = CalculatorTool()
        result = await tool.execute(expression="10 / 2")
        assert result.success is True
        assert result.output["result"] == 5

    @pytest.mark.asyncio
    async def test_calculator_invalid_expression(self):
        """Test invalid expression."""
        tool = CalculatorTool()
        result = await tool.execute(expression="invalid +++ expression")
        assert result.success is False


class TestCodeExecutionTool:
    """Test CodeExecutionTool."""

    @pytest.mark.asyncio
    async def test_code_execution_simple(self):
        """Test simple code execution."""
        tool = CodeExecutionTool()
        result = await tool.execute(code="result = 42")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_code_execution_with_result(self):
        """Test code execution with result."""
        tool = CodeExecutionTool()
        result = await tool.execute(code="result = 2 + 2")
        assert result.success is True


class TestWebLookupTool:
    """Test WebLookupTool."""

    @pytest.mark.asyncio
    async def test_web_lookup(self):
        """Test web lookup."""
        tool = WebLookupTool()
        result = await tool.execute(url="https://example.com")
        assert result.success is True
        assert "url" in result.output

    @pytest.mark.asyncio
    async def test_web_lookup_max_length(self):
        """Test web lookup with max length."""
        tool = WebLookupTool()
        result = await tool.execute(url="https://example.com", max_length=1000)
        assert result.success is True


class TestToolRegistry:
    """Test ToolRegistry."""

    def test_registry_creation(self):
        """Test registry creation."""
        registry = ToolRegistry()
        assert len(registry._tools) == 0

    def test_registry_register(self):
        """Test tool registration."""
        registry = ToolRegistry()
        tool = CustomTool()
        registry.register(tool)
        assert "custom" in registry._tools

    def test_registry_register_duplicate(self):
        """Test duplicate registration."""
        registry = ToolRegistry()
        tool = CustomTool()
        registry.register(tool)
        
        with pytest.raises(ValueError):
            registry.register(tool)

    def test_registry_get_tool(self):
        """Test getting tool."""
        registry = ToolRegistry()
        tool = CustomTool()
        registry.register(tool)
        
        retrieved = registry.get_tool("custom")
        assert retrieved is not None
        assert retrieved.name == "custom"

    def test_registry_get_nonexistent(self):
        """Test getting nonexistent tool."""
        registry = ToolRegistry()
        tool = registry.get_tool("nonexistent")
        assert tool is None

    def test_registry_list_tools(self):
        """Test listing tools."""
        registry = ToolRegistry()
        registry.register(CustomTool())
        registry.register(SearchTool())
        
        tools = registry.list_tools()
        assert len(tools) == 2

    def test_registry_list_by_category(self):
        """Test listing tools by category."""
        registry = ToolRegistry()
        registry.register(SearchTool())
        registry.register(CalculatorTool())
        
        search_tools = registry.list_tools(ToolCategory.SEARCH)
        assert len(search_tools) == 1
        assert search_tools[0]["name"] == "search"

    def test_registry_unregister(self):
        """Test tool unregistration."""
        registry = ToolRegistry()
        tool = CustomTool()
        registry.register(tool)
        registry.unregister("custom")
        
        assert "custom" not in registry._tools

    @pytest.mark.asyncio
    async def test_registry_call_tool(self):
        """Test calling tool through registry."""
        registry = ToolRegistry()
        registry.register(CustomTool())
        
        result = await registry.call_tool("custom", input="test")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_registry_call_nonexistent(self):
        """Test calling nonexistent tool."""
        registry = ToolRegistry()
        
        result = await registry.call_tool("nonexistent")
        assert result.success is False

    def test_registry_repr(self):
        """Test registry representation."""
        registry = ToolRegistry()
        registry.register(CustomTool())
        
        repr_str = repr(registry)
        assert "1 tools" in repr_str


class TestDefaultRegistry:
    """Test default registry creation."""

    def test_create_default_registry(self):
        """Test default registry creation."""
        registry = create_default_registry()
        
        assert registry.get_tool("search") is not None
        assert registry.get_tool("calculate") is not None
        assert registry.get_tool("execute_code") is not None
        assert registry.get_tool("web_lookup") is not None

    @pytest.mark.asyncio
    async def test_default_registry_tools_work(self):
        """Test that default tools work."""
        registry = create_default_registry()
        
        result = await registry.call_tool("calculate", expression="2 + 2")
        assert result.success is True


class TestToolResult:
    """Test ToolResult."""

    def test_result_success(self):
        """Test successful result."""
        result = ToolResult(
            tool_name="test",
            success=True,
            output="success",
        )
        assert result.success is True
        assert result.output == "success"

    def test_result_failure(self):
        """Test failed result."""
        result = ToolResult(
            tool_name="test",
            success=False,
            error="error message",
        )
        assert result.success is False
        assert result.error == "error message"

    def test_result_repr(self):
        """Test result representation."""
        result = ToolResult(
            tool_name="test",
            success=True,
            execution_time_ms=100,
        )
        repr_str = repr(result)
        assert "✓" in repr_str
        assert "100" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
