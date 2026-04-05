"""
Tests for Session Memory Consolidation
=======================================

Verifies that unified.py successfully consolidates functionality from:
- ultimate_memory_hooks.py (SessionHooks)
- session_stitcher.py (SessionStitcher)

Also tests deprecation wrappers for backwards compatibility.

Created: 2026-04-01
"""

import json
import os
import shutil
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path

import pytest

# Import unified implementations
from agentic_brain.memory import (
    HookEvent,
    MemoryEntry,
    MemoryType,
    SessionHooks,
    SessionLink,
    SessionStitcher,
    UnifiedMemory,
    find_related_sessions,
    get_session_context,
    get_session_hooks,
    get_session_stitcher,
    get_unified_memory,
    on_assistant_response,
    on_session_start,
    on_tool_use,
    on_user_prompt,
    stitch_message,
)


class TestUnifiedMemoryBasics:
    """Test core UnifiedMemory functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir) / "test.db"
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def memory(self, temp_db):
        """Create UnifiedMemory instance."""
        return UnifiedMemory(db_path=str(temp_db))

    def test_memory_creation(self, memory):
        """Test memory instance creation."""
        assert memory is not None
        assert memory._sqlite is not None

    def test_store_and_search(self, memory):
        """Test basic store and search."""
        # Store a memory
        entry = memory.store(
            content="Python is great for ML",
            memory_type=MemoryType.LONG_TERM,
            importance=0.8,
        )
        assert entry is not None
        assert entry.content == "Python is great for ML"
        assert entry.memory_type == MemoryType.LONG_TERM

        # Search for it
        results = memory.search("Python programming")
        assert len(results) > 0
        assert any("Python" in r.content for r in results)

    def test_session_memory(self, memory):
        """Test session-specific memory."""
        session_id = "test-session-001"

        # Add message
        memory.add_message(session_id, "user", "Hello!")
        memory.add_message(session_id, "assistant", "Hi there!")

        # Get context
        context = memory.get_session_context(session_id)
        assert context is not None
        assert len(context) > 0

    def test_memory_stats(self, memory):
        """Test stats method."""
        memory.store("Test 1", MemoryType.SESSION)
        memory.store("Test 2", MemoryType.LONG_TERM)
        memory.store("Test 3", MemoryType.EPISODIC)

        stats = memory.stats()
        assert stats["total"] == 3
        assert stats["session"] == 1
        assert stats["long_term"] == 1
        assert stats["episodic"] == 1


class TestSessionHooks:
    """Test SessionHooks consolidation from ultimate_memory_hooks."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir) / "test.db"
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def hooks(self, temp_db):
        """Create SessionHooks instance."""
        mem = UnifiedMemory(db_path=str(temp_db))
        return SessionHooks(memory=mem, session_id="test-session")

    def test_hooks_creation(self, hooks):
        """Test SessionHooks creation."""
        assert hooks is not None
        assert hooks.session_id == "test-session"
        assert hooks.turn_count == 0
        assert len(hooks.events) == 0

    def test_on_session_start(self, hooks):
        """Test on_session_start hook."""
        result = hooks.on_session_start()
        assert result["success"] is True
        assert result["session_id"] == "test-session"
        assert "recent_context" in result
        assert len(hooks.events) == 1

    def test_on_user_prompt(self, hooks):
        """Test on_user_prompt hook."""
        result = hooks.on_user_prompt("What is Python?")
        assert result["success"] is True
        assert "event_id" in result
        assert len(hooks.events) == 1

    def test_on_assistant_response(self, hooks):
        """Test on_assistant_response hook."""
        result = hooks.on_assistant_response("Python is a programming language")
        assert result["success"] is True
        assert "event_id" in result
        assert len(hooks.events) == 1

    def test_on_tool_use(self, hooks):
        """Test on_tool_use hook."""
        result = hooks.on_tool_use(
            tool_name="bash", tool_args={"command": "ls"}, phase="pre"
        )
        assert result["success"] is True
        assert "event_id" in result
        assert len(hooks.events) == 1

    def test_on_tool_use_post(self, hooks):
        """Test post-tool hook."""
        result = hooks.on_tool_use(
            tool_name="bash", phase="post", result="file1.txt\nfile2.txt"
        )
        assert result["success"] is True
        assert len(hooks.events) == 1

    def test_on_voice_input(self, hooks):
        """Test on_voice_input hook."""
        result = hooks.on_voice_input(text="Show me the source code", lady="Karen")
        assert result["success"] is True
        assert len(hooks.events) == 1

    def test_multiple_hooks_sequence(self, hooks):
        """Test sequence of hook calls."""
        hooks.on_session_start()
        hooks.on_user_prompt("Work on SD-1330")
        hooks.on_assistant_response("I'll help")
        hooks.on_tool_use("jira", phase="pre", tool_args={"ticket": "SD-1330"})
        hooks.on_tool_use("jira", phase="post", result="Ticket updated")
        hooks.on_session_end()

        assert hooks.turn_count == 6
        assert len(hooks.events) == 6

    def test_session_hooks_memory_storage(self, hooks):
        """Test that hooks store in unified memory."""
        hooks.on_user_prompt("Testing memory storage")
        hooks.on_assistant_response("Memory stored successfully")

        # Search for stored memories
        results = hooks.memory.search("memory storage")
        assert len(results) > 0


