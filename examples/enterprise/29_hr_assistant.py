#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 29: HR & People Operations Bot

An enterprise HR assistant:
- Policy questions (leave, benefits, expenses)
- Onboarding checklists for new hires
- Time-off requests and approvals
- Employee directory search
- Training and development queries

Key patterns demonstrated:
- Policy knowledge base integration
- Workflow automation for onboarding
- Approval chains for requests
- Role-based data access (employee vs HR vs manager)
- Confidential data handling

Usage:
    python examples/29_hr_assistant.py

Requirements:
    pip install agentic-brain
"""

import asyncio
import json
import random
import string
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class LeaveType(Enum):
    """Types of leave."""

    ANNUAL = "annual"
    SICK = "sick"
    PERSONAL = "personal"
    PARENTAL = "parental"
    BEREAVEMENT = "bereavement"
    UNPAID = "unpaid"
    PUBLIC_HOLIDAY = "public_holiday"


class RequestStatus(Enum):
    """Status of requests."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class EmployeeStatus(Enum):
    """Employee status."""

    ACTIVE = "active"
    ONBOARDING = "onboarding"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class UserRole(Enum):
    """System user roles."""

    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR = "hr"
    ADMIN = "admin"


class OnboardingTaskStatus(Enum):
    """Onboarding task status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class Employee:
    """Employee record."""

    id: str
    email: str
    name: str
    department: str
    title: str
    manager_id: str
    role: UserRole
    start_date: date
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    phone: str = ""
    location: str = ""
    team: str = ""
    annual_leave_balance: float = 20.0
    sick_leave_balance: float = 10.0
    personal_leave_balance: float = 3.0


@dataclass
class LeaveRequest:
    """Leave request."""

    id: str
    employee_id: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    days: float
    reason: str
    status: RequestStatus = RequestStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: str = ""
    approved_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class OnboardingTask:
    """Onboarding checklist task."""

    id: str
    title: str
    description: str
    category: str  # IT, HR, Team, Compliance, etc.
    responsible_role: str  # who completes this
    due_day: int  # days from start date
    status: OnboardingTaskStatus = OnboardingTaskStatus.PENDING
    completed_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class OnboardingPlan:
    """New hire onboarding plan."""

    employee_id: str
    tasks: list[OnboardingTask] = field(default_factory=list)
    progress_percent: float = 0.0
    start_date: date = field(default_factory=date.today)


@dataclass
class PolicyDocument:
    """HR policy document."""

    id: str
    title: str
    category: str
    summary: str
    content: str
    keywords: list
    effective_date: date
    last_reviewed: date
    version: str = "1.0"


@dataclass
class TrainingCourse:
    """Training course."""

    id: str
    title: str
    description: str
    category: str
    duration_hours: float
    mandatory: bool
    provider: str = "Internal"
    url: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# HR SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class HRService:
    """Enterprise HR service."""

    def __init__(self):
        """Initialize with demo data."""
        self.employees: dict[str, Employee] = {}
        self.leave_requests: dict[str, LeaveRequest] = {}
        self.onboarding_plans: dict[str, OnboardingPlan] = {}
        self.policies: dict[str, PolicyDocument] = {}
        self.courses: dict[str, TrainingCourse] = {}
        self.current_user: Optional[Employee] = None
        self._load_demo_data()

    def _generate_id(self, prefix: str = "REQ") -> str:
        """Generate unique ID."""
        suffix = "".join(random.choices(string.digits, k=6))
        return f"{prefix}-{suffix}"

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo employees
        employees = [
            Employee(
                "E001",
                "alice.johnson@company.com",
                "Alice Johnson",
                "Engineering",
                "Software Engineer",
                "E005",
                UserRole.EMPLOYEE,
                date(2022, 3, 15),
                phone="x1001",
                location="Building A",
                team="Platform",
            ),
            Employee(
                "E002",
                "bob.smith@company.com",
                "Bob Smith",
                "Marketing",
                "Marketing Manager",
                "E006",
                UserRole.MANAGER,
                date(2021, 6, 1),
                phone="x2001",
                location="Building B",
                team="Brand",
            ),
            Employee(
                "E003",
                "carol.white@company.com",
                "Carol White",
                "HR",
                "HR Specialist",
                "E007",
                UserRole.HR,
                date(2020, 1, 10),
                phone="x3001",
                location="Building A",
                team="People Ops",
            ),
            Employee(
                "E004",
                "david.chen@company.com",
                "David Chen",
                "Engineering",
                "Junior Developer",
                "E005",
                UserRole.EMPLOYEE,
                date(2024, 1, 8),
                EmployeeStatus.ONBOARDING,
                phone="x1002",
                location="Building A",
                team="Platform",
            ),
            Employee(
                "E005",
                "eva.martinez@company.com",
                "Eva Martinez",
                "Engineering",
                "Engineering Manager",
                "E008",
                UserRole.MANAGER,
                date(2019, 4, 20),
                phone="x1010",
                location="Building A",
                team="Platform",
            ),
            Employee(
                "E006",
                "frank.brown@company.com",
                "Frank Brown",
                "Marketing",
                "VP Marketing",
                "E008",
                UserRole.MANAGER,
                date(2018, 9, 1),
                phone="x2010",
                location="Building B",
                team="Marketing",
            ),
            Employee(
                "E007",
                "grace.lee@company.com",
                "Grace Lee",
                "HR",
                "HR Director",
                "E008",
                UserRole.HR,
                date(2017, 2, 14),
                phone="x3010",
                location="Building A",
                team="People Ops",
            ),
            Employee(
                "E008",
                "henry.wilson@company.com",
                "Henry Wilson",
                "Executive",
                "CEO",
                "",
                UserRole.ADMIN,
                date(2015, 1, 1),
                phone="x9001",
                location="Executive Suite",
                team="Leadership",
            ),
        ]
        for emp in employees:
            self.employees[emp.id] = emp

        # Demo leave requests
        leave_requests = [
            LeaveRequest(
                id="LR-001",
                employee_id="E001",
                leave_type=LeaveType.ANNUAL,
                start_date=date(2024, 3, 25),
                end_date=date(2024, 3, 29),
                days=5.0,
                reason="Family vacation",
                status=RequestStatus.APPROVED,
                approved_by="E005",
                approved_at=datetime(2024, 3, 1, 10, 30),
            ),
            LeaveRequest(
                id="LR-002",
                employee_id="E002",
                leave_type=LeaveType.SICK,
                start_date=date(2024, 3, 20),
                end_date=date(2024, 3, 20),
                days=1.0,
                reason="Feeling unwell",
                status=RequestStatus.PENDING,
            ),
            LeaveRequest(
                id="LR-003",
                employee_id="E001",
                leave_type=LeaveType.PERSONAL,
                start_date=date(2024, 4, 15),
                end_date=date(2024, 4, 15),
                days=1.0,
                reason="Personal appointment",
                status=RequestStatus.PENDING,
            ),
        ]
        for lr in leave_requests:
            self.leave_requests[lr.id] = lr

        # Onboarding plan for new hire
        onboarding_tasks = [
            OnboardingTask(
                "T001",
                "Complete I-9 Form",
                "Submit identification documents",
                "HR",
                "employee",
                1,
            ),
            OnboardingTask(
                "T002",
                "Set up direct deposit",
                "Provide banking information",
                "HR",
                "employee",
                3,
            ),
            OnboardingTask(
                "T003",
                "Laptop provisioning",
                "Set up work laptop and accounts",
                "IT",
                "it_team",
                1,
                OnboardingTaskStatus.COMPLETED,
                datetime.now() - timedelta(days=1),
            ),
            OnboardingTask(
                "T004",
                "Complete security training",
                "Online security awareness course",
                "Compliance",
                "employee",
                7,
            ),
            OnboardingTask(
                "T005",
                "Meet with manager",
                "Initial 1:1 meeting with direct manager",
                "Team",
                "manager",
                1,
                OnboardingTaskStatus.COMPLETED,
                datetime.now(),
            ),
            OnboardingTask(
                "T006",
                "Review employee handbook",
                "Read and acknowledge company policies",
                "HR",
                "employee",
                5,
            ),
            OnboardingTask(
                "T007",
                "Set up benefits enrollment",
                "Choose health and retirement plans",
                "HR",
                "employee",
                30,
            ),
            OnboardingTask(
                "T008",
                "Complete team introductions",
                "Meet all team members",
                "Team",
                "employee",
                5,
            ),
            OnboardingTask(
                "T009",
                "Access badge activation",
                "Activate building access badge",
                "Facilities",
                "facilities_team",
                1,
                OnboardingTaskStatus.COMPLETED,
                datetime.now() - timedelta(days=1),
            ),
            OnboardingTask(
                "T010",
                "Development environment setup",
                "Configure local dev tools",
                "IT",
                "employee",
                3,
            ),
        ]
        plan = OnboardingPlan(
            employee_id="E004",
            tasks=onboarding_tasks,
            progress_percent=30.0,
            start_date=date(2024, 1, 8),
        )
        self.onboarding_plans["E004"] = plan

        # HR Policies
        policies = [
            PolicyDocument(
                id="POL-001",
                title="Annual Leave Policy",
                category="Leave",
                summary="Guidelines for requesting and taking annual leave",
                content="""Annual Leave Entitlement:
