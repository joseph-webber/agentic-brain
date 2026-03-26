#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
06 - Custom System Prompts & Personas
======================================

Create specialized AI assistants with custom personalities!
Define system prompts that control behavior, tone, and expertise.

Use cases:
- Customer service bot with brand voice
- Technical expert with specific domain knowledge
- Creative writing assistant
- Code review specialist

Run:
    python examples/06_custom_prompts.py

Requirements:
    - Ollama or OpenAI configured
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from agentic_brain import Agent

# ============================================================================
# Example Personas
# ============================================================================


@dataclass
class Persona:
    """Defines an AI persona with specific characteristics."""

    name: str
    description: str
    system_prompt: str
    temperature: float = 0.7


# Pre-built personas
PERSONAS = {
    "pirate": Persona(
        name="Captain Claude",
        description="A friendly pirate who speaks in pirate dialect",
        system_prompt="""You are Captain Claude, a friendly pirate captain!

Personality:
- Speak in pirate dialect (arrr, matey, ye, etc.)
- Be helpful but add pirate flavor to everything
- Reference sea adventures and treasure
- End messages with pirate exclamations

Example:
User: What's the weather like?
You: Arrr, let me check the skies for ye, matey! The horizon be lookin' clear today, perfect weather for sailin'! ⚓
""",
        temperature=0.8,
    ),
    "expert": Persona(
        name="Dr. TechBot",
        description="A senior software architect with deep technical expertise",
        system_prompt="""You are Dr. TechBot, a senior software architect with 20+ years experience.

Expertise:
- System design and architecture
- Python, TypeScript, Go, Rust
- Cloud platforms (AWS, GCP, Azure)
- Databases (SQL, NoSQL, Graph)
- DevOps and CI/CD

Communication style:
- Be precise and technical
- Provide code examples when helpful
- Explain trade-offs
- Reference best practices and patterns
- Be confident but acknowledge uncertainty

Always consider: performance, scalability, maintainability, security.
""",
        temperature=0.3,
    ),
    "poet": Persona(
        name="Verse",
        description="A creative poet who responds in verse",
        system_prompt="""You are Verse, a creative poet who expresses everything through poetry.

Style:
- Respond in verse (rhyming when natural)
- Use metaphors and imagery
- Be thoughtful and contemplative
- Vary between short haikus and longer poems
- Express technical concepts poetically

Example:
User: Explain recursion
You: A function calls itself once more,
     Like mirrors facing, floor to floor,
     Each reflection holds the last,
     Until the base case comes at last.
""",
        temperature=0.9,
    ),
    "tutor": Persona(
        name="Professor Learn",
        description="A patient Socratic tutor",
        system_prompt="""You are Professor Learn, a patient and encouraging tutor.

Teaching approach:
- Use the Socratic method - ask guiding questions
- Break complex topics into small steps
- Provide encouragement and positive reinforcement
- Use analogies and real-world examples
- Check understanding before moving forward
- Never make the student feel stupid

Structure responses:
1. Acknowledge their question
2. Ask a guiding question OR explain one concept
3. Provide an example
4. Check understanding

End each response with encouragement or a thought-provoking question.
""",
        temperature=0.5,
    ),
    "reviewer": Persona(
        name="CodeReviewer",
        description="A thorough but kind code reviewer",
        system_prompt="""You are CodeReviewer, an expert code reviewer focused on quality.

Review criteria:
1. Correctness - Does it work as intended?
2. Readability - Is it clear and maintainable?
3. Performance - Are there obvious inefficiencies?
4. Security - Any vulnerabilities?
5. Best practices - Following conventions?

Communication:
- Start with something positive (specific)
- Be direct but kind
- Explain WHY something should change
- Provide concrete suggestions
- Prioritize issues (critical/important/minor)

Use format:
✅ Good: [specific praise]
⚠️ Consider: [suggestion with reason]
❌ Issue: [problem and fix]
""",
        temperature=0.3,
    ),
}


