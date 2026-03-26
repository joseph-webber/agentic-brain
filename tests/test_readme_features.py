# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
import re
from pathlib import Path

import pytest

README_PATH = Path(__file__).parent.parent / "README.md"


@pytest.fixture
def readme_content():
    return README_PATH.read_text()


class TestReadmeFeatures:
    """Ensure all major features are prominently displayed on homepage"""

    def test_readme_exists(self):
        assert README_PATH.exists(), "README.md must exist"

    def test_graphrag_featured(self, readme_content):
        """GraphRAG must be prominently featured"""
        assert "GraphRAG" in readme_content or "graphrag" in readme_content.lower()
        assert "177" in readme_content or "loaders" in readme_content.lower()

    def test_smart_router_featured(self, readme_content):
        """Smart LLM Router must be featured"""
        assert "Smart" in readme_content and "Router" in readme_content

    def test_hardware_acceleration_featured(self, readme_content):
        """Hardware acceleration must be highlighted"""
        assert "MLX" in readme_content or "Apple Silicon" in readme_content
        assert "CUDA" in readme_content
        assert "ROCm" in readme_content

    def test_personas_featured(self, readme_content):
        """Persona system must be featured"""
        assert "persona" in readme_content.lower()
        assert "industry" in readme_content.lower() or "mode" in readme_content.lower()

    def test_ethics_module_featured(self, readme_content):
        """Ethics module must be mentioned"""
        assert "ethics" in readme_content.lower() or "safety" in readme_content.lower()

    def test_authentication_featured(self, readme_content):
        """Authentication options must be listed"""
        assert "auth" in readme_content.lower()
        assert "JWT" in readme_content or "OAuth" in readme_content

    def test_event_streaming_featured(self, readme_content):
        """Event streaming must be mentioned"""
        assert "Kafka" in readme_content or "Redpanda" in readme_content

    def test_llm_providers_featured(self, readme_content):
        """LLM providers must be listed"""
        providers = ["OpenAI", "Anthropic", "Claude", "Groq", "Ollama", "Gemini"]
        found = sum(1 for p in providers if p in readme_content)
        assert (
            found >= 3
        ), f"At least 3 LLM providers should be mentioned, found {found}"

    def test_installation_section_exists(self, readme_content):
        """Installation instructions must exist"""
        assert "pip install" in readme_content or "Installation" in readme_content

    def test_quick_start_exists(self, readme_content):
        """Quick start section must exist"""
        assert "Quick Start" in readme_content or "Getting Started" in readme_content

    def test_python_version_correct(self, readme_content):
        """Python version badge must show 3.11+"""
        assert "3.11" in readme_content
        assert (
            "3.10" not in readme_content
            or "3.10" in readme_content
            and "not" in readme_content.lower()
        )

    def test_diagrams_present(self, readme_content):
        """Architecture diagrams must be present"""
        # Check for Mermaid or ASCII diagrams
        has_mermaid = "```mermaid" in readme_content
        has_ascii = "┌" in readme_content or "╔" in readme_content
        assert has_mermaid or has_ascii, "Must have architecture diagrams"

    def test_no_broken_badges(self, readme_content):
        """Check for broken badge URLs"""
        # Look for badge patterns
        badge_pattern = r"\[!\[.*?\]\(.*?\)\]"
        badges = re.findall(badge_pattern, readme_content)
        # All badges should have valid URLs (not placeholder)
        for badge in badges:
            assert "TODO" not in badge
            assert "PLACEHOLDER" not in badge