• Full-time employees: 20 days per year
• Part-time employees: Pro-rated based on hours
• Accrual: Leave accrues monthly (1.67 days/month)

Requesting Leave:
• Submit requests at least 2 weeks in advance
• Manager approval required
• No more than 10 consecutive days without VP approval

Carryover:
• Maximum 5 days can be carried to next year
• Unused days over limit are forfeited

Blackout Periods:
• Year-end close (Dec 15 - Jan 5)
• Requires special approval during these periods""",
                keywords=["annual leave", "vacation", "time off", "PTO", "holiday"],
                effective_date=date(2023, 1, 1),
                last_reviewed=date(2024, 1, 15),
            ),
            PolicyDocument(
                id="POL-002",
                title="Sick Leave Policy",
                category="Leave",
                summary="Guidelines for sick leave and medical absences",
                content="""Sick Leave Entitlement:
• Full-time employees: 10 days per year
• Can be used for personal illness or family care

Documentation:
• 1-2 days: No documentation required
• 3+ days: Medical certificate required

Notification:
• Notify manager before shift start if possible
• Update daily if absence extends

Return to Work:
• Fit-for-duty note may be required after 5+ days
• HR may request fitness assessment for safety roles""",
                keywords=["sick leave", "illness", "medical", "doctor", "unwell"],
                effective_date=date(2023, 1, 1),
                last_reviewed=date(2024, 1, 15),
            ),
            PolicyDocument(
                id="POL-003",
                title="Expense Reimbursement Policy",
                category="Finance",
                summary="Guidelines for submitting business expenses",
                content="""Eligible Expenses:
