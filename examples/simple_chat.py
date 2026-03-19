#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Simple Chat Example
===================

A minimal chatbot that actually works.
Run with: python examples/simple_chat.py

Requirements:
- Ollama running locally with llama3.1:8b
- OR set environment variable: export OPENAI_API_KEY=your_key
"""

from agentic_brain.chat import Chatbot, ChatConfig


def main():
    # Create a simple chatbot (no persistence, no memory)
    config = ChatConfig.minimal()
    bot = Chatbot("assistant", config=config)
    
    print("=" * 50)
    print("🤖 Agentic Brain Chat")
    print("=" * 50)
    print("Type 'quit' to exit, 'stats' for statistics")
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("Goodbye! 👋")
                break
            
            if user_input.lower() == 'stats':
                print(f"📊 Stats: {bot.get_stats()}")
                continue
            
            # Get response
            response = bot.chat(user_input)
            print(f"Bot: {response}")
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


if __name__ == "__main__":
    main()
