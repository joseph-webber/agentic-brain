# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Persona-Driven Installer for Agentic Brain
==========================================

Interactive installer that guides users through persona-based setup.
Everything flows from persona selection:

1. User picks a persona (or install type)
2. ADL is generated from persona template
3. All config files are generated from ADL
4. Router templates and modes are configured

Simple and clean - no backward compatibility needed.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

from .adl.generator import generate_config_from_adl
from .adl.parser import parse_adl_string
from .adl.personas import (
    PERSONA_TEMPLATES,
    generate_adl_from_persona,
    get_persona_mode,
)


def clear_screen():
    """Clear terminal screen."""
    os.system("clear" if os.name == "posix" else "cls")


def print_header(text: str):
    """Print a styled header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_step(number: int, text: str):
    """Print a numbered step."""
    print(f"\n✨ Step {number}: {text}")
    print("-" * 70)


def ask_choice(question: str, choices: List[str], default: Optional[int] = None) -> str:
    """Ask user to pick from a list of choices."""
    print(f"\n{question}\n")

    for i, choice in enumerate(choices, 1):
        prefix = "→" if default == i else " "
        print(f"  {prefix} {i}. {choice}")

    if default:
        prompt = f"\nChoice [1-{len(choices)}] (default {default}): "
    else:
        prompt = f"\nChoice [1-{len(choices)}]: "

    while True:
        response = input(prompt).strip()

        # Use default if provided and user just hits enter
        if not response and default:
            return choices[default - 1]

        try:
            idx = int(response)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
        except ValueError:
            pass

        print(f"❌ Please enter a number between 1 and {len(choices)}")


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    suffix = " [Y/n]" if default else " [y/N]"
    response = input(f"\n{question}{suffix}: ").strip().lower()

    if not response:
        return default

    return response in ["y", "yes"]


def run_simple_install():
    """Simple installation - pick persona and go."""
    print_step(1, "Choose Your Persona")

    # Build persona choices
    personas = []
    descriptions = []
    for name, template in PERSONA_TEMPLATES.items():
        personas.append(name)
        descriptions.append(f"{template.name} - {template.description}")

    choice = ask_choice(
        "What type of assistant do you want?",
        descriptions,
        default=1,  # Professional is default
    )

    # Extract persona name from choice
    persona_name = choice.split(" - ")[0].lower()

    # Find matching persona
    selected_persona = None
    for name, template in PERSONA_TEMPLATES.items():
        if template.name.lower() == persona_name:
            selected_persona = name
            break

    if not selected_persona:
        print(f"❌ Error: Could not find persona for '{persona_name}'")
        sys.exit(1)

    print(f"\n✅ Selected: {PERSONA_TEMPLATES[selected_persona].name}")
    print(f"   {PERSONA_TEMPLATES[selected_persona].description}")

    # Step 2: Confirm and generate
    print_step(2, "Generate Configuration")

    if not ask_yes_no("Generate configuration files from this persona?"):
        print("\n❌ Installation cancelled.")
        return False

    # Generate ADL from persona
    try:
        adl_content = generate_adl_from_persona(selected_persona)

        # Write ADL file
        adl_path = Path.cwd() / "brain.adl"
        adl_path.write_text(adl_content)
        print("\n✅ Created: brain.adl")

        # Parse and generate config files
        config = parse_adl_string(adl_content)
        result = generate_config_from_adl(config, output_dir=Path.cwd())

        print("✅ Generated configuration files:")
        print(f"   - {result.config_module}")
        print(f"   - {result.env_file}")
        print(f"   - {result.docker_compose}")

        # Set default mode
        mode_code = get_persona_mode(selected_persona)
        print(f"\n✅ Default mode set to: {mode_code}")

        return True

    except Exception as e:
        print(f"\n❌ Error generating configuration: {e}")
        return False


def run_advanced_install():
    """Advanced installation - manual ADL editing."""
    print_step(1, "Create Default ADL File")

    # Ask which persona to start with
    personas = list(PERSONA_TEMPLATES.keys())
    descriptions = [
        f"{PERSONA_TEMPLATES[p].name} - {PERSONA_TEMPLATES[p].description}"
        for p in personas
    ]

    choice = ask_choice(
        "Start with which persona template?",
        descriptions + ["Blank - I'll write my own"],
        default=1,
    )

    adl_path = Path.cwd() / "brain.adl"

    if "Blank" in choice:
        # Create minimal blank ADL
        adl_content = """application AgenticBrain {
  name "My AI Assistant"
  version "1.0.0"
}

