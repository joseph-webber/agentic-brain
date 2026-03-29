# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from dataclasses import asdict
from typing import Any, Optional

from agentic_brain.db import BrainRedis
from agentic_brain.rag import RAGPipeline

from .intents import CommerceContext, CommerceUserType
from .woo_chatbot import WooCommerceChatbot


class ChatbotIntegrator:
    """
    Integration layer for WooCommerce Chatbot with Brain core systems.

    Provides:
    - Redis-backed session management
    - RAG-based product search
    - Event bus connectivity
    """

    def __init__(self, chatbot: WooCommerceChatbot):
        self.chatbot = chatbot
        # Initialize RAG and Redis
        # Note: These assume default configs or env vars
        self.rag = RAGPipeline()
        self.redis = BrainRedis()

    async def process_message(
        self, session_id: str, message: str, user_type: str = "customer"
    ) -> str:
        """
        Process a message with full brain integration.

        Args:
            session_id: Unique session identifier
            message: User message
            user_type: 'customer', 'guest', or 'admin'

        Returns:
            Chatbot response string
        """
        # 1. Retrieve session
        session_data = await self.redis.get_session(session_id) or {}

        # 2. Reconstruct context from session or defaults
        context_data = session_data.get("context", {})
        # Filter context_data to match CommerceContext fields to avoid errors
        # (Simplified for now, assuming matching schema)
        try:
            context = CommerceContext(
                user_type=CommerceUserType(user_type), **context_data
            )
        except TypeError:
            # Fallback if schema changed
            context = CommerceContext(user_type=CommerceUserType(user_type))

        # 3. RAG Search (Augmentation)
        # If we detect a search intent, we could query RAG here
        # For now, we leave it to the chatbot internals or future expansion

        # 4. Handle message via core chatbot logic
        response = await self.chatbot.handle_message(
            message, user_type=CommerceUserType(user_type), context=context
        )

        # 5. Save updated session state
        session_data["context"] = asdict(context)
        session_data["last_updated"] = "now"  # In real app use timestamp
        await self.redis.set_session(session_id, session_data)

        return response
