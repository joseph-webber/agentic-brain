# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#!/usr/bin/env python3
"""
Test Enhanced Installer
=======================

Quick test script to verify all installer features work correctly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentic_brain.installer_enhanced import (
    detect_gpu,
    detect_llm_keys,
    detect_os,
    detect_python,
    detect_timezone,
    detect_voices,
    get_config_dir,
    test_llm_connection,
)


def test_detections():
    """Test all detection functions."""
    print("Testing Enhanced Installer Functions...\n")

    # OS Detection
    print("1. OS Detection")
    os_info = detect_os()
    print(f"   ✓ System: {os_info['system']}")
    print(f"   ✓ Release: {os_info['release']}")
    print(f"   ✓ Machine: {os_info['machine']}")
    if os_info.get("is_apple_silicon"):
        print("   ✓ Apple Silicon detected!")
    print()

    # Python Detection
    print("2. Python Detection")
    python_info = detect_python()
    print(f"   ✓ Version: {python_info['version']}")
    print(f"   ✓ Executable: {python_info['executable']}")
    print(f"   ✓ In virtualenv: {python_info['is_virtualenv']}")
    print(f"   ✓ Version OK: {python_info['version_ok']}")
    print()

    # GPU Detection
    print("3. GPU Detection")
    gpu_info = detect_gpu()
    if gpu_info["has_gpu"]:
        print(f"   ✓ GPU Found: {gpu_info['type']}")
        print(f"   ✓ Name: {gpu_info['name']}")
        print(f"   ✓ Can Accelerate: {gpu_info['can_accelerate']}")
    else:
        print("   ○ No GPU detected (CPU only)")
    print()

    # Voice Detection
    print("4. Voice Detection")
    voices_info = detect_voices()
    if voices_info["has_tts"]:
        print(f"   ✓ TTS System: {voices_info['system']}")
        print(f"   ✓ Voices Available: {len(voices_info['voices'])}")
        if voices_info["recommended"]:
            print(f"   ✓ Recommended: {', '.join(voices_info['recommended'][:3])}")
    else:
        print("   ○ No TTS system detected")
    print()

    # Timezone Detection
    print("5. Timezone Detection")
    tz_info = detect_timezone()
    print(f"   ✓ Timezone: {tz_info['name']}")
    print(f"   ✓ Offset: {tz_info['offset']}")
    print()

    # LLM Keys Detection
    print("6. LLM Keys Detection")
    llm_keys = detect_llm_keys()
    available = [k for k, v in llm_keys.items() if v]
    if available:
        print(f"   ✓ Found: {', '.join([k.capitalize() for k in available])}")
    else:
        print("   ○ No API keys or local LLM found")
    print()

    # Config Directory
    print("7. Config Directory")
    config_dir = get_config_dir()
    print(f"   ✓ Location: {config_dir}")
    print(f"   ✓ Exists: {config_dir.exists()}")
    print()

    # Overall Status
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_ok = True

    if not python_info["version_ok"]:
        print("⚠ Python version too old (requires 3.9+)")
        all_ok = False

    if not llm_keys or not any(llm_keys.values()):
        print("⚠ No LLM providers configured")
        all_ok = False

    if all_ok:
        print("✅ All core features working!")
    else:
        print("⚠ Some features need configuration")

    print("=" * 60)


def test_llm_connections():
    """Test LLM provider connections."""
    print("\n\nTesting LLM Connections...\n")

    llm_keys = detect_llm_keys()

    for provider, available in llm_keys.items():
        if available:
            print(f"Testing {provider.capitalize()}...", end=" ", flush=True)
            success, message = test_llm_connection(provider)
            if success:
                print(f"✓ {message}")
            else:
                print(f"✗ {message}")


if __name__ == "__main__":
    try:
        test_detections()
        test_llm_connections()

        print("\n✅ All tests passed!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
