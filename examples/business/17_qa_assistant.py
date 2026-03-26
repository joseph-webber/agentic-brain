#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 17: Store QA & Quality Control Chatbot

An AI assistant for quality assurance tasks:
- Pre-shipment checks ("QA check order #12345")
- Product inspections ("Inspect batch from TechSupply Co")
- Defect logging ("Found damaged packaging on 3 units")
- Customer complaint triage ("Customer says product broken")
- Return processing ("Process return RMA-001")

This example shows how to build a QA workflow assistant
that guides staff through standardized quality checks.

Key patterns demonstrated:
- Guided workflows with step-by-step checks
- Defect tracking and categorization
- Integration with order management
- Photo/evidence capture prompts

Usage:
    python examples/17_qa_assistant.py

Requirements:
    pip install agentic-brain
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import json

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class DefectSeverity(Enum):
    """Defect severity levels."""

    COSMETIC = "cosmetic"  # Minor, sellable at discount
    FUNCTIONAL = "functional"  # Affects use, not sellable
    SAFETY = "safety"  # Dangerous, must be destroyed
    PACKAGING = "packaging"  # Box/packaging only, repackage


class DefectType(Enum):
    """Common defect categories."""

    DAMAGED_BOX = "damaged_box"
    MISSING_PARTS = "missing_parts"
    SCRATCHED = "scratched"
    DENTED = "dented"
    NOT_WORKING = "not_working"
    WRONG_ITEM = "wrong_item"
    EXPIRED = "expired"
    COUNTERFEIT = "counterfeit"


class QAResult(Enum):
    """QA check result."""

    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"  # Pass with notes


class ReturnReason(Enum):
    """Customer return reasons."""

    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    CHANGED_MIND = "changed_mind"
    NOT_AS_DESCRIBED = "not_as_described"
    DAMAGED_IN_SHIPPING = "damaged_shipping"


@dataclass
class Defect:
    """A recorded defect."""

    id: str
    defect_type: DefectType
    severity: DefectSeverity
    description: str
    sku: str
    batch_id: str = ""
    photo_path: str = ""
    reported_by: str = ""
    reported_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: str = ""


@dataclass
class QACheck:
    """A QA inspection record."""

    id: str
    order_id: str
    items_checked: int
    items_passed: int
    items_failed: int
    defects: list[Defect] = field(default_factory=list)
    checked_by: str = ""
    checked_at: datetime = field(default_factory=datetime.now)
    result: QAResult = QAResult.PASS
    notes: str = ""

    @property
    def pass_rate(self) -> float:
        if self.items_checked == 0:
            return 0.0
        return (self.items_passed / self.items_checked) * 100


@dataclass
class ReturnRequest:
    """Customer return/RMA request."""

    rma_id: str
    order_id: str
    customer_email: str
    reason: ReturnReason
    customer_description: str
    items: list[tuple[str, int]]  # (sku, quantity)
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, received, inspected, resolved
    inspection_notes: str = ""
    resolution: str = ""  # refund, replacement, rejected


# ══════════════════════════════════════════════════════════════════════════════
# QA CHECKLISTS
# ══════════════════════════════════════════════════════════════════════════════

