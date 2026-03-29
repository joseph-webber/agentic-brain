#!/usr/bin/env python3
"""
Quick test to verify clock MCP server is properly integrated
and available through the main MCP server.
"""

from agentic_brain.mcp.tools import get_all_tools
from agentic_brain.utils.clock import get_clock
import json


def test_clock_singleton():
    """Test the clock singleton directly"""
    print("🔍 Testing Clock Singleton...")
    clock = get_clock()
    
    assert clock.year() == 2026, "Year should be 2026"
    assert len(clock.iso_date()) == 10, "ISO date should be YYYY-MM-DD"
    assert clock.greeting() in ["Good morning", "Good afternoon", "Good evening"]
    
    print("   ✅ Clock singleton working")


def test_clock_tools_registered():
    """Test that all clock tools are registered"""
    print("\n🔍 Testing Clock Tools Registration...")
    all_tools = get_all_tools()
    
    expected_tools = [
        "clock_now",
        "clock_adelaide",
        "clock_utc",
        "clock_year",
        "clock_date",
        "clock_greeting",
        "clock_is_business_hours",
        "clock_convert",
        "clock_format",
    ]
    
    for tool_name in expected_tools:
        assert tool_name in all_tools, f"Tool {tool_name} not registered"
        assert "function" in all_tools[tool_name], f"Tool {tool_name} missing function"
        assert "description" in all_tools[tool_name], f"Tool {tool_name} missing description"
    
    print(f"   ✅ All {len(expected_tools)} clock tools registered")


def test_clock_tools_callable():
    """Test that clock tools can be called"""
    print("\n🔍 Testing Clock Tools Callable...")
    all_tools = get_all_tools()
    
    # Test a few key tools
    tests = [
        ("clock_year", {}, "should return year 2026"),
        ("clock_date", {}, "should return ISO date"),
        ("clock_greeting", {}, "should return JSON with greeting"),
        ("clock_is_business_hours", {}, "should return JSON with business hours info"),
    ]
    
    for tool_name, args, description in tests:
        func = all_tools[tool_name]["function"]
        result = func(**args)
        assert result is not None, f"{tool_name} returned None"
        print(f"   ✅ {tool_name} - {description}")


def test_clock_year_correct():
    """Test that clock_year returns correct year"""
    print("\n🔍 Testing Clock Year (Critical!)...")
    all_tools = get_all_tools()
    
    func = all_tools["clock_year"]["function"]
    result = func()
    
    data = json.loads(result)
    assert data["year"] == 2026, "Year should be 2026, not stale!"
    assert "warning" in data, "Should have staleness warning"
    
    print(f"   ✅ Clock reports correct year: {data['year']}")
    print(f"   ⚠️  Warning: {data['warning']}")


def test_config_exists():
    """Test that timezone.yaml config exists"""
    print("\n🔍 Testing Configuration...")
    import os
    
    config_path = "/Users/joe/brain/agentic-brain/config/timezone.yaml"
    assert os.path.exists(config_path), f"Config not found: {config_path}"
    
    print(f"   ✅ Configuration file exists")


def main():
    """Run all tests"""
    print("=" * 70)
    print("CLOCK MCP SERVER - INTEGRATION TEST")
    print("=" * 70)
    
    try:
        test_clock_singleton()
        test_clock_tools_registered()
        test_clock_tools_callable()
        test_clock_year_correct()
        test_config_exists()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nClock MCP Server is ready for use by AI agents.")
        print("Tools are properly integrated and returning correct data.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