llm Primary {
  provider ollama
  model "llama3.2:3b"
  temperature 0.7
  maxTokens 2048
}

modes {
  default free
  routing simple
}
"""
        adl_path.write_text(adl_content)
        print(f"\n✅ Created blank ADL: {adl_path}")
    else:
        # Extract persona name
        persona_name = choice.split(" - ")[0].lower()
        selected_persona = None
        for name, template in PERSONA_TEMPLATES.items():
            if template.name.lower() == persona_name:
                selected_persona = name
                break

        if selected_persona:
            adl_content = generate_adl_from_persona(selected_persona)
            adl_path.write_text(adl_content)
            print(f"\n✅ Created ADL from {selected_persona} persona: {adl_path}")

    print_step(2, "Edit Your ADL File")
    print(f"\nEdit {adl_path} to customize your configuration.")
    print("When done, run: agentic adl generate")

    if ask_yes_no("Open in editor now?", default=False):
        editor = os.environ.get("EDITOR", "nano")
        os.system(f"{editor} {adl_path}")

        print("\n✅ ADL file ready for generation.")

        if ask_yes_no("Generate config files now?"):
            try:
                config = parse_adl_string(adl_path.read_text())
                result = generate_config_from_adl(config, output_dir=Path.cwd())
                print("\n✅ Generated configuration files:")
                print(f"   - {result.config_module}")
                print(f"   - {result.env_file}")
                print(f"   - {result.docker_compose}")
                return True
            except Exception as e:
                print(f"\n❌ Error: {e}")
                return False

    return True


def run_installer():
    """Main installer entry point."""
    clear_screen()

    print(
        """
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║                    🧠 Agentic Brain Setup                         ║
║                                                                   ║
║            Persona-driven AI assistant configuration              ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""
    )

    print("\nWelcome! This installer will help you set up Agentic Brain.")
    print("We'll configure everything based on your use case.\n")

    # Step 0: Choose install type
    install_type = ask_choice(
        "How would you like to install?",
        [
            "Simple (recommended) - Pick a persona, we handle the rest",
            "Advanced - Manually configure ADL file",
        ],
        default=1,
    )

    success = False
    if "Simple" in install_type:
        success = run_simple_install()
    else:
        success = run_advanced_install()

    if success:
        print_header("🎉 Installation Complete!")
        print(
            """
Your Agentic Brain is ready to use!

Next steps:
  1. Review generated files (brain.adl, adl_config.py, .env)
  2. Install dependencies: pip install -e .
  3. Start chatting: python -m agentic_brain.chat

Documentation: https://github.com/joseph-webber/agentic-brain
"""
        )
        return True
    else:
        print_header("❌ Installation Failed")
        print("\nPlease check the errors above and try again.")
        return False


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Agentic Brain Persona-Driven Installer"
    )
    parser.add_argument(
        "--persona",
        choices=list(PERSONA_TEMPLATES.keys()),
        help="Skip interactive mode and use this persona",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Generate config without prompts (requires --persona)",
    )

    args = parser.parse_args()

    if args.non_interactive:
        if not args.persona:
            print("❌ Error: --non-interactive requires --persona")
            sys.exit(1)

        # Non-interactive install
        print(f"🧠 Generating config for {args.persona} persona...")
        try:
            adl_content = generate_adl_from_persona(args.persona)
            adl_path = Path.cwd() / "brain.adl"
            adl_path.write_text(adl_content)

            config = parse_adl_string(adl_content)
            result = generate_config_from_adl(config, output_dir=Path.cwd())

            print(f"✅ Created: {adl_path}")
            print(f"✅ Generated: {result.config_module}")
            print(f"✅ Generated: {result.env_file}")
            print(f"✅ Generated: {result.docker_compose}")

            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    elif args.persona:
        # Interactive with pre-selected persona
        print(f"🧠 Using {args.persona} persona...")
        # Still show confirmation
        if not ask_yes_no(f"Generate {args.persona} configuration?", default=True):
            print("❌ Cancelled.")
            sys.exit(1)

        try:
            adl_content = generate_adl_from_persona(args.persona)
            adl_path = Path.cwd() / "brain.adl"
            adl_path.write_text(adl_content)

            config = parse_adl_string(adl_content)
            result = generate_config_from_adl(config, output_dir=Path.cwd())

            print("\n✅ Installation complete!")
            print(f"   Created: {adl_path}")
            print("   Generated configuration files")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)
    else:
        # Fully interactive
        success = run_installer()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
