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
"""Analytics dashboard helpers for multi-conversation chatbot insights."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ConversationMetrics:
    total_conversations: int
    resolved_conversations: int
    escalated_conversations: int
    average_messages_per_conversation: float
    average_first_response_seconds: float


@dataclass(frozen=True)
class CommonQuestionInsight:
    topic: str
    count: int
    share_of_conversations: float


@dataclass(frozen=True)
class ConversionTracking:
    total_conversations: int
    converted_conversations: int
    conversion_rate: float
    attributed_revenue: float


@dataclass(frozen=True)
class CustomerSatisfactionScore:
    average_score: float
    response_count: int
    sentiment_mix: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PeakHourInsight:
    hour_of_day: int
    conversations: int


class ChatbotAnalyticsDashboard:
    """Compute dashboard-ready chatbot analytics from raw conversation logs."""

    QUESTION_TOPICS = {
        "shipping": {"delivery", "shipping", "tracking", "where is my order"},
        "refund": {"refund", "return", "cancel"},
        "pricing": {"discount", "coupon", "price", "sale"},
        "product": {"size", "stock", "available", "recommend"},
    }

    def conversation_metrics(
        self, conversations: Iterable[Mapping[str, object]]
    ) -> ConversationMetrics:
        conversation_list = list(conversations)
        if not conversation_list:
            return ConversationMetrics(0, 0, 0, 0.0, 0.0)

        resolved = 0
        escalated = 0
        message_counts: list[int] = []
        first_response_seconds: list[float] = []

        for convo in conversation_list:
            messages = list(convo.get("messages", []))
            message_counts.append(len(messages))
            if convo.get("resolved"):
                resolved += 1
            if convo.get("escalated"):
                escalated += 1

            user_at = None
            assistant_at = None
            for message in messages:
                role = str(message.get("role", "")).lower()
                timestamp = message.get("timestamp")
                if not isinstance(timestamp, datetime):
                    continue
                if role == "user" and user_at is None:
                    user_at = timestamp
                elif role == "assistant" and user_at is not None:
                    assistant_at = timestamp
                    break
            if user_at and assistant_at:
                first_response_seconds.append((assistant_at - user_at).total_seconds())

        return ConversationMetrics(
            total_conversations=len(conversation_list),
            resolved_conversations=resolved,
            escalated_conversations=escalated,
            average_messages_per_conversation=round(mean(message_counts), 2),
            average_first_response_seconds=(
                round(mean(first_response_seconds), 2)
                if first_response_seconds
                else 0.0
            ),
        )

    def common_questions_analysis(
        self,
        conversations: Iterable[Mapping[str, object]],
        *,
        top_n: int = 5,
    ) -> list[CommonQuestionInsight]:
        conversation_list = list(conversations)
        topic_counter: Counter[str] = Counter()
        for convo in conversation_list:
            user_text = " ".join(
                str(message.get("content", "")).lower()
                for message in convo.get("messages", [])
                if str(message.get("role", "")).lower() == "user"
            )
            for topic, hints in self.QUESTION_TOPICS.items():
                if any(hint in user_text for hint in hints):
                    topic_counter[topic] += 1

        total = max(len(conversation_list), 1)
        return [
            CommonQuestionInsight(
                topic=topic, count=count, share_of_conversations=round(count / total, 2)
            )
            for topic, count in topic_counter.most_common(top_n)
        ]

    def conversion_tracking(
        self, conversations: Iterable[Mapping[str, object]]
    ) -> ConversionTracking:
        conversation_list = list(conversations)
        converted = 0
        revenue = 0.0
        for convo in conversation_list:
            if convo.get("converted"):
                converted += 1
                revenue += float(convo.get("conversion_value", 0.0) or 0.0)

        total = len(conversation_list)
        return ConversionTracking(
            total_conversations=total,
            converted_conversations=converted,
            conversion_rate=round((converted / total), 2) if total else 0.0,
            attributed_revenue=round(revenue, 2),
        )

    def customer_satisfaction_scores(
        self, conversations: Iterable[Mapping[str, object]]
    ) -> CustomerSatisfactionScore:
        ratings: list[float] = []
        sentiment_mix: Counter[str] = Counter()
        for convo in conversations:
            if convo.get("satisfaction_score") is not None:
                ratings.append(float(convo["satisfaction_score"]))
            sentiment = str(convo.get("sentiment", "neutral")).lower()
            sentiment_mix[sentiment] += 1

        average = round(mean(ratings), 2) if ratings else 0.0
        return CustomerSatisfactionScore(
            average_score=average,
            response_count=len(ratings),
            sentiment_mix=dict(sentiment_mix),
        )

    def peak_hours_analysis(
        self,
        conversations: Iterable[Mapping[str, object]],
        *,
        top_n: int = 3,
    ) -> list[PeakHourInsight]:
        hours: Counter[int] = Counter()
        for convo in conversations:
            started_at = convo.get("started_at")
            if isinstance(started_at, datetime):
                hours[started_at.hour] += 1

        return [
            PeakHourInsight(hour_of_day=hour, conversations=count)
            for hour, count in hours.most_common(top_n)
        ]

    def build_dashboard(
        self, conversations: Iterable[Mapping[str, object]]
    ) -> dict[str, object]:
        conversation_list = list(conversations)
        return {
            "conversation_metrics": self.conversation_metrics(conversation_list),
            "common_questions": self.common_questions_analysis(conversation_list),
            "conversion_tracking": self.conversion_tracking(conversation_list),
            "customer_satisfaction": self.customer_satisfaction_scores(
                conversation_list
            ),
            "peak_hours": self.peak_hours_analysis(conversation_list),
        }


__all__ = [
    "ChatbotAnalyticsDashboard",
    "CommonQuestionInsight",
    "ConversationMetrics",
    "ConversionTracking",
    "CustomerSatisfactionScore",
    "PeakHourInsight",
]
