#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Live Chat Customer Support Bot
==============================

Real-time customer chat support with:
- Typing indicators and read receipts
- Conversation handoff to human agents
- Canned responses for common questions
- Customer sentiment detection
- Chat history and context retention
- CSAT survey after chat completion

Demo: Electronics store support (monitors, keyboards, cables)
"""

import asyncio
import json
import random
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ChatStatus(Enum):
    """Chat session status."""

    WAITING = "waiting"
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class AgentType(Enum):
    """Type of agent handling the chat."""

    BOT = "bot"
    HUMAN = "human"


class Sentiment(Enum):
    """Customer sentiment levels."""

    VERY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    VERY_POSITIVE = 2


class MessageType(Enum):
    """Types of chat messages."""

    TEXT = "text"
    SYSTEM = "system"
    TYPING = "typing"
    READ_RECEIPT = "read_receipt"
    TRANSFER = "transfer"
    CSAT = "csat"


@dataclass
class ChatMessage:
    """A single chat message."""

    id: str
    content: str
    sender: str
    sender_type: AgentType
    timestamp: datetime
    message_type: MessageType = MessageType.TEXT
    metadata: dict = field(default_factory=dict)
    read: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "sender": self.sender,
            "sender_type": self.sender_type.value,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type.value,
            "metadata": self.metadata,
            "read": self.read,
        }


@dataclass
class Customer:
    """Customer information."""

    id: str
    name: str
    email: str
    phone: Optional[str] = None
    tier: str = "standard"
    previous_chats: int = 0
    lifetime_value: float = 0.0
    tags: list = field(default_factory=list)

    @property
    def is_vip(self) -> bool:
        return self.tier == "vip" or self.lifetime_value > 1000


@dataclass
class HumanAgent:
    """Human support agent."""

    id: str
    name: str
    skills: list
    max_concurrent: int = 3
    current_chats: int = 0
    available: bool = True
    avg_resolution_time: float = 300.0

    @property
    def can_accept_chat(self) -> bool:
        return self.available and self.current_chats < self.max_concurrent


@dataclass
class ChatSession:
    """A live chat session."""

    id: str
    customer: Customer
    status: ChatStatus
    created_at: datetime
    messages: list = field(default_factory=list)
    current_agent: Optional[str] = None
    agent_type: AgentType = AgentType.BOT
    sentiment_history: list = field(default_factory=list)
    escalation_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None
    csat_score: Optional[int] = None
    tags: list = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        end = self.resolved_at or datetime.now()
        return (end - self.created_at).total_seconds()

    @property
    def message_count(self) -> int:
        return len([m for m in self.messages if m.message_type == MessageType.TEXT])

    @property
    def current_sentiment(self) -> Sentiment:
        if not self.sentiment_history:
            return Sentiment.NEUTRAL
        return self.sentiment_history[-1]


class SentimentAnalyzer:
    """Analyzes customer sentiment from messages."""

    NEGATIVE_PATTERNS = [
        r"\b(angry|furious|upset|frustrated|annoyed|terrible|awful|horrible)\b",
        r"\b(hate|worst|useless|broken|scam|rip.?off|waste)\b",
        r"\b(ridiculous|unacceptable|disappointed|disgusted)\b",
        r"(!{2,}|\?{2,})",
        r"\b(wtf|bs|damn|hell)\b",
    ]

    POSITIVE_PATTERNS = [
        r"\b(thanks|thank you|appreciate|grateful|awesome|great|excellent)\b",
        r"\b(perfect|wonderful|amazing|fantastic|love|helpful)\b",
        r"\b(good job|well done|impressed|satisfied)\b",
        r"(:\)|😊|👍|❤️|🙏)",
    ]

    ESCALATION_PATTERNS = [
        r"\b(manager|supervisor|human|person|real person|escalate)\b",
        r"\b(speak to someone|talk to someone|not a bot)\b",
        r"\b(sue|lawyer|legal|complaint|report)\b",
    ]

    def __init__(self):
        self.negative_regex = [
            re.compile(p, re.IGNORECASE) for p in self.NEGATIVE_PATTERNS
        ]
        self.positive_regex = [
            re.compile(p, re.IGNORECASE) for p in self.POSITIVE_PATTERNS
        ]
        self.escalation_regex = [
            re.compile(p, re.IGNORECASE) for p in self.ESCALATION_PATTERNS
        ]

    def analyze(self, text: str) -> tuple[Sentiment, float, bool]:
        """Analyze text for sentiment.

        Returns:
            Tuple of (sentiment, confidence, requires_escalation)
        """
        text = text.lower()

        negative_score = sum(1 for r in self.negative_regex if r.search(text))
        positive_score = sum(1 for r in self.positive_regex if r.search(text))
        requires_escalation = any(r.search(text) for r in self.escalation_regex)

        # Calculate net sentiment
        net_score = positive_score - negative_score

        # Determine sentiment level
        if net_score <= -2:
            sentiment = Sentiment.VERY_NEGATIVE
        elif net_score == -1:
            sentiment = Sentiment.NEGATIVE
        elif net_score == 0:
            sentiment = Sentiment.NEUTRAL
        elif net_score == 1:
            sentiment = Sentiment.POSITIVE
        else:
            sentiment = Sentiment.VERY_POSITIVE

        # Confidence based on signal strength
        total_signals = positive_score + negative_score
        confidence = min(0.5 + (total_signals * 0.1), 0.95)

        return sentiment, confidence, requires_escalation

    def get_trend(self, history: list[Sentiment]) -> str:
        """Analyze sentiment trend over conversation."""
        if len(history) < 2:
            return "stable"

        recent = [s.value for s in history[-3:]]
        if len(recent) >= 2:
            if recent[-1] > recent[0]:
                return "improving"
            elif recent[-1] < recent[0]:
                return "declining"
        return "stable"


class CannedResponses:
    """Pre-written responses for common questions."""

    def __init__(self):
        self.responses = {
            "greeting": [
                "Hello! Welcome to TechStore support. How can I help you today?",
                "Hi there! Thanks for reaching out. What can I assist you with?",
                "Welcome! I'm here to help with any questions about our products.",
            ],
            "shipping": {
                "general": "We offer free standard shipping (5-7 business days) on orders over $50. Express shipping (2-3 days) is available for $12.99.",
                "tracking": "You can track your order using the tracking number in your confirmation email at our website's Order Status page.",
                "international": "We ship to 30+ countries. International shipping typically takes 10-14 business days.",
            },
            "returns": {
                "policy": "We offer a 30-day return policy for unopened items in original packaging. Opened electronics can be returned within 14 days if defective.",
                "process": "To start a return, go to My Orders, select the item, and click 'Return Item'. You'll receive a prepaid shipping label via email.",
                "refund": "Refunds are processed within 5-7 business days after we receive the returned item.",
            },
            "warranty": {
                "general": "All our products come with a 1-year manufacturer warranty. Extended warranties are available at checkout.",
                "claim": "To file a warranty claim, please have your order number ready and describe the issue. I can help you start the process.",
            },
            "products": {
                "monitors": 'We carry monitors from 22" to 34" including gaming, professional, and ultrawide options. What size or type are you looking for?',
                "keyboards": "We have mechanical, membrane, and wireless keyboards. Gaming keyboards feature RGB and macro keys. What's your preference?",
                "cables": "We stock HDMI, DisplayPort, USB-C, and ethernet cables in various lengths. What type and length do you need?",
            },
            "transfer": "I understand you'd like to speak with a human agent. Let me connect you with one of our support specialists.",
            "wait": "Please hold while I connect you with an available agent. Your estimated wait time is {wait_time} minutes.",
            "closing": [
                "Is there anything else I can help you with today?",
                "Do you have any other questions?",
                "Is there anything else you'd like to know?",
            ],
            "goodbye": [
                "Thank you for chatting with us! Have a great day!",
                "Thanks for reaching out! Take care!",
                "Glad I could help! Don't hesitate to reach out if you have more questions.",
            ],
        }

        self.keyword_mapping = {
            "ship": "shipping.general",
            "deliver": "shipping.general",
            "track": "shipping.tracking",
            "international": "shipping.international",
            "return": "returns.policy",
            "exchange": "returns.policy",
            "refund": "returns.refund",
            "warranty": "warranty.general",
            "broken": "warranty.claim",
            "defective": "warranty.claim",
            "monitor": "products.monitors",
            "screen": "products.monitors",
            "display": "products.monitors",
            "keyboard": "products.keyboards",
            "cable": "products.cables",
            "hdmi": "products.cables",
            "usb": "products.cables",
        }

    def get_response(self, category: str, subcategory: Optional[str] = None) -> str:
        """Get a canned response by category."""
        if subcategory:
            key = f"{category}.{subcategory}"
        else:
            key = category

        parts = key.split(".")
        response = self.responses

        for part in parts:
            if isinstance(response, dict) and part in response:
                response = response[part]
            else:
                return None

        if isinstance(response, list):
            return random.choice(response)
        return response

    def find_by_keywords(self, text: str) -> Optional[str]:
        """Find a canned response based on keywords in text."""
        text_lower = text.lower()

        for keyword, response_key in self.keyword_mapping.items():
            if keyword in text_lower:
                parts = response_key.split(".")
                return self.get_response(parts[0], parts[1] if len(parts) > 1 else None)

        return None


class LiveChatBot:
    """Live chat support bot with human handoff."""

    def __init__(self, store_name: str = "TechStore"):
        self.store_name = store_name
        self.sessions: dict[str, ChatSession] = {}
        self.customers: dict[str, Customer] = {}
        self.human_agents: dict[str, HumanAgent] = {}
        self.message_counter = 0

        self.sentiment_analyzer = SentimentAnalyzer()
        self.canned_responses = CannedResponses()

        # Configuration
        self.typing_delay = 0.05  # Seconds per character
        self.max_typing_delay = 3.0
        self.sentiment_escalation_threshold = -3  # Sum of recent sentiments
        self.auto_close_timeout = 300  # Seconds of inactivity

        # Callbacks
        self.on_message: Optional[Callable] = None
        self.on_typing: Optional[Callable] = None
        self.on_status_change: Optional[Callable] = None
        self.on_transfer: Optional[Callable] = None

        # Metrics
        self.metrics = {
            "total_chats": 0,
            "bot_resolved": 0,
            "human_resolved": 0,
            "escalated": 0,
            "abandoned": 0,
            "avg_response_time": 0.0,
            "avg_resolution_time": 0.0,
            "avg_csat": 0.0,
            "csat_responses": 0,
        }

        self._init_demo_agents()

    def _init_demo_agents(self):
        """Initialize demo human agents."""
        agents = [
            HumanAgent(
                id="agent_1",
                name="Sarah",
                skills=["general", "technical", "billing"],
                max_concurrent=3,
            ),
            HumanAgent(
                id="agent_2",
                name="Mike",
                skills=["general", "returns", "shipping"],
                max_concurrent=4,
            ),
            HumanAgent(
                id="agent_3",
                name="Lisa",
                skills=["technical", "warranty"],
                max_concurrent=2,
            ),
        ]
        for agent in agents:
            self.human_agents[agent.id] = agent

    def _generate_id(self, prefix: str = "msg") -> str:
        """Generate unique ID."""
        self.message_counter += 1
        return f"{prefix}_{int(time.time())}_{self.message_counter}"

    async def start_chat(self, customer: Customer) -> ChatSession:
        """Start a new chat session."""
        session_id = self._generate_id("chat")

        session = ChatSession(
            id=session_id,
            customer=customer,
            status=ChatStatus.ACTIVE,
            created_at=datetime.now(),
            current_agent="bot",
            agent_type=AgentType.BOT,
        )

        self.sessions[session_id] = session
        self.customers[customer.id] = customer
        self.metrics["total_chats"] += 1

        # Send greeting
        greeting = self.canned_responses.get_response("greeting")
        if customer.is_vip:
            greeting = f"Welcome back, {customer.name}! As a VIP customer, you're our priority. {greeting}"

        await self._send_bot_message(session, greeting)

        if self.on_status_change:
            await self.on_status_change(session, ChatStatus.ACTIVE)

        return session

    async def _send_bot_message(
        self, session: ChatSession, content: str, show_typing: bool = True
    ):
        """Send a message from the bot."""
        if show_typing:
            await self._show_typing(session, content)

        message = ChatMessage(
            id=self._generate_id(),
            content=content,
            sender="bot",
            sender_type=AgentType.BOT,
            timestamp=datetime.now(),
        )

        session.messages.append(message)

        if self.on_message:
            await self.on_message(session, message)

        return message

    async def _show_typing(self, session: ChatSession, content: str):
        """Show typing indicator based on message length."""
        typing_time = min(len(content) * self.typing_delay, self.max_typing_delay)

        typing_msg = ChatMessage(
            id=self._generate_id("typing"),
            content="",
            sender="bot",
            sender_type=AgentType.BOT,
            timestamp=datetime.now(),
            message_type=MessageType.TYPING,
        )

        if self.on_typing:
            await self.on_typing(session, True)

        await asyncio.sleep(typing_time)

        if self.on_typing:
            await self.on_typing(session, False)

    async def handle_customer_message(
        self, session_id: str, content: str
    ) -> list[ChatMessage]:
        """Handle an incoming customer message."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status not in [ChatStatus.ACTIVE, ChatStatus.TRANSFERRED]:
            raise ValueError(f"Session {session_id} is not active")

        # Record customer message
        customer_msg = ChatMessage(
            id=self._generate_id(),
            content=content,
            sender=session.customer.name,
            sender_type=AgentType.HUMAN,
            timestamp=datetime.now(),
        )
        session.messages.append(customer_msg)

        # Analyze sentiment
        sentiment, confidence, needs_escalation = self.sentiment_analyzer.analyze(
            content
        )
        session.sentiment_history.append(sentiment)

        responses = []

        # Check for escalation triggers
        if needs_escalation or self._should_escalate(session):
            await self._escalate_to_human(
                session,
                "Customer requested" if needs_escalation else "Negative sentiment",
            )
            return responses

        # Handle message if bot is responding
        if session.agent_type == AgentType.BOT:
            # Try canned response first
            canned = self.canned_responses.find_by_keywords(content)

            if canned:
                msg = await self._send_bot_message(session, canned)
                responses.append(msg)
            else:
                # Generate contextual response
                response = await self._generate_response(session, content)
                msg = await self._send_bot_message(session, response)
                responses.append(msg)

            # Add closing question if appropriate
            if len(session.messages) > 4 and random.random() < 0.3:
                closing = self.canned_responses.get_response("closing")
                msg = await self._send_bot_message(session, closing)
                responses.append(msg)

        return responses

    def _should_escalate(self, session: ChatSession) -> bool:
        """Check if session should be escalated based on sentiment."""
        if len(session.sentiment_history) < 2:
            return False

        recent = session.sentiment_history[-3:]
        sentiment_sum = sum(s.value for s in recent)

        return sentiment_sum <= self.sentiment_escalation_threshold

    async def _escalate_to_human(self, session: ChatSession, reason: str):
        """Escalate chat to a human agent."""
        session.escalation_reason = reason
        self.metrics["escalated"] += 1

        # Find available agent
        available_agent = None
        for agent in self.human_agents.values():
            if agent.can_accept_chat:
                available_agent = agent
                break

        if available_agent:
            session.current_agent = available_agent.id
            session.agent_type = AgentType.HUMAN
            session.status = ChatStatus.TRANSFERRED
            available_agent.current_chats += 1

            transfer_msg = self.canned_responses.get_response("transfer")
            await self._send_bot_message(session, transfer_msg)

            # System message about transfer
            system_msg = ChatMessage(
                id=self._generate_id(),
                content=f"Chat transferred to {available_agent.name}",
                sender="system",
                sender_type=AgentType.BOT,
                timestamp=datetime.now(),
                message_type=MessageType.TRANSFER,
            )
            session.messages.append(system_msg)

            if self.on_transfer:
                await self.on_transfer(session, available_agent)
        else:
            # No agents available - put in queue
            wait_time = self._estimate_wait_time()
            wait_msg = self.canned_responses.get_response("wait").format(
                wait_time=wait_time
            )
            await self._send_bot_message(session, wait_msg)
            session.status = ChatStatus.WAITING

        if self.on_status_change:
            await self.on_status_change(session, session.status)

    def _estimate_wait_time(self) -> int:
        """Estimate wait time for human agent."""
        busy_agents = sum(
            1 for a in self.human_agents.values() if not a.can_accept_chat
        )
        waiting_chats = sum(
            1 for s in self.sessions.values() if s.status == ChatStatus.WAITING
        )

        avg_time = sum(a.avg_resolution_time for a in self.human_agents.values()) / len(
            self.human_agents
        )
        estimated_seconds = (waiting_chats + 1) * (
            avg_time / max(len(self.human_agents) - busy_agents, 1)
        )

        return max(1, int(estimated_seconds / 60))

    async def _generate_response(self, session: ChatSession, message: str) -> str:
        """Generate a contextual response."""
        message_lower = message.lower()

        # Check for common intents
        if any(word in message_lower for word in ["hi", "hello", "hey"]):
            return "Hello! How can I help you today?"

        if any(word in message_lower for word in ["thank", "thanks"]):
            return "You're welcome! Is there anything else I can help with?"

        if any(word in message_lower for word in ["bye", "goodbye", "done"]):
            return await self._initiate_close(session)

        if "order" in message_lower and any(
            w in message_lower for w in ["status", "where", "when"]
        ):
            return "I can help you track your order! Please provide your order number (it starts with TS-) or the email used for the purchase."

        if "price" in message_lower or "cost" in message_lower:
            return "I'd be happy to help with pricing! Which product are you interested in? We have monitors, keyboards, cables, and more."

        if "recommend" in message_lower or "suggest" in message_lower:
            return "I can help you find the right product! What will you be using it for? Gaming, work, or general use?"

        # Default fallback
        return "I want to make sure I help you correctly. Could you tell me more about what you're looking for? I can assist with orders, products, shipping, returns, and more."

    async def _initiate_close(self, session: ChatSession) -> str:
        """Start the chat closing process."""
        # Return goodbye and prepare for CSAT
        goodbye = self.canned_responses.get_response("goodbye")

        # Schedule CSAT survey
        asyncio.create_task(self._send_csat_survey(session))

        return goodbye

    async def _send_csat_survey(self, session: ChatSession):
        """Send CSAT survey after delay."""
        await asyncio.sleep(2)

        survey_msg = ChatMessage(
            id=self._generate_id("csat"),
            content="How would you rate your support experience today? (1-5 stars)",
            sender="system",
            sender_type=AgentType.BOT,
            timestamp=datetime.now(),
            message_type=MessageType.CSAT,
            metadata={"survey_type": "csat", "options": [1, 2, 3, 4, 5]},
        )

        session.messages.append(survey_msg)

        if self.on_message:
            await self.on_message(session, survey_msg)

    async def submit_csat(self, session_id: str, score: int):
        """Submit CSAT score for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return

        session.csat_score = score
        session.status = ChatStatus.RESOLVED
        session.resolved_at = datetime.now()

        # Update metrics
        self.metrics["csat_responses"] += 1
        current_avg = self.metrics["avg_csat"]
        self.metrics["avg_csat"] = (
            current_avg * (self.metrics["csat_responses"] - 1) + score
        ) / self.metrics["csat_responses"]

        if session.agent_type == AgentType.BOT:
            self.metrics["bot_resolved"] += 1
        else:
            self.metrics["human_resolved"] += 1
            # Free up human agent
            agent = self.human_agents.get(session.current_agent)
            if agent:
                agent.current_chats -= 1

        # Update resolution time
        self._update_resolution_time(session)

        if self.on_status_change:
            await self.on_status_change(session, ChatStatus.RESOLVED)

    def _update_resolution_time(self, session: ChatSession):
        """Update average resolution time metric."""
        resolved = self.metrics["bot_resolved"] + self.metrics["human_resolved"]
        if resolved > 0:
            current_avg = self.metrics["avg_resolution_time"]
            self.metrics["avg_resolution_time"] = (
                current_avg * (resolved - 1) + session.duration_seconds
            ) / resolved

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID."""
        return self.sessions.get(session_id)

    def get_chat_history(self, session_id: str) -> list[dict]:
        """Get formatted chat history."""
        session = self.sessions.get(session_id)
        if not session:
            return []

        return [
            msg.to_dict()
            for msg in session.messages
            if msg.message_type == MessageType.TEXT
        ]

    def get_metrics(self) -> dict:
        """Get current metrics."""
        active_chats = sum(
            1 for s in self.sessions.values() if s.status == ChatStatus.ACTIVE
        )
        waiting_chats = sum(
            1 for s in self.sessions.values() if s.status == ChatStatus.WAITING
        )

        return {
            **self.metrics,
            "active_chats": active_chats,
            "waiting_chats": waiting_chats,
            "available_agents": sum(
                1 for a in self.human_agents.values() if a.can_accept_chat
            ),
            "bot_resolution_rate": (
                self.metrics["bot_resolved"] / max(self.metrics["total_chats"], 1) * 100
            ),
        }

    def mark_message_read(self, session_id: str, message_id: str):
        """Mark a message as read."""
        session = self.sessions.get(session_id)
        if session:
            for msg in session.messages:
                if msg.id == message_id:
                    msg.read = True
                    break


