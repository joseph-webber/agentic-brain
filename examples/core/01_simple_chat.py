#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Simple Chat - Minimal Example
==============================

The absolute minimum to get a chatbot running.
Just 5 lines of code to start chatting!

This is the "Hello World" of agentic-brain.

Level: 🟢 Beginner

Usage:
    python examples/core/01_simple_chat.py

Requirements:
    - Ollama running locally with llama3.1:8b
    - OR set OPENAI_API_KEY for OpenAI
"""

from agentic_brain import Agent

# Create an agent - that's it!
agent = Agent()

# Chat and get a response
response = agent.chat("Hello! What can you help me with?")

# Print the response
print(response)


# =============================================================================
# Interactive Mode
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Agentic Brain - Simple Chat")
    print("=" * 50)
    print("Type 'quit' to exit\n")

    # Create a fresh agent for interactive mode
    bot = Agent(name="assistant")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye! 👋")
                break

            response = bot.chat(user_input)
            print(f"Bot: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")
