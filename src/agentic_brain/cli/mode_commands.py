# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Mode CLI Commands for Agentic Brain
====================================

Commands for managing the 42 operational modes:
- mode list     - List all modes with short codes
- mode switch   - Switch to a mode by code
- mode current  - Show current active mode
- mode wizard   - Interactive mode selection
- mode info     - Show detailed mode information
"""

import argparse
import sys
from typing import Optional


# Colors for terminal output
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"


def supports_color() -> bool:
    """Check if terminal supports color output."""
    import os

    if os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


# Disable colors if not supported
if not supports_color():
    for attr in dir(Colors):
        if not attr.startswith("_"):
            setattr(Colors, attr, "")


def print_header(text: str) -> None:
    """Print a colored header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}→ {text}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {text}", file=sys.stderr)


def mode_list_command(args: argparse.Namespace) -> int:
    """
    List all 42 available modes with their short codes.

    Displays modes organized by category (USER, INDUSTRY, ARCHITECTURE,
    COMPLIANCE, POWER) with their codes for quick switching.
    """
    try:
        from agentic_brain.modes.manager import get_manager

        manager = get_manager()
        current = manager.current()
        current_name = current.name if current else None

        print_header("Agentic Brain Modes (42 total)")

        modes_by_cat = manager.list_by_category()

        for category, modes in modes_by_cat.items():
            # Category header
            cat_color = {
                "user": Colors.GREEN,
                "industry": Colors.BLUE,
                "architecture": Colors.MAGENTA,
                "compliance": Colors.YELLOW,
                "power": Colors.RED,
            }.get(category, Colors.CYAN)

            print(f"{cat_color}{Colors.BOLD}{category.upper()}{Colors.RESET}")
            print("-" * 50)

            for mode in modes:
                # Mark current mode
                marker = "→" if mode.name == current_name else " "
                active = Colors.GREEN if mode.name == current_name else ""

                # Format: [CODE] Name - Description
                print(
                    f"  {active}{marker} [{Colors.CYAN}{mode.code:5}{Colors.RESET}] "
                    f"{active}{mode.name:15}{Colors.RESET} - {Colors.DIM}{mode.description[:40]}{Colors.RESET}"
                )
            print()

        print(f"{Colors.DIM}Use 'ab mode switch <CODE>' to change modes{Colors.RESET}")
        print(
            f"{Colors.DIM}Use 'ab mode info <CODE>' for detailed information{Colors.RESET}\n"
        )

        return 0

    except Exception as e:
        print_error(f"Failed to list modes: {e}")
        return 1


def mode_switch_command(args: argparse.Namespace) -> int:
    """
    Switch to a mode by its short code or name.

    Example: ab mode switch MED  (switches to Medical mode)
    """
    try:
        from agentic_brain.modes.manager import get_manager

        manager = get_manager()
        code = args.code

        # Check if mode exists
        if not manager.exists(code):
            print_error(f"Mode not found: {code}")
            print_info("Use 'ab mode list' to see available modes")
            return 1

        # Get mode info before switch
        mode = manager.get(code)
        old_mode = manager.current()
        old_name = old_mode.name if old_mode else "None"

        # Perform the switch
        transition = manager.switch(
            code, announce=not args.quiet if hasattr(args, "quiet") else True
        )

        if transition.success:
            print_success(f"Switched from {old_name} → {mode.name}")
            print(f"  {Colors.DIM}Code: {mode.code}{Colors.RESET}")
            print(f"  {Colors.DIM}Category: {mode.category.value}{Colors.RESET}")
            print(
                f"  {Colors.DIM}Switch time: {transition.duration_ms:.2f}ms{Colors.RESET}"
            )
            return 0
        else:
            print_error(f"Switch failed: {transition.error}")
            return 1

    except Exception as e:
        print_error(f"Failed to switch mode: {e}")
        return 1


def mode_current_command(args: argparse.Namespace) -> int:
    """
    Show the current active mode with details.
    """
    try:
        from agentic_brain.modes.manager import get_manager

        manager = get_manager()
        mode = manager.current()

        if not mode:
            print_warning("No mode currently active")
            print_info("Use 'ab mode switch <CODE>' to activate a mode")
            return 0

        print_header("Current Mode")

        print(
            f"  {Colors.BOLD}Name:{Colors.RESET}        {Colors.GREEN}{mode.name}{Colors.RESET}"
        )
        print(
            f"  {Colors.BOLD}Code:{Colors.RESET}        {Colors.CYAN}{mode.code}{Colors.RESET}"
        )
        print(f"  {Colors.BOLD}Category:{Colors.RESET}    {mode.category.value}")
        print(f"  {Colors.BOLD}Description:{Colors.RESET} {mode.description}")
        print(f"  {Colors.BOLD}Icon:{Colors.RESET}        {mode.icon}")
        print()

        # Show key settings
        print(
            f"  {Colors.BOLD}LLM Model:{Colors.RESET}   {mode.config.llm.primary_model}"
        )
        print(
            f"  {Colors.BOLD}RAG Type:{Colors.RESET}    {mode.config.rag.rag_type.value}"
        )
        print(
            f"  {Colors.BOLD}Security:{Colors.RESET}    {mode.config.security.level.value}"
        )
        print(
            f"  {Colors.BOLD}Voice:{Colors.RESET}       {mode.config.voice.primary_voice}"
        )
        print()

        return 0

    except Exception as e:
        print_error(f"Failed to get current mode: {e}")
        return 1


