#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
SDA Dashboard - Property Manager Command Center
===============================================

Management-by-exception dashboard for SDA property managers.
Provides real-time alerts, workflow automation, and operational oversight.

FEATURES:
- Morning alerts (arrears, vacancies, compliance due)
- Reconciliation queue status
- Distribution calculation notifications
- Property occupancy overview
- Investor communication center
- End-of-month workflow automation
- Performance metrics and KPIs

Author: Agentic Brain Framework
License: MIT
"""

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class AlertPriority(Enum):
    """Alert priority levels."""

    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # Action within hours
    MEDIUM = "medium"  # Action within 24 hours
    LOW = "low"  # Informational
    INFO = "info"  # FYI only


class AlertCategory(Enum):
    """Categories of alerts."""

    ARREARS = "arrears"
    VACANCY = "vacancy"
    COMPLIANCE = "compliance"
    MAINTENANCE = "maintenance"
    RECONCILIATION = "reconciliation"
    DISTRIBUTION = "distribution"
    INVESTOR = "investor"
    LEASE = "lease"
    SYSTEM = "system"


class WorkflowStatus(Enum):
    """Workflow status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class OccupancyStatus(Enum):
    """Property occupancy status."""

    OCCUPIED = "occupied"
    VACANT = "vacant"
    NOTICE_GIVEN = "notice_given"
    MAINTENANCE = "maintenance"
    ONBOARDING = "onboarding"


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class Alert:
    """Dashboard alert."""

    alert_id: str
    category: AlertCategory
    priority: AlertPriority
    title: str
    message: str
    property_id: Optional[str] = None
    entity_id: Optional[str] = None  # tenant_id, owner_id, etc.
    created_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[date] = None
    is_acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    action_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowStep:
    """Individual step in a workflow."""

    step_id: str
    name: str
    description: str
    order: int
    status: WorkflowStatus = WorkflowStatus.PENDING
    assigned_to: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    blockers: List[str] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    """Automated workflow."""

    workflow_id: str
    name: str
    description: str
    workflow_type: str  # "end_of_month", "onboarding", "compliance", etc.
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def progress_percent(self) -> int:
        if not self.steps:
            return 0
        completed = len([s for s in self.steps if s.status == WorkflowStatus.COMPLETED])
        return int((completed / len(self.steps)) * 100)


@dataclass
class PropertyStatus:
    """Real-time property status."""

    property_id: str
    address: str
    suburb: str
    sda_category: str
    occupancy_status: OccupancyStatus
    current_tenant: Optional[str] = None
    monthly_income: Decimal = Decimal("0")
    arrears_amount: Decimal = Decimal("0")
    next_compliance_due: Optional[date] = None
    last_inspection: Optional[date] = None
    investor_count: int = 0
    alerts_count: int = 0

    def __post_init__(self):
        self.monthly_income = Decimal(str(self.monthly_income))
        self.arrears_amount = Decimal(str(self.arrears_amount))


@dataclass
class ReconciliationQueueItem:
    """Item in reconciliation queue."""

    item_id: str
    transaction_date: date
    description: str
    amount: Decimal
    source: str  # bank name or source
    status: str  # matched, unmatched, exception
    suggested_match: Optional[str] = None
    confidence_score: float = 0.0
    added_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.amount = Decimal(str(self.amount))


@dataclass
class DistributionBatch:
    """Distribution calculation batch."""

    batch_id: str
    period_start: date
    period_end: date
    status: str  # pending, calculating, ready, approved, paid
    property_count: int
    investor_count: int
    total_distributions: Decimal
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    def __post_init__(self):
        self.total_distributions = Decimal(str(self.total_distributions))


@dataclass
class KPIMetric:
    """Key Performance Indicator metric."""

    name: str
    value: float
    target: float
    unit: str
    trend: str  # up, down, stable
    period: str  # daily, weekly, monthly
    description: str = ""

    @property
    def performance_percent(self) -> float:
        if self.target == 0:
            return 0
        return (self.value / self.target) * 100


# ============================================================================
# ALERT MANAGER
# ============================================================================


