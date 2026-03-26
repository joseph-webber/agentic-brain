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

"""Dataset preparation utilities for fine-tuning LLMs.

Supports multiple formats: Alpaca, ShareGPT, OpenAI JSONL, Hugging Face.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DatasetFormat(Enum):
    """Supported dataset formats for fine-tuning."""

    ALPACA = "alpaca"
    SHAREGPT = "sharegpt"
    OPENAI_JSONL = "openai_jsonl"
    HUGGINGFACE = "huggingface"


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # "system", "user", "assistant"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationTurn:
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class Conversation:
    """A multi-turn conversation for fine-tuning."""

    turns: list[ConversationTurn]
    id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Generate ID if not provided."""
        if self.id is None:
            content_hash = hashlib.md5(
                json.dumps([t.to_dict() for t in self.turns]).encode()
            ).hexdigest()[:12]
            self.id = f"conv_{content_hash}"

    def to_alpaca(self) -> dict[str, str]:
        """Convert to Alpaca format (instruction/input/output)."""
        instruction = ""
        input_text = ""
        output = ""

        for turn in self.turns:
            if turn.role == "system":
                instruction = turn.content
            elif turn.role == "user":
                input_text = turn.content
            elif turn.role == "assistant":
                output = turn.content

        return {
            "instruction": instruction or "Complete the following task.",
            "input": input_text,
            "output": output,
        }

    def to_sharegpt(self) -> dict[str, Any]:
        """Convert to ShareGPT format."""
        conversations = []
        for turn in self.turns:
            role_map = {"system": "system", "user": "human", "assistant": "gpt"}
            conversations.append(
                {"from": role_map.get(turn.role, turn.role), "value": turn.content}
            )
        return {"id": self.id, "conversations": conversations}

    def to_openai(self) -> dict[str, Any]:
        """Convert to OpenAI JSONL format."""
        messages = [turn.to_dict() for turn in self.turns]
        return {"messages": messages}

    def total_tokens_estimate(self) -> int:
        """Estimate token count (rough: ~4 chars per token)."""
        total_chars = sum(len(t.content) for t in self.turns)
        return total_chars // 4


@dataclass
class QAPair:
    """A question-answer pair for fine-tuning."""

    question: str
    answer: str
    context: str | None = None
    id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Generate ID if not provided."""
        if self.id is None:
            content_hash = hashlib.md5(
                f"{self.question}{self.answer}".encode()
            ).hexdigest()[:12]
            self.id = f"qa_{content_hash}"

    def to_conversation(self) -> Conversation:
        """Convert to conversation format."""
        turns = []
        if self.context:
            turns.append(ConversationTurn(role="system", content=self.context))
        turns.append(ConversationTurn(role="user", content=self.question))
        turns.append(ConversationTurn(role="assistant", content=self.answer))
        return Conversation(turns=turns, id=self.id, metadata=self.metadata)


@dataclass
class Document:
    """A document for instruction tuning."""

    content: str
    title: str | None = None
    source: str | None = None
    id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Generate ID if not provided."""
        if self.id is None:
            content_hash = hashlib.md5(self.content.encode()).hexdigest()[:12]
            self.id = f"doc_{content_hash}"

    def to_qa_pairs(
        self,
        questions: list[str] | None = None,
    ) -> list[QAPair]:
        """Convert document to Q&A pairs.

        If questions not provided, generates basic questions.
        """
        if questions:
            return [
                QAPair(
                    question=q,
                    answer=self.content,
                    context=f"Document: {self.title}" if self.title else None,
                    metadata={"source": self.source, **self.metadata},
                )
                for q in questions
            ]

        # Generate basic questions from document
        default_questions = [
            (
                f"What is the content of the document titled '{self.title}'?"
                if self.title
                else "What does this document describe?"
            ),
            f"Summarize: {self.title}" if self.title else "Summarize this content.",
        ]

        return [
            QAPair(
                question=q,
                answer=self.content,
                context=f"Source: {self.source}" if self.source else None,
                metadata={"source": self.source, **self.metadata},
            )
            for q in default_questions
        ]


