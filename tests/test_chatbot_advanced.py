# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from agentic_brain.commerce.chatbot.ai_features import ChatbotAIFeatures
from agentic_brain.commerce.chatbot.analytics_dashboard import ChatbotAnalyticsDashboard
from agentic_brain.commerce.chatbot.multi_channel import (
    FacebookMessengerAdapter,
    SMSAdapter,
    UnifiedInbox,
    WhatsAppAdapter,
)
from agentic_brain.commerce.chatbot.personalization import ChatbotPersonalization
from agentic_brain.commerce.chatbot.training import ChatbotTrainingPipeline
from agentic_brain.commerce.models import (
    WooCategory,
    WooOrder,
    WooOrderItem,
    WooOrderTotals,
    WooProduct,
)


def make_order(order_id: int, status: str, total: str, product_id: int) -> WooOrder:
    amount = Decimal(total)
    return WooOrder(
        id=order_id,
        status=status,
        items=[
            WooOrderItem(
                id=order_id,
                product_id=product_id,
                name=f"Product {product_id}",
                quantity=1,
                price=amount,
                total=amount,
            )
        ],
        totals=WooOrderTotals(
            subtotal=amount,
            discount_total=Decimal("0"),
            shipping_total=Decimal("0"),
            tax_total=Decimal("0"),
            total=amount,
            currency="USD",
        ),
    )


def make_product(
    product_id: int, name: str, price: str, category_id: int, *, in_stock: bool = True
) -> WooProduct:
    return WooProduct(
        id=product_id,
        name=name,
        price=Decimal(price),
        stock=10 if in_stock else 0,
        in_stock=in_stock,
        categories=[WooCategory(id=category_id, name=f"Category {category_id}")],
    )


def test_ai_features_support_sentiment_urgency_translation_and_handoff_summary():
    features = ChatbotAIFeatures()
    text = "Hola, necesito ayuda urgente con mi pedido, I am very frustrated and want a refund!!!"

    sentiment = features.analyze_sentiment(text)
    urgency = features.detect_urgency(text, sentiment=sentiment, customer_tier="vip")
    language = features.detect_language("hola gracias pedido urgente")
    translation = features.auto_translate("hola pedido urgente", target_language="en")
    summary = features.summarize_for_handoff(
        [
            {"role": "user", "content": "Hola, where is my order?"},
            {"role": "assistant", "content": "I am checking the shipment."},
            {"role": "user", "content": "I need a refund now, this is urgent."},
        ]
    )

    assert sentiment.label == "negative"
    assert urgency.should_escalate is True
    assert urgency.level in {"high", "critical"}
    assert language.code == "es"
    assert translation.translated is True
    assert "hello" in translation.translated_text
    assert summary.urgency in {"high", "critical"}
    assert summary.unresolved_items


def test_personalization_supports_persona_history_browsing_recommendations_and_pricing():
    personalization = ChatbotPersonalization()
    orders = [
        make_order(1, "completed", "250.00", 101),
        make_order(2, "completed", "220.00", 102),
        make_order(3, "processing", "210.00", 101),
        make_order(4, "completed", "230.00", 103),
        make_order(5, "completed", "240.00", 101),
    ]
    history = personalization.analyze_purchase_history(orders)
    browsing = personalization.track_browsing_behavior(
        [
            {
                "event": "view_product",
                "product_id": 201,
                "category_id": 10,
                "price": "199.00",
            },
            {
                "event": "compare",
                "product_id": 202,
                "category_id": 10,
                "price": "249.00",
            },
            {
                "event": "checkout_start",
                "product_id": 203,
                "category_id": 10,
                "price": "299.00",
            },
        ]
    )
    persona = personalization.detect_persona(
        customer={"tags": ["vip"]},
        purchase_history=history,
        browsing_profile=browsing,
    )
    catalog = [
        make_product(201, "Premium Speaker", "249.00", 10),
        make_product(202, "Budget Cable", "19.00", 11),
        make_product(203, "Studio Headphones", "299.00", 10),
    ]

    recommendations = personalization.personalized_recommendations(
        catalog=catalog,
        purchase_history=history,
        browsing_profile=browsing,
        persona=persona,
    )
    pricing = personalization.dynamic_pricing_suggestions(
        product=catalog[0],
        persona=persona,
        purchase_history=history,
        cart_total=Decimal("350.00"),
        inventory_pressure=0.9,
    )

    assert history.total_orders == 5
    assert browsing.intent_stage == "decision"
    assert persona.persona == "vip"
    assert recommendations
    assert recommendations[0].product_id in {201, 203}
    assert pricing.suggested_discount_percent > 0
    assert pricing.suggested_price is not None


