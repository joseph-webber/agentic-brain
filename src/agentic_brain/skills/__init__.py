"""
Skills system for agentic-brain.

Skills are modular expertise packages that extend agent capabilities.
Inspired by GitHub Copilot custom instructions and Claude's tool system.

Example:
    >>> from agentic_brain.skills import Skill, SkillRegistry
    >>> 
    >>> @Skill.register("code-review")
    ... def review_code(code: str) -> str:
    ...     return "Code looks good!"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Any, Dict
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class SkillDefinition:
    """
    Skill definition following Claude/Copilot patterns.
    
    Attributes:
        name: Unique skill identifier
        description: What the skill does
        instructions: System prompt additions
        tools: List of tool functions
        examples: Usage examples
    """
    name: str
    description: str
    instructions: str = ""
    tools: list[Callable] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "examples": self.examples,
            "version": self.version,
            "author": self.author,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SkillDefinition":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            instructions=data.get("instructions", ""),
            examples=data.get("examples", []),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
        )
    
    @classmethod
    def from_file(cls, path: Path) -> "SkillDefinition":
        """Load skill from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


class SkillRegistry:
    """
    Registry for managing skills.
    
    Skills can be:
    - Registered programmatically
    - Loaded from JSON files
    - Discovered from directories
    
    Example:
        >>> registry = SkillRegistry()
        >>> registry.register(code_review_skill)
        >>> registry.load_from_directory("./skills")
        >>> 
        >>> skill = registry.get("code-review")
        >>> print(skill.instructions)
    """
    
    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
    
    def register(self, skill: SkillDefinition) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")
    
    def get(self, name: str) -> Optional[SkillDefinition]:
        """Get skill by name."""
        return self._skills.get(name)
    
    def list(self) -> list[str]:
        """List all registered skills."""
        return list(self._skills.keys())
    
    def load_from_file(self, path: Path) -> SkillDefinition:
        """Load and register skill from file."""
        skill = SkillDefinition.from_file(path)
        self.register(skill)
        return skill
    
    def load_from_directory(self, directory: Path) -> list[SkillDefinition]:
        """Load all skills from directory."""
        directory = Path(directory)
        skills = []
        
        for path in directory.glob("*.json"):
            try:
                skill = self.load_from_file(path)
                skills.append(skill)
            except Exception as e:
                logger.warning(f"Failed to load skill from {path}: {e}")
        
        return skills
    
    def get_instructions(self, *skill_names: str) -> str:
        """
        Get combined instructions from multiple skills.
        
        Args:
            skill_names: Names of skills to combine
            
        Returns:
            Combined instruction string
        """
        parts = []
        for name in skill_names:
            skill = self.get(name)
            if skill and skill.instructions:
                parts.append(f"## {skill.name}\n{skill.instructions}")
        
        return "\n\n".join(parts)
    
    def __contains__(self, name: str) -> bool:
        return name in self._skills
    
    def __len__(self) -> int:
        return len(self._skills)


# Built-in skills
ACCESSIBILITY_SKILL = SkillDefinition(
    name="accessibility",
    description="Accessibility-first development following WCAG 2.1 AA standards",
    instructions="""
## Accessibility Guidelines

Always consider accessibility in all outputs:

1. **Images**: Every image needs alt text
2. **Buttons**: Every button needs aria-label  
3. **Forms**: Every input needs associated label
4. **Color**: Never rely on color alone
5. **Keyboard**: Ensure full keyboard navigation
6. **Focus**: Visible focus indicators required
7. **Screen readers**: Test with VoiceOver/NVDA

When writing code:
- Add ARIA labels to interactive elements
- Use semantic HTML (header, nav, main, footer)
- Ensure color contrast ratio >= 4.5:1
- Support reduced motion preferences
""",
    examples=[
        "Add aria-label to this button",
        "Make this form accessible",
        "Check color contrast",
    ],
    author="Joseph Webber",
)

CODE_REVIEW_SKILL = SkillDefinition(
    name="code-review",
    description="Professional code review with security focus",
    instructions="""
## Code Review Guidelines

When reviewing code, check for:

### Security
- SQL injection vulnerabilities
- Hardcoded credentials
- Input validation
- Error message exposure

### Quality  
- Clear naming conventions
- Appropriate comments
- DRY principles
- Single responsibility

### Testing
- Unit test coverage
- Edge cases handled
- Error paths tested

### Performance
- N+1 queries
- Memory leaks
- Unnecessary loops

Provide actionable feedback with examples.
""",
    examples=[
        "Review this PR for security issues",
        "Check this code for best practices",
    ],
    author="Joseph Webber",
)

DATA_SEPARATION_SKILL = SkillDefinition(
    name="data-separation",
    description="Multi-tenant data isolation patterns",
    instructions="""
## Data Separation Patterns

Implement proper data scoping:

### Scopes
- **PUBLIC**: Shared knowledge, no restrictions
- **PRIVATE**: Admin/system data, internal only  
- **CUSTOMER**: Per-client isolation, B2B

### Rules
1. Always specify scope when storing data
2. Customer data requires customer_id
3. Never cross scope boundaries in queries
4. Audit log all scope changes

### Queries
- Filter by scope in every query
- Include customer_id for CUSTOMER scope
- Use parameterized queries only
""",
    examples=[
        "Store this in customer scope for Acme",
        "Query public knowledge base",
    ],
    author="Joseph Webber",
)


# Global registry with built-in skills
_default_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """Get or create default skill registry with built-ins."""
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
        _default_registry.register(ACCESSIBILITY_SKILL)
        _default_registry.register(CODE_REVIEW_SKILL)
        _default_registry.register(DATA_SEPARATION_SKILL)
    return _default_registry


# Decorator for easy skill registration
class Skill:
    """
    Decorator for registering skills.
    
    Example:
        >>> @Skill.define(
        ...     name="my-skill",
        ...     description="Does something useful"
        ... )
        ... class MySkill:
        ...     instructions = "Do this, not that"
    """
    
    @staticmethod
    def define(
        name: str,
        description: str,
        **kwargs,
    ) -> Callable:
        """Define a skill from a class."""
        def decorator(cls):
            skill = SkillDefinition(
                name=name,
                description=description,
                instructions=getattr(cls, "instructions", ""),
                examples=getattr(cls, "examples", []),
                **kwargs,
            )
            get_registry().register(skill)
            return cls
        return decorator
