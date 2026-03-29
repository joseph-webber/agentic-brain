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
"""Advanced AI features for enterprise WooCommerce chatbots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

POSITIVE_WORDS = {
    "amazing",
    "awesome",
    "easy",
    "excellent",
    "fantastic",
    "good",
    "great",
    "happy",
    "helpful",
    "love",
    "perfect",
    "quick",
    "satisfied",
    "thanks",
}
NEGATIVE_WORDS = {
    "angry",
    "annoyed",
    "awful",
    "bad",
    "broken",
    "cancel",
    "disappointed",
    "frustrated",
    "hate",
    "issue",
    "late",
    "refund",
    "terrible",
    "upset",
    "waiting",
    "worst",
}
URGENCY_WORDS = {
    "asap",
    "immediately",
    "now",
    "today",
    "urgent",
    "right away",
    "escalate",
}
ESCALATION_WORDS = {
    "chargeback",
    "complaint",
    "lawyer",
    "manager",
    "refund",
    "supervisor",
}
LANGUAGE_HINTS: dict[str, tuple[str, set[str]]] = {
    "es": ("Spanish", {"hola", "pedido", "gracias", "reembolso", "urgente", "ayuda"}),
    "fr": (
        "French",
        {"bonjour", "commande", "merci", "remboursement", "urgent", "aide"},
    ),
    "de": (
        "German",
        {"hallo", "bestellung", "danke", "ruckerstattung", "hilfe", "dringend"},
    ),
    "it": ("Italian", {"ciao", "ordine", "grazie", "rimborso", "aiuto", "urgente"}),
    "pt": (
        "Portuguese",
        {"ola", "pedido", "obrigado", "reembolso", "ajuda", "urgente"},
    ),
    "en": ("English", {"hello", "order", "thanks", "refund", "help", "urgent"}),
}
TRANSLATION_DICTIONARY: dict[tuple[str, str], dict[str, str]] = {
    ("es", "en"): {
        "hola": "hello",
        "pedido": "order",
        "gracias": "thanks",
        "reembolso": "refund",
        "urgente": "urgent",
        "ayuda": "help",
        "donde": "where",
        "esta": "is",
        "mi": "my",
    },
    ("fr", "en"): {
        "bonjour": "hello",
        "commande": "order",
        "merci": "thanks",
        "remboursement": "refund",
        "urgent": "urgent",
        "aide": "help",
        "ou": "where",
        "est": "is",
        "ma": "my",
    },
    ("de", "en"): {
        "hallo": "hello",
        "bestellung": "order",
        "danke": "thanks",
        "ruckerstattung": "refund",
        "hilfe": "help",
        "dringend": "urgent",
        "wo": "where",
        "ist": "is",
        "meine": "my",
    },
    ("it", "en"): {
        "ciao": "hello",
        "ordine": "order",
        "grazie": "thanks",
        "rimborso": "refund",
        "aiuto": "help",
        "urgente": "urgent",
        "dove": "where",
        "mio": "my",
    },
    ("pt", "en"): {
        "ola": "hello",
        "pedido": "order",
        "obrigado": "thanks",
        "reembolso": "refund",
        "ajuda": "help",
        "urgente": "urgent",
        "onde": "where",
        "esta": "is",
        "meu": "my",
    },
}


@dataclass(frozen=True)
class SentimentAnalysis:
    """Outcome of a customer-sentiment assessment."""

    label: str
    score: float
    positive_signals: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UrgencyAssessment:
    """Priority recommendation for triaging a conversation."""

    level: str
    score: int
    should_escalate: bool
    reasons: list[str] = field(default_factory=list)
    target_response_minutes: int = 30


@dataclass(frozen=True)
class LanguageDetection:
    """Language classification for an inbound message."""

    code: str
    language: str
    confidence: float


@dataclass(frozen=True)
class TranslationResult:
    """Translation payload used by the chatbot and hand-off tooling."""

    source_language: str
    target_language: str
    original_text: str
    translated_text: str
    translated: bool


@dataclass(frozen=True)
class ConversationSummary:
    """Structured summary for human hand-off or CRM notes."""

    headline: str
    customer_goal: str
    key_points: list[str] = field(default_factory=list)
    unresolved_items: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    urgency: str = "normal"
    recommended_action: str = "Continue with automated support."


class ChatbotAIFeatures:
    """Enterprise-friendly AI primitives backed by deterministic heuristics."""

    def analyze_sentiment(self, message: str) -> SentimentAnalysis:
        text = (message or "").lower()
        tokens = [token.strip(".,!?;:'\"()[]{}") for token in text.split()]
        positives = sorted({token for token in tokens if token in POSITIVE_WORDS})
        negatives = sorted({token for token in tokens if token in NEGATIVE_WORDS})

        raw_score = len(positives) - len(negatives)
        punctuation_boost = text.count("!")
        if negatives and punctuation_boost:
            raw_score -= punctuation_boost
        elif positives and punctuation_boost:
            raw_score += punctuation_boost

        score = max(min(raw_score / 5, 1.0), -1.0)
        if score >= 0.25:
            label = "positive"
        elif score <= -0.25:
            label = "negative"
        else:
            label = "neutral"

        return SentimentAnalysis(
            label=label,
            score=round(score, 2),
            positive_signals=positives,
            negative_signals=negatives,
        )

    def detect_urgency(
        self,
        message: str,
        *,
        sentiment: SentimentAnalysis | None = None,
        customer_tier: str | None = None,
    ) -> UrgencyAssessment:
        text = (message or "").lower()
        sentiment = sentiment or self.analyze_sentiment(message)

        score = 0
        reasons: list[str] = []
        if sentiment.label == "negative":
            score += 2
            reasons.append("Negative sentiment detected")
        if sentiment.score <= -0.6:
            score += 2
            reasons.append("Strong frustration signal")
        if any(word in text for word in URGENCY_WORDS):
            score += 2
            reasons.append("Explicit urgency language")
        if any(word in text for word in ESCALATION_WORDS):
            score += 3
            reasons.append("Escalation or refund language")
        if text.count("!") >= 2 or text.isupper():
            score += 1
            reasons.append("Elevated emotional intensity")
        if customer_tier and customer_tier.lower() in {
            "vip",
            "enterprise",
            "wholesale",
        }:
            score += 1
            reasons.append("Priority customer tier")

        if score >= 6:
            level = "critical"
            target_response_minutes = 5
        elif score >= 4:
            level = "high"
            target_response_minutes = 10
        elif score >= 2:
            level = "elevated"
            target_response_minutes = 30
        else:
            level = "normal"
            target_response_minutes = 120

        return UrgencyAssessment(
            level=level,
            score=score,
            should_escalate=level in {"critical", "high"},
            reasons=reasons,
            target_response_minutes=target_response_minutes,
        )

    def detect_language(self, text: str) -> LanguageDetection:
        normalized = (text or "").lower()
        tokens = {
            token.strip(".,!?;:'\"()[]{}¿¡")
            for token in normalized.split()
            if token.strip()
        }
        if not tokens:
            return LanguageDetection(code="en", language="English", confidence=0.2)

        best_code = "en"
        best_language = "English"
        best_hits = 0
        for code, (language, hints) in LANGUAGE_HINTS.items():
            hits = len(tokens & hints)
            if hits > best_hits:
                best_code = code
                best_hits = hits
                best_language = language
        if best_hits == 0:
            return LanguageDetection(code="en", language="English", confidence=0.35)
        confidence = min(0.45 + (best_hits * 0.18), 0.98)
        return LanguageDetection(
            code=best_code, language=best_language, confidence=round(confidence, 2)
        )

    def auto_translate(
        self,
        text: str,
        *,
        target_language: str = "en",
        source_language: str | None = None,
    ) -> TranslationResult:
        source = source_language or self.detect_language(text).code
        target = target_language.lower()
        original = text or ""

        if source == target:
            return TranslationResult(
                source_language=source,
                target_language=target,
                original_text=original,
                translated_text=original,
                translated=False,
            )

        mapping = TRANSLATION_DICTIONARY.get((source, target), {})
        translated_tokens = []
        changed = False
        for raw in original.split():
            stripped = raw.strip(".,!?;:'\"()[]{}¿¡").lower()
            translated = mapping.get(stripped, raw)
            if translated != raw:
                changed = True
            translated_tokens.append(translated)

        translated_text = " ".join(translated_tokens)
        if not changed:
            translated_text = original

        return TranslationResult(
            source_language=source,
            target_language=target,
            original_text=original,
            translated_text=translated_text,
            translated=changed,
        )

    def summarize_for_handoff(
        self,
        conversation: Iterable[Mapping[str, object]],
        *,
        max_key_points: int = 4,
    ) -> ConversationSummary:
        messages = list(conversation)
        user_messages = [
            str(m.get("content", ""))
            for m in messages
            if str(m.get("role", "")).lower() == "user"
        ]
        assistant_messages = [
            str(m.get("content", ""))
            for m in messages
            if str(m.get("role", "")).lower() == "assistant"
        ]
        full_user_text = " ".join(user_messages)

        sentiment = self.analyze_sentiment(full_user_text)
        urgency = self.detect_urgency(full_user_text, sentiment=sentiment)

        headline = (
            user_messages[-1][:80] if user_messages else "Customer support hand-off"
        )
        customer_goal = (
            user_messages[0][:120] if user_messages else "Speak with support"
        )

        point_candidates: list[str] = []
        if user_messages:
            point_candidates.append(f"Customer opened with: {user_messages[0][:90]}")
        if len(user_messages) > 1:
            point_candidates.append(f"Latest customer update: {user_messages[-1][:90]}")
        if assistant_messages:
            point_candidates.append(
                f"Bot actions so far: {assistant_messages[-1][:90]}"
            )
        language = self.detect_language(full_user_text)
        if language.code != "en":
            point_candidates.append(f"Customer language detected: {language.language}")

        unresolved: list[str] = []
        lower = full_user_text.lower()
        if any(term in lower for term in {"refund", "return", "cancel"}):
            unresolved.append("Refund or return decision pending")
        if any(term in lower for term in {"where", "tracking", "delivery", "late"}):
            unresolved.append("Shipping or fulfilment update needed")
        if any(term in lower for term in {"discount", "price", "coupon"}):
            unresolved.append("Commercial resolution may be required")
        if not unresolved and user_messages:
            unresolved.append("Confirm the final resolution with the customer")

        action = "Escalate to a live agent immediately."
        if urgency.level == "elevated":
            action = "Prioritize a human review in the next queue window."
        elif urgency.level == "normal":
            action = "Continue with bot support unless the customer requests a human."

        return ConversationSummary(
            headline=headline,
            customer_goal=customer_goal,
            key_points=point_candidates[:max_key_points],
            unresolved_items=unresolved[:max_key_points],
            sentiment=sentiment.label,
            urgency=urgency.level,
            recommended_action=action,
        )


__all__ = [
    "ChatbotAIFeatures",
    "ConversationSummary",
    "LanguageDetection",
    "SentimentAnalysis",
    "TranslationResult",
    "UrgencyAssessment",
]
