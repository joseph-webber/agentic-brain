"""Span management for RAGTracer
"""
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional


class Span:
    def __init__(self, name: str, tracer: "RAGTracer" = None, attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.tracer = tracer
        self.attributes: Dict[str, Any] = dict(attributes or {})
        self.start_time = time.perf_counter()
        self.end_time: Optional[float] = None
        self.children: List["Span"] = []
        self.ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_child(self, span: "Span") -> None:
        self.children.append(span)

    def end(self) -> None:
        if not self.ended:
            self.end_time = time.perf_counter()
            self.ended = True
            if self.tracer:
                self.tracer._on_span_end(self)

    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "attributes": self.attributes,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "children": [c.to_dict() for c in self.children],
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.end()