class ChatUI:
    """Console-based chat UI for demo."""

    def __init__(self, bot: LiveChatBot):
        self.bot = bot
        self.current_session: Optional[ChatSession] = None

        # Wire up callbacks
        self.bot.on_message = self._on_message
        self.bot.on_typing = self._on_typing
        self.bot.on_status_change = self._on_status_change
        self.bot.on_transfer = self._on_transfer

    async def _on_message(self, session: ChatSession, message: ChatMessage):
        """Handle new message."""
        if message.sender_type == AgentType.BOT:
            sender_display = f"🤖 {self.bot.store_name}"
        else:
            sender_display = f"👤 {message.sender}"

        if message.message_type == MessageType.SYSTEM:
            print(f"\n  ℹ️  {message.content}")
        elif message.message_type == MessageType.CSAT:
            print(f"\n  📊 {message.content}")
        else:
            print(f"\n  {sender_display}: {message.content}")

    async def _on_typing(self, session: ChatSession, is_typing: bool):
        """Handle typing indicator."""
        if is_typing:
            print("  💬 Bot is typing...", end="\r")

    async def _on_status_change(self, session: ChatSession, status: ChatStatus):
        """Handle status change."""
        status_icons = {
            ChatStatus.ACTIVE: "🟢",
            ChatStatus.WAITING: "🟡",
            ChatStatus.TRANSFERRED: "🔄",
            ChatStatus.RESOLVED: "✅",
            ChatStatus.ABANDONED: "⚪",
        }
        print(f"\n  {status_icons.get(status, '•')} Chat status: {status.value}")

    async def _on_transfer(self, session: ChatSession, agent: HumanAgent):
        """Handle transfer to human."""
        print(f"\n  👋 {agent.name} has joined the chat")

    def print_header(self):
        """Print chat header."""
        print("\n" + "=" * 60)
        print(f"  🛒 {self.bot.store_name} Live Chat Support")
        print("=" * 60)
        print("  Type your message and press Enter")
        print("  Commands: /status /history /metrics /quit")
        print("-" * 60)

    async def run(self, customer: Customer):
        """Run the chat interface."""
        self.print_header()

        # Start chat session
        self.current_session = await self.bot.start_chat(customer)

        while True:
            try:
                # Get user input
                user_input = input("\n  You: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    if await self._handle_command(user_input):
                        break
                    continue

                # Check for CSAT response
                if (
                    self.current_session.messages
                    and self.current_session.messages[-1].message_type
                    == MessageType.CSAT
                ):
                    try:
                        score = int(user_input)
                        if 1 <= score <= 5:
                            await self.bot.submit_csat(self.current_session.id, score)
                            print(
                                f"\n  ⭐ Thank you for your feedback! ({score}/5 stars)"
                            )
                            print("  Chat session ended.")
                            break
                    except ValueError:
                        pass

                # Handle regular message
                await self.bot.handle_customer_message(
                    self.current_session.id, user_input
                )

            except KeyboardInterrupt:
                print("\n\n  Chat ended by user.")
                break
            except Exception as e:
                print(f"\n  ❌ Error: {e}")

    async def _handle_command(self, command: str) -> bool:
        """Handle slash commands. Returns True to exit."""
        cmd = command.lower().strip()

        if cmd == "/quit":
            print("\n  Chat ended.")
            return True

        if cmd == "/status":
            session = self.current_session
            sentiment = session.current_sentiment
            sentiment_icons = {
                Sentiment.VERY_NEGATIVE: "😠",
                Sentiment.NEGATIVE: "😕",
                Sentiment.NEUTRAL: "😐",
                Sentiment.POSITIVE: "🙂",
                Sentiment.VERY_POSITIVE: "😊",
            }
            print(f"\n  Session: {session.id}")
            print(f"  Status: {session.status.value}")
            print(f"  Duration: {int(session.duration_seconds)}s")
            print(f"  Messages: {session.message_count}")
            print(
                f"  Sentiment: {sentiment_icons.get(sentiment, '•')} {sentiment.name}"
            )
            return False

        if cmd == "/history":
            print("\n  --- Chat History ---")
            for msg in self.bot.get_chat_history(self.current_session.id):
                print(
                    f"  [{msg['timestamp'][:19]}] {msg['sender']}: {msg['content'][:50]}..."
                )
            return False

        if cmd == "/metrics":
            metrics = self.bot.get_metrics()
            print("\n  --- Support Metrics ---")
            print(f"  Total Chats: {metrics['total_chats']}")
            print(f"  Bot Resolved: {metrics['bot_resolved']}")
            print(f"  Human Resolved: {metrics['human_resolved']}")
            print(f"  Escalated: {metrics['escalated']}")
            print(f"  Avg Resolution: {metrics['avg_resolution_time']:.1f}s")
            print(f"  Avg CSAT: {metrics['avg_csat']:.2f}/5")
            print(f"  Bot Resolution Rate: {metrics['bot_resolution_rate']:.1f}%")
            return False

        print(f"  Unknown command: {command}")
        return False


async def demo():
    """Run the live chat demo."""
    print("\n" + "=" * 60)
    print("  Live Chat Support Demo")
    print("  Electronics Store Customer Service")
    print("=" * 60)

    # Create bot
    bot = LiveChatBot(store_name="TechStore Electronics")

    # Create demo customer
    customer = Customer(
        id="cust_demo_1",
        name="Alex",
        email="alex@example.com",
        tier="standard",
        previous_chats=2,
        lifetime_value=450.00,
    )

    # Run chat UI
    ui = ChatUI(bot)
    await ui.run(customer)

    # Show final metrics
    print("\n" + "=" * 60)
    print("  Final Session Metrics")
    print("=" * 60)
    metrics = bot.get_metrics()
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")


async def automated_demo():
    """Run automated demo showing various scenarios."""
    print("\n" + "=" * 60)
    print("  Live Chat Support - Automated Demo")
    print("=" * 60)

    bot = LiveChatBot(store_name="TechStore Electronics")

    # Track messages for display
    messages = []

    async def track_message(session, msg):
        messages.append((session.id, msg))
        sender = "🤖 Bot" if msg.sender_type == AgentType.BOT else "👤 Customer"
        if msg.message_type == MessageType.TEXT:
            print(f"  {sender}: {msg.content}")

    bot.on_message = track_message

    # Scenario 1: Simple product inquiry
    print("\n--- Scenario 1: Product Inquiry ---")
    customer1 = Customer(id="c1", name="Jordan", email="jordan@test.com")
    session1 = await bot.start_chat(customer1)
    await bot.handle_customer_message(
        session1.id, "Hi, I'm looking for a gaming monitor"
    )
    await bot.handle_customer_message(
        session1.id, "Thanks! What about mechanical keyboards?"
    )
    await bot.handle_customer_message(session1.id, "Perfect, thanks for the help!")

    # Scenario 2: Shipping inquiry
    print("\n--- Scenario 2: Shipping Question ---")
    customer2 = Customer(id="c2", name="Sam", email="sam@test.com")
    session2 = await bot.start_chat(customer2)
    await bot.handle_customer_message(session2.id, "How much does shipping cost?")
    await bot.handle_customer_message(session2.id, "Do you ship internationally?")

    # Scenario 3: Escalation to human
    print("\n--- Scenario 3: Escalation Request ---")
    customer3 = Customer(id="c3", name="Casey", email="casey@test.com")
    session3 = await bot.start_chat(customer3)
    await bot.handle_customer_message(
        session3.id, "I want to speak to a real person please"
    )

    # Scenario 4: Negative sentiment escalation
    print("\n--- Scenario 4: Negative Sentiment ---")
    customer4 = Customer(id="c4", name="Morgan", email="morgan@test.com")
    session4 = await bot.start_chat(customer4)
    await bot.handle_customer_message(
        session4.id, "This is ridiculous! My order is late!"
    )
    await bot.handle_customer_message(
        session4.id, "I've been waiting two weeks! This is unacceptable!"
    )

    # Final metrics
    print("\n" + "=" * 60)
    print("  Demo Metrics Summary")
    print("=" * 60)
    metrics = bot.get_metrics()
    print(f"  Total Chats: {metrics['total_chats']}")
    print(f"  Escalated: {metrics['escalated']}")
    print(f"  Active: {metrics['active_chats']}")
    print(f"  Bot Resolution Rate: {metrics['bot_resolution_rate']:.1f}%")


if __name__ == "__main__":
    import sys

    if "--auto" in sys.argv:
        asyncio.run(automated_demo())
    else:
        asyncio.run(demo())
