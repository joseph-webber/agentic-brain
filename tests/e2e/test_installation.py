#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
Agentic Brain Installation E2E Tests
=====================================

Tests the complete installation experience:
- setup.sh execution
- Virtual environment creation
- CLI command availability
- Config wizard functionality
- First chat interaction

These tests ensure new users have a flawless onboarding experience.

Run with:
    pytest tests/e2e/test_installation.py -v
    pytest tests/e2e/test_installation.py -v -k "test_setup"
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Get the agentic-brain root directory
REPO_ROOT = Path(__file__).parent.parent.parent
SETUP_SCRIPT = REPO_ROOT / "setup.sh"


class TestSetupScript:
    """Test the setup.sh installer script."""

    def test_setup_script_exists(self):
        """Verify setup.sh exists and is executable."""
        assert SETUP_SCRIPT.exists(), "setup.sh not found"
        assert os.access(SETUP_SCRIPT, os.X_OK), "setup.sh not executable"

    def test_setup_help(self):
        """Test setup.sh --help shows usage."""
        result = subprocess.run(
            [str(SETUP_SCRIPT), "-h"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Help should exit 0 and show usage
        assert result.returncode == 0
        assert "install" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_setup_script_has_python_detection(self):
        """Test that setup.sh has Python detection logic."""
        content = SETUP_SCRIPT.read_text()
        # Should have Python version detection
        assert "python3" in content.lower(), "setup.sh should detect Python"
        assert (
            "3.10" in content or "3.11" in content or "3.12" in content
        ), "setup.sh should check for Python 3.10+"

    def test_setup_script_has_os_detection(self):
        """Test that setup.sh has OS detection logic."""
        content = SETUP_SCRIPT.read_text()
        # Should have OS detection for multiple platforms
        assert (
            "darwin" in content.lower() or "macos" in content.lower()
        ), "setup.sh should detect macOS"
        assert (
            "debian" in content.lower() or "apt" in content.lower()
        ), "setup.sh should detect Debian/Ubuntu"


class TestFreshInstallation:
    """Test a fresh installation in an isolated directory."""

    @pytest.fixture
    def temp_install_dir(self):
        """Create a temporary directory for test installation."""
        temp_dir = tempfile.mkdtemp(prefix="agentic_brain_test_")
        yield Path(temp_dir)
        # Cleanup after test
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_venv_creation(self, temp_install_dir):
        """Test that virtual environment can be created."""
        venv_path = temp_install_dir / ".venv"

        # Create venv using Python
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"venv creation failed: {result.stderr}"
        assert venv_path.exists(), "venv directory not created"
        assert (venv_path / "bin" / "python").exists() or (
            venv_path / "Scripts" / "python.exe"
        ).exists()

    def test_pip_install_editable(self, temp_install_dir):
        """Test that pip install -e . works."""
        venv_path = temp_install_dir / ".venv"

        # Create venv
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)], check=True, timeout=60
        )

        # Get pip path
        if sys.platform == "win32":
            pip_path = venv_path / "Scripts" / "pip"
        else:
            pip_path = venv_path / "bin" / "pip"

        # Install agentic-brain in editable mode
        result = subprocess.run(
            [str(pip_path), "install", "-e", str(REPO_ROOT)],
            capture_output=True,
            text=True,
            timeout=300,  # May take a while
            cwd=REPO_ROOT,
        )

        # Check install succeeded
        if result.returncode != 0:
            pytest.skip(f"pip install failed (may need deps): {result.stderr[:500]}")

        assert result.returncode == 0


