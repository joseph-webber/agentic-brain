# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Agentic Brain Chat Module
=========================

Production-ready chatbot with:
- Session persistence (survives restarts)
- Neo4j memory integration
- Conversation threading
- Multi-user support with data isolation
- Simple, clean API

Quick Start:
    from agentic_brain.chat import Chatbot
    
    bot = Chatbot("assistant")
    response = bot.chat("Hello!")
    print(response)

With Memory:
    from agentic_brain import Neo4jMemory
    from agentic_brain.chat import Chatbot
    
    memory = Neo4jMemory()
    bot = Chatbot("support", memory=memory)
    
    # Bot remembers across sessions
    bot.chat("My order number is 12345")
    # Later...
    bot.chat("What was my order number?")  # Knows it's 12345

Multi-User (Business):
    bot = Chatbot("support", memory=memory)
    
    # Each customer isolated
    bot.chat("I need help", user_id="customer_1")
    bot.chat("I need help", user_id="customer_2")  # Different context
"""

from .chatbot import Chatbot, ChatMessage, ChatSession
from .session import SessionManager, Session
from .config import ChatConfig

__all__ = [
    "Chatbot",
    "ChatMessage", 
    "ChatSession",
    "SessionManager",
    "Session",
    "ChatConfig",
]