# Product-specific QA checklists
QA_CHECKLISTS = {
    "electronics": [
        {
            "step": "Visual Inspection",
            "checks": [
                "No scratches or dents on body",
                "Screen/display undamaged",
                "Buttons click properly",
                "Accessories present (charger, tools, manual)",
            ],
        },
        {
            "step": "Functional Test",
            "checks": [
                "Powers on correctly",
                "Heats to temperature",
                "Battery holds charge indicator",
                "No unusual smells or sounds",
            ],
        },
        {
            "step": "Packaging",
            "checks": [
                "Box undamaged",
                "Seals intact",
                "Correct item for order",
                "Warranty card included",
            ],
        },
    ],
    "cable": [
        {
            "step": "Visual Inspection",
            "checks": [
                "Connectors undamaged",
                "Cable jacket intact",
                "Correct length",
                "Labeling correct",
            ],
        },
        {
            "step": "Functional Test",
            "checks": [
                "Continuity test passed",
                "No intermittent connection",
            ],
        },
        {
            "step": "Packaging",
            "checks": [
                "Coiled properly",
                "Cable tie/velcro present",
            ],
        },
    ],
    "accessory": [
        {
            "step": "Visual Inspection",
            "checks": [
                "No visible damage",
                "Correct item",
                "Complete set if applicable",
            ],
        },
        {
            "step": "Packaging",
            "checks": [
                "Packaging intact",
                "Correct labeling",
            ],
        },
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATED DATABASE
# ══════════════════════════════════════════════════════════════════════════════


class QADB:
    """Simulated QA database."""

    def __init__(self):
        self.defects: dict[str, Defect] = {}
        self.qa_checks: dict[str, QACheck] = {}
        self.returns: dict[str, ReturnRequest] = {}
        self.defect_counter = 0
        self.qa_counter = 0

        # Sample data
        self.orders = {
            "12345": {
                "items": [("KB-ERGO1", 2), ("UMON-HUB4", 5)],
                "customer": "john@example.com",
            },
            "12346": {"items": [("MON-27HD", 1)], "customer": "jane@example.com"},
        }

        self.product_categories = {
            "KB-": "electronics",
            "MON-": "electronics",
            "CABLE-": "cable",
        }

    def get_checklist(self, sku: str) -> list[dict]:
        """Get QA checklist for product type."""
        for prefix, category in self.product_categories.items():
            if sku.startswith(prefix):
                return QA_CHECKLISTS.get(category, QA_CHECKLISTS["accessory"])
        return QA_CHECKLISTS["accessory"]

    def create_defect(
        self,
        defect_type: DefectType,
        severity: DefectSeverity,
        description: str,
        sku: str,
        batch_id: str = "",
    ) -> Defect:
        """Record a new defect."""
        self.defect_counter += 1
        defect = Defect(
            id=f"DEF-{self.defect_counter:04d}",
            defect_type=defect_type,
            severity=severity,
            description=description,
            sku=sku,
            batch_id=batch_id,
        )
        self.defects[defect.id] = defect
        return defect

    def create_qa_check(self, order_id: str) -> QACheck:
        """Create a new QA check record."""
        self.qa_counter += 1
        check = QACheck(
            id=f"QA-{self.qa_counter:04d}",
            order_id=order_id,
            items_checked=0,
            items_passed=0,
            items_failed=0,
        )
        self.qa_checks[check.id] = check
        return check

    def get_recent_defects(self, limit: int = 10) -> list[Defect]:
        """Get recent defects."""
        defects = sorted(
            self.defects.values(), key=lambda d: d.reported_at, reverse=True
        )
        return defects[:limit]

    def get_defect_stats(self) -> dict:
        """Get defect statistics."""
        stats = {"total": len(self.defects), "by_type": {}, "by_severity": {}}
        for defect in self.defects.values():
            stats["by_type"][defect.defect_type.value] = (
                stats["by_type"].get(defect.defect_type.value, 0) + 1
            )
            stats["by_severity"][defect.severity.value] = (
                stats["by_severity"].get(defect.severity.value, 0) + 1
            )
        return stats


# ══════════════════════════════════════════════════════════════════════════════
# QA ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class QAAssistant:
    """
    AI-powered QA assistant for quality control workflows.
    """

    def __init__(self, db: QADB):
        self.db = db
        self.current_check: Optional[QACheck] = None
        self.current_checklist: list[dict] = []
        self.current_step: int = 0
        self.current_check_index: int = 0
        self.current_sku: str = ""

    async def process_message(self, message: str) -> str:
        """Process user message and return response."""
        message_lower = message.lower().strip()

        # QA check commands
        if "qa check" in message_lower or "inspect order" in message_lower:
            return await self._start_qa_check(message)

        # Continue QA workflow
        if self.current_check:
            if any(
                word in message_lower for word in ["pass", "ok", "good", "yes", "✓"]
            ):
                return await self._record_check_pass()
            elif any(
                word in message_lower
                for word in ["fail", "no", "defect", "issue", "problem"]
            ):
                return await self._record_check_fail(message)
            elif "skip" in message_lower:
                return await self._skip_check()
            elif "done" in message_lower or "complete" in message_lower:
                return await self._complete_qa_check()

        # Defect logging
        if (
            "defect" in message_lower
            or "damaged" in message_lower
            or "broken" in message_lower
        ):
            return await self._log_defect(message)

        # Customer complaint
        if "complaint" in message_lower or "customer says" in message_lower:
            return await self._handle_complaint(message)

        # Return processing
        if "return" in message_lower or "rma" in message_lower:
            return await self._process_return(message)

        # Defect stats
        if "stats" in message_lower or "report" in message_lower:
            return await self._show_stats()

        return self._help_message()

    async def _start_qa_check(self, message: str) -> str:
        """Start a QA check on an order."""
        import re

        match = re.search(r"#?(\d{4,})", message)
        if not match:
            return "Which order? Say 'QA check order #12345'"

        order_id = match.group(1)
        if order_id not in self.db.orders:
            return f"Order #{order_id} not found."

        order = self.db.orders[order_id]
        self.current_check = self.db.create_qa_check(order_id)

        # Start with first item
        first_sku = order["items"][0][0]
        self.current_sku = first_sku
        self.current_checklist = self.db.get_checklist(first_sku)
        self.current_step = 0
        self.current_check_index = 0

        return self._format_check_prompt()

    def _format_check_prompt(self) -> str:
        """Format the current check prompt."""
        if not self.current_checklist:
            return "No checklist available."

        step = self.current_checklist[self.current_step]
        check = step["checks"][self.current_check_index]

        progress = f"[{self.current_step + 1}/{len(self.current_checklist)}] "
        return (
            f"📋 {self.current_sku} - {step['step']}\n\n"
            f"{progress}{check}\n\n"
            f"Say 'pass' ✓ or 'fail' ✗ (describe issue)"
        )

    async def _record_check_pass(self) -> str:
        """Record a passing check."""
        if not self.current_check:
            return "No active QA check."

        # Move to next check
        return await self._next_check("✓ Passed")

    async def _record_check_fail(self, message: str) -> str:
        """Record a failing check with defect."""
        if not self.current_check:
            return "No active QA check."

        # Extract defect description
        description = message.replace("fail", "").replace("defect", "").strip()
        if not description:
            description = "Failed QA check"

        # Determine severity from keywords
        severity = DefectSeverity.COSMETIC
        if any(word in message.lower() for word in ["broken", "not working", "dead"]):
            severity = DefectSeverity.FUNCTIONAL
        elif any(word in message.lower() for word in ["dangerous", "safety", "hazard"]):
            severity = DefectSeverity.SAFETY
        elif any(word in message.lower() for word in ["box", "packaging", "dent"]):
            severity = DefectSeverity.PACKAGING

        # Create defect record
        defect = self.db.create_defect(
            defect_type=DefectType.NOT_WORKING,
            severity=severity,
            description=description,
            sku=self.current_sku,
        )
        self.current_check.defects.append(defect)
        self.current_check.items_failed += 1

        return await self._next_check(f"❌ Defect logged: {defect.id}")

    async def _skip_check(self) -> str:
        """Skip current check."""
        return await self._next_check("⏭️ Skipped")

    async def _next_check(self, status: str) -> str:
        """Move to the next check in the list."""
        step = self.current_checklist[self.current_step]

        self.current_check_index += 1

        # If more checks in current step
        if self.current_check_index < len(step["checks"]):
            return f"{status}\n\n{self._format_check_prompt()}"

        # Move to next step
        self.current_step += 1
        self.current_check_index = 0

        # If more steps
        if self.current_step < len(self.current_checklist):
            return f"{status}\n\n{self._format_check_prompt()}"

        # Checklist complete for this item
        self.current_check.items_checked += 1
        if not self.current_check.defects:
            self.current_check.items_passed += 1

        return (
            f"{status}\n\n"
            f"✅ {self.current_sku} inspection complete!\n"
            f"Say 'done' to finish or continue with next item."
        )

    async def _complete_qa_check(self) -> str:
        """Complete the QA check and generate summary."""
        if not self.current_check:
            return "No active QA check."

        check = self.current_check

        # Determine overall result
        if check.items_failed == 0:
            check.result = QAResult.PASS
            result_emoji = "✅"
        elif check.items_failed < check.items_checked:
            check.result = QAResult.CONDITIONAL
            result_emoji = "⚠️"
        else:
            check.result = QAResult.FAIL
            result_emoji = "❌"

        summary = (
            f"{'=' * 40}\n"
            f"📋 QA CHECK COMPLETE: {check.id}\n"
            f"{'=' * 40}\n\n"
            f"Order: #{check.order_id}\n"
            f"Result: {result_emoji} {check.result.value.upper()}\n\n"
            f"Items checked: {check.items_checked}\n"
            f"  ✓ Passed: {check.items_passed}\n"
            f"  ✗ Failed: {check.items_failed}\n"
        )

        if check.defects:
            summary += f"\nDefects found: {len(check.defects)}\n"
            for defect in check.defects:
                summary += f"  • {defect.id}: {defect.description}\n"

        self.current_check = None
        self.current_checklist = []

        return summary

    async def _log_defect(self, message: str) -> str:
        """Log a defect directly."""
        # Parse defect from message
        quantity_match = re.search(r"(\d+)\s*(units?)?", message)
        quantity = int(quantity_match.group(1)) if quantity_match else 1

        severity = DefectSeverity.COSMETIC
        if "packaging" in message.lower() or "box" in message.lower():
            severity = DefectSeverity.PACKAGING
        elif "not working" in message.lower() or "broken" in message.lower():
            severity = DefectSeverity.FUNCTIONAL

        defect = self.db.create_defect(
            defect_type=(
                DefectType.DAMAGED_BOX
                if severity == DefectSeverity.PACKAGING
                else DefectType.NOT_WORKING
            ),
            severity=severity,
            description=message,
            sku="UNKNOWN",
        )

        return (
            f"🔴 Defect logged: {defect.id}\n"
            f"Severity: {severity.value}\n"
            f"Quantity: {quantity}\n\n"
            f"Add photo? Say 'photo added' or continue."
        )

    async def _handle_complaint(self, message: str) -> str:
        """Triage a customer complaint."""
        # Simple keyword-based triage
        if any(
            word in message.lower() for word in ["dangerous", "injury", "hurt", "fire"]
        ):
            priority = "🔴 URGENT - SAFETY"
            action = "Stop selling this batch. Contact customer immediately. File incident report."
        elif any(word in message.lower() for word in ["broken", "not working", "dead"]):
            priority = "🟠 HIGH - DEFECTIVE"
            action = "Offer replacement or refund. Check batch for similar issues."
        elif any(word in message.lower() for word in ["wrong item", "missing"]):
            priority = "🟡 MEDIUM - FULFILLMENT ERROR"
            action = "Send correct item. Review pick/pack process."
        else:
            priority = "🟢 LOW - GENERAL"
            action = "Respond within 24 hours. Standard resolution."

        return (
            f"📞 COMPLAINT TRIAGE\n"
            f"{'=' * 40}\n\n"
            f"Priority: {priority}\n\n"
            f"Recommended action:\n{action}\n\n"
            f"Create RMA? Say 'process return RMA-XXX'"
        )

    async def _process_return(self, message: str) -> str:
        """Process a return request."""
        import re

        rma_match = re.search(r"RMA[- ]?(\d+)", message, re.IGNORECASE)

        if rma_match:
            rma_id = f"RMA-{rma_match.group(1)}"
            return (
                f"📦 Return {rma_id}\n"
                f"{'=' * 40}\n\n"
                f"Return inspection checklist:\n"
                f"□ Package received in good condition\n"
                f"□ All items present\n"
                f"□ Item matches RMA description\n"
                f"□ Defect verified (if defective return)\n"
                f"□ Photos taken\n\n"
                f"Say 'refund approved' or 'replacement needed' or 'return rejected'"
            )

        return "Create RMA: Say 'process return RMA-001' with RMA number"

    async def _show_stats(self) -> str:
        """Show defect statistics."""
        stats = self.db.get_defect_stats()

        lines = [
            "📊 DEFECT STATISTICS",
            "=" * 40,
            f"\nTotal defects: {stats['total']}",
            "\nBy severity:",
        ]

        for severity, count in stats.get("by_severity", {}).items():
            lines.append(f"  • {severity}: {count}")

        lines.append("\nBy type:")
        for defect_type, count in stats.get("by_type", {}).items():
            lines.append(f"  • {defect_type}: {count}")

        return "\n".join(lines)

    def _help_message(self) -> str:
        """Return help text."""
        return """🔍 QA Assistant - I can help with:

• "QA check order #12345" - Start inspection
• "Defect: damaged packaging on 3 units"
• "Customer says product not working"
• "Process return RMA-001"
• "Show stats"

Just ask naturally!"""


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    """Demo the QA assistant."""
    print("=" * 60)
    print("🔍 QA ASSISTANT")
    print("=" * 60)
    print()

    db = QADB()
    assistant = QAAssistant(db)

    # Demo conversations
    demo_messages = [
        "QA check order #12345",
        "pass",
        "pass",
        "fail - screen has a scratch",
        "pass",
        "done",
        "Customer says product not working",
        "Show stats",
    ]

    for message in demo_messages:
        print(f"👤 {message}")
        response = await assistant.process_message(message)
        print(f"🤖 {response}")
        print("-" * 40)


if __name__ == "__main__":
    import re  # Needed for _log_defect

    asyncio.run(main())