class AlertManager:
    """
    Manages dashboard alerts and notifications.

    Features:
    - Priority-based alert queue
    - Auto-escalation
    - Acknowledgment tracking
    - Alert aggregation
    """

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.subscribers: List[Callable] = []

    def create_alert(
        self,
        category: AlertCategory,
        priority: AlertPriority,
        title: str,
        message: str,
        property_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        due_date: Optional[date] = None,
        metadata: Optional[Dict] = None,
    ) -> Alert:
        """Create a new alert."""
        alert_id = (
            f"ALT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.alerts):04d}"
        )

        alert = Alert(
            alert_id=alert_id,
            category=category,
            priority=priority,
            title=title,
            message=message,
            property_id=property_id,
            entity_id=entity_id,
            due_date=due_date,
            metadata=metadata or {},
        )

        self.alerts[alert_id] = alert
        self._notify_subscribers(alert)

        logger.info(f"Alert created: {alert_id} - {title}")
        return alert

    def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """Acknowledge an alert."""
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.is_acknowledged = True
        alert.acknowledged_by = user
        alert.acknowledged_at = datetime.now()

        logger.info(f"Alert {alert_id} acknowledged by {user}")
        return True

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.is_resolved = True
        alert.resolved_at = datetime.now()

        logger.info(f"Alert {alert_id} resolved")
        return True

    def get_active_alerts(
        self,
        category: Optional[AlertCategory] = None,
        priority: Optional[AlertPriority] = None,
        property_id: Optional[str] = None,
    ) -> List[Alert]:
        """Get active (unresolved) alerts with optional filters."""
        alerts = [a for a in self.alerts.values() if not a.is_resolved]

        if category:
            alerts = [a for a in alerts if a.category == category]
        if priority:
            alerts = [a for a in alerts if a.priority == priority]
        if property_id:
            alerts = [a for a in alerts if a.property_id == property_id]

        # Sort by priority (critical first) then by date
        priority_order = {
            AlertPriority.CRITICAL: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3,
            AlertPriority.INFO: 4,
        }

        return sorted(alerts, key=lambda a: (priority_order[a.priority], a.created_at))

    def get_morning_briefing(self) -> Dict[str, Any]:
        """Generate morning briefing summary."""
        active = self.get_active_alerts()

        return {
            "total_alerts": len(active),
            "critical": len(
                [a for a in active if a.priority == AlertPriority.CRITICAL]
            ),
            "high": len([a for a in active if a.priority == AlertPriority.HIGH]),
            "medium": len([a for a in active if a.priority == AlertPriority.MEDIUM]),
            "low": len([a for a in active if a.priority == AlertPriority.LOW]),
            "by_category": self._count_by_category(active),
            "overdue_actions": len(
                [a for a in active if a.due_date and a.due_date < date.today()]
            ),
            "unacknowledged": len([a for a in active if not a.is_acknowledged]),
        }

    def _count_by_category(self, alerts: List[Alert]) -> Dict[str, int]:
        """Count alerts by category."""
        counts = {}
        for alert in alerts:
            cat = alert.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def subscribe(self, callback: Callable):
        """Subscribe to new alerts."""
        self.subscribers.append(callback)

    def _notify_subscribers(self, alert: Alert):
        """Notify all subscribers of new alert."""
        for callback in self.subscribers:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")


# ============================================================================
# WORKFLOW ENGINE
# ============================================================================


