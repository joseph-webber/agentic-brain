"""
Integration Example: How the Voice System Uses User Regional Data

This shows how to integrate regional learning into the voice system
for automatic regionalization of speech output.
"""

from agentic_brain.voice import (
    get_user_region_storage,
    regionalize_text,
    speak,
)


def regionalized_speak(text: str, voice: str = "Karen (Premium)"):
    """
    Speak text with automatic regionalization based on user's learned preferences.

    Example:
        regionalized_speak("That is great! Thank you very much!")
        # Will automatically apply user's regional expressions
        # Adelaide user might hear: "That is heaps good! Ta dead set much!"
    """
    # Get user's storage
    storage = get_user_region_storage()

    # Check if region is configured
    if storage.get_region() is None:
        # No region set, use original text
        return speak(text, voice=voice)

    # Apply user's learned regional expressions
    regionalized = storage.regionalize(text)

    # Speak the regionalized version
    return speak(regionalized, voice=voice)


def report_regional_learning():
    """Show user their regional learning statistics."""
    storage = get_user_region_storage()
    region = storage.get_region()

    if not region:
        speak("No region configured. Set your region to enable regional learning!")
        return

    stats = storage.get_learning_stats()
    top_expr = storage.get_top_expressions(limit=5)

    report = f"""
    Your Regional Profile
    =====================
    
    Region: {region.city}, {region.state}
    Timezone: {region.timezone}
    
    Learning Statistics:
    - Custom expressions: {stats['total_custom']}
    - Auto-learned expressions: {stats['total_learned']}
    - Total expressions: {stats['total_expressions']}
    - Corrections logged: {stats['corrections_count']}
    
    Top Expressions:
    """

    for standard, regional, count in top_expr:
        report += f"\n    {count}x: '{standard}' → '{regional}'"

    speak(report)


def setup_regional_learning_for_user(city: str, state: str = None):
    """
    Set up regional learning for a new user.

    Example:
        setup_regional_learning_for_user("Adelaide", "South Australia")
    """
    from agentic_brain.voice import set_user_region

    print(f"Setting up regional learning for {city}...")

    # Set the region
    region = set_user_region(city, state)

    # Greet the user with their regional greeting
    storage = get_user_region_storage()
    greeting = (
        storage.get_region().favorite_greetings[0]
        if storage.get_region().favorite_greetings
        else "G'day!"
    )

    regionalized_speak(f"{greeting} You're all set up for {region.city}!")


def export_user_regional_config(filename: str = None):
    """Export user's regional configuration for backup or sharing."""
    storage = get_user_region_storage()

    if filename is None:
        filename = f"{storage.get_region().city.lower()}_regional_config.json"

    from pathlib import Path

    filepath = Path.home() / ".agentic-brain" / "regions" / filename

    if storage.export_config(filepath):
        speak(f"Regional configuration exported to {filepath}")
        return str(filepath)
    else:
        speak("Failed to export regional configuration")
        return None


def import_regional_config(filename: str):
    """Import someone else's regional configuration."""
    from pathlib import Path

    filepath = Path(filename)
    if not filepath.exists():
        speak(f"File not found: {filename}")
        return False

    storage = get_user_region_storage()
    if storage.import_config(filepath):
        region = storage.get_region()
        speak(f"Imported regional configuration for {region.city}!")
        return True
    else:
        speak("Failed to import regional configuration")
        return False


# Example: Multi-region voice assistant
class RegionalVoiceAssistant:
    """
    Voice assistant that adapts to different Australian regions.

    Example:
        assistant = RegionalVoiceAssistant()
        assistant.set_region("Brisbane")
        assistant.speak("That is great!")  # Uses Brisbane slang
        assistant.show_stats()
    """

    def __init__(self):
        self.storage = get_user_region_storage()

    def set_region(self, city: str, state: str = None):
        """Set the region."""
        from agentic_brain.voice import set_user_region

        set_user_region(city, state)
        self.storage = get_user_region_storage()
        region = self.storage.get_region()
        print(f"Set region to {region.city}, {region.state}")

    def add_expression(self, standard: str, regional: str):
        """Add a custom regional expression."""
        self.storage.add_expression(standard, regional)
        print(f"Added: '{standard}' → '{regional}'")

    def speak(self, text: str, voice: str = "Karen (Premium)"):
        """Speak with regionalization."""
        regionalized = self.storage.regionalize(text)
        print(f"Speaking: {regionalized}")
        # In real usage: speak(regionalized, voice=voice)

    def learn_from_correction(self, original: str, corrected: str):
        """Learn from user correction."""
        std, regional = self.storage.learn_from_correction(original, corrected)
        if std:
            print(f"Learned: '{std}' → '{regional}'")

    def show_stats(self):
        """Show learning statistics."""
        stats = self.storage.get_learning_stats()
        print(f"Expressions learned: {stats['total_expressions']}")
        print(f"Corrections: {stats['corrections_count']}")


# ============================================================================
# DEMO: How regional learning enhances user experience
# ============================================================================

if __name__ == "__main__":
    print(
        """
    VOICE SYSTEM + REGIONAL LEARNING INTEGRATION
    ============================================
    
    The user regional data storage system integrates seamlessly with
    the voice system to provide personalized, location-aware interactions.
    
    Features:
    1. Automatic regionalization of speech output
    2. Learning from user corrections
    3. Usage tracking and statistics
    4. Export/import of regional configs
    5. Multi-region support
    """
    )

    # Example: Create assistant
    # assistant = RegionalVoiceAssistant()
    # assistant.set_region("Adelaide")
    # assistant.add_expression("great", "heaps good")
    # assistant.speak("That is great!")
    # assistant.learn_from_correction("that is great", "that is heaps good")
    # assistant.show_stats()