• Business travel (air, hotel, meals)
• Client entertainment (with prior approval)
• Professional development (courses, conferences)
• Office supplies when working remotely

Submission Requirements:
• Submit within 30 days of expense
• Original receipts required for all expenses over $25
• Itemized receipts required for meals

Approval Thresholds:
• Up to $500: Manager approval
• $500 - $2,000: Director approval
• Over $2,000: VP approval

Per Diem Rates (Domestic Travel):
• Meals: $75/day
• Incidentals: $20/day""",
                keywords=["expense", "reimbursement", "travel", "receipt", "per diem"],
                effective_date=date(2023, 7, 1),
                last_reviewed=date(2024, 2, 1),
            ),
            PolicyDocument(
                id="POL-004",
                title="Remote Work Policy",
                category="Work Arrangements",
                summary="Guidelines for working from home",
                content="""Eligibility:
• All employees after 90-day probation
• Role must be suitable for remote work
• Manager approval required

Expectations:
• Maintain regular working hours
• Be available during core hours (10am - 3pm)
• Respond to messages within 1 hour
• Attend required in-person meetings

Equipment:
• Company provides laptop and basic peripherals
• $500 one-time stipend for home office setup
• IT support available remotely

Security:
• Use VPN for all company systems
• No public WiFi for sensitive work
• Secure workspace away from others""",
                keywords=[
                    "remote work",
                    "work from home",
                    "wfh",
                    "hybrid",
                    "telecommute",
                ],
                effective_date=date(2023, 1, 1),
                last_reviewed=date(2024, 1, 1),
            ),
            PolicyDocument(
                id="POL-005",
                title="Parental Leave Policy",
                category="Leave",
                summary="Leave for new parents",
                content="""Paid Parental Leave:
• Primary caregiver: 16 weeks at 100% pay
• Secondary caregiver: 6 weeks at 100% pay
• Applies to birth, adoption, and foster placement

Eligibility:
• 1 year of service required
• Full-time and part-time employees

Taking Leave:
• Must begin within 12 months of birth/placement
• Can be taken in 2 separate blocks
• Additional unpaid leave available

