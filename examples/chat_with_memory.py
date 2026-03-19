#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Chat with Memory Example
========================

A chatbot that remembers facts across sessions.
Uses Neo4j for long-term memory storage.

Run with: python examples/chat_with_memory.py

Requirements:
- Neo4j running (localhost:7687)
- Ollama running with llama3.1:8b
"""

from agentic_brain import Neo4jMemory
from agentic_brain.chat import Chatbot, ChatConfig


def main():
    # Connect to Neo4j memory
    print("Connecting to Neo4j...")
    try:
        memory = Neo4jMemory(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password"  # Change this!
        )
        print("✅ Connected to Neo4j")
    except Exception as e:
        print(f"⚠️  Neo4j not available: {e}")
        print("Running without memory...")
        memory = None
    
    # Create chatbot with persistence and memory
    config = ChatConfig(
        persist_sessions=True,
        use_memory=True,
        max_history=50
    )
    
    bot = Chatbot(
        name="memory-bot",
        memory=memory,
        config=config
    )
    
    print()
    print("=" * 50)
    print("🧠 Chat with Memory")
    print("=" * 50)
    print("I'll remember important facts you tell me.")
    print("Try: 'My name is Joseph' or 'Remember I work at ACME'")
    print("Commands: 'quit', 'stats', 'clear'")
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("Goodbye! Your session is saved. 👋")
                break
            
            if user_input.lower() == 'stats':
                print(f"📊 Stats: {bot.get_stats()}")
                continue
            
            if user_input.lower() == 'clear':
                bot.clear_session()
                print("🗑️  Session cleared")
                continue
            
            # Get response
            response = bot.chat(user_input)
            print(f"Bot: {response}")
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye! Your session is saved. 👋")
            break


if __name__ == "__main__":
    main()