def mode_info_command(args: argparse.Namespace) -> int:
    """
    Show detailed information about a specific mode.

    Example: ab mode info MED
    """
    try:
        from agentic_brain.modes.manager import get_manager

        manager = get_manager()
        code = args.code

        if not manager.exists(code):
            print_error(f"Mode not found: {code}")
            print_info("Use 'ab mode list' to see available modes")
            return 1

        mode = manager.get(code)
        current = manager.current()
        is_active = current and current.name == mode.name

        print_header(f"{mode.icon} {mode.name} Mode")

        if is_active:
            print(f"  {Colors.GREEN}[ACTIVE]{Colors.RESET}\n")

        # Basic info
        print(
            f"  {Colors.BOLD}Code:{Colors.RESET}        {Colors.CYAN}{mode.code}{Colors.RESET}"
        )
        print(f"  {Colors.BOLD}Category:{Colors.RESET}    {mode.category.value}")
        print(f"  {Colors.BOLD}Version:{Colors.RESET}     {mode.version}")
        print(f"  {Colors.BOLD}Description:{Colors.RESET} {mode.description}")
        print()

        # LLM Config
        print(f"{Colors.BOLD}LLM Configuration:{Colors.RESET}")
        llm = mode.config.llm
        print(f"  Primary Model:    {llm.primary_model}")
        print(f"  Fallback Model:   {llm.fallback_model}")
        print(f"  Local Model:      {llm.local_model}")
        print(f"  Temperature:      {llm.temperature}")
        print(f"  Max Tokens:       {llm.max_tokens}")
        print(f"  Context Window:   {llm.context_window:,}")
        print()

        # RAG Config
        print(f"{Colors.BOLD}RAG Configuration:{Colors.RESET}")
        rag = mode.config.rag
        print(f"  RAG Type:         {rag.rag_type.value}")
        print(f"  Neo4j Enabled:    {rag.neo4j_enabled}")
        print(f"  Vector DB:        {rag.vector_db}")
        print(f"  Embedding Model:  {rag.embedding_model}")
        print(f"  Top K:            {rag.top_k}")
        print(f"  Graph Depth:      {rag.graph_depth}")
        print()

        # Security Config
        print(f"{Colors.BOLD}Security Configuration:{Colors.RESET}")
        sec = mode.config.security
        print(f"  Level:            {sec.level.value}")
        print(f"  Encryption:       {sec.encryption_required}")
        print(f"  Audit Logging:    {sec.audit_logging}")
        print(f"  PII Detection:    {sec.pii_detection}")
        print(f"  Air Gapped:       {sec.air_gapped}")
        print()

        # Voice Config
        print(f"{Colors.BOLD}Voice Configuration:{Colors.RESET}")
        voice = mode.config.voice
        print(f"  Enabled:          {voice.enabled}")
        print(f"  Primary Voice:    {voice.primary_voice}")
        print(f"  Speech Rate:      {voice.speech_rate}")
        print(f"  Announce Changes: {voice.announce_mode_changes}")
        print()

        # Compliance
        if mode.config.compliance.frameworks:
            print(f"{Colors.BOLD}Compliance:{Colors.RESET}")
            print(f"  Frameworks:       {', '.join(mode.config.compliance.frameworks)}")
            if mode.config.compliance.data_residency:
                print(f"  Data Residency:   {mode.config.compliance.data_residency}")
            print()

        # Features
        print(f"{Colors.BOLD}Features:{Colors.RESET}")
        features = mode.config.features
        enabled = [k for k, v in features.items() if v]
        disabled = [k for k, v in features.items() if not v]
        print(f"  Enabled:  {', '.join(enabled) if enabled else 'None'}")
        print(f"  Disabled: {', '.join(disabled) if disabled else 'None'}")
        print()

        return 0

    except Exception as e:
        print_error(f"Failed to get mode info: {e}")
        return 1


