#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Streaming Responses
====================

Real-time token-by-token streaming for instant UX.
Watch responses appear character by character!

Streaming provides:
- Immediate visual feedback
- Better perceived performance
- Real-time UI updates

Level: 🟡 Intermediate

Usage:
    python examples/core/03_streaming.py

Requirements:
    - Ollama running with llama3.1:8b
    - OR set OPENAI_API_KEY for OpenAI
    - pip install agentic-brain
"""

import asyncio
import logging
from typing import AsyncGenerator

from agentic_brain.errors import AgenticBrainError

from agentic_brain.streaming import StreamingResponse

logger = logging.getLogger(__name__)


async def basic_streaming():
    """
    Example 1: Basic token streaming.

    Simplest approach - stream tokens directly.
    """
    print("\n" + "=" * 60)
    print("Example 1: Basic Token Streaming")
    print("=" * 60)

    # Create streaming response handler
    streamer = StreamingResponse(
        provider="ollama",  # or "openai", "anthropic"
        model="llama3.1:8b",  # or "gpt-4", "claude-3-sonnet"
        temperature=0.7,
    )

    prompt = "What is machine learning in 2-3 sentences?"
    print(f"\nPrompt: {prompt}\n")
    print("Response: ", end="", flush=True)

    # Stream tokens as they arrive
    async for token in streamer.stream(prompt):
        # Print each token immediately
        print(token.token, end="", flush=True)

    print("\n")  # Newline after response


async def streaming_with_history():
    """
    Example 2: Streaming with conversation history.

    Multi-turn conversation with context.
    """
    print("\n" + "=" * 60)
    print("Example 2: Streaming with Conversation History")
    print("=" * 60)

    # Previous conversation context
    history = [
        {"role": "user", "content": "What is AI?"},
        {
            "role": "assistant",
            "content": "AI is artificial intelligence - machines that can learn and reason.",
        },
    ]

    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.5,
    )

    print("\nConversation history:")
    for msg in history:
        role = "You" if msg["role"] == "user" else "Bot"
        print(f"  {role}: {msg['content']}")

    follow_up = "Can you give me an example?"
    print(f"\nYou: {follow_up}")
    print("Bot: ", end="", flush=True)

    # Stream with history for context
    async for token in streamer.stream(follow_up, history=history):
        print(token.token, end="", flush=True)

    print("\n")


async def streaming_with_callbacks():
    """
    Example 3: Streaming with start/end callbacks.

    Track stream lifecycle events.
    """
    print("\n" + "=" * 60)
    print("Example 3: Stream Lifecycle Events")
    print("=" * 60)

    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        max_tokens=100,
    )

    token_count = 0

    print("\nPrompt: Explain quantum computing briefly.\n")

    async for token in streamer.stream("Explain quantum computing briefly."):
        # Detect stream start
        if token.is_start:
            print("⬇️  Stream started!")
            print("Response: ", end="", flush=True)

        # Print token
        print(token.token, end="", flush=True)
        token_count += 1

        # Detect stream end
        if token.is_end:
            print("\n\n✅ Stream complete!")
            print(f"   Tokens: {token_count}")
            print(f"   Finish reason: {token.finish_reason}")


async def interactive_streaming():
    """
    Interactive streaming chat session.
    """
    print("\n" + "=" * 60)
    print("Interactive Streaming Chat")
    print("=" * 60)
    print("Type 'quit' to exit\n")

    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.7,
    )

    history = []

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye! 👋")
                break

            # Add to history
            history.append({"role": "user", "content": user_input})

            # Stream response
            print("Bot: ", end="", flush=True)
            response_text = ""

            async for token in streamer.stream(user_input, history=history[:-1]):
                print(token.token, end="", flush=True)
                response_text += token.token

            print("\n")

            # Add response to history
            history.append({"role": "assistant", "content": response_text})

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


async def main():
    """Run all streaming examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + "   Streaming Responses - Real-time Token Delivery".center(58) + "║")
    print("╚" + "=" * 58 + "╝")

    print("\n🚀 Make sure Ollama is running: ollama serve")

    try:
        # Run examples
        await basic_streaming()
        await streaming_with_history()
        await streaming_with_callbacks()

        # Offer interactive mode
        print("\n" + "=" * 60)
        response = input("Start interactive streaming chat? (y/n): ").strip().lower()
        if response == "y":
            await interactive_streaming()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure Ollama is running with llama3.1:8b")


if __name__ == "__main__":
    asyncio.run(main())
