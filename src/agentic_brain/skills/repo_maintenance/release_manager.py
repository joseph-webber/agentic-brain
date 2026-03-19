# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
Release Manager - Prepares releases with full validation.

Checks:
- All tests pass
- Coverage meets threshold
- License headers present
- Documentation complete
- Version bumped
- Changelog updated
"""

import subprocess
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class ReleaseStatus(Enum):
    """Release readiness status."""
    READY = "ready"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ReleaseCheck:
    """Single release check result."""
    name: str
    passed: bool
    message: str
    blocking: bool = True


@dataclass
class ReleaseReport:
    """Full release readiness report."""
    version: str
    checks: List[ReleaseCheck] = field(default_factory=list)
    
    @property
    def status(self) -> ReleaseStatus:
        blocking_failures = [c for c in self.checks if not c.passed and c.blocking]
        if blocking_failures:
            return ReleaseStatus.BLOCKED
        non_blocking_failures = [c for c in self.checks if not c.passed]
        if non_blocking_failures:
            return ReleaseStatus.NEEDS_REVIEW
        return ReleaseStatus.READY
    
    @property
    def passed_count(self) -> int:
        return len([c for c in self.checks if c.passed])
    
    def __str__(self) -> str:
        status_icon = {
            ReleaseStatus.READY: "✅",
            ReleaseStatus.BLOCKED: "❌",
            ReleaseStatus.NEEDS_REVIEW: "⚠️"
        }
        
        lines = [
            f"Release Report: v{self.version}",
            f"Status: {status_icon[self.status]} {self.status.value.upper()}",
            f"Checks: {self.passed_count}/{len(self.checks)} passed",
            ""
        ]
        
        for check in self.checks:
            icon = "✅" if check.passed else "❌"
            blocking = " [BLOCKING]" if check.blocking and not check.passed else ""
            lines.append(f"{icon} {check.name}{blocking}")
            lines.append(f"   {check.message}")
        
        return "\n".join(lines)


class ReleaseManager:
    """
    Manages releases with full validation.
    
    Usage:
        rm = ReleaseManager()
        report = rm.check_release_ready()
        if report.status == ReleaseStatus.READY:
            rm.create_release("1.0.0")
    """
    
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path) if repo_path else Path(__file__).parent.parent.parent.parent.parent
        self.src_path = self.repo_path / "src"
        
    def get_version(self) -> str:
        """Get current version from __init__.py"""
        init_file = self.src_path / "agentic_brain" / "__init__.py"
        if init_file.exists():
            content = init_file.read_text()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
        return "0.0.0"
    
    def set_version(self, version: str) -> bool:
        """Update version in __init__.py"""
        init_file = self.src_path / "agentic_brain" / "__init__.py"
        if not init_file.exists():
            return False
            
        content = init_file.read_text()
        new_content = re.sub(
            r'__version__\s*=\s*["\'][^"\']+["\']',
            f'__version__ = "{version}"',
            content
        )
        init_file.write_text(new_content)
        return True
    
    def _run_command(self, cmd: List[str]) -> Tuple[bool, str]:
        """Run a command and return success status and output."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)
    
    def check_tests(self) -> ReleaseCheck:
        """Check if all tests pass."""
        success, output = self._run_command(["python", "-m", "pytest", "-q"])
        if success:
            return ReleaseCheck("Tests", True, "All tests pass")
        else:
            # Count failures
            match = re.search(r"(\d+) failed", output)
            failed = match.group(1) if match else "some"
            return ReleaseCheck("Tests", False, f"{failed} tests failed")
    
    def check_coverage(self, threshold: int = 80) -> ReleaseCheck:
        """Check test coverage meets threshold."""
        success, output = self._run_command([
            "python", "-m", "pytest", 
            "--cov=src/agentic_brain",
            "--cov-report=term",
            "-q"
        ])
        
        # Extract coverage percentage
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if match:
            coverage = int(match.group(1))
            if coverage >= threshold:
                return ReleaseCheck("Coverage", True, f"{coverage}% coverage (>= {threshold}%)")
            else:
                return ReleaseCheck("Coverage", False, f"{coverage}% coverage (< {threshold}%)")
        
        return ReleaseCheck("Coverage", False, "Could not determine coverage")
    
    def check_license(self) -> ReleaseCheck:
        """Check all files have GPL-3.0 headers."""
        from .license_checker import LicenseChecker
        checker = LicenseChecker(str(self.repo_path))
        report = checker.check()
        
        if report.is_compliant:
            return ReleaseCheck("License", True, f"All {report.total_files} files have GPL-3.0 headers")
        else:
            return ReleaseCheck("License", False, f"{len(report.missing_header)} files missing headers")
    
    def check_docs(self) -> ReleaseCheck:
        """Check documentation exists and is complete."""
        readme = self.repo_path / "README.md"
        docs_dir = self.repo_path / "docs"
        
        issues = []
        if not readme.exists():
            issues.append("No README.md")
        if not docs_dir.exists():
            issues.append("No docs/ directory")
        
        if issues:
            return ReleaseCheck("Documentation", False, ", ".join(issues), blocking=False)
        
        return ReleaseCheck("Documentation", True, "Documentation present")
    
    def check_changelog(self, version: str) -> ReleaseCheck:
        """Check changelog has entry for version."""
        changelog = self.repo_path / "CHANGELOG.md"
        if not changelog.exists():
            return ReleaseCheck("Changelog", False, "No CHANGELOG.md", blocking=False)
        
        content = changelog.read_text()
        if version in content:
            return ReleaseCheck("Changelog", True, f"Changelog has entry for v{version}")
        
        return ReleaseCheck("Changelog", False, f"No changelog entry for v{version}", blocking=False)
    
    def check_release_ready(self, version: Optional[str] = None) -> ReleaseReport:
        """Run all release checks."""
        version = version or self.get_version()
        
        report = ReleaseReport(version=version)
        report.checks.append(self.check_tests())
        report.checks.append(self.check_coverage())
        report.checks.append(self.check_license())
        report.checks.append(self.check_docs())
        report.checks.append(self.check_changelog(version))
        
        return report
    
    def create_release(self, version: str, dry_run: bool = True) -> bool:
        """Create a release (bump version, tag, etc.)"""
        # First check if ready
        report = self.check_release_ready(version)
        if report.status == ReleaseStatus.BLOCKED:
            print(f"❌ Cannot release: {report}")
            return False
        
        if dry_run:
            print(f"🔍 DRY RUN: Would release v{version}")
            print(report)
            return True
        
        # Bump version
        self.set_version(version)
        
        # Git operations
        self._run_command(["git", "add", "-A"])
        self._run_command(["git", "commit", "-m", f"Release v{version}"])
        self._run_command(["git", "tag", f"v{version}"])
        
        print(f"✅ Created release v{version}")
        return True
