#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 56: Tenant Self-Service Portal

A tenant-facing portal for managing their rental experience.
Allows tenants to manage payments, submit maintenance requests,
access documents, and communicate with property managers.

Features:
- Rent payment status and history
- Maintenance request submission
- Lease document access
- Inspection appointment booking
- Payment plan requests
- Communication with property manager
- Move-in/move-out checklists
- Bond claim tracking

Australian-specific:
- State-based bond authority integration
- Residential Tenancies Act compliance
- BPAY and direct debit payment options
- Standard form compliance

Usage:
    python examples/56_tenant_portal.py

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


class PaymentStatus(Enum):
    """Status of a rent payment."""

    PAID = "Paid"
    DUE = "Due"
    OVERDUE = "Overdue"
    PENDING = "Pending"
    FAILED = "Failed"


class MaintenanceCategory(Enum):
    """Categories for maintenance requests."""

    PLUMBING = "Plumbing"
    ELECTRICAL = "Electrical"
    APPLIANCE = "Appliances"
    HEATING_COOLING = "Heating/Cooling"
    LOCKS_SECURITY = "Locks/Security"
    PEST = "Pest Control"
    STRUCTURAL = "Structural"
    GARDEN = "Garden/Outdoor"
    GENERAL = "General"


class MaintenanceUrgency(Enum):
    """Urgency levels for maintenance."""

    EMERGENCY = "Emergency (Safety Risk)"
    URGENT = "Urgent (Same Week)"
    ROUTINE = "Routine (Within 2 Weeks)"
    LOW = "Low Priority"


class MaintenanceStatus(Enum):
    """Status of maintenance requests."""

    SUBMITTED = "Submitted"
    ACKNOWLEDGED = "Acknowledged"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class DocumentType(Enum):
    """Types of documents available to tenants."""

    LEASE_AGREEMENT = "Lease Agreement"
    CONDITION_REPORT = "Condition Report"
    BOND_RECEIPT = "Bond Receipt"
    RENT_LEDGER = "Rent Ledger"
    INSPECTION_REPORT = "Inspection Report"
    NOTICE = "Notice"
    CORRESPONDENCE = "Correspondence"


class InspectionSlot(Enum):
    """Available inspection time slots."""

    MORNING = "Morning (9am - 12pm)"
    AFTERNOON = "Afternoon (1pm - 4pm)"
    LATE_AFTERNOON = "Late Afternoon (4pm - 6pm)"


class PaymentPlanStatus(Enum):
    """Status of payment plan requests."""

    REQUESTED = "Requested"
    UNDER_REVIEW = "Under Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    DEFAULTED = "Defaulted"


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class TenantProfile:
    """Tenant's profile information."""

    tenant_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    property_address: str
    lease_start: date
    lease_end: Optional[date]
    weekly_rent: Decimal
    bond_amount: Decimal
    bond_reference: str
    property_manager_name: str
    property_manager_email: str
    property_manager_phone: str
    emergency_maintenance_phone: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_lease_periodic(self) -> bool:
        return self.lease_end is None

    @property
    def days_until_lease_end(self) -> Optional[int]:
        if self.lease_end is None:
            return None
        return (self.lease_end - date.today()).days


@dataclass
class RentPayment:
    """A rent payment record."""

    payment_id: str
    period_start: date
    period_end: date
    amount_due: Decimal
    amount_paid: Decimal
    status: PaymentStatus
    due_date: date
    paid_date: Optional[date] = None
    payment_method: str = ""
    reference: str = ""

    @property
    def balance_owing(self) -> Decimal:
        return self.amount_due - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return (
            self.status in [PaymentStatus.DUE, PaymentStatus.OVERDUE]
            and date.today() > self.due_date
        )


@dataclass
class MaintenanceRequest:
    """A maintenance request submitted by tenant."""

    request_id: str
    category: MaintenanceCategory
    urgency: MaintenanceUrgency
    title: str
    description: str
    status: MaintenanceStatus = MaintenanceStatus.SUBMITTED
    submitted_date: datetime = field(default_factory=datetime.now)

    # Scheduling
    preferred_dates: list[date] = field(default_factory=list)
    access_instructions: str = ""
    pet_details: str = ""

    # Progress
    scheduled_date: Optional[datetime] = None
    tradesperson_name: str = ""
    tradesperson_phone: str = ""
    completion_date: Optional[datetime] = None

    # Media
    photos: list[str] = field(default_factory=list)

    # Communication
    messages: list[dict] = field(default_factory=list)


