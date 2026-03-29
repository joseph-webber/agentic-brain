# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tests for agentic-brain agent module.
"""

from unittest.mock import MagicMock, patch

from agentic_brain.agent import Agent, AgentConfig
from agentic_brain.memory import DataScope, InMemoryStore


class TestAgentConfig:
    """Test AgentConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = AgentConfig()

        assert config.name == "agent"
        assert config.memory_scope == DataScope.PRIVATE
        assert config.audio_enabled is True
        assert config.voice == "Karen"

    def test_custom_config(self):
        """Test custom configuration."""
        config = AgentConfig(
            name="helper",
            memory_scope=DataScope.CUSTOMER,
            customer_id="acme",
            audio_enabled=False,
        )

        assert config.name == "helper"
        assert config.memory_scope == DataScope.CUSTOMER
        assert config.customer_id == "acme"


class TestAgent:
    """Test Agent class."""

    def test_agent_creation(self):
        """Test creating an agent."""
        agent = Agent(name="test-agent", audio_enabled=False)

        assert agent.config.name == "test-agent"
        assert isinstance(agent.memory, InMemoryStore)
        assert repr(agent) == "Agent(name='test-agent', scope=private)"

    def test_agent_with_system_prompt(self):
        """Test agent with custom system prompt."""
        agent = Agent(
            name="custom",
            system_prompt="You are a helpful assistant.",
            audio_enabled=False,
        )

        assert agent.system_prompt == "You are a helpful assistant."

    def test_default_system_prompt(self):
        """Test default system prompt."""
        agent = Agent(name="default", audio_enabled=False)

        assert "helpful AI assistant" in agent.system_prompt

    def test_agent_context_manager(self):
        """Test agent as context manager."""
        with Agent(name="ctx", audio_enabled=False) as agent:
            assert agent.config.name == "ctx"
        # Should not raise


class TestAgentMemory:
    """Test agent memory operations."""

    def test_remember(self):
        """Test storing memories."""
        agent = Agent(name="mem-test", audio_enabled=False)

        mem = agent.remember("Important fact")

        assert mem.content == "Important fact"
        assert mem.scope == DataScope.PRIVATE

    def test_remember_with_scope(self):
        """Test remembering with specific scope."""
        agent = Agent(name="scope-test", audio_enabled=False)

        mem = agent.remember("Public info", scope=DataScope.PUBLIC)

        assert mem.scope == DataScope.PUBLIC

    def test_recall(self):
        """Test searching memories."""
        agent = Agent(name="recall-test", audio_enabled=False)

        agent.remember("Python is great")
        agent.remember("Java is also good")

        results = agent.recall("Python")

        assert len(results) == 1
        assert "Python" in results[0].content

    def test_recall_empty(self):
        """Test recall with no matches."""
        agent = Agent(name="empty-test", audio_enabled=False)

        results = agent.recall("nonexistent")

        assert len(results) == 0


