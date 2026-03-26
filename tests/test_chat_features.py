# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Tests for unified ChatFeatures interface."""

from datetime import UTC

import pytest

from agentic_brain.transport import (
    ChatFeatures,
    MessageStatus,
    PresenceStatus,
    TransportType,
)


class MockWebSocket:
    """Mock FastAPI WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def send_json(self, data):
        if self.closed:
            raise Exception("WebSocket closed")
        self.sent_messages.append(data)

    async def close(self):
        self.closed = True


class TestChatFeaturesInit:
    """Test ChatFeatures initialization."""

    def test_init_local_mode(self):
        """Test local-only initialization."""
        features = ChatFeatures(transport_type=None)

        assert features.transport_type is None
        assert features.presence is not None
        assert features.receipts is not None

    def test_init_websocket_mode(self):
        """Test WebSocket mode initialization."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)

        assert features.transport_type == TransportType.WEBSOCKET
        # Should be WebSocketPresence and WebSocketReadReceipts
        assert hasattr(features.presence, "add_connection")
        assert hasattr(features.receipts, "add_connection")


class TestLocalMode:
    """Test ChatFeatures in local mode."""

    @pytest.mark.asyncio
    async def test_presence_works(self):
        """Test presence in local mode."""
        features = ChatFeatures()

        await features.set_online("user1")
        assert features.is_online("user1")

        await features.set_away("user1")
        user = features.get_presence("user1")
        assert user.status == PresenceStatus.AWAY

    @pytest.mark.asyncio
    async def test_typing_works(self):
        """Test typing in local mode."""
        features = ChatFeatures()

        await features.set_online("user1")
        await features.start_typing("user1", "chat-room")

        assert features.is_typing("user1", "chat-room")

        await features.stop_typing("user1", "chat-room")
        assert not features.is_typing("user1", "chat-room")

    @pytest.mark.asyncio
    async def test_receipts_work(self):
        """Test receipts in local mode."""
        features = ChatFeatures()

        await features.track_message("msg1", "sender", "session1", ["recipient"])
        await features.mark_sent("msg1")
        await features.mark_delivered("msg1")
        await features.mark_read("msg1", "recipient")

        info = features.get_message_info("msg1")
        assert info.status == MessageStatus.READ
        assert "recipient" in info.read_by

    @pytest.mark.asyncio
    async def test_unread_count(self):
        """Test unread count tracking."""
        features = ChatFeatures()

        await features.track_message("msg1", "sender", "s1", ["user1"])
        await features.track_message("msg2", "sender", "s1", ["user1"])
        await features.mark_sent("msg1")
        await features.mark_sent("msg2")

        assert features.get_unread_count("user1", "s1") == 2

        await features.mark_read("msg1", "user1")
        assert features.get_unread_count("user1", "s1") == 1


class TestWebSocketMode:
    """Test ChatFeatures in WebSocket mode."""

    @pytest.mark.asyncio
    async def test_add_connection(self):
        """Test adding WebSocket connection."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)
        ws = MockWebSocket()

        await features.add_connection("user1", ws)

        # User should be online
        assert features.is_online("user1")

    @pytest.mark.asyncio
    async def test_remove_connection(self):
        """Test removing WebSocket connection."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)
        # Disable broadcast to avoid issues
        features.presence._broadcast_changes = False
        features.receipts._broadcast_changes = False

        ws = MockWebSocket()

        await features.add_connection("user1", ws)
        user_id = await features.remove_connection(ws)

        assert user_id == "user1"

    @pytest.mark.asyncio
    async def test_presence_broadcasts(self):
        """Test that presence changes broadcast."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await features.add_connection("user1", ws1, auto_online=False)
        await features.add_connection("user2", ws2, auto_online=False)

        await features.set_online("user1")

        # Both should receive broadcast
        assert len(ws1.sent_messages) > 0
        assert len(ws2.sent_messages) > 0

    @pytest.mark.asyncio
    async def test_handle_message_presence(self):
        """Test handling incoming presence message."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)
        features.presence._broadcast_changes = False

        ws = MockWebSocket()
        await features.add_connection("user1", ws, auto_online=False)

        await features.handle_message(
            ws,
            {
                "type": "presence",
                "action": "online",
            },
        )

        assert features.is_online("user1")

    @pytest.mark.asyncio
    async def test_handle_message_typing(self):
        """Test handling incoming typing message."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)
        features.presence._broadcast_changes = False

        ws = MockWebSocket()
        await features.add_connection("user1", ws)

        await features.handle_message(
            ws,
            {
                "type": "typing",
                "action": "start",
                "session_id": "chat-room",
            },
        )

        assert features.is_typing("user1", "chat-room")

    @pytest.mark.asyncio
    async def test_handle_message_receipt(self):
        """Test handling incoming receipt message."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)
        features.presence._broadcast_changes = False
        features.receipts._broadcast_changes = False

        ws = MockWebSocket()
        await features.add_connection("recipient", ws)

        await features.track_message("msg1", "sender", "s1", ["recipient"])

        await features.handle_message(
            ws,
            {
                "type": "receipt",
                "action": "read",
                "message_id": "msg1",
            },
        )

        info = features.get_message_info("msg1")
        assert "recipient" in info.read_by


