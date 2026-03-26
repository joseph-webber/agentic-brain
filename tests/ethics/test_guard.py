# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
"""Tests for ethics guard."""

import pytest

from agentic_brain.ethics import EthicsGuard, check_content


class TestEthicsGuard:
    """Test the ethics guard content checker."""

    def test_clean_content_passes(self):
        """Clean content should pass."""
        result = check_content("Hello, how are you?", channel="teams")
        assert result.safe is True
        assert len(result.blocked_reasons) == 0

    def test_email_address_blocked(self):
        """Email addresses should be blocked."""
        result = check_content("Contact me at test@example.com", channel="github")
        assert result.safe is False
        assert any("email" in r.lower() for r in result.blocked_reasons)

    def test_api_key_blocked(self):
        """API keys should be blocked."""
        result = check_content(
            "Use key sk-abc123def456ghi789jkl012mno345pqr", channel="docs"
        )
        assert result.safe is False
        assert any("api key" in r.lower() for r in result.blocked_reasons)

    def test_unprofessional_words_flagged(self):
        """Unprofessional words should be flagged in work channels."""
        result = check_content("This is stupid and dumb", channel="teams", strict=False)
        assert len(result.warnings) > 0

    def test_unprofessional_blocked_in_strict_mode(self):
        """Unprofessional words should be blocked in strict mode."""
        result = check_content("This is stupid", channel="teams", strict=True)
        assert result.safe is False

    def test_professional_content_passes(self):
        """Professional content passes all checks."""
        content = "The implementation is complete. Please review the pull request."
        result = check_content(content, channel="jira")
        assert result.safe is True


class TestEthicsGuardPatterns:
    """Test specific pattern detection."""

    def test_github_token_detected(self):
        """GitHub tokens should be detected."""
        result = check_content(
            "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", channel="docs"
        )
        assert result.safe is False

    def test_aws_key_detected(self):
        """AWS keys should be detected."""
        result = check_content("AKIAIOSFODNN7EXAMPLE", channel="docs")
        assert result.safe is False

    def test_localhost_warning(self):
        """Localhost should trigger warning."""
        guard = EthicsGuard(strict_mode=False)
        result = guard.check("Connect to localhost:8080", channel="docs")
        assert len(result.warnings) > 0
