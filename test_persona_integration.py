#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Test persona-driven ADL integration.

Verifies:
1. Persona templates exist and are valid ADL
2. ADL parsing works for all personas
3. Config generation works
4. Mode mapping is correct
"""

import sys
import tempfile
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentic_brain.adl.personas import (
    PERSONA_TEMPLATES,
    list_personas,
    generate_adl_from_persona,
    get_persona_mode,
)
from agentic_brain.adl.parser import parse_adl
from agentic_brain.adl.generator import generate_config_from_adl


def test_persona_templates():
    """Test that all persona templates are valid."""
    print("Testing persona templates...")

    for name, template in PERSONA_TEMPLATES.items():
        print(f"  ✓ {name}: {template.description}")

        # Verify required fields
        assert template.name, f"{name} missing name"
        assert template.description, f"{name} missing description"
        assert template.adl_content, f"{name} missing ADL content"
        assert template.mode_code, f"{name} missing mode code"

    print(f"✅ All {len(PERSONA_TEMPLATES)} persona templates valid\n")


def test_adl_parsing():
    """Test that all persona ADL can be parsed."""
    print("Testing ADL parsing...")

    for name in PERSONA_TEMPLATES.keys():
        adl_content = generate_adl_from_persona(name)

        try:
            config = parse_adl(adl_content)
            print(f"  ✓ {name}: parsed successfully")

            # Verify basic structure
            assert config.application is not None, f"{name} missing application block"
            assert len(config.llms) > 0, f"{name} missing LLM blocks"

        except Exception as e:
            print(f"  ✗ {name}: FAILED - {e}")
            raise

    print(f"✅ All personas parsed successfully\n")


def test_config_generation():
    """Test that config files can be generated."""
    print("Testing config generation...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Test with professional persona
        adl_content = generate_adl_from_persona("professional")
        config = parse_adl(adl_content)

        result = generate_config_from_adl(config, output_dir, overwrite=True)

        # Verify files were created
        assert result.config_module.exists(), "Config module not created"
        assert result.env_file.exists(), "Env file not created"
        assert result.docker_compose.exists(), "Docker compose not created"

        print(f"  ✓ Generated:")
        print(f"    - {result.config_module.name}")
        print(f"    - {result.env_file.name}")
        print(f"    - {result.docker_compose.name}")
        print(f"    - {result.api_module.name}")

        # Check env file has expected content
        env_content = result.env_file.read_text()
        assert "LLM_DEFAULT_PROVIDER" in env_content, "Missing LLM provider"
        assert "LLM_DEFAULT_MODEL" in env_content, "Missing LLM model"

    print("✅ Config generation successful\n")


def test_mode_mapping():
    """Test that persona modes map correctly."""
    print("Testing mode mapping...")

    expected_modes = {
        "professional": "B",
        "technical": "D",
        "creative": "CR",
        "accessibility": "H",
        "research": "R",
        "minimal": "F",
    }

    for persona, expected_mode in expected_modes.items():
        actual_mode = get_persona_mode(persona)
        assert (
            actual_mode == expected_mode
        ), f"{persona} mode mismatch: expected {expected_mode}, got {actual_mode}"
        print(f"  ✓ {persona} → {actual_mode}")

    print("✅ Mode mapping correct\n")


def test_list_personas():
    """Test listing personas."""
    print("Testing persona listing...")

    personas = list_personas()
    assert len(personas) >= 6, "Expected at least 6 personas"

    for name, description in personas.items():
        print(f"  ✓ {name}: {description}")

    print(f"✅ Listed {len(personas)} personas\n")


def main():
    """Run all tests."""
    print("=" * 70)
    print("PERSONA-DRIVEN ADL INTEGRATION TEST")
    print("=" * 70 + "\n")

    try:
        test_persona_templates()
        test_adl_parsing()
        test_config_generation()
        test_mode_mapping()
        test_list_personas()

        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        return 0

    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
