#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 28: IT Support Ticket Bot

An enterprise IT helpdesk assistant:
- Create/track support tickets
- Troubleshooting workflows (password reset, VPN, printer)
- Knowledge base search for solutions
- Escalation to human agents
- SLA tracking and priority management

Key patterns demonstrated:
- Ticket lifecycle management
- Guided troubleshooting workflows
- Knowledge base integration
- Role-based access (employee, technician, admin)
- SLA breach detection and escalation

Usage:
    python examples/28_it_helpdesk.py

Requirements:
    pip install agentic-brain
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import json
import random
import string

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class TicketPriority(Enum):
    """Support ticket priority levels."""

    CRITICAL = "critical"  # System down, business impact - 1 hour SLA
    HIGH = "high"  # Major issue, limited workaround - 4 hour SLA
    MEDIUM = "medium"  # Standard issue - 24 hour SLA
    LOW = "low"  # Minor issue or enhancement - 72 hour SLA


class TicketStatus(Enum):
    """Support ticket status."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    PENDING_VENDOR = "pending_vendor"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(Enum):
    """IT support categories."""

    PASSWORD_RESET = "password_reset"
    VPN_ACCESS = "vpn_access"
    EMAIL_ISSUE = "email_issue"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    PRINTER = "printer"
    NETWORK = "network"
    SECURITY = "security"
    ACCESS_REQUEST = "access_request"
    OTHER = "other"


class UserRole(Enum):
    """System user roles."""

    EMPLOYEE = "employee"
    TECHNICIAN = "technician"
    SENIOR_TECH = "senior_tech"
    ADMIN = "admin"


@dataclass
class User:
    """System user."""

    id: str
    email: str
    name: str
    department: str
    role: UserRole
    manager_id: str = ""
    phone: str = ""
    location: str = ""


@dataclass
class Ticket:
    """IT support ticket."""

    id: str
    title: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    requester_id: str
    assigned_to: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution: str = ""
    notes: list = field(default_factory=list)
    related_tickets: list = field(default_factory=list)
    escalation_count: int = 0

    def __post_init__(self):
        """Calculate SLA due date based on priority."""
        if self.due_at is None:
            sla_hours = {
                TicketPriority.CRITICAL: 1,
                TicketPriority.HIGH: 4,
                TicketPriority.MEDIUM: 24,
                TicketPriority.LOW: 72,
            }
            self.due_at = self.created_at + timedelta(hours=sla_hours[self.priority])

    def is_sla_breached(self) -> bool:
        """Check if SLA has been breached."""
        if self.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return False
        return datetime.now() > self.due_at

    def time_to_sla(self) -> timedelta:
        """Get time remaining until SLA breach."""
        return self.due_at - datetime.now()


@dataclass
class KnowledgeArticle:
    """Knowledge base article."""

    id: str
    title: str
    category: TicketCategory
    symptoms: list
    solution: str
    steps: list
    keywords: list
    views: int = 0
    helpful_votes: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    author_id: str = ""


@dataclass
class TroubleshootingStep:
    """A step in a troubleshooting workflow."""

    step_number: int
    instruction: str
    expected_result: str
    if_success: str = "proceed"
    if_failure: str = "escalate"


# ══════════════════════════════════════════════════════════════════════════════
# IT HELPDESK SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class ITHelpdeskService:
    """Enterprise IT helpdesk management service."""

    def __init__(self):
        """Initialize with demo data."""
        self.tickets: dict[str, Ticket] = {}
        self.users: dict[str, User] = {}
        self.knowledge_base: dict[str, KnowledgeArticle] = {}
        self.current_user: Optional[User] = None
        self._load_demo_data()

    def _generate_id(self, prefix: str = "TKT") -> str:
        """Generate unique ID."""
        suffix = "".join(random.choices(string.digits, k=6))
        return f"{prefix}-{suffix}"

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo users
        users = [
            User(
                "U001",
                "john.smith@company.com",
                "John Smith",
                "Engineering",
                UserRole.EMPLOYEE,
                "U005",
                "x1234",
                "Building A",
            ),
            User(
                "U002",
                "sarah.jones@company.com",
                "Sarah Jones",
                "Marketing",
                UserRole.EMPLOYEE,
                "U006",
                "x1235",
                "Building B",
            ),
            User(
                "U003",
                "tech.support@company.com",
                "Mike Chen",
                "IT",
                UserRole.TECHNICIAN,
                "U004",
                "x5001",
                "IT Office",
            ),
            User(
                "U004",
                "senior.tech@company.com",
                "Emily Davis",
                "IT",
                UserRole.SENIOR_TECH,
                "U007",
                "x5002",
                "IT Office",
            ),
            User(
                "U005",
                "manager.eng@company.com",
                "Robert Wilson",
                "Engineering",
                UserRole.EMPLOYEE,
                "",
                "x2001",
                "Building A",
            ),
            User(
                "U006",
                "manager.mkt@company.com",
                "Lisa Brown",
                "Marketing",
                UserRole.EMPLOYEE,
                "",
                "x2002",
                "Building B",
            ),
            User(
                "U007",
                "it.director@company.com",
                "James Taylor",
                "IT",
                UserRole.ADMIN,
                "",
                "x9001",
                "IT Office",
            ),
        ]
        for user in users:
            self.users[user.id] = user

        # Demo tickets
        demo_tickets = [
            Ticket(
                id="TKT-100001",
                title="Cannot connect to VPN from home",
                description="Getting 'Authentication failed' error when trying to connect to VPN. "
                "Worked fine yesterday. Using Windows 11 laptop.",
                category=TicketCategory.VPN_ACCESS,
                priority=TicketPriority.HIGH,
                status=TicketStatus.IN_PROGRESS,
                requester_id="U001",
                assigned_to="U003",
                created_at=datetime.now() - timedelta(hours=2),
            ),
            Ticket(
                id="TKT-100002",
                title="Printer not printing - Marketing floor",
                description="HP LaserJet on 3rd floor is showing 'offline' but it's powered on. "
                "Multiple users affected.",
                category=TicketCategory.PRINTER,
                priority=TicketPriority.MEDIUM,
                status=TicketStatus.NEW,
                requester_id="U002",
                created_at=datetime.now() - timedelta(hours=5),
            ),
            Ticket(
                id="TKT-100003",
                title="Password expired - locked out of system",
                description="Password expired over the weekend, cannot log into Windows or email. "
                "Need urgent reset for Monday meeting.",
                category=TicketCategory.PASSWORD_RESET,
                priority=TicketPriority.CRITICAL,
                status=TicketStatus.ESCALATED,
                requester_id="U005",
                assigned_to="U004",
                created_at=datetime.now() - timedelta(minutes=30),
                escalation_count=1,
            ),
            Ticket(
                id="TKT-100004",
                title="Request access to SharePoint Finance folder",
                description="Need read access to Finance Q4 Reports folder for budget review. "
                "Manager approved via email.",
                category=TicketCategory.ACCESS_REQUEST,
                priority=TicketPriority.LOW,
                status=TicketStatus.PENDING_USER,
                requester_id="U002",
                assigned_to="U003",
                created_at=datetime.now() - timedelta(days=1),
                notes=["Waiting for manager's written approval form"],
            ),
            Ticket(
                id="TKT-100005",
                title="Laptop keyboard not working",
                description="Several keys on Dell Latitude stopped working after coffee spill. "
                "Need hardware replacement.",
                category=TicketCategory.HARDWARE,
                priority=TicketPriority.MEDIUM,
                status=TicketStatus.RESOLVED,
                requester_id="U001",
                assigned_to="U003",
                created_at=datetime.now() - timedelta(days=3),
                resolved_at=datetime.now() - timedelta(days=2),
                resolution="Replaced keyboard under warranty. Advised user on proper care.",
            ),
        ]
        for ticket in demo_tickets:
            self.tickets[ticket.id] = ticket

        # Knowledge base articles
        kb_articles = [
            KnowledgeArticle(
                id="KB-001",
                title="VPN Connection Troubleshooting Guide",
                category=TicketCategory.VPN_ACCESS,
                symptoms=[
                    "Cannot connect to VPN",
                    "Authentication failed",
                    "VPN timeout",
                ],
                solution="Follow the step-by-step troubleshooting process below.",
                steps=[
                    "1. Verify you are connected to the internet (try loading google.com)",
                    "2. Check VPN client is up to date (version 5.x or higher)",
                    "3. Clear VPN credentials: Settings > Credentials > Clear",
                    "4. Restart VPN client completely",
                    "5. Try connecting again with your network credentials",
                    "6. If still failing, check if MFA token is synchronized",
                    "7. Contact IT if issue persists after all steps",
                ],
                keywords=[
                    "vpn",
                    "connection",
                    "authentication",
                    "remote",
                    "work from home",
                ],
                views=1523,
                helpful_votes=142,
                author_id="U004",
            ),
            KnowledgeArticle(
                id="KB-002",
                title="Password Reset Self-Service",
                category=TicketCategory.PASSWORD_RESET,
                symptoms=["Forgot password", "Password expired", "Account locked"],
                solution="Use self-service portal or contact IT for manual reset.",
                steps=[
                    "1. Go to https://password.company.com",
                    "2. Click 'Forgot Password' or 'Unlock Account'",
                    "3. Verify identity using security questions or mobile auth",
                    "4. Create new password following policy requirements",
                    "5. Password must be 12+ chars with uppercase, number, and symbol",
                    "6. Wait 5 minutes for synchronization across all systems",
                ],
                keywords=["password", "reset", "forgot", "locked", "expired"],
                views=3847,
                helpful_votes=412,
                author_id="U004",
            ),
            KnowledgeArticle(
                id="KB-003",
                title="Printer Offline Troubleshooting",
                category=TicketCategory.PRINTER,
                symptoms=["Printer offline", "Print jobs stuck", "Cannot find printer"],
                solution="Check physical connection and reinstall printer driver.",
                steps=[
                    "1. Check printer is powered on and has no error lights",
                    "2. Verify network cable is connected (for network printers)",
                    "3. Open Windows Settings > Devices > Printers",
                    "4. Right-click printer > 'See what's printing' > Cancel all jobs",
                    "5. Right-click printer > 'Set as default' if needed",
                    "6. If still offline, remove and re-add the printer",
                    "7. For persistent issues, request IT to check network port",
                ],
                keywords=["printer", "offline", "printing", "stuck", "queue"],
                views=892,
                helpful_votes=67,
                author_id="U003",
            ),
            KnowledgeArticle(
                id="KB-004",
                title="Email Not Syncing on Mobile",
                category=TicketCategory.EMAIL_ISSUE,
                symptoms=[
                    "Email not syncing",
                    "Mobile email stopped",
                    "Outlook app error",
                ],
                solution="Remove and re-add email account on mobile device.",
                steps=[
                    "1. Open Outlook app on mobile device",
                    "2. Go to Settings > tap your account",
                    "3. Select 'Delete Account' (emails remain on server)",
                    "4. Re-add account using your company email",
                    "5. Authenticate with MFA when prompted",
                    "6. Allow 10-15 minutes for full sync",
                ],
                keywords=["email", "mobile", "sync", "outlook", "phone"],
                views=2156,
                helpful_votes=234,
                author_id="U003",
            ),
            KnowledgeArticle(
                id="KB-005",
                title="Software Installation Request Process",
                category=TicketCategory.SOFTWARE,
                symptoms=["Need software installed", "Access denied", "Cannot install"],
                solution="Submit software request through IT portal for approval.",
                steps=[
                    "1. Go to IT Self-Service Portal",
                    "2. Click 'Software Request'",
                    "3. Search for software in catalog",
                    "4. If not listed, provide business justification",
                    "5. Manager approval required for licensed software",
                    "6. IT will install within 2 business days after approval",
                ],
                keywords=["software", "install", "request", "application", "program"],
                views=1087,
                helpful_votes=89,
                author_id="U004",
            ),
        ]
        for article in kb_articles:
            self.knowledge_base[article.id] = article

        # Set default user
        self.current_user = self.users["U001"]

    # ──────────────────────────────────────────────────────────────────────────
    # TICKET MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def create_ticket(
        self, title: str, description: str, category: str, priority: str = "medium"
    ) -> dict:
        """Create a new support ticket."""
        try:
            cat = TicketCategory[category.upper()]
            pri = TicketPriority[priority.upper()]
        except KeyError:
            return {
                "success": False,
                "error": f"Invalid category or priority. "
                f"Categories: {[c.value for c in TicketCategory]}. "
                f"Priorities: {[p.value for p in TicketPriority]}",
            }

        ticket_id = self._generate_id()
        ticket = Ticket(
            id=ticket_id,
            title=title,
            description=description,
            category=cat,
            priority=pri,
            status=TicketStatus.NEW,
            requester_id=self.current_user.id,
        )
        self.tickets[ticket_id] = ticket

        # Auto-assign based on category for demo
        if pri == TicketPriority.CRITICAL:
            ticket.assigned_to = "U004"  # Senior tech for critical
        else:
            ticket.assigned_to = "U003"  # Regular tech

        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": f"Ticket {ticket_id} created successfully",
            "priority": pri.value,
            "sla_due": ticket.due_at.strftime("%Y-%m-%d %H:%M"),
            "assigned_to": (
                self.users[ticket.assigned_to].name
                if ticket.assigned_to
                else "Unassigned"
            ),
        }

    def get_ticket(self, ticket_id: str) -> dict:
        """Get ticket details."""
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            return {"success": False, "error": f"Ticket {ticket_id} not found"}

        requester = self.users.get(ticket.requester_id)
        assignee = self.users.get(ticket.assigned_to) if ticket.assigned_to else None

        return {
            "success": True,
            "ticket": {
                "id": ticket.id,
                "title": ticket.title,
                "description": ticket.description,
                "category": ticket.category.value,
                "priority": ticket.priority.value,
                "status": ticket.status.value,
                "requester": requester.name if requester else "Unknown",
                "requester_email": requester.email if requester else "",
                "assigned_to": assignee.name if assignee else "Unassigned",
                "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": ticket.updated_at.strftime("%Y-%m-%d %H:%M"),
                "sla_due": ticket.due_at.strftime("%Y-%m-%d %H:%M"),
                "sla_breached": ticket.is_sla_breached(),
                "time_to_sla": (
                    str(ticket.time_to_sla())
                    if not ticket.is_sla_breached()
                    else "BREACHED"
                ),
                "resolution": ticket.resolution,
                "notes": ticket.notes,
                "escalation_count": ticket.escalation_count,
            },
        }

    def update_ticket(
        self,
        ticket_id: str,
        status: str = None,
        notes: str = None,
        resolution: str = None,
        priority: str = None,
    ) -> dict:
        """Update a ticket."""
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            return {"success": False, "error": f"Ticket {ticket_id} not found"}

        # Check permissions
        can_update = (
            self.current_user.role
            in [UserRole.TECHNICIAN, UserRole.SENIOR_TECH, UserRole.ADMIN]
            or ticket.requester_id == self.current_user.id
        )
        if not can_update:
            return {"success": False, "error": "Permission denied"}

        changes = []

        if status:
            try:
                new_status = TicketStatus[status.upper()]
                old_status = ticket.status
                ticket.status = new_status
                changes.append(f"Status: {old_status.value} → {new_status.value}")

                if new_status == TicketStatus.RESOLVED:
                    ticket.resolved_at = datetime.now()
            except KeyError:
                return {"success": False, "error": f"Invalid status: {status}"}

        if priority:
            try:
                new_priority = TicketPriority[priority.upper()]
                old_priority = ticket.priority
                ticket.priority = new_priority
                changes.append(f"Priority: {old_priority.value} → {new_priority.value}")
            except KeyError:
                return {"success": False, "error": f"Invalid priority: {priority}"}

        if notes:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            note_entry = f"[{timestamp}] {self.current_user.name}: {notes}"
            ticket.notes.append(note_entry)
            changes.append("Added note")

        if resolution:
            ticket.resolution = resolution
            changes.append("Added resolution")

        ticket.updated_at = datetime.now()

        return {
            "success": True,
            "ticket_id": ticket_id,
            "changes": changes,
            "message": f"Ticket {ticket_id} updated successfully",
        }

    def escalate_ticket(self, ticket_id: str, reason: str) -> dict:
        """Escalate ticket to senior technician."""
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            return {"success": False, "error": f"Ticket {ticket_id} not found"}

        ticket.status = TicketStatus.ESCALATED
        ticket.escalation_count += 1
        ticket.assigned_to = "U004"  # Senior tech

        # Upgrade priority on escalation
        if ticket.priority == TicketPriority.LOW:
            ticket.priority = TicketPriority.MEDIUM
        elif ticket.priority == TicketPriority.MEDIUM:
            ticket.priority = TicketPriority.HIGH

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        ticket.notes.append(
            f"[{timestamp}] ESCALATION #{ticket.escalation_count}: {reason}"
        )
        ticket.updated_at = datetime.now()

        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": f"Ticket escalated to {self.users['U004'].name}",
            "new_priority": ticket.priority.value,
            "escalation_count": ticket.escalation_count,
        }

    def list_tickets(
        self,
        status: str = None,
        priority: str = None,
        assigned_to_me: bool = False,
        my_tickets: bool = False,
    ) -> dict:
        """List tickets with optional filters."""
        tickets = list(self.tickets.values())

        # Apply filters
        if status:
            try:
                stat = TicketStatus[status.upper()]
                tickets = [t for t in tickets if t.status == stat]
            except KeyError:
                pass

        if priority:
            try:
                pri = TicketPriority[priority.upper()]
                tickets = [t for t in tickets if t.priority == pri]
            except KeyError:
                pass

        if assigned_to_me:
            tickets = [t for t in tickets if t.assigned_to == self.current_user.id]

        if my_tickets:
            tickets = [t for t in tickets if t.requester_id == self.current_user.id]

        # Sort by priority and creation date
        priority_order = {
            TicketPriority.CRITICAL: 0,
            TicketPriority.HIGH: 1,
            TicketPriority.MEDIUM: 2,
            TicketPriority.LOW: 3,
        }
        tickets.sort(key=lambda t: (priority_order[t.priority], t.created_at))

        return {
            "success": True,
            "count": len(tickets),
            "tickets": [
                {
                    "id": t.id,
                    "title": t.title[:50] + "..." if len(t.title) > 50 else t.title,
                    "category": t.category.value,
                    "priority": t.priority.value,
                    "status": t.status.value,
                    "sla_breached": t.is_sla_breached(),
                    "created": t.created_at.strftime("%Y-%m-%d %H:%M"),
                }
                for t in tickets
            ],
        }

    def get_sla_report(self) -> dict:
        """Get SLA compliance report."""
        active_tickets = [
            t
            for t in self.tickets.values()
            if t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
        ]

        breached = [t for t in active_tickets if t.is_sla_breached()]
        at_risk = [
            t
            for t in active_tickets
            if not t.is_sla_breached() and t.time_to_sla() < timedelta(hours=2)
        ]

        return {
            "success": True,
            "report": {
                "total_active": len(active_tickets),
                "sla_breached": len(breached),
                "at_risk": len(at_risk),
                "compliant": len(active_tickets) - len(breached),
                "compliance_rate": (
                    f"{((len(active_tickets) - len(breached)) / len(active_tickets) * 100):.1f}%"
                    if active_tickets
                    else "N/A"
                ),
                "breached_tickets": [
                    {"id": t.id, "title": t.title, "priority": t.priority.value}
                    for t in breached
                ],
                "at_risk_tickets": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "time_remaining": str(t.time_to_sla()),
                    }
                    for t in at_risk
                ],
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # KNOWLEDGE BASE
    # ──────────────────────────────────────────────────────────────────────────

    def search_knowledge_base(self, query: str, category: str = None) -> dict:
        """Search knowledge base for solutions."""
        query_lower = query.lower()
        results = []

        for article in self.knowledge_base.values():
            score = 0

            # Title match
            if query_lower in article.title.lower():
                score += 10

            # Keyword match
            for keyword in article.keywords:
                if keyword.lower() in query_lower or query_lower in keyword.lower():
                    score += 5

            # Symptom match
            for symptom in article.symptoms:
                if query_lower in symptom.lower():
                    score += 7

            # Category filter
            if category:
                try:
                    cat = TicketCategory[category.upper()]
                    if article.category != cat:
                        continue
                except KeyError:
                    pass

            if score > 0:
                results.append((article, score))

        # Sort by relevance
        results.sort(key=lambda x: x[1], reverse=True)

        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "articles": [
                {
                    "id": article.id,
                    "title": article.title,
                    "category": article.category.value,
                    "relevance_score": score,
                    "preview": article.solution[:100] + "...",
                    "views": article.views,
                    "helpful_votes": article.helpful_votes,
                }
                for article, score in results[:5]
            ],
        }

    def get_article(self, article_id: str) -> dict:
        """Get full knowledge base article."""
        article = self.knowledge_base.get(article_id)
        if not article:
            return {"success": False, "error": f"Article {article_id} not found"}

        # Increment views
        article.views += 1

        return {
            "success": True,
            "article": {
                "id": article.id,
                "title": article.title,
                "category": article.category.value,
                "symptoms": article.symptoms,
                "solution": article.solution,
                "steps": article.steps,
                "keywords": article.keywords,
                "views": article.views,
                "helpful_votes": article.helpful_votes,
                "last_updated": article.updated_at.strftime("%Y-%m-%d"),
            },
        }

    def mark_article_helpful(self, article_id: str, helpful: bool = True) -> dict:
        """Mark article as helpful or not."""
        article = self.knowledge_base.get(article_id)
        if not article:
            return {"success": False, "error": f"Article {article_id} not found"}

        if helpful:
            article.helpful_votes += 1

        return {
            "success": True,
            "message": "Thank you for your feedback!",
            "new_helpful_count": article.helpful_votes,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # TROUBLESHOOTING WORKFLOWS
    # ──────────────────────────────────────────────────────────────────────────

    def get_troubleshooting_workflow(self, category: str) -> dict:
        """Get step-by-step troubleshooting workflow for a category."""
        workflows = {
            "password_reset": [
                TroubleshootingStep(
                    1,
                    "Ask user if they can access password reset portal at https://password.company.com",
                    "User can access the portal",
                    "proceed",
                    "Check network connectivity",
                ),
                TroubleshootingStep(
                    2,
                    "Guide user through 'Forgot Password' flow with security questions",
                    "User answers security questions correctly",
                    "proceed",
                    "Verify identity manually",
                ),
                TroubleshootingStep(
                    3,
                    "Have user create new password meeting policy (12+ chars, upper, lower, number, symbol)",
                    "Password created successfully",
                    "proceed",
                    "Check for password policy errors",
                ),
                TroubleshootingStep(
                    4,
                    "Confirm user can log into Windows with new password",
                    "Login successful",
                    "resolve",
                    "Wait 5 minutes for sync and retry",
                ),
            ],
            "vpn_access": [
                TroubleshootingStep(
                    1,
                    "Verify internet connectivity - can user load external websites?",
                    "Internet working",
                    "proceed",
                    "Troubleshoot internet first",
                ),
                TroubleshootingStep(
                    2,
                    "Check VPN client version - must be 5.x or higher",
                    "Version is current",
                    "proceed",
                    "Guide user to update client",
                ),
                TroubleshootingStep(
                    3,
                    "Have user clear VPN credentials and restart client",
                    "Credentials cleared",
                    "proceed",
                    "Assist with clearing cache",
                ),
                TroubleshootingStep(
                    4,
                    "Attempt VPN connection with network credentials",
                    "Connection successful",
                    "resolve",
                    "Check MFA token sync",
                ),
                TroubleshootingStep(
                    5,
                    "Verify MFA token is generating correctly",
                    "MFA working",
                    "resolve",
                    "Escalate to security team",
                ),
            ],
            "printer": [
                TroubleshootingStep(
                    1,
                    "Check printer is powered on with no error lights",
                    "Printer powered and no errors",
                    "proceed",
                    "Check physical printer",
                ),
                TroubleshootingStep(
                    2,
                    "Verify network cable connection or WiFi status",
                    "Network connected",
                    "proceed",
                    "Reconnect network cable",
                ),
                TroubleshootingStep(
                    3,
                    "Clear print queue via Windows Devices settings",
                    "Queue cleared",
                    "proceed",
                    "Restart print spooler service",
                ),
                TroubleshootingStep(
                    4,
                    "Remove and re-add printer in Windows",
                    "Printer re-added",
                    "proceed",
                    "Check printer drivers",
                ),
                TroubleshootingStep(
                    5,
                    "Send test print",
                    "Test page printed",
                    "resolve",
                    "Escalate to on-site support",
                ),
            ],
            "email_issue": [
                TroubleshootingStep(
                    1,
                    "Verify Outlook is fully updated",
                    "Outlook up to date",
                    "proceed",
                    "Update Outlook",
                ),
                TroubleshootingStep(
                    2,
                    "Check online mode - can user access OWA (webmail)?",
                    "OWA accessible",
                    "proceed",
                    "Escalate to email team",
                ),
                TroubleshootingStep(
                    3,
                    "Clear Outlook cache and restart application",
                    "Cache cleared",
                    "proceed",
                    "Create new Outlook profile",
                ),
                TroubleshootingStep(
                    4,
                    "Rebuild Outlook profile if issues persist",
                    "Profile rebuilt",
                    "resolve",
                    "Escalate to email team",
                ),
            ],
        }

        try:
            cat_key = category.lower()
            if cat_key not in workflows:
                return {
                    "success": False,
                    "error": f"No workflow found for '{category}'. "
                    f"Available: {list(workflows.keys())}",
                }

            steps = workflows[cat_key]
            return {
                "success": True,
                "category": cat_key,
                "total_steps": len(steps),
                "steps": [
                    {
                        "step": s.step_number,
                        "instruction": s.instruction,
                        "expected_result": s.expected_result,
                        "if_success": s.if_success,
                        "if_failure": s.if_failure,
                    }
                    for s in steps
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────────
    # USER MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def switch_user(self, user_id: str) -> dict:
        """Switch current user context (for demo)."""
        user = self.users.get(user_id)
        if not user:
            return {"success": False, "error": f"User {user_id} not found"}

        self.current_user = user
        return {
            "success": True,
            "message": f"Switched to user: {user.name}",
            "role": user.role.value,
            "department": user.department,
        }

    def list_users(self) -> dict:
        """List all users (admin only)."""
        if self.current_user.role not in [UserRole.ADMIN, UserRole.SENIOR_TECH]:
            return {
                "success": False,
                "error": "Permission denied - admin access required",
            }

        return {
            "success": True,
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                    "department": u.department,
                    "role": u.role.value,
                    "location": u.location,
                }
                for u in self.users.values()
            ],
        }

    def get_dashboard(self) -> dict:
        """Get IT helpdesk dashboard for current user."""
        is_tech = self.current_user.role in [
            UserRole.TECHNICIAN,
            UserRole.SENIOR_TECH,
            UserRole.ADMIN,
        ]

        if is_tech:
            # Tech dashboard - all tickets
            my_assigned = [
                t
                for t in self.tickets.values()
                if t.assigned_to == self.current_user.id
            ]
            open_assigned = [
                t
                for t in my_assigned
                if t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
            ]
            breached = [t for t in open_assigned if t.is_sla_breached()]

            all_open = [
                t
                for t in self.tickets.values()
                if t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
            ]
            unassigned = [t for t in all_open if not t.assigned_to]

            return {
                "success": True,
                "role": "technician",
                "dashboard": {
                    "my_open_tickets": len(open_assigned),
                    "my_sla_breached": len(breached),
                    "total_open": len(all_open),
                    "unassigned": len(unassigned),
                    "critical_tickets": len(
                        [t for t in all_open if t.priority == TicketPriority.CRITICAL]
                    ),
                    "high_priority": len(
                        [t for t in all_open if t.priority == TicketPriority.HIGH]
                    ),
                    "recent_tickets": [
                        {
                            "id": t.id,
                            "title": t.title[:40],
                            "priority": t.priority.value,
                            "status": t.status.value,
                        }
                        for t in sorted(
                            all_open, key=lambda x: x.created_at, reverse=True
                        )[:5]
                    ],
                },
            }
        else:
            # Employee dashboard - their tickets only
            my_tickets = [
                t
                for t in self.tickets.values()
                if t.requester_id == self.current_user.id
            ]
            open_tickets = [
                t
                for t in my_tickets
                if t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
            ]

            return {
                "success": True,
                "role": "employee",
                "dashboard": {
                    "my_open_tickets": len(open_tickets),
                    "my_total_tickets": len(my_tickets),
                    "pending_my_action": len(
                        [
                            t
                            for t in open_tickets
                            if t.status == TicketStatus.PENDING_USER
                        ]
                    ),
                    "recent_tickets": [
                        {"id": t.id, "title": t.title[:40], "status": t.status.value}
                        for t in sorted(
                            my_tickets, key=lambda x: x.created_at, reverse=True
                        )[:5]
                    ],
                },
            }


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT FOR AI ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an IT Helpdesk Support Assistant for a corporate enterprise.

Your role is to:
1. Help employees create and track support tickets
2. Guide users through troubleshooting steps
3. Search the knowledge base for solutions
4. Escalate issues to human technicians when needed
5. Monitor SLA compliance

You have access to these tools:
- create_ticket: Create new support tickets
- get_ticket: Get ticket details
- update_ticket: Update ticket status, add notes
- escalate_ticket: Escalate to senior technician
- list_tickets: List tickets with filters
- search_knowledge_base: Find solutions in KB
- get_article: Read full KB article
- get_troubleshooting_workflow: Get step-by-step troubleshooting
- get_sla_report: View SLA compliance report
- get_dashboard: View helpdesk dashboard

When helping users:
1. First try to solve the issue using the knowledge base
2. Guide through troubleshooting steps when possible
3. Create a ticket if the issue cannot be self-resolved
4. Set appropriate priority based on business impact
5. Escalate critical issues promptly

Be professional, patient, and thorough. Remember that some users may be frustrated - acknowledge their concerns and focus on resolution."""


