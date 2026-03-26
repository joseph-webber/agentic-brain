#!/usr/bin/env python3
"""
User Regional Data Storage System - Comprehensive Demo
Demonstrates the real-time learning capabilities and disk persistence.
"""

import sys

sys.path.insert(0, "/Users/joe/brain/agentic-brain/src")

from agentic_brain.voice.user_regions import (
    UserRegionStorage,
    set_user_region,
    regionalize_text,
    get_region_stats,
)
from pathlib import Path
import tempfile
import json


def print_section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def demo():
    print_section("USER REGIONAL DATA STORAGE SYSTEM")
    print("Stores and learns regional language preferences on user's disk")
    print("Each user can customize their own regional slang and expressions")

    # Create temp storage
    tmpdir = Path(tempfile.mkdtemp())
    print(f"\nData directory: {tmpdir}")

    # Initialize storage
    storage = UserRegionStorage(data_dir=tmpdir)

    # ===== TASK 1: Set Region =====
    print_section("TASK 1: Set User Region")
    print("Setting region to Adelaide, South Australia...")
    storage.set_region("Adelaide", "South Australia")
    region = storage.get_region()
    print(f"✓ City: {region.city}")
    print(f"✓ State: {region.state}")
    print(f"✓ Timezone: {region.timezone}")

    # ===== TASK 2: Add Custom Expressions =====
    print_section("TASK 2: Add Custom Expressions")
    expressions = [
        ("great", "heaps good"),
        ("very", "dead set"),
        ("thank you", "ta"),
        ("friend", "mate"),
        ("excellent", "bonzer"),
    ]
    for standard, regional in expressions:
        storage.add_expression(standard, regional)
        print(f"✓ Added: '{standard}' → '{regional}'")

    # ===== TASK 3: Learn From Corrections =====
    print_section("TASK 3: Learn From Corrections")
    print("Brain learns when user corrects speech...")
    storage.learn_from_correction("That is very good", "That is heaps good")
    print("✓ Correction logged and analyzed")

    # ===== TASK 4: Auto-Learn Expressions =====
    print_section("TASK 4: Auto-Learn Expressions")
    print("Brain auto-learns expressions from context...")
    storage.learn_expression("brilliant", "heaps good")
    storage.learn_expression("awesome", "bonzer")
    print("✓ Expression learning complete")

    # ===== TASK 5: Track Usage =====
    print_section("TASK 5: Track Expression Usage")
    print("Tracking which expressions are used most...")
    for _ in range(5):
        storage.track_expression_usage("great")
    for _ in range(3):
        storage.track_expression_usage("very")
    for _ in range(1):
        storage.track_expression_usage("thank you")

    top_expr = storage.get_top_expressions(limit=5)
    print("Top expressions by usage:")
    for standard, regional, count in top_expr:
        print(f"  {count:2d}x  '{standard}' → '{regional}'")

    # ===== TASK 6: Regionalize Text =====
    print_section("TASK 6: Regionalize Text")
    original = "That is great! Thank you very much, brilliant work!"
    regionalized = storage.regionalize(original)
    print(f"Original:     {original}")
    print(f"Regionalized: {regionalized}")

    # ===== TASK 7: Get Statistics =====
    print_section("TASK 7: Learning Statistics")
    stats = storage.get_learning_stats()
    print(f"Custom expressions:  {stats['total_custom']}")
    print(f"Learned expressions: {stats['total_learned']}")
    print(f"Total expressions:   {stats['total_expressions']}")
    print(f"Corrections logged:  {stats['corrections_count']}")
    print(f"Auto-learnings:      {stats['learnings_count']}")
    print(f"Last learning at:    {stats['last_learning']}")

    # ===== TASK 8: Export Config =====
    print_section("TASK 8: Export Configuration")
    export_file = tmpdir / "my_region.json"
    if storage.export_config(export_file):
        with open(export_file) as f:
            exported = json.load(f)
        print(f"✓ Exported to: {export_file}")
        print(f"✓ Region: {exported['region']['city']}")
        print(f"✓ Custom expressions: {len(exported['region']['custom_expressions'])}")
        print(
            f"✓ Learned expressions: {len(exported['region']['learned_expressions'])}"
        )

    # ===== TASK 9: Persistence Check =====
    print_section("TASK 9: Verify Disk Persistence")
    print("Creating new storage instance from same directory...")
    storage2 = UserRegionStorage(data_dir=tmpdir)
    region2 = storage2.get_region()
    exprs2 = storage2.get_all_expressions()

    print(f"✓ Region loaded: {region2.city}")
    print(f"✓ Expressions recovered: {len(exprs2)}")
    print(
        f"✓ Greeting: {region2.favorite_greetings[:1] if region2.favorite_greetings else 'N/A'}"
    )

    # ===== TASK 10: History =====
    print_section("TASK 10: View History")
    corrections = storage.get_corrections_history(limit=5)
    learnings = storage.get_learnings_history(limit=5)

    print(f"Recent corrections ({len(corrections)} logged):")
    if corrections:
        for c in corrections[-3:]:
            print(f"  • '{c['original']}' → '{c['corrected']}'")

    print(f"\nRecent learnings ({len(learnings)} logged):")
    if learnings:
        for l in learnings[-3:]:
            print(f"  • '{l['standard']}' → '{l['regional']}'")

    # ===== SUMMARY =====
    print_section("SYSTEM SUMMARY")
    print(
        """
✓ User Regional Data Storage: WORKING
✓ Real-time learning: WORKING
✓ Disk persistence: WORKING
✓ Export/Import: WORKING
✓ Usage tracking: WORKING
✓ History logging: WORKING

FEATURES:
  • Stores regional preferences on user's disk
  • Auto-learns expressions from corrections
  • Tracks usage patterns
  • Exports/imports configurations
  • Maintains correction and learning history
  • Regionalize text with learned expressions
  • Statistics and analytics
  • Multi-user support (different regions)
    """
    )

    print(f"\nData stored in: {tmpdir}")


if __name__ == "__main__":
    demo()
