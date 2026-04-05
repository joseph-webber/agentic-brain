# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""Query decomposition helpers for multi-step routing."""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class QueryDecomposition:
    """Result of breaking a query into smaller parts."""

    original_query: str
    parts: tuple[str, ...]
    connectors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_multi_step(self) -> bool:
        return len(self.parts) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "parts": list(self.parts),
            "connectors": list(self.connectors),
            "is_multi_step": self.is_multi_step,
            "metadata": dict(self.metadata),
        }


class QueryDecomposer:
    """Split a query into safe, actionable sub-queries."""

    CONNECTOR_PATTERNS = (
        (re.compile(r"\b(?:and also|as well as|along with|plus)\b", re.I), "coordination"),
        (re.compile(r"\b(?:then|after that|next)\b", re.I), "sequence"),
        (re.compile(r"[;\n]+"), "delimiter"),
    )

    def decompose(self, query: str) -> QueryDecomposition:
        normalized = " ".join(query.strip().split())
        if not normalized:
            return QueryDecomposition(query, (), metadata={"word_count": 0})

        parts, connectors = self._split(normalized)
        parts = tuple(self._cleanup_part(part) for part in parts if self._cleanup_part(part))
        if not parts:
            parts = (normalized,)
        metadata = {
            "word_count": len(re.findall(r"[a-z0-9]+", normalized.lower())),
            "part_count": len(parts),
        }
        return QueryDecomposition(
            original_query=query,
            parts=parts,
            connectors=tuple(connectors),
            metadata=metadata,
        )

    def _split(self, query: str) -> tuple[list[str], list[str]]:
        if self._should_keep_single(query):
            return [query], []

        current = [query]
        connectors: list[str] = []
        for pattern, label in self.CONNECTOR_PATTERNS:
            next_parts: list[str] = []
            changed = False
            for chunk in current:
                segments = [segment.strip() for segment in pattern.split(chunk) if segment and segment.strip()]
                if len(segments) > 1:
                    next_parts.extend(segments)
                    connectors.extend([label] * (len(segments) - 1))
                    changed = True
                else:
                    next_parts.append(chunk)
            current = next_parts
            if changed:
                continue

        if len(current) == 1 and " and " in query.lower() and not self._looks_like_compare(query):
            current = [segment.strip() for segment in re.split(r"\band\b", query, flags=re.I) if segment and segment.strip()]
            if len(current) > 1:
                connectors.extend(["conjunction"] * (len(current) - 1))

        if len(current) == 1:
            return current, connectors

        if self._looks_like_compare(query):
            return [query], []

        return current, connectors

    def _cleanup_part(self, part: str) -> str:
        cleaned = part.strip(" ,.;:")
        cleaned = re.sub(r"^(?:and|then|also|plus)\s+", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _should_keep_single(self, query: str) -> bool:
        word_count = len(re.findall(r"[a-z0-9]+", query.lower()))
        has_conjunction = " and " in query.lower() and not self._looks_like_compare(query)
        return word_count <= 5 and not has_conjunction and ";" not in query and "\n" not in query

    def _looks_like_compare(self, query: str) -> bool:
        lowered = query.lower()
        return any(
            phrase in lowered
            for phrase in (
                "compare",
                "difference between",
                "versus",
                "vs",
            )
        )