# ══════════════════════════════════════════════════════════════════════════════
# AGENT TOOLS
# ══════════════════════════════════════════════════════════════════════════════


def create_helpdesk_tools(service: ITHelpdeskService) -> list:
    """Create tool definitions for the IT helpdesk agent."""
    return [
        {
            "name": "create_ticket",
            "description": "Create a new IT support ticket",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Brief title of the issue",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the problem",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: password_reset, vpn_access, email_issue, hardware, software, printer, network, security, access_request, other",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority: critical, high, medium, low",
                    },
                },
                "required": ["title", "description", "category"],
            },
            "function": lambda title, description, category, priority="medium": service.create_ticket(
                title, description, category, priority
            ),
        },
        {
            "name": "get_ticket",
            "description": "Get details of a specific support ticket",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID (e.g., TKT-100001)",
                    }
                },
                "required": ["ticket_id"],
            },
            "function": lambda ticket_id: service.get_ticket(ticket_id),
        },
        {
            "name": "update_ticket",
            "description": "Update a ticket's status, add notes, or set resolution",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "Ticket ID"},
                    "status": {
                        "type": "string",
                        "description": "New status: new, in_progress, pending_user, pending_vendor, escalated, resolved, closed",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Note to add to the ticket",
                    },
                    "resolution": {
                        "type": "string",
                        "description": "Resolution description",
                    },
                    "priority": {"type": "string", "description": "New priority level"},
                },
                "required": ["ticket_id"],
            },
            "function": lambda ticket_id, status=None, notes=None, resolution=None, priority=None: service.update_ticket(
                ticket_id, status, notes, resolution, priority
            ),
        },
        {
            "name": "escalate_ticket",
            "description": "Escalate a ticket to a senior technician",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID to escalate",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for escalation",
                    },
                },
                "required": ["ticket_id", "reason"],
            },
            "function": lambda ticket_id, reason: service.escalate_ticket(
                ticket_id, reason
            ),
        },
        {
            "name": "list_tickets",
            "description": "List tickets with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status"},
                    "priority": {"type": "string", "description": "Filter by priority"},
                    "assigned_to_me": {
                        "type": "boolean",
                        "description": "Show only tickets assigned to current user",
                    },
                    "my_tickets": {
                        "type": "boolean",
                        "description": "Show only tickets I created",
                    },
                },
            },
            "function": lambda status=None, priority=None, assigned_to_me=False, my_tickets=False: service.list_tickets(
                status, priority, assigned_to_me, my_tickets
            ),
        },
        {
            "name": "search_knowledge_base",
            "description": "Search the knowledge base for solutions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {
                        "type": "string",
                        "description": "Optional category filter",
                    },
                },
                "required": ["query"],
            },
            "function": lambda query, category=None: service.search_knowledge_base(
                query, category
            ),
        },
        {
            "name": "get_article",
            "description": "Get full knowledge base article with solution steps",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "Article ID (e.g., KB-001)",
                    }
                },
                "required": ["article_id"],
            },
            "function": lambda article_id: service.get_article(article_id),
        },
        {
            "name": "get_troubleshooting_workflow",
            "description": "Get step-by-step troubleshooting guide for an issue category",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Issue category: password_reset, vpn_access, printer, email_issue",
                    }
                },
                "required": ["category"],
            },
            "function": lambda category: service.get_troubleshooting_workflow(category),
        },
        {
            "name": "get_sla_report",
            "description": "Get SLA compliance report showing breached and at-risk tickets",
            "parameters": {"type": "object", "properties": {}},
            "function": lambda: service.get_sla_report(),
        },
        {
            "name": "get_dashboard",
            "description": "Get IT helpdesk dashboard with ticket summary",
            "parameters": {"type": "object", "properties": {}},
            "function": lambda: service.get_dashboard(),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# DEMO AND INTERACTIVE MODES
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate IT helpdesk capabilities."""
    print("=" * 70)
    print("IT HELPDESK SUPPORT BOT - DEMO MODE")
    print("=" * 70)

    service = ITHelpdeskService()

    # Show dashboard
    print("\n📊 TECHNICIAN DASHBOARD")
    print("-" * 50)
    service.switch_user("U003")  # Switch to technician
    dashboard = service.get_dashboard()
    d = dashboard["dashboard"]
    print(f"My Open Tickets: {d['my_open_tickets']}")
    print(f"SLA Breached: {d['my_sla_breached']}")
    print(f"Total Open: {d['total_open']}")
    print(f"Unassigned: {d['unassigned']}")
    print(f"Critical: {d['critical_tickets']}")

    # List all open tickets
    print("\n📋 OPEN TICKETS")
    print("-" * 50)
    result = service.list_tickets()
    for ticket in result["tickets"]:
        sla_flag = "⚠️ SLA BREACH" if ticket["sla_breached"] else ""
        print(
            f"  [{ticket['priority'].upper()}] {ticket['id']}: {ticket['title']} [{ticket['status']}] {sla_flag}"
        )

    # SLA Report
    print("\n⏱️ SLA COMPLIANCE REPORT")
    print("-" * 50)
    sla = service.get_sla_report()
    r = sla["report"]
    print(f"Total Active: {r['total_active']}")
    print(f"Compliance Rate: {r['compliance_rate']}")
    print(f"Breached: {r['sla_breached']}")
    print(f"At Risk: {r['at_risk']}")

    # Search knowledge base
    print("\n🔍 KNOWLEDGE BASE SEARCH: 'vpn connection'")
    print("-" * 50)
    kb_result = service.search_knowledge_base("vpn connection")
    for article in kb_result["articles"]:
        print(
            f"  [{article['id']}] {article['title']} (Score: {article['relevance_score']})"
        )

    # Get troubleshooting workflow
    print("\n🔧 VPN TROUBLESHOOTING WORKFLOW")
    print("-" * 50)
    workflow = service.get_troubleshooting_workflow("vpn_access")
    for step in workflow["steps"]:
        print(f"  Step {step['step']}: {step['instruction']}")
        print(f"         → If OK: {step['if_success']}, If not: {step['if_failure']}")

    # Create a new ticket
    print("\n➕ CREATING NEW TICKET")
    print("-" * 50)
    service.switch_user("U001")  # Switch to employee
    new_ticket = service.create_ticket(
        title="Outlook crashing when opening attachments",
        description="Outlook 365 crashes every time I try to open PDF attachments. Started this morning after Windows update.",
        category="software",
        priority="medium",
    )
    print(f"Created: {new_ticket['ticket_id']}")
    print(f"Priority: {new_ticket['priority']}")
    print(f"SLA Due: {new_ticket['sla_due']}")
    print(f"Assigned to: {new_ticket['assigned_to']}")

    # Get ticket details
    print("\n📄 TICKET DETAILS: TKT-100001")
    print("-" * 50)
    ticket = service.get_ticket("TKT-100001")
    t = ticket["ticket"]
    print(f"Title: {t['title']}")
    print(f"Status: {t['status']}")
    print(f"Priority: {t['priority']}")
    print(f"Requester: {t['requester']}")
    print(f"Assigned to: {t['assigned_to']}")
    print(f"SLA Status: {'BREACHED' if t['sla_breached'] else t['time_to_sla']}")

    # Escalate a ticket
    print("\n⬆️ ESCALATING TICKET TKT-100002")
    print("-" * 50)
    service.switch_user("U003")  # Switch to technician
    result = service.escalate_ticket(
        "TKT-100002", "Multiple users affected, needs senior review"
    )
    print(f"Result: {result['message']}")
    print(f"New Priority: {result['new_priority']}")

    print("\n" + "=" * 70)
    print("Demo complete! Run with --interactive for full chat mode.")
    print("=" * 70)


async def interactive():
    """Run interactive IT helpdesk chat."""
    print("=" * 70)
    print("IT HELPDESK SUPPORT BOT")
    print("=" * 70)
    print("\nWelcome to IT Support! I can help you with:")
    print("  • Report technical issues and create support tickets")
    print("  • Search our knowledge base for solutions")
    print("  • Guide you through troubleshooting steps")
    print("  • Check status of your existing tickets")
    print("\nType 'quit' to exit, 'demo' for demo mode.\n")

    service = ITHelpdeskService()
    tools = create_helpdesk_tools(service)

    # Try to import agentic-brain
    try:
        from agentic_brain import Agent

        agent = Agent(system_prompt=SYSTEM_PROMPT, tools=tools, model="gpt-4")
        use_agent = True
    except ImportError:
        print("Note: agentic-brain not installed. Running in simple mode.\n")
        use_agent = False

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("\nThank you for using IT Support. Goodbye!")
                break

            if user_input.lower() == "demo":
                await demo()
                continue

            if user_input.lower() == "dashboard":
                result = service.get_dashboard()
                print(
                    f"\n🤖 Assistant: Here's your dashboard:\n{json.dumps(result, indent=2)}"
                )
                continue

            if user_input.lower().startswith("search "):
                query = user_input[7:]
                result = service.search_knowledge_base(query)
                print(
                    f"\n🤖 Assistant: Knowledge base results:\n{json.dumps(result, indent=2)}"
                )
                continue

            if use_agent:
                response = await agent.chat(user_input)
                print(f"\n🤖 Assistant: {response}")
            else:
                # Simple mode without agent
                print("\n🤖 Assistant: I understand you need help with IT support.")
                print("   In full mode, I would use AI to understand your issue and")
                print("   guide you through troubleshooting or create a ticket.")
                print("\n   Quick commands available:")
                print("   - 'dashboard' - View your ticket dashboard")
                print("   - 'search <query>' - Search knowledge base")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(demo())


if __name__ == "__main__":
    main()
