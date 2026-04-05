#!/usr/bin/env python3
"""
Discord AI Chatbot with RAG - Agentic Brain Example

This example shows how to build an intelligent Discord chatbot that:
1. Uses the DiscordLoader to load past messages for context (RAG)
2. Uses LLMRouter for intelligent responses
3. Maintains conversation memory per channel/user
4. Supports slash commands and mentions

The DiscordLoader is ONE PIECE of the puzzle - it provides historical
context. Combined with real-time message handling and the LLM router,
you get a powerful conversational AI.

Requirements:
    pip install discord.py agentic-brain

Environment Variables:
    DISCORD_BOT_TOKEN: Your Discord bot token
    DISCORD_APPLICATION_ID: Your Discord application ID (for slash commands)

Discord Developer Portal Setup:
    1. Go to https://discord.com/developers/applications
    2. Create New Application
    3. Go to Bot section, create bot, copy token
    4. Go to OAuth2 > URL Generator
    5. Select: bot, applications.commands
    6. Bot Permissions: Send Messages, Read Message History, Use Slash Commands
    7. Copy generated URL and invite bot to your server

Author: Agentic Brain Team
License: GPL-3.0
Created: 2026-03-22
"""

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Discord imports
try:
    import discord
    from discord import app_commands
    from discord.ext import commands

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("discord.py not installed. Run: pip install discord.py")

# Agentic Brain imports
from agentic_brain import Agent, LLMRouter, Memory
from agentic_brain.chat import Chatbot
from agentic_brain.rag import DiscordLoader, VectorStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class BotConfig:
    """Discord bot configuration."""

    # Bot settings
    name: str = "BrainBot"
    description: str = "An intelligent AI assistant powered by Agentic Brain"
    prefix: str = "!"

    # AI settings
    model: str = "gpt-4"
    fallback_model: str = "ollama/llama3.1:8b"
    max_tokens: int = 1000
    temperature: float = 0.7

    # RAG settings
    enable_rag: bool = True
    rag_context_messages: int = 50  # How many past messages to load for context
    rag_context_days: int = 7  # How many days back to search

    # Memory settings
    memory_per_channel: bool = True  # Separate memory per channel
    memory_per_user: bool = False  # Or separate per user
    max_memory_messages: int = 20  # How many messages to remember

    # Rate limiting
    cooldown_seconds: float = 1.0
    max_response_length: int = 2000  # Discord limit

    # Channels to operate in (empty = all)
    allowed_channels: List[int] = field(default_factory=list)

    # System prompt
    system_prompt: str = """You are a helpful AI assistant in a Discord server.
Be friendly, concise, and helpful. Use Discord markdown for formatting.
Keep responses under 2000 characters (Discord limit).
If you don't know something, say so honestly.
You can use emojis to make responses more engaging. 🤖"""


# =============================================================================
# Conversation Memory
# =============================================================================


