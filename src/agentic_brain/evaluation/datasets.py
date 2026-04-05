"""Dataset utilities for RAG evaluation."""

from dataclasses import dataclass
from typing import List, Optional, Iterable


@dataclass
class Example:
    id: str
    question: str
    gold_answer: str
    gold_context_ids: List[str]
    contexts: Optional[List[str]] = None


class Dataset:
    def __init__(self, examples: Optional[Iterable[Example]] = None):
        self.examples = list(examples or [])

    def add(self, example: Example) -> None:
        self.examples.append(example)

    def __len__(self) -> int:
        return len(self.examples)

    def __iter__(self):
        return iter(self.examples)

    @classmethod
    def from_list(cls, items: Iterable[dict]):
        examples = []
        for it in items:
            ex = Example(
                id=str(it.get("id")),
                question=it.get("question", ""),
                gold_answer=it.get("gold_answer", ""),
                gold_context_ids=list(it.get("gold_context_ids", [])),
                contexts=(
                    list(it.get("contexts", []))
                    if it.get("contexts") is not None
                    else None
                ),
            )
            examples.append(ex)
        return cls(examples)

    def sample(self, n=1):
        from random import sample

        if n > len(self.examples):
            raise ValueError("sample size larger than dataset")
        return sample(self.examples, n)