Return to Work:
• Guaranteed same or equivalent role
• Flexible return options available
• Phased return can be arranged""",
                keywords=[
                    "parental leave",
                    "maternity",
                    "paternity",
                    "baby",
                    "adoption",
                ],
                effective_date=date(2023, 1, 1),
                last_reviewed=date(2024, 1, 1),
            ),
        ]
        for pol in policies:
            self.policies[pol.id] = pol

        # Training courses
        courses = [
            TrainingCourse(
                "TR-001",
                "Security Awareness Training",
                "Annual cybersecurity training covering phishing, passwords, and data protection",
                "Compliance",
                1.0,
                True,
            ),
            TrainingCourse(
                "TR-002",
                "Harassment Prevention",
                "Understanding workplace harassment and creating a respectful environment",
                "Compliance",
                2.0,
                True,
            ),
            TrainingCourse(
                "TR-003",
                "New Manager Essentials",
                "Core skills for first-time managers",
                "Leadership",
                8.0,
                False,
            ),
            TrainingCourse(
                "TR-004",
                "Effective Communication",
                "Improve written and verbal communication skills",
                "Professional Development",
                4.0,
                False,
            ),
            TrainingCourse(
                "TR-005",
                "Project Management Fundamentals",
                "Introduction to project management methodologies",
                "Professional Development",
                6.0,
                False,
            ),
        ]
        for course in courses:
            self.courses[course.id] = course

        # Set default user
        self.current_user = self.employees["E001"]

    # ──────────────────────────────────────────────────────────────────────────
    # LEAVE MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def get_leave_balance(self, employee_id: str = None) -> dict:
        """Get leave balance for an employee."""
        emp_id = employee_id or self.current_user.id
        employee = self.employees.get(emp_id)

        if not employee:
            return {"success": False, "error": f"Employee {emp_id} not found"}

        # Check permissions
        can_view = (
            emp_id == self.current_user.id
            or self.current_user.role in [UserRole.HR, UserRole.ADMIN]
            or employee.manager_id == self.current_user.id
        )

        if not can_view:
            return {"success": False, "error": "Permission denied"}

        # Calculate pending leave
        pending = [
            lr
            for lr in self.leave_requests.values()
            if lr.employee_id == emp_id and lr.status == RequestStatus.PENDING
        ]
        pending_days = sum(lr.days for lr in pending)

        return {
            "success": True,
            "employee": employee.name,
            "balances": {
                "annual_leave": {
                    "available": employee.annual_leave_balance,
                    "pending": sum(
                        lr.days for lr in pending if lr.leave_type == LeaveType.ANNUAL
                    ),
                    "total_entitlement": 20.0,
                },
                "sick_leave": {
                    "available": employee.sick_leave_balance,
                    "pending": sum(
                        lr.days for lr in pending if lr.leave_type == LeaveType.SICK
                    ),
                    "total_entitlement": 10.0,
                },
                "personal_leave": {
                    "available": employee.personal_leave_balance,
                    "pending": sum(
                        lr.days for lr in pending if lr.leave_type == LeaveType.PERSONAL
                    ),
                    "total_entitlement": 3.0,
                },
            },
        }

    def request_leave(
        self, leave_type: str, start_date: str, end_date: str, reason: str
    ) -> dict:
        """Submit a leave request."""
        try:
            l_type = LeaveType[leave_type.upper()]
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except (KeyError, ValueError) as e:
            return {"success": False, "error": f"Invalid input: {e}"}

        if end < start:
            return {"success": False, "error": "End date must be after start date"}

        # Calculate days (simple, excludes weekends)
        days = 0
        current = start
        while current <= end:
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                days += 1
            current += timedelta(days=1)

        # Check balance
        balance = self.get_leave_balance()
        if not balance["success"]:
            return balance

        type_key = leave_type.lower() + "_leave"
        if type_key in balance["balances"]:
            available = balance["balances"][type_key]["available"]
            if days > available:
                return {
                    "success": False,
                    "error": f"Insufficient {leave_type} balance. Available: {available} days, Requested: {days} days",
                }

        # Create request
        request_id = self._generate_id("LR")
        request = LeaveRequest(
            id=request_id,
            employee_id=self.current_user.id,
            leave_type=l_type,
            start_date=start,
            end_date=end,
            days=days,
            reason=reason,
        )
        self.leave_requests[request_id] = request

        # Get manager info
        manager = self.employees.get(self.current_user.manager_id)

        return {
            "success": True,
            "request_id": request_id,
            "days_requested": days,
            "pending_approval_from": manager.name if manager else "HR",
            "message": f"Leave request {request_id} submitted for {days} days from {start_date} to {end_date}",
        }

    def approve_leave(self, request_id: str, approved: bool, notes: str = "") -> dict:
        """Approve or reject a leave request."""
        request = self.leave_requests.get(request_id)
        if not request:
            return {"success": False, "error": f"Request {request_id} not found"}

        employee = self.employees.get(request.employee_id)
        if not employee:
            return {"success": False, "error": "Employee not found"}

        # Check permissions
        is_manager = employee.manager_id == self.current_user.id
        is_hr = self.current_user.role in [UserRole.HR, UserRole.ADMIN]

        if not (is_manager or is_hr):
            return {
                "success": False,
                "error": "Permission denied - not authorized to approve",
            }

        if request.status != RequestStatus.PENDING:
            return {
                "success": False,
                "error": f"Request already {request.status.value}",
            }

        request.status = RequestStatus.APPROVED if approved else RequestStatus.REJECTED
        request.approved_by = self.current_user.id
        request.approved_at = datetime.now()
        request.notes = notes

        # Deduct from balance if approved
        if approved:
            if request.leave_type == LeaveType.ANNUAL:
                employee.annual_leave_balance -= request.days
            elif request.leave_type == LeaveType.SICK:
                employee.sick_leave_balance -= request.days
            elif request.leave_type == LeaveType.PERSONAL:
                employee.personal_leave_balance -= request.days

        return {
            "success": True,
            "request_id": request_id,
            "status": request.status.value,
            "message": f"Leave request {request_id} has been {'approved' if approved else 'rejected'}",
            "employee": employee.name,
            "dates": f"{request.start_date} to {request.end_date}",
        }

    def list_leave_requests(
        self, status: str = None, pending_my_approval: bool = False
    ) -> dict:
        """List leave requests."""
        requests = list(self.leave_requests.values())

        if pending_my_approval:
            # Show requests for direct reports
            my_reports = [
                e.id
                for e in self.employees.values()
                if e.manager_id == self.current_user.id
            ]
            requests = [
                r
                for r in requests
                if r.employee_id in my_reports and r.status == RequestStatus.PENDING
            ]
        elif self.current_user.role not in [UserRole.HR, UserRole.ADMIN]:
            # Regular employees see only their own
            requests = [r for r in requests if r.employee_id == self.current_user.id]

        if status:
            try:
                stat = RequestStatus[status.upper()]
                requests = [r for r in requests if r.status == stat]
            except KeyError:
                pass

        return {
            "success": True,
            "count": len(requests),
            "requests": [
                {
                    "id": r.id,
                    "employee": (
                        self.employees[r.employee_id].name
                        if r.employee_id in self.employees
                        else "Unknown"
                    ),
                    "type": r.leave_type.value,
                    "dates": f"{r.start_date} to {r.end_date}",
                    "days": r.days,
                    "status": r.status.value,
                    "reason": r.reason[:50],
                }
                for r in sorted(requests, key=lambda x: x.start_date)
            ],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # ONBOARDING
    # ──────────────────────────────────────────────────────────────────────────

    def get_onboarding_status(self, employee_id: str = None) -> dict:
        """Get onboarding status for a new hire."""
        emp_id = employee_id or self.current_user.id

        if emp_id not in self.onboarding_plans:
            return {"success": False, "error": f"No onboarding plan found for {emp_id}"}

        plan = self.onboarding_plans[emp_id]
        employee = self.employees.get(emp_id)

        # Calculate progress
        completed = len(
            [t for t in plan.tasks if t.status == OnboardingTaskStatus.COMPLETED]
        )
        total = len(plan.tasks)
        progress = (completed / total * 100) if total > 0 else 0

        # Group tasks by status
        pending = [t for t in plan.tasks if t.status == OnboardingTaskStatus.PENDING]
        in_progress = [
            t for t in plan.tasks if t.status == OnboardingTaskStatus.IN_PROGRESS
        ]
        done = [t for t in plan.tasks if t.status == OnboardingTaskStatus.COMPLETED]

        return {
            "success": True,
            "employee": employee.name if employee else "Unknown",
            "start_date": plan.start_date.isoformat(),
            "progress": f"{progress:.0f}%",
            "summary": {
                "completed": completed,
                "in_progress": len(in_progress),
                "pending": len(pending),
                "total": total,
            },
            "pending_tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "category": t.category,
                    "responsible": t.responsible_role,
                    "due_day": t.due_day,
                    "due_date": (
                        plan.start_date + timedelta(days=t.due_day)
                    ).isoformat(),
                }
                for t in pending[:5]  # Show top 5
            ],
            "completed_tasks": len(done),
        }

    def update_onboarding_task(
        self, task_id: str, status: str, notes: str = ""
    ) -> dict:
        """Update an onboarding task status."""
        # Find the task
        for plan in self.onboarding_plans.values():
            for task in plan.tasks:
                if task.id == task_id:
                    try:
                        new_status = OnboardingTaskStatus[status.upper()]
                        task.status = new_status
                        task.notes = notes
                        if new_status == OnboardingTaskStatus.COMPLETED:
                            task.completed_at = datetime.now()

                        return {
                            "success": True,
                            "task_id": task_id,
                            "title": task.title,
                            "new_status": new_status.value,
                            "message": f"Task '{task.title}' marked as {new_status.value}",
                        }
                    except KeyError:
                        return {"success": False, "error": f"Invalid status: {status}"}

        return {"success": False, "error": f"Task {task_id} not found"}

    # ──────────────────────────────────────────────────────────────────────────
    # EMPLOYEE DIRECTORY
    # ──────────────────────────────────────────────────────────────────────────

    def search_employees(
        self, query: str = None, department: str = None, team: str = None
    ) -> dict:
        """Search employee directory."""
        employees = list(self.employees.values())

        if query:
            query_lower = query.lower()
            employees = [
                e
                for e in employees
                if query_lower in e.name.lower()
                or query_lower in e.title.lower()
                or query_lower in e.email.lower()
            ]

        if department:
            employees = [
                e for e in employees if department.lower() in e.department.lower()
            ]

        if team:
            employees = [e for e in employees if team.lower() in e.team.lower()]

        # Filter out sensitive info for non-HR
        is_hr = self.current_user.role in [UserRole.HR, UserRole.ADMIN]

        return {
            "success": True,
            "count": len(employees),
            "employees": [
                {
                    "id": e.id if is_hr else None,
                    "name": e.name,
                    "email": e.email,
                    "title": e.title,
                    "department": e.department,
                    "team": e.team,
                    "location": e.location,
                    "phone": e.phone,
                    "manager": (
                        self.employees[e.manager_id].name
                        if e.manager_id in self.employees
                        else None
                    ),
                }
                for e in employees
            ],
        }

    def get_org_chart(self, manager_id: str = None) -> dict:
        """Get organizational chart."""
        if manager_id:
            manager = self.employees.get(manager_id)
            if not manager:
                return {"success": False, "error": f"Manager {manager_id} not found"}
        else:
            # Find CEO (no manager)
            manager = next(
                (e for e in self.employees.values() if not e.manager_id), None
            )

        def build_tree(emp_id):
            emp = self.employees.get(emp_id)
            if not emp:
                return None

            reports = [e for e in self.employees.values() if e.manager_id == emp_id]
            return {
                "name": emp.name,
                "title": emp.title,
                "department": emp.department,
                "direct_reports": (
                    [build_tree(r.id) for r in reports] if reports else []
                ),
            }

        if manager:
            tree = build_tree(manager.id)
            return {"success": True, "org_chart": tree}
        else:
            return {"success": False, "error": "No root manager found"}

    # ──────────────────────────────────────────────────────────────────────────
    # POLICIES
    # ──────────────────────────────────────────────────────────────────────────

    def search_policies(self, query: str, category: str = None) -> dict:
        """Search HR policies."""
        query_lower = query.lower()
        results = []

        for policy in self.policies.values():
            score = 0

            if query_lower in policy.title.lower():
                score += 10
            if query_lower in policy.summary.lower():
                score += 5
            for kw in policy.keywords:
                if kw.lower() in query_lower or query_lower in kw.lower():
                    score += 7

            if category and category.lower() != policy.category.lower():
                continue

            if score > 0:
                results.append((policy, score))

        results.sort(key=lambda x: x[1], reverse=True)

        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "policies": [
                {
                    "id": p.id,
                    "title": p.title,
                    "category": p.category,
                    "summary": p.summary,
                    "relevance": score,
                    "effective_date": p.effective_date.isoformat(),
                }
                for p, score in results
            ],
        }

    def get_policy(self, policy_id: str) -> dict:
        """Get full policy document."""
        policy = self.policies.get(policy_id)
        if not policy:
            return {"success": False, "error": f"Policy {policy_id} not found"}

        return {
            "success": True,
            "policy": {
                "id": policy.id,
                "title": policy.title,
                "category": policy.category,
                "summary": policy.summary,
                "content": policy.content,
                "effective_date": policy.effective_date.isoformat(),
                "last_reviewed": policy.last_reviewed.isoformat(),
                "version": policy.version,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # TRAINING
    # ──────────────────────────────────────────────────────────────────────────

    def list_training_courses(
        self, mandatory_only: bool = False, category: str = None
    ) -> dict:
        """List available training courses."""
        courses = list(self.courses.values())

        if mandatory_only:
            courses = [c for c in courses if c.mandatory]

        if category:
            courses = [c for c in courses if category.lower() in c.category.lower()]

        return {
            "success": True,
            "count": len(courses),
            "courses": [
                {
                    "id": c.id,
                    "title": c.title,
                    "description": c.description,
                    "category": c.category,
                    "duration_hours": c.duration_hours,
                    "mandatory": c.mandatory,
                    "provider": c.provider,
                }
                for c in courses
            ],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # USER MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def switch_user(self, user_id: str) -> dict:
        """Switch current user context (for demo)."""
        user = self.employees.get(user_id)
        if not user:
            return {"success": False, "error": f"User {user_id} not found"}

        self.current_user = user
        return {
            "success": True,
            "message": f"Switched to: {user.name}",
            "role": user.role.value,
            "department": user.department,
        }

    def get_my_profile(self) -> dict:
        """Get current user's profile."""
        emp = self.current_user
        manager = self.employees.get(emp.manager_id) if emp.manager_id else None

        return {
            "success": True,
            "profile": {
                "name": emp.name,
                "email": emp.email,
                "title": emp.title,
                "department": emp.department,
                "team": emp.team,
                "manager": manager.name if manager else None,
                "start_date": emp.start_date.isoformat(),
                "location": emp.location,
                "status": emp.status.value,
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an HR & People Operations Assistant for a corporate enterprise.

Your role is to:
1. Answer policy questions about leave, benefits, and expenses
2. Help employees with time-off requests
3. Guide new hires through onboarding
4. Search the employee directory
5. Find training and development resources

You have access to these tools:
- get_leave_balance: Check leave balances
- request_leave: Submit a leave request
- approve_leave: Approve/reject requests (managers only)
- list_leave_requests: View leave requests
- get_onboarding_status: Check onboarding progress
- update_onboarding_task: Update task status
- search_employees: Search directory
- get_org_chart: View organizational structure
- search_policies: Find HR policies
- get_policy: Read full policy
- list_training_courses: Browse training
- get_my_profile: View own profile

Always be professional and helpful. Protect employee confidentiality - only share information the user is authorized to see based on their role."""


# ══════════════════════════════════════════════════════════════════════════════
# AGENT TOOLS
# ══════════════════════════════════════════════════════════════════════════════


def create_hr_tools(service: HRService) -> list:
    """Create tool definitions for the HR agent."""
    return [
        {
            "name": "get_leave_balance",
            "description": "Get leave balance for an employee",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee ID (optional, defaults to self)",
                    }
                },
            },
            "function": lambda employee_id=None: service.get_leave_balance(employee_id),
        },
        {
            "name": "request_leave",
            "description": "Submit a leave request",
            "parameters": {
                "type": "object",
                "properties": {
                    "leave_type": {
                        "type": "string",
                        "description": "Type: annual, sick, personal, parental",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date YYYY-MM-DD",
                    },
                    "reason": {"type": "string", "description": "Reason for leave"},
                },
                "required": ["leave_type", "start_date", "end_date", "reason"],
            },
            "function": lambda leave_type, start_date, end_date, reason: service.request_leave(
                leave_type, start_date, end_date, reason
            ),
        },
        {
            "name": "approve_leave",
            "description": "Approve or reject a leave request (managers only)",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "Leave request ID"},
                    "approved": {
                        "type": "boolean",
                        "description": "True to approve, False to reject",
                    },
                    "notes": {"type": "string", "description": "Optional notes"},
                },
                "required": ["request_id", "approved"],
            },
            "function": lambda request_id, approved, notes="": service.approve_leave(
                request_id, approved, notes
            ),
        },
        {
            "name": "list_leave_requests",
            "description": "List leave requests",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status"},
                    "pending_my_approval": {
                        "type": "boolean",
                        "description": "Show only requests pending my approval",
                    },
                },
            },
            "function": lambda status=None, pending_my_approval=False: service.list_leave_requests(
                status, pending_my_approval
            ),
        },
        {
            "name": "get_onboarding_status",
            "description": "Get onboarding status and checklist",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee ID (optional)",
                    }
                },
            },
            "function": lambda employee_id=None: service.get_onboarding_status(
                employee_id
            ),
        },
        {
            "name": "update_onboarding_task",
            "description": "Update an onboarding task status",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID"},
                    "status": {
                        "type": "string",
                        "description": "Status: pending, in_progress, completed",
                    },
                    "notes": {"type": "string", "description": "Optional notes"},
                },
                "required": ["task_id", "status"],
            },
            "function": lambda task_id, status, notes="": service.update_onboarding_task(
                task_id, status, notes
            ),
        },
        {
            "name": "search_employees",
            "description": "Search the employee directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search by name, title, or email",
                    },
                    "department": {
                        "type": "string",
                        "description": "Filter by department",
                    },
                    "team": {"type": "string", "description": "Filter by team"},
                },
            },
            "function": lambda query=None, department=None, team=None: service.search_employees(
                query, department, team
            ),
        },
        {
            "name": "get_org_chart",
            "description": "Get organizational chart",
            "parameters": {
                "type": "object",
                "properties": {
                    "manager_id": {
                        "type": "string",
                        "description": "Start from this manager (optional)",
                    }
                },
            },
            "function": lambda manager_id=None: service.get_org_chart(manager_id),
        },
        {
            "name": "search_policies",
            "description": "Search HR policies",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {"type": "string", "description": "Category filter"},
                },
                "required": ["query"],
            },
            "function": lambda query, category=None: service.search_policies(
                query, category
            ),
        },
        {
            "name": "get_policy",
            "description": "Get full policy document",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string", "description": "Policy ID"}
                },
                "required": ["policy_id"],
            },
            "function": lambda policy_id: service.get_policy(policy_id),
        },
        {
            "name": "list_training_courses",
            "description": "List available training courses",
            "parameters": {
                "type": "object",
                "properties": {
                    "mandatory_only": {
                        "type": "boolean",
                        "description": "Show only mandatory courses",
                    },
                    "category": {"type": "string", "description": "Filter by category"},
                },
            },
            "function": lambda mandatory_only=False, category=None: service.list_training_courses(
                mandatory_only, category
            ),
        },
        {
            "name": "get_my_profile",
            "description": "Get current user's profile",
            "parameters": {"type": "object", "properties": {}},
            "function": lambda: service.get_my_profile(),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# DEMO AND INTERACTIVE MODES
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate HR assistant capabilities."""
    print("=" * 70)
    print("HR & PEOPLE OPERATIONS BOT - DEMO MODE")
    print("=" * 70)

    service = HRService()

    # My profile
    print("\n👤 MY PROFILE")
    print("-" * 50)
    profile = service.get_my_profile()
    p = profile["profile"]
    print(f"Name: {p['name']}")
    print(f"Title: {p['title']}")
    print(f"Department: {p['department']}")
    print(f"Manager: {p['manager']}")

    # Leave balance
    print("\n📅 LEAVE BALANCES")
    print("-" * 50)
    balance = service.get_leave_balance()
    b = balance["balances"]
    print(f"Annual Leave: {b['annual_leave']['available']} days available")
    print(f"Sick Leave: {b['sick_leave']['available']} days available")
    print(f"Personal Leave: {b['personal_leave']['available']} days available")

    # Submit leave request
    print("\n✈️ SUBMITTING LEAVE REQUEST")
    print("-" * 50)
    result = service.request_leave(
        leave_type="annual",
        start_date="2024-05-01",
        end_date="2024-05-03",
        reason="Short vacation",
    )
    print(f"Request ID: {result['request_id']}")
    print(f"Days: {result['days_requested']}")
    print(f"Awaiting approval from: {result['pending_approval_from']}")

    # Policy search
    print("\n📋 POLICY SEARCH: 'expense reimbursement'")
    print("-" * 50)
    policies = service.search_policies("expense reimbursement")
    for pol in policies["policies"]:
        print(f"  [{pol['id']}] {pol['title']}")
        print(f"      {pol['summary']}")

    # Onboarding status (for new hire)
    print("\n🎯 ONBOARDING STATUS: David Chen (new hire)")
    print("-" * 50)
    onboarding = service.get_onboarding_status("E004")
    print(f"Progress: {onboarding['progress']}")
    print(
        f"Completed: {onboarding['summary']['completed']}/{onboarding['summary']['total']}"
    )
    print("\nPending Tasks:")
    for task in onboarding["pending_tasks"]:
        print(f"  • {task['title']} (Due: {task['due_date']})")

    # Employee search
    print("\n🔍 EMPLOYEE SEARCH: 'Engineering'")
    print("-" * 50)
    employees = service.search_employees(department="Engineering")
    for emp in employees["employees"]:
        print(f"  {emp['name']} - {emp['title']}")

    # Training courses
    print("\n📚 MANDATORY TRAINING COURSES")
    print("-" * 50)
    courses = service.list_training_courses(mandatory_only=True)
    for course in courses["courses"]:
        print(f"  [{course['id']}] {course['title']} ({course['duration_hours']}h)")

    # Manager view - pending approvals
    print("\n👔 MANAGER VIEW: Pending Leave Approvals")
    print("-" * 50)
    service.switch_user("E005")  # Switch to manager
    pending = service.list_leave_requests(pending_my_approval=True)
    if pending["requests"]:
        for req in pending["requests"]:
            print(f"  {req['id']}: {req['employee']} - {req['type']} ({req['dates']})")
    else:
        print("  No pending approvals")

    print("\n" + "=" * 70)
    print("Demo complete! Run with --interactive for full chat mode.")
    print("=" * 70)


async def interactive():
    """Run interactive HR chat."""
    print("=" * 70)
    print("HR & PEOPLE OPERATIONS ASSISTANT")
    print("=" * 70)
    print("\nWelcome! I can help you with:")
    print("  • Leave requests and balances")
    print("  • Company policies and benefits")
    print("  • Employee directory search")
    print("  • Onboarding and training")
    print("\nType 'quit' to exit, 'demo' for demo mode.\n")

    service = HRService()
    tools = create_hr_tools(service)

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
                print("\nThank you for using HR Assistant. Goodbye!")
                break

            if user_input.lower() == "demo":
                await demo()
                continue

            if user_input.lower() == "balance":
                result = service.get_leave_balance()
                print(f"\n🤖 Assistant: {json.dumps(result, indent=2)}")
                continue

            if user_input.lower() == "profile":
                result = service.get_my_profile()
                print(f"\n🤖 Assistant: {json.dumps(result, indent=2)}")
                continue

            if use_agent:
                response = await agent.chat(user_input)
                print(f"\n🤖 Assistant: {response}")
            else:
                print("\n🤖 Assistant: I understand your HR question.")
                print("   Quick commands: 'balance', 'profile', 'demo'")

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
