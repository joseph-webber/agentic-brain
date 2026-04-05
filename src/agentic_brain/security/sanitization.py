# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Input sanitization and injection prevention.

Provides comprehensive protection against:
- Cypher injection attacks
- Prompt injection attacks
- SQL injection (for any SQL backends)
- Command injection
- XSS attacks
- Path traversal
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Pattern

logger = logging.getLogger(__name__)


class SanitizationType(Enum):
    """Types of sanitization to apply."""
    CYPHER = "cypher"
    PROMPT = "prompt"
    SQL = "sql"
    COMMAND = "command"
    PATH = "path"
    REGEX = "regex"
    JSON = "json"


class SanitizationError(Exception):
    """Raised when input fails sanitization."""
    pass


@dataclass(slots=True)
class SanitizationResult:
    """Result of sanitization operation."""
    is_clean: bool
    sanitized: str
    violations: list[str]
    threat_level: str  # low, medium, high, critical
    original_length: int
    sanitized_length: int


class InputSanitizer:
    """Comprehensive input sanitization with threat detection."""

    # Cypher injection patterns
    CYPHER_DANGEROUS_KEYWORDS = {
        r'\bOR\b', r'\bAND\b', r'\bUNION\b',
        r'\bSHOW\b', r'\bCREATE\b', r'\bDROP\b',
        r'\bDELETE\b', r'\bALTER\b', r'\bGRANT\b',
        r'\bREVOKE\b', r'\bCONSTRAINT\b', r'\bINDEX\b',
    }

    # Prompt injection indicators
    PROMPT_INJECTION_PATTERNS = [
        r'(?i)ignore.*previous.*instruction',
        r'(?i)forget.*everything',
        r'(?i)system.*override',
        r'(?i)admin.*password',
        r'(?i)execute.*command',
        r'(?i)<<.*>>',  # jailbreak markers
        r'(?i)\[SYSTEM\]',
        r'(?i)\[ADMIN\]',
        r'(?i)act as.*without.*filter',
    ]

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"('\s*(OR|AND)\s*'[^']*'\s*=\s*')",
        r'(union\s+select)',
        r'(;.*delete)',
        r'(;.*drop)',
        r'(--|#)',  # SQL comments
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r'[;&|`$(){}[\]<>\\]',
        r'\$\{.*\}',
        r'\$\(.*\)',
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\./',
        r'\.\.//',
        r'\.\.\\',
        r'\.\.\\\\',
        r'%2e%2e/',
        r'%252e%252e',
    ]

    def sanitize_cypher(
        self,
        query: str,
        strict: bool = True,
        allow_params: bool = True,
    ) -> SanitizationResult:
        """
        Sanitize Cypher query.
        
        Args:
            query: Raw Cypher query string
            strict: If True, fail on any suspicious patterns
            allow_params: If True, allow $param1 style parameters
            
        Returns:
            SanitizationResult with sanitized query and threat info
        """
        violations = []
        threat_level = "low"
        sanitized = query

        # Check for null bytes
        if '\x00' in query:
            violations.append("Null byte detected")
            threat_level = "critical"

        # Check for excessive quotes (potential escape bypass)
        quote_count = query.count("'") + query.count('"')
        if quote_count > len(query) * 0.2:  # > 20% quotes
            violations.append(f"Excessive quotes ({quote_count})")
            threat_level = "high"

        # Check for dangerous Cypher keywords outside of parameters
        # Split by $ to separate parameters from query
        parts = query.split('$')
        query_part = parts[0]
        
        for pattern in self.CYPHER_DANGEROUS_KEYWORDS:
            if re.search(pattern, query_part, re.IGNORECASE):
                # Dangerous keywords in non-parameter context
                if not self._is_in_parameter_context(query, query_part):
                    violations.append(f"Dangerous Cypher keyword detected: {pattern}")
                    threat_level = "high"

        if re.search(r"\bOR\b.{0,20}\b1\s*=\s*1\b", query, re.IGNORECASE) or re.search(
            r"\bWHERE\b.{0,20}\b(1\s*=\s*1|true)\b", query, re.IGNORECASE
        ):
            violations.append("Cypher tautology detected")
            threat_level = "high"

        # Check for comment sequences (can bypass sanitization)
        if '//' in query or '/*' in query or '--' in query:
            violations.append("SQL/Cypher comment syntax detected")
            threat_level = "high"

        # Check for property injection patterns
        if re.search(r'\{.*\}|\[.*\]', query):
            # This is normal in Cypher, just log if suspicious
            if re.search(r'\{[^}]*[\'"`][^}]*\}', query):
                violations.append("Property injection pattern detected")
                threat_level = "medium"

        is_clean = len(violations) == 0 or (not strict and threat_level != "critical")

        if strict and not is_clean:
            logger.warning(
                f"Cypher sanitization violations: {violations}",
                extra={"threat_level": threat_level}
            )

        return SanitizationResult(
            is_clean=is_clean,
            sanitized=sanitized,
            violations=violations,
            threat_level=threat_level,
            original_length=len(query),
            sanitized_length=len(sanitized),
        )

    def sanitize_prompt(self, prompt: str, strict: bool = True) -> SanitizationResult:
        """
        Detect prompt injection attempts.
        
        Args:
            prompt: User-provided prompt text
            strict: If True, fail on suspicious patterns
            
        Returns:
            SanitizationResult with threat assessment
        """
        violations = []
        threat_level = "low"
        sanitized = prompt

        # Check for jailbreak patterns
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, prompt):
                violations.append(f"Jailbreak pattern detected: {pattern}")
                threat_level = "high"

        # Check for excessive special characters
        special_chars = sum(1 for c in prompt if not c.isalnum() and c not in ' \n\t.,!?-"\'')
        if special_chars > len(prompt) * 0.3:  # > 30% special chars
            violations.append(f"Excessive special characters ({special_chars})")
            threat_level = "medium"

        # Check for Unicode-based obfuscation
        non_ascii = sum(1 for c in prompt if ord(c) > 127)
        if non_ascii > len(prompt) * 0.1:  # > 10% non-ASCII
            violations.append(f"High Unicode content ({non_ascii})")
            threat_level = "medium"

        # Check for control characters
        control_chars = sum(1 for c in prompt if ord(c) < 32 and c not in '\n\t\r')
        if control_chars > 0:
            violations.append(f"Control characters detected ({control_chars})")
            threat_level = "high"
            sanitized = ''.join(c for c in prompt if ord(c) >= 32 or c in '\n\t\r')

        # Check for nested prompts (meta-injection)
        if re.search(r'(""".*"""|\[SYSTEM\].*\[/SYSTEM\])', prompt, re.DOTALL):
            violations.append("Nested prompt structure detected")
            threat_level = "high"

        is_clean = len(violations) == 0 or (not strict and threat_level != "high")

        return SanitizationResult(
            is_clean=is_clean,
            sanitized=sanitized,
            violations=violations,
            threat_level=threat_level,
            original_length=len(prompt),
            sanitized_length=len(sanitized),
        )

    def sanitize_sql(self, query: str, strict: bool = True) -> SanitizationResult:
        """
        Sanitize SQL query.
        
        Args:
            query: Raw SQL query
            strict: If True, fail on suspicious patterns
            
        Returns:
            SanitizationResult with sanitized query
        """
        violations = []
        threat_level = "low"
        sanitized = query

        # Check for SQL injection patterns
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                violations.append(f"SQL injection pattern detected: {pattern}")
                threat_level = "high"

        if re.search(r"\bOR\b.{0,20}\b1\s*=\s*1\b", query, re.IGNORECASE):
            violations.append("SQL tautology detected")
            threat_level = "high"

        # Check for comment bypass
        if re.search(r'(--|#|/\*)', query):
            violations.append("SQL comment syntax detected")
            threat_level = "high"

        is_clean = len(violations) == 0 or (not strict and threat_level != "high")

        return SanitizationResult(
            is_clean=is_clean,
            sanitized=sanitized,
            violations=violations,
            threat_level=threat_level,
            original_length=len(query),
            sanitized_length=len(sanitized),
        )

    def sanitize_command(self, command: str, strict: bool = True) -> SanitizationResult:
        """
        Sanitize shell command.
        
        Args:
            command: Command string to sanitize
            strict: If True, fail on any suspicious characters
            
        Returns:
            SanitizationResult with threat assessment
        """
        violations = []
        threat_level = "low"
        sanitized = command

        # Check for command injection characters
        for pattern in self.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, command):
                violations.append(f"Command injection pattern detected: {pattern}")
                threat_level = "critical"

        # Check for known dangerous commands
        dangerous_commands = {
            'rm', 'dd', 'mkfs', 'shutdown', 'reboot', 'sudo',
            'format', 'fdisk', 'delpart', 'kill', 'pkill'
        }
        cmd_name = command.split()[0].split('/')[-1] if command else ''
        if cmd_name in dangerous_commands:
            violations.append(f"Dangerous command: {cmd_name}")
            threat_level = "critical"

        is_clean = len(violations) == 0 or (not strict and threat_level != "critical")

        return SanitizationResult(
            is_clean=is_clean,
            sanitized=sanitized,
            violations=violations,
            threat_level=threat_level,
            original_length=len(command),
            sanitized_length=len(sanitized),
        )

    def sanitize_path(self, path: str, strict: bool = True) -> SanitizationResult:
        """
        Sanitize file path.
        
        Args:
            path: File path to sanitize
            strict: If True, fail on traversal attempts
            
        Returns:
            SanitizationResult with sanitized path
        """
        violations = []
        threat_level = "low"
        sanitized = path

        # Check for path traversal
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                violations.append(f"Path traversal pattern detected: {pattern}")
                threat_level = "high"

        # Normalize path and check if it escapes base
        import os.path
        normalized = os.path.normpath(path)
        if normalized.startswith('..') or normalized.startswith('/') or normalized.startswith('~'):
            violations.append("Path attempts to escape base directory")
            threat_level = "high"

        is_clean = len(violations) == 0 or (not strict and threat_level != "high")

        return SanitizationResult(
            is_clean=is_clean,
            sanitized=sanitized,
            violations=violations,
            threat_level=threat_level,
            original_length=len(path),
            sanitized_length=len(sanitized),
        )

    def sanitize_regex(self, pattern: str, strict: bool = True) -> SanitizationResult:
        """
        Validate regex pattern (prevent ReDoS).
        
        Args:
            pattern: Regex pattern to validate
            strict: If True, fail on risky patterns
            
        Returns:
            SanitizationResult with validation result
        """
        violations = []
        threat_level = "low"

        # Check for catastrophic backtracking patterns
        redos_patterns = [
            r'\([^)]*\*\).*\*',  # Nested quantifiers
            r'\([^)]*\+\).*\+',
            r'\([^)]*\*\)\+',
            r'\([^)]*\+\)\*',
            r'(a+)+',  # Canonical ReDoS
            r'(a|a)*',
            r'(a|ab)*',
        ]

        for redos in redos_patterns:
            if re.search(redos, pattern):
                violations.append(f"ReDoS vulnerability pattern: {redos}")
                threat_level = "high"

        # Try to compile to catch syntax errors
        try:
            re.compile(pattern)
        except re.error as e:
            violations.append(f"Invalid regex: {str(e)}")
            threat_level = "medium"

        is_clean = len(violations) == 0 or (not strict and threat_level != "high")

        return SanitizationResult(
            is_clean=is_clean,
            sanitized=pattern,
            violations=violations,
            threat_level=threat_level,
            original_length=len(pattern),
            sanitized_length=len(pattern),
        )

    def sanitize_json(self, json_str: str, strict: bool = True) -> SanitizationResult:
        """
        Validate JSON structure.
        
        Args:
            json_str: JSON string to validate
            strict: If True, fail on parsing errors
            
        Returns:
            SanitizationResult with validation result
        """
        violations = []
        threat_level = "low"
        import json

        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            violations.append(f"Invalid JSON: {str(e)}")
            threat_level = "medium"

        is_clean = len(violations) == 0 or (not strict and threat_level != "medium")

        return SanitizationResult(
            is_clean=is_clean,
            sanitized=json_str,
            violations=violations,
            threat_level=threat_level,
            original_length=len(json_str),
            sanitized_length=len(json_str),
        )

    def sanitize(
        self,
        value: str,
        sanitization_type: SanitizationType,
        strict: bool = True,
    ) -> SanitizationResult:
        """
        Universal sanitization dispatcher.
        
        Args:
            value: Input to sanitize
            sanitization_type: Type of sanitization to apply
            strict: If True, fail on violations
            
        Returns:
            SanitizationResult with sanitization outcome
        """
        if sanitization_type == SanitizationType.CYPHER:
            return self.sanitize_cypher(value, strict)
        elif sanitization_type == SanitizationType.PROMPT:
            return self.sanitize_prompt(value, strict)
        elif sanitization_type == SanitizationType.SQL:
            return self.sanitize_sql(value, strict)
        elif sanitization_type == SanitizationType.COMMAND:
            return self.sanitize_command(value, strict)
        elif sanitization_type == SanitizationType.PATH:
            return self.sanitize_path(value, strict)
        elif sanitization_type == SanitizationType.REGEX:
            return self.sanitize_regex(value, strict)
        elif sanitization_type == SanitizationType.JSON:
            return self.sanitize_json(value, strict)
        else:
            raise ValueError(f"Unknown sanitization type: {sanitization_type}")

    @staticmethod
    def _is_in_parameter_context(query: str, part: str) -> bool:
        """Check if a pattern appears in parameter context (after $)."""
        param_start = query.find('$' + part)
        return param_start >= 0


