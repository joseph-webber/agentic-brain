# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Cultural Sensitivity Tests

Ensures agentic-brain is appropriate for global audiences including:
- Defense and military
- Enterprise and corporate
- Social influencers
- International users

Zero tolerance for offensive content.
"""

import pytest

from agentic_brain.ethics.cultural_sensitivity import (
    CulturalSensitivityChecker,
    SensitivityLevel,
    check_cultural_sensitivity,
    is_globally_appropriate,
)


class TestReligiousNeutrality:
    """Test that religious content is detected and blocked."""

    def test_religious_terms_blocked(self):
        """Religious terms should be blocked in professional contexts."""
        religious_phrases = [
            "Let's pray for success",
            "God willing, this will work",
            "Jesus Christ, that's amazing",
            "Bless this project",
            "Thank Allah for this opportunity",
        ]

        for phrase in religious_phrases:
            issues = check_cultural_sensitivity(phrase, context="enterprise")
            assert any(i.category == "religious" for i in issues)
            assert any(i.level == SensitivityLevel.BLOCK for i in issues)

    def test_secular_alternatives_ok(self):
        """Secular language should pass."""
        secular_phrases = [
            "Hopefully this will work",
            "That's amazing",
            "Thank you for this opportunity",
            "Let's hope for success",
        ]

        for phrase in secular_phrases:
            assert is_globally_appropriate(phrase, context="enterprise")


class TestPoliticalNeutrality:
    """Test that political content is detected and blocked."""

    def test_political_terms_blocked(self):
        """Political terms should be blocked."""
        political_phrases = [
            "The liberal approach is better",
            "Conservative values are important",
            "Left-wing policies won't work",
            "This is a socialist idea",
        ]

        for phrase in political_phrases:
            issues = check_cultural_sensitivity(phrase, context="defense")
            assert any(i.category == "political" for i in issues)
            assert any(i.level == SensitivityLevel.BLOCK for i in issues)

    def test_neutral_policy_discussion_ok(self):
        """Neutral policy discussion should pass."""
        neutral_phrases = [
            "The policy has trade-offs",
            "Multiple perspectives exist",
            "Different approaches are possible",
            "The decision depends on priorities",
        ]

        for phrase in neutral_phrases:
            assert is_globally_appropriate(phrase, context="enterprise")


class TestCulturalStereotypes:
    """Test that cultural stereotypes are detected."""

    def test_asian_math_stereotype_blocked(self):
        """Asian math genius stereotype should be blocked."""
        stereotypes = [
            "Asians are good at math",
            "Chinese people are naturally smart",
            "Japanese employees are math geniuses",
        ]

        for phrase in stereotypes:
            issues = check_cultural_sensitivity(phrase)
            assert any(i.category == "stereotype" for i in issues)

    def test_gender_stereotype_blocked(self):
        """Gender stereotypes should be blocked."""
        stereotypes = [
            "Women are more emotional",
            "Females are too sensitive for this",
        ]

        for phrase in stereotypes:
            issues = check_cultural_sensitivity(phrase)
            assert any(i.category == "stereotype" for i in issues)

    def test_individual_excellence_ok(self):
        """Individual achievements without stereotypes should pass."""
        appropriate_phrases = [
            "Dr. Lee excels at mathematics",
            "Sarah is highly analytical",
            "The team shows great technical skill",
        ]

        for phrase in appropriate_phrases:
            # Should pass - no stereotypes
            issues = check_cultural_sensitivity(phrase)
            stereotype_blocks = [
                i
                for i in issues
                if i.category == "stereotype" and i.level == SensitivityLevel.BLOCK
            ]
            assert len(stereotype_blocks) == 0


class TestInclusiveLanguage:
    """Test that non-inclusive language is detected."""

    def test_gendered_language_warned(self):
        """Non-inclusive gendered language should trigger warnings."""
        gendered_phrases = [
            "Hey guys, let's start the meeting",
            "We need more manpower for this project",
            "The chairman will decide",
        ]

        for phrase in gendered_phrases:
            issues = check_cultural_sensitivity(phrase, strict=False)
            assert any(i.category == "inclusive" for i in issues)

    def test_inclusive_alternatives_ok(self):
        """Inclusive alternatives should pass."""
        inclusive_phrases = [
            "Hey everyone, let's start the meeting",
            "We need more personnel for this project",
            "The chair will decide",
            "They will present their findings",
        ]

        for phrase in inclusive_phrases:
            issues = check_cultural_sensitivity(phrase)
            inclusive_blocks = [
                i
                for i in issues
                if i.category == "inclusive" and i.level == SensitivityLevel.BLOCK
            ]
            assert len(inclusive_blocks) == 0


class TestGlobalAudienceAppropriate:
    """Test the main API for checking global appropriateness."""

    def test_defense_context_strict(self):
        """Defense context should be extremely strict."""
        # Should fail
        assert not is_globally_appropriate(
            "Let's pray this deployment succeeds", context="defense"
        )

        # Should pass
        assert is_globally_appropriate(
            "The deployment is scheduled for 0600 hours", context="defense"
        )

    def test_enterprise_context_strict(self):
        """Enterprise context should be strict."""
        # Should fail
        assert not is_globally_appropriate(
            "The conservative approach is better", context="enterprise"
        )

        # Should pass
        assert is_globally_appropriate(
            "The cautious approach minimizes risk", context="enterprise"
        )

    def test_social_context_strict(self):
        """Social influencer context should be strict."""
        # Should fail
        assert not is_globally_appropriate(
            "Asians are naturally good at this", context="social"
        )

        # Should pass
        assert is_globally_appropriate(
            "This skill requires practice and dedication", context="social"
        )


class TestStrictMode:
    """Test strict mode escalation."""

    def test_warnings_become_blocks_in_strict_defense(self):
        """In strict mode + defense context, warnings become blocks."""
        checker = CulturalSensitivityChecker(strict_mode=True)
        issues = checker.check("Hey guys, let's review this", context="defense")

        # In strict defense mode, even inclusive language warnings block
        assert any(
            i.level == SensitivityLevel.BLOCK and i.category == "inclusive"
            for i in issues
        )

    def test_warnings_stay_warnings_in_lenient_general(self):
        """In lenient mode + general context, warnings stay warnings."""
        checker = CulturalSensitivityChecker(strict_mode=False)
        issues = checker.check("Hey guys, let's review this", context="general")

        # In lenient general mode, inclusive language is just a warning
        inclusive_issues = [i for i in issues if i.category == "inclusive"]
        if inclusive_issues:
            assert all(i.level == SensitivityLevel.WARNING for i in inclusive_issues)


class TestNeutralExamples:
    """Test neutral example generation."""

    def test_neutral_country_examples(self):
        """Neutral country examples should be globally safe."""
        checker = CulturalSensitivityChecker()

        for _ in range(10):
            country = checker.suggest_neutral_example("country")
            assert country in checker.NEUTRAL_EXAMPLES

    def test_neutral_examples_diverse(self):
        """Neutral examples should be geographically diverse."""
        checker = CulturalSensitivityChecker()

        # Check we have representation from multiple continents
        examples = set(checker.NEUTRAL_EXAMPLES)

        # Should include Asian countries
        assert any(c in ["Japan", "South Korea", "Singapore"] for c in examples)

        # Should include European countries
        assert any(
            c in ["Germany", "Sweden", "Norway", "United Kingdom"] for c in examples
        )

        # Should include Oceania
        assert any(c in ["Australia", "New Zealand"] for c in examples)

        # Should include North America
        assert "Canada" in examples


class TestRealWorldExamples:
    """Test with real-world content examples."""

    def test_jira_comment_professional(self):
        """JIRA comments should be professional and neutral."""
        good_comment = """
        Completed code review. Found 3 issues:
        1. SQL injection risk in user input
        2. Missing error handling
        3. Performance concern with nested loops

        Please address these before merging.
        """
        assert is_globally_appropriate(good_comment, context="enterprise")

    def test_teams_message_professional(self):
        """Teams messages should be professional and inclusive."""
        good_message = "Hi team, the deployment is scheduled for tomorrow at 10 AM. Please ensure all tests pass before then."
        assert is_globally_appropriate(good_message, context="enterprise")

    def test_pr_description_neutral(self):
        """PR descriptions should be neutral and technical."""
        good_pr = """
        ## Changes
        - Added authentication middleware
        - Implemented rate limiting
        - Updated documentation

        ## Testing
        - All unit tests pass
        - Manual testing completed
        """
        assert is_globally_appropriate(good_pr, context="enterprise")


@pytest.mark.integration
class TestEthicsIntegration:
    """Test integration with existing ethics system."""

    def test_cultural_sensitivity_with_ethics_guard(self):
        """Cultural sensitivity should work with ethics guard."""
        from agentic_brain.ethics import check_content

        # Content with both credential and cultural issue
        bad_content = "Contact me at user@example.com and pray for success"

        # Ethics guard should catch credential
        ethics_result = check_content(bad_content, channel="teams")
        assert not ethics_result.safe

        # Cultural sensitivity should catch religious content
        cultural_issues = check_cultural_sensitivity(bad_content, context="enterprise")
        assert any(i.category == "religious" for i in cultural_issues)
