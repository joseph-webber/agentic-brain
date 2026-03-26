"""
Ethics Guard - Content checking before external communication.

This module provides tools to check content before sending to external channels.
"""

from dataclasses import dataclass
from typing import Optional, List
import re


@dataclass
class ContentCheckResult:
    """Result of content safety check."""
    safe: bool
    content: str
    warnings: List[str]
    blocked_reasons: List[str]
    channel: str
    
    @property
    def needs_review(self) -> bool:
        """Content has warnings but isn't blocked."""
        return len(self.warnings) > 0 and self.safe


class EthicsGuard:
    """
    Guard that checks content before external communication.
    
    Usage:
        guard = EthicsGuard()
        result = guard.check("Hello world", channel="teams")
        if result.safe:
            send_to_teams(result.content)
    """
    
    # Patterns that should never appear in external content
    BLOCKED_PATTERNS = [
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "email address"),
        (r'sk-[A-Za-z0-9]{32,}', "OpenAI API key"),
        (r'ghp_[A-Za-z0-9]{36}', "GitHub token"),
        (r'xoxb-[A-Za-z0-9-]+', "Slack token"),
        (r'AKIA[0-9A-Z]{16}', "AWS access key"),
    ]
    
    # Patterns that trigger warnings
    WARNING_PATTERNS = [
        (r'\b(password|secret|token|key)\s*[:=]\s*\S+', "possible credential"),
        (r'\b(localhost|127\.0\.0\.1)', "local address"),
    ]
    
    # Words that should be reviewed in professional contexts
    REVIEW_WORDS = [
        "ludicrous", "smash", "trash", "stupid", "dumb", 
        "hate", "kill", "die", "sucks",
    ]
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize the ethics guard.
        
        Args:
            strict_mode: If True, warnings become blocks
        """
        self.strict_mode = strict_mode
    
    def check(self, content: str, channel: str = "general") -> ContentCheckResult:
        """
        Check content for safety issues.
        
        Args:
            content: The content to check
            channel: The target channel (teams, jira, email, github, etc.)
            
        Returns:
            ContentCheckResult with safety assessment
        """
        warnings = []
        blocked_reasons = []
        
        # Check blocked patterns
        for pattern, description in self.BLOCKED_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                blocked_reasons.append(f"Contains {description}")
        
        # Check warning patterns
        for pattern, description in self.WARNING_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(f"May contain {description}")
        
        # Check review words in professional channels
        professional_channels = ["teams", "jira", "email", "github", "linkedin"]
        if channel.lower() in professional_channels:
            for word in self.REVIEW_WORDS:
                if word.lower() in content.lower():
                    warnings.append(f"Contains word '{word}' - review for professionalism")
        
        # In strict mode, warnings become blocks
        if self.strict_mode and warnings:
            blocked_reasons.extend(warnings)
            warnings = []
        
        safe = len(blocked_reasons) == 0
        
        return ContentCheckResult(
            safe=safe,
            content=content,
            warnings=warnings,
            blocked_reasons=blocked_reasons,
            channel=channel,
        )


def check_content(content: str, channel: str = "general", strict: bool = True) -> ContentCheckResult:
    """
    Convenience function to check content safety.
    
    Args:
        content: Content to check
        channel: Target channel
        strict: Use strict mode
        
    Returns:
        ContentCheckResult
    """
    guard = EthicsGuard(strict_mode=strict)
    return guard.check(content, channel)
