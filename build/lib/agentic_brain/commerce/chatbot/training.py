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
"""Training and continuous-learning helpers for store-specific chatbots."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Iterable, Mapping


@dataclass(frozen=True)
class FineTuneExample:
    prompt: str
    completion: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FAQEntry:
    question: str
    answer: str
    frequency: int


@dataclass(frozen=True)
class IntentModelArtifact:
    intents: dict[str, list[str]]
    version: str
    training_examples: int

    def predict(self, text: str) -> str:
        normalized = (text or "").lower()
        best_intent = "unknown"
        best_score = 0
        for intent, keywords in self.intents.items():
            score = sum(1 for keyword in keywords if keyword in normalized)
            if score > best_score:
                best_intent = intent
                best_score = score
        return best_intent


@dataclass(frozen=True)
class ContinuousLearningReport:
    accepted_examples: int
    ignored_examples: int
    promoted_intents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ChatbotTrainingPipeline:
    """Build deterministic training artifacts from logs and feedback."""

    def build_fine_tuning_dataset(
        self,
        conversations: Iterable[Mapping[str, object]],
        *,
        store_name: str,
    ) -> list[FineTuneExample]:
        dataset: list[FineTuneExample] = []
        for conversation in conversations:
            messages = list(conversation.get("messages", []))
            for idx, message in enumerate(messages[:-1]):
                if str(message.get("role", "")).lower() != "user":
                    continue
                reply = messages[idx + 1]
                if str(reply.get("role", "")).lower() != "assistant":
                    continue
                dataset.append(
                    FineTuneExample(
                        prompt=str(message.get("content", "")),
                        completion=str(reply.get("content", "")),
                        metadata={
                            "store": store_name,
                            "conversation_id": conversation.get("conversation_id"),
                            "channel": conversation.get("channel", "web"),
                        },
                    )
                )
        return dataset

    def auto_generate_faq(
        self,
        conversations: Iterable[Mapping[str, object]],
        *,
        min_frequency: int = 2,
    ) -> list[FAQEntry]:
        question_counter: Counter[str] = Counter()
        answers: dict[str, str] = {}
        for conversation in conversations:
            last_question = None
            for message in conversation.get("messages", []):
                role = str(message.get("role", "")).lower()
                content = str(message.get("content", "")).strip()
                if not content:
                    continue
                if role == "user":
                    canonical = content.rstrip("?!.").lower()
                    question_counter[canonical] += 1
                    last_question = canonical
                elif (
                    role == "assistant"
                    and last_question
                    and last_question not in answers
                ):
                    answers[last_question] = content

        faqs = [
            FAQEntry(
                question=question,
                answer=answers.get(question, "Answer requires review."),
                frequency=count,
            )
            for question, count in question_counter.items()
            if count >= min_frequency
        ]
        faqs.sort(key=lambda entry: entry.frequency, reverse=True)
        return faqs

    def train_intent_model_from_logs(
        self, logs: Iterable[Mapping[str, object]]
    ) -> IntentModelArtifact:
        keywords_by_intent: defaultdict[str, Counter[str]] = defaultdict(Counter)
        example_count = 0
        for log in logs:
            intent = str(log.get("intent", "unknown")).lower()
            text = str(log.get("text", "")).lower()
            example_count += 1
            for token in text.split():
                cleaned = token.strip(".,!?;:'\"()[]{}")
                if len(cleaned) >= 4:
                    keywords_by_intent[intent][cleaned] += 1

        compact = {
            intent: [keyword for keyword, _ in counter.most_common(8)]
            for intent, counter in keywords_by_intent.items()
        }
        digest = sha256(repr(sorted(compact.items())).encode()).hexdigest()[:12]
        return IntentModelArtifact(
            intents=compact, version=f"intent-{digest}", training_examples=example_count
        )

    def continuous_learning_from_feedback(
        self,
        feedback_events: Iterable[Mapping[str, object]],
        *,
        positive_threshold: int = 4,
    ) -> ContinuousLearningReport:
        accepted = 0
        ignored = 0
        promoted: Counter[str] = Counter()
        notes: list[str] = []

        for event in feedback_events:
            score = int(event.get("score", 0) or 0)
            intent = str(event.get("intent", "unknown")).lower()
            if score >= positive_threshold:
                accepted += 1
                promoted[intent] += 1
            else:
                ignored += 1

        for intent, count in promoted.items():
            notes.append(f"Promote {intent} examples by {count} interactions")

        return ContinuousLearningReport(
            accepted_examples=accepted,
            ignored_examples=ignored,
            promoted_intents=[intent for intent, _ in promoted.most_common()],
            notes=notes,
        )


__all__ = [
    "ChatbotTrainingPipeline",
    "ContinuousLearningReport",
    "FAQEntry",
    "FineTuneExample",
    "IntentModelArtifact",
]
