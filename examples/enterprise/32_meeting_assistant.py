#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 32: Meeting & Notes Assistant

An enterprise meeting management assistant:
- Meeting scheduling
- Agenda creation
- Action item extraction
- Notes summarization
- Follow-up reminders

Key patterns demonstrated:
- Calendar integration concepts
- Natural language processing for action items
- Meeting note templates
- Attendee management
- Recurring meeting patterns

Usage:
    python examples/32_meeting_assistant.py

Requirements:
    pip install agentic-brain
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date, time
from enum import Enum
from typing import Optional
import json
import random
import string
import re

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class MeetingType(Enum):
    """Types of meetings."""

    ONE_ON_ONE = "one_on_one"
    TEAM_STANDUP = "team_standup"
    PROJECT_UPDATE = "project_update"
    BRAINSTORM = "brainstorm"
    CLIENT_CALL = "client_call"
    ALL_HANDS = "all_hands"
    INTERVIEW = "interview"
    WORKSHOP = "workshop"
    REVIEW = "review"
    OTHER = "other"


class MeetingStatus(Enum):
    """Meeting status."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


class AttendeeStatus(Enum):
    """Attendee response status."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"


class ActionItemStatus(Enum):
    """Action item status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class ActionItemPriority(Enum):
    """Action item priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RecurrencePattern(Enum):
    """Meeting recurrence patterns."""

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


@dataclass
class User:
    """System user."""

    id: str
    email: str
    name: str
    department: str
    timezone: str = "America/New_York"


@dataclass
class Attendee:
    """Meeting attendee."""

    user_id: str
    name: str
    email: str
    status: AttendeeStatus = AttendeeStatus.PENDING
    is_organizer: bool = False
    is_optional: bool = False


@dataclass
class AgendaItem:
    """Meeting agenda item."""

    id: str
    title: str
    description: str = ""
    presenter: str = ""
    duration_minutes: int = 10
    order: int = 0
    completed: bool = False


