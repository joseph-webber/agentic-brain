# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
Repository Maintenance Skills - Self-Maintaining Agentic Brain

These skills help agentic-brain maintain itself:
- License compliance (GPL-3.0 headers)
- Documentation completeness
- Test coverage verification  
- Code quality checks
- Release preparation
- CI/CD integration

Perfect for forks - keeps YOUR agentic-brain up to date!

Usage:
    from agentic_brain.skills.repo_maintenance import RepoMaintainer
    
    maintainer = RepoMaintainer()
    report = maintainer.full_audit()
    maintainer.fix_all()
"""

from .maintainer import RepoMaintainer
from .license_checker import LicenseChecker
from .doc_generator import DocGenerator
from .release_manager import ReleaseManager

__all__ = [
    "RepoMaintainer",
    "LicenseChecker",
    "DocGenerator", 
    "ReleaseManager",
]
