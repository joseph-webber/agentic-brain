"""
Agentic Brain Chatbot Examples

Ready-to-use chatbot implementations for various platforms.
Each chatbot combines:
- RAG loaders for historical context
- LLM Router for intelligent responses
- Conversation memory
- Platform-specific features

Available Chatbots:
- discord_bot.py - Discord server chatbot with slash commands
- (more coming soon)

Requirements vary by platform - see individual files.
"""

from pathlib import Path

# Export example paths for easy discovery
EXAMPLES_DIR = Path(__file__).parent
DISCORD_BOT = EXAMPLES_DIR / "discord_bot.py"

__all__ = ["EXAMPLES_DIR", "DISCORD_BOT"]