class TestSessionStitcher:
    """Test SessionStitcher consolidation from session_stitcher.py."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir) / "test.db"
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def stitcher(self, temp_db):
        """Create SessionStitcher instance."""
        mem = UnifiedMemory(db_path=str(temp_db))
        return SessionStitcher(memory=mem)

    def test_stitcher_creation(self, stitcher):
        """Test SessionStitcher creation."""
        assert stitcher is not None
        assert stitcher._current_session is None

    def test_start_session(self, stitcher):
        """Test session start."""
        session_id = stitcher.start_session("test-session-001")
        assert session_id == "test-session-001"
        assert stitcher._current_session == "test-session-001"

    def test_process_message_basic(self, stitcher):
        """Test basic message processing."""
        stitcher.start_session("session-001")
        result = stitcher.process_message("Working on bug fix")

        assert result["session_id"] == "session-001"
        assert result["message_count"] == 1
        assert "entities" in result
        assert "topics" in result

    def test_process_message_with_jira(self, stitcher):
        """Test message processing with JIRA ticket."""
        stitcher.start_session("session-001")
        result = stitcher.process_message("Working on SD-1330 payment feature")

        assert result["session_id"] == "session-001"
        jira_tickets = result["entities"].get("jira_tickets", [])
        assert "SD-1330" in jira_tickets

    def test_process_message_with_pr(self, stitcher):
        """Test message processing with PR number."""
        stitcher.start_session("session-001")
        result = stitcher.process_message("PR #209 is ready for review")

        assert result["session_id"] == "session-001"
        pr_numbers = result["entities"].get("pr_numbers", [])
        assert "209" in pr_numbers

    def test_extract_entities(self, stitcher):
        """Test entity extraction."""
        entities = stitcher._extract_entities(
            "SD-1330 and PR #209 with Steve and Kate in /src/utils.py"
        )
        assert "SD-1330" in entities["jira_tickets"]
        assert "209" in entities["pr_numbers"]
        assert len(entities["file_paths"]) > 0

    def test_extract_topics(self, stitcher):
        """Test topic extraction."""
        topics = stitcher._extract_topics("Debugging the code and fixing the bug")
        assert "coding" in topics

    def test_find_related_sessions_jira(self, stitcher):
        """Test finding related sessions by JIRA ticket."""
        # First session with SD-1330
        stitcher.start_session("session-001")
        stitcher.process_message("Working on SD-1330")

        # Second session also mentioning SD-1330
        stitcher.start_session("session-002")
        stitcher.process_message("Continuing work on SD-1330")

        # Find related
        related = stitcher.find_related_sessions(entities=["SD-1330"])
        assert len(related) > 0

    def test_get_session_context(self, stitcher):
        """Test getting session context."""
        stitcher.start_session("session-001")
        stitcher.process_message("Working on SD-1330 bug")
        stitcher.process_message("Fixed the issue")

        context = stitcher.get_session_context("session-001")
        assert context["session_id"] == "session-001"
        assert context["message_count"] == 2
        assert "entities" in context
        assert "topics" in context

    def test_end_session(self, stitcher):
        """Test session end."""
        stitcher.start_session("session-001")
        stitcher.process_message("Did some work")

        result = stitcher.end_session()
        assert result["success"] is True
        assert "summary" in result
        assert stitcher._current_session is None

    def test_multiple_sessions_continuity(self, stitcher):
        """Test continuity across sessions."""
        # Session 1
        stitcher.start_session("session-001")
        stitcher.process_message("Working on SD-1330")
        stitcher.end_session()

        # Session 2
        stitcher.start_session("session-002")
        result = stitcher.process_message("Continuing SD-1330")
        stitcher.end_session()

        # Should find related sessions
        assert len(result["related_sessions"]) > 0


class TestHookEventDataclass:
    """Test HookEvent consolidation."""

    def test_hook_event_creation(self):
        """Test HookEvent creation."""
        event = HookEvent(
            event_type="userPrompt",
            source="copilot-cli",
            timestamp="2026-04-01T10:00:00Z",
            session_id="session-001",
            content="Test content",
            role="user",
        )
        assert event.event_type == "userPrompt"
        assert event.source == "copilot-cli"
        assert event.role == "user"
        assert event.event_id is not None

    def test_hook_event_to_dict(self):
        """Test HookEvent conversion to dict."""
        event = HookEvent(
            event_type="userPrompt",
            source="copilot-cli",
            timestamp="2026-04-01T10:00:00Z",
            session_id="session-001",
            content="Test",
        )
        d = event.to_dict()
        assert d["event_type"] == "userPrompt"
        assert d["source"] == "copilot-cli"
        assert d["session_id"] == "session-001"


class TestSessionLinkDataclass:
    """Test SessionLink consolidation."""

    def test_session_link_creation(self):
        """Test SessionLink creation."""
        link = SessionLink(
            from_session="session-001",
            to_session="session-002",
            link_type="jira_ticket",
            shared_items=["SD-1330"],
            strength=0.95,
            timestamp="2026-04-01T10:00:00Z",
        )
        assert link.from_session == "session-001"
        assert link.to_session == "session-002"
        assert link.strength == 0.95

    def test_session_link_to_dict(self):
        """Test SessionLink conversion to dict."""
        link = SessionLink(
            from_session="session-001",
            to_session="session-002",
            link_type="topic",
            shared_items=["deployment"],
            strength=0.8,
            timestamp="2026-04-01T10:00:00Z",
        )
        d = link.to_dict()
        assert d["link_type"] == "topic"
        assert d["strength"] == 0.8


class TestFactoryFunctions:
    """Test factory functions."""

    def test_get_unified_memory_singleton(self):
        """Test get_unified_memory creates singleton."""
        mem1 = get_unified_memory()
        mem2 = get_unified_memory()
        assert mem1 is mem2

    def test_get_session_hooks_singleton(self):
        """Test get_session_hooks creates singleton."""
        hooks1 = get_session_hooks()
        hooks2 = get_session_hooks()
        assert hooks1 is hooks2

    def test_get_session_stitcher_singleton(self):
        """Test get_session_stitcher creates singleton."""
        stitcher1 = get_session_stitcher()
        stitcher2 = get_session_stitcher()
        assert stitcher1 is stitcher2


class TestShellCallableFunctions:
    """Test shell-callable hook functions."""

    def test_on_session_start_json(self):
        """Test on_session_start with JSON."""
        result = on_session_start('{"key": "value"}')
        data = json.loads(result)
        assert data["success"] is True

    def test_on_user_prompt_json(self):
        """Test on_user_prompt with JSON."""
        result = on_user_prompt("Hello assistant", "{}")
        data = json.loads(result)
        assert data["success"] is True

    def test_on_assistant_response_json(self):
        """Test on_assistant_response with JSON."""
        result = on_assistant_response("Hello user", "{}")
        data = json.loads(result)
        assert data["success"] is True

    def test_on_tool_use_json(self):
        """Test on_tool_use with JSON."""
        result = on_tool_use("bash", "pre", '{"cmd": "ls"}', "")
        data = json.loads(result)
        assert data["success"] is True


class TestDeprecationWrappers:
    """Test deprecation wrappers for backwards compatibility."""

    def test_ultimate_memory_hooks_import(self):
        """Test that old imports still work (with warnings)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import sys

            sys.path.insert(0, os.path.expanduser("~/brain"))
            from core.hooks.ultimate_memory_hooks import (
                UltimateMemoryHooks,
                get_hooks,
            )

            # Should warn about deprecation
            assert len(w) >= 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "DEPRECATED" in str(w[-1].message).upper()

    def test_session_stitcher_import(self):
        """Test that old session_stitcher imports still work."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import sys

            sys.path.insert(0, os.path.expanduser("~/brain"))
            from core.memory.session_stitcher import (
                SessionStitcher as OldStitcher,
            )
            from core.memory.session_stitcher import (
                get_stitcher,
            )

            # Should warn about deprecation
            assert len(w) >= 1
            assert issubclass(w[-1].category, DeprecationWarning)


class TestConsolidationIntegration:
    """Test full consolidation - hooks + stitcher working together."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir) / "test.db"
        shutil.rmtree(tmpdir)

    def test_hooks_and_stitcher_integration(self, temp_db):
        """Test hooks and stitcher working together."""
        mem = UnifiedMemory(db_path=str(temp_db))
        hooks = SessionHooks(memory=mem)
        stitcher = SessionStitcher(memory=mem)

        # Start session with hooks
        hooks.on_session_start()

        # Process messages with stitcher
        stitcher.start_session(hooks.session_id)
        result = stitcher.process_message("Working on SD-1330 feature")

        # Hooks capture more events
        hooks.on_user_prompt("Continue on SD-1330")
        hooks.on_assistant_response("Continuing...")

        # Both systems should see the same memory
        stats = mem.stats()
        assert stats["total"] >= 2  # At least 2 memories stored


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