async def demo_personas():
    """
    Demonstrate different personas with the same question.
    """
    print("\n" + "=" * 60)
    print("Persona Demo - Same Question, Different Styles")
    print("=" * 60)

    question = "Explain what recursion is in programming"

    for persona_name in ["pirate", "expert", "poet", "tutor"]:
        persona = PERSONAS[persona_name]

        print(f"\n🎭 {persona.name} ({persona.description})")
        print("-" * 50)

        # Create agent with persona
        agent = Agent(
            name=persona_name,
            system_prompt=persona.system_prompt,
            temperature=persona.temperature,
        )

        # Get response
        response = await agent.chat_async(question)
        print(response)


async def custom_persona_builder():
    """
    Build a custom persona interactively.
    """
    print("\n" + "=" * 60)
    print("Custom Persona Builder")
    print("=" * 60)

    print("\n📝 Let's create your custom AI persona!\n")

    # Get persona details
    name = input("Persona name: ").strip() or "CustomBot"
    role = (
        input("What role/expertise? (e.g., 'fitness coach'): ").strip() or "assistant"
    )
    tone = (
        input("Communication tone? (e.g., 'friendly', 'professional'): ").strip()
        or "helpful"
    )

    # Build system prompt
    system_prompt = f"""You are {name}, a {role}.

Communication style:
- Tone: {tone}
- Be helpful and knowledgeable in your domain
- Provide practical, actionable advice
- Stay in character consistently

You are an expert in your field. Help users with enthusiasm!
"""

    print(f"\n✅ Created persona: {name}")
    print(f"System prompt:\n{system_prompt}")

    # Test the persona
    print("\n" + "=" * 60)
    print(f"Chat with {name}")
    print("=" * 60)
    print("Type 'quit' to exit\n")

    agent = Agent(name=name, system_prompt=system_prompt, temperature=0.7)

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye! 👋")
                break

            response = await agent.chat_async(user_input)
            print(f"{name}: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


async def interactive_persona_chat():
    """
    Chat with different personas interactively.
    """
    print("\n" + "=" * 60)
    print("Interactive Persona Chat")
    print("=" * 60)
    print("\nAvailable personas:")
    for name, persona in PERSONAS.items():
        print(f"  • {name}: {persona.description}")
    print("\nCommands:")
    print("  /switch <name>  - Switch persona")
    print("  /list           - List personas")
    print("  /quit           - Exit\n")

    current_persona = "expert"
    persona = PERSONAS[current_persona]
    agent = Agent(
        name=persona.name,
        system_prompt=persona.system_prompt,
        temperature=persona.temperature,
    )

    print(f"Currently: {persona.name}\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                parts = user_input.split()
                cmd = parts[0].lower()

                if cmd == "/quit":
                    print("Goodbye! 👋")
                    break

                elif cmd == "/list":
                    print("\nPersonas:")
                    for name, p in PERSONAS.items():
                        marker = "→" if name == current_persona else " "
                        print(f"  {marker} {name}: {p.description}")
                    print()
                    continue

                elif cmd == "/switch" and len(parts) > 1:
                    new_persona = parts[1].lower()
                    if new_persona in PERSONAS:
                        current_persona = new_persona
                        persona = PERSONAS[current_persona]
                        agent = Agent(
                            name=persona.name,
                            system_prompt=persona.system_prompt,
                            temperature=persona.temperature,
                        )
                        print(f"✅ Switched to: {persona.name}\n")
                    else:
                        print(f"❌ Unknown persona: {new_persona}")
                    continue

                else:
                    print(f"Unknown command: {cmd}")
                    continue

            # Regular chat
            response = await agent.chat_async(user_input)
            print(f"{persona.name}: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


async def main():
    """Run persona examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + "   Custom Prompts & Personas".center(58) + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        # Demo personas
        await demo_personas()

        # Menu
        print("\n" + "=" * 60)
        print("What would you like to do?")
        print("  1. Chat with existing personas")
        print("  2. Build a custom persona")
        print("  3. Exit")

        choice = input("\nChoice (1-3): ").strip()

        if choice == "1":
            await interactive_persona_chat()
        elif choice == "2":
            await custom_persona_builder()
        else:
            print("Goodbye! 👋")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
