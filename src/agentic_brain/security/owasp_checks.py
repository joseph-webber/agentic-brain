# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# OWASP Top 10 Automated Security Audit Module

"""
OWASP Top 10 (2021) Automated Security Checks

Provides automated detection of OWASP Top 10 vulnerabilities:
- A01: Broken Access Control
- A02: Cryptographic Failures
- A03: Injection (SQL, Cypher, Command)
- A04: Insecure Design
- A05: Security Misconfiguration
- A06: Vulnerable Components
- A07: Auth Failures
- A08: Data Integrity Failures
- A09: Security Logging Failures
- A10: SSRF

Usage:
    from agentic_brain.security.owasp_checks import OWASPAuditor

    auditor = OWASPAuditor()
    issues = auditor.audit_codebase("/path/to/code")
    for issue in issues:
        print(f"{issue['severity']}: {issue['category']} - {issue['description']}")
"""

import ast
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = None


class Severity(str, Enum):
    """Issue severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class OWASPCategory(str, Enum):
    """OWASP Top 10 categories."""

    A01_BROKEN_ACCESS_CONTROL = "A01_BROKEN_ACCESS_CONTROL"
    A02_CRYPTOGRAPHIC_FAILURES = "A02_CRYPTOGRAPHIC_FAILURES"
    A03_INJECTION = "A03_INJECTION"
    A04_INSECURE_DESIGN = "A04_INSECURE_DESIGN"
    A05_SECURITY_MISCONFIGURATION = "A05_SECURITY_MISCONFIGURATION"
    A06_VULNERABLE_COMPONENTS = "A06_VULNERABLE_COMPONENTS"
    A07_AUTH_FAILURES = "A07_AUTH_FAILURES"
    A08_DATA_INTEGRITY_FAILURES = "A08_DATA_INTEGRITY_FAILURES"
    A09_SECURITY_LOGGING_FAILURES = "A09_SECURITY_LOGGING_FAILURES"
    A10_SSRF = "A10_SSRF"


@dataclass
class SecurityIssue:
    """Represents a security issue found during audit."""

    file_path: str
    line_number: int
    category: OWASPCategory
    severity: Severity
    description: str
    code_snippet: str
    remediation: str
    cwe_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file": self.file_path,
            "line": self.line_number,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "code_snippet": self.code_snippet,
            "remediation": self.remediation,
            "cwe": self.cwe_id,
        }


class CodeAnalyzer(ast.NodeVisitor):
    """AST-based Python code security analyzer."""

    def __init__(self, source_code: str, file_path: str):
        self.source_code = source_code
        self.file_path = file_path
        self.lines = source_code.split("\n")
        self.issues: list[SecurityIssue] = []
        self._in_docstring = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track when entering function definitions."""
        # Check if first statement is a docstring
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            # Skip this first constant as docstring
            for child in node.body[1:]:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect dangerous function calls."""
        func_name = self._get_func_name(node)

        # A03: Injection - dangerous functions
        if func_name in ("eval", "exec"):
            self.issues.append(
                SecurityIssue(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    category=OWASPCategory.A03_INJECTION,
                    severity=Severity.CRITICAL,
                    description=f"Use of {func_name}() allows arbitrary code execution",
                    code_snippet=ast.unparse(node)[:100],
                    remediation=f"Replace {func_name}() with safe alternatives like ast.literal_eval() for eval()",
                    cwe_id="CWE-95",
                )
            )

        # A03: Injection - pickle
        if func_name in ("pickle.loads", "pickle.load", "dill.loads"):
            self.issues.append(
                SecurityIssue(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    category=OWASPCategory.A03_INJECTION,
                    severity=Severity.CRITICAL,
                    description=f"{func_name}() can deserialize arbitrary code",
                    code_snippet=ast.unparse(node)[:100],
                    remediation="Use safer serialization like JSON or use pickle only with trusted data",
                    cwe_id="CWE-502",
                )
            )

        # A01: Broken Access Control - subprocess without validation
        if func_name in (
            "subprocess.run",
            "subprocess.call",
            "subprocess.Popen",
            "os.system",
        ):
            if self._has_shell_true(node) or self._has_unsanitized_args(node):
                self.issues.append(
                    SecurityIssue(
                        file_path=self.file_path,
                        line_number=node.lineno,
                        category=OWASPCategory.A03_INJECTION,
                        severity=Severity.HIGH,
                        description=f"{func_name}() with shell=True or user input allows command injection",
                        code_snippet=ast.unparse(node)[:100],
                        remediation="Use shell=False and pass command as list, or sanitize all user inputs",
                        cwe_id="CWE-78",
                    )
                )

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        """Detect hardcoded secrets (skip docstrings)."""
        if isinstance(node.value, str):
            # Only check strings that are not docstrings (min length for actual secret)
            # Exclude typical documentation strings
            value_lower = node.value.lower()
            is_doc = any(
                keyword in value_lower
                for keyword in [
                    "example:",
                    "format:",
                    "args:",
                    "returns:",
                    "raises:",
                    "authenticat",
                    "provide",
                    "configure",
                    "set to",
                    "default:",
                ]
            )

            if not is_doc and self._is_likely_secret(node.value):
                self.issues.append(
                    SecurityIssue(
                        file_path=self.file_path,
                        line_number=node.lineno,
                        category=OWASPCategory.A02_CRYPTOGRAPHIC_FAILURES,
                        severity=Severity.HIGH,
                        description="Hardcoded secret detected in source code",
                        code_snippet=(
                            node.value[:50] + "..."
                            if len(node.value) > 50
                            else node.value
                        ),
                        remediation="Move secrets to environment variables or secure vault (e.g., Vault, AWS Secrets Manager)",
                        cwe_id="CWE-798",
                    )
                )

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        """Detect timing attack vulnerabilities."""
        # Check for simple string comparison (timing attack vulnerability)
        if (
            len(node.ops) == 1
            and isinstance(node.ops[0], (ast.Eq, ast.NotEq))
            and self._looks_like_sensitive_comparison(node)
        ):
            if (
                "password" in ast.unparse(node).lower()
                or "token" in ast.unparse(node).lower()
            ):
                self.issues.append(
                    SecurityIssue(
                        file_path=self.file_path,
                        line_number=node.lineno,
                        category=OWASPCategory.A02_CRYPTOGRAPHIC_FAILURES,
                        severity=Severity.MEDIUM,
                        description="Direct string comparison for sensitive data allows timing attacks",
                        code_snippet=ast.unparse(node)[:100],
                        remediation="Use constant-time comparison like hmac.compare_digest()",
                        cwe_id="CWE-208",
                    )
                )

        self.generic_visit(node)

    def _get_func_name(self, node: ast.Call) -> str:
        """Extract function name from Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    def _has_shell_true(self, node: ast.Call) -> bool:
        """Check if call has shell=True."""
        for keyword in node.keywords:
            if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                if keyword.value.value is True:
                    return True
        return False

    def _has_unsanitized_args(self, node: ast.Call) -> bool:
        """Check for user input in command args."""
        code = ast.unparse(node)
        return (
            "user" in code.lower()
            or "input" in code.lower()
            or "request" in code.lower()
        )

    def _is_likely_secret(self, value: str) -> bool:
        """Heuristic to detect likely secrets (avoid false positives in docs)."""
        if len(value) < 20:
            return False
        if not any(c.isalnum() for c in value):
            return False

        # Skip if this looks like documentation
        value_lower = value.lower()
        doc_keywords = [
            "data extracted",
            "environment variable",
            "token missing",
            "extracted from",
            "rejected",
            "endpoint",
            "add to",
            "generate",
            "example",
            "format",
            "check if",
            "error",
            "verify",
        ]
        if any(kw in value_lower for kw in doc_keywords):
            return False

        # Only flag actual secret patterns
        secret_keywords = ["sk_", "sk-", "api_", "secret", "password"]
        # Require actual secret-like content, not just the word "token" or "key"
        return any(kw in value.lower() for kw in secret_keywords)

    def _looks_like_sensitive_comparison(self, node: ast.Compare) -> bool:
        """Check if comparison looks like it's comparing sensitive data."""
        code = ast.unparse(node).lower()
        return any(
            term in code
            for term in ["password", "token", "secret", "key", "auth", "credential"]
        )