class ConversationMemory:
    """Manage conversation memory per channel or user."""

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self._memories: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def get_key(self, channel_id: int, user_id: int, per_channel: bool = True) -> str:
        """Get memory key."""
        if per_channel:
            return f"channel:{channel_id}"
        return f"user:{user_id}"

    def add_message(self, key: str, role: str, content: str, user_name: str = None):
        """Add message to memory."""
        self._memories[key].append(
            {
                "role": role,
                "content": content,
                "user_name": user_name,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Trim to max size
        if len(self._memories[key]) > self.max_messages:
            self._memories[key] = self._memories[key][-self.max_messages :]

    def get_messages(self, key: str) -> List[Dict[str, Any]]:
        """Get messages for context."""
        return self._memories[key].copy()

    def clear(self, key: str):
        """Clear memory for key."""
        self._memories[key] = []

    def format_for_llm(self, key: str) -> List[Dict[str, str]]:
        """Format messages for LLM context."""
        messages = []
        for msg in self._memories[key]:
            if msg["role"] == "user":
                name = msg.get("user_name", "User")
                messages.append(
                    {"role": "user", "content": f"[{name}]: {msg['content']}"}
                )
            else:
                messages.append({"role": "assistant", "content": msg["content"]})
        return messages


# =============================================================================
# RAG Context Manager
# =============================================================================


class DiscordRAGContext:
    """Manage RAG context from Discord history."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.loader: Optional[DiscordLoader] = None
        self.vector_store: Optional[VectorStore] = None
        self._channel_contexts: Dict[int, List[str]] = {}

    async def initialize(self, token: str):
        """Initialize RAG components."""
        if not self.config.enable_rag:
            logger.info("RAG disabled in config")
            return

        try:
            self.loader = DiscordLoader(token=token)
            self.loader.authenticate()

            # Initialize vector store for semantic search
            self.vector_store = VectorStore(
                provider="sentence_transformers", model="all-MiniLM-L6-v2"
            )

            logger.info("RAG context manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            self.loader = None

    async def load_channel_context(self, channel_id: int) -> List[str]:
        """Load recent messages from channel for context."""
        if not self.loader or channel_id in self._channel_contexts:
            return self._channel_contexts.get(channel_id, [])

        try:
            # Load recent messages
            docs = await asyncio.to_thread(
                self.loader.load_channel,
                channel_id,
                limit=self.config.rag_context_messages,
            )

            # Extract text content
            context = [doc.content for doc in docs if doc.content]
            self._channel_contexts[channel_id] = context

            # Index in vector store for semantic search
            if self.vector_store and context:
                await asyncio.to_thread(
                    self.vector_store.add_texts,
                    context,
                    metadatas=[
                        {"channel_id": channel_id, "index": i}
                        for i in range(len(context))
                    ],
                )

            logger.info(f"Loaded {len(context)} messages from channel {channel_id}")
            return context

        except Exception as e:
            logger.error(f"Failed to load channel context: {e}")
            return []

    async def search_context(
        self, query: str, channel_id: int = None, k: int = 5
    ) -> List[str]:
        """Search for relevant context using semantic search."""
        if not self.vector_store:
            return []

        try:
            # Search with optional channel filter
            filter_dict = {"channel_id": channel_id} if channel_id else None

            results = await asyncio.to_thread(
                self.vector_store.similarity_search, query, k=k, filter=filter_dict
            )

            return [r.content for r in results]

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return []


# =============================================================================
# Main Discord Bot
# =============================================================================


class AgenticBrainBot(commands.Bot):
    """Discord bot powered by Agentic Brain."""

    def __init__(self, config: BotConfig = None):
        self.config = config or BotConfig()

        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix=self.config.prefix,
            description=self.config.description,
            intents=intents,
        )

        # Initialize components
        self.memory = ConversationMemory(max_messages=self.config.max_memory_messages)
        self.rag_context: Optional[DiscordRAGContext] = None
        self.router: Optional[LLMRouter] = None
        self._cooldowns: Dict[int, datetime] = {}

    async def setup_hook(self):
        """Called when bot is starting up."""
        logger.info("Setting up Agentic Brain Bot...")

        # Initialize LLM Router
        self.router = LLMRouter(
            default_model=self.config.model,
            fallback_models=[self.config.fallback_model],
            enable_fallback=True,
        )

        # Initialize RAG context
        token = os.environ.get("DISCORD_BOT_TOKEN")
        self.rag_context = DiscordRAGContext(self.config)
        await self.rag_context.initialize(token)

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        logger.info("Bot setup complete!")

    async def on_ready(self):
        """Called when bot is connected and ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Set status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"@{self.user.name} or {self.config.prefix}ask",
            )
        )

    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        # Ignore own messages and bots
        if message.author == self.user or message.author.bot:
            return

        # Check if in allowed channel
        if (
            self.config.allowed_channels
            and message.channel.id not in self.config.allowed_channels
        ):
            return

        # Check for mention or DM
        should_respond = (
            self.user.mentioned_in(message)
            or isinstance(message.channel, discord.DMChannel)
            or message.content.startswith(self.config.prefix)
        )

        if not should_respond:
            return

        # Check cooldown
        if not self._check_cooldown(message.author.id):
            return

        # Process message
        async with message.channel.typing():
            await self._handle_message(message)

        # Process commands too
        await self.process_commands(message)

    def _check_cooldown(self, user_id: int) -> bool:
        """Check if user is on cooldown."""
        now = datetime.now()
        last_msg = self._cooldowns.get(user_id)

        if last_msg and (now - last_msg).total_seconds() < self.config.cooldown_seconds:
            return False

        self._cooldowns[user_id] = now
        return True

    async def _handle_message(self, message: discord.Message):
        """Generate response to message."""
        try:
            # Clean message content (remove mention)
            content = message.content
            for mention in message.mentions:
                content = content.replace(f"<@{mention.id}>", "").replace(
                    f"<@!{mention.id}>", ""
                )
            content = content.strip()

            if not content:
                content = "Hello!"

            # Get memory key
            memory_key = self.memory.get_key(
                message.channel.id, message.author.id, self.config.memory_per_channel
            )

            # Add user message to memory
            self.memory.add_message(
                memory_key, "user", content, message.author.display_name
            )

            # Build context
            context_messages = self.memory.format_for_llm(memory_key)

            # Get RAG context if enabled
            rag_context = ""
            if self.rag_context and self.config.enable_rag:
                relevant = await self.rag_context.search_context(
                    content, channel_id=message.channel.id, k=3
                )
                if relevant:
                    rag_context = "\n\nRelevant past discussions:\n" + "\n---\n".join(
                        relevant
                    )

            # Build system prompt with RAG context
            system_prompt = self.config.system_prompt
            if rag_context:
                system_prompt += rag_context

            # Generate response
            response = await self._generate_response(
                system_prompt=system_prompt,
                messages=context_messages,
                user_message=content,
            )

            # Add response to memory
            self.memory.add_message(memory_key, "assistant", response)

            # Send response (handle Discord length limits)
            await self._send_response(message.channel, response)

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await message.channel.send(
                "Sorry, I encountered an error. Please try again. 😅"
            )

    async def _generate_response(
        self, system_prompt: str, messages: List[Dict[str, str]], user_message: str
    ) -> str:
        """Generate response using LLM Router."""
        try:
            # Build full messages list
            full_messages = [{"role": "system", "content": system_prompt}]
            full_messages.extend(messages)

            # Generate response
            response = await asyncio.to_thread(
                self.router.chat,
                messages=full_messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            return response.content

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")

            # Try fallback
            try:
                response = await asyncio.to_thread(
                    self.router.chat,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    model=self.config.fallback_model,
                    max_tokens=self.config.max_tokens,
                )
                return response.content + "\n\n_*Using fallback model*_"
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                raise

    async def _send_response(self, channel: discord.TextChannel, response: str):
        """Send response, handling Discord length limits."""
        # Discord has 2000 char limit
        max_len = self.config.max_response_length

        if len(response) <= max_len:
            await channel.send(response)
            return

        # Split into chunks
        chunks = []
        while response:
            if len(response) <= max_len:
                chunks.append(response)
                break

            # Find good break point
            break_point = response.rfind("\n", 0, max_len)
            if break_point == -1:
                break_point = response.rfind(" ", 0, max_len)
            if break_point == -1:
                break_point = max_len

            chunks.append(response[:break_point])
            response = response[break_point:].lstrip()

        # Send chunks
        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(0.5)  # Small delay between chunks
            await channel.send(chunk)


# =============================================================================
# Slash Commands
# =============================================================================


def setup_commands(bot: AgenticBrainBot):
    """Set up slash commands."""

    @bot.tree.command(name="ask", description="Ask the AI a question")
    @app_commands.describe(question="Your question for the AI")
    async def ask(interaction: discord.Interaction, question: str):
        """Ask the AI a question."""
        await interaction.response.defer(thinking=True)

        try:
            # Get memory context
            memory_key = bot.memory.get_key(
                interaction.channel_id,
                interaction.user.id,
                bot.config.memory_per_channel,
            )

            # Add to memory
            bot.memory.add_message(
                memory_key, "user", question, interaction.user.display_name
            )

            # Generate response
            response = await bot._generate_response(
                system_prompt=bot.config.system_prompt,
                messages=bot.memory.format_for_llm(memory_key),
                user_message=question,
            )

            # Add response to memory
            bot.memory.add_message(memory_key, "assistant", response)

            # Send response
            if len(response) > 2000:
                response = response[:1997] + "..."

            await interaction.followup.send(response)

        except Exception as e:
            logger.error(f"Slash command error: {e}")
            await interaction.followup.send(
                "Sorry, something went wrong. Please try again. 😅"
            )

    @bot.tree.command(name="clear", description="Clear conversation memory")
    async def clear(interaction: discord.Interaction):
        """Clear conversation memory."""
        memory_key = bot.memory.get_key(
            interaction.channel_id, interaction.user.id, bot.config.memory_per_channel
        )
        bot.memory.clear(memory_key)
        await interaction.response.send_message(
            "Memory cleared! Starting fresh. 🧹", ephemeral=True
        )

    @bot.tree.command(name="model", description="Check or change the AI model")
    @app_commands.describe(new_model="New model to use (optional)")
    async def model(interaction: discord.Interaction, new_model: str = None):
        """Check or change model."""
        if new_model:
            bot.config.model = new_model
            await interaction.response.send_message(
                f"Model changed to: `{new_model}` ✅", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Current model: `{bot.config.model}`\n"
                f"Fallback: `{bot.config.fallback_model}`",
                ephemeral=True,
            )

    @bot.tree.command(name="help", description="Show bot help")
    async def help_command(interaction: discord.Interaction):
        """Show help message."""
        embed = discord.Embed(
            title=f"🤖 {bot.config.name} Help",
            description=bot.config.description,
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="💬 Chat", value="Just @mention me or DM me to chat!", inline=False
        )

        embed.add_field(
            name="📝 Commands",
            value=(
                "`/ask` - Ask a question\n"
                "`/clear` - Clear memory\n"
                "`/model` - Check/change model\n"
                "`/search` - Search channel history\n"
                "`/help` - This help message"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚙️ Features",
            value=(
                "✅ Conversation memory\n"
                "✅ RAG context from channel history\n"
                "✅ Automatic fallback to local LLM\n"
                "✅ Multi-server support"
            ),
            inline=False,
        )

        embed.set_footer(text="Powered by Agentic Brain 🧠")

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="search", description="Search channel history")
    @app_commands.describe(query="What to search for")
    async def search(interaction: discord.Interaction, query: str):
        """Search channel history using RAG."""
        await interaction.response.defer(thinking=True)

        if not bot.rag_context or not bot.config.enable_rag:
            await interaction.followup.send(
                "RAG search is not enabled for this bot.", ephemeral=True
            )
            return

        try:
            # Load channel context if not already
            await bot.rag_context.load_channel_context(interaction.channel_id)

            # Search
            results = await bot.rag_context.search_context(
                query, channel_id=interaction.channel_id, k=5
            )

            if not results:
                await interaction.followup.send(
                    f"No results found for: `{query}`", ephemeral=True
                )
                return

            # Format results
            embed = discord.Embed(
                title=f"🔍 Search Results: {query}", color=discord.Color.green()
            )

            for i, result in enumerate(results, 1):
                # Truncate long results
                text = result[:200] + "..." if len(result) > 200 else result
                embed.add_field(name=f"Result {i}", value=text, inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Search error: {e}")
            await interaction.followup.send(
                "Search failed. Please try again.", ephemeral=True
            )

    @bot.tree.command(name="stats", description="Show bot statistics")
    async def stats(interaction: discord.Interaction):
        """Show bot stats."""
        # Get router stats if available
        router_stats = {}
        if bot.router:
            try:
                router_stats = bot.router.get_stats()
            except:
                pass

        embed = discord.Embed(title="📊 Bot Statistics", color=discord.Color.purple())

        embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)

        embed.add_field(name="Model", value=bot.config.model, inline=True)

        embed.add_field(
            name="RAG Enabled",
            value="✅ Yes" if bot.config.enable_rag else "❌ No",
            inline=True,
        )

        if router_stats:
            embed.add_field(
                name="LLM Requests",
                value=str(router_stats.get("total_requests", "N/A")),
                inline=True,
            )

            embed.add_field(
                name="Fallbacks Used",
                value=str(router_stats.get("fallback_count", 0)),
                inline=True,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# =============================================================================
# Specialized Bot Variants
# =============================================================================


class CustomerSupportBot(AgenticBrainBot):
    """Discord bot configured for customer support."""

    def __init__(self):
        config = BotConfig(
            name="SupportBot",
            description="Customer support assistant",
            system_prompt="""You are a helpful customer support assistant.
Be professional, empathetic, and solution-focused.
If you can't help with something, politely explain and suggest alternatives.
Always be patient and understanding.
Use clear, simple language.""",
            temperature=0.5,  # More consistent
            enable_rag=True,  # Use past tickets for context
        )
        super().__init__(config)


class CodingAssistantBot(AgenticBrainBot):
    """Discord bot configured for coding help."""

    def __init__(self):
        config = BotConfig(
            name="CodeBot",
            description="Coding assistant",
            system_prompt="""You are an expert coding assistant.
Help with programming questions, debug code, explain concepts.
Always provide code examples when helpful.
Use Discord markdown for code blocks: ```language
Be precise and technically accurate.""",
            model="gpt-4",  # Best for code
            temperature=0.3,  # More precise
        )
        super().__init__(config)


class CommunityModBot(AgenticBrainBot):
    """Discord bot configured for community moderation assistance."""

    def __init__(self):
        config = BotConfig(
            name="ModBot",
            description="Community moderation assistant",
            system_prompt="""You are a community moderation assistant.
Help answer questions about server rules and guidelines.
Be fair, consistent, and helpful.
Direct complex issues to human moderators.
Never make final moderation decisions - only advise.""",
            temperature=0.4,
            enable_rag=True,  # Learn from past discussions
        )
        super().__init__(config)


# =============================================================================
# Australian Business Bot (WCAG Compliant)
# =============================================================================


class AustralianBusinessBot(AgenticBrainBot):
    """Discord bot for Australian business community.

    Features:
    - Australian business hours awareness
    - ACL consumer law compliance
    - ASIC/ACCC regulation awareness
    - Legal disclaimers
    """

    def __init__(self):
        config = BotConfig(
            name="AusBusinessBot",
            description="Australian business assistant with legal compliance",
            system_prompt="""You are an Australian business assistant.
You help with business questions while being mindful of Australian regulations.

IMPORTANT DISCLAIMERS:
- You provide general information only, NOT legal or financial advice
- Always recommend consulting qualified professionals for specific matters
- Be aware of Australian Consumer Law (ACL) protections
- Reference ASIC, ACCC, and Fair Work when relevant

Australian business context:
- Standard business hours: 9am-5pm AEST/AEDT
- GST is 10% on most goods/services
- ABN required for businesses
- Fair Work Act governs employment

Always be helpful, accurate, and compliant. 🦘""",
            temperature=0.4,
            enable_rag=True,
        )
        super().__init__(config)

    async def _generate_response(
        self, system_prompt: str, messages: list, user_message: str
    ) -> str:
        """Override to add Australian legal disclaimer when needed."""
        response = await super()._generate_response(
            system_prompt, messages, user_message
        )

        # Add disclaimer for sensitive topics
        sensitive_keywords = [
            "legal",
            "law",
            "tax",
            "financial",
            "invest",
            "sue",
            "court",
            "contract",
        ]
        if any(kw in user_message.lower() for kw in sensitive_keywords):
            response += "\n\n_⚠️ This is general information only, not professional advice. Please consult a qualified Australian professional for your specific situation._"

        return response


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Main entry point."""
    if not DISCORD_AVAILABLE:
        print("Error: discord.py is required")
        print("Install with: pip install discord.py")
        return

    # Get token
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        print("\nTo get a token:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Create an application")
        print("3. Go to Bot section, create bot")
        print("4. Copy token and set DISCORD_BOT_TOKEN")
        return

    # Create bot
    bot = AgenticBrainBot()

    # Set up commands
    setup_commands(bot)

    # Add some basic prefix commands
    @bot.command(name="ping")
    async def ping(ctx):
        """Check bot latency."""
        latency = round(bot.latency * 1000)
        await ctx.send(f"Pong! 🏓 Latency: {latency}ms")

    @bot.command(name="info")
    async def info(ctx):
        """Show bot info."""
        embed = discord.Embed(
            title=f"ℹ️ {bot.config.name}",
            description=bot.config.description,
            color=discord.Color.blue(),
        )
        embed.add_field(name="Prefix", value=bot.config.prefix)
        embed.add_field(name="Model", value=bot.config.model)
        embed.add_field(
            name="RAG", value="Enabled" if bot.config.enable_rag else "Disabled"
        )
        embed.set_footer(text="Powered by Agentic Brain")
        await ctx.send(embed=embed)

    # Run bot
    print(f"Starting {bot.config.name}...")
    print(f"Model: {bot.config.model}")
    print(f"RAG: {'Enabled' if bot.config.enable_rag else 'Disabled'}")
    print("Press Ctrl+C to stop")

    bot.run(token)


if __name__ == "__main__":
    main()