class TestCallbacks:
    """Test callback registration."""

    @pytest.mark.asyncio
    async def test_presence_callback(self):
        """Test presence change callback."""
        features = ChatFeatures()

        changes = []
        features.on_presence_change(lambda u: changes.append(u))

        await features.set_online("user1")

        assert len(changes) == 1

    @pytest.mark.asyncio
    async def test_typing_callback(self):
        """Test typing change callback."""
        features = ChatFeatures()

        typing_events = []
        features.on_typing_change(lambda t: typing_events.append(t))

        await features.set_online("user1")
        await features.start_typing("user1", "chat-room")

        assert len(typing_events) >= 1

    @pytest.mark.asyncio
    async def test_status_callback(self):
        """Test message status callback."""
        features = ChatFeatures()

        status_changes = []
        features.on_status_change(lambda info: status_changes.append(info.status))

        await features.track_message("msg1", "sender", "s1", ["r1"])
        await features.mark_sent("msg1")

        assert MessageStatus.SENT in status_changes

    @pytest.mark.asyncio
    async def test_read_callback(self):
        """Test message read callback."""
        features = ChatFeatures()

        reads = []
        features.on_read(lambda m, r: reads.append((m, r)))

        await features.track_message("msg1", "sender", "s1", ["r1"])
        await features.mark_read("msg1", "r1")

        assert ("msg1", "r1") in reads


