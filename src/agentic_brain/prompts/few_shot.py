# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Few-shot example helpers for prompt construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class FewShotExample:
    """A single input/output example."""

    input_text: str
    output_text: str
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def format(
        self,
        *,
        input_label: str = "Input",
        output_label: str = "Output",
        explanation_label: str = "Reasoning",
    ) -> str:
        """Format the example for prompt inclusion."""
        parts = [
            f"{input_label}: {self.input_text}",
            f"{output_label}: {self.output_text}",
        ]
        if self.explanation:
            parts.append(f"{explanation_label}: {self.explanation}")
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the example."""
        return {
            "input_text": self.input_text,
            "output_text": self.output_text,
            "explanation": self.explanation,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FewShotExample:
        """Deserialize the example."""
        return cls(
            input_text=str(data["input_text"]),
            output_text=str(data["output_text"]),
            explanation=str(data.get("explanation", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class FewShotCollection:
    """A set of examples with consistent formatting."""

    examples: list[FewShotExample] = field(default_factory=list)
    title: str = "Few-shot examples"

    @classmethod
    def from_pairs(
        cls,
        pairs: Iterable[tuple[str, str]],
        *,
        title: str = "Few-shot examples",
    ) -> FewShotCollection:
        """Create a collection from input/output pairs."""
        return cls(
            examples=[FewShotExample(input_text=inp, output_text=out) for inp, out in pairs],
            title=title,
        )

    def add(self, example: FewShotExample) -> FewShotCollection:
        """Append an example and return self."""
        self.examples.append(example)
        return self

    def extend(self, examples: Iterable[FewShotExample]) -> FewShotCollection:
        """Extend the collection and return self."""
        self.examples.extend(examples)
        return self

    def render(
        self,
        *,
        include_title: bool = True,
        include_explanations: bool = True,
        input_label: str = "Input",
        output_label: str = "Output",
    ) -> str:
        """Render the collection to text."""
        if not self.examples:
            return ""

        rendered = [
            example.format(
                input_label=input_label,
                output_label=output_label,
                explanation_label="Reasoning",
            )
            if include_explanations
            else "\n".join(
                [
                    f"{input_label}: {example.input_text}",
                    f"{output_label}: {example.output_text}",
                ]
            )
            for example in self.examples
        ]
        body = "\n\n".join(
            f"### Example {index + 1}\n{example_text}"
            for index, example_text in enumerate(rendered)
        )
        if include_title:
            return f"## {self.title}\n\n{body}"
        return body

    def to_dict(self) -> dict[str, Any]:
        """Serialize the collection."""
        return {
            "title": self.title,
            "examples": [example.to_dict() for example in self.examples],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FewShotCollection:
        """Deserialize the collection."""
        return cls(
            title=str(data.get("title", "Few-shot examples")),
            examples=[
                FewShotExample.from_dict(example)
                for example in data.get("examples", [])
            ],
        )

