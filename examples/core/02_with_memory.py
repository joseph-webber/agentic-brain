#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Chat with Neo4j Memory
=======================

A chatbot that remembers conversations across sessions.
Uses Neo4j graph database for persistent long-term memory.

The agent will:
- Remember facts you tell it ("My name is User")
- Recall information in future sessions
- Build a knowledge graph of your interactions

Level: 🟢 Beginner

Usage:
    python examples/core/02_with_memory.py

Requirements:
    - Neo4j running on localhost:7687
    - Ollama or OpenAI configured
    - pip install agentic-brain
"""

import asyncio
import logging

from agentic_brain import Agent, Neo4jMemory
from agentic_brain.errors import AgenticBrainError

logger = logging.getLogger(__name__)

# Neo4j connection settings (adjust for your setup)
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # Change this!


async def main() -> None:
    """Run the memory-enabled chatbot."""
    print("=" * 50)
    print("🧠 Agentic Brain - Chat with Memory")
    print("=" * 50)

    # Connect to Neo4j memory
    memory = None
    print("\nConnecting to Neo4j...")
    try:
        memory = Neo4jMemory(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
        print("✅ Connected to Neo4j")
    except AgenticBrainError as e:
        logger.warning("Neo4j not available: %s", e)
        print(f"⚠️  Neo4j not available: {e}")
        print("Running without persistent memory...")

    # Create agent with memory
    agent = Agent(
        name="memory-bot",
        memory=memory,
        system_prompt=(
            "You are a helpful assistant with perfect memory. "
            "Remember important facts the user tells you."
        ),
    )

    print("\n💡 Tips:")
    print("  - Tell me facts: 'My name is User'")
    print("  - Ask me later: 'What's my name?'")
    print("  - I'll remember across sessions!")
    print("\nCommands: 'quit', 'stats', 'clear'\n")

    try:
        while True:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() == "quit":
                print("Goodbye! Your memories are saved. 👋")
                break

            if user_input.lower() == "stats":
                if memory:
                    stats = await memory.get_stats()
                    print(f"📊 Memory Stats: {stats}")
                else:
                    print("📊 No persistent memory configured")
                continue

            if user_input.lower() == "clear":
                agent.clear_history()
                print("🗑️  Conversation cleared (memories preserved)")
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"Bot: {response}\n")

    except KeyboardInterrupt:
        print("\nGoodbye! Your memories are saved. 👋")
    finally:
        if memory:
            await memory.close()


if __name__ == "__main__":
    asyncio.run(main())