class WorkflowEngine:
    """
    Manages automated workflows.

    Features:
    - Workflow templates
    - Step sequencing
    - Blocker management
    - Progress tracking
    """

    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.templates: Dict[str, Dict] = {}

        self._load_default_templates()

    def _load_default_templates(self):
        """Load default workflow templates."""
        self.templates = {
            "end_of_month": {
                "name": "End of Month Processing",
                "description": "Monthly financial close workflow",
                "steps": [
                    {
                        "name": "Reconcile Transactions",
                        "description": "Complete bank reconciliation",
                    },
                    {
                        "name": "Review Exceptions",
                        "description": "Handle unmatched transactions",
                    },
                    {
                        "name": "Calculate Distributions",
                        "description": "Calculate investor distributions",
                    },
                    {
                        "name": "Generate Statements",
                        "description": "Create investor statements",
                    },
                    {
                        "name": "Approve Distributions",
                        "description": "Get management approval",
                    },
                    {
                        "name": "Generate ABA File",
                        "description": "Create bulk payment file",
                    },
                    {
                        "name": "Process Payments",
                        "description": "Upload ABA and confirm payments",
                    },
                    {
                        "name": "Archive Period",
                        "description": "Archive month-end reports",
                    },
                ],
            },
            "tenant_onboarding": {
                "name": "Tenant Onboarding",
                "description": "New tenant setup workflow",
                "steps": [
                    {
                        "name": "NDIS Verification",
                        "description": "Verify NDIS plan and SDA funding",
                    },
                    {
                        "name": "Documentation Collection",
                        "description": "Collect required documents",
                    },
                    {
                        "name": "Lease Preparation",
                        "description": "Prepare SDA lease agreement",
                    },
                    {"name": "Lease Signing", "description": "Execute lease agreement"},
                    {
                        "name": "Bond Processing",
                        "description": "Collect and lodge bond",
                    },
                    {
                        "name": "Property Induction",
                        "description": "Property walkthrough and keys",
                    },
                    {
                        "name": "Service Coordination",
                        "description": "Setup with support coordinator",
                    },
                    {
                        "name": "System Setup",
                        "description": "Create tenant in financial system",
                    },
                ],
            },
            "compliance_audit": {
                "name": "Compliance Audit Preparation",
                "description": "SDA compliance audit workflow",
                "steps": [
                    {
                        "name": "Document Assembly",
                        "description": "Gather all compliance documents",
                    },
                    {
                        "name": "Registration Check",
                        "description": "Verify SDA registration status",
                    },
                    {
                        "name": "Safety Compliance",
                        "description": "Check fire safety, smoke alarms",
                    },
                    {
                        "name": "Building Standards",
                        "description": "Review building certification",
                    },
                    {
                        "name": "Worker Screening",
                        "description": "Verify all worker clearances",
                    },
                    {
                        "name": "Incident Register",
                        "description": "Review incident records",
                    },
                    {
                        "name": "Self-Assessment",
                        "description": "Complete pre-audit checklist",
                    },
                    {
                        "name": "Schedule Audit",
                        "description": "Book auditor appointment",
                    },
                ],
            },
            "vacancy_management": {
                "name": "Vacancy Management",
                "description": "Property vacancy filling workflow",
                "steps": [
                    {
                        "name": "Exit Inspection",
                        "description": "Complete exit condition report",
                    },
                    {
                        "name": "Maintenance Review",
                        "description": "Identify required repairs",
                    },
                    {
                        "name": "Property Preparation",
                        "description": "Complete make-ready works",
                    },
                    {
                        "name": "Marketing Listing",
                        "description": "List on SDA platforms",
                    },
                    {
                        "name": "Applicant Screening",
                        "description": "Review NDIS applicants",
                    },
                    {
                        "name": "Property Viewings",
                        "description": "Conduct property inspections",
                    },
                    {"name": "Application Approval", "description": "Select tenant"},
                    {
                        "name": "Commence Onboarding",
                        "description": "Start tenant onboarding",
                    },
                ],
            },
        }

    def create_workflow(
        self,
        template_name: str,
        metadata: Optional[Dict] = None,
        created_by: str = "system",
    ) -> Optional[Workflow]:
        """Create workflow from template."""
        if template_name not in self.templates:
            logger.error(f"Unknown template: {template_name}")
            return None

        template = self.templates[template_name]
        workflow_id = (
            f"WF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.workflows):04d}"
        )

        steps = []
        for i, step_def in enumerate(template["steps"]):
            step = WorkflowStep(
                step_id=f"{workflow_id}-S{i+1:02d}",
                name=step_def["name"],
                description=step_def["description"],
                order=i + 1,
            )
            steps.append(step)

        workflow = Workflow(
            workflow_id=workflow_id,
            name=template["name"],
            description=template["description"],
            workflow_type=template_name,
            steps=steps,
            created_by=created_by,
            metadata=metadata or {},
        )

        self.workflows[workflow_id] = workflow
        logger.info(f"Workflow created: {workflow_id} - {workflow.name}")
        return workflow

    def start_workflow(self, workflow_id: str) -> bool:
        """Start a workflow."""
        if workflow_id not in self.workflows:
            return False

        workflow = self.workflows[workflow_id]
        workflow.status = WorkflowStatus.IN_PROGRESS
        workflow.started_at = datetime.now()

        # Start first step
        if workflow.steps:
            workflow.steps[0].status = WorkflowStatus.IN_PROGRESS
            workflow.steps[0].started_at = datetime.now()

        logger.info(f"Workflow {workflow_id} started")
        return True

    def complete_step(
        self, workflow_id: str, step_id: str, outputs: Optional[Dict] = None
    ) -> bool:
        """Complete a workflow step."""
        if workflow_id not in self.workflows:
            return False

        workflow = self.workflows[workflow_id]
        step = next((s for s in workflow.steps if s.step_id == step_id), None)

        if not step:
            return False

        step.status = WorkflowStatus.COMPLETED
        step.completed_at = datetime.now()
        step.outputs = outputs or {}

        # Start next step
        next_step = next((s for s in workflow.steps if s.order == step.order + 1), None)

        if next_step:
            next_step.status = WorkflowStatus.IN_PROGRESS
            next_step.started_at = datetime.now()
        else:
            # Workflow complete
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()

        logger.info(f"Step {step_id} completed")
        return True

    def block_step(self, workflow_id: str, step_id: str, reason: str) -> bool:
        """Block a workflow step."""
        if workflow_id not in self.workflows:
            return False

        workflow = self.workflows[workflow_id]
        step = next((s for s in workflow.steps if s.step_id == step_id), None)

        if not step:
            return False

        step.status = WorkflowStatus.BLOCKED
        step.blockers.append(reason)
        workflow.status = WorkflowStatus.BLOCKED

        logger.info(f"Step {step_id} blocked: {reason}")
        return True

    def get_active_workflows(self) -> List[Workflow]:
        """Get all active (in-progress or blocked) workflows."""
        return [
            w
            for w in self.workflows.values()
            if w.status in [WorkflowStatus.IN_PROGRESS, WorkflowStatus.BLOCKED]
        ]

    def get_workflow_summary(self, workflow_id: str) -> Optional[Dict]:
        """Get summary of a workflow."""
        if workflow_id not in self.workflows:
            return None

        workflow = self.workflows[workflow_id]

        return {
            "workflow_id": workflow.workflow_id,
            "name": workflow.name,
            "status": workflow.status.value,
            "progress_percent": workflow.progress_percent,
            "total_steps": len(workflow.steps),
            "completed_steps": len(
                [s for s in workflow.steps if s.status == WorkflowStatus.COMPLETED]
            ),
            "blocked_steps": len(
                [s for s in workflow.steps if s.status == WorkflowStatus.BLOCKED]
            ),
            "current_step": next(
                (
                    s.name
                    for s in workflow.steps
                    if s.status == WorkflowStatus.IN_PROGRESS
                ),
                None,
            ),
            "blockers": [b for s in workflow.steps for b in s.blockers],
        }