@dataclass
class Document:
    """A document available to the tenant."""

    document_id: str
    document_type: DocumentType
    title: str
    filename: str
    upload_date: date
    file_size_kb: int
    description: str = ""


@dataclass
class InspectionBooking:
    """An inspection appointment."""

    booking_id: str
    inspection_date: date
    time_slot: InspectionSlot
    status: str = "Confirmed"
    notes: str = ""
    inspection_type: str = "Routine"


@dataclass
class PaymentPlanRequest:
    """A request for a payment plan."""

    request_id: str
    total_arrears: Decimal
    proposed_weekly_amount: Decimal
    reason: str
    status: PaymentPlanStatus = PaymentPlanStatus.REQUESTED
    submitted_date: date = field(default_factory=date.today)

    # If approved
    approved_amount: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class Message:
    """A message in the communication thread."""

    message_id: str
    sender: str  # "tenant" or "manager"
    subject: str
    content: str
    sent_date: datetime
    read: bool = False
    attachments: list[str] = field(default_factory=list)


@dataclass
class ChecklistItem:
    """An item in a move checklist."""

    item_id: str
    category: str
    description: str
    completed: bool = False
    notes: str = ""
    photo: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# TENANT PORTAL
# ══════════════════════════════════════════════════════════════════════════════


class TenantPortal:
    """Self-service portal for tenants."""

    def __init__(self, tenant: TenantProfile):
        """Initialize the tenant portal."""
        self.tenant = tenant

        # Data stores
        self.payments: list[RentPayment] = []
        self.maintenance_requests: list[MaintenanceRequest] = []
        self.documents: list[Document] = []
        self.inspections: list[InspectionBooking] = []
        self.messages: list[Message] = []
        self.payment_plans: list[PaymentPlanRequest] = []
        self.move_in_checklist: list[ChecklistItem] = []
        self.move_out_checklist: list[ChecklistItem] = []

        # Session tracking
        self.last_login: Optional[datetime] = None
        self.notifications: list[str] = []

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        random_part = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        return f"{prefix}-{random_part}"

    def login(self) -> dict:
        """Process tenant login and return dashboard data."""
        self.last_login = datetime.now()

        # Generate any pending notifications
        self._check_notifications()

        return {
            "tenant": self.tenant.full_name,
            "property": self.tenant.property_address,
            "notifications": self.notifications.copy(),
            "rent_balance": float(self.get_current_balance()),
            "open_maintenance": len(
                [
                    m
                    for m in self.maintenance_requests
                    if m.status
                    not in [MaintenanceStatus.COMPLETED, MaintenanceStatus.CANCELLED]
                ]
            ),
            "unread_messages": len(
                [m for m in self.messages if not m.read and m.sender == "manager"]
            ),
            "upcoming_inspection": self._get_next_inspection(),
        }

    def _check_notifications(self):
        """Check for any notifications to display."""
        self.notifications = []

        # Check rent due soon
        for payment in self.payments:
            if payment.status == PaymentStatus.DUE:
                days_until_due = (payment.due_date - date.today()).days
                if days_until_due <= 3 and days_until_due >= 0:
                    self.notifications.append(
                        f"🔔 Rent of ${payment.amount_due} due in {days_until_due} days"
                    )

        # Check overdue rent
        overdue = [p for p in self.payments if p.is_overdue]
        if overdue:
            total = sum(p.balance_owing for p in overdue)
            self.notifications.append(f"⚠️ You have ${total:.2f} in overdue rent")

        # Check lease expiry
        if self.tenant.days_until_lease_end is not None:
            if (
                self.tenant.days_until_lease_end <= 60
                and self.tenant.days_until_lease_end > 0
            ):
                self.notifications.append(
                    f"📋 Your lease expires in {self.tenant.days_until_lease_end} days. "
                    "Contact your property manager about renewal."
                )

        # Check upcoming inspection
        next_insp = self._get_next_inspection()
        if next_insp:
            days_until = (next_insp.inspection_date - date.today()).days
            if days_until <= 7:
                self.notifications.append(
                    f"🔍 Routine inspection scheduled for "
                    f"{next_insp.inspection_date.strftime('%d %B')} ({next_insp.time_slot.value})"
                )

    def _get_next_inspection(self) -> Optional[InspectionBooking]:
        """Get the next scheduled inspection."""
        upcoming = [
            i
            for i in self.inspections
            if i.inspection_date >= date.today() and i.status == "Confirmed"
        ]
        if upcoming:
            return min(upcoming, key=lambda x: x.inspection_date)
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # RENT & PAYMENTS
    # ─────────────────────────────────────────────────────────────────────────

    def get_current_balance(self) -> Decimal:
        """Get current rent balance (positive = owing, negative = in credit)."""
        total_due = sum(p.amount_due for p in self.payments)
        total_paid = sum(p.amount_paid for p in self.payments)
        return total_due - total_paid

    def get_payment_history(self, months: int = 6) -> list[RentPayment]:
        """Get payment history for the last N months."""
        cutoff = date.today() - timedelta(days=months * 30)
        return [p for p in self.payments if p.period_start >= cutoff]

    def get_upcoming_payments(self) -> list[RentPayment]:
        """Get upcoming rent payments."""
        return [
            p
            for p in self.payments
            if p.status in [PaymentStatus.DUE, PaymentStatus.PENDING]
            and p.due_date >= date.today()
        ]

    def get_payment_details(self) -> dict:
        """Get payment method details (BPAY, direct debit, etc.)."""
        return {
            "bpay_biller_code": "12345",
            "bpay_reference": f"T{self.tenant.tenant_id[-6:]}",
            "bank_name": "Adelaide Property Trust",
            "bsb": "105-029",
            "account_number": "87654321",
            "account_name": "APM RENT TRUST",
            "reference": self.tenant.tenant_id,
            "weekly_rent": float(self.tenant.weekly_rent),
            "rent_due_day": "Every Monday",
        }

    def request_payment_plan(
        self,
        total_arrears: Decimal,
        proposed_weekly_amount: Decimal,
        reason: str,
    ) -> str:
        """Request a payment plan for rent arrears."""
        request = PaymentPlanRequest(
            request_id=self._generate_id("PP"),
            total_arrears=total_arrears,
            proposed_weekly_amount=proposed_weekly_amount,
            reason=reason,
        )

        self.payment_plans.append(request)

        # Send notification to property manager
        self._send_internal_message(
            subject="Payment Plan Request",
            content=f"Payment plan requested for ${total_arrears:.2f} arrears. "
            f"Proposed: ${proposed_weekly_amount:.2f}/week. "
            f"Reason: {reason}",
        )

        print(f"✅ Payment plan request submitted: {request.request_id}")
        return request.request_id

    def get_payment_plan_status(self) -> Optional[PaymentPlanRequest]:
        """Get status of active payment plan request."""
        active = [
            p
            for p in self.payment_plans
            if p.status
            in [
                PaymentPlanStatus.REQUESTED,
                PaymentPlanStatus.UNDER_REVIEW,
                PaymentPlanStatus.APPROVED,
                PaymentPlanStatus.ACTIVE,
            ]
        ]
        return active[0] if active else None

    # ─────────────────────────────────────────────────────────────────────────
    # MAINTENANCE
    # ─────────────────────────────────────────────────────────────────────────

    def submit_maintenance_request(
        self,
        category: MaintenanceCategory,
        urgency: MaintenanceUrgency,
        title: str,
        description: str,
        preferred_dates: list[date] = None,
        access_instructions: str = "",
        pet_details: str = "",
        photos: list[str] = None,
    ) -> str:
        """Submit a new maintenance request."""
        request = MaintenanceRequest(
            request_id=self._generate_id("MR"),
            category=category,
            urgency=urgency,
            title=title,
            description=description,
            preferred_dates=preferred_dates or [],
            access_instructions=access_instructions,
            pet_details=pet_details,
            photos=photos or [],
        )

        self.maintenance_requests.append(request)

        # For emergencies, display emergency number
        if urgency == MaintenanceUrgency.EMERGENCY:
            print(
                f"🚨 EMERGENCY: For immediate assistance, call {self.tenant.emergency_maintenance_phone}"
            )

        print(f"✅ Maintenance request submitted: {request.request_id}")
        print(f"   Category: {category.value}")
        print(f"   Urgency: {urgency.value}")

        return request.request_id

    def get_maintenance_requests(
        self, include_closed: bool = False
    ) -> list[MaintenanceRequest]:
        """Get maintenance requests."""
        if include_closed:
            return self.maintenance_requests
        return [
            m
            for m in self.maintenance_requests
            if m.status
            not in [MaintenanceStatus.COMPLETED, MaintenanceStatus.CANCELLED]
        ]

    def get_maintenance_status(self, request_id: str) -> Optional[dict]:
        """Get detailed status of a maintenance request."""
        for req in self.maintenance_requests:
            if req.request_id == request_id:
                return {
                    "request_id": req.request_id,
                    "title": req.title,
                    "category": req.category.value,
                    "urgency": req.urgency.value,
                    "status": req.status.value,
                    "submitted": req.submitted_date.strftime("%d/%m/%Y %H:%M"),
                    "scheduled": (
                        req.scheduled_date.strftime("%d/%m/%Y %H:%M")
                        if req.scheduled_date
                        else None
                    ),
                    "tradesperson": req.tradesperson_name or None,
                    "tradesperson_phone": req.tradesperson_phone or None,
                    "messages": len(req.messages),
                }
        return None

    def add_maintenance_comment(self, request_id: str, message: str) -> bool:
        """Add a comment to a maintenance request."""
        for req in self.maintenance_requests:
            if req.request_id == request_id:
                req.messages.append(
                    {
                        "sender": "tenant",
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                print(f"✅ Comment added to {request_id}")
                return True
        return False

    def add_maintenance_photo(self, request_id: str, photo_path: str) -> bool:
        """Add a photo to a maintenance request."""
        for req in self.maintenance_requests:
            if req.request_id == request_id:
                req.photos.append(photo_path)
                print(f"✅ Photo added to {request_id}")
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # DOCUMENTS
    # ─────────────────────────────────────────────────────────────────────────

    def get_documents(self, doc_type: Optional[DocumentType] = None) -> list[Document]:
        """Get available documents."""
        if doc_type is None:
            return self.documents
        return [d for d in self.documents if d.document_type == doc_type]

    def download_document(self, document_id: str) -> Optional[dict]:
        """Get download details for a document."""
        for doc in self.documents:
            if doc.document_id == document_id:
                return {
                    "document_id": doc.document_id,
                    "filename": doc.filename,
                    "file_size": f"{doc.file_size_kb} KB",
                    "download_url": f"/api/documents/{doc.document_id}/download",
                    "expires": (datetime.now() + timedelta(hours=1)).isoformat(),
                }
        return None

    def get_lease_summary(self) -> dict:
        """Get a summary of the lease agreement."""
        return {
            "property": self.tenant.property_address,
            "tenant": self.tenant.full_name,
            "start_date": self.tenant.lease_start.strftime("%d/%m/%Y"),
            "end_date": (
                self.tenant.lease_end.strftime("%d/%m/%Y")
                if self.tenant.lease_end
                else "Periodic"
            ),
            "weekly_rent": float(self.tenant.weekly_rent),
            "bond": float(self.tenant.bond_amount),
            "bond_reference": self.tenant.bond_reference,
            "property_manager": self.tenant.property_manager_name,
            "contact_email": self.tenant.property_manager_email,
            "contact_phone": self.tenant.property_manager_phone,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # INSPECTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def get_inspection_schedule(self) -> list[InspectionBooking]:
        """Get all scheduled inspections."""
        return [i for i in self.inspections if i.inspection_date >= date.today()]

    def request_inspection_reschedule(
        self,
        booking_id: str,
        preferred_dates: list[date],
        preferred_slot: InspectionSlot,
        reason: str,
    ) -> bool:
        """Request to reschedule an inspection."""
        for insp in self.inspections:
            if insp.booking_id == booking_id:
                # Send message to property manager
                self._send_internal_message(
                    subject=f"Inspection Reschedule Request - {insp.inspection_date.strftime('%d/%m/%Y')}",
                    content=f"Reason: {reason}\n\n"
                    f"Preferred dates: {', '.join(d.strftime('%d/%m/%Y') for d in preferred_dates)}\n"
                    f"Preferred time: {preferred_slot.value}",
                )
                print(f"✅ Reschedule request submitted for inspection {booking_id}")
                return True
        return False

    def confirm_inspection_attendance(
        self, booking_id: str, attending: bool, notes: str = ""
    ) -> bool:
        """Confirm whether tenant will be present for inspection."""
        for insp in self.inspections:
            if insp.booking_id == booking_id:
                insp.notes = (
                    f"Tenant {'will' if attending else 'will NOT'} be present. {notes}"
                )
                print(f"✅ Attendance confirmed for inspection {booking_id}")
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # COMMUNICATION
    # ─────────────────────────────────────────────────────────────────────────

    def _send_internal_message(self, subject: str, content: str):
        """Internal method to send a message."""
        msg = Message(
            message_id=self._generate_id("MSG"),
            sender="tenant",
            subject=subject,
            content=content,
            sent_date=datetime.now(),
        )
        self.messages.append(msg)

    def send_message(
        self, subject: str, content: str, attachments: list[str] = None
    ) -> str:
        """Send a message to the property manager."""
        msg = Message(
            message_id=self._generate_id("MSG"),
            sender="tenant",
            subject=subject,
            content=content,
            sent_date=datetime.now(),
            attachments=attachments or [],
        )

        self.messages.append(msg)
        print(f"✅ Message sent: {msg.message_id}")
        return msg.message_id

    def get_messages(self, unread_only: bool = False) -> list[Message]:
        """Get messages."""
        if unread_only:
            return [m for m in self.messages if not m.read and m.sender == "manager"]
        return sorted(self.messages, key=lambda x: x.sent_date, reverse=True)

    def mark_message_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        for msg in self.messages:
            if msg.message_id == message_id:
                msg.read = True
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # CHECKLISTS
    # ─────────────────────────────────────────────────────────────────────────

    def get_move_in_checklist(self) -> list[ChecklistItem]:
        """Get the move-in checklist."""
        if not self.move_in_checklist:
            self._generate_move_in_checklist()
        return self.move_in_checklist

    def _generate_move_in_checklist(self):
        """Generate standard move-in checklist items."""
        items = [
            ("Keys", "Collect all keys and test each one"),
            ("Keys", "Get garage remote / fob if applicable"),
            ("Utilities", "Set up electricity account"),
            ("Utilities", "Set up gas account if applicable"),
            ("Utilities", "Set up internet/NBN"),
            ("Utilities", "Water - confirm meter reading"),
            ("Condition Report", "Review condition report thoroughly"),
            ("Condition Report", "Note any discrepancies within 3 days"),
            ("Condition Report", "Take date-stamped photos"),
            ("Safety", "Test smoke alarms"),
            ("Safety", "Locate fire extinguisher/blanket"),
            ("Safety", "Note emergency exits"),
            ("Appliances", "Test all appliances"),
            ("Appliances", "Check oven, cooktop, rangehood"),
            ("Appliances", "Check dishwasher if applicable"),
            ("Appliances", "Check washing machine connections"),
            ("General", "Test all lights and switches"),
            ("General", "Check all taps and drainage"),
            ("General", "Check windows and locks"),
            ("General", "Check blinds/curtains"),
        ]

        for i, (category, description) in enumerate(items):
            self.move_in_checklist.append(
                ChecklistItem(
                    item_id=f"MI-{i+1:03d}",
                    category=category,
                    description=description,
                )
            )

    def get_move_out_checklist(self) -> list[ChecklistItem]:
        """Get the move-out checklist."""
        if not self.move_out_checklist:
            self._generate_move_out_checklist()
        return self.move_out_checklist

    def _generate_move_out_checklist(self):
        """Generate standard move-out checklist items."""
        items = [
            ("Notice", "Provide written notice to property manager"),
            ("Notice", "Confirm move-out date"),
            ("Cleaning", "Clean all rooms thoroughly"),
            ("Cleaning", "Clean oven and rangehood"),
            ("Cleaning", "Clean all windows inside"),
            ("Cleaning", "Clean bathroom/s - remove mould"),
            ("Cleaning", "Shampoo carpets (if required)"),
            ("Cleaning", "Clean all light fittings"),
            ("Gardens", "Mow lawns and trim edges"),
            ("Gardens", "Weed garden beds"),
            ("Gardens", "Remove any rubbish"),
            ("Repairs", "Fill picture hooks (match paint if required)"),
            ("Repairs", "Replace any blown light globes"),
            ("Repairs", "Ensure all items in condition report are present"),
            ("Utilities", "Cancel electricity account"),
            ("Utilities", "Cancel gas account"),
            ("Utilities", "Redirect mail"),
            ("Keys", "Return ALL keys"),
            ("Keys", "Return garage remotes/fobs"),
            ("Final", "Take final photos with date"),
            ("Final", "Attend final inspection if possible"),
            ("Final", "Provide forwarding address for bond"),
        ]

        for i, (category, description) in enumerate(items):
            self.move_out_checklist.append(
                ChecklistItem(
                    item_id=f"MO-{i+1:03d}",
                    category=category,
                    description=description,
                )
            )

    def update_checklist_item(
        self, item_id: str, completed: bool, notes: str = ""
    ) -> bool:
        """Update a checklist item."""
        all_items = self.move_in_checklist + self.move_out_checklist
        for item in all_items:
            if item.item_id == item_id:
                item.completed = completed
                item.notes = notes
                print(f"✅ Updated checklist item: {item_id}")
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # BOND
    # ─────────────────────────────────────────────────────────────────────────

    def get_bond_status(self) -> dict:
        """Get bond information."""
        return {
            "amount": float(self.tenant.bond_amount),
            "reference": self.tenant.bond_reference,
            "status": "Lodged",
            "lodged_with": "CBS South Australia",  # Would vary by state
            "how_to_claim": "Bond can be claimed at end of tenancy via CBS online portal",
            "url": "https://www.cbs.sa.gov.au/bond",
        }

    def request_bond_refund(self, forwarding_address: str, bank_details: dict) -> str:
        """Request bond refund (for end of tenancy)."""
        request_id = self._generate_id("BOND")

        self._send_internal_message(
            subject="Bond Refund Request",
            content=f"Bond refund requested.\n\n"
            f"Forwarding address: {forwarding_address}\n"
            f"BSB: {bank_details.get('bsb', 'Not provided')}\n"
            f"Account: {bank_details.get('account', 'Not provided')}\n"
            f"Name: {bank_details.get('name', 'Not provided')}",
        )

        print(f"✅ Bond refund request submitted: {request_id}")
        return request_id


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA GENERATORS
# ══════════════════════════════════════════════════════════════════════════════


def create_demo_tenant() -> TenantProfile:
    """Create a demo tenant profile."""
    return TenantProfile(
        tenant_id="TEN-SA2024",
        first_name="Emily",
        last_name="Thompson",
        email="emily.thompson@email.com",
        phone="0412 345 678",
        property_address="Unit 12/45 Rundle Street, Adelaide SA 5000",
        lease_start=date(2025, 3, 1),
        lease_end=date(2026, 2, 28),
        weekly_rent=Decimal("520"),
        bond_amount=Decimal("2080"),
        bond_reference="CBS-2025-123456",
        property_manager_name="Sarah Mitchell",
        property_manager_email="sarah@adelaidepm.com.au",
        property_manager_phone="08 8231 1234",
        emergency_maintenance_phone="0400 123 456",
    )


def populate_demo_data(portal: TenantPortal):
    """Populate portal with demo data."""

    # Add payment history
    today = date.today()
    for i in range(12):
        payment_date = today - timedelta(weeks=i)
        status = PaymentStatus.PAID if i > 0 else PaymentStatus.DUE

        portal.payments.append(
            RentPayment(
                payment_id=f"PAY-{12-i:03d}",
                period_start=payment_date - timedelta(days=6),
                period_end=payment_date,
                amount_due=portal.tenant.weekly_rent,
                amount_paid=(
                    portal.tenant.weekly_rent
                    if status == PaymentStatus.PAID
                    else Decimal("0")
                ),
                status=status,
                due_date=payment_date,
                paid_date=payment_date if status == PaymentStatus.PAID else None,
                payment_method="Direct Debit" if status == PaymentStatus.PAID else "",
            )
        )

    # Add documents
    documents = [
        (
            DocumentType.LEASE_AGREEMENT,
            "Residential Tenancy Agreement",
            "lease_agreement.pdf",
            245,
        ),
        (
            DocumentType.CONDITION_REPORT,
            "Ingoing Condition Report",
            "condition_report_in.pdf",
            1820,
        ),
        (DocumentType.BOND_RECEIPT, "Bond Lodgement Receipt", "bond_receipt.pdf", 45),
        (DocumentType.RENT_LEDGER, "Rent Ledger - Current", "rent_ledger.pdf", 32),
    ]

    for doc_type, title, filename, size in documents:
        portal.documents.append(
            Document(
                document_id=portal._generate_id("DOC"),
                document_type=doc_type,
                title=title,
                filename=filename,
                upload_date=portal.tenant.lease_start,
                file_size_kb=size,
            )
        )

    # Add an upcoming inspection
    portal.inspections.append(
        InspectionBooking(
            booking_id=portal._generate_id("INSP"),
            inspection_date=today + timedelta(days=14),
            time_slot=InspectionSlot.MORNING,
            inspection_type="Routine",
        )
    )

    # Add a maintenance request
    portal.maintenance_requests.append(
        MaintenanceRequest(
            request_id="MR-DEMO01",
            category=MaintenanceCategory.PLUMBING,
            urgency=MaintenanceUrgency.ROUTINE,
            title="Dripping tap in bathroom",
            description="The hot water tap in the bathroom basin has been dripping for a few days.",
            status=MaintenanceStatus.SCHEDULED,
            submitted_date=datetime.now() - timedelta(days=3),
            scheduled_date=datetime.now() + timedelta(days=2),
            tradesperson_name="Quick Fix Plumbing",
            tradesperson_phone="0412 888 999",
        )
    )

    # Add a message from property manager
    portal.messages.append(
        Message(
            message_id="MSG-DEMO01",
            sender="manager",
            subject="Welcome to your new home!",
            content="Hi Emily,\n\nWelcome to Unit 12/45 Rundle Street! "
            "Please don't hesitate to reach out if you have any questions.\n\n"
            "Kind regards,\nSarah Mitchell",
            sent_date=datetime.now() - timedelta(days=30),
            read=True,
        )
    )

    portal.messages.append(
        Message(
            message_id="MSG-DEMO02",
            sender="manager",
            subject="Upcoming routine inspection",
            content="Hi Emily,\n\nThis is a reminder that your routine inspection is "
            f"scheduled for {(today + timedelta(days=14)).strftime('%d %B %Y')}.\n\n"
            "Please ensure the property is accessible.\n\n"
            "Kind regards,\nSarah Mitchell",
            sent_date=datetime.now() - timedelta(days=7),
            read=False,
        )
    )


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate the tenant portal."""

    print("=" * 70)
    print("Tenant Self-Service Portal Demo")
    print("=" * 70)

    # Create tenant and portal
    tenant = create_demo_tenant()
    portal = TenantPortal(tenant)

    # Populate demo data
    populate_demo_data(portal)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Login
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔐 Tenant Login")
    print("─" * 50)

    dashboard = portal.login()
    print(f"\n👋 Welcome back, {dashboard['tenant']}!")
    print(f"📍 Property: {dashboard['property']}")

    if dashboard["notifications"]:
        print("\n🔔 Notifications:")
        for notif in dashboard["notifications"]:
            print(f"   {notif}")

    print("\n📊 Dashboard:")
    print(f"   💰 Rent Balance: ${dashboard['rent_balance']:.2f}")
    print(f"   🔧 Open Maintenance: {dashboard['open_maintenance']}")
    print(f"   ✉️ Unread Messages: {dashboard['unread_messages']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Check Payments
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("💰 Rent & Payments")
    print("─" * 50)

    balance = portal.get_current_balance()
    print(f"\n📋 Current Balance: ${balance:.2f}")

    # Payment details
    details = portal.get_payment_details()
    print("\n💳 Payment Options:")
    print(f"   BPAY Biller: {details['bpay_biller_code']}")
    print(f"   BPAY Ref: {details['bpay_reference']}")
    print(f"   Bank: {details['bank_name']}")
    print(f"   BSB: {details['bsb']}")
    print(f"   Account: {details['account_number']}")

    # Recent payments
    recent = portal.get_payment_history(months=3)
    print(f"\n📜 Recent Payments ({len(recent)} records):")
    for p in recent[:3]:
        status_icon = "✅" if p.status == PaymentStatus.PAID else "⏳"
        print(
            f"   {status_icon} {p.period_end.strftime('%d/%m/%Y')}: ${p.amount_due} - {p.status.value}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Submit Maintenance Request
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔧 Maintenance Requests")
    print("─" * 50)

    # Check existing requests
    existing = portal.get_maintenance_requests()
    if existing:
        print(f"\n📋 Open Requests ({len(existing)}):")
        for req in existing:
            print(f"   • {req.title} [{req.status.value}]")
            if req.scheduled_date:
                print(
                    f"     Scheduled: {req.scheduled_date.strftime('%d/%m/%Y %H:%M')}"
                )
                print(f"     Tradesperson: {req.tradesperson_name}")

    # Submit a new request
    print("\n📝 Submitting new maintenance request...")
    request_id = portal.submit_maintenance_request(
        category=MaintenanceCategory.ELECTRICAL,
        urgency=MaintenanceUrgency.ROUTINE,
        title="Light not working in bedroom",
        description="The ceiling light in the main bedroom stopped working. "
        "Have tried replacing the globe but it still doesn't work.",
        preferred_dates=[
            date.today() + timedelta(days=7),
            date.today() + timedelta(days=8),
        ],
        access_instructions="I work from home, available all day",
        pet_details="No pets",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Access Documents
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📄 Documents")
    print("─" * 50)

    documents = portal.get_documents()
    print(f"\n📁 Available Documents ({len(documents)}):")
    for doc in documents:
        print(f"   📄 {doc.title}")
        print(f"      {doc.filename} ({doc.file_size_kb} KB)")

    # Lease summary
    lease = portal.get_lease_summary()
    print("\n📜 Lease Summary:")
    print(f"   Start: {lease['start_date']}")
    print(f"   End: {lease['end_date']}")
    print(f"   Weekly Rent: ${lease['weekly_rent']}")
    print(f"   Bond: ${lease['bond']} (Ref: {lease['bond_reference']})")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Inspections
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔍 Inspections")
    print("─" * 50)

    inspections = portal.get_inspection_schedule()
    if inspections:
        print("\n📅 Upcoming Inspections:")
        for insp in inspections:
            print(f"   📆 {insp.inspection_date.strftime('%d %B %Y')}")
            print(f"      Time: {insp.time_slot.value}")
            print(f"      Type: {insp.inspection_type}")

        # Confirm attendance
        portal.confirm_inspection_attendance(
            inspections[0].booking_id,
            attending=True,
            notes="I'll be working from home",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Messages
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("✉️ Messages")
    print("─" * 50)

    messages = portal.get_messages()
    unread = [m for m in messages if not m.read and m.sender == "manager"]

    if unread:
        print(f"\n📬 Unread Messages ({len(unread)}):")
        for msg in unread:
            print(f"   ✉️ {msg.subject}")
            print("      From: Property Manager")
            print(f"      Date: {msg.sent_date.strftime('%d/%m/%Y')}")
            portal.mark_message_read(msg.message_id)

    # Send a message
    print("\n📤 Sending message to property manager...")
    portal.send_message(
        subject="Question about parking",
        content="Hi Sarah,\n\nI wanted to confirm which car park bay is assigned to Unit 12? "
        "I couldn't find it in my lease agreement.\n\n"
        "Thanks,\nEmily",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Move-In Checklist
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("✅ Move-In Checklist")
    print("─" * 50)

    checklist = portal.get_move_in_checklist()

    # Group by category
    categories = {}
    for item in checklist:
        if item.category not in categories:
            categories[item.category] = []
        categories[item.category].append(item)

    print(f"\n📋 Checklist ({len(checklist)} items):")
    for category, items in list(categories.items())[:3]:
        print(f"\n   {category}:")
        for item in items[:2]:
            status = "☑️" if item.completed else "⬜"
            print(f"      {status} {item.description}")
    print("   ... and more")

    # Update some items
    portal.update_checklist_item("MI-001", completed=True, notes="All 3 keys received")
    portal.update_checklist_item("MI-002", completed=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Bond Information
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔐 Bond Information")
    print("─" * 50)

    bond = portal.get_bond_status()
    print(f"\n💰 Bond Amount: ${bond['amount']:.2f}")
    print(f"   Reference: {bond['reference']}")
    print(f"   Status: {bond['status']}")
    print(f"   Lodged with: {bond['lodged_with']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("✅ Tenant Portal Demo Complete!")
    print("\nFeatures demonstrated:")
    print("  • Tenant login and dashboard")
    print("  • Rent payment history and options")
    print("  • Maintenance request submission")
    print("  • Document access")
    print("  • Inspection scheduling")
    print("  • Property manager communication")
    print("  • Move-in/out checklists")
    print("  • Bond information")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
