"""Report generation for RAG evaluation."""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class EvaluationReport:
    per_item: List[Dict[str, Any]] = field(default_factory=list)

    def add_item(self, item_result: Dict[str, Any]):
        self.per_item.append(item_result)

    def summary(self) -> Dict[str, float]:
        if not self.per_item:
            return {}
        sums = {}
        counts = len(self.per_item)
        # collect numeric keys from all items
        numeric_keys = set()
        for item in self.per_item:
            for k, v in item.items():
                if isinstance(v, (int, float)):
                    numeric_keys.add(k)
        for k in numeric_keys:
            sums[k] = sum(item.get(k, 0.0) for item in self.per_item) / counts
        return sums

    def to_dict(self) -> Dict[str, Any]:
        return {"per_item": self.per_item, "summary": self.summary()}

    def to_markdown(self) -> str:
        s = self.summary()
        lines = ["# Evaluation Report", "", "## Summary", ""]
        for k, v in sorted(s.items()):
            lines.append(f"- {k}: {v:.4f}")
        lines.append("")
        lines.append("## Per item")
        for it in self.per_item:
            lines.append(f"- {it}")
        return "\n".join(lines)
