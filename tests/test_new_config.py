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

"""Tests for agentic_brain.cli.new_config module.

Critical tests for the configuration wizard that runs during `agentic new-config`.
Includes regression tests for questionary style compatibility.
"""

import importlib

import pytest

MODULES = [
    "agentic_brain.cli.new_config",
]


def test_module_imports():
    """Test module can be imported."""
    for module_path in MODULES:
        module = importlib.import_module(module_path)
        assert module is not None


def test_basic_functionality():
    """Test basic functionality placeholder."""
    assert MODULES


class TestWizardStyle:
    """Tests for WIZARD_STYLE questionary compatibility.

    Regression tests for: https://github.com/joseph-webber/agentic-brain/issues/XX
    Bug: questionary 2.1.1 passes style class names as kwargs to PromptSession.
    The 'instruction' style name was being interpreted as a keyword argument,
    causing: PromptSession.__init__() got an unexpected keyword argument 'instruction'
    """

    def test_wizard_style_no_instruction_key(self):
        """CRITICAL: Ensure WIZARD_STYLE does not contain 'instruction' style.

        The 'instruction' style class causes questionary autocomplete() to crash
        because it gets passed as a kwarg to prompt_toolkit's PromptSession.
        """
        from agentic_brain.cli.new_config import WIZARD_STYLE

        if WIZARD_STYLE is None:
            pytest.skip("questionary not installed")

        # Get all style class names from the style
        style_dict = dict(WIZARD_STYLE.style_rules)

        # CRITICAL: 'instruction' must NOT be in the style
        assert "instruction" not in style_dict, (
            "WIZARD_STYLE contains 'instruction' style which causes "
            "PromptSession.__init__() crash in questionary 2.1.1. "
            "Remove this style class to fix the bug."
        )

    def test_wizard_style_has_required_classes(self):
        """Ensure WIZARD_STYLE has all required style classes for questionary."""
        from agentic_brain.cli.new_config import WIZARD_STYLE

        if WIZARD_STYLE is None:
            pytest.skip("questionary not installed")

        style_dict = dict(WIZARD_STYLE.style_rules)

        # These are the safe style classes that questionary expects
        required_classes = ["qmark", "question", "answer", "pointer", "highlighted"]

        for cls in required_classes:
            assert cls in style_dict, f"Missing required style class: {cls}"

    def test_wizard_style_with_autocomplete(self):
        """Test that WIZARD_STYLE works with questionary.autocomplete().

        This is the actual function that was crashing on Windows.
        We can't fully test interactive prompts, but we can verify the
        style object is compatible with autocomplete's internals.
        """
        try:
            import questionary
            from questionary import Style
        except ImportError:
            pytest.skip("questionary not installed")

        from agentic_brain.cli.new_config import WIZARD_STYLE

        if WIZARD_STYLE is None:
            pytest.skip("questionary Style not available")

        # Create an autocomplete question (don't run it, just validate construction)
        # This will fail at construction time if style has invalid keys
        try:
            q = questionary.autocomplete(
                message="Test prompt",
                choices=["option1", "option2", "option3"],
                style=WIZARD_STYLE,
            )
            # If we get here, the style is compatible
            assert q is not None
        except TypeError as e:
            if "instruction" in str(e):
                pytest.fail(
                    f"WIZARD_STYLE causes autocomplete crash: {e}. "
                    "Remove 'instruction' from style classes."
                )
            raise


class TestTemplates:
    """Tests for configuration templates."""

    def test_templates_defined(self):
        """Ensure all templates are properly defined."""
        from agentic_brain.cli.new_config import TEMPLATES

        assert "minimal" in TEMPLATES
        assert "retail" in TEMPLATES
        assert "support" in TEMPLATES
        assert "enterprise" in TEMPLATES

    def test_template_structure(self):
        """Ensure templates have required fields."""
        from agentic_brain.cli.new_config import TEMPLATES

        for name, template in TEMPLATES.items():
            assert "name" in template, f"Template {name} missing 'name'"
            assert "description" in template, f"Template {name} missing 'description'"
            assert "features" in template, f"Template {name} missing 'features'"
            assert isinstance(
                template["features"], list
            ), f"Template {name} features should be list"


class TestLLMProviders:
    """Tests for LLM provider definitions."""

    def test_providers_defined(self):
        """Ensure all LLM providers are defined."""
        from agentic_brain.cli.new_config import LLM_PROVIDERS

        # Core providers that must exist
        assert "ollama" in LLM_PROVIDERS
        assert "openai" in LLM_PROVIDERS
        assert "anthropic" in LLM_PROVIDERS

    def test_provider_structure(self):
        """Ensure providers have required fields."""
        from agentic_brain.cli.new_config import LLM_PROVIDERS

        for name, provider in LLM_PROVIDERS.items():
            assert "name" in provider, f"Provider {name} missing 'name'"
            assert "description" in provider, f"Provider {name} missing 'description'"
            assert "requires_key" in provider, f"Provider {name} missing 'requires_key'"
            assert "models" in provider, f"Provider {name} missing 'models'"
            assert (
                "default_model" in provider
            ), f"Provider {name} missing 'default_model'"
            assert isinstance(
                provider["models"], list
            ), f"Provider {name} models should be list"
            assert (
                provider["default_model"] in provider["models"]
            ), f"Provider {name} default_model not in models list"

    def test_ollama_no_key_required(self):
        """Ollama should not require an API key (it's local)."""
        from agentic_brain.cli.new_config import LLM_PROVIDERS

        assert LLM_PROVIDERS["ollama"]["requires_key"] is False

    def test_cloud_providers_require_key(self):
        """Cloud providers should require API keys."""
        from agentic_brain.cli.new_config import LLM_PROVIDERS

        cloud_providers = ["openai", "anthropic", "openrouter", "groq", "google"]

        for provider in cloud_providers:
            if provider in LLM_PROVIDERS:
                assert (
                    LLM_PROVIDERS[provider]["requires_key"] is True
                ), f"Cloud provider {provider} should require API key"