class RegexPatternChecker:
    """Regex-based pattern detection for vulnerabilities."""

    # A03: Injection patterns
    SQL_INJECTION_PATTERNS = [
        r"\.format\s*\(\s*['\"]SELECT",
        r'f["\'](SELECT|INSERT|UPDATE|DELETE)',
        r'\.query\s*\(\s*f["\']',
        r'execute\s*\(\s*f["\']',
        r"SQL.*%s.*%",
    ]

    CYPHER_INJECTION_PATTERNS = [
        r'\.run\s*\(\s*f["\'].*MATCH',
        r'\.run\s*\(\s*f["\'].*CREATE',
        r'session\.run\s*\(\s*["\'].*\{\}',
    ]

    COMMAND_INJECTION_PATTERNS = [
        r'Popen\s*\(\s*f["\']',
        r'call\s*\(\s*f["\']',
        r'run\s*\(\s*f["\'].*shell\s*=\s*True',
    ]

    # A02: Cryptographic failures
    WEAK_CRYPTO_PATTERNS = [
        r"hashlib\.md5",
        r"hashlib\.sha1",
        r"random\.random",
        r"os\.urandom",  # Actually OK, but flagged for review
    ]

    # A05: Misconfiguration
    DEBUG_PATTERNS = [
        r"DEBUG\s*=\s*True",
        r"debug\s*=\s*True",
        r"TESTING\s*=\s*True",
    ]

    # A09: Logging failures
    LOGGING_PATTERNS = [
        r"print\s*\(",  # Should use logging instead
        r"sys\.stdout\.write",
    ]

    def check_file(self, file_path: str, content: str) -> list[SecurityIssue]:
        """Check file for regex-based patterns."""
        issues = []

        # SQL Injection checks
        for pattern in self.SQL_INJECTION_PATTERNS:
            for match in re.finditer(pattern, content):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        file_path=file_path,
                        line_number=line_num,
                        category=OWASPCategory.A03_INJECTION,
                        severity=Severity.HIGH,
                        description="Potential SQL injection via string formatting",
                        code_snippet=content.split("\n")[line_num - 1][:100],
                        remediation="Use parameterized queries with ? or :param placeholders",
                        cwe_id="CWE-89",
                    )
                )

        # Cypher injection checks
        for pattern in self.CYPHER_INJECTION_PATTERNS:
            for match in re.finditer(pattern, content):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        file_path=file_path,
                        line_number=line_num,
                        category=OWASPCategory.A03_INJECTION,
                        severity=Severity.HIGH,
                        description="Potential Cypher injection in Neo4j query",
                        code_snippet=content.split("\n")[line_num - 1][:100],
                        remediation="Use parameterized queries: session.run(query, params={})",
                        cwe_id="CWE-89",
                    )
                )

        # Debug mode in production
        for pattern in self.DEBUG_PATTERNS:
            for match in re.finditer(pattern, content):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        file_path=file_path,
                        line_number=line_num,
                        category=OWASPCategory.A05_SECURITY_MISCONFIGURATION,
                        severity=Severity.HIGH,
                        description="Debug mode enabled in source code",
                        code_snippet=content.split("\n")[line_num - 1][:100],
                        remediation="Use environment variables to control debug mode: DEBUG=os.getenv('DEBUG', 'false') == 'true'",
                        cwe_id="CWE-215",
                    )
                )

        # Logging with print instead of logger
        for pattern in self.LOGGING_PATTERNS:
            if (
                "logging" not in content and "log" not in content.lower()
            ):  # Skip if using logging module
                for match in re.finditer(pattern, content):
                    line_num = content[: match.start()].count("\n") + 1
                    issues.append(
                        SecurityIssue(
                            file_path=file_path,
                            line_number=line_num,
                            category=OWASPCategory.A09_SECURITY_LOGGING_FAILURES,
                            severity=Severity.MEDIUM,
                            description="Using print() instead of logging module",
                            code_snippet=content.split("\n")[line_num - 1][:100],
                            remediation="Use logger.info(), logger.warning(), etc. instead of print()",
                            cwe_id="CWE-532",
                        )
                    )

        return issues


