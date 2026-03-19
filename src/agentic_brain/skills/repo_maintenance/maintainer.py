# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
Repository Maintainer - Master controller for all maintenance tasks.

The brain that keeps agentic-brain healthy!
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from .license_checker import LicenseChecker, LicenseReport
from .doc_generator import DocGenerator, DocReport
from .release_manager import ReleaseManager, ReleaseReport, ReleaseStatus


@dataclass
class MaintenanceReport:
    """Full maintenance audit report."""
    timestamp: datetime = field(default_factory=datetime.now)
    license_report: Optional[LicenseReport] = None
    doc_report: Optional[DocReport] = None
    release_report: Optional[ReleaseReport] = None
    issues: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Check if repo is in healthy state."""
        if self.license_report and not self.license_report.is_compliant:
            return False
        if self.release_report and self.release_report.status == ReleaseStatus.BLOCKED:
            return False
        return True
    
    @property
    def score(self) -> int:
        """Calculate health score 0-100."""
        score = 100
        
        if self.license_report:
            score -= (100 - self.license_report.compliance_rate) * 0.3
        
        if self.doc_report:
            score -= (100 - self.doc_report.coverage) * 0.2
        
        if self.release_report:
            failed = len(self.release_report.checks) - self.release_report.passed_count
            score -= failed * 10
        
        return max(0, int(score))
    
    def __str__(self) -> str:
        lines = [
            "=" * 50,
            "AGENTIC BRAIN MAINTENANCE REPORT",
            "=" * 50,
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Health Score: {self.score}/100",
            f"Status: {'✅ HEALTHY' if self.is_healthy else '❌ NEEDS ATTENTION'}",
            ""
        ]
        
        if self.license_report:
            lines.append(f"📜 License: {self.license_report.compliance_rate:.0f}% compliant")
        
        if self.doc_report:
            lines.append(f"📚 Docs: {self.doc_report.coverage:.0f}% coverage")
        
        if self.release_report:
            lines.append(f"🚀 Release: {self.release_report.status.value}")
        
        if self.issues:
            lines.append("\n⚠️ Issues Found:")
            for issue in self.issues:
                lines.append(f"  - {issue}")
        
        if self.actions_taken:
            lines.append("\n✅ Actions Taken:")
            for action in self.actions_taken:
                lines.append(f"  - {action}")
        
        lines.append("=" * 50)
        return "\n".join(lines)


class RepoMaintainer:
    """
    Master controller for agentic-brain repository maintenance.
    
    Coordinates all maintenance tasks:
    - License compliance
    - Documentation generation
    - Release preparation
    - Code quality
    
    Usage:
        maintainer = RepoMaintainer()
        
        # Full audit
        report = maintainer.full_audit()
        print(report)
        
        # Auto-fix issues
        maintainer.fix_all()
        
        # Prepare release
        maintainer.prepare_release("1.0.0")
    """
    
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path) if repo_path else Path(__file__).parent.parent.parent.parent.parent
        
        # Initialize sub-components
        self.license_checker = LicenseChecker(str(self.repo_path))
        self.doc_generator = DocGenerator(str(self.repo_path))
        self.release_manager = ReleaseManager(str(self.repo_path))
    
    def full_audit(self) -> MaintenanceReport:
        """
        Run complete maintenance audit.
        
        Checks:
        - License headers
        - Documentation coverage
        - Release readiness
        """
        report = MaintenanceReport()
        
        # License check
        report.license_report = self.license_checker.check()
        if not report.license_report.is_compliant:
            report.issues.append(f"{len(report.license_report.missing_header)} files missing GPL-3.0 headers")
        
        # Documentation check
        report.doc_report = self.doc_generator.scan()
        if report.doc_report.undocumented:
            report.issues.append(f"{len(report.doc_report.undocumented)} modules missing docstrings")
        
        # Release readiness
        report.release_report = self.release_manager.check_release_ready()
        if report.release_report.status == ReleaseStatus.BLOCKED:
            report.issues.append("Release is blocked - see release report")
        
        return report
    
    def fix_all(self, generate_docs: bool = True) -> MaintenanceReport:
        """
        Auto-fix all fixable issues.
        
        Actions:
        - Add missing license headers
        - Generate missing documentation
        """
        report = self.full_audit()
        
        # Fix licenses
        if report.license_report and not report.license_report.is_compliant:
            fixed = self.license_checker.fix_all()
            if fixed.fixed_files:
                report.actions_taken.append(f"Added GPL-3.0 headers to {len(fixed.fixed_files)} files")
        
        # Generate docs
        if generate_docs:
            doc_report = self.doc_generator.generate()
            if doc_report.generated_files:
                report.actions_taken.append(f"Generated {len(doc_report.generated_files)} documentation files")
        
        return report
    
    def prepare_release(self, version: str, dry_run: bool = True) -> MaintenanceReport:
        """
        Prepare a release.
        
        Steps:
        1. Run full audit
        2. Fix all issues
        3. Validate release readiness
        4. Bump version (if not dry run)
        """
        # First fix everything
        report = self.fix_all()
        
        # Check release readiness
        release_report = self.release_manager.check_release_ready(version)
        report.release_report = release_report
        
        if release_report.status == ReleaseStatus.READY:
            if not dry_run:
                self.release_manager.create_release(version, dry_run=False)
                report.actions_taken.append(f"Created release v{version}")
            else:
                report.actions_taken.append(f"[DRY RUN] Would create release v{version}")
        else:
            report.issues.append(f"Cannot release: {release_report.status.value}")
        
        return report
    
    def quick_check(self) -> Dict[str, Any]:
        """Quick health check - returns dict for easy consumption."""
        license_report = self.license_checker.check()
        version = self.release_manager.get_version()
        
        return {
            "version": version,
            "license_compliant": license_report.is_compliant,
            "files_checked": license_report.total_files,
            "files_compliant": license_report.compliant_files,
            "ready_for_release": license_report.is_compliant,
        }


# CLI interface
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Agentic Brain Repo Maintainer")
    parser.add_argument("command", choices=["audit", "fix", "release", "check"], 
                        help="Command to run")
    parser.add_argument("--version", help="Version for release")
    parser.add_argument("--repo", help="Repository path")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    
    args = parser.parse_args()
    
    maintainer = RepoMaintainer(args.repo)
    
    if args.command == "audit":
        print(maintainer.full_audit())
    elif args.command == "fix":
        print(maintainer.fix_all())
    elif args.command == "release":
        version = args.version or maintainer.release_manager.get_version()
        print(maintainer.prepare_release(version, dry_run=args.dry_run))
    elif args.command == "check":
        import json
        print(json.dumps(maintainer.quick_check(), indent=2))
