"""Lightweight Langfuse integration shim.
This module does not depend on the official Langfuse SDK to keep tests simple.
"""

from __future__ import annotations

from typing import Any


class LangfuseClient:
    def __init__(self, api_key: str = None, project: str = None):
        self.api_key = api_key
        self.project = project
        self.events = []

    def send_event(self, span) -> None:
        # collect a lightweight event representation
        try:
            ev = {
                "name": span.name,
                "duration": span.duration,
                "attributes": span.attributes,
            }
            self.events.append(ev)
        except Exception:
            # don't let failure break tracing
            pass