def test_analytics_dashboard_surfaces_enterprise_metrics():
    dashboard = ChatbotAnalyticsDashboard()
    start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    conversations = [
        {
            "started_at": start,
            "resolved": True,
            "escalated": False,
            "converted": True,
            "conversion_value": 120.0,
            "satisfaction_score": 4.8,
            "sentiment": "positive",
            "messages": [
                {"role": "user", "content": "Where is my order?", "timestamp": start},
                {
                    "role": "assistant",
                    "content": "It shipped this morning.",
                    "timestamp": start + timedelta(seconds=20),
                },
            ],
        },
        {
            "started_at": start.replace(hour=10),
            "resolved": False,
            "escalated": True,
            "converted": False,
            "conversion_value": 0.0,
            "satisfaction_score": 2.0,
            "sentiment": "negative",
            "messages": [
                {
                    "role": "user",
                    "content": "I need a refund for this late delivery.",
                    "timestamp": start.replace(hour=10),
                },
                {
                    "role": "assistant",
                    "content": "I can help with that.",
                    "timestamp": start.replace(hour=10) + timedelta(seconds=40),
                },
            ],
        },
    ]

    snapshot = dashboard.build_dashboard(conversations)
    metrics = snapshot["conversation_metrics"]
    common = snapshot["common_questions"]
    conversion = snapshot["conversion_tracking"]
    satisfaction = snapshot["customer_satisfaction"]
    peaks = snapshot["peak_hours"]

    assert metrics.total_conversations == 2
    assert metrics.escalated_conversations == 1
    assert any(item.topic == "shipping" for item in common)
    assert any(item.topic == "refund" for item in common)
    assert conversion.conversion_rate == 0.5
    assert satisfaction.average_score == 3.4
    assert peaks[0].conversations >= 1


def test_training_pipeline_builds_datasets_faqs_intents_and_learning_reports():
    pipeline = ChatbotTrainingPipeline()
    conversations = [
        {
            "conversation_id": "c1",
            "channel": "web",
            "messages": [
                {"role": "user", "content": "Where is my order?"},
                {"role": "assistant", "content": "Your order is in transit."},
                {"role": "user", "content": "Where is my order?"},
                {"role": "assistant", "content": "It should arrive tomorrow."},
            ],
        },
        {
            "conversation_id": "c2",
            "channel": "web",
            "messages": [
                {"role": "user", "content": "How do I get a refund?"},
                {
                    "role": "assistant",
                    "content": "You can start a return from your account page.",
                },
            ],
        },
    ]
    dataset = pipeline.build_fine_tuning_dataset(conversations, store_name="Demo Store")
    faqs = pipeline.auto_generate_faq(conversations, min_frequency=2)
    artifact = pipeline.train_intent_model_from_logs(
        [
            {"intent": "order_status", "text": "where is my order and tracking"},
            {"intent": "refund", "text": "refund status for my return"},
            {"intent": "order_status", "text": "track order delivery please"},
        ]
    )
    learning = pipeline.continuous_learning_from_feedback(
        [
            {"intent": "order_status", "score": 5},
            {"intent": "refund", "score": 2},
            {"intent": "order_status", "score": 4},
        ]
    )

    assert len(dataset) == 3
    assert faqs[0].frequency == 2
    assert artifact.predict("Can you track my order?") == "order_status"
    assert learning.accepted_examples == 2
    assert "order_status" in learning.promoted_intents


def test_multi_channel_integrations_feed_unified_inbox():
    inbox = UnifiedInbox()
    whatsapp = WhatsAppAdapter()
    facebook = FacebookMessengerAdapter()
    sms = SMSAdapter()
    now = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)

    inbox.ingest(
        whatsapp,
        {
            "id": "wa-1",
            "from": "+61400000001",
            "text": "Need help with my order",
            "timestamp": now,
            "urgent": True,
        },
    )
    inbox.ingest(
        facebook,
        {
            "id": "fb-1",
            "customer_id": "fb-user",
            "message": "Do you ship internationally?",
            "timestamp": now + timedelta(minutes=5),
        },
    )
    inbox.ingest(
        sms,
        {
            "id": "sms-1",
            "from": "+61400000001",
            "text": "Any update?",
            "timestamp": now + timedelta(minutes=10),
            "read": True,
        },
    )

    items = inbox.list_items()
    whatsapp_outbound = whatsapp.prepare_outbound(
        "+61400000001", "Thanks, a specialist will reply shortly."
    )
    sms_outbound = sms.prepare_outbound(
        "+61400000002",
        "This message should be trimmed if it exceeds the channel limit." * 5,
    )

    assert items
    assert items[0].priority == "high"
    assert items[0].channel == "whatsapp"
    assert len(inbox.conversation_thread("whatsapp", "+61400000001")) == 1
    assert whatsapp_outbound["channel"] == "whatsapp"
    assert len(sms_outbound["message"]) <= sms.capabilities.max_message_length
