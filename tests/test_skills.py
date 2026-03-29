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
Tests for agentic-brain skills module.
"""

import json
import tempfile
from pathlib import Path

from agentic_brain.skills import (
    ACCESSIBILITY_SKILL,
    CODE_REVIEW_SKILL,
    DATA_SEPARATION_SKILL,
    Skill,
    SkillDefinition,
    SkillRegistry,
    get_registry,
)


class TestSkillDefinition:
    """Test SkillDefinition dataclass."""

    def test_skill_creation(self):
        """Test creating a skill definition."""
        skill = SkillDefinition(
            name="test-skill",
            description="A test skill",
            instructions="Do testing things",
        )

        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.instructions == "Do testing things"

    def test_skill_with_examples(self):
        """Test skill with examples."""
        skill = SkillDefinition(
            name="example-skill",
            description="Has examples",
            examples=["Example 1", "Example 2"],
        )

        assert len(skill.examples) == 2
        assert "Example 1" in skill.examples

    def test_skill_to_dict(self):
        """Test skill serialization."""
        skill = SkillDefinition(
            name="serial-skill",
            description="Serializable",
            instructions="Instructions here",
            version="2.0.0",
            author="Test Author",
        )

        data = skill.to_dict()

        assert data["name"] == "serial-skill"
        assert data["version"] == "2.0.0"
        assert data["author"] == "Test Author"

    def test_skill_from_dict(self):
        """Test skill deserialization."""
        data = {
            "name": "loaded-skill",
            "description": "Loaded from dict",
            "instructions": "Some instructions",
            "version": "1.5.0",
        }

        skill = SkillDefinition.from_dict(data)

        assert skill.name == "loaded-skill"
        assert skill.version == "1.5.0"

    def test_skill_from_file(self):
        """Test loading skill from JSON file."""
        skill_data = {
            "name": "file-skill",
            "description": "From file",
            "instructions": "File instructions",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(skill_data, f)
            temp_path = Path(f.name)

        try:
            skill = SkillDefinition.from_file(temp_path)

            assert skill.name == "file-skill"
            assert skill.description == "From file"
        finally:
            temp_path.unlink()


class TestSkillRegistry:
    """Test SkillRegistry."""

    def test_registry_creation(self):
        """Test creating empty registry."""
        registry = SkillRegistry()

        assert len(registry) == 0
        assert registry.list() == []

    def test_register_skill(self):
        """Test registering a skill."""
        registry = SkillRegistry()
        skill = SkillDefinition(
            name="reg-skill",
            description="Registered",
        )

        registry.register(skill)

        assert "reg-skill" in registry
        assert len(registry) == 1

    def test_get_skill(self):
        """Test getting a skill by name."""
        registry = SkillRegistry()
        skill = SkillDefinition(
            name="get-skill",
            description="Gettable",
        )
        registry.register(skill)

        retrieved = registry.get("get-skill")

        assert retrieved is not None
        assert retrieved.name == "get-skill"

    def test_get_nonexistent(self):
        """Test getting nonexistent skill."""
        registry = SkillRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_list_skills(self):
        """Test listing skill names."""
        registry = SkillRegistry()
        registry.register(SkillDefinition("skill-a", "A"))
        registry.register(SkillDefinition("skill-b", "B"))

        names = registry.list()

        assert len(names) == 2
        assert "skill-a" in names
        assert "skill-b" in names

    def test_get_combined_instructions(self):
        """Test getting combined instructions from multiple skills."""
        registry = SkillRegistry()
        registry.register(
            SkillDefinition(
                "skill-1",
                "First skill",
                instructions="Do first things",
            )
        )
        registry.register(
            SkillDefinition(
                "skill-2",
                "Second skill",
                instructions="Do second things",
            )
        )

        combined = registry.get_instructions("skill-1", "skill-2")

        assert "skill-1" in combined
        assert "Do first things" in combined
        assert "skill-2" in combined
        assert "Do second things" in combined

    def test_load_from_directory(self):
        """Test loading skills from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create skill files
            skill1 = {"name": "dir-skill-1", "description": "First"}
            skill2 = {"name": "dir-skill-2", "description": "Second"}

            (tmppath / "skill1.json").write_text(json.dumps(skill1))
            (tmppath / "skill2.json").write_text(json.dumps(skill2))

            registry = SkillRegistry()
            skills = registry.load_from_directory(tmppath)

            assert len(skills) == 2
            assert "dir-skill-1" in registry
            assert "dir-skill-2" in registry


class TestBuiltinSkills:
    """Test built-in skills."""

    def test_accessibility_skill(self):
        """Test accessibility skill is defined."""
        assert ACCESSIBILITY_SKILL.name == "accessibility"
        assert "WCAG" in ACCESSIBILITY_SKILL.description
        assert "aria" in ACCESSIBILITY_SKILL.instructions.lower()

    def test_code_review_skill(self):
        """Test code review skill is defined."""
        assert CODE_REVIEW_SKILL.name == "code-review"
        assert "Security" in CODE_REVIEW_SKILL.instructions
        assert "SQL injection" in CODE_REVIEW_SKILL.instructions

    def test_data_separation_skill(self):
        """Test data separation skill is defined."""
        assert DATA_SEPARATION_SKILL.name == "data-separation"
        assert "PUBLIC" in DATA_SEPARATION_SKILL.instructions
        assert "PRIVATE" in DATA_SEPARATION_SKILL.instructions
        assert "CUSTOMER" in DATA_SEPARATION_SKILL.instructions


class TestGetRegistry:
    """Test global registry function."""

    def test_get_registry_has_builtins(self):
        """Test global registry includes built-in skills."""
        registry = get_registry()

        assert "accessibility" in registry
        assert "code-review" in registry
        assert "data-separation" in registry

    def test_get_registry_singleton(self):
        """Test get_registry returns same instance."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2


class TestSkillDecorator:
    """Test Skill decorator."""

    def test_skill_define_decorator(self):
        """Test defining skill with decorator."""

        @Skill.define(
            name="decorator-skill",
            description="Defined via decorator",
        )
        class MySkill:
            instructions = "Do decorated things"
            examples = ["Example usage"]

        registry = get_registry()
        skill = registry.get("decorator-skill")

        assert skill is not None
        assert skill.name == "decorator-skill"
        assert skill.instructions == "Do decorated things"

    def test_decorator_preserves_class(self):
        """Test decorator returns the original class."""

        @Skill.define(
            name="preserved-skill",
            description="Class preserved",
        )
        class PreservedSkill:
            custom_attr = "preserved"

        assert hasattr(PreservedSkill, "custom_attr")
        assert PreservedSkill.custom_attr == "preserved"
