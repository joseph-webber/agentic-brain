#!/usr/bin/env python3
"""
Example: Using Clock MCP Server Tools

This example demonstrates how AI agents should use the clock server
to get accurate, never-stale date/time information.
"""

from agentic_brain.mcp.clock_server import (
    clock_year,
    clock_adelaide,
    clock_greeting,
    clock_is_business_hours,
    clock_convert,
    clock_format,
)
import json


def example_greeting():
    """Example: Get appropriate greeting for Joseph"""
    print("=" * 70)
    print("EXAMPLE 1: Smart Greeting")
    print("=" * 70)

    greeting_data = json.loads(clock_greeting())

    greeting = greeting_data["greeting"]
    time = greeting_data["time"]

    print(f"\n{greeting}, Joseph!")
    print(f"The time in Adelaide is {time}")
    print()


def example_year_check():
    """Example: Prevent stale year confusion"""
    print("=" * 70)
    print("EXAMPLE 2: Year Check (Prevent AI Confusion)")
    print("=" * 70)

    year_data = json.loads(clock_year())

    print(f"\nCurrent year: {year_data['year']}")
    print(f"⚠️  {year_data['warning']}")
    print()


def example_business_hours():
    """Example: Check if it's a good time to send work messages"""
    print("=" * 70)
    print("EXAMPLE 3: Business Hours Detection")
    print("=" * 70)

    hours_data = json.loads(clock_is_business_hours())

    is_work_time = hours_data["is_business_hours"]
    is_weekend = hours_data["is_weekend"]
    day = hours_data["day"]
    time = hours_data["time"]

    print(f"\nCurrent time: {day}, {time}")

    if is_weekend:
        print("🏖️  It's the weekend! Enjoy your time off.")
    elif is_work_time:
        print("💼 Business hours - good time for work communications")
    else:
        print("🌙 Outside business hours - consider waiting until morning")

    print()


def example_adelaide_info():
    """Example: Get comprehensive Adelaide time info"""
    print("=" * 70)
    print("EXAMPLE 4: Adelaide Time (Joseph's Timezone)")
    print("=" * 70)

    adelaide_data = json.loads(clock_adelaide())

    print(f"\n📍 Adelaide, South Australia")
    print(f"   Date: {adelaide_data['date']}")
    print(f"   Time: {adelaide_data['time']}")
    print(f"   Day: {adelaide_data['day']}")
    print(f"   Timezone: {adelaide_data['timezone']} ({adelaide_data['offset']})")
    print(f"   Year: {adelaide_data['year']}")
    print()


def example_timezone_conversion():
    """Example: Convert between timezones"""
    print("=" * 70)
    print("EXAMPLE 5: Timezone Conversion")
    print("=" * 70)

    # Convert current UTC time to Adelaide
    conversion = json.loads(clock_convert("UTC", "Australia/Adelaide"))

    utc_time = conversion["from"]["datetime"]
    adelaide_time = conversion["to"]["datetime"]
    offset = conversion["offset_hours"]

    print(f"\n🌍 UTC: {utc_time}")
    print(f"🇦🇺 Adelaide: {adelaide_time}")
    print(f"   (Adelaide is {offset} hours ahead of UTC)")
    print()


def example_custom_format():
    """Example: Custom date/time formatting"""
    print("=" * 70)
    print("EXAMPLE 6: Custom Formatting")
    print("=" * 70)

    formats = [
        ("%A, %B %d, %Y", "Full date"),
        ("%Y-%m-%d", "ISO date"),
        ("%I:%M %p", "12-hour time"),
        ("%H:%M:%S", "24-hour time"),
        ("%B %Y", "Month and year"),
    ]

    print()
    for fmt, description in formats:
        result = clock_format(fmt)
        print(f"   {description:20s}: {result}")
    print()


def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("CLOCK MCP SERVER - PRACTICAL EXAMPLES")
    print("=" * 70)
    print()

    # Run examples
    example_greeting()
    example_year_check()
    example_business_hours()
    example_adelaide_info()
    example_timezone_conversion()
    example_custom_format()

    print("=" * 70)
    print("✅ All Examples Complete!")
    print("=" * 70)
    print()
    print("💡 Use these tools in your AI agent to:")
    print("   - Get accurate, never-stale dates")
    print("   - Provide time-appropriate greetings")
    print("   - Respect business hours")
    print("   - Handle timezone conversions")
    print("   - Format dates for any use case")
    print()


if __name__ == "__main__":
    main()