@dataclass
class ValidationResult:
    """Result of dataset validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.is_valid


class DatasetBuilder:
    """Builder for creating fine-tuning datasets.

    Supports multiple input sources and output formats.
    """

    def __init__(self) -> None:
        """Initialize the dataset builder."""
        self._conversations: list[Conversation] = []
        self._metadata: dict[str, Any] = {}
        self._seen_hashes: set[str] = set()

    @property
    def size(self) -> int:
        """Return number of conversations in dataset."""
        return len(self._conversations)

    def from_conversations(
        self,
        conversations: list[dict[str, Any] | Conversation],
    ) -> DatasetBuilder:
        """Add conversations to the dataset.

        Args:
            conversations: List of conversation dicts or Conversation objects

        Returns:
            Self for chaining
        """
        for conv in conversations:
            if isinstance(conv, Conversation):
                self._add_conversation(conv)
            elif isinstance(conv, dict):
                turns = []
                messages = conv.get("messages") or conv.get("turns") or []
                for msg in messages:
                    turns.append(ConversationTurn.from_dict(msg))
                self._add_conversation(
                    Conversation(
                        turns=turns,
                        id=conv.get("id"),
                        metadata=conv.get("metadata", {}),
                    )
                )
        return self

    def from_qa_pairs(
        self,
        qa_pairs: list[dict[str, Any] | QAPair],
    ) -> DatasetBuilder:
        """Add Q&A pairs to the dataset.

        Args:
            qa_pairs: List of Q&A pair dicts or QAPair objects

        Returns:
            Self for chaining
        """
        for qa in qa_pairs:
            if isinstance(qa, QAPair):
                self._add_conversation(qa.to_conversation())
            elif isinstance(qa, dict):
                pair = QAPair(
                    question=qa["question"],
                    answer=qa["answer"],
                    context=qa.get("context"),
                    id=qa.get("id"),
                    metadata=qa.get("metadata", {}),
                )
                self._add_conversation(pair.to_conversation())
        return self

    def from_documents(
        self,
        documents: list[dict[str, Any] | Document],
        questions_per_doc: list[list[str]] | None = None,
    ) -> DatasetBuilder:
        """Add documents to the dataset as Q&A pairs.

        Args:
            documents: List of document dicts or Document objects
            questions_per_doc: Optional list of questions for each document

        Returns:
            Self for chaining
        """
        for i, doc in enumerate(documents):
            if isinstance(doc, Document):
                doc_obj = doc
            else:
                doc_obj = Document(
                    content=doc["content"],
                    title=doc.get("title"),
                    source=doc.get("source"),
                    id=doc.get("id"),
                    metadata=doc.get("metadata", {}),
                )

            questions = (
                questions_per_doc[i]
                if questions_per_doc and i < len(questions_per_doc)
                else None
            )
            qa_pairs = doc_obj.to_qa_pairs(questions)
            for qa in qa_pairs:
                self._add_conversation(qa.to_conversation())
        return self

    def from_jsonl(self, path: str | Path) -> DatasetBuilder:
        """Load conversations from JSONL file.

        Args:
            path: Path to JSONL file

        Returns:
            Self for chaining
        """
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            conversations = [json.loads(line) for line in f if line.strip()]
        return self.from_conversations(conversations)

    def _add_conversation(self, conv: Conversation) -> bool:
        """Add conversation if not duplicate.

        Returns:
            True if added, False if duplicate
        """
        content_hash = hashlib.md5(
            json.dumps([t.to_dict() for t in conv.turns]).encode()
        ).hexdigest()

        if content_hash in self._seen_hashes:
            return False

        self._seen_hashes.add(content_hash)
        self._conversations.append(conv)
        return True

    def dedupe(self) -> int:
        """Remove duplicate conversations.

        Returns:
            Number of duplicates removed
        """
        original_count = len(self._conversations)
        unique_convs: list[Conversation] = []
        seen: set[str] = set()

        for conv in self._conversations:
            content_hash = hashlib.md5(
                json.dumps([t.to_dict() for t in conv.turns]).encode()
            ).hexdigest()

            if content_hash not in seen:
                seen.add(content_hash)
                unique_convs.append(conv)

        self._conversations = unique_convs
        self._seen_hashes = seen
        return original_count - len(unique_convs)

    def filter_by_quality(
        self,
        min_turns: int = 2,
        max_turns: int | None = None,
        min_tokens: int = 10,
        max_tokens: int | None = None,
        require_assistant: bool = True,
    ) -> int:
        """Filter conversations by quality criteria.

        Args:
            min_turns: Minimum number of turns
            max_turns: Maximum number of turns (None for no limit)
            min_tokens: Minimum estimated tokens
            max_tokens: Maximum estimated tokens (None for no limit)
            require_assistant: Require at least one assistant turn

        Returns:
            Number of conversations removed
        """
        original_count = len(self._conversations)
        filtered: list[Conversation] = []

        for conv in self._conversations:
            # Check turn count
            if len(conv.turns) < min_turns:
                continue
            if max_turns and len(conv.turns) > max_turns:
                continue

            # Check token count
            tokens = conv.total_tokens_estimate()
            if tokens < min_tokens:
                continue
            if max_tokens and tokens > max_tokens:
                continue

            # Check for assistant turn
            if require_assistant:
                has_assistant = any(t.role == "assistant" for t in conv.turns)
                if not has_assistant:
                    continue

            filtered.append(conv)

        self._conversations = filtered
        return original_count - len(filtered)

    def filter_by_content(
        self,
        exclude_patterns: list[str] | None = None,
        require_patterns: list[str] | None = None,
    ) -> int:
        """Filter conversations by content patterns.

        Args:
            exclude_patterns: Regex patterns to exclude
            require_patterns: Regex patterns that must be present

        Returns:
            Number of conversations removed
        """
        original_count = len(self._conversations)
        filtered: list[Conversation] = []

        exclude_re = [re.compile(p) for p in (exclude_patterns or [])]
        require_re = [re.compile(p) for p in (require_patterns or [])]

        for conv in self._conversations:
            full_text = " ".join(t.content for t in conv.turns)

            # Check exclusions
            excluded = False
            for pattern in exclude_re:
                if pattern.search(full_text):
                    excluded = True
                    break

            if excluded:
                continue

            # Check requirements
            if require_re:
                has_all = all(p.search(full_text) for p in require_re)
                if not has_all:
                    continue

            filtered.append(conv)

        self._conversations = filtered
        return original_count - len(filtered)

    def validate(self) -> ValidationResult:
        """Validate the dataset.

        Returns:
            ValidationResult with errors, warnings, and stats
        """
        errors: list[str] = []
        warnings: list[str] = []
        stats: dict[str, Any] = {
            "total_conversations": len(self._conversations),
            "total_turns": sum(len(c.turns) for c in self._conversations),
            "total_tokens_estimate": sum(
                c.total_tokens_estimate() for c in self._conversations
            ),
            "avg_turns_per_conversation": 0.0,
            "avg_tokens_per_conversation": 0.0,
            "role_distribution": {"system": 0, "user": 0, "assistant": 0},
        }

        if not self._conversations:
            errors.append("Dataset is empty")
            return ValidationResult(is_valid=False, errors=errors, stats=stats)

        # Calculate averages
        stats["avg_turns_per_conversation"] = stats["total_turns"] / len(
            self._conversations
        )
        stats["avg_tokens_per_conversation"] = stats["total_tokens_estimate"] / len(
            self._conversations
        )

        # Count roles
        for conv in self._conversations:
            for turn in conv.turns:
                if turn.role in stats["role_distribution"]:
                    stats["role_distribution"][turn.role] += 1

        # Validation checks
        no_assistant = sum(
            1
            for c in self._conversations
            if not any(t.role == "assistant" for t in c.turns)
        )
        if no_assistant > 0:
            warnings.append(f"{no_assistant} conversations have no assistant response")

        empty_turns = sum(
            1 for c in self._conversations for t in c.turns if not t.content.strip()
        )
        if empty_turns > 0:
            warnings.append(f"{empty_turns} turns have empty content")

        # Check for very short conversations
        short_convs = sum(1 for c in self._conversations if len(c.turns) < 2)
        if short_convs > 0:
            warnings.append(f"{short_convs} conversations have fewer than 2 turns")

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid, errors=errors, warnings=warnings, stats=stats
        )

    def split(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        shuffle: bool = True,
        seed: int | None = None,
    ) -> tuple[DatasetBuilder, DatasetBuilder, DatasetBuilder]:
        """Split dataset into train/val/test sets.

        Args:
            train_ratio: Fraction for training
            val_ratio: Fraction for validation
            test_ratio: Fraction for testing
            shuffle: Whether to shuffle before splitting
            seed: Random seed for reproducibility

        Returns:
            Tuple of (train, val, test) DatasetBuilder instances
        """
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
            raise ValueError("Ratios must sum to 1.0")

        convs = list(self._conversations)

        if shuffle:
            import random

            if seed is not None:
                random.seed(seed)
            random.shuffle(convs)

        n = len(convs)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)

        train_builder = DatasetBuilder()
        train_builder._conversations = convs[:train_end]

        val_builder = DatasetBuilder()
        val_builder._conversations = convs[train_end:val_end]

        test_builder = DatasetBuilder()
        test_builder._conversations = convs[val_end:]

        return train_builder, val_builder, test_builder

    def iterate(
        self,
        format: DatasetFormat = DatasetFormat.OPENAI_JSONL,
    ) -> Iterator[dict[str, Any]]:
        """Iterate over conversations in specified format.

        Args:
            format: Output format

        Yields:
            Conversation dictionaries in requested format
        """
        for conv in self._conversations:
            if format == DatasetFormat.ALPACA:
                yield conv.to_alpaca()
            elif format == DatasetFormat.SHAREGPT:
                yield conv.to_sharegpt()
            elif format == DatasetFormat.OPENAI_JSONL:
                yield conv.to_openai()
            elif format == DatasetFormat.HUGGINGFACE:
                yield {
                    "id": conv.id,
                    "messages": [t.to_dict() for t in conv.turns],
                    "metadata": conv.metadata,
                }

    def to_jsonl(
        self,
        path: str | Path,
        format: DatasetFormat = DatasetFormat.OPENAI_JSONL,
    ) -> int:
        """Export dataset to JSONL file.

        Args:
            path: Output path
            format: Output format

        Returns:
            Number of records written
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with path.open("w", encoding="utf-8") as f:
            for record in self.iterate(format):
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        return count

    def to_parquet(
        self,
        path: str | Path,
        format: DatasetFormat = DatasetFormat.OPENAI_JSONL,
    ) -> int:
        """Export dataset to Parquet file.

        Args:
            path: Output path
            format: Output format

        Returns:
            Number of records written

        Raises:
            ImportError: If pyarrow/pandas not installed
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for parquet export. "
                "Install with: pip install pandas pyarrow"
            )

        records = list(self.iterate(format))
        df = pd.DataFrame(records)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

        return len(records)

    def to_hf_dataset(
        self,
        format: DatasetFormat = DatasetFormat.HUGGINGFACE,
    ) -> Any:
        """Export to Hugging Face Dataset object.

        Args:
            format: Output format

        Returns:
            datasets.Dataset object

        Raises:
            ImportError: If datasets library not installed
        """
        try:
            from datasets import Dataset
        except ImportError:
            raise ImportError(
                "datasets library is required. " "Install with: pip install datasets"
            )

        records = list(self.iterate(format))
        return Dataset.from_list(records)

    def to_list(
        self,
        format: DatasetFormat = DatasetFormat.OPENAI_JSONL,
    ) -> list[dict[str, Any]]:
        """Export dataset as a list of records.

        Args:
            format: Output format

        Returns:
            List of conversation dictionaries
        """
        return list(self.iterate(format))