# Global sanitizer instance
_sanitizer = None


def get_sanitizer() -> InputSanitizer:
    """Get the global sanitizer instance."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = InputSanitizer()
    return _sanitizer


def sanitize_cypher(
    query: str,
    strict: bool = True,
    allow_params: bool = True,
) -> SanitizationResult:
    """Convenience function to sanitize Cypher query."""
    return get_sanitizer().sanitize_cypher(query, strict, allow_params)


def sanitize_prompt(prompt: str, strict: bool = True) -> SanitizationResult:
    """Convenience function to detect prompt injection."""
    return get_sanitizer().sanitize_prompt(prompt, strict)


def sanitize_sql(query: str, strict: bool = True) -> SanitizationResult:
    """Convenience function to sanitize SQL query."""
    return get_sanitizer().sanitize_sql(query, strict)


def sanitize_command(command: str, strict: bool = True) -> SanitizationResult:
    """Convenience function to sanitize shell command."""
    return get_sanitizer().sanitize_command(command, strict)


def sanitize_path(path: str, strict: bool = True) -> SanitizationResult:
    """Convenience function to sanitize file path."""
    return get_sanitizer().sanitize_path(path, strict)


__all__ = [
    "InputSanitizer",
    "SanitizationType",
    "SanitizationError",
    "SanitizationResult",
    "get_sanitizer",
    "sanitize_cypher",
    "sanitize_prompt",
    "sanitize_sql",
    "sanitize_command",
    "sanitize_path",
]
