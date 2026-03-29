# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
ADL Persona Templates
=====================

Persona modes provide complete ADL configurations that define the
entire behavior of the Agentic Brain. Each persona includes:

- LLM settings (provider, model, temperature)
- Mode configuration
- RAG settings
- Voice settings
- Router template selection

Personas map directly to operational modes and provide sensible
defaults for different use cases.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PersonaTemplate:
    """A complete persona configuration."""

    name: str
    description: str
    adl_content: str
    mode_code: str  # Maps to modes registry (e.g., "D" for developer)


PERSONA_TEMPLATES: Dict[str, PersonaTemplate] = {
    "professional": PersonaTemplate(
        name="Professional",
        description="Business/enterprise use - focused, precise, secure",
        mode_code="B",
        adl_content="""application AgenticBrain {
  name "My AI Assistant"
  version "1.0.0"
  persona professional
}

llm Primary {
  provider auto  // Auto-detect best available (Ollama → OpenAI → Groq)
  model "llama3.2:3b"  // Fast, efficient for business tasks
  temperature 0.3  // More focused and deterministic
  maxTokens 2048
  systemPrompt "You are a professional AI assistant for business use. Be concise, accurate, and formal."
}

rag MainRAG {
  vectorStore basic  // No Neo4j required
  embeddingModel "all-MiniLM-L6-v2"
  chunkSize 512
  chunkOverlap 50
  loaders ["pdf", "txt", "md"]
}

voice Assistant {
  provider system  // Use system default voice
  defaultVoice "default"
  rate 160
}

modes {
  default business
  routing smart  // Use smart router for optimal provider selection
  fallback ["ollama", "openai"]
}

security {
  level standard
  rateLimit 100  // requests per minute
  requireAuth false
}
""",
    ),
    "creative": PersonaTemplate(
        name="Creative",
        description="Writing, brainstorming, content generation",
        mode_code="CR",
        adl_content="""application AgenticBrain {
  name "Creative Assistant"
  persona creative
}

llm Primary {
  provider auto
  model "llama3.2:3b"
  temperature 0.9  // More creative and diverse outputs
  maxTokens 4096  // Longer responses for creative work
  systemPrompt "You are a creative AI assistant. Be imaginative, engaging, and help with writing and brainstorming."
}

rag MainRAG {
  vectorStore basic
  embeddingModel "all-MiniLM-L6-v2"
  chunkSize 1024  // Larger chunks for narrative context
  chunkOverlap 128
  loaders ["pdf", "txt", "md", "docx"]
}

voice Assistant {
  provider system
  defaultVoice "default"
  rate 150  // Slightly slower for better comprehension
}

modes {
  default creator
  routing smart
  fallback ["ollama", "openai"]
}

security {
  level standard
  rateLimit 100
  requireAuth false
}
""",
    ),
    "technical": PersonaTemplate(
        name="Technical",
        description="Coding, debugging, system administration",
        mode_code="D",
        adl_content="""application AgenticBrain {
  name "Developer Assistant"
  persona technical
}

llm Primary {
  provider auto
  model "llama3.2:3b"
  temperature 0.2  // More deterministic for code
  maxTokens 4096  // Longer for code examples
  systemPrompt "You are an expert software engineer. Provide clear, well-documented code with best practices."
}

rag MainRAG {
  vectorStore basic
  embeddingModel "all-MiniLM-L6-v2"
  chunkSize 1024  // Larger for code context
  chunkOverlap 128
  loaders ["py", "js", "ts", "java", "go", "md", "txt"]
}

voice Assistant {
  provider system
  defaultVoice "default"
  rate 165  // Slightly faster for technical users
}

modes {
  default developer
  routing smart
  fallback ["ollama", "openai", "groq"]
}

security {
  level standard
  rateLimit 150  // Higher limit for dev workflows
  requireAuth false
}
""",
    ),
    "accessibility": PersonaTemplate(
        name="Accessibility",
        description="Screen reader optimized, WCAG compliant",
        mode_code="H",
        adl_content="""application AgenticBrain {
  name "Accessible Assistant"
  persona accessibility
}

llm Primary {
  provider auto
  model "llama3.2:3b"
  temperature 0.4
  maxTokens 2048
  systemPrompt "You are an accessibility-focused AI assistant. Always provide clear, structured responses optimized for screen readers. Use semantic formatting."
}

rag MainRAG {
  vectorStore basic
  embeddingModel "all-MiniLM-L6-v2"
  chunkSize 512
  chunkOverlap 50
  loaders ["txt", "md"]  // Prioritize text-based formats
}

voice Assistant {
  provider system
  defaultVoice "default"
  rate 160  // Clear pace for screen readers
}

modes {
  default home  // Accessible home mode
  routing smart
  fallback ["ollama", "openai"]
}

security {
  level standard
  rateLimit 100
  requireAuth false
}

accessibility {
  wcagLevel "AA"  // WCAG 2.1 Level AA compliance
  screenReaderOptimized true
  highContrast true
}
""",
    ),
    "research": PersonaTemplate(
        name="Research",
        description="Academic research, data analysis, citations",
        mode_code="R",
        adl_content="""application AgenticBrain {
  name "Research Assistant"
  persona research
}

llm Primary {
  provider auto
  model "llama3.2:3b"
  temperature 0.5  // Balanced creativity and accuracy
  maxTokens 4096  // Longer for detailed analysis
  systemPrompt "You are a rigorous research assistant. Cite sources, be objective, and structure arguments logically."
}

rag MainRAG {
  vectorStore basic
  embeddingModel "all-MiniLM-L6-v2"
  chunkSize 1024  // Larger for academic context
  chunkOverlap 256  // More overlap for citation context
  loaders ["pdf", "txt", "md", "docx"]
}

voice Assistant {
  provider system
  defaultVoice "default"
  rate 155  // Deliberate pace for comprehension
}

modes {
  default research
  routing smart
  fallback ["ollama", "openai"]
}

security {
  level standard
  rateLimit 100
  requireAuth false
}
""",
    ),
    "minimal": PersonaTemplate(
        name="Minimal",
        description="Bare minimum - just chatbot, no extras",
        mode_code="F",
        adl_content="""application AgenticBrain {
  name "Simple Chat"
  persona minimal
}

llm Primary {
  provider auto
  model "llama3.2:3b"
  temperature 0.7
  maxTokens 2048
}

modes {
  default free
  routing simple  // No smart routing
}

security {
  level standard
  rateLimit 100
  requireAuth false
}
""",
    ),
}


def get_persona_template(name: str) -> Optional[PersonaTemplate]:
    """Get a persona template by name."""
    return PERSONA_TEMPLATES.get(name.lower())


def list_personas() -> Dict[str, str]:
    """List all available personas with descriptions."""
    return {name: template.description for name, template in PERSONA_TEMPLATES.items()}


def generate_adl_from_persona(persona_name: str) -> str:
    """Generate ADL content from a persona name."""
    template = get_persona_template(persona_name)
    if template is None:
        raise ValueError(f"Unknown persona: {persona_name}")
    return template.adl_content


def get_persona_mode(persona_name: str) -> str:
    """Get the mode code for a persona."""
    template = get_persona_template(persona_name)
    if template is None:
        raise ValueError(f"Unknown persona: {persona_name}")
    return template.mode_code


__all__ = [
    "PersonaTemplate",
    "PERSONA_TEMPLATES",
    "get_persona_template",
    "list_personas",
    "generate_adl_from_persona",
    "get_persona_mode",
]
