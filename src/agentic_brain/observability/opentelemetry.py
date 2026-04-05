"""OpenTelemetry exporter shim.
If opentelemetry is available, the real exporter could be implemented here. For testing and safety
we provide a minimal shim that converts spans to a serializable form.
"""

from __future__ import annotations
from typing import Any, Dict


class OTELShim:
    def __init__(self):
        self.exported = []

    def export_span(self, span) -> None:
        try:
            data: Dict[str, Any] = {
                "name": span.name,
                "duration": span.duration,
                "attributes": span.attributes,
            }
            self.exported.append(data)
        except Exception:
            pass
