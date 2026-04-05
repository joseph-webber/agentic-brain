#!/usr/bin/env python3
"""
Regional Voice Demo - Show off location-aware expressions!

This demo shows how the regional voice system adapts to the user's location
in Adelaide, South Australia and can learn new expressions.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentic_brain.voice.regional import (
    AUSTRALIAN_REGIONS,
    get_regional_voice,
    list_regions,
)


def demo_adelaide():
    """Demo Adelaide-specific expressions."""
    print("\n" + "=" * 60)
    print("🇦🇺  ADELAIDE REGIONAL VOICE DEMO")
    print("=" * 60)

    rv = get_regional_voice()

    print(f"\n📍 Location: {rv.region_name}")
    print(f"   Timezone: {rv.timezone}")

    # Demo greetings
    print("\n👋 Greetings:")
    for _ in range(3):
        print(f"   {rv.get_greeting()}")

    # Demo farewells
    print("\n👋 Farewells:")
    for _ in range(3):
        print(f"   {rv.get_farewell()}")

    # Demo regionalizations
    print("\n🗣️  Regional Expressions:")
    examples = [
        "That's very great! Thank you!",
        "Let's go to the bottle shop this afternoon",
        "That's definitely good",
        "The service station has a barbecue",
        "This chocolate biscuit is delicious!",
    ]

    for text in examples:
        regionalized = rv.regionalize(text)
        print(f"\n   Standard: {text}")
        print(f"   Adelaide: {regionalized}")

    # Demo local knowledge
    print("\n📚 Local Knowledge:")
    knowledge_topics = [
        ("coffee_order", "☕"),
        ("football", "🏈"),
        ("wine_region", "🍷"),
        ("beach", "🏖️"),
        ("events", "🎭"),
    ]

    for topic, emoji in knowledge_topics:
        info = rv.get_local_knowledge(topic)
        if info:
            print(f"\n   {emoji} {topic.replace('_', ' ').title()}:")
            print(f"      {info}")


def demo_travel():
    """Demo switching regions when traveling."""
    print("\n\n" + "=" * 60)
    print("✈️  TRAVEL DEMO - Adelaide to Melbourne")
    print("=" * 60)

    rv = get_regional_voice()

    # Start in Adelaide
    print("\n📍 Starting in Adelaide...")
    text = "That's very great!"
    adelaide_version = rv.regionalize(text)
    print(f"   Adelaide: {adelaide_version}")
    print(f"   Greeting: {rv.get_greeting()}")

    # Travel to Melbourne
    print("\n✈️  Flying to Melbourne...")
    rv.save_location("melbourne")
    rv._load_location()

    print("\n📍 Now in Melbourne!")
    melbourne_version = rv.regionalize(text)
    print(f"   Melbourne: {melbourne_version}")
    print(f"   Greeting: {rv.get_greeting()}")

    # Check coffee culture difference
    adelaide_coffee = AUSTRALIAN_REGIONS["adelaide"].local_knowledge.get("coffee_order")
    melbourne_coffee = AUSTRALIAN_REGIONS["melbourne"].local_knowledge.get("coffee")

    print("\n☕ Coffee Culture:")
    print(f"   Adelaide: {adelaide_coffee}")
    print(f"   Melbourne: {melbourne_coffee}")

    # Return to Adelaide
    print("\n✈️  Flying back to Adelaide...")
    rv.save_location("adelaide")
    rv._load_location()
    print(f"   Back home! {rv.get_greeting()}")


def demo_learning():
    """Demo learning new expressions."""
    print("\n\n" + "=" * 60)
    print("🎓  LEARNING NEW EXPRESSIONS")
    print("=" * 60)

    rv = get_regional_voice()

    # Before learning
    text = "How is your friend going? That's awesome!"
    print("\n   Before learning:")
    print(f"   {text}")
    print(f"   → {rv.regionalize(text)}")

    # Learn new expressions
    print("\n   📝 Teaching new slang...")
    rv.add_expression("friend", "mate")
    rv.add_expression("going", "goin'")
    rv.add_expression("awesome", "bonza")

    # After learning
    print("\n   After learning:")
    print(f"   {text}")
    print(f"   → {rv.regionalize(text)}")

    # Learn local knowledge
    print("\n   📝 Adding local knowledge...")
    rv.add_local_knowledge("pub", "The Adelaide Casino is popular for poker")

    pub_info = rv.get_local_knowledge("pub")
    print(f"\n   Pub info: {pub_info}")


def demo_all_regions():
    """Show all available regions."""
    print("\n\n" + "=" * 60)
    print("🌏  ALL AVAILABLE REGIONS")
    print("=" * 60)

    regions = list_regions()

    print(f"\n   Found {len(regions)} regions:\n")

    from agentic_brain.voice.regional import get_available_regions

    all_regions = get_available_regions()

    # Group by country
    by_country = {}
    for key, profile in all_regions.items():
        country = profile.country
        if country not in by_country:
            by_country[country] = []
        by_country[country].append((key, profile))

    for country, profiles in sorted(by_country.items()):
        print(f"   {country}")
        print(f"   {'-'*40}")
        for key, profile in sorted(profiles, key=lambda x: x[1].city):
            print(f"   {key:<20} - {profile.city}, {profile.state}")
        print()


def demo_voice_test():
    """Demo with actual voice output (macOS only)."""
    print("\n\n" + "=" * 60)
    print("🎙️  VOICE OUTPUT TEST")
    print("=" * 60)

    import platform

    if platform.system() != "Darwin":
        print("\n   ⚠️  Voice output requires macOS")
        return

    try:
        from agentic_brain.audio import speak

        rv = get_regional_voice()

        # Standard text
        standard = "Hello! That's very great! Thank you!"
        regional = rv.regionalize(standard)

        print(f"\n   Standard: {standard}")
        print(f"   Regional: {regional}")
        print("\n   🎙️ Speaking regional version...")

        speak(regional, voice="Karen (Premium)", rate=160, regionalize=False)

        print("   ✓ Done!")

    except Exception as e:
        print(f"   ⚠️  Could not test voice: {e}")


def main():
    """Run all demos."""
    print("\n🎙️  REGIONAL VOICE INTELLIGENCE DEMO")
    print("   Location-aware expressions for the brain!\n")

    try:
        demo_adelaide()
        demo_travel()
        demo_learning()
        demo_all_regions()
        demo_voice_test()

        print("\n\n" + "=" * 60)
        print("✅  DEMO COMPLETE!")
        print("=" * 60)
        print("\n   Try these commands:")
        print("   - ab voice location              # Show current location")
        print("   - ab voice location melbourne    # Change to Melbourne")
        print("   - ab voice expressions           # Show all expressions")
        print("   - ab voice knowledge             # Show local knowledge")
        print("   - ab voice regionalize 'text'    # Convert text")
        print()

    except KeyboardInterrupt:
        print("\n\n   Demo interrupted!")
    except Exception as e:
        print(f"\n\n   Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
