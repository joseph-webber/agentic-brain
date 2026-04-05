#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
04 - Multi-User Sessions
=========================

Handle multiple users with isolated conversation sessions.
Each user has their own context that doesn't leak to others.

Use cases:
- Chatbot serving multiple customers
- Slack/Discord bot with per-user memory
- Multi-tenant AI applications

Run:
    python examples/04_multi_user.py

Requirements:
    - Ollama or OpenAI configured
    - Neo4j (optional, for persistence)
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional

from agentic_brain import Agent, DataScope, Neo4jMemory


@dataclass
class UserSession:
    """Represents a single user's chat session."""

    user_id: str
    agent: Agent
    message_count: int = 0
    context: Dict = field(default_factory=dict)


class MultiUserChatbot:
    """
    A chatbot that handles multiple users with isolated sessions.

    Each user gets:
    - Their own conversation history
    - Isolated memory scope (DataScope.PRIVATE)
    - Personal context that doesn't leak
    """

    def __init__(self, memory: Optional[Neo4jMemory] = None):
        """
        Initialize the multi-user chatbot.

        Args:
            memory: Optional Neo4j memory for persistence
        """
        self.memory = memory
        self.sessions: Dict[str, UserSession] = {}

    async def get_or_create_session(self, user_id: str) -> UserSession:
        """
        Get existing session or create new one for user.

        Args:
            user_id: Unique identifier for the user

        Returns:
            UserSession for this user
        """
        if user_id not in self.sessions:
            # Create new agent for this user
            agent = Agent(
                name=f"assistant-{user_id}",
                memory=self.memory,
                data_scope=DataScope.PRIVATE,  # User data is private
                system_prompt=f"You are a helpful assistant for user {user_id}. "
                "Remember their preferences and past conversations.",
            )

            # Create session
            self.sessions[user_id] = UserSession(user_id=user_id, agent=agent)
            print(f"📝 Created new session for user: {user_id}")

        return self.sessions[user_id]

    async def chat(self, user_id: str, message: str) -> str:
        """
        Handle a chat message from a user.

        Args:
            user_id: User sending the message
            message: The message content

        Returns:
            Agent's response
        """
        # Get or create session
        session = await self.get_or_create_session(user_id)

        # Increment message count
        session.message_count += 1

        # Get response from agent
        response = await session.agent.chat_async(message)

        return response

    async def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics for a user's session."""
        if user_id not in self.sessions:
            return {"error": "User not found"}

        session = self.sessions[user_id]
        return {
            "user_id": user_id,
            "message_count": session.message_count,
            "context": session.context,
        }

    async def clear_user_session(self, user_id: str) -> bool:
        """Clear a user's session (keeps long-term memory)."""
        if user_id in self.sessions:
            self.sessions[user_id].agent.clear_history()
            self.sessions[user_id].message_count = 0
            return True
        return False

    async def list_active_users(self) -> list:
        """List all active user sessions."""
        return list(self.sessions.keys())


async def simulate_multi_user_chat():
    """
    Simulate multiple users chatting simultaneously.

    This demonstrates:
    - Isolated conversations per user
    - No context leakage between users
    - Concurrent message handling
    """
    print("\n" + "=" * 60)
    print("Simulating Multi-User Chat")
    print("=" * 60)

    # Create multi-user chatbot
    chatbot = MultiUserChatbot()

    # Simulate conversations from different users
    conversations = [
        ("alice", "Hi! My name is Alice."),
        ("bob", "Hello, I'm Bob. I work as a developer."),
        ("alice", "I love hiking and photography."),
        ("bob", "Can you remember what I do for work?"),
        ("alice", "What's my name?"),
        ("charlie", "I'm new here. My name is Charlie."),
    ]

    print("\n📨 Processing messages from multiple users:\n")

    for user_id, message in conversations:
        # Process message
        response = await chatbot.chat(user_id, message)

        # Display
        print(f"[{user_id}] You: {message}")
        print(f"[{user_id}] Bot: {response}\n")

        # Small delay to simulate real usage
        await asyncio.sleep(0.1)

    # Show active users
    print("\n" + "=" * 60)
    print("Active Users:")
    users = await chatbot.list_active_users()
    for user in users:
        stats = await chatbot.get_user_stats(user)
        print(f"  • {user}: {stats['message_count']} messages")


async def interactive_multi_user():
    """
    Interactive multi-user chat mode.

    Switch between users to test isolation.
    """
    print("\n" + "=" * 60)
    print("Interactive Multi-User Chat")
    print("=" * 60)
    print("\nCommands:")
    print("  /user <name>  - Switch to user")
    print("  /list         - List active users")
    print("  /stats        - Show current user stats")
    print("  /quit         - Exit")
    print()

    chatbot = MultiUserChatbot()
    current_user = "default"

    while True:
        try:
            # Show current user in prompt
            user_input = input(f"[{current_user}] You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                parts = user_input.split()
                cmd = parts[0].lower()

                if cmd == "/quit":
                    print("Goodbye! 👋")
                    break

                elif cmd == "/user" and len(parts) > 1:
                    current_user = parts[1]
                    print(f"Switched to user: {current_user}")
                    continue

                elif cmd == "/list":
                    users = await chatbot.list_active_users()
                    print(f"Active users: {', '.join(users) if users else 'None'}")
                    continue

                elif cmd == "/stats":
                    stats = await chatbot.get_user_stats(current_user)
                    print(f"Stats: {stats}")
                    continue

                else:
                    print(f"Unknown command: {cmd}")
                    continue

            # Regular message
            response = await chatbot.chat(current_user, user_input)
            print(f"[{current_user}] Bot: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


async def main():
    """Run multi-user examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + "   Multi-User Sessions - Isolated Conversations".center(58) + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        # Run simulation
        await simulate_multi_user_chat()

        # Offer interactive mode
        print("\n" + "=" * 60)
        response = input("Start interactive multi-user mode? (y/n): ").strip().lower()
        if response == "y":
            await interactive_multi_user()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