# ============================================================================
# DASHBOARD ENGINE
# ============================================================================


class SDADashboard:
    """
    Main dashboard for SDA property management.

    Provides:
    - Real-time property status
    - Alert management
    - Workflow automation
    - KPI tracking
    - End-of-month processing
    """

    def __init__(self, company_name: str = "SDA Housing Provider Pty Ltd"):
        self.company_name = company_name
        self.alert_manager = AlertManager()
        self.workflow_engine = WorkflowEngine()

        # Data stores
        self.property_statuses: Dict[str, PropertyStatus] = {}
        self.reconciliation_queue: List[ReconciliationQueueItem] = []
        self.distribution_batches: Dict[str, DistributionBatch] = {}
        self.kpis: Dict[str, KPIMetric] = {}

        # Initialize KPIs
        self._initialize_kpis()

    def _initialize_kpis(self):
        """Initialize default KPIs."""
        self.kpis = {
            "occupancy_rate": KPIMetric(
                name="Occupancy Rate",
                value=0.0,
                target=95.0,
                unit="%",
                trend="stable",
                period="monthly",
                description="Percentage of properties occupied",
            ),
            "collection_rate": KPIMetric(
                name="Rent Collection Rate",
                value=0.0,
                target=98.0,
                unit="%",
                trend="stable",
                period="monthly",
                description="Percentage of rent collected on time",
            ),
            "arrears_total": KPIMetric(
                name="Total Arrears",
                value=0.0,
                target=5000.0,  # Target to stay below
                unit="$",
                trend="stable",
                period="monthly",
                description="Total outstanding arrears amount",
            ),
            "reconciliation_rate": KPIMetric(
                name="Auto-Match Rate",
                value=0.0,
                target=95.0,
                unit="%",
                trend="stable",
                period="monthly",
                description="Percentage of transactions auto-matched",
            ),
            "compliance_score": KPIMetric(
                name="Compliance Score",
                value=0.0,
                target=100.0,
                unit="%",
                trend="stable",
                period="monthly",
                description="Overall compliance rating",
            ),
            "investor_satisfaction": KPIMetric(
                name="Investor Satisfaction",
                value=0.0,
                target=90.0,
                unit="%",
                trend="stable",
                period="quarterly",
                description="Investor satisfaction score",
            ),
        }

    def update_property_status(self, status: PropertyStatus):
        """Update property status."""
        self.property_statuses[status.property_id] = status

        # Create alerts based on status
        if status.occupancy_status == OccupancyStatus.VACANT:
            self.alert_manager.create_alert(
                AlertCategory.VACANCY,
                AlertPriority.HIGH,
                f"Vacancy: {status.address}",
                f"Property at {status.address}, {status.suburb} is vacant",
                property_id=status.property_id,
            )

        if status.arrears_amount > 500:
            priority = (
                AlertPriority.CRITICAL
                if status.arrears_amount > 2000
                else AlertPriority.HIGH
            )
            self.alert_manager.create_alert(
                AlertCategory.ARREARS,
                priority,
                f"Arrears: ${status.arrears_amount:.2f}",
                f"Tenant at {status.address} has ${status.arrears_amount:.2f} outstanding",
                property_id=status.property_id,
                entity_id=status.current_tenant,
            )

        if (
            status.next_compliance_due
            and status.next_compliance_due <= date.today() + timedelta(days=30)
        ):
            self.alert_manager.create_alert(
                AlertCategory.COMPLIANCE,
                AlertPriority.MEDIUM,
                f"Compliance Due: {status.address}",
                f"Compliance check due on {status.next_compliance_due}",
                property_id=status.property_id,
                due_date=status.next_compliance_due,
            )

    def add_reconciliation_item(self, item: ReconciliationQueueItem):
        """Add item to reconciliation queue."""
        self.reconciliation_queue.append(item)

        if item.status == "exception":
            self.alert_manager.create_alert(
                AlertCategory.RECONCILIATION,
                AlertPriority.MEDIUM,
                f"Reconciliation Exception: ${item.amount}",
                f"Transaction '{item.description}' requires manual review",
                metadata={"transaction_id": item.item_id},
            )

    def create_distribution_batch(
        self,
        period_start: date,
        period_end: date,
        property_count: int,
        investor_count: int,
        total_amount: Decimal,
    ) -> DistributionBatch:
        """Create a new distribution batch."""
        batch_id = f"BATCH-{period_end.strftime('%Y%m')}"

        batch = DistributionBatch(
            batch_id=batch_id,
            period_start=period_start,
            period_end=period_end,
            status="ready",
            property_count=property_count,
            investor_count=investor_count,
            total_distributions=total_amount,
        )

        self.distribution_batches[batch_id] = batch

        self.alert_manager.create_alert(
            AlertCategory.DISTRIBUTION,
            AlertPriority.MEDIUM,
            f"Distributions Ready: {period_end.strftime('%B %Y')}",
            f"{investor_count} distributions totaling ${total_amount:,.2f} ready for approval",
            metadata={"batch_id": batch_id},
        )

        return batch

    def approve_distribution_batch(self, batch_id: str, approved_by: str) -> bool:
        """Approve a distribution batch."""
        if batch_id not in self.distribution_batches:
            return False

        batch = self.distribution_batches[batch_id]
        batch.status = "approved"
        batch.approved_by = approved_by
        batch.approved_at = datetime.now()

        logger.info(f"Distribution batch {batch_id} approved by {approved_by}")
        return True

    def update_kpi(self, kpi_name: str, value: float, trend: str = "stable"):
        """Update a KPI value."""
        if kpi_name in self.kpis:
            self.kpis[kpi_name].value = value
            self.kpis[kpi_name].trend = trend

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get complete dashboard summary."""
        active_alerts = self.alert_manager.get_active_alerts()
        active_workflows = self.workflow_engine.get_active_workflows()

        # Calculate occupancy
        occupied = len(
            [
                p
                for p in self.property_statuses.values()
                if p.occupancy_status == OccupancyStatus.OCCUPIED
            ]
        )
        total_props = len(self.property_statuses)
        occupancy_rate = (occupied / total_props * 100) if total_props > 0 else 0

        # Calculate total arrears
        total_arrears = sum(p.arrears_amount for p in self.property_statuses.values())

        return {
            "company": self.company_name,
            "timestamp": datetime.now().isoformat(),
            "properties": {
                "total": total_props,
                "occupied": occupied,
                "vacant": len(
                    [
                        p
                        for p in self.property_statuses.values()
                        if p.occupancy_status == OccupancyStatus.VACANT
                    ]
                ),
                "occupancy_rate": f"{occupancy_rate:.1f}%",
            },
            "financials": {
                "total_arrears": f"${total_arrears:,.2f}",
                "reconciliation_queue": len(self.reconciliation_queue),
                "unmatched_transactions": len(
                    [r for r in self.reconciliation_queue if r.status == "unmatched"]
                ),
                "pending_distributions": len(
                    [
                        b
                        for b in self.distribution_batches.values()
                        if b.status == "ready"
                    ]
                ),
            },
            "alerts": {
                "total_active": len(active_alerts),
                "critical": len(
                    [a for a in active_alerts if a.priority == AlertPriority.CRITICAL]
                ),
                "high": len(
                    [a for a in active_alerts if a.priority == AlertPriority.HIGH]
                ),
                "unacknowledged": len(
                    [a for a in active_alerts if not a.is_acknowledged]
                ),
            },
            "workflows": {
                "active": len(active_workflows),
                "blocked": len(
                    [w for w in active_workflows if w.status == WorkflowStatus.BLOCKED]
                ),
            },
            "kpis": {
                name: {
                    "value": f"{kpi.value:.1f}{kpi.unit}",
                    "target": f"{kpi.target:.1f}{kpi.unit}",
                    "performance": f"{kpi.performance_percent:.0f}%",
                    "trend": kpi.trend,
                }
                for name, kpi in self.kpis.items()
            },
        }

    def get_morning_briefing(self) -> str:
        """Generate morning briefing text."""
        summary = self.get_dashboard_summary()
        alerts = self.alert_manager.get_morning_briefing()

        briefing = f"""