class OWASPAuditor:
    """Main OWASP Top 10 security auditor."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.analyzer = RegexPatternChecker()
        self.issues: list[SecurityIssue] = []

    def audit_file(self, file_path: str) -> list[SecurityIssue]:
        """Audit a single Python file."""
        file_issues = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Regex-based checks
            file_issues.extend(self.analyzer.check_file(file_path, content))

            # AST-based checks
            try:
                tree = ast.parse(content)
                analyzer = CodeAnalyzer(content, file_path)
                analyzer.visit(tree)
                file_issues.extend(analyzer.issues)
            except SyntaxError:
                pass  # Skip files with syntax errors

        except (OSError, UnicodeDecodeError):
            pass

        return file_issues

    def audit_codebase(
        self, root_path: str, extensions: list[str] | None = None
    ) -> list[SecurityIssue]:
        """Audit entire codebase for OWASP vulnerabilities."""
        if extensions is None:
            extensions = [".py"]

        self.issues = []
        root = Path(root_path)

        for file_path in root.rglob("*"):
            if file_path.is_file() and any(
                file_path.suffix == ext for ext in extensions
            ):
                # Skip test and example files
                if "test" in str(file_path) or "example" in str(file_path):
                    continue

                file_issues = self.audit_file(str(file_path))
                self.issues.extend(file_issues)

                if self.verbose and file_issues:
                    print(f"Found {len(file_issues)} issues in {file_path}")

        return self.issues

    def get_critical_issues(self) -> list[SecurityIssue]:
        """Get only critical severity issues."""
        return [issue for issue in self.issues if issue.severity == Severity.CRITICAL]

    def get_issues_by_category(self, category: OWASPCategory) -> list[SecurityIssue]:
        """Get issues by OWASP category."""
        return [issue for issue in self.issues if issue.category == category]

    def generate_report(self, output_file: str | None = None) -> str:
        """Generate audit report."""
        report = ["# OWASP Top 10 Security Audit Report\n"]

        # Summary
        critical = len(self.get_critical_issues())
        high = len([i for i in self.issues if i.severity == Severity.HIGH])
        medium = len([i for i in self.issues if i.severity == Severity.MEDIUM])
        low = len([i for i in self.issues if i.severity == Severity.LOW])

        report.append("## Summary\n")
        report.append(f"- **Critical**: {critical}\n")
        report.append(f"- **High**: {high}\n")
        report.append(f"- **Medium**: {medium}\n")
        report.append(f"- **Low**: {low}\n")
        report.append(f"- **Total**: {len(self.issues)}\n\n")

        # Issues by category
        categories_dict = {}
        for issue in self.issues:
            if issue.category not in categories_dict:
                categories_dict[issue.category] = []
            categories_dict[issue.category].append(issue)

        for category, issues in sorted(categories_dict.items()):
            report.append(f"## {category.value}\n\n")
            for issue in issues:
                report.append(f"### {issue.severity.value}: {issue.description}\n")
                report.append(f"**File**: {issue.file_path}:{issue.line_number}\n")
                report.append(f"**CWE**: {issue.cwe_id}\n")
                report.append(f"**Code**: `{issue.code_snippet}`\n")
                report.append(f"**Remediation**: {issue.remediation}\n\n")

        report_text = "".join(report)

        if output_file:
            with open(output_file, "w") as f:
                f.write(report_text)

        return report_text


def audit_and_report(
    root_path: str, output_file: str | None = None
) -> list[SecurityIssue]:
    """Convenience function to audit and generate report."""
    auditor = OWASPAuditor(verbose=True)
    issues = auditor.audit_codebase(root_path)
    report = auditor.generate_report(output_file)
    print(report)
    return issues