class TestAgentChat:
    """Test agent chat functionality."""

    @patch("agentic_brain.router.LLMRouter.chat")
    def test_chat_basic(self, mock_chat):
        """Test basic chat."""
        mock_chat.return_value = MagicMock(content="Hello there!")

        agent = Agent(name="chat-test", audio_enabled=False)
        response = agent.chat("Hello")

        assert response == "Hello there!"
        mock_chat.assert_called_once()

    @patch("agentic_brain.router.LLMRouter.chat")
    def test_chat_stores_history(self, mock_chat):
        """Test chat stores conversation history."""
        mock_chat.return_value = MagicMock(content="Response")

        agent = Agent(name="history-test", audio_enabled=False)
        agent.chat("Message 1")
        agent.chat("Message 2")

        history = agent.history

        assert len(history) == 4  # 2 user + 2 assistant
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Message 1"
        assert history[1]["role"] == "assistant"

    @patch("agentic_brain.router.LLMRouter.chat")
    def test_chat_remembers(self, mock_chat):
        """Test chat stores in memory when remember=True."""
        mock_chat.return_value = MagicMock(content="Response")

        agent = Agent(name="remember-test", audio_enabled=False)
        agent.chat("Remember this", remember=True)

        # Should have 2 memories: user message + assistant response
        results = agent.recall("Remember")
        assert len(results) >= 1

    @patch("agentic_brain.router.LLMRouter.chat")
    def test_chat_no_remember(self, mock_chat):
        """Test chat doesn't store when remember=False."""
        mock_chat.return_value = MagicMock(content="Response")

        agent = Agent(name="no-remember-test", audio_enabled=False)
        agent.chat("Don't remember", remember=False)

        results = agent.recall("Don't remember")
        assert len(results) == 0

    @patch("agentic_brain.router.LLMRouter.chat")
    def test_chat_error_handling(self, mock_chat):
        """Test chat handles LLM errors gracefully."""
        mock_chat.side_effect = Exception("LLM error")

        agent = Agent(name="error-test", audio_enabled=False)
        response = agent.chat("Test")

        assert "trouble responding" in response

    def test_clear_history(self):
        """Test clearing conversation history."""
        agent = Agent(name="clear-test", audio_enabled=False)
        agent._history = [{"role": "user", "content": "test"}]

        agent.clear_history()

        assert len(agent.history) == 0


class TestAgentAudio:
    """Test agent audio functionality."""

    @patch("agentic_brain.audio.Audio.speak")
    @patch("agentic_brain.router.LLMRouter.chat")
    def test_chat_with_speak(self, mock_chat, mock_speak):
        """Test chat with speak=True."""
        mock_chat.return_value = MagicMock(content="Spoken response")
        mock_speak.return_value = True

        agent = Agent(name="speak-test", audio_enabled=True)
        agent.chat("Hello", speak=True)

        mock_speak.assert_called_once_with("Spoken response")

    @patch("agentic_brain.audio.Audio.speak")
    def test_speak_method(self, mock_speak):
        """Test agent speak method."""
        mock_speak.return_value = True

        agent = Agent(name="speak-method-test", audio_enabled=True)
        agent.speak("Test message")

        mock_speak.assert_called_once_with("Test message")

    @patch("agentic_brain.audio.Audio.announce")
    def test_announce_method(self, mock_announce):
        """Test agent announce method."""
        mock_announce.return_value = True

        agent = Agent(name="announce-test", audio_enabled=True)
        agent.announce("Important!", sound="success")

        mock_announce.assert_called_once_with("Important!", sound="success")

    def test_speak_disabled(self):
        """Test speak when audio disabled."""
        agent = Agent(name="disabled-test", audio_enabled=False)

        result = agent.speak("Test")

        assert result is False


class TestAgentCustomerScope:
    """Test agent with customer scope."""

    def test_customer_scope_agent(self):
        """Test agent configured for customer scope."""
        agent = Agent(
            name="customer-agent",
            memory_scope=DataScope.CUSTOMER,
            customer_id="acme-corp",
            audio_enabled=False,
        )

        assert agent.config.memory_scope == DataScope.CUSTOMER
        assert agent.config.customer_id == "acme-corp"

    def test_customer_memory_isolation(self):
        """Test customer memories are isolated."""
        # Agent for customer A
        agent_a = Agent(
            name="agent-a",
            memory_scope=DataScope.CUSTOMER,
            customer_id="customer-a",
            audio_enabled=False,
        )

        # Agent for customer B
        agent_b = Agent(
            name="agent-b",
            memory_scope=DataScope.CUSTOMER,
            customer_id="customer-b",
            audio_enabled=False,
        )

        agent_a.remember("Customer A data")
        agent_b.remember("Customer B data")

        # Each should only see their own data
        results_a = agent_a.recall("data")
        results_b = agent_b.recall("data")

        assert len(results_a) == 1
        assert "Customer A" in results_a[0].content

        assert len(results_b) == 1
        assert "Customer B" in results_b[0].content
