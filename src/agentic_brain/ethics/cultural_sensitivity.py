# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Cultural Sensitivity Module

Provides tools to detect and prevent culturally insensitive content.
Critical for global enterprise, defense, and social influencer audiences.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class SensitivityLevel(Enum):
    """Severity level for cultural sensitivity issues."""

    INFO = "info"  # Educational, no action needed
    WARNING = "warning"  # Review recommended
    BLOCK = "block"  # Must not send


@dataclass
class CulturalIssue:
    """Represents a cultural sensitivity concern."""

    level: SensitivityLevel
    category: str
    description: str
    suggestion: Optional[str] = None
    context: Optional[str] = None


class CulturalSensitivityChecker:
    """
    Checks content for cultural sensitivity issues.

    Designed for global audiences including:
    - Defense and military
    - Enterprise and corporate
    - Social influencers
    - International users

    Zero tolerance for:
    - Religious bias or mockery
    - Political advocacy
    - Cultural stereotypes
    - Racial insensitivity
    - Gender bias
    """

    # Religious terms that should be avoided in professional contexts
    RELIGIOUS_TERMS = {
        "god",
        "jesus",
        "christ",
        "allah",
        "buddha",
        "hindu",
        "muslim",
        "christian",
        "jewish",
        "islam",
        "church",
        "temple",
        "mosque",
        "pray",
        "prayer",
        "worship",
        "holy",
        "sacred",
        "bless",
        "blessed",
        "blessing",
        "amen",
        "hallelujah",
        "praise",
        "salvation",
        "sin",
        "hell",
        "heaven",
    }

    # Political terms that indicate bias
    POLITICAL_TERMS = {
        "liberal",
        "conservative",
        "left-wing",
        "right-wing",
        "democrat",
        "republican",
        "communist",
        "socialist",
        "fascist",
        "patriot",
        "woke",
        "antifa",
        "maga",
    }

    # Cultural stereotypes to avoid
    STEREOTYPE_PATTERNS = [
        (
            r"\b(asians?|chinese|japanese|koreans?)\b.*("
            r"good at math|naturally good at|naturally smart|math geniuses?|math genius|math prodigies?|math whiz(?:zes)?|smart|genius"
            r")",
            "Avoid stereotyping Asians as math geniuses",
        ),
        (
            r"\b(wom[ae]n|female?s)\b.*("
            r"too sensitive|overly sensitive|sensitive|too emotional|so emotional|emotional"
            r")",
            "Avoid gender stereotypes about emotions",
        ),
        (
            r"\b(irish|scottish)\b.*\b(drunk|drinking)\b",
            "Avoid cultural stereotypes about drinking",
        ),
        (r"\b(italian)\b.*\b(mafia|mob)\b", "Avoid Italian mafia stereotypes"),
        (r"\b(jewish)\b.*\b(money|cheap|wealthy)\b", "Avoid antisemitic stereotypes"),
        (
            r"\b(muslim|arab)\b.*\b(terrorist|extremist)\b",
            "Avoid Islamophobic stereotypes",
        ),
        (
            r"\b(african|black)\b.*\b(athletic|sports)\b",
            "Avoid racial stereotypes about athletics",
        ),
        (
            r"\b(indian)\b.*\b(call center|tech support)\b",
            "Avoid cultural stereotypes about jobs",
        ),
    ]

    # Inclusive language suggestions
    INCLUSIVE_ALTERNATIVES = {
        "guys": "everyone / folks / team",
        "mankind": "humanity / humankind",
        "manpower": "workforce / personnel",
        "man-hours": "work-hours / person-hours",
        "chairman": "chairperson / chair",
        "policeman": "police officer",
        "fireman": "firefighter",
        "stewardess": "flight attendant",
        "mailman": "mail carrier",
        "he/she": "they",
        "his/her": "their",
    }

    # Countries and regions (for neutral examples)
    NEUTRAL_EXAMPLES = [
        "Australia",
        "Canada",
        "Japan",
        "Germany",
        "Singapore",
        "South Korea",
        "United Kingdom",
        "New Zealand",
        "Sweden",
        "Norway",
    ]

    def __init__(self, strict_mode: bool = True):
        """
        Initialize cultural sensitivity checker.

        Args:
            strict_mode: If True, warnings become blocks
        """
        self.strict_mode = strict_mode

    def check(self, content: str, context: str = "general") -> List[CulturalIssue]:
        """
        Check content for cultural sensitivity issues.

        Args:
            content: Text to check
            context: Context (e.g., "defense", "enterprise", "social")

        Returns:
            List of cultural issues found
        """
        issues = []

        # Check for religious content (needs original case for display)
        religious_issues = self._check_religious(content)
        issues.extend(religious_issues)

        # Check for political bias
        political_issues = self._check_political(content)
        issues.extend(political_issues)

        # Check for stereotypes
        stereotype_issues = self._check_stereotypes(content)
        issues.extend(stereotype_issues)

        # Check for non-inclusive language
        inclusive_issues = self._check_inclusive_language(content)
        issues.extend(inclusive_issues)

        # In strict mode, escalate warnings to blocks for sensitive contexts
        if self.strict_mode and context in ["defense", "enterprise", "social"]:
            for issue in issues:
                if issue.level == SensitivityLevel.WARNING:
                    issue.level = SensitivityLevel.BLOCK

        return issues

    def _check_religious(self, content: str) -> List[CulturalIssue]:
        """Check for religious content."""
        issues = []

        for term in self.RELIGIOUS_TERMS:
            if re.search(rf"\b{term}\b", content, re.IGNORECASE):
                issues.append(
                    CulturalIssue(
                        level=SensitivityLevel.BLOCK,
                        category="religious",
                        description=f"Contains religious term: '{term}'",
                        suggestion="Remove religious references for global neutrality",
                        context="Religious content may offend non-believers or other faiths",
                    )
                )

        return issues

    def _check_political(self, content: str) -> List[CulturalIssue]:
        """Check for political bias."""
        issues = []

        for term in self.POLITICAL_TERMS:
            if re.search(rf"\b{term}\b", content, re.IGNORECASE):
                issues.append(
                    CulturalIssue(
                        level=SensitivityLevel.BLOCK,
                        category="political",
                        description=f"Contains political term: '{term}'",
                        suggestion="Use neutral language without political alignment",
                        context="Political content may alienate users with different views",
                    )
                )

        return issues

    def _check_stereotypes(self, content: str) -> List[CulturalIssue]:
        """Check for cultural stereotypes."""
        issues = []

        for pattern, suggestion in self.STEREOTYPE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(
                    CulturalIssue(
                        level=SensitivityLevel.BLOCK,
                        category="stereotype",
                        description="Potential cultural stereotype detected",
                        suggestion=suggestion,
                        context="Stereotypes reinforce harmful biases",
                    )
                )

        return issues

    def _check_inclusive_language(self, content: str) -> List[CulturalIssue]:
        """Check for non-inclusive language."""
        issues = []

        for term, alternative in self.INCLUSIVE_ALTERNATIVES.items():
            if re.search(rf"\b{re.escape(term)}\b", content, re.IGNORECASE):
                issues.append(
                    CulturalIssue(
                        level=SensitivityLevel.WARNING,
                        category="inclusive",
                        description=f"Non-inclusive language: '{term}'",
                        suggestion=f"Consider using: {alternative}",
                        context="Inclusive language improves global accessibility",
                    )
                )

        return issues

    def is_safe_for_global_audience(
        self, content: str, context: str = "general"
    ) -> bool:
        """
        Quick check if content is safe for global audiences.

        Args:
            content: Text to check
            context: Context (e.g., "defense", "enterprise", "social")

        Returns:
            True if safe, False if issues found
        """
        issues = self.check(content, context)
        return not any(issue.level == SensitivityLevel.BLOCK for issue in issues)

    def suggest_neutral_example(self, category: str = "country") -> str:
        """
        Get a culturally neutral example.

        Args:
            category: Type of example needed

        Returns:
            Neutral example string
        """
        if category == "country":
            import random

            return random.choice(self.NEUTRAL_EXAMPLES)

        return "Example"


def check_cultural_sensitivity(
    content: str, context: str = "general", strict: bool = True
) -> List[CulturalIssue]:
    """
    Convenience function to check cultural sensitivity.

    Args:
        content: Text to check
        context: Context (e.g., "defense", "enterprise", "social")
        strict: Use strict mode

    Returns:
        List of cultural issues

    Example:
        issues = check_cultural_sensitivity(
            "Hey guys, let's pray for success!",
            context="enterprise"
        )
        # Returns: [CulturalIssue(BLOCK, religious, ...),
        #           CulturalIssue(WARNING, inclusive, ...)]
    """
    checker = CulturalSensitivityChecker(strict_mode=strict)
    return checker.check(content, context)


def is_globally_appropriate(content: str, context: str = "general") -> bool:
    """
    Quick check if content is appropriate for global audiences.

    Args:
        content: Text to check
        context: Context type

    Returns:
        True if appropriate, False otherwise

    Example:
        if is_globally_appropriate(message, context="defense"):
            send_message(message)
        else:
            quarantine_for_review(message)
    """
    checker = CulturalSensitivityChecker(strict_mode=True)
    return checker.is_safe_for_global_audience(content, context)