================================================================================
                        MORNING BRIEFING - {datetime.now().strftime('%A, %B %d, %Y')}
                        {self.company_name}
================================================================================

📊 PORTFOLIO OVERVIEW
---------------------
Properties: {summary['properties']['total']} total
  • Occupied: {summary['properties']['occupied']}
  • Vacant: {summary['properties']['vacant']}
  • Occupancy Rate: {summary['properties']['occupancy_rate']}

💰 FINANCIAL STATUS
-------------------
Total Arrears: {summary['financials']['total_arrears']}
Reconciliation Queue: {summary['financials']['reconciliation_queue']} items
  • Unmatched: {summary['financials']['unmatched_transactions']}
Pending Distributions: {summary['financials']['pending_distributions']} batches

🚨 ALERTS REQUIRING ATTENTION
-----------------------------
Total Active: {alerts['total_alerts']}
  • 🔴 Critical: {alerts['critical']}
  • 🟠 High: {alerts['high']}
  • 🟡 Medium: {alerts['medium']}
  • 🟢 Low: {alerts['low']}

Unacknowledged: {alerts['unacknowledged']}
Overdue Actions: {alerts['overdue_actions']}

📋 ACTIVE WORKFLOWS
-------------------
In Progress: {summary['workflows']['active']}
Blocked: {summary['workflows']['blocked']}