def mode_wizard_command(args: argparse.Namespace) -> int:
    """
    Interactive wizard for selecting the right mode.

    Guides users through choosing the appropriate mode based on
    their use case, industry, and requirements.
    """
    try:
        from agentic_brain.modes.base import ModeCategory
        from agentic_brain.modes.manager import get_manager

        manager = get_manager()

        print_header("Mode Selection Wizard")
        print("Let's find the right mode for you!\n")

        # Step 1: Category selection
        categories = {
            "1": ("USER", "Personal, Developer, Business, Enterprise"),
            "2": ("INDUSTRY", "Medical, Legal, Banking, Education, etc."),
            "3": ("ARCHITECTURE", "Monolith, Microservices, Edge, etc."),
            "4": ("COMPLIANCE", "HIPAA, GDPR, SOX, APRA"),
            "5": ("POWER", "Turbo, Maximum (highest performance)"),
        }

        print(f"{Colors.BOLD}Step 1: What type of mode do you need?{Colors.RESET}\n")
        for key, (name, desc) in categories.items():
            print(f"  [{key}] {Colors.CYAN}{name:12}{Colors.RESET} - {desc}")
        print()

        try:
            choice = input(f"{Colors.BOLD}Enter choice (1-5): {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            print_info("Wizard cancelled")
            return 0

        if choice not in categories:
            print_error("Invalid choice")
            return 1

        category_name = categories[choice][0].lower()

        # Get modes for this category
        modes_by_cat = manager.list_by_category()
        category_modes = modes_by_cat.get(category_name, [])

        if not category_modes:
            print_error(f"No modes found for category: {category_name}")
            return 1

        # Step 2: Mode selection within category
        print(f"\n{Colors.BOLD}Step 2: Choose a mode:{Colors.RESET}\n")

        for i, mode in enumerate(category_modes, 1):
            print(
                f"  [{i}] {Colors.CYAN}{mode.code:5}{Colors.RESET} {mode.name:15} - {mode.description[:45]}"
            )
        print()

        try:
            mode_choice = input(
                f"{Colors.BOLD}Enter choice (1-{len(category_modes)}): {Colors.RESET}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            print_info("Wizard cancelled")
            return 0

        try:
            mode_idx = int(mode_choice) - 1
            if mode_idx < 0 or mode_idx >= len(category_modes):
                raise ValueError()
            selected_mode = category_modes[mode_idx]
        except ValueError:
            print_error("Invalid choice")
            return 1

        # Step 3: Confirm and switch
        print(
            f"\n{Colors.BOLD}Selected: {selected_mode.icon} {selected_mode.name}{Colors.RESET}"
        )
        print(f"  {selected_mode.description}\n")

        try:
            confirm = input("Switch to this mode? [Y/n]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            print_info("Wizard cancelled")
            return 0

        if confirm in ("", "y", "yes"):
            transition = manager.switch(selected_mode.code)
            if transition.success:
                print_success(f"Switched to {selected_mode.name} mode!")
                print(
                    f"  {Colors.DIM}Switch time: {transition.duration_ms:.2f}ms{Colors.RESET}\n"
                )
                return 0
            else:
                print_error(f"Switch failed: {transition.error}")
                return 1
        else:
            print_info("Mode not changed")
            return 0

    except Exception as e:
        print_error(f"Wizard failed: {e}")
        return 1


def mode_stats_command(args: argparse.Namespace) -> int:
    """
    Show mode manager statistics.
    """
    try:
        from agentic_brain.modes.manager import get_manager

        manager = get_manager()
        stats = manager.stats()

        print_header("Mode Manager Statistics")

        print(
            f"  {Colors.BOLD}Current Mode:{Colors.RESET}      {stats['current_mode'] or 'None'}"
        )
        print(f"  {Colors.BOLD}Total Modes:{Colors.RESET}       {stats['total_modes']}")
        print(
            f"  {Colors.BOLD}Total Switches:{Colors.RESET}    {stats['total_switches']}"
        )
        print(
            f"  {Colors.BOLD}Avg Switch Time:{Colors.RESET}   {stats['avg_switch_time_ms']:.2f}ms"
        )
        print(
            f"  {Colors.BOLD}Min Switch Time:{Colors.RESET}   {stats['min_switch_time_ms']:.2f}ms"
        )
        print(
            f"  {Colors.BOLD}Max Switch Time:{Colors.RESET}   {stats['max_switch_time_ms']:.2f}ms"
        )
        print()

        # Mode counts by category
        print(f"{Colors.BOLD}Modes by Category:{Colors.RESET}")
        for cat, count in stats["mode_counts"].items():
            print(f"  {cat:15} {count}")
        print()

        # Recent transitions
        if stats["recent_transitions"]:
            print(f"{Colors.BOLD}Recent Transitions:{Colors.RESET}")
            for t in stats["recent_transitions"]:
                status = Colors.GREEN + "✓" if t["success"] else Colors.RED + "✗"
                print(
                    f"  {status}{Colors.RESET} {t['from'] or 'None'} → {t['to']} ({t['duration_ms']:.2f}ms)"
                )
            print()

        return 0

    except Exception as e:
        print_error(f"Failed to get stats: {e}")
        return 1


def mode_command(args: argparse.Namespace) -> int:
    """
    Main mode command dispatcher.

    Routes to subcommands: list, switch, current, info, wizard, stats
    """
    # Default to list if no subcommand
    subcommand = getattr(args, "mode_subcommand", None)

    if subcommand is None or subcommand == "list":
        return mode_list_command(args)
    elif subcommand == "switch":
        return mode_switch_command(args)
    elif subcommand == "current":
        return mode_current_command(args)
    elif subcommand == "info":
        return mode_info_command(args)
    elif subcommand == "wizard":
        return mode_wizard_command(args)
    elif subcommand == "stats":
        return mode_stats_command(args)
    else:
        print_error(f"Unknown mode subcommand: {subcommand}")
        return 1
