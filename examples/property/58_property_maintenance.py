#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 58: Maintenance & Trades Coordinator

A system for managing property maintenance workflows, tradesperson
coordination, and work order management in property management.

Features:
- Work order management
- Tradesperson assignment
- Quote comparison
- Job status tracking
- Before/after photo documentation
- Invoice processing
- Preferred supplier management
- Emergency job escalation

Australian-specific:
- Licensed trade requirements
- WorkCover compliance
- ABN verification
- State licensing boards

Usage:
    python examples/58_property_maintenance.py

Requirements:
    pip install agentic-brain

Author: agentic-brain
License: MIT
"""

import asyncio
import random
import string
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# ENUMS AND CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════


class WorkOrderStatus(Enum):
    """Status of a work order."""

    NEW = "New"
    QUOTING = "Awaiting Quotes"
    QUOTE_RECEIVED = "Quotes Received"
    PENDING_APPROVAL = "Pending Approval"
    APPROVED = "Approved"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    INVOICED = "Invoiced"
    PAID = "Paid"
    CANCELLED = "Cancelled"
    ON_HOLD = "On Hold"


class JobPriority(Enum):
    """Priority levels for maintenance jobs."""

    EMERGENCY = "Emergency"  # 4 hours - safety risk
    URGENT = "Urgent"  # 24 hours - essential service
    HIGH = "High"  # 48 hours
    NORMAL = "Normal"  # 7 days
    LOW = "Low"  # 14+ days - cosmetic/minor


class TradeCategory(Enum):
    """Categories of trades."""

    PLUMBING = "Plumbing"
    ELECTRICAL = "Electrical"
    HVAC = "HVAC/Air Conditioning"
    LOCKSMITH = "Locksmith"
    APPLIANCE = "Appliance Repair"
    ROOFING = "Roofing"
    CARPENTRY = "Carpentry"
    PAINTING = "Painting"
    FLOORING = "Flooring"
    GLAZING = "Glazing"
    PEST_CONTROL = "Pest Control"
    CLEANING = "Cleaning"
    GARDENING = "Gardening"
    POOL = "Pool Maintenance"
    FENCING = "Fencing"
    GENERAL = "General Handyman"


class SupplierStatus(Enum):
    """Status of a supplier/tradesperson."""

    ACTIVE = "Active"
    INACTIVE = "Inactive"
    SUSPENDED = "Suspended"
    PENDING_VERIFICATION = "Pending Verification"


class InvoiceStatus(Enum):
    """Status of invoices."""

    RECEIVED = "Received"
    UNDER_REVIEW = "Under Review"
    APPROVED = "Approved"
    QUEUED_FOR_PAYMENT = "Queued for Payment"
    PAID = "Paid"
    DISPUTED = "Disputed"


class AustralianState(Enum):
    """Australian states for licensing."""

    NSW = "New South Wales"
    VIC = "Victoria"
    QLD = "Queensland"
    SA = "South Australia"
    WA = "Western Australia"
    TAS = "Tasmania"
    NT = "Northern Territory"
    ACT = "Australian Capital Territory"


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Tradesperson:
    """A tradesperson/supplier in the system."""

    supplier_id: str
    business_name: str
    contact_name: str
    phone: str
    email: str
    abn: str

    # Trade info
    trade_categories: list[TradeCategory]
    service_areas: list[str]  # Postcodes or suburb names

    # Compliance
    status: SupplierStatus = SupplierStatus.ACTIVE
    license_number: Optional[str] = None
    license_state: Optional[AustralianState] = None
    license_expiry: Optional[date] = None
    insurance_expiry: Optional[date] = None
    workcover_verified: bool = False

    # Performance
    rating: float = 5.0  # Out of 5
    jobs_completed: int = 0
    average_response_hours: float = 24.0

    # Preferences
    preferred_supplier: bool = False
    notes: str = ""

    @property
    def is_compliant(self) -> bool:
        """Check if all compliance requirements are met."""
        today = date.today()

        if self.license_expiry and self.license_expiry < today:
            return False
        if self.insurance_expiry and self.insurance_expiry < today:
            return False
        return self.workcover_verified

    def check_compliance_issues(self) -> list[str]:
        """Return list of compliance issues."""
        issues = []
        today = date.today()

        if self.license_expiry:
            if self.license_expiry < today:
                issues.append("❌ Trade license expired")
            elif self.license_expiry < today + timedelta(days=30):
                issues.append(f"⚠️ Trade license expires {self.license_expiry}")

        if self.insurance_expiry:
            if self.insurance_expiry < today:
                issues.append("❌ Public liability insurance expired")
            elif self.insurance_expiry < today + timedelta(days=30):
                issues.append(f"⚠️ Insurance expires {self.insurance_expiry}")

        if not self.workcover_verified:
            issues.append("⚠️ WorkCover not verified")

        return issues


@dataclass
class Quote:
    """A quote from a tradesperson."""

    quote_id: str
    work_order_id: str
    supplier_id: str
    supplier_name: str

    # Quote details
    amount: Decimal
    gst_included: bool = True
    valid_until: date = field(default_factory=lambda: date.today() + timedelta(days=14))

    # Breakdown
    labour_cost: Decimal = Decimal("0")
    materials_cost: Decimal = Decimal("0")
    call_out_fee: Decimal = Decimal("0")

    # Availability
    available_date: Optional[date] = None
    estimated_duration: str = ""  # e.g., "2-3 hours"

    # Documents
    quote_document: Optional[str] = None
    notes: str = ""

    # Selection
    selected: bool = False
    selected_date: Optional[datetime] = None


@dataclass
class WorkOrder:
    """A maintenance work order."""

    work_order_id: str
    property_id: str
    property_address: str

    # Request details
    trade_category: TradeCategory
    priority: JobPriority
    title: str
    description: str
    reported_by: str  # "tenant", "inspection", "landlord", "manager"

    # Status
    status: WorkOrderStatus = WorkOrderStatus.NEW
    created_date: datetime = field(default_factory=datetime.now)

    # Assignment
    assigned_supplier_id: Optional[str] = None
    assigned_supplier_name: Optional[str] = None

    # Scheduling
    scheduled_date: Optional[datetime] = None
    access_instructions: str = ""
    tenant_notified: bool = False

    # Completion
    completed_date: Optional[datetime] = None
    work_description: str = ""

    # Media
    photos_before: list[str] = field(default_factory=list)
    photos_after: list[str] = field(default_factory=list)

    # Financial
    approved_amount: Decimal = Decimal("0")
    landlord_approved: bool = False
    landlord_approved_date: Optional[datetime] = None

    # Quotes
    quotes: list[Quote] = field(default_factory=list)

    # Communication
    notes: list[dict] = field(default_factory=list)

    @property
    def response_time_hours(self) -> Optional[float]:
        """Calculate response time if scheduled."""
        if self.scheduled_date:
            delta = self.scheduled_date - self.created_date
            return delta.total_seconds() / 3600
        return None

    @property
    def best_quote(self) -> Optional[Quote]:
        """Get the lowest quote."""
        if not self.quotes:
            return None
        return min(self.quotes, key=lambda q: q.amount)


@dataclass
class Invoice:
    """An invoice from a tradesperson."""

    invoice_id: str
    work_order_id: str
    supplier_id: str
    supplier_name: str

    # Invoice details
    invoice_number: str
    invoice_date: date
    due_date: date
    amount: Decimal
    gst: Decimal

    # Status
    status: InvoiceStatus = InvoiceStatus.RECEIVED

    # Payment
    paid_date: Optional[date] = None
    payment_reference: str = ""

    # Documents
    invoice_document: Optional[str] = None


@dataclass
class EmergencyJob:
    """An emergency maintenance job requiring immediate attention."""

    emergency_id: str
    work_order_id: str
    property_address: str

    # Emergency details
    issue_type: str
    description: str
    reported_time: datetime

    # Contact
    tenant_name: str
    tenant_phone: str

    # Escalation
    escalation_level: int = 1  # 1=initial, 2=supervisor, 3=manager
    escalated_to: Optional[str] = None

    # Response
    tradesperson_contacted: bool = False
    tradesperson_name: Optional[str] = None
    tradesperson_eta: Optional[datetime] = None

    # Resolution
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    resolution_notes: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE COORDINATOR
# ══════════════════════════════════════════════════════════════════════════════


class MaintenanceCoordinator:
    """Coordinates property maintenance and trades."""

    def __init__(self, agency_name: str):
        """Initialize the maintenance coordinator."""
        self.agency_name = agency_name

        # Data stores
        self.suppliers: dict[str, Tradesperson] = {}
        self.work_orders: dict[str, WorkOrder] = {}
        self.invoices: list[Invoice] = []
        self.emergencies: list[EmergencyJob] = []

        # Configuration
        self.auto_approve_limit = Decimal("500")  # Auto-approve under this
        self.emergency_contact = "0400 123 456"

        # Audit log
        self.audit_log: list[dict] = []

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        random_part = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        return f"{prefix}-{random_part}"

    def _log_action(
        self, action: str, entity_type: str, entity_id: str, details: str = ""
    ):
        """Log an action for audit trail."""
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
            }
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SUPPLIER MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def add_supplier(self, supplier: Tradesperson) -> str:
        """Add a new supplier/tradesperson."""
        if not supplier.supplier_id:
            supplier.supplier_id = self._generate_id("SUP")

        self.suppliers[supplier.supplier_id] = supplier
        self._log_action(
            "ADD", "Supplier", supplier.supplier_id, supplier.business_name
        )

        print(f"✅ Added supplier: {supplier.business_name}")
        return supplier.supplier_id

    def get_supplier(self, supplier_id: str) -> Optional[Tradesperson]:
        """Get supplier by ID."""
        return self.suppliers.get(supplier_id)

    def find_suppliers(
        self,
        trade: TradeCategory,
        postcode: Optional[str] = None,
        preferred_only: bool = False,
    ) -> list[Tradesperson]:
        """Find suitable suppliers for a job."""
        suppliers = [
            s
            for s in self.suppliers.values()
            if trade in s.trade_categories
            and s.status == SupplierStatus.ACTIVE
            and s.is_compliant
        ]

        if postcode:
            # Simple postcode matching (first 2 digits for area)
            area = postcode[:2]
            suppliers = [
                s
                for s in suppliers
                if any(pc.startswith(area) for pc in s.service_areas)
            ]

        if preferred_only:
            suppliers = [s for s in suppliers if s.preferred_supplier]

        # Sort by rating, then response time
        return sorted(suppliers, key=lambda s: (-s.rating, s.average_response_hours))

    def verify_supplier_abn(self, supplier_id: str) -> dict:
        """Verify supplier ABN (simulated)."""
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return {"error": "Supplier not found"}

        # In production, this would call the ABR API
        return {
            "abn": supplier.abn,
            "business_name": supplier.business_name,
            "status": "Active",
            "gst_registered": True,
            "verified_date": date.today().isoformat(),
        }

    def check_supplier_compliance(self) -> list[dict]:
        """Check compliance status of all suppliers."""
        issues = []

        for supplier in self.suppliers.values():
            if supplier.status != SupplierStatus.ACTIVE:
                continue

            supplier_issues = supplier.check_compliance_issues()
            if supplier_issues:
                issues.append(
                    {
                        "supplier_id": supplier.supplier_id,
                        "business_name": supplier.business_name,
                        "issues": supplier_issues,
                    }
                )

        return issues

    def update_supplier_rating(
        self, supplier_id: str, rating: float, feedback: str = ""
    ):
        """Update supplier rating after job completion."""
        supplier = self.suppliers.get(supplier_id)
        if supplier:
            # Rolling average
            total_ratings = supplier.rating * supplier.jobs_completed
            supplier.jobs_completed += 1
            supplier.rating = (total_ratings + rating) / supplier.jobs_completed

            self._log_action("RATE", "Supplier", supplier_id, f"Rating: {rating}/5")

    # ─────────────────────────────────────────────────────────────────────────
    # WORK ORDER MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def create_work_order(
        self,
        property_id: str,
        property_address: str,
        trade_category: TradeCategory,
        priority: JobPriority,
        title: str,
        description: str,
        reported_by: str = "tenant",
        photos: list[str] = None,
    ) -> str:
        """Create a new work order."""
        work_order = WorkOrder(
            work_order_id=self._generate_id("WO"),
            property_id=property_id,
            property_address=property_address,
            trade_category=trade_category,
            priority=priority,
            title=title,
            description=description,
            reported_by=reported_by,
            photos_before=photos or [],
        )

        self.work_orders[work_order.work_order_id] = work_order
        self._log_action(
            "CREATE",
            "WorkOrder",
            work_order.work_order_id,
            f"{priority.value}: {title}",
        )

        # Auto-escalate emergencies
        if priority == JobPriority.EMERGENCY:
            self._handle_emergency(work_order)

        print(f"✅ Created work order: {work_order.work_order_id}")
        print(f"   Priority: {priority.value}")
        print(f"   Category: {trade_category.value}")

        return work_order.work_order_id

    def _handle_emergency(self, work_order: WorkOrder):
        """Handle emergency work order creation."""
        emergency = EmergencyJob(
            emergency_id=self._generate_id("EMG"),
            work_order_id=work_order.work_order_id,
            property_address=work_order.property_address,
            issue_type=work_order.trade_category.value,
            description=work_order.description,
            reported_time=datetime.now(),
            tenant_name="Unknown",  # Would come from property data
            tenant_phone="Unknown",
        )

        self.emergencies.append(emergency)

        print(f"🚨 EMERGENCY JOB CREATED: {emergency.emergency_id}")
        print(f"   Emergency Line: {self.emergency_contact}")

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        """Get work order by ID."""
        return self.work_orders.get(work_order_id)

    def list_work_orders(
        self,
        status: Optional[WorkOrderStatus] = None,
        priority: Optional[JobPriority] = None,
        property_id: Optional[str] = None,
    ) -> list[WorkOrder]:
        """List work orders with optional filters."""
        orders = list(self.work_orders.values())

        if status:
            orders = [o for o in orders if o.status == status]

        if priority:
            orders = [o for o in orders if o.priority == priority]

        if property_id:
            orders = [o for o in orders if o.property_id == property_id]

        # Sort by priority, then date
        priority_order = {
            JobPriority.EMERGENCY: 0,
            JobPriority.URGENT: 1,
            JobPriority.HIGH: 2,
            JobPriority.NORMAL: 3,
            JobPriority.LOW: 4,
        }

        return sorted(
            orders, key=lambda o: (priority_order[o.priority], o.created_date)
        )

    def update_work_order_status(
        self, work_order_id: str, status: WorkOrderStatus
    ) -> bool:
        """Update work order status."""
        order = self.work_orders.get(work_order_id)
        if order:
            order.status = status
            self._log_action(
                "UPDATE", "WorkOrder", work_order_id, f"Status -> {status.value}"
            )
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # QUOTE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def request_quotes(
        self, work_order_id: str, supplier_ids: list[str] = None
    ) -> list[str]:
        """Request quotes from suppliers."""
        order = self.work_orders.get(work_order_id)
        if not order:
            return []

        if not supplier_ids:
            # Find suitable suppliers
            suppliers = self.find_suppliers(order.trade_category)
            supplier_ids = [s.supplier_id for s in suppliers[:3]]  # Top 3

        order.status = WorkOrderStatus.QUOTING

        notified = []
        for sid in supplier_ids:
            supplier = self.suppliers.get(sid)
            if supplier:
                notified.append(supplier.business_name)
                # In production, send email/SMS

        self._log_action(
            "REQUEST_QUOTES",
            "WorkOrder",
            work_order_id,
            f"Requested from: {', '.join(notified)}",
        )

        print(f"📤 Quote requests sent to {len(notified)} suppliers")
        return notified

    def add_quote(
        self,
        work_order_id: str,
        supplier_id: str,
        amount: Decimal,
        labour: Decimal = Decimal("0"),
        materials: Decimal = Decimal("0"),
        call_out: Decimal = Decimal("0"),
        available_date: Optional[date] = None,
        estimated_duration: str = "",
        notes: str = "",
    ) -> str:
        """Add a quote to a work order."""
        order = self.work_orders.get(work_order_id)
        supplier = self.suppliers.get(supplier_id)

        if not order or not supplier:
            return ""

        quote = Quote(
            quote_id=self._generate_id("QT"),
            work_order_id=work_order_id,
            supplier_id=supplier_id,
            supplier_name=supplier.business_name,
            amount=amount,
            labour_cost=labour,
            materials_cost=materials,
            call_out_fee=call_out,
            available_date=available_date,
            estimated_duration=estimated_duration,
            notes=notes,
        )

        order.quotes.append(quote)

        if order.status == WorkOrderStatus.QUOTING:
            order.status = WorkOrderStatus.QUOTE_RECEIVED

        self._log_action(
            "ADD_QUOTE",
            "WorkOrder",
            work_order_id,
            f"{supplier.business_name}: ${amount}",
        )

        print(f"✅ Quote added: ${amount} from {supplier.business_name}")
        return quote.quote_id

    def compare_quotes(self, work_order_id: str) -> dict:
        """Compare quotes for a work order."""
        order = self.work_orders.get(work_order_id)
        if not order or not order.quotes:
            return {"error": "No quotes found"}

        quotes_data = []
        for quote in order.quotes:
            supplier = self.suppliers.get(quote.supplier_id)
            quotes_data.append(
                {
                    "quote_id": quote.quote_id,
                    "supplier": quote.supplier_name,
                    "amount": float(quote.amount),
                    "labour": float(quote.labour_cost),
                    "materials": float(quote.materials_cost),
                    "call_out": float(quote.call_out_fee),
                    "available": (
                        quote.available_date.strftime("%d/%m/%Y")
                        if quote.available_date
                        else "TBC"
                    ),
                    "duration": quote.estimated_duration,
                    "supplier_rating": supplier.rating if supplier else 0,
                    "preferred": supplier.preferred_supplier if supplier else False,
                }
            )

        # Sort by amount
        quotes_data.sort(key=lambda q: q["amount"])

        best = quotes_data[0]

        return {
            "work_order_id": work_order_id,
            "property": order.property_address,
            "job": order.title,
            "quotes": quotes_data,
            "recommendation": {
                "quote_id": best["quote_id"],
                "supplier": best["supplier"],
                "amount": best["amount"],
                "reason": "Lowest quote"
                + (" (preferred supplier)" if best["preferred"] else ""),
            },
        }

    def select_quote(self, work_order_id: str, quote_id: str) -> bool:
        """Select a quote for a work order."""
        order = self.work_orders.get(work_order_id)
        if not order:
            return False

        for quote in order.quotes:
            if quote.quote_id == quote_id:
                quote.selected = True
                quote.selected_date = datetime.now()

                order.assigned_supplier_id = quote.supplier_id
                order.assigned_supplier_name = quote.supplier_name
                order.approved_amount = quote.amount

                # Check if auto-approve
                if quote.amount <= self.auto_approve_limit:
                    order.landlord_approved = True
                    order.landlord_approved_date = datetime.now()
                    order.status = WorkOrderStatus.APPROVED
                    print(f"✅ Quote auto-approved (under ${self.auto_approve_limit})")
                else:
                    order.status = WorkOrderStatus.PENDING_APPROVAL
                    print(f"⏳ Quote requires landlord approval (${quote.amount})")

                self._log_action(
                    "SELECT_QUOTE",
                    "WorkOrder",
                    work_order_id,
                    f"Selected: {quote.supplier_name} ${quote.amount}",
                )
                return True

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # JOB SCHEDULING & COMPLETION
    # ─────────────────────────────────────────────────────────────────────────

    def schedule_job(
        self,
        work_order_id: str,
        scheduled_date: datetime,
        access_instructions: str = "",
    ) -> bool:
        """Schedule a job with the assigned tradesperson."""
        order = self.work_orders.get(work_order_id)
        if not order:
            return False

        order.scheduled_date = scheduled_date
        order.access_instructions = access_instructions
        order.status = WorkOrderStatus.SCHEDULED

        # In production, send notifications
        order.tenant_notified = True

        self._log_action(
            "SCHEDULE",
            "WorkOrder",
            work_order_id,
            f"Scheduled: {scheduled_date.strftime('%d/%m/%Y %H:%M')}",
        )

        print(f"📅 Job scheduled: {scheduled_date.strftime('%d/%m/%Y %H:%M')}")
        return True

    def start_job(self, work_order_id: str) -> bool:
        """Mark job as in progress."""
        order = self.work_orders.get(work_order_id)
        if order:
            order.status = WorkOrderStatus.IN_PROGRESS
            self._log_action("START", "WorkOrder", work_order_id)
            return True
        return False

    def complete_job(
        self,
        work_order_id: str,
        work_description: str,
        photos_after: list[str] = None,
    ) -> bool:
        """Mark job as completed."""
        order = self.work_orders.get(work_order_id)
        if not order:
            return False

        order.status = WorkOrderStatus.COMPLETED
        order.completed_date = datetime.now()
        order.work_description = work_description
        order.photos_after = photos_after or []

        self._log_action("COMPLETE", "WorkOrder", work_order_id)

        print(f"✅ Job completed: {work_order_id}")
        return True

    def get_job_timeline(self, work_order_id: str) -> list[dict]:
        """Get timeline of events for a work order."""
        events = [e for e in self.audit_log if e["entity_id"] == work_order_id]
        return sorted(events, key=lambda e: e["timestamp"])

    # ─────────────────────────────────────────────────────────────────────────
    # INVOICE PROCESSING
    # ─────────────────────────────────────────────────────────────────────────

    def receive_invoice(
        self,
        work_order_id: str,
        invoice_number: str,
        amount: Decimal,
        gst: Decimal,
        invoice_date: date,
        due_date: date,
        document: Optional[str] = None,
    ) -> str:
        """Receive an invoice from a tradesperson."""
        order = self.work_orders.get(work_order_id)
        if not order:
            return ""

        invoice = Invoice(
            invoice_id=self._generate_id("INV"),
            work_order_id=work_order_id,
            supplier_id=order.assigned_supplier_id or "",
            supplier_name=order.assigned_supplier_name or "",
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            amount=amount,
            gst=gst,
            invoice_document=document,
        )

        self.invoices.append(invoice)
        order.status = WorkOrderStatus.INVOICED

        self._log_action(
            "RECEIVE_INVOICE",
            "Invoice",
            invoice.invoice_id,
            f"${amount} for WO {work_order_id}",
        )

        print(f"📄 Invoice received: {invoice.invoice_id}")
        return invoice.invoice_id

    def approve_invoice(self, invoice_id: str) -> bool:
        """Approve an invoice for payment."""
        for invoice in self.invoices:
            if invoice.invoice_id == invoice_id:
                invoice.status = InvoiceStatus.APPROVED
                self._log_action("APPROVE", "Invoice", invoice_id)
                return True
        return False

    def mark_invoice_paid(self, invoice_id: str, payment_reference: str) -> bool:
        """Mark an invoice as paid."""
        for invoice in self.invoices:
            if invoice.invoice_id == invoice_id:
                invoice.status = InvoiceStatus.PAID
                invoice.paid_date = date.today()
                invoice.payment_reference = payment_reference

                # Update work order
                order = self.work_orders.get(invoice.work_order_id)
                if order:
                    order.status = WorkOrderStatus.PAID

                self._log_action(
                    "PAY", "Invoice", invoice_id, f"Ref: {payment_reference}"
                )
                return True
        return False

    def get_pending_invoices(self) -> list[Invoice]:
        """Get invoices pending payment."""
        return [
            inv
            for inv in self.invoices
            if inv.status
            in [
                InvoiceStatus.RECEIVED,
                InvoiceStatus.UNDER_REVIEW,
                InvoiceStatus.APPROVED,
                InvoiceStatus.QUEUED_FOR_PAYMENT,
            ]
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # EMERGENCY MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def escalate_emergency(self, emergency_id: str, reason: str) -> bool:
        """Escalate an emergency to the next level."""
        for emergency in self.emergencies:
            if emergency.emergency_id == emergency_id:
                emergency.escalation_level += 1

                levels = {
                    2: "After Hours Supervisor",
                    3: "Property Manager",
                    4: "Agency Principal",
                }

                emergency.escalated_to = levels.get(
                    emergency.escalation_level, "Management"
                )

                print(
                    f"🚨 Emergency escalated to Level {emergency.escalation_level}: "
                    f"{emergency.escalated_to}"
                )
                return True
        return False

    def assign_emergency_tradesperson(
        self,
        emergency_id: str,
        supplier_id: str,
        eta: datetime,
    ) -> bool:
        """Assign a tradesperson to an emergency."""
        for emergency in self.emergencies:
            if emergency.emergency_id == emergency_id:
                supplier = self.suppliers.get(supplier_id)
                if supplier:
                    emergency.tradesperson_contacted = True
                    emergency.tradesperson_name = supplier.business_name
                    emergency.tradesperson_eta = eta

                    print(f"✅ Emergency assigned: {supplier.business_name}")
                    print(f"   ETA: {eta.strftime('%H:%M')}")
                    return True
        return False

    def resolve_emergency(self, emergency_id: str, resolution_notes: str) -> bool:
        """Mark an emergency as resolved."""
        for emergency in self.emergencies:
            if emergency.emergency_id == emergency_id:
                emergency.resolved = True
                emergency.resolution_time = datetime.now()
                emergency.resolution_notes = resolution_notes

                print(f"✅ Emergency resolved: {emergency_id}")
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    def get_maintenance_summary(self, days: int = 30) -> dict:
        """Get maintenance summary for the last N days."""
        cutoff = datetime.now() - timedelta(days=days)

        orders = [o for o in self.work_orders.values() if o.created_date >= cutoff]

        by_status = {}
        for order in orders:
            status = order.status.value
            if status not in by_status:
                by_status[status] = 0
            by_status[status] += 1

        by_trade = {}
        for order in orders:
            trade = order.trade_category.value
            if trade not in by_trade:
                by_trade[trade] = 0
            by_trade[trade] += 1

        completed = [
            o
            for o in orders
            if o.status
            in [
                WorkOrderStatus.COMPLETED,
                WorkOrderStatus.INVOICED,
                WorkOrderStatus.PAID,
            ]
        ]
        total_spent = sum(o.approved_amount for o in completed)

        return {
            "period_days": days,
            "total_work_orders": len(orders),
            "by_status": by_status,
            "by_trade": by_trade,
            "total_spent": float(total_spent),
            "average_per_job": float(total_spent / len(completed)) if completed else 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA
# ══════════════════════════════════════════════════════════════════════════════


def populate_demo_suppliers(coordinator: MaintenanceCoordinator):
    """Add demo suppliers."""
    suppliers = [
        Tradesperson(
            supplier_id="",
            business_name="Quick Fix Plumbing",
            contact_name="Mike Johnson",
            phone="0412 111 222",
            email="mike@quickfixplumbing.com.au",
            abn="12 345 678 901",
            trade_categories=[TradeCategory.PLUMBING],
            service_areas=["5000", "5001", "5006", "5007", "5031", "5032"],
            license_number="PGE123456",
            license_state=AustralianState.SA,
            license_expiry=date(2027, 3, 15),
            insurance_expiry=date(2026, 12, 31),
            workcover_verified=True,
            rating=4.8,
            jobs_completed=45,
            average_response_hours=4.0,
            preferred_supplier=True,
        ),
        Tradesperson(
            supplier_id="",
            business_name="Sparky Electrical Services",
            contact_name="David Chen",
            phone="0423 333 444",
            email="david@sparkyelectrical.com.au",
            abn="23 456 789 012",
            trade_categories=[TradeCategory.ELECTRICAL],
            service_areas=["5000", "5006", "5031", "5032", "5095"],
            license_number="PGE234567",
            license_state=AustralianState.SA,
            license_expiry=date(2026, 8, 30),
            insurance_expiry=date(2026, 11, 15),
            workcover_verified=True,
            rating=4.9,
            jobs_completed=62,
            average_response_hours=6.0,
            preferred_supplier=True,
        ),
        Tradesperson(
            supplier_id="",
            business_name="Cool Air HVAC",
            contact_name="Sarah Williams",
            phone="0434 555 666",
            email="sarah@coolair.com.au",
            abn="34 567 890 123",
            trade_categories=[TradeCategory.HVAC],
            service_areas=[
                "5000",
                "5001",
                "5006",
                "5007",
                "5031",
                "5032",
                "5067",
                "5095",
            ],
            license_number="ARC123456",
            license_state=AustralianState.SA,
            license_expiry=date(2027, 5, 20),
            insurance_expiry=date(2026, 9, 30),
            workcover_verified=True,
            rating=4.7,
            jobs_completed=38,
            average_response_hours=8.0,
        ),
        Tradesperson(
            supplier_id="",
            business_name="Handy Andy Services",
            contact_name="Andrew Peters",
            phone="0445 777 888",
            email="andy@handyandy.com.au",
            abn="45 678 901 234",
            trade_categories=[
                TradeCategory.GENERAL,
                TradeCategory.CARPENTRY,
                TradeCategory.PAINTING,
            ],
            service_areas=[
                "5000",
                "5001",
                "5006",
                "5007",
                "5031",
                "5032",
                "5045",
                "5067",
            ],
            insurance_expiry=date(2026, 10, 15),
            workcover_verified=True,
            rating=4.5,
            jobs_completed=28,
            average_response_hours=12.0,
        ),
        Tradesperson(
            supplier_id="",
            business_name="Green Thumb Gardens",
            contact_name="Lisa Green",
            phone="0456 999 000",
            email="lisa@greenthumb.com.au",
            abn="56 789 012 345",
            trade_categories=[TradeCategory.GARDENING],
            service_areas=["5000", "5006", "5031", "5045", "5067", "5095"],
            insurance_expiry=date(2026, 8, 30),
            workcover_verified=True,
            rating=4.6,
            jobs_completed=52,
            average_response_hours=24.0,
        ),
    ]

    for supplier in suppliers:
        coordinator.add_supplier(supplier)


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate the maintenance coordinator."""

    print("=" * 70)
    print("Maintenance & Trades Coordinator Demo")
    print("=" * 70)

    # Initialize coordinator
    coordinator = MaintenanceCoordinator("Adelaide Property Management")

    # Add suppliers
    print("\n" + "─" * 50)
    print("👷 Adding Suppliers/Tradespeople")
    print("─" * 50)
    populate_demo_suppliers(coordinator)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Create Work Order
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📋 Creating Work Orders")
    print("─" * 50)

    # Normal priority job
    wo1_id = coordinator.create_work_order(
        property_id="PROP-001",
        property_address="Unit 5/123 Wakefield Street, Adelaide SA 5000",
        trade_category=TradeCategory.PLUMBING,
        priority=JobPriority.NORMAL,
        title="Leaking tap in bathroom",
        description="Hot water tap in bathroom basin dripping constantly. "
        "Washer may need replacement.",
        reported_by="tenant",
        photos=["photo_tap_leak_01.jpg"],
    )

    # Urgent job
    coordinator.create_work_order(
        property_id="PROP-002",
        property_address="8 Jacaranda Crescent, Mawson Lakes SA 5095",
        trade_category=TradeCategory.ELECTRICAL,
        priority=JobPriority.URGENT,
        title="Power point not working",
        description="Power point in living room completely dead. "
        "Other outlets working fine.",
        reported_by="tenant",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Find Suppliers and Request Quotes
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔍 Finding Suppliers")
    print("─" * 50)

    plumbers = coordinator.find_suppliers(TradeCategory.PLUMBING, postcode="5000")
    print(f"\nFound {len(plumbers)} plumbers for Adelaide CBD:")
    for plumber in plumbers:
        pref = "⭐ " if plumber.preferred_supplier else "  "
        print(f"   {pref}{plumber.business_name} (Rating: {plumber.rating}/5)")

    # Request quotes
    print("\n📤 Requesting quotes...")
    coordinator.request_quotes(wo1_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Add Quotes
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("💰 Receiving Quotes")
    print("─" * 50)

    # Get supplier IDs
    supplier_ids = list(coordinator.suppliers.keys())

    coordinator.add_quote(
        work_order_id=wo1_id,
        supplier_id=supplier_ids[0],  # Quick Fix Plumbing
        amount=Decimal("165"),
        labour=Decimal("120"),
        materials=Decimal("45"),
        available_date=date.today() + timedelta(days=2),
        estimated_duration="1 hour",
    )

    coordinator.add_quote(
        work_order_id=wo1_id,
        supplier_id=supplier_ids[
            0
        ],  # Another quote from same (simulating different supplier)
        amount=Decimal("195"),
        labour=Decimal("140"),
        materials=Decimal("55"),
        call_out=Decimal("0"),
        available_date=date.today() + timedelta(days=1),
        estimated_duration="1-2 hours",
        notes="Can come tomorrow if needed",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Compare and Select Quote
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📊 Quote Comparison")
    print("─" * 50)

    comparison = coordinator.compare_quotes(wo1_id)

    print(f"\nProperty: {comparison['property']}")
    print(f"Job: {comparison['job']}")
    print("\nQuotes received:")
    for q in comparison["quotes"]:
        print(f"   ${q['amount']:.2f} - {q['supplier']} (Available: {q['available']})")

    rec = comparison["recommendation"]
    print(f"\n💡 Recommendation: {rec['supplier']} at ${rec['amount']:.2f}")
    print(f"   Reason: {rec['reason']}")

    # Select the quote
    print("\n✅ Selecting recommended quote...")
    work_order = coordinator.get_work_order(wo1_id)
    if work_order and work_order.quotes:
        coordinator.select_quote(wo1_id, work_order.quotes[0].quote_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Schedule Job
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📅 Scheduling Job")
    print("─" * 50)

    scheduled_time = datetime.now() + timedelta(days=2, hours=9)
    coordinator.schedule_job(
        wo1_id,
        scheduled_date=scheduled_time,
        access_instructions="Tenant will be home. Enter via front door. "
        "Cat may be loose - please don't let it out.",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Complete Job
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("✅ Completing Job")
    print("─" * 50)

    coordinator.start_job(wo1_id)
    print("🔧 Job in progress...")

    coordinator.complete_job(
        wo1_id,
        work_description="Replaced washer on hot water tap. Tap was also loose - "
        "tightened and resealed. All working correctly now.",
        photos_after=["photo_tap_fixed_01.jpg", "photo_tap_fixed_02.jpg"],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Invoice Processing
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📄 Processing Invoice")
    print("─" * 50)

    invoice_id = coordinator.receive_invoice(
        work_order_id=wo1_id,
        invoice_number="QFP-2026-0342",
        amount=Decimal("165"),
        gst=Decimal("15"),
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=14),
    )

    coordinator.approve_invoice(invoice_id)
    print("✅ Invoice approved")

    coordinator.mark_invoice_paid(invoice_id, "EFT-20260315-001")
    print("💰 Invoice marked as paid")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Supplier Compliance Check
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📋 Supplier Compliance Check")
    print("─" * 50)

    compliance_issues = coordinator.check_supplier_compliance()
    if compliance_issues:
        print("\n⚠️ Compliance issues found:")
        for issue in compliance_issues:
            print(f"\n   {issue['business_name']}:")
            for i in issue["issues"]:
                print(f"      {i}")
    else:
        print("✅ All suppliers compliant")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 9: Create Emergency Job
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🚨 Emergency Job Scenario")
    print("─" * 50)

    coordinator.create_work_order(
        property_id="PROP-003",
        property_address="22 Willow Avenue, Norwood SA 5067",
        trade_category=TradeCategory.PLUMBING,
        priority=JobPriority.EMERGENCY,
        title="Burst pipe - water everywhere",
        description="Pipe burst under kitchen sink. Water flooding kitchen. "
        "Main has been turned off.",
        reported_by="tenant",
    )

    # Assign emergency tradesperson
    if coordinator.emergencies:
        emergency = coordinator.emergencies[-1]
        coordinator.assign_emergency_tradesperson(
            emergency.emergency_id,
            supplier_id=supplier_ids[0],
            eta=datetime.now() + timedelta(hours=1),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 10: Summary Report
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📊 Maintenance Summary (Last 30 Days)")
    print("─" * 50)

    summary = coordinator.get_maintenance_summary(days=30)

    print(f"\nTotal Work Orders: {summary['total_work_orders']}")
    print("\nBy Status:")
    for status, count in summary["by_status"].items():
        print(f"   {status}: {count}")

    print("\nBy Trade:")
    for trade, count in summary["by_trade"].items():
        print(f"   {trade}: {count}")

    print(f"\nTotal Spent: ${summary['total_spent']:.2f}")
    print(f"Average per Job: ${summary['average_per_job']:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("✅ Maintenance Coordinator Demo Complete!")
    print("\nFeatures demonstrated:")
    print("  • Supplier/tradesperson management")
    print("  • Work order creation and tracking")
    print("  • Quote request and comparison")
    print("  • Job scheduling and completion")
    print("  • Before/after photo documentation")
    print("  • Invoice processing")
    print("  • Supplier compliance monitoring")
    print("  • Emergency job handling")
    print("  • Maintenance reporting")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