📈 KEY PERFORMANCE INDICATORS
-----------------------------
"""
        for name, kpi in summary["kpis"].items():
            icon = "✅" if float(kpi["performance"].replace("%", "")) >= 100 else "⚠️"
            briefing += f"{icon} {name.replace('_', ' ').title()}: {kpi['value']} (Target: {kpi['target']}, {kpi['trend']})\n"

        briefing += """
================================================================================
                              END OF BRIEFING
================================================================================
"""
        return briefing

    def start_end_of_month_workflow(self, user: str = "system") -> Workflow:
        """Start end-of-month processing workflow."""
        workflow = self.workflow_engine.create_workflow(
            "end_of_month",
            metadata={"period": datetime.now().strftime("%Y-%m")},
            created_by=user,
        )

        if workflow:
            self.workflow_engine.start_workflow(workflow.workflow_id)

            self.alert_manager.create_alert(
                AlertCategory.SYSTEM,
                AlertPriority.INFO,
                "End of Month Started",
                f"End of month workflow {workflow.workflow_id} has been initiated",
                metadata={"workflow_id": workflow.workflow_id},
            )

        return workflow


# ============================================================================
# DEMO DATA GENERATOR
# ============================================================================


def generate_demo_data() -> SDADashboard:
    """Generate demo data for testing."""
    dashboard = SDADashboard("Accessible Homes Property Co")

    # Add property statuses
    properties = [
        PropertyStatus(
            property_id="PROP-001",
            address="Unit 1, 42 Example Street",
            suburb="Sampletown",
            sda_category="high_physical_support",
            occupancy_status=OccupancyStatus.OCCUPIED,
            current_tenant="TEN-001",
            monthly_income=Decimal("4850.00"),
            arrears_amount=Decimal("0"),
            next_compliance_due=date.today() + timedelta(days=45),
            last_inspection=date.today() - timedelta(days=60),
            investor_count=4,
        ),
        PropertyStatus(
            property_id="PROP-002",
            address="3/88 Demo Road",
            suburb="Testville",
            sda_category="fully_accessible",
            occupancy_status=OccupancyStatus.OCCUPIED,
            current_tenant="TEN-002",
            monthly_income=Decimal("4420.00"),
            arrears_amount=Decimal("875.50"),
            next_compliance_due=date.today() + timedelta(days=15),
            last_inspection=date.today() - timedelta(days=90),
            investor_count=1,
        ),
        PropertyStatus(
            property_id="PROP-003",
            address="15 Showcase Avenue",
            suburb="Exampleville",
            sda_category="robust",
            occupancy_status=OccupancyStatus.VACANT,
            monthly_income=Decimal("0"),
            arrears_amount=Decimal("0"),
            next_compliance_due=date.today() + timedelta(days=120),
            last_inspection=date.today() - timedelta(days=30),
            investor_count=2,
        ),
        PropertyStatus(
            property_id="PROP-004",
            address="7/22 Sample Lane",
            suburb="Demoburg",
            sda_category="improved_liveability",
            occupancy_status=OccupancyStatus.NOTICE_GIVEN,
            current_tenant="TEN-004",
            monthly_income=Decimal("3200.00"),
            arrears_amount=Decimal("2450.00"),
            next_compliance_due=date.today() - timedelta(days=5),  # Overdue!
            last_inspection=date.today() - timedelta(days=180),
            investor_count=3,
        ),
    ]

    for prop in properties:
        dashboard.update_property_status(prop)

    # Add reconciliation items
    recon_items = [
        ReconciliationQueueItem(
            item_id="TXN-001",
            transaction_date=date.today() - timedelta(days=2),
            description="NDIS PAYMENT - UNKNOWN REF",
            amount=Decimal("3245.50"),
            source="CommBank",
            status="unmatched",
            confidence_score=0.3,
        ),
        ReconciliationQueueItem(
            item_id="TXN-002",
            transaction_date=date.today() - timedelta(days=1),
            description="DIRECT CREDIT - PARTIAL PAYMENT",
            amount=Decimal("500.00"),
            source="CommBank",
            status="exception",
            suggested_match="INV-TEN2-202503",
            confidence_score=0.6,
        ),
    ]

    for item in recon_items:
        dashboard.add_reconciliation_item(item)

    # Create pending distribution batch
    dashboard.create_distribution_batch(
        period_start=date(2025, 2, 1),
        period_end=date(2025, 2, 28),
        property_count=4,
        investor_count=10,
        total_amount=Decimal("45678.90"),
    )

    # Update KPIs
    dashboard.update_kpi("occupancy_rate", 75.0, "down")
    dashboard.update_kpi("collection_rate", 94.5, "stable")
    dashboard.update_kpi("arrears_total", 3325.50, "up")
    dashboard.update_kpi("reconciliation_rate", 92.0, "stable")
    dashboard.update_kpi("compliance_score", 88.0, "down")
    dashboard.update_kpi("investor_satisfaction", 87.5, "stable")

    # Start a workflow
    workflow = dashboard.workflow_engine.create_workflow(
        "vacancy_management",
        metadata={"property_id": "PROP-003"},
    )
    dashboard.workflow_engine.start_workflow(workflow.workflow_id)

    return dashboard


# ============================================================================
# DEMO RUNNER
# ============================================================================


def run_demo():
    """Run comprehensive dashboard demo."""
    print("=" * 80)
    print("     SDA DASHBOARD - PROPERTY MANAGER COMMAND CENTER")
    print("     Management-by-Exception Dashboard")
    print("=" * 80)
    print()

    # Initialize with demo data
    print("📊 Initializing dashboard with demo data...")
    dashboard = generate_demo_data()
    print(f"   ✓ Company: {dashboard.company_name}")
    print(f"   ✓ Properties: {len(dashboard.property_statuses)}")
    print(f"   ✓ Active Alerts: {len(dashboard.alert_manager.get_active_alerts())}")
    print()

    # Show morning briefing
    print("📋 MORNING BRIEFING")
    print(dashboard.get_morning_briefing())

    # Show active alerts
    print("\n🚨 ACTIVE ALERTS (Top 5)")
    print("-" * 80)
    alerts = dashboard.alert_manager.get_active_alerts()[:5]
    for alert in alerts:
        priority_icons = {
            AlertPriority.CRITICAL: "🔴",
            AlertPriority.HIGH: "🟠",
            AlertPriority.MEDIUM: "🟡",
            AlertPriority.LOW: "🟢",
            AlertPriority.INFO: "ℹ️",
        }
        icon = priority_icons.get(alert.priority, "⚪")
        print(f"   {icon} [{alert.category.value.upper()}] {alert.title}")
        print(f"      {alert.message}")
        print(f"      Created: {alert.created_at.strftime('%Y-%m-%d %H:%M')}")
        print()

    # Show reconciliation queue
    print("🏦 RECONCILIATION QUEUE")
    print("-" * 80)
    for item in dashboard.reconciliation_queue:
        status_icon = "❓" if item.status == "unmatched" else "⚠️"
        print(f"   {status_icon} {item.description}")
        print(f"      Amount: ${item.amount:,.2f} | Date: {item.transaction_date}")
        print(f"      Status: {item.status} | Confidence: {item.confidence_score:.0%}")
        print()

    # Show distribution batches
    print("💰 DISTRIBUTION BATCHES")
    print("-" * 80)
    for batch_id, batch in dashboard.distribution_batches.items():
        print(f"   📦 {batch_id}")
        print(f"      Period: {batch.period_start} to {batch.period_end}")
        print(
            f"      Properties: {batch.property_count} | Investors: {batch.investor_count}"
        )
        print(f"      Total: ${batch.total_distributions:,.2f}")
        print(f"      Status: {batch.status.upper()}")
        print()

    # Show active workflows
    print("📋 ACTIVE WORKFLOWS")
    print("-" * 80)
    workflows = dashboard.workflow_engine.get_active_workflows()
    for wf in workflows:
        summary = dashboard.workflow_engine.get_workflow_summary(wf.workflow_id)
        print(f"   📝 {wf.name} ({wf.workflow_id})")
        print(
            f"      Progress: {summary['progress_percent']}% ({summary['completed_steps']}/{summary['total_steps']} steps)"
        )
        print(f"      Current Step: {summary['current_step']}")
        print(f"      Status: {summary['status']}")
        print()

    # Demonstrate end-of-month workflow
    print("🗓️ STARTING END-OF-MONTH WORKFLOW")
    print("-" * 80)
    eom_workflow = dashboard.start_end_of_month_workflow("PropertyManager")
    if eom_workflow:
        summary = dashboard.workflow_engine.get_workflow_summary(
            eom_workflow.workflow_id
        )
        print(f"   ✓ Workflow started: {eom_workflow.workflow_id}")
        print(f"   ✓ First step: {summary['current_step']}")
        print()

        # Complete first step
        first_step = eom_workflow.steps[0]
        dashboard.workflow_engine.complete_step(
            eom_workflow.workflow_id,
            first_step.step_id,
            outputs={"matched": 45, "exceptions": 3},
        )
        print(f"   ✓ Completed: {first_step.name}")

        summary = dashboard.workflow_engine.get_workflow_summary(
            eom_workflow.workflow_id
        )
        print(f"   ✓ Progress: {summary['progress_percent']}%")
        print(f"   ✓ Next step: {summary['current_step']}")
    print()

    # Final dashboard summary
    print("📊 DASHBOARD SUMMARY")
    print("-" * 80)
    summary = dashboard.get_dashboard_summary()
    print(json.dumps(summary, indent=2, default=str))
    print()

    print("=" * 80)
    print("                    DEMO COMPLETE")
    print("=" * 80)

    return dashboard


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SDA Dashboard - Property Manager Command Center"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Run demo mode with sample data"
    )
    parser.add_argument(
        "--briefing", action="store_true", help="Generate morning briefing"
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.briefing:
        dashboard = generate_demo_data()
        print(dashboard.get_morning_briefing())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
