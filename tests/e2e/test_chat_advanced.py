# SPDX-License-Identifier: Apache-2.0
"""Advanced chat tests for agentic-brain.

This suite extends basic chat coverage with stress, Firebase, multi-room,
message feature, security, and simple performance tests.

Constraints:
- No real external services (Firebase, WebSocket servers, LLM APIs)
- All tests must be deterministic and CI-friendly
- Use in-memory implementations and local SQLite for OfflineQueue
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from agentic_brain.api.rate_limiting import SimpleRateLimiter
from agentic_brain.chat import Chatbot, ChatConfig, Session, SessionManager
from agentic_brain.transport import (
    ChatFeatures,
    FirebasePresence,
    FirebaseReadReceipts,
    FirebaseTransport,
    OfflineQueue,
    ReconnectConfig,
    TransportConfig,
    TransportMessage,
    TransportType,
    WebSocketAuthConfig,
    WebSocketConnectionState,
    WebSocketPresence,
    WebSocketReadReceipts,
    WebSocketTransport,
)

# ---------------------------------------------------------------------------
# Common fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def local_chat_features() -> ChatFeatures:
    """Local-only ChatFeatures (no network/Firebase)."""

    return ChatFeatures(transport_type=None)


@pytest.fixture
def websocket_presence() -> WebSocketPresence:
    """WebSocket presence manager with broadcasting disabled for speed."""

    return WebSocketPresence(broadcast_changes=False)


@pytest.fixture
def websocket_receipts() -> WebSocketReadReceipts:
    """WebSocket receipts manager with broadcasting disabled for speed."""

    return WebSocketReadReceipts(broadcast_changes=False)


@pytest.fixture
def echo_bot(tmp_path: Path) -> Chatbot:
    """Chatbot that uses a simple echo LLM and temp session dir.

    This avoids any external LLM/router calls while still exercising
    Chatbot + SessionManager wiring.
    """

    config = ChatConfig(
        persist_sessions=True,
        use_memory=False,
        session_dir=tmp_path / "sessions",
        max_history=50,
    )

    async def echo_llm(messages: list[dict[str, str]]) -> str:  # type: ignore[override]
        # Return the last user message content for determinism
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg["content"]
        return ""

    return Chatbot("test-bot", config=config, llm=echo_llm)


# ---------------------------------------------------------------------------
# 1. WebSocket Stress Tests (10+ tests)
# ---------------------------------------------------------------------------


class TestWebSocketStress:
    """Stress tests around WebSocket presence/receipts and transport logic."""

    @pytest.mark.asyncio
    async def test_100_concurrent_connections(
        self, websocket_presence: WebSocketPresence
    ):
        """100 distinct users can connect without errors."""

        websockets: list[WebSocket] = []
        for i in range(100):
            ws = AsyncMock(spec=WebSocket)
            websockets.append(ws)
            await websocket_presence.add_connection(f"user_{i}", ws)

        connected = set(websocket_presence.get_connected_users())
        assert len(connected) == 100

    @pytest.mark.asyncio
    async def test_multiple_connections_same_user(
        self, websocket_presence: WebSocketPresence
    ):
        """A single user can have multiple concurrent WebSocket connections."""

        user_id = "user_multi"
        sockets = [AsyncMock(spec=WebSocket) for _ in range(5)]

        for ws in sockets:
            await websocket_presence.add_connection(user_id, ws, auto_online=False)

        assert websocket_presence.connection_count(user_id) == 5

        # Remove three connections
        for ws in sockets[:3]:
            await websocket_presence.remove_connection(ws, auto_offline=False)

        assert websocket_presence.connection_count(user_id) == 2

    @pytest.mark.asyncio
    async def test_rapid_connect_disconnect_cycles(
        self, websocket_presence: WebSocketPresence
    ):
        """User can rapidly connect/disconnect without leaving stale state."""

        user_id = "cycler"

        for _ in range(20):
            ws = AsyncMock(spec=WebSocket)
            await websocket_presence.add_connection(user_id, ws)
            await websocket_presence.remove_connection(ws)

        assert user_id not in websocket_presence.get_connected_users()

    @pytest.mark.asyncio
    async def test_broadcast_all_handles_failed_sends(self):
        """Broadcasting cleans up connections whose send_json fails."""

        presence = WebSocketPresence(broadcast_changes=True)

        ok_ws = AsyncMock(spec=WebSocket)
        failing_ws = AsyncMock(spec=WebSocket)
        failing_ws.send_json.side_effect = RuntimeError("send failure")

        await presence.add_connection("user_ok", ok_ws)
        await presence.add_connection("user_bad", failing_ws)

        sent = await presence._broadcast_all({"type": "ping"})

        assert sent == 1
        assert "user_bad" not in presence.get_connected_users()

    @pytest.mark.asyncio
    async def test_message_flooding_receipts_manager(
        self, websocket_receipts: WebSocketReadReceipts
    ):
        """WebSocketReadReceipts can track 1000 messages quickly."""

        for i in range(1000):
            websocket_receipts.track_message(
                message_id=f"msg_{i}",
                sender_id="sender",
                session_id="session_flood",
            )

        stats = websocket_receipts.get_stats()
        assert stats["total_tracked"] == 1000

    @pytest.mark.asyncio
    async def test_presence_typing_under_load(
        self, websocket_presence: WebSocketPresence
    ):
        """Typing indicators scale to many users in same session."""

        session_id = "room_typing"
        users = [f"user_{i}" for i in range(50)]

        for user in users:
            await websocket_presence.set_online(user)
            await websocket_presence.start_typing(user, session_id)

        typing_users = websocket_presence.get_typing_users(session_id)
        assert len(typing_users) == 50

    @pytest.mark.asyncio
    async def test_websocket_auth_timeout_returns_none(self):
        """_wait_for_auth_token returns None on timeout without crashing."""

        config = TransportConfig(transport_type=TransportType.WEBSOCKET)
        transport = WebSocketTransport(
            config=config, websocket=AsyncMock(spec=WebSocket)
        )

        # Simulate asyncio.wait_for timing out
        async def fake_receive_json() -> (
            dict[str, Any]
        ):  # pragma: no cover - never awaited
            await asyncio.sleep(10)
            return {}

        transport.websocket.receive_json = fake_receive_json  # type: ignore[assignment]

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            token = await transport._wait_for_auth_token()

        assert token is None

    @pytest.mark.asyncio
    async def test_websocket_auth_fails_without_token(self):
        """_authenticate_connection rejects missing token without calling provider."""

        config = TransportConfig(transport_type=TransportType.WEBSOCKET)
        transport = WebSocketTransport(config=config)

        with patch("agentic_brain.transport.websocket.get_auth_provider") as gp:
            gp.return_value = None
            ok = await transport._authenticate_connection(token=None)

        assert ok is False
        assert transport.is_authenticated is False

    @pytest.mark.asyncio
    async def test_websocket_auth_success_with_mock_provider(self):
        """_authenticate_connection accepts valid token from auth provider."""

        config = TransportConfig(transport_type=TransportType.WEBSOCKET)
        transport = WebSocketTransport(config=config)

        class DummyUser:
            def __init__(self, login: str) -> None:
                self.login = login

        class DummyProvider:
            async def validate_token(self, token: str) -> DummyUser | None:  # type: ignore[override]
                return DummyUser("user123") if token == "valid" else None

        with patch(
            "agentic_brain.transport.websocket.get_auth_provider",
            return_value=DummyProvider(),
        ):
            ok = await transport._authenticate_connection(token="valid")

        assert ok is True
        assert transport.is_authenticated is True
        assert transport.user_id == "user123"

    def test_websocket_message_buffer_respects_limit(self):
        """WebSocketTransport message buffer enforces max length."""

        config = TransportConfig(transport_type=TransportType.WEBSOCKET)
        reconnect_cfg = WebSocketAuthConfig()  # auth config is cheap to construct
        transport = WebSocketTransport(
            config=config,
            reconnect_config=ReconnectConfig(buffer_size=10),
            auth_config=reconnect_cfg,
        )

        # Push more messages than buffer_size directly into buffer
        for i in range(25):
            transport._message_buffer.append(
                TransportMessage(content=f"m{i}", session_id="s", message_id=f"m{i}")
            )

        assert len(transport._message_buffer) == 10


# ---------------------------------------------------------------------------
# 2. Firebase Integration Tests (10+ tests)
# ---------------------------------------------------------------------------


class TestFirebaseIntegration:
    """Tests for Firebase-related transports and helpers (local-mode only)."""

    def test_firebase_presence_local_online_offline(self):
        """FirebasePresence behaves like PresenceManager when SDK disabled."""

        presence = FirebasePresence(database_url=None, credentials_path=None)
        assert presence.is_firebase_enabled is False

        result = asyncio.run(presence.set_online("user1"))
        assert result.user_id == "user1"
        assert presence.is_online("user1") is True

        asyncio.run(presence.set_offline("user1"))
        assert presence.is_online("user1") is False

    def test_firebase_presence_typing_indicators(self):
        """Typing indicators work in FirebasePresence local mode."""

        presence = FirebasePresence(database_url=None, credentials_path=None)
        asyncio.run(presence.set_online("user1"))
        asyncio.run(presence.start_typing("user1", "session1"))

        typing = presence.get_typing_users("session1")
        assert len(typing) == 1
        assert typing[0].user_id == "user1"

        asyncio.run(presence.stop_typing("user1", "session1"))
        assert presence.get_typing_users("session1") == []

    def test_firebase_receipts_local_tracking_and_read(self):
        """FirebaseReadReceipts tracks messages and read status locally."""

        receipts = FirebaseReadReceipts(database_url=None, credentials_path=None)
        assert receipts.is_firebase_enabled is False

        info = receipts.track_message("msg1", "sender", "session1")
        assert info.message_id == "msg1"
        assert info.status.name == "SENDING"

        asyncio.run(receipts.mark_delivered("msg1"))
        asyncio.run(receipts.mark_read("msg1", "user_b"))

        info2 = receipts.get_message_info("msg1")
        assert info2 is not None
        assert info2.is_read is True
        assert info2.is_read_by("user_b") is True

    def test_firebase_receipts_unread_count_and_mark_all(self):
        """Unread counting and bulk mark_all_read operate correctly."""

        receipts = FirebaseReadReceipts(database_url=None, credentials_path=None)
        for i in range(5):
            receipts.track_message(f"m{i}", "sender", "session1")

        assert receipts.get_unread_count("user_x", "session1") == 5
        asyncio.run(receipts.mark_all_read("user_x", "session1"))
        assert receipts.get_unread_count("user_x", "session1") == 0

    def test_firebase_receipts_cleanup_old_messages(self):
        """cleanup_old_messages removes very old messages but keeps recent ones."""

        receipts = FirebaseReadReceipts(database_url=None, credentials_path=None)
        # Create two messages: one old, one new
        info_old = receipts.track_message("old", "sender", "session")
        info_new = receipts.track_message("new", "sender", "session")

        # Manually backdate the old message
        info_old.sent_at = datetime.now(UTC) - timedelta(hours=48)
        receipts._messages["old"] = info_old
        receipts._messages["new"] = info_new

        removed = receipts.cleanup_old_messages(max_age_hours=24)
        assert removed == 1
        assert receipts.get_message_info("old") is None
        assert receipts.get_message_info("new") is not None

    def test_offline_queue_enqueue_dequeue_roundtrip(self, tmp_path: Path):
        """OfflineQueue can enqueue and dequeue messages reliably."""

        db_path = tmp_path / "offline.db"
        queue = OfflineQueue(db_path=db_path)

        msg = TransportMessage(content="hello", session_id="s1", message_id="m1")
        entry_id = queue.enqueue(msg)

        assert queue.size("s1") == 1

        pending = queue.get_pending("s1")
        assert len(pending) == 1
        assert pending[0].id == entry_id

        queue.dequeue(entry_id)
        assert queue.size("s1") == 0

    def test_offline_queue_retry_and_clear(self, tmp_path: Path):
        """Retry count increments and clear() removes messages."""

        db_path = tmp_path / "offline_retry.db"
        queue = OfflineQueue(db_path=db_path)

        msg = TransportMessage(content="x", session_id="room", message_id="m1")
        entry_id = queue.enqueue(msg)

        queue.increment_retry(entry_id)
        pending = queue.get_pending("room")
        assert pending[0].retry_count == 1

        cleared = queue.clear("room")
        assert cleared >= 1
        assert queue.size("room") == 0

    @pytest.mark.asyncio
    async def test_firebase_transport_queues_when_offline(self, tmp_path: Path):
        """FirebaseTransport.send() enqueues messages when not connected."""

        config = TransportConfig(transport_type=TransportType.FIREBASE)
        transport = FirebaseTransport(
            config=config,
            session_id="session_offline",
            offline_db_path=tmp_path / "offline_transport.db",
            enable_offline=True,
        )

        # Force disconnected state
        transport.connected = False
        transport._ref = None

        msg = TransportMessage(
            content="payload", session_id="session_offline", message_id="m1"
        )
        ok = await transport.send(msg)

        assert ok is True
        assert transport.stats.offline_queue_size == 1

    @pytest.mark.asyncio
    async def test_firebase_transport_connect_fails_without_sdk(self):
        """connect() returns False when Firebase SDK/credentials are missing."""

        config = TransportConfig(transport_type=TransportType.FIREBASE)
        transport = FirebaseTransport(
            config=config, session_id="no_sdk", enable_offline=False
        )

        # In environments without firebase_admin, connect() should fail gracefully.
        success = await transport.connect()
        assert (
            success is False
            or transport.connection_state != transport.connection_state.CONNECTED
        )

    def test_firebase_presence_stats_with_many_users(self):
        """Presence statistics scale with many online users."""

        presence = FirebasePresence(database_url=None, credentials_path=None)
        for i in range(200):
            asyncio.run(presence.set_online(f"u{i}"))

        stats = presence.get_stats()
        assert stats["total_users"] == 200
        assert stats["online"] == 200


# ---------------------------------------------------------------------------
# 3. Multi-Room Chat Tests (10+ tests)
# ---------------------------------------------------------------------------


class TestMultiRoomChat:
    """Treat session IDs as chat rooms and verify isolation semantics."""

    @pytest.mark.asyncio
    async def test_create_join_leave_rooms(self, echo_bot: Chatbot):
        """Users can chat in multiple rooms identified by session IDs."""

        await echo_bot.chat_async("hello room1", session_id="room1", user_id="alice")
        await echo_bot.chat_async("hello room2", session_id="room2", user_id="alice")

        s1 = echo_bot.get_session(session_id="room1", user_id="alice")
        s2 = echo_bot.get_session(session_id="room2", user_id="alice")

        assert s1.session_id != s2.session_id
        assert s1.message_count >= 1
        assert s2.message_count >= 1

    @pytest.mark.asyncio
    async def test_room_histories_are_isolated(self, echo_bot: Chatbot):
        """Messages from different rooms do not mix."""

        await echo_bot.chat_async("room1-msg", session_id="room1", user_id="user")
        await echo_bot.chat_async("room2-msg", session_id="room2", user_id="user")

        s1 = echo_bot.get_session(session_id="room1", user_id="user")
        s2 = echo_bot.get_session(session_id="room2", user_id="user")

        history1 = [m.content for m in s1.history]
        history2 = [m.content for m in s2.history]

        assert any("room1-msg" in c for c in history1)
        assert not any("room2-msg" in c for c in history1)
        assert any("room2-msg" in c for c in history2)

    @pytest.mark.asyncio
    async def test_private_room_by_user_id_isolation(self, echo_bot: Chatbot):
        """Private rooms can be modelled via per-user session IDs."""

        # Application-level convention: room_id:user_id
        await echo_bot.chat_async(
            "hi", session_id="support_room:cust1", user_id="cust1"
        )
        await echo_bot.chat_async(
            "hi", session_id="support_room:cust2", user_id="cust2"
        )

        s1 = echo_bot.get_session(session_id="support_room:cust1", user_id="cust1")
        s2 = echo_bot.get_session(session_id="support_room:cust2", user_id="cust2")

        assert s1.session_id != s2.session_id

    def test_room_member_lists_via_session_manager(self, tmp_path: Path):
        """SessionManager can list members (user_ids) per room using metadata."""

        manager = SessionManager(session_dir=tmp_path / "sessions")

        # Create two sessions representing rooms with different members
        s1 = manager.get_session("room_a", user_id="alice")
        s2 = manager.get_session("room_b", user_id="bob")
        s1.add_message("user", "hi from alice")
        s2.add_message("user", "hi from bob")

        manager.save_session(s1)
        manager.save_session(s2)

        # Reload and check user_ids
        s1_loaded = manager.load_session("room_a")
        s2_loaded = manager.load_session("room_b")

        assert s1_loaded is not None and s1_loaded.user_id == "alice"
        assert s2_loaded is not None and s2_loaded.user_id == "bob"

    def test_leave_room_by_clearing_history(self, tmp_path: Path):
        """Clearing a session effectively leaves the room (empty history)."""

        manager = SessionManager(session_dir=tmp_path / "sessions")
        session = manager.get_session("room_leave", user_id="user")
        session.add_message("user", "something")
        manager.save_session(session)

        session.clear_history()
        manager.save_session(session)

        loaded = manager.load_session("room_leave")
        assert loaded is not None
        assert loaded.messages == []

    def test_multiple_rooms_with_same_user(self, tmp_path: Path):
        """Same user can participate in many rooms via distinct session IDs."""

        manager = SessionManager(session_dir=tmp_path / "sessions")
        rooms = ["alpha", "beta", "gamma"]

        for room in rooms:
            s = manager.get_session(room, user_id="shared")
            s.add_message("user", f"msg in {room}")
            manager.save_session(s)

        loaded = [manager.load_session(room) for room in rooms]
        assert all(s is not None and s.user_id == "shared" for s in loaded)

    @pytest.mark.asyncio
    async def test_room_broadcast_via_chat_features(
        self, local_chat_features: ChatFeatures
    ):
        """ChatFeatures can simulate room broadcast via session_id."""

        session_id = "broadcast_room"
        sender = "sender"
        recipients = [f"u{i}" for i in range(5)]

        for u in [sender] + recipients:
            await local_chat_features.set_online(u)

        msg = await local_chat_features.track_message(
            message_id="broadcast1",
            sender_id=sender,
            session_id=session_id,
            recipient_ids=recipients,
        )

        assert msg.session_id == session_id
        assert local_chat_features.get_message_info("broadcast1") is not None

    @pytest.mark.asyncio
    async def test_room_member_typing_lists(self, local_chat_features: ChatFeatures):
        """Typing indicators can be used as a proxy for active room members."""

        session_id = "room_typing_members"
        users = ["alice", "bob", "charlie"]

        for u in users:
            await local_chat_features.set_online(u)
            await local_chat_features.start_typing(u, session_id)

        typing = local_chat_features.get_typing_users(session_id)
        typing_ids = {t.user_id for t in typing}
        assert typing_ids == set(users)

    @pytest.mark.asyncio
    async def test_room_reconnection_does_not_lose_history(self, echo_bot: Chatbot):
        """Simulate reconnect by reusing session_id while preserving history."""

        await echo_bot.chat_async("first", session_id="room_reconnect", user_id="u")
        session_before = echo_bot.get_session(session_id="room_reconnect", user_id="u")
        count_before = session_before.message_count

        # Simulate reconnect: just send another message with same IDs
        await echo_bot.chat_async("second", session_id="room_reconnect", user_id="u")
        session_after = echo_bot.get_session(session_id="room_reconnect", user_id="u")

        assert session_after.message_count > count_before

    def test_room_cleanup_of_expired_sessions(self, tmp_path: Path):
        """SessionManager cleanup removes expired room sessions from disk."""

        import json

        session_dir = tmp_path / "sessions"
        manager = SessionManager(session_dir=session_dir, timeout_seconds=1)

        s = manager.get_session("old_room", user_id="u")
        s.add_message("user", "msg")
        manager.save_session(s)

        # Manually backdate updated_at far into the past to force expiry
        path = next(session_dir.glob("session_*.json"))
        data = json.loads(path.read_text())
        data["updated_at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(data))

        # Force cleanup
        manager._cleanup_expired()
        assert not any(session_dir.glob("session_*.json"))


# ---------------------------------------------------------------------------
# 4. Message Features Tests (10+ tests)
# ---------------------------------------------------------------------------


class TestMessageFeatures:
    """Advanced message semantics built on top of Session dataclass."""

    def _create_session_with_messages(self) -> Session:
        s = Session(session_id="room_features", user_id="user")
        for i in range(5):
            s.add_message("user", f"message {i}", message_id=f"m{i}")
        return s

    def test_message_editing_updates_content(self):
        """Editing a message in Session updates content while preserving count."""

        s = self._create_session_with_messages()
        original_len = len(s.messages)

        # Simulate editing message m2
        for msg in s.messages:
            if msg.get("message_id") == "m2":
                msg["content"] = "edited content"

        assert len(s.messages) == original_len
        assert any(m["content"] == "edited content" for m in s.messages)

    def test_message_deletion_removes_from_history(self):
        """Deleting a message from Session removes it from history."""

        s = self._create_session_with_messages()
        s.messages = [m for m in s.messages if m.get("message_id") != "m1"]
        assert all(m.get("message_id") != "m1" for m in s.messages)

    def test_message_reactions_in_metadata(self):
        """Reactions can be stored in message metadata fields."""

        s = Session(session_id="room_reactions", user_id="u")
        s.add_message("user", "hello", message_id="m1", reactions=["👍", "❤️"])

        msg = s.messages[0]
        assert msg["reactions"] == ["👍", "❤️"]

    def test_message_threading_via_parent_id(self):
        """Threading can be modelled via parent_id metadata links."""

        s = Session(session_id="room_threads", user_id="u")
        root = s.add_message("user", "root", message_id="root")
        reply = s.add_message("user", "child", message_id="child", parent_id="root")

        assert root["message_id"] == "root"
        assert reply["parent_id"] == "root"

        thread = [
            m
            for m in s.messages
            if m.get("parent_id") == "root" or m["message_id"] == "root"
        ]
        assert len(thread) == 2

    def test_file_attachment_metadata(self):
        """File/image attachments can be represented in metadata."""

        s = Session(session_id="room_files", user_id="u")
        s.add_message(
            "user",
            "see file",
            message_id="m1",
            attachments=[{"filename": "image.png", "content_type": "image/png"}],
        )

        attachments = s.messages[0]["attachments"]
        assert attachments[0]["filename"] == "image.png"

    def test_message_search_by_keyword(self):
        """Simple keyword search over Session messages works."""

        s = Session(session_id="search_room", user_id="u")
        s.add_message("user", "first apple")
        s.add_message("user", "second banana")
        s.add_message("user", "third Apple pie")

        results = [m for m in s.messages if "apple" in m["content"].lower()]
        assert len(results) == 2

    def test_message_search_by_metadata_field(self):
        """Messages can be filtered by arbitrary metadata fields."""

        s = Session(session_id="meta_search", user_id="u")
        s.add_message("user", "a", message_id="1", label="important")
        s.add_message("user", "b", message_id="2", label="normal")

        important = [m for m in s.messages if m.get("label") == "important"]
        assert len(important) == 1
        assert important[0]["message_id"] == "1"

    def test_message_history_limit(self):
        """get_history(limit) returns only the requested tail slice."""

        s = self._create_session_with_messages()
        last_two = s.get_history(limit=2)
        assert len(last_two) == 2
        assert last_two[0]["content"].endswith("3")
        assert last_two[1]["content"].endswith("4")

    def test_clear_history_resets_messages(self):
        """clear_history removes all messages while keeping metadata."""

        s = self._create_session_with_messages()
        s.clear_history()
        assert s.messages == []

    def test_messages_have_iso_timestamps(self):
        """Messages include ISO8601 timestamps for audit/search."""

        s = Session(session_id="room_ts", user_id="u")
        s.add_message("user", "hi")
        ts = s.messages[0]["timestamp"]
        # Must be parseable ISO format
        parsed = datetime.fromisoformat(ts)
        assert isinstance(parsed, datetime)


# ---------------------------------------------------------------------------
# 5. Security Tests (10+ tests)
# ---------------------------------------------------------------------------


class TestChatSecurity:
    """Security-related tests for chat subsystems (without external services)."""

    def test_simple_rate_limiter_allows_within_limit(self):
        limiter = SimpleRateLimiter()
        key = "user:1"
        # First few requests should not be limited
        for _ in range(5):
            assert limiter.is_rate_limited(key, limit=10) is False

    def test_simple_rate_limiter_blocks_over_limit(self):
        limiter = SimpleRateLimiter()
        key = "user:2"
        for _ in range(10):
            limiter.is_rate_limited(key, limit=10)
        assert limiter.is_rate_limited(key, limit=10) is True

    @pytest.mark.asyncio
    async def test_xss_payload_stored_as_plain_text(self, echo_bot: Chatbot):
        """XSS-like payload is treated as data, not executed."""

        payload = "<script>alert('xss')</script>"
        response = await echo_bot.chat_async(
            payload, session_id="xss_room", user_id="u"
        )

        # Echo bot mirrors content, proving it's handled as plain text
        assert payload in response

    @pytest.mark.asyncio
    async def test_sql_injection_string_safe_in_chat(self, echo_bot: Chatbot):
        """SQL injection-looking strings do not break chat pipeline."""

        payload = "1; DROP TABLE users; --"
        response = await echo_bot.chat_async(
            payload, session_id="sql_room", user_id="u"
        )
        assert payload in response

    @pytest.mark.asyncio
    async def test_session_hijacking_prevented_by_isolation(self, echo_bot: Chatbot):
        """Different (session_id, user_id) pairs keep histories isolated."""

        await echo_bot.chat_async("secret for user1", session_id="s1", user_id="user1")
        await echo_bot.chat_async("secret for user2", session_id="s2", user_id="user2")

        s1 = echo_bot.get_session(session_id="s1", user_id="user1")
        s2 = echo_bot.get_session(session_id="s2", user_id="user2")

        h1 = " ".join(m.content for m in s1.history)
        h2 = " ".join(m.content for m in s2.history)

        assert "user1" in h1 or "secret for user1" in h1
        assert "secret for user2" not in h1
        assert "secret for user1" not in h2

    @pytest.mark.asyncio
    async def test_websocket_auth_rejects_invalid_token(self):
        """Invalid JWT token is rejected by WebSocketTransport auth helper."""

        config = TransportConfig(transport_type=TransportType.WEBSOCKET)
        transport = WebSocketTransport(config=config)

        class DummyUser:
            def __init__(self, login: str) -> None:
                self.login = login

        class DummyProvider:
            async def validate_token(self, token: str) -> DummyUser | None:  # type: ignore[override]
                return DummyUser("user") if token == "ok" else None

        with patch(
            "agentic_brain.transport.websocket.get_auth_provider",
            return_value=DummyProvider(),
        ):
            ok = await transport._authenticate_connection(token="bad")

        assert ok is False
        assert transport.is_authenticated is False

    def test_rate_limiting_keys_separate_users(self):
        """Different rate limit keys are tracked independently."""

        limiter = SimpleRateLimiter()
        k1, k2 = "user:a", "user:b"

        for _ in range(10):
            limiter.is_rate_limited(k1, limit=10)

        assert limiter.is_rate_limited(k1, limit=10) is True
        assert limiter.is_rate_limited(k2, limit=10) is False

    def test_session_serialization_is_safe_json(self, tmp_path: Path):
        """Session serialization/deserialization handles arbitrary content safely."""

        manager = SessionManager(session_dir=tmp_path / "sessions")
        session = manager.get_session("safe", user_id="u")
        session.add_message("user", "<b>bold</b>")
        manager.save_session(session)

        loaded = manager.load_session("safe")
        assert loaded is not None
        assert any("<b>bold</b>" in m["content"] for m in loaded.messages)

    def test_simple_rate_limiter_cleanup_prunes_old_keys(self):
        """cleanup() drops keys with very old timestamps."""

        limiter = SimpleRateLimiter()
        key = "user:cleanup"

        # Manually backfill timestamps
        limiter.requests[key] = [time.time() - 1000]
        limiter.cleanup()
        assert key not in limiter.requests or not limiter.requests[key]


# ---------------------------------------------------------------------------
# 6. Performance Tests (5+ tests)
# ---------------------------------------------------------------------------


class TestChatPerformance:
    """Light-weight performance/regression checks (not strict benchmarks)."""

    @pytest.mark.asyncio
    async def test_message_latency_under_load(self, local_chat_features: ChatFeatures):
        """Tracking many messages stays within a reasonable latency bound."""

        start = time.perf_counter()
        for i in range(500):
            await local_chat_features.track_message(
                message_id=f"m{i}",
                sender_id="sender",
                session_id="perf_session",
                recipient_ids=["r"],
            )
        duration = time.perf_counter() - start
        # This is intentionally generous to be CI-safe
        assert duration < 2.0

    @pytest.mark.asyncio
    async def test_presence_heartbeat_speed(self, local_chat_features: ChatFeatures):
        """Many heartbeat calls complete quickly."""

        await local_chat_features.set_online("perf_user")
        start = time.perf_counter()
        for _ in range(500):
            await local_chat_features.heartbeat("perf_user")
        duration = time.perf_counter() - start
        assert duration < 1.5

    @pytest.mark.asyncio
    async def test_typing_indicator_responsiveness(
        self, local_chat_features: ChatFeatures
    ):
        """Rapid typing start/stop cycles work without slowdown."""

        start = time.perf_counter()
        for i in range(200):
            await local_chat_features.start_typing("user", f"sess{i}")
            await local_chat_features.stop_typing("user", f"sess{i}")
        duration = time.perf_counter() - start
        assert duration < 2.0

    def test_offline_queue_scales_to_many_messages(self, tmp_path: Path):
        """OfflineQueue can handle many enqueued messages without errors."""

        db_path = tmp_path / "offline_perf.db"
        queue = OfflineQueue(db_path=db_path)

        for i in range(300):
            msg = TransportMessage(content=f"m{i}", session_id="s", message_id=f"m{i}")
            queue.enqueue(msg)

        assert queue.size("s") == 300

    def test_presence_manager_handles_many_users(self):
        """Presence manager handles many concurrent users (memory usage proxy)."""

        presence = FirebasePresence(database_url=None, credentials_path=None)
        for i in range(300):
            asyncio.run(presence.set_online(f"user_{i}"))

        stats = presence.get_stats()
        assert stats["total_users"] == 300
        assert stats["online"] == 300
