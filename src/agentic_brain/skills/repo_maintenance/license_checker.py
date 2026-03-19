# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
License Checker - Ensures GPL-3.0 compliance across all source files.

Scans, validates, and auto-fixes license headers.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


GPL3_HEADER = '''# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) {year} {author}
#
# This file is part of Agentic Brain.
'''

SPDX_PATTERN = "SPDX-License-Identifier: GPL-3.0"


@dataclass
class LicenseReport:
    """License compliance report."""
    total_files: int = 0
    compliant_files: int = 0
    missing_header: List[str] = field(default_factory=list)
    fixed_files: List[str] = field(default_factory=list)
    
    @property
    def compliance_rate(self) -> float:
        if self.total_files == 0:
            return 100.0
        return (self.compliant_files / self.total_files) * 100
    
    @property
    def is_compliant(self) -> bool:
        return len(self.missing_header) == 0
    
    def __str__(self) -> str:
        status = "✅ COMPLIANT" if self.is_compliant else "❌ NON-COMPLIANT"
        return f"""
License Compliance Report
========================
Status: {status}
Total Files: {self.total_files}
Compliant: {self.compliant_files} ({self.compliance_rate:.1f}%)
Missing Header: {len(self.missing_header)}
Fixed: {len(self.fixed_files)}
"""


class LicenseChecker:
    """
    GPL-3.0 license header checker and fixer.
    
    Usage:
        checker = LicenseChecker()
        report = checker.check()
        checker.fix_all()
    """
    
    def __init__(
        self, 
        repo_path: Optional[str] = None,
        author: str = "Joseph Webber <joseph.webber@me.com>"
    ):
        self.repo_path = Path(repo_path) if repo_path else Path(__file__).parent.parent.parent.parent.parent
        self.src_path = self.repo_path / "src"
        self.author = author
        self.year = datetime.now().year
        
    def _get_python_files(self) -> List[Path]:
        """Find all Python files in src/"""
        if not self.src_path.exists():
            return []
        return list(self.src_path.rglob("*.py"))
    
    def _has_valid_header(self, file_path: Path) -> bool:
        """Check if file has valid GPL-3.0 SPDX header."""
        try:
            content = file_path.read_text()
            return SPDX_PATTERN in content[:500]
        except Exception:
            return False
    
    def _get_header(self) -> str:
        """Get license header with current year."""
        return GPL3_HEADER.format(year=self.year, author=self.author)
    
    def check(self) -> LicenseReport:
        """Check all Python files for license compliance."""
        files = self._get_python_files()
        missing = []
        
        for f in files:
            if not self._has_valid_header(f):
                missing.append(str(f.relative_to(self.repo_path)))
        
        return LicenseReport(
            total_files=len(files),
            compliant_files=len(files) - len(missing),
            missing_header=missing,
        )
    
    def fix_file(self, file_path: Path) -> bool:
        """Add GPL-3.0 header to a file if missing."""
        if self._has_valid_header(file_path):
            return False
            
        try:
            content = file_path.read_text()
            
            # Handle shebang
            if content.startswith("#!"):
                lines = content.split("\n", 1)
                new_content = lines[0] + "\n" + self._get_header() + lines[1]
            else:
                new_content = self._get_header() + content
                
            file_path.write_text(new_content)
            return True
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")
            return False
    
    def fix_all(self) -> LicenseReport:
        """Fix all files missing GPL-3.0 headers."""
        report = self.check()
        fixed = []
        
        for rel_path in report.missing_header:
            full_path = self.repo_path / rel_path
            if self.fix_file(full_path):
                fixed.append(rel_path)
        
        new_report = self.check()
        new_report.fixed_files = fixed
        return new_report
