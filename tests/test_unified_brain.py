# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Tests for Unified Brain - multi-LLM coordination."""

from unittest.mock import MagicMock, patch

import pytest


class TestUnifiedBrain:
    """Test unified brain coordination."""

    @pytest.fixture
    def brain_with_mocks(self):
        with (
            patch("agentic_brain.unified_brain.RedisRouterCache") as redis_cls,
            patch("agentic_brain.unified_brain.RedisInterBotComm") as interbot_cls,
            patch("agentic_brain.unified_brain.LLMRouter") as router_cls,
        ):
            redis_instance = MagicMock()
            redis_cls.return_value = redis_instance
            interbot_cls.return_value = MagicMock()
            router_cls.return_value = MagicMock()

            from agentic_brain.unified_brain import UnifiedBrain

            brain = UnifiedBrain()
            yield brain, redis_instance

    def test_brain_initialization_registers_bots(self, brain_with_mocks):
        """Test brain initializes with default bots and registers them."""
        brain, redis_instance = brain_with_mocks
        assert len(brain.bots) >= 5
        assert redis_instance.set_bot_status.call_count == len(brain.bots)

    def test_route_coding_task_prefers_free(self, brain_with_mocks):
        """Test coding tasks route to free coder bot by default."""
        brain, _ = brain_with_mocks
        bot = brain.route_task("implement a new feature")
        assert bot == "ollama-quality"

    def test_route_review_task_prefers_free(self, brain_with_mocks):
        """Test review tasks route to free reviewer bot by default."""
        brain, _ = brain_with_mocks
        bot = brain.route_task("review this code")
        assert bot == "gemini-pro"

    def test_route_fast_task(self, brain_with_mocks):
        """Test fast tasks route to fast bot."""
        brain, _ = brain_with_mocks
        bot = brain.route_task("quick question")
        assert bot == "ollama-fast"

    def test_prefer_paid_when_requested(self, brain_with_mocks):
        """Test paid models can be preferred when requested."""
        brain, _ = brain_with_mocks
        bot = brain.route_task("review this code", prefer_free=False)
        assert bot == "claude-sonnet"

    def test_broadcast_task(self, brain_with_mocks):
        """Test broadcasting to all bots."""
        brain, redis_instance = brain_with_mocks
        brain.broadcast_task("collaborative task", wait_for_consensus=True)
        redis_instance.publish_task.assert_called_once()
        args, _ = redis_instance.publish_task.call_args
        assert args[0] == "all"
        assert args[1]["content"] == "collaborative task"
        assert args[1]["consensus_required"] is True

    def test_brain_status(self, brain_with_mocks):
        """Test brain status report."""
        brain, redis_instance = brain_with_mocks
        redis_instance.get_all_bots.return_value = {
            "bot-1": {"status": "available", "provider": "ollama", "roles": ["coder"]}
        }
        status = brain.get_brain_status()
        assert status["total_bots"] == 1
        assert "providers" in status
        assert "ollama" in status["providers"]
