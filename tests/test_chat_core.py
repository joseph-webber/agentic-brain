# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.chat.chatbot import Chatbot, ChatConfig
from agentic_brain.chat.session import Session


# Mock LLMRouter to avoid API calls
@pytest.fixture
def mock_llm_router():
    router = AsyncMock()
    router.chat.return_value = "Mock response"
    return router


@pytest.fixture
def chatbot(mock_llm_router):
    """Chatbot wired to a mock LLM router (no real API calls).

    We pass the mock in via the Chatbot ``llm`` parameter so all chat
    traffic is handled by ``mock_llm_router.chat``.
    """
    config = ChatConfig(persist_sessions=False)
    bot = Chatbot("test_bot", config=config, llm=mock_llm_router)
    return bot


@pytest.mark.asyncio
async def test_basic_chat_loop(chatbot, mock_llm_router):
    """Test that basic chat sends message and gets response."""
    response = await chatbot.chat_async("Hello")
    assert response == "Mock response"

    # Verify LLM was called with correct history
    mock_llm_router.chat.assert_called_once()
    call_args = mock_llm_router.chat.call_args
    messages = call_args[1]["messages"]
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Hello"


@pytest.mark.asyncio
async def test_model_switching(chatbot):
    """Test slash commands for model switching."""
    # Initial state
    assert chatbot._current_model == "L2"

    # Switch to Claude
    response = await chatbot.chat_async("/CL")
    assert "Switched to CL" in response
    assert chatbot._current_model == "CL"
    assert "claude" in chatbot.config.model.lower()

    # Switch to OpenAI
    response = await chatbot.chat_async("/OP")
    assert "Switched to OP" in response
    assert chatbot._current_model == "OP"
    assert "gpt" in chatbot.config.model.lower()


@pytest.mark.asyncio
async def test_slash_commands(chatbot):
    """Test other slash commands."""
    # Help command
    response = await chatbot.chat_async("/help")
    assert "AVAILABLE MODELS" in response

    # Current command
    response = await chatbot.chat_async("/current")
    assert "Current Model" in response

    # Fallback toggle
    response = await chatbot.chat_async("/fallback")
    assert "Auto-fallback" in response


@pytest.mark.asyncio
async def test_history_persistence(chatbot):
    """Test that history is maintained in session."""
    session_id = "test_session"

    # First turn
    await chatbot.chat_async("Hello", session_id=session_id)
    session = chatbot.get_session(session_id=session_id)
    assert len(session.history) == 2  # User + Assistant

    # Second turn
    await chatbot.chat_async("How are you?", session_id=session_id)
    session = chatbot.get_session(session_id=session_id)
    assert len(session.history) == 4

    # Check content
    assert session.history[0].content == "Hello"
    assert session.history[2].content == "How are you?"


@pytest.mark.asyncio
async def test_error_handling(chatbot, mock_llm_router):
    """Test graceful error handling."""
    # Simulate LLM failure
    mock_llm_router.chat.side_effect = Exception("API Error")

    response = await chatbot.chat_async("Trigger error")
    assert "I encountered an error" in response
    assert "API Error" in response

    # Check stats
    assert chatbot.stats["errors"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skip_ci
async def test_streaming_support(chatbot, mock_llm_router):
    """Test streaming capability (EXPECTED TO FAIL currently)."""

    # Setup mock for streaming
    async def mock_stream():
        yield "Part 1"
        yield "Part 2"

    mock_llm_router.chat_stream = MagicMock(return_value=mock_stream())

    # This method doesn't exist yet, so we expect this test to fail or needs implementation
    # We'll check if chat_stream exists or if chat_async handles generators

    if not hasattr(chatbot, "chat_stream"):
        pytest.fail("chat_stream method missing on Chatbot")

    # If implemented, it should look like this:
    chunks = []
    async for chunk in chatbot.chat_stream("Hello"):
        chunks.append(chunk)

    assert "".join(chunks) == "Part 1Part 2"