class TestStats:
    """Test statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_local(self):
        """Test stats in local mode."""
        features = ChatFeatures()

        await features.set_online("user1")
        await features.track_message("msg1", "sender", "s1", ["r1"])

        stats = features.get_stats()

        assert stats["transport"] == "local"
        assert "presence" in stats
        assert "receipts" in stats
        assert stats["presence"]["online"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_websocket(self):
        """Test stats in WebSocket mode."""
        features = ChatFeatures(transport_type=TransportType.WEBSOCKET)
        features.presence._broadcast_changes = False

        ws = MockWebSocket()
        await features.add_connection("user1", ws)

        stats = features.get_stats()

        assert stats["transport"] == "websocket"
        assert stats["presence"]["connections"] == 1


class TestLifecycle:
    """Test lifecycle management."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with ChatFeatures() as features:
            await features.set_online("user1")
            assert features.is_online("user1")
        # Should clean up after exit

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test manual start/stop."""
        features = ChatFeatures()

        await features.start()
        await features.set_online("user1")
        await features.stop()


class TestHelperMethods:
    """Test helper/convenience methods."""

    @pytest.mark.asyncio
    async def test_heartbeat(self):
        """Test heartbeat updates last activity."""
        features = ChatFeatures()

        await features.set_online("user1")
        user1 = features.get_presence("user1")
        first_activity = user1.last_activity

        import asyncio

        await asyncio.sleep(0.1)

        await features.heartbeat("user1")
        user2 = features.get_presence("user1")

        assert user2.last_activity > first_activity

    @pytest.mark.asyncio
    async def test_get_online_users(self):
        """Test getting all online users."""
        features = ChatFeatures()

        await features.set_online("user1")
        await features.set_online("user2")
        await features.set_offline("user2")

        online = features.get_online_users()

        assert len(online) == 1
        assert online[0].user_id == "user1"

    @pytest.mark.asyncio
    async def test_mark_all_read(self):
        """Test marking all messages read."""
        features = ChatFeatures()

        await features.track_message("msg1", "sender", "s1", ["user1"])
        await features.track_message("msg2", "sender", "s1", ["user1"])
        await features.track_message("msg3", "sender", "s2", ["user1"])

        marked_count = await features.mark_all_read("user1", "s1")

        assert marked_count == 2
        assert features.get_unread_count("user1", "s2") == 1  # msg3 still unread


class TestCommerceChatbotHelpers:
    """Tests for WooCommerce chatbot helper classes."""

    def test_cart_summary_and_discount(self):
        from decimal import Decimal

        from agentic_brain.commerce import CartAssistant, CartLine

        assistant = CartAssistant(currency="usd")
        lines = [
            CartLine(
                product_id=1, name="T-Shirt", quantity=2, unit_price=Decimal("25")
            ),
            CartLine(product_id=2, name="Jeans", quantity=1, unit_price=Decimal("80")),
        ]

        summary = assistant.build_summary(lines, shipping_total=Decimal("10"))
        assert summary.subtotal == Decimal("130")
        assert summary.total == Decimal("140")

        # Apply a simple 10% preview discount using a string code
        discounted = assistant.apply_coupon(summary, "WELCOME10")
        assert discounted.total < summary.total
        assert "WELCOME10" in discounted.applied_coupons

    def test_add_to_cart_parsing(self):
        from agentic_brain.commerce import CartAssistant

        assistant = CartAssistant()
        intent = assistant.parse_add_to_cart_intent("please add 3 red shirts")
        assert intent["quantity"] == 3
        assert "red shirts" in intent["query"]

    def test_product_alternatives_and_history(self):
        from decimal import Decimal

        from agentic_brain.commerce import (
            ProductAdvisor,
            WooAddress,
            WooCategory,
            WooCustomer,
            WooOrder,
            WooOrderItem,
            WooOrderTotals,
            WooProduct,
        )

        advisor = ProductAdvisor()

        cat_shirts = WooCategory(id=1, name="Shirts")
        base = WooProduct(
            id=1,
            name="Blue Shirt",
            price=Decimal("50"),
            description="",
            stock=0,
            categories=[cat_shirts],
            images=[],
        )
        alt1 = WooProduct(
            id=2,
            name="Green Shirt",
            price=Decimal("45"),
            description="",
            stock=5,
            categories=[cat_shirts],
            images=[],
        )
        alt2 = WooProduct(
            id=3,
            name="Red Shirt",
            price=Decimal("60"),
            description="",
            stock=5,
            categories=[cat_shirts],
            images=[],
        )

        alts = advisor.suggest_alternatives(base, [alt1, alt2])
        assert alts[0].id == 2  # cheaper first

        # History-based recommendation should avoid already purchased IDs
        order = WooOrder(
            id=10,
            status="completed",
            customer=WooCustomer(
                id=1,
                email="test@example.com",
                name="Test User",
                billing_address=WooAddress(country="AU"),
                shipping_address=WooAddress(country="AU"),
            ),
            items=[
                WooOrderItem(
                    id=1,
                    product_id=2,
                    name="Green Shirt",
                    sku=None,
                    quantity=1,
                    price=Decimal("45"),
                    total=Decimal("45"),
                )
            ],
            totals=WooOrderTotals(
                subtotal=Decimal("45"),
                discount_total=Decimal("0"),
                shipping_total=Decimal("0"),
                tax_total=Decimal("0"),
                total=Decimal("45"),
                currency="AUD",
            ),
            shipping=WooAddress(country="AU"),
            billing=WooAddress(country="AU"),
            coupons=[],
        )
        recs = advisor.recommend_from_history([order], [base, alt1, alt2])
        # alt2 is in the same category and not yet purchased
        assert any(p.id == 3 for p in recs)

    def test_order_support_status_and_eta(self):
        from datetime import datetime, timezone
        from decimal import Decimal

        from agentic_brain.commerce import (
            EtaEstimate,
            OrderSupport,
            WooAddress,
            WooCustomer,
            WooOrder,
            WooOrderTotals,
        )

        support = OrderSupport()

        order = WooOrder(
            id=42,
            status="processing",
            customer=WooCustomer(
                id=1,
                email="test@example.com",
                name="Test User",
                billing_address=WooAddress(country="AU"),
                shipping_address=WooAddress(country="AU"),
            ),
            items=[],
            totals=WooOrderTotals(
                subtotal=Decimal("100"),
                discount_total=Decimal("0"),
                shipping_total=Decimal("10"),
                tax_total=Decimal("0"),
                total=Decimal("110"),
                currency="AUD",
            ),
            shipping=WooAddress(country="AU"),
            billing=WooAddress(country="AU"),
            coupons=[],
        )

        summary = support.summarise_status(order)
        assert summary.is_shipped
        assert "being prepared" in summary.description

        created_at = datetime(2026, 1, 1, tzinfo=UTC)
        eta = support.estimate_eta(order, created_at=created_at, domestic=True)
        assert isinstance(eta, EtaEstimate)
        assert eta.eta_date >= created_at.date()

    def test_live_handoff_helpers(self):
        from datetime import datetime, timedelta, timezone

        from agentic_brain.commerce import LiveHandoffAssistant

        assistant = LiveHandoffAssistant()
        convo = [
            {"role": "user", "content": "I am really upset, nothing works"},
            {"role": "assistant", "content": "Let me help you with that"},
        ]

        # Escalation to human support with context
        request = assistant.build_handoff_request(
            conversation=convo, reason="angry customer"
        )
        assert request.priority == "high"
        assert "Customer said" in request.summary

        # Queue status
        status = assistant.queue_status(position=3, average_handle_minutes=4)
        assert status.estimated_wait_minutes == 8

        # Callback scheduling
        start = datetime.now(UTC) + timedelta(hours=1)
        end = start + timedelta(minutes=30)
        callback = assistant.schedule_callback(
            contact_method="phone", window_start=start, window_end=end
        )
        assert callback.confirmed
