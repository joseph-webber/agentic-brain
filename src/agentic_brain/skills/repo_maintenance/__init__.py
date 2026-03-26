# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Repository Maintenance Skills - Self-Maintaining Agentic Brain

These skills help agentic-brain maintain itself:
- License compliance (Apache-2.0 headers)
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

from .doc_generator import DocGenerator
from .license_checker import LicenseChecker
from .maintainer import RepoMaintainer
from .release_manager import ReleaseManager

__all__ = [
    "RepoMaintainer",
    "LicenseChecker",
    "DocGenerator",
    "ReleaseManager",
]