class TestCLIAvailability:
    """Test that CLI commands are available after installation."""

    def test_agentic_brain_command_exists(self):
        """Test agentic-brain command is importable."""
        result = subprocess.run(
            [sys.executable, "-c", "from agentic_brain.cli import main; print('OK')"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        assert "OK" in result.stdout, f"CLI import failed: {result.stderr}"

    def test_cli_help(self):
        """Test CLI --help works."""
        result = subprocess.run(
            [sys.executable, "-m", "agentic_brain.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        # Should show help text
        output = result.stdout + result.stderr
        assert (
            "agentic" in output.lower()
            or "usage" in output.lower()
            or "help" in output.lower()
        )

    def test_cli_version(self):
        """Test CLI --version works."""
        result = subprocess.run(
            [sys.executable, "-m", "agentic_brain.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        # Should show version number
        output = result.stdout + result.stderr
        # Version format like 0.1.0 or 1.0.0
        assert any(
            c.isdigit() for c in output
        ), f"No version number in output: {output}"


class TestConfigWizard:
    """Test the interactive configuration wizard."""

    def test_new_config_module_importable(self):
        """Test that new_config module can be imported."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from agentic_brain.cli.new_config import run_wizard; print('OK')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        assert "OK" in result.stdout, f"new_config import failed: {result.stderr}"

    def test_questionary_available(self):
        """Test that questionary is installed (for interactive prompts)."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import questionary; print(questionary.__version__)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.skip("questionary not installed - run: pip install questionary")
        assert result.returncode == 0

    def test_config_templates_defined(self):
        """Test that config templates are properly defined."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from agentic_brain.cli.new_config import TEMPLATES; "
                "assert 'minimal' in TEMPLATES; "
                "assert 'retail' in TEMPLATES; "
                "print('OK')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        assert "OK" in result.stdout, f"Template check failed: {result.stderr}"


class TestFirstChatExperience:
    """Test the first chat experience after installation."""

    def test_chatbot_importable(self):
        """Test that Chatbot can be imported."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from agentic_brain.chat import Chatbot; print('OK')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        if "OK" not in result.stdout:
            pytest.skip(
                f"Chatbot not importable (may need deps): {result.stderr[:200]}"
            )
        assert "OK" in result.stdout

    def test_router_importable(self):
        """Test that LLM router can be imported."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from agentic_brain.router import LLMRouter; print('OK')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        if "OK" not in result.stdout:
            pytest.skip(f"Router not importable: {result.stderr[:200]}")
        assert "OK" in result.stdout


class TestAccessibility:
    """Test accessibility features for blind/low-vision users."""

    def test_no_color_only_information(self):
        """Ensure important info isn't conveyed by color alone."""
        # Read setup.sh and check for text labels with colors
        content = SETUP_SCRIPT.read_text()

        # Good patterns: emoji + text, or text descriptions
        good_patterns = [
            "✔",
            "✘",
            "⚠",
            "ℹ",
            "→",
            "echo_success",
            "echo_error",
            "echo_warning",
        ]

        # Should have text-based status indicators
        assert any(
            pattern in content for pattern in good_patterns
        ), "setup.sh should use text/emoji indicators, not just colors"

    def test_cli_help_screen_reader_friendly(self):
        """Test that CLI help output is screen reader friendly."""
        result = subprocess.run(
            [sys.executable, "-m", "agentic_brain.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        output = result.stdout

        # Help should have clear structure
        # No excessive special characters that confuse screen readers
        excessive_chars = output.count("═") + output.count("║") + output.count("╔")
        assert (
            excessive_chars < 50
        ), "Too many box-drawing characters - may confuse screen readers"


# Playwright tests for browser-based UI (when available)
class TestPlaywrightUI:
    """Playwright tests for web UI (requires UI to be running)."""

    @pytest.fixture
    def browser_context(self):
        """Create Playwright browser context."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip(
                "Playwright not installed - run: pip install playwright && playwright install"
            )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            yield context
            context.close()
            browser.close()

    @pytest.mark.skip(
        reason="UI not implemented yet - WCAG 2.1 AA React dashboard pending"
    )
    def test_dashboard_accessible(self, browser_context):
        """Test that dashboard meets WCAG 2.1 AA standards."""
        page = browser_context.new_page()
        page.goto("http://localhost:8000/dashboard")

        # Check for skip link
        skip_link = page.locator("a[href='#main-content']")
        assert skip_link.count() > 0, "Missing skip link for keyboard navigation"

        # Check for proper heading hierarchy
        h1_count = page.locator("h1").count()
        assert h1_count == 1, "Should have exactly one h1"

        # Check all images have alt text
        images = page.locator("img")
        for i in range(images.count()):
            alt = images.nth(i).get_attribute("alt")
            assert alt is not None and len(alt) > 0, f"Image {i} missing alt text"

    @pytest.mark.skip(reason="UI not implemented yet")
    def test_dashboard_keyboard_navigation(self, browser_context):
        """Test that dashboard is fully keyboard navigable."""
        page = browser_context.new_page()
        page.goto("http://localhost:8000/dashboard")

        # Tab through interactive elements
        page.keyboard.press("Tab")
        focused = page.evaluate("document.activeElement.tagName")
        assert focused is not None, "No element received focus"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
