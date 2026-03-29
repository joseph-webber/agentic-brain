# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
GitHub Homepage Skill - Learning README Optimizer

This skill learns how to make better GitHub homepages over time:
- Remembers what worked and what didn't
- Tracks SEO best practices
- Stores snapshots of good versions
- Suggests improvements based on learnings

Never lose good content again - the skill remembers!

Usage:
    from agentic_brain.skills.github_homepage import HomepageSkill

    skill = HomepageSkill()
    skill.snapshot("Added GraphRAG section")  # Save current state
    skill.learn("GraphRAG diagram increased engagement")  # Record learning
    suggestions = skill.suggest_improvements()  # Get AI suggestions
"""

from .homepage_skill import HomepageSkill
from .readme_analyzer import ReadmeAnalyzer

__all__ = [
    "HomepageSkill",
    "ReadmeAnalyzer",
]
