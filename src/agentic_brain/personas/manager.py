# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Persona:
    """
    Represents an AI persona with a specific role and style.
    """

    name: str
    description: str
    system_prompt: str
    style_guidelines: List[str] = field(default_factory=list)
    temperature: float = 0.7
    safety_level: str = "standard"

    def format_system_prompt(self) -> str:
        """Combine base prompt with style guidelines."""
        if not self.style_guidelines:
            return self.system_prompt

        style_text = "\n".join(f"- {g}" for g in self.style_guidelines)
        return f"{self.system_prompt}\n\nStyle Guidelines:\n{style_text}"


class PersonaManager:
    """
    Manages available personas.
    """

    _instance = None

    def __init__(self):
        self._personas: Dict[str, Persona] = {}
        self._register_defaults()

    @classmethod
    def get_instance(cls) -> "PersonaManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, persona: Persona):
        """Register a new persona."""
        self._personas[persona.name] = persona

    def get(self, name: str) -> Optional[Persona]:
        """Get a persona by name."""
        return self._personas.get(name)

    def list_personas(self) -> List[str]:
        """List all available persona names."""
        return list(self._personas.keys())

    def _register_defaults(self):
        """Register default personas."""
        # General Assistant
        self.register(
            Persona(
                name="default",
                description="Helpful general assistant",
                system_prompt="You are a helpful, harmless, and honest AI assistant.",
                style_guidelines=["Be concise", "Use clear formatting"],
            )
        )

        # Coder
        self.register(
            Persona(
                name="coder",
                description="Expert software engineer",
                system_prompt="You are an expert software engineer with deep knowledge of Python, TypeScript, and system design.",
                style_guidelines=[
                    "Write clean, documented code",
                    "Follow PEP 8 for Python",
                    "Include type hints",
                    "Explain complex logic",
                ],
            )
        )

        # Creative Writer
        self.register(
            Persona(
                name="creative",
                description="Creative writer and storyteller",
                system_prompt="You are a creative writer with a flair for engaging storytelling and vivid imagery.",
                style_guidelines=["Show, don't tell", "Use evocative language"],
            )
        )

        # Analyst
        self.register(
            Persona(
                name="analyst",
                description="Data and systems analyst",
                system_prompt="You are a rigorous analyst capable of breaking down complex problems and finding patterns.",
                style_guidelines=[
                    "Be objective",
                    "Cite evidence",
                    "Structure arguments logically",
                ],
            )
        )

        # Industry Personas
        try:
            from .industries import INDUSTRY_PERSONAS

            for persona in INDUSTRY_PERSONAS.values():
                self.register(persona)
        except ImportError:
            pass  # Avoid circular import issues if running tests directly on this file


def get_persona(name: str) -> Optional[Persona]:
    """Convenience function to get a persona."""
    return PersonaManager.get_instance().get(name)
