"""Arize Phoenix (Phoenix) lightweight shim.
No external dependency required for tests — collects events in memory.
"""

from __future__ import annotations

from typing import Any


class PhoenixClient:
    def __init__(self, api_key: str = None, dataset: str = None):
        self.api_key = api_key
        self.dataset = dataset
        self.events = []

    def send_event(self, span) -> None:
        try:
            ev = {
                "name": span.name,
                "duration": span.duration,
                "attributes": span.attributes,
            }
            self.events.append(ev)
        except Exception:
            pass