@dataclass
class ActionItem:
    """Action item from a meeting."""

    id: str
    meeting_id: str
    title: str
    description: str
    assignee_id: str
    assignee_name: str
    due_date: date
    priority: ActionItemPriority
    status: ActionItemStatus = ActionItemStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class MeetingNotes:
    """Meeting notes/minutes."""

    meeting_id: str
    raw_transcript: str = ""
    summary: str = ""
    key_decisions: list = field(default_factory=list)
    discussion_points: list = field(default_factory=list)
    action_items: list = field(default_factory=list)
    next_steps: list = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Meeting:
    """Meeting record."""

    id: str
    title: str
    description: str
    meeting_type: MeetingType
    start_time: datetime
    end_time: datetime
    location: str  # Room name or video link
    organizer_id: str
    attendees: list[Attendee] = field(default_factory=list)
    agenda: list[AgendaItem] = field(default_factory=list)
    status: MeetingStatus = MeetingStatus.SCHEDULED
    recurrence: RecurrencePattern = RecurrencePattern.NONE
    notes: Optional[MeetingNotes] = None
    action_items: list[ActionItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    parent_meeting_id: str = ""  # For recurring meetings


# ══════════════════════════════════════════════════════════════════════════════
# MEETING SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class MeetingService:
    """Enterprise meeting management service."""

    def __init__(self):
        """Initialize with demo data."""
        self.users: dict[str, User] = {}
        self.meetings: dict[str, Meeting] = {}
        self.action_items: dict[str, ActionItem] = {}
        self.current_user: Optional[User] = None
        self._load_demo_data()

    def _generate_id(self, prefix: str = "MTG") -> str:
        """Generate unique ID."""
        suffix = "".join(random.choices(string.digits + string.ascii_uppercase, k=6))
        return f"{prefix}-{suffix}"

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo users
        users = [
            User("U001", "alice@company.com", "Alice Johnson", "Engineering"),
            User("U002", "bob@company.com", "Bob Smith", "Engineering"),
            User("U003", "carol@company.com", "Carol White", "Product"),
            User("U004", "david@company.com", "David Chen", "Design"),
            User("U005", "eva@company.com", "Eva Martinez", "Engineering"),
        ]
        for user in users:
            self.users[user.id] = user

        # Demo meetings
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        next_week = now + timedelta(days=7)

        # Past meeting with notes
        past_meeting = Meeting(
            id="MTG-001",
            title="Sprint Planning - Q1 Features",
            description="Planning session for Q1 feature development",
            meeting_type=MeetingType.PROJECT_UPDATE,
            start_time=now - timedelta(days=2, hours=2),
            end_time=now - timedelta(days=2, hours=1),
            location="Conference Room A / https://meet.company.com/sprint",
            organizer_id="U001",
            attendees=[
                Attendee(
                    "U001",
                    "Alice Johnson",
                    "alice@company.com",
                    AttendeeStatus.ACCEPTED,
                    is_organizer=True,
                ),
                Attendee(
                    "U002", "Bob Smith", "bob@company.com", AttendeeStatus.ACCEPTED
                ),
                Attendee(
                    "U003", "Carol White", "carol@company.com", AttendeeStatus.ACCEPTED
                ),
                Attendee(
                    "U004", "David Chen", "david@company.com", AttendeeStatus.DECLINED
                ),
            ],
            agenda=[
                AgendaItem(
                    "AG-001",
                    "Review Q4 retrospective",
                    "Learnings from last quarter",
                    "Carol",
                    15,
                    1,
                    True,
                ),
                AgendaItem(
                    "AG-002",
                    "Q1 Feature priorities",
                    "Discuss and rank features",
                    "Alice",
                    30,
                    2,
                    True,
                ),
                AgendaItem(
                    "AG-003",
                    "Resource allocation",
                    "Team assignments",
                    "Bob",
                    15,
                    3,
                    True,
                ),
            ],
            status=MeetingStatus.COMPLETED,
            notes=MeetingNotes(
                meeting_id="MTG-001",
                raw_transcript="""
Alice: Let's start with the Q4 retrospective. Carol, can you summarize?
Carol: Sure. Main wins were the payment integration and mobile app release. 
Challenges were the database migration delays and some communication gaps.
Bob: I think we should focus on better documentation this quarter.
Alice: Agreed. Let's add that to our goals. Now for Q1 priorities...
Carol: The customer feedback shows strong demand for the analytics dashboard.
Alice: That's our top priority then. Bob, can you lead that effort?
Bob: Yes, I can start next week. I'll need David for the UI work though.
Alice: David's out today but I'll follow up with him. We should target end of February.
Carol: We also need to address the performance issues in the search feature.
Alice: Let's make that second priority. Bob, can you assign someone from your team?
Bob: I'll have Sarah look into it. She's great with optimization.
Alice: Perfect. Let's reconvene next week with more detailed plans.
                """,
                summary="Sprint planning for Q1 focused on analytics dashboard (top priority) and search performance improvements. Team aligned on goals with clear ownership assigned.",
                key_decisions=[
                    "Analytics dashboard is top priority for Q1",
                    "Target completion: end of February",
                    "Search performance is second priority",
                    "Improved documentation added as team goal",
                ],
                discussion_points=[
                    "Q4 retrospective: payment integration and mobile app were wins",
                    "Database migration caused delays last quarter",
                    "Strong customer demand for analytics features",
                    "Need to follow up with David on UI work",
                ],
                action_items=[
                    "Bob to lead analytics dashboard development",
                    "Alice to follow up with David about UI work",
                    "Sarah to investigate search performance issues",
                    "Carol to prepare detailed feature specs by Friday",
                ],
                next_steps=[
                    "Bob to create project plan for analytics dashboard",
                    "Team to review specs at next week's meeting",
                    "Alice to schedule David follow-up",
                ],
                created_by="U001",
            ),
        )
        self.meetings[past_meeting.id] = past_meeting

        # Add action items from past meeting
        action_items_demo = [
            ActionItem(
                id="ACT-001",
                meeting_id="MTG-001",
                title="Lead analytics dashboard development",
                description="Take ownership of the analytics dashboard project and create initial technical design",
                assignee_id="U002",
                assignee_name="Bob Smith",
                due_date=date.today() + timedelta(days=5),
                priority=ActionItemPriority.HIGH,
                status=ActionItemStatus.IN_PROGRESS,
            ),
            ActionItem(
                id="ACT-002",
                meeting_id="MTG-001",
                title="Follow up with David about UI work",
                description="Discuss timeline and capacity for analytics dashboard UI",
                assignee_id="U001",
                assignee_name="Alice Johnson",
                due_date=date.today(),
                priority=ActionItemPriority.MEDIUM,
                status=ActionItemStatus.COMPLETED,
                completed_at=datetime.now() - timedelta(hours=3),
            ),
            ActionItem(
                id="ACT-003",
                meeting_id="MTG-001",
                title="Investigate search performance issues",
                description="Profile search queries and identify bottlenecks",
                assignee_id="U005",
                assignee_name="Eva Martinez",
                due_date=date.today() + timedelta(days=7),
                priority=ActionItemPriority.MEDIUM,
                status=ActionItemStatus.PENDING,
            ),
            ActionItem(
                id="ACT-004",
                meeting_id="MTG-001",
                title="Prepare detailed feature specs",
                description="Document requirements for top 3 Q1 features",
                assignee_id="U003",
                assignee_name="Carol White",
                due_date=date.today() - timedelta(days=1),
                priority=ActionItemPriority.HIGH,
                status=ActionItemStatus.OVERDUE,
            ),
        ]
        for ai in action_items_demo:
            self.action_items[ai.id] = ai
            past_meeting.action_items.append(ai)

        # Upcoming team standup
        standup = Meeting(
            id="MTG-002",
            title="Engineering Daily Standup",
            description="Daily sync for engineering team",
            meeting_type=MeetingType.TEAM_STANDUP,
            start_time=tomorrow.replace(hour=9, minute=0, second=0),
            end_time=tomorrow.replace(hour=9, minute=15, second=0),
            location="https://meet.company.com/standup",
            organizer_id="U001",
            attendees=[
                Attendee(
                    "U001",
                    "Alice Johnson",
                    "alice@company.com",
                    AttendeeStatus.ACCEPTED,
                    is_organizer=True,
                ),
                Attendee(
                    "U002", "Bob Smith", "bob@company.com", AttendeeStatus.ACCEPTED
                ),
                Attendee(
                    "U005", "Eva Martinez", "eva@company.com", AttendeeStatus.TENTATIVE
                ),
            ],
            recurrence=RecurrencePattern.DAILY,
            status=MeetingStatus.SCHEDULED,
        )
        self.meetings[standup.id] = standup

        # One-on-one meeting
        one_on_one = Meeting(
            id="MTG-003",
            title="Alice / Bob 1:1",
            description="Weekly one-on-one",
            meeting_type=MeetingType.ONE_ON_ONE,
            start_time=tomorrow.replace(hour=14, minute=0, second=0),
            end_time=tomorrow.replace(hour=14, minute=30, second=0),
            location="Alice's Office",
            organizer_id="U001",
            attendees=[
                Attendee(
                    "U001",
                    "Alice Johnson",
                    "alice@company.com",
                    AttendeeStatus.ACCEPTED,
                    is_organizer=True,
                ),
                Attendee(
                    "U002", "Bob Smith", "bob@company.com", AttendeeStatus.ACCEPTED
                ),
            ],
            agenda=[
                AgendaItem("AG-004", "Project updates", "", "Bob", 10, 1),
                AgendaItem("AG-005", "Career development", "", "Both", 10, 2),
                AgendaItem("AG-006", "Any blockers?", "", "Bob", 10, 3),
            ],
            recurrence=RecurrencePattern.WEEKLY,
            status=MeetingStatus.SCHEDULED,
        )
        self.meetings[one_on_one.id] = one_on_one

        # Client call
        client_call = Meeting(
            id="MTG-004",
            title="Acme Corp - Quarterly Review",
            description="Quarterly business review with Acme Corp",
            meeting_type=MeetingType.CLIENT_CALL,
            start_time=next_week.replace(hour=10, minute=0, second=0),
            end_time=next_week.replace(hour=11, minute=0, second=0),
            location="https://meet.company.com/acme-qbr",
            organizer_id="U003",
            attendees=[
                Attendee(
                    "U003",
                    "Carol White",
                    "carol@company.com",
                    AttendeeStatus.ACCEPTED,
                    is_organizer=True,
                ),
                Attendee(
                    "U001",
                    "Alice Johnson",
                    "alice@company.com",
                    AttendeeStatus.ACCEPTED,
                ),
                Attendee(
                    "U002", "Bob Smith", "bob@company.com", AttendeeStatus.PENDING
                ),
            ],
            agenda=[
                AgendaItem(
                    "AG-007",
                    "Q4 Results Review",
                    "Present delivery metrics",
                    "Carol",
                    20,
                    1,
                ),
                AgendaItem(
                    "AG-008", "Roadmap Preview", "Share Q1-Q2 plans", "Alice", 20, 2
                ),
                AgendaItem("AG-009", "Client Feedback", "Gather input", "Carol", 15, 3),
                AgendaItem("AG-010", "Next Steps", "Action items", "All", 5, 4),
            ],
            status=MeetingStatus.SCHEDULED,
        )
        self.meetings[client_call.id] = client_call

        # Set default user
        self.current_user = self.users["U001"]

    # ──────────────────────────────────────────────────────────────────────────
    # MEETING MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def schedule_meeting(
        self,
        title: str,
        description: str,
        meeting_type: str,
        start_time: str,
        duration_minutes: int,
        location: str,
        attendee_ids: list,
        recurrence: str = "none",
    ) -> dict:
        """Schedule a new meeting."""
        try:
            m_type = MeetingType[meeting_type.upper()]
            rec = RecurrencePattern[recurrence.upper()]
            start = datetime.fromisoformat(start_time)
        except (KeyError, ValueError) as e:
            return {"success": False, "error": f"Invalid input: {e}"}

        end = start + timedelta(minutes=duration_minutes)
        meeting_id = self._generate_id()

        # Create attendee list
        attendees = [
            Attendee(
                self.current_user.id,
                self.current_user.name,
                self.current_user.email,
                AttendeeStatus.ACCEPTED,
                is_organizer=True,
            )
        ]

        for user_id in attendee_ids:
            user = self.users.get(user_id)
            if user and user.id != self.current_user.id:
                attendees.append(
                    Attendee(user.id, user.name, user.email, AttendeeStatus.PENDING)
                )

        meeting = Meeting(
            id=meeting_id,
            title=title,
            description=description,
            meeting_type=m_type,
            start_time=start,
            end_time=end,
            location=location,
            organizer_id=self.current_user.id,
            attendees=attendees,
            recurrence=rec,
        )

        self.meetings[meeting_id] = meeting

        return {
            "success": True,
            "meeting_id": meeting_id,
            "title": title,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "attendees": len(attendees),
            "message": f"Meeting '{title}' scheduled for {start.strftime('%B %d at %I:%M %p')}",
        }

    def get_meeting(self, meeting_id: str) -> dict:
        """Get meeting details."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        return {
            "success": True,
            "meeting": {
                "id": meeting.id,
                "title": meeting.title,
                "description": meeting.description,
                "type": meeting.meeting_type.value,
                "start_time": meeting.start_time.isoformat(),
                "end_time": meeting.end_time.isoformat(),
                "duration_minutes": int(
                    (meeting.end_time - meeting.start_time).total_seconds() / 60
                ),
                "location": meeting.location,
                "status": meeting.status.value,
                "recurrence": meeting.recurrence.value,
                "organizer": next(
                    (a.name for a in meeting.attendees if a.is_organizer), "Unknown"
                ),
                "attendees": [
                    {
                        "name": a.name,
                        "email": a.email,
                        "status": a.status.value,
                        "is_organizer": a.is_organizer,
                        "is_optional": a.is_optional,
                    }
                    for a in meeting.attendees
                ],
                "agenda": [
                    {
                        "id": ag.id,
                        "title": ag.title,
                        "presenter": ag.presenter,
                        "duration_minutes": ag.duration_minutes,
                        "completed": ag.completed,
                    }
                    for ag in sorted(meeting.agenda, key=lambda x: x.order)
                ],
                "has_notes": meeting.notes is not None,
                "action_items_count": len(meeting.action_items),
            },
        }

    def list_meetings(
        self,
        start_date: str = None,
        end_date: str = None,
        status: str = None,
        include_past: bool = False,
    ) -> dict:
        """List meetings with filters."""
        meetings = list(self.meetings.values())

        # Filter by date range
        if start_date:
            start = datetime.fromisoformat(start_date)
            meetings = [m for m in meetings if m.start_time >= start]
        elif not include_past:
            meetings = [m for m in meetings if m.end_time >= datetime.now()]

        if end_date:
            end = datetime.fromisoformat(end_date)
            meetings = [m for m in meetings if m.start_time <= end]

        # Filter by status
        if status:
            try:
                stat = MeetingStatus[status.upper()]
                meetings = [m for m in meetings if m.status == stat]
            except KeyError:
                pass

        # Filter to user's meetings
        meetings = [
            m
            for m in meetings
            if any(a.user_id == self.current_user.id for a in m.attendees)
        ]

        # Sort by start time
        meetings.sort(key=lambda m: m.start_time)

        return {
            "success": True,
            "count": len(meetings),
            "meetings": [
                {
                    "id": m.id,
                    "title": m.title,
                    "type": m.meeting_type.value,
                    "start_time": m.start_time.isoformat(),
                    "end_time": m.end_time.isoformat(),
                    "status": m.status.value,
                    "location": m.location[:40] if len(m.location) > 40 else m.location,
                    "attendee_count": len(m.attendees),
                }
                for m in meetings
            ],
        }

    def update_attendance(self, meeting_id: str, status: str) -> dict:
        """Update current user's attendance status."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        try:
            att_status = AttendeeStatus[status.upper()]
        except KeyError:
            return {"success": False, "error": f"Invalid status: {status}"}

        # Find and update attendee
        for attendee in meeting.attendees:
            if attendee.user_id == self.current_user.id:
                attendee.status = att_status
                return {
                    "success": True,
                    "meeting_id": meeting_id,
                    "status": att_status.value,
                    "message": f"Attendance updated to {att_status.value}",
                }

        return {"success": False, "error": "You are not an attendee of this meeting"}

    def cancel_meeting(self, meeting_id: str, reason: str = "") -> dict:
        """Cancel a meeting."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        if meeting.organizer_id != self.current_user.id:
            return {
                "success": False,
                "error": "Only the organizer can cancel the meeting",
            }

        meeting.status = MeetingStatus.CANCELLED

        return {
            "success": True,
            "meeting_id": meeting_id,
            "message": f"Meeting '{meeting.title}' has been cancelled",
            "attendees_notified": len(meeting.attendees),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # AGENDA MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def add_agenda_item(
        self,
        meeting_id: str,
        title: str,
        description: str = "",
        presenter: str = "",
        duration_minutes: int = 10,
    ) -> dict:
        """Add an agenda item to a meeting."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        agenda_id = self._generate_id("AG")
        order = len(meeting.agenda) + 1

        item = AgendaItem(
            id=agenda_id,
            title=title,
            description=description,
            presenter=presenter,
            duration_minutes=duration_minutes,
            order=order,
        )
        meeting.agenda.append(item)

        return {
            "success": True,
            "agenda_item_id": agenda_id,
            "meeting_id": meeting_id,
            "message": f"Agenda item '{title}' added to meeting",
        }

    def get_agenda(self, meeting_id: str) -> dict:
        """Get meeting agenda."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        total_duration = sum(ag.duration_minutes for ag in meeting.agenda)

        return {
            "success": True,
            "meeting_id": meeting_id,
            "meeting_title": meeting.title,
            "total_duration_minutes": total_duration,
            "agenda": [
                {
                    "id": ag.id,
                    "order": ag.order,
                    "title": ag.title,
                    "description": ag.description,
                    "presenter": ag.presenter or "TBD",
                    "duration_minutes": ag.duration_minutes,
                    "completed": ag.completed,
                }
                for ag in sorted(meeting.agenda, key=lambda x: x.order)
            ],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # MEETING NOTES
    # ──────────────────────────────────────────────────────────────────────────

    def save_meeting_notes(
        self,
        meeting_id: str,
        summary: str,
        key_decisions: list = None,
        discussion_points: list = None,
        next_steps: list = None,
        raw_transcript: str = "",
    ) -> dict:
        """Save meeting notes."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        notes = MeetingNotes(
            meeting_id=meeting_id,
            raw_transcript=raw_transcript,
            summary=summary,
            key_decisions=key_decisions or [],
            discussion_points=discussion_points or [],
            next_steps=next_steps or [],
            created_by=self.current_user.id,
        )
        meeting.notes = notes
        meeting.status = MeetingStatus.COMPLETED

        return {
            "success": True,
            "meeting_id": meeting_id,
            "message": "Meeting notes saved successfully",
        }

    def get_meeting_notes(self, meeting_id: str) -> dict:
        """Get meeting notes."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        if not meeting.notes:
            return {"success": False, "error": "No notes recorded for this meeting"}

        notes = meeting.notes
        author = self.users.get(notes.created_by)

        return {
            "success": True,
            "meeting_id": meeting_id,
            "meeting_title": meeting.title,
            "notes": {
                "summary": notes.summary,
                "key_decisions": notes.key_decisions,
                "discussion_points": notes.discussion_points,
                "action_items": notes.action_items,
                "next_steps": notes.next_steps,
                "created_by": author.name if author else "Unknown",
                "created_at": notes.created_at.isoformat(),
            },
        }

    def summarize_transcript(self, meeting_id: str, transcript: str) -> dict:
        """Extract summary and action items from meeting transcript."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        # Simple NLP extraction (in production, use actual NLP/LLM)
        lines = transcript.strip().split("\n")

        # Extract potential action items (look for action phrases)
        action_patterns = [
            r"(?:I'll|I will|we'll|we will|can you|please|need to|should|must|have to)\s+(.+?)(?:\.|$)",
            r"(?:by|before|until)\s+(\w+day|\w+\s+\d+)",
            r"(\w+)\s+(?:will|to)\s+(.+?)(?:\.|$)",
        ]

        extracted_actions = []
        decisions = []
        discussion = []

        for line in lines:
            line_lower = line.lower()

            # Look for decisions
            if any(
                word in line_lower
                for word in ["decided", "agreed", "approved", "will go with"]
            ):
                decisions.append(line.strip())

            # Look for action items
            for pattern in action_patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = " ".join(match)
                    if len(match) > 10:  # Filter out short matches
                        extracted_actions.append(match.strip())

            # General discussion points
            if ":" in line and len(line) > 20:
                discussion.append(line.strip())

        # Remove duplicates
        extracted_actions = list(dict.fromkeys(extracted_actions))[:5]
        decisions = list(dict.fromkeys(decisions))[:5]
        discussion = discussion[:5]

        return {
            "success": True,
            "meeting_id": meeting_id,
            "extraction": {
                "potential_action_items": extracted_actions,
                "potential_decisions": decisions,
                "discussion_points": discussion,
                "transcript_length": len(transcript),
                "lines_processed": len(lines),
            },
            "note": "Review and edit extracted items before saving",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # ACTION ITEMS
    # ──────────────────────────────────────────────────────────────────────────

    def create_action_item(
        self,
        meeting_id: str,
        title: str,
        description: str,
        assignee_id: str,
        due_date: str,
        priority: str = "medium",
    ) -> dict:
        """Create an action item from a meeting."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return {"success": False, "error": f"Meeting {meeting_id} not found"}

        assignee = self.users.get(assignee_id)
        if not assignee:
            return {"success": False, "error": f"User {assignee_id} not found"}

        try:
            pri = ActionItemPriority[priority.upper()]
            due = datetime.strptime(due_date, "%Y-%m-%d").date()
        except (KeyError, ValueError) as e:
            return {"success": False, "error": f"Invalid input: {e}"}

        action_id = self._generate_id("ACT")

        action_item = ActionItem(
            id=action_id,
            meeting_id=meeting_id,
            title=title,
            description=description,
            assignee_id=assignee_id,
            assignee_name=assignee.name,
            due_date=due,
            priority=pri,
        )

        self.action_items[action_id] = action_item
        meeting.action_items.append(action_item)

        return {
            "success": True,
            "action_item_id": action_id,
            "meeting_id": meeting_id,
            "assigned_to": assignee.name,
            "due_date": due_date,
            "priority": priority,
            "message": f"Action item created and assigned to {assignee.name}",
        }

    def list_action_items(
        self,
        assignee_id: str = None,
        status: str = None,
        meeting_id: str = None,
        overdue_only: bool = False,
    ) -> dict:
        """List action items with filters."""
        items = list(self.action_items.values())

        # Default to current user
        if assignee_id:
            items = [i for i in items if i.assignee_id == assignee_id]
        else:
            items = [i for i in items if i.assignee_id == self.current_user.id]

        if status:
            try:
                stat = ActionItemStatus[status.upper()]
                items = [i for i in items if i.status == stat]
            except KeyError:
                pass

        if meeting_id:
            items = [i for i in items if i.meeting_id == meeting_id]

        if overdue_only:
            today = date.today()
            items = [
                i
                for i in items
                if i.due_date < today and i.status not in [ActionItemStatus.COMPLETED]
            ]

        # Update overdue status
        for item in items:
            if item.due_date < date.today() and item.status == ActionItemStatus.PENDING:
                item.status = ActionItemStatus.OVERDUE

        # Sort by due date
        items.sort(key=lambda i: (i.status.value, i.due_date))

        return {
            "success": True,
            "count": len(items),
            "action_items": [
                {
                    "id": i.id,
                    "title": i.title,
                    "meeting_id": i.meeting_id,
                    "assignee": i.assignee_name,
                    "due_date": i.due_date.isoformat(),
                    "priority": i.priority.value,
                    "status": i.status.value,
                    "is_overdue": i.due_date < date.today()
                    and i.status != ActionItemStatus.COMPLETED,
                }
                for i in items
            ],
        }

    def update_action_item(
        self, action_id: str, status: str = None, notes: str = None
    ) -> dict:
        """Update an action item."""
        item = self.action_items.get(action_id)
        if not item:
            return {"success": False, "error": f"Action item {action_id} not found"}

        if status:
            try:
                new_status = ActionItemStatus[status.upper()]
                item.status = new_status
                if new_status == ActionItemStatus.COMPLETED:
                    item.completed_at = datetime.now()
            except KeyError:
                return {"success": False, "error": f"Invalid status: {status}"}

        if notes:
            item.notes = notes

        return {
            "success": True,
            "action_item_id": action_id,
            "status": item.status.value,
            "message": f"Action item updated",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # DASHBOARD & REPORTS
    # ──────────────────────────────────────────────────────────────────────────

    def get_dashboard(self) -> dict:
        """Get meeting dashboard for current user."""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0)
        today_end = now.replace(hour=23, minute=59, second=59)
        week_end = now + timedelta(days=7)

        # Today's meetings
        today_meetings = [
            m
            for m in self.meetings.values()
            if today_start <= m.start_time <= today_end
            and any(a.user_id == self.current_user.id for a in m.attendees)
            and m.status == MeetingStatus.SCHEDULED
        ]

        # Upcoming this week
        upcoming = [
            m
            for m in self.meetings.values()
            if now < m.start_time <= week_end
            and any(a.user_id == self.current_user.id for a in m.attendees)
            and m.status == MeetingStatus.SCHEDULED
        ]

        # Pending RSVPs
        pending_rsvp = [
            m
            for m in self.meetings.values()
            if any(
                a.user_id == self.current_user.id and a.status == AttendeeStatus.PENDING
                for a in m.attendees
            )
            and m.status == MeetingStatus.SCHEDULED
        ]

        # My action items
        my_actions = [
            i
            for i in self.action_items.values()
            if i.assignee_id == self.current_user.id
            and i.status not in [ActionItemStatus.COMPLETED]
        ]
        overdue = [i for i in my_actions if i.due_date < date.today()]

        return {
            "success": True,
            "dashboard": {
                "today_meetings": len(today_meetings),
                "upcoming_this_week": len(upcoming),
                "pending_rsvp": len(pending_rsvp),
                "open_action_items": len(my_actions),
                "overdue_action_items": len(overdue),
                "next_meeting": (
                    {
                        "id": upcoming[0].id,
                        "title": upcoming[0].title,
                        "start_time": upcoming[0].start_time.isoformat(),
                        "location": upcoming[0].location,
                    }
                    if upcoming
                    else None
                ),
                "today_schedule": [
                    {
                        "id": m.id,
                        "title": m.title,
                        "time": m.start_time.strftime("%I:%M %p"),
                        "type": m.meeting_type.value,
                    }
                    for m in sorted(today_meetings, key=lambda x: x.start_time)
                ],
            },
        }

    def get_weekly_summary(self) -> dict:
        """Get summary of meetings from the past week."""
        week_ago = datetime.now() - timedelta(days=7)

        past_meetings = [
            m
            for m in self.meetings.values()
            if m.start_time >= week_ago
            and m.status == MeetingStatus.COMPLETED
            and any(a.user_id == self.current_user.id for a in m.attendees)
        ]

        # Count by type
        type_counts = {}
        for m in past_meetings:
            type_counts[m.meeting_type.value] = (
                type_counts.get(m.meeting_type.value, 0) + 1
            )

        # Total meeting hours
        total_hours = sum(
            (m.end_time - m.start_time).total_seconds() / 3600 for m in past_meetings
        )

        # Action items created this week
        week_actions = [
            i
            for i in self.action_items.values()
            if i.created_at >= week_ago and i.assignee_id == self.current_user.id
        ]

        return {
            "success": True,
            "summary": {
                "period": "Last 7 days",
                "meetings_attended": len(past_meetings),
                "total_meeting_hours": round(total_hours, 1),
                "meetings_by_type": type_counts,
                "action_items_received": len(week_actions),
                "action_items_completed": len(
                    [i for i in week_actions if i.status == ActionItemStatus.COMPLETED]
                ),
                "meetings": [
                    {
                        "title": m.title,
                        "date": m.start_time.strftime("%B %d"),
                        "has_notes": m.notes is not None,
                        "action_items": len(m.action_items),
                    }
                    for m in sorted(
                        past_meetings, key=lambda x: x.start_time, reverse=True
                    )[:5]
                ],
            },
        }

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
            "message": f"Switched to: {user.name}",
            "department": user.department,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Meeting & Notes Assistant for an enterprise organization.

Your role is to:
1. Help schedule and manage meetings
2. Create and organize meeting agendas
3. Record and summarize meeting notes
4. Extract and track action items
5. Send follow-up reminders

You have access to these tools:
- schedule_meeting: Schedule a new meeting
- get_meeting: Get meeting details
- list_meetings: List meetings with filters
- update_attendance: RSVP to meetings
- cancel_meeting: Cancel a meeting
- add_agenda_item: Add agenda item
- get_agenda: Get meeting agenda
- save_meeting_notes: Save notes after meeting
- get_meeting_notes: Retrieve meeting notes
- summarize_transcript: Extract key points from transcript
- create_action_item: Create action item
- list_action_items: List action items
- update_action_item: Update action item status
- get_dashboard: View meeting dashboard
- get_weekly_summary: Get weekly meeting summary

Be proactive about suggesting agendas for meetings. Help extract clear, actionable items from discussions. Keep meeting notes organized and searchable."""


# ══════════════════════════════════════════════════════════════════════════════
# AGENT TOOLS
# ══════════════════════════════════════════════════════════════════════════════


def create_meeting_tools(service: MeetingService) -> list:
    """Create tool definitions for the meeting agent."""
    return [
        {
            "name": "schedule_meeting",
            "description": "Schedule a new meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Meeting title"},
                    "description": {
                        "type": "string",
                        "description": "Meeting description",
                    },
                    "meeting_type": {
                        "type": "string",
                        "description": "Type: one_on_one, team_standup, project_update, brainstorm, client_call, etc.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes",
                    },
                    "location": {"type": "string", "description": "Room or video link"},
                    "attendee_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "User IDs to invite",
                    },
                    "recurrence": {
                        "type": "string",
                        "description": "Recurrence: none, daily, weekly, biweekly, monthly",
                    },
                },
                "required": [
                    "title",
                    "description",
                    "meeting_type",
                    "start_time",
                    "duration_minutes",
                    "location",
                    "attendee_ids",
                ],
            },
            "function": lambda title, description, meeting_type, start_time, duration_minutes, location, attendee_ids, recurrence="none": service.schedule_meeting(
                title,
                description,
                meeting_type,
                start_time,
                duration_minutes,
                location,
                attendee_ids,
                recurrence,
            ),
        },
        {
            "name": "get_meeting",
            "description": "Get meeting details",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"}
                },
                "required": ["meeting_id"],
            },
            "function": lambda meeting_id: service.get_meeting(meeting_id),
        },
        {
            "name": "list_meetings",
            "description": "List meetings with filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date filter (ISO format)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date filter (ISO format)",
                    },
                    "status": {"type": "string", "description": "Status filter"},
                    "include_past": {
                        "type": "boolean",
                        "description": "Include past meetings",
                    },
                },
            },
            "function": lambda start_date=None, end_date=None, status=None, include_past=False: service.list_meetings(
                start_date, end_date, status, include_past
            ),
        },
        {
            "name": "update_attendance",
            "description": "Update attendance status (RSVP)",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"},
                    "status": {
                        "type": "string",
                        "description": "Status: accepted, declined, tentative",
                    },
                },
                "required": ["meeting_id", "status"],
            },
            "function": lambda meeting_id, status: service.update_attendance(
                meeting_id, status
            ),
        },
        {
            "name": "add_agenda_item",
            "description": "Add an agenda item to a meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"},
                    "title": {"type": "string", "description": "Agenda item title"},
                    "description": {"type": "string", "description": "Description"},
                    "presenter": {
                        "type": "string",
                        "description": "Who presents this item",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Estimated duration",
                    },
                },
                "required": ["meeting_id", "title"],
            },
            "function": lambda meeting_id, title, description="", presenter="", duration_minutes=10: service.add_agenda_item(
                meeting_id, title, description, presenter, duration_minutes
            ),
        },
        {
            "name": "get_agenda",
            "description": "Get meeting agenda",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"}
                },
                "required": ["meeting_id"],
            },
            "function": lambda meeting_id: service.get_agenda(meeting_id),
        },
        {
            "name": "save_meeting_notes",
            "description": "Save meeting notes",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"},
                    "summary": {"type": "string", "description": "Meeting summary"},
                    "key_decisions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key decisions made",
                    },
                    "discussion_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Main discussion points",
                    },
                    "next_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Next steps",
                    },
                },
                "required": ["meeting_id", "summary"],
            },
            "function": lambda meeting_id, summary, key_decisions=None, discussion_points=None, next_steps=None: service.save_meeting_notes(
                meeting_id, summary, key_decisions, discussion_points, next_steps
            ),
        },
        {
            "name": "get_meeting_notes",
            "description": "Get meeting notes",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"}
                },
                "required": ["meeting_id"],
            },
            "function": lambda meeting_id: service.get_meeting_notes(meeting_id),
        },
        {
            "name": "summarize_transcript",
            "description": "Extract key points from meeting transcript",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"},
                    "transcript": {
                        "type": "string",
                        "description": "Meeting transcript text",
                    },
                },
                "required": ["meeting_id", "transcript"],
            },
            "function": lambda meeting_id, transcript: service.summarize_transcript(
                meeting_id, transcript
            ),
        },
        {
            "name": "create_action_item",
            "description": "Create an action item from a meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "Meeting ID"},
                    "title": {"type": "string", "description": "Action item title"},
                    "description": {"type": "string", "description": "Description"},
                    "assignee_id": {
                        "type": "string",
                        "description": "User ID to assign to",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date YYYY-MM-DD",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority: low, medium, high, urgent",
                    },
                },
                "required": [
                    "meeting_id",
                    "title",
                    "description",
                    "assignee_id",
                    "due_date",
                ],
            },
            "function": lambda meeting_id, title, description, assignee_id, due_date, priority="medium": service.create_action_item(
                meeting_id, title, description, assignee_id, due_date, priority
            ),
        },
        {
            "name": "list_action_items",
            "description": "List action items",
            "parameters": {
                "type": "object",
                "properties": {
                    "assignee_id": {
                        "type": "string",
                        "description": "Filter by assignee",
                    },
                    "status": {"type": "string", "description": "Filter by status"},
                    "meeting_id": {
                        "type": "string",
                        "description": "Filter by meeting",
                    },
                    "overdue_only": {
                        "type": "boolean",
                        "description": "Show only overdue items",
                    },
                },
            },
            "function": lambda assignee_id=None, status=None, meeting_id=None, overdue_only=False: service.list_action_items(
                assignee_id, status, meeting_id, overdue_only
            ),
        },
        {
            "name": "update_action_item",
            "description": "Update action item status",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "string", "description": "Action item ID"},
                    "status": {
                        "type": "string",
                        "description": "Status: pending, in_progress, completed",
                    },
                    "notes": {"type": "string", "description": "Notes"},
                },
                "required": ["action_id"],
            },
            "function": lambda action_id, status=None, notes=None: service.update_action_item(
                action_id, status, notes
            ),
        },
        {
            "name": "get_dashboard",
            "description": "Get meeting dashboard",
            "parameters": {"type": "object", "properties": {}},
            "function": lambda: service.get_dashboard(),
        },
        {
            "name": "get_weekly_summary",
            "description": "Get weekly meeting summary",
            "parameters": {"type": "object", "properties": {}},
            "function": lambda: service.get_weekly_summary(),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# DEMO AND INTERACTIVE MODES
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate meeting assistant capabilities."""
    print("=" * 70)
    print("MEETING & NOTES ASSISTANT - DEMO MODE")
    print("=" * 70)

    service = MeetingService()

    # Dashboard
    print("\n📊 MEETING DASHBOARD")
    print("-" * 50)
    dashboard = service.get_dashboard()
    d = dashboard["dashboard"]
    print(f"Today's meetings: {d['today_meetings']}")
    print(f"Upcoming this week: {d['upcoming_this_week']}")
    print(f"Pending RSVPs: {d['pending_rsvp']}")
    print(f"Open action items: {d['open_action_items']}")
    print(f"Overdue items: {d['overdue_action_items']}")

    if d["next_meeting"]:
        print(f"\nNext meeting: {d['next_meeting']['title']}")
        print(f"   Time: {d['next_meeting']['start_time']}")

    # List meetings
    print("\n📅 UPCOMING MEETINGS")
    print("-" * 50)
    meetings = service.list_meetings()
    for m in meetings["meetings"]:
        print(f"  [{m['type']}] {m['title']}")
        print(f"      {m['start_time'][:16]} | {m['location'][:30]}")

    # Get meeting details
    print("\n📋 MEETING DETAILS: Sprint Planning")
    print("-" * 50)
    meeting = service.get_meeting("MTG-001")
    m = meeting["meeting"]
    print(f"Title: {m['title']}")
    print(f"Status: {m['status']}")
    print(f"Attendees: {len(m['attendees'])}")
    print(f"Has notes: {m['has_notes']}")
    print(f"Action items: {m['action_items_count']}")

    # Get meeting notes
    print("\n📝 MEETING NOTES")
    print("-" * 50)
    notes = service.get_meeting_notes("MTG-001")
    n = notes["notes"]
    print(f"Summary: {n['summary'][:100]}...")
    print(f"\nKey Decisions:")
    for decision in n["key_decisions"][:3]:
        print(f"  • {decision}")
    print(f"\nAction Items:")
    for action in n["action_items"][:3]:
        print(f"  → {action}")

    # Action items
    print("\n✅ MY ACTION ITEMS")
    print("-" * 50)
    actions = service.list_action_items()
    for a in actions["action_items"]:
        status_icon = (
            "⚠️" if a["is_overdue"] else "○" if a["status"] == "pending" else "◐"
        )
        print(f"  {status_icon} [{a['priority']}] {a['title']}")
        print(f"      Due: {a['due_date']} | Status: {a['status']}")

    # Get agenda
    print("\n📑 MEETING AGENDA: Alice/Bob 1:1")
    print("-" * 50)
    agenda = service.get_agenda("MTG-003")
    print(f"Total duration: {agenda['total_duration_minutes']} minutes")
    for ag in agenda["agenda"]:
        print(
            f"  {ag['order']}. {ag['title']} ({ag['duration_minutes']}min) - {ag['presenter']}"
        )

    # Weekly summary
    print("\n📊 WEEKLY SUMMARY")
    print("-" * 50)
    summary = service.get_weekly_summary()
    s = summary["summary"]
    print(f"Meetings attended: {s['meetings_attended']}")
    print(f"Total meeting hours: {s['total_meeting_hours']}")
    print(f"Action items received: {s['action_items_received']}")
    print(f"Action items completed: {s['action_items_completed']}")

    print("\n" + "=" * 70)
    print("Demo complete! Run with --interactive for full chat mode.")
    print("=" * 70)


async def interactive():
    """Run interactive meeting assistant chat."""
    print("=" * 70)
    print("MEETING & NOTES ASSISTANT")
    print("=" * 70)
    print("\nWelcome! I can help you with:")
    print("  • Schedule and manage meetings")
    print("  • Create agendas and take notes")
    print("  • Track action items and follow-ups")
    print("\nType 'quit' to exit, 'demo' for demo mode.\n")

    service = MeetingService()
    tools = create_meeting_tools(service)

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
                print("\nGoodbye!")
                break

            if user_input.lower() == "demo":
                await demo()
                continue

            if user_input.lower() == "dashboard":
                result = service.get_dashboard()
                print(f"\n🤖 Assistant: {json.dumps(result, indent=2)}")
                continue

            if user_input.lower() == "actions":
                result = service.list_action_items()
                print(f"\n🤖 Assistant: {json.dumps(result, indent=2)}")
                continue

            if use_agent:
                response = await agent.chat(user_input)
                print(f"\n🤖 Assistant: {response}")
            else:
                print("\n🤖 Assistant: I understand your meeting request.")
                print("   Quick commands: 'dashboard', 'actions', 'demo'")

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
