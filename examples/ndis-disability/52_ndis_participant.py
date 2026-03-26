#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 52: NDIS Participant Portal Assistant
==============================================

Accessible portal assistant for NDIS participants and their families.
Helps participants understand and manage their NDIS plans in plain language.

CRITICAL: On-premise deployment for participant data privacy!

This assistant helps with:
- Plan explanation in plain language
- Budget tracking and remaining funds
- Service provider directory search
- Appointment scheduling
- Goal progress visualization
- Support request submission
- Document management
- Accessible design (screen reader friendly)

Architecture (Privacy-First):
    ┌──────────────────────────────────────────────────────────────┐
    │                    PARTICIPANT PORTAL                         │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐  │
    │  │  Ollama  │  │  Local Data  │  │   Portal Assistant     │  │
    │  │  (Local) │◄─┤  (Encrypted) │◄─┤  (This Application)    │  │
    │  └──────────┘  └──────────────┘  └────────────────────────┘  │
    │                                                               │
    │                  ACCESSIBLE UI                                │
    │       ┌─────────────────────────────────┐                    │
    │       │  🔊 Screen Reader Compatible    │                    │
    │       │  📱 Mobile Friendly             │                    │
    │       │  🎨 High Contrast Available     │                    │
    │       │  ⌨️  Keyboard Navigation        │                    │
    │       └─────────────────────────────────┘                    │
    └──────────────────────────────────────────────────────────────┘

IMPORTANT DISCLAIMERS:
    ⚠️  This is NOT the official NDIS myplace portal
    ⚠️  Always check myplace.ndis.gov.au for official information
    ⚠️  This is a demonstration/educational tool only
    ⚠️  All data shown is FICTIONAL

Accessibility Features:
    - Plain language explanations
    - Screen reader optimized output
    - Keyboard navigation support
    - High contrast text options
    - Audio descriptions available
    - Simple, uncluttered interface

Usage:
    python examples/52_ndis_participant.py
    python examples/52_ndis_participant.py --demo
    python examples/52_ndis_participant.py --accessible
    python examples/52_ndis_participant.py --audio

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b
"""

import asyncio
import argparse
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, Any
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# DISCLAIMERS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

PARTICIPANT_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                           IMPORTANT NOTICE                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This is NOT the official NDIS myplace portal.                               ║
║  This is a demonstration assistant to help you understand NDIS.              ║
║                                                                              ║
║  For your official NDIS information:                                         ║
║    • Visit: myplace.ndis.gov.au                                             ║
║    • Call: 1800 800 110                                                      ║
║    • Use the official NDIS app                                              ║
║                                                                              ║
║  All participant data shown here is FICTIONAL for demonstration.            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

ACCESSIBILITY_NOTICE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACCESSIBILITY OPTIONS                                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This assistant is designed for everyone. Available options:                  ║
║                                                                              ║
║  • Type 'speak' - Audio descriptions of your plan                           ║
║  • Type 'simple' - Extra simple language                                    ║
║  • Type 'large' - Larger, clearer text output                               ║
║  • Type 'help' - Step by step assistance                                    ║
║                                                                              ║
║  We're here to help! Take your time.                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


class SupportCategory(Enum):
    """NDIS Support Categories with plain language names."""

    CORE_DAILY = ("Core - Daily Activities", "Help with everyday tasks")
    CORE_CONSUMABLES = ("Core - Consumables", "Items you use up")
    CORE_SOCIAL = ("Core - Social & Community", "Getting out and about")
    CORE_TRANSPORT = ("Core - Transport", "Help getting places")
    CB_COORDINATION = ("CB - Support Coordination", "Help managing your plan")
    CB_DAILY = ("CB - Daily Living", "Learning daily skills")
    CB_RELATIONSHIPS = ("CB - Relationships", "Building connections")
    CB_HEALTH = ("CB - Health & Wellbeing", "Staying healthy")
    CB_LEARNING = ("CB - Lifelong Learning", "Education and learning")
    CB_WORK = ("CB - Employment", "Getting a job")
    CAPITAL_AT = ("Capital - Assistive Tech", "Equipment and technology")
    CAPITAL_HOME = ("Capital - Home Mods", "Changes to your home")

    def __init__(self, official_name: str, plain_name: str):
        self.official_name = official_name
        self.plain_name = plain_name


class GoalStatus(Enum):
    """Goal progress status."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "Working On It"
    ON_TRACK = "Going Well"
    NEEDS_ATTENTION = "Need Some Help"
    ACHIEVED = "Done!"


class AppointmentType(Enum):
    """Types of appointments."""

    THERAPY = "Therapy Session"
    SUPPORT_WORKER = "Support Worker Visit"
    COORDINATOR = "Meeting with Coordinator"
    MEDICAL = "Medical Appointment"
    COMMUNITY = "Community Activity"
    REVIEW = "Plan Review Meeting"
    OTHER = "Other"


# ══════════════════════════════════════════════════════════════════════════════
# PLAIN LANGUAGE TRANSLATOR
# ══════════════════════════════════════════════════════════════════════════════


class PlainLanguageTranslator:
    """
    Translates NDIS jargon into plain, accessible language.

    Designed to help participants understand their plans without
    needing to know official NDIS terminology.
    """

    TRANSLATIONS = {
        # Funding terms
        "core supports": "money for everyday help",
        "capacity building": "money to help you learn new skills",
        "capital supports": "money for equipment and home changes",
        "stated supports": "set amount for specific things",
        "flexible supports": "money you can use in different ways",
        "plan managed": "a plan manager handles your money",
        "self managed": "you handle your own money",
        "ndia managed": "NDIS pays providers directly",
        # Process terms
        "planning meeting": "a meeting to talk about what help you need",
        "plan review": "looking at your plan to see if it still works for you",
        "change of circumstances": "when something in your life changes",
        "reasonable and necessary": "things that help you and are fair to ask for",
        "mainstream services": "services everyone can use, like doctors",
        # People
        "support coordinator": "someone who helps you use your plan",
        "local area coordinator": "someone from NDIS who helps in your area",
        "lac": "someone from NDIS who helps in your area",
        "nominee": "someone who helps make decisions with you",
        "child representative": "a person helping a child use their plan",
        # Documents
        "service agreement": "a written promise between you and a provider",
        "quote": "how much something will cost",
        "invoice": "a bill for services",
    }

    @classmethod
    def translate(cls, text: str) -> str:
        """Translate NDIS jargon to plain language."""
        result = text.lower()
        for jargon, plain in cls.TRANSLATIONS.items():
            result = result.replace(jargon, plain)
        return result

    @classmethod
    def explain_budget(
        cls, category: SupportCategory, amount: float, spent: float
    ) -> str:
        """Explain a budget category in plain language."""
        remaining = amount - spent
        percentage = (spent / amount * 100) if amount > 0 else 0

        explanations = {
            SupportCategory.CORE_DAILY: "for help with things like getting dressed, showering, and meals",
            SupportCategory.CORE_SOCIAL: "for help to go places and meet people",
            SupportCategory.CORE_TRANSPORT: "to help you travel to appointments and activities",
            SupportCategory.CB_COORDINATION: "for someone to help you organize your supports",
            SupportCategory.CB_HEALTH: "to help you stay healthy and well",
            SupportCategory.CB_DAILY: "to learn skills for everyday life",
            SupportCategory.CB_WORK: "to help you find and keep a job",
            SupportCategory.CAPITAL_AT: "for equipment and technology that helps you",
        }

        base = explanations.get(category, "for your supports")

        if percentage < 25:
            status = "You've barely used this - lots left!"
        elif percentage < 50:
            status = "You've used some, plenty remaining."
        elif percentage < 75:
            status = "You've used about half."
        elif percentage < 90:
            status = "Getting lower - plan ahead."
        else:
            status = "Almost used up - talk to your coordinator."

        return f"""
💰 {category.plain_name}
   This money is {base}.
   
   Total: ${amount:,.2f}
   Used: ${spent:,.2f}
   Left: ${remaining:,.2f}
   
   {status}
"""


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ParticipantPlan:
    """Participant's NDIS plan - simplified view."""

    participant_id: str
    plan_number: str
    start_date: str
    end_date: str
    plan_type: str  # NDIA, Plan, Self managed
    total_funding: float
    budgets: dict  # category -> {"total": x, "spent": y}
    goals: list

    def days_remaining(self) -> int:
        """Calculate days until plan ends."""
        end = datetime.strptime(self.end_date, "%Y-%m-%d")
        return max(0, (end - datetime.now()).days)

    def total_spent(self) -> float:
        """Total spent across all categories."""
        return sum(b.get("spent", 0) for b in self.budgets.values())

    def total_remaining(self) -> float:
        """Total remaining funding."""
        return self.total_funding - self.total_spent()


@dataclass
class Goal:
    """A goal in the participant's plan."""

    goal_id: str
    statement: str
    plain_description: str
    category: str
    status: GoalStatus
    progress: int  # 0-100
    activities: list[str]
    next_steps: list[str]

    def progress_bar(self, width: int = 20) -> str:
        """Visual progress bar for accessibility."""
        filled = int(width * self.progress / 100)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return f"[{bar}] {self.progress}%"


@dataclass
class Appointment:
    """An upcoming appointment."""

    appointment_id: str
    appointment_type: AppointmentType
    provider_name: str
    date: str
    time: str
    location: str
    notes: str = ""
    reminder_sent: bool = False


@dataclass
class Provider:
    """A service provider."""

    provider_id: str
    name: str
    services: list[str]
    location: str
    phone: str
    email: str
    rating: float  # 1-5
    wheelchair_accessible: bool
    accepts_new_clients: bool
    plain_description: str


@dataclass
class SupportRequest:
    """A request for support or help."""

    request_id: str
    participant_id: str
    request_type: str
    description: str
    urgency: str  # routine, soon, urgent
    submitted_date: str
    status: str  # submitted, reviewed, actioned, closed


# ══════════════════════════════════════════════════════════════════════════════
# PARTICIPANT DATA STORE
# ══════════════════════════════════════════════════════════════════════════════


class ParticipantPortalStore:
    """Local data store for participant portal."""

    def __init__(self):
        self.plans: dict[str, ParticipantPlan] = {}
        self.goals: dict[str, list[Goal]] = {}
        self.appointments: dict[str, list[Appointment]] = {}
        self.providers: list[Provider] = []
        self.requests: list[SupportRequest] = []
        self.documents: dict[str, list[dict]] = {}

    def get_plan(self, participant_id: str) -> Optional[ParticipantPlan]:
        return self.plans.get(participant_id)

    def get_goals(self, participant_id: str) -> list[Goal]:
        return self.goals.get(participant_id, [])

    def get_appointments(self, participant_id: str) -> list[Appointment]:
        apps = self.appointments.get(participant_id, [])
        # Sort by date
        return sorted(apps, key=lambda x: f"{x.date} {x.time}")

    def get_upcoming_appointments(
        self, participant_id: str, days: int = 14
    ) -> list[Appointment]:
        """Get appointments in the next N days."""
        all_apps = self.get_appointments(participant_id)
        cutoff = datetime.now() + timedelta(days=days)
        upcoming = []

        for app in all_apps:
            try:
                app_date = datetime.strptime(app.date, "%Y-%m-%d")
                if datetime.now() <= app_date <= cutoff:
                    upcoming.append(app)
            except ValueError:
                pass

        return upcoming

    def search_providers(
        self,
        service_type: Optional[str] = None,
        location: Optional[str] = None,
        wheelchair_accessible: Optional[bool] = None,
    ) -> list[Provider]:
        """Search for providers with filters."""
        results = self.providers

        if service_type:
            service_lower = service_type.lower()
            results = [
                p
                for p in results
                if any(service_lower in s.lower() for s in p.services)
            ]

        if location:
            location_lower = location.lower()
            results = [p for p in results if location_lower in p.location.lower()]

        if wheelchair_accessible is not None:
            results = [
                p for p in results if p.wheelchair_accessible == wheelchair_accessible
            ]

        return results

    def submit_request(self, request: SupportRequest) -> str:
        """Submit a support request."""
        self.requests.append(request)
        return request.request_id

    def get_documents(self, participant_id: str) -> list[dict]:
        """Get uploaded documents."""
        return self.documents.get(participant_id, [])

    def add_document(self, participant_id: str, doc: dict):
        """Add a document record."""
        if participant_id not in self.documents:
            self.documents[participant_id] = []
        self.documents[participant_id].append(doc)


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA GENERATOR
# ══════════════════════════════════════════════════════════════════════════════


class DemoDataGenerator:
    """Generate realistic demo data for participants."""

    @staticmethod
    def create_demo_plan() -> ParticipantPlan:
        """Create a demo plan."""
        return ParticipantPlan(
            participant_id="DEMO001",
            plan_number=f"PLN{secrets.randbelow(1000000):06d}",
            start_date=(datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),
            end_date=(datetime.now() + timedelta(days=185)).strftime("%Y-%m-%d"),
            plan_type="Plan Managed",
            total_funding=65000.00,
            budgets={
                "core_daily": {"total": 35000, "spent": 14000},
                "core_social": {"total": 12000, "spent": 4800},
                "core_transport": {"total": 3000, "spent": 1200},
                "cb_coordination": {"total": 8000, "spent": 3500},
                "cb_health": {"total": 5000, "spent": 1500},
                "capital_at": {"total": 2000, "spent": 800},
            },
            goals=[],
        )

    @staticmethod
    def create_demo_goals() -> list[Goal]:
        """Create demo goals."""
        return [
            Goal(
                goal_id="G001",
                statement="Increase independence in daily living activities",
                plain_description="I want to do more things by myself at home, like cooking and cleaning",
                category="Daily Living",
                status=GoalStatus.IN_PROGRESS,
                progress=45,
                activities=[
                    "Learning to cook simple meals",
                    "Practicing cleaning routines",
                    "Managing personal hygiene",
                ],
                next_steps=[
                    "Try a new recipe each week",
                    "Create a weekly cleaning schedule",
                ],
            ),
            Goal(
                goal_id="G002",
                statement="Improve social connections and community participation",
                plain_description="I want to make more friends and do fun activities outside",
                category="Social & Community",
                status=GoalStatus.ON_TRACK,
                progress=60,
                activities=[
                    "Joining a local social group",
                    "Attending community events",
                    "Catching up with friends weekly",
                ],
                next_steps=[
                    "Join the art class at community centre",
                    "Plan a coffee catch-up with new friend",
                ],
            ),
            Goal(
                goal_id="G003",
                statement="Maintain health and wellbeing",
                plain_description="I want to stay healthy and feel good",
                category="Health & Wellbeing",
                status=GoalStatus.ON_TRACK,
                progress=70,
                activities=[
                    "Regular exercise program",
                    "Attending therapy sessions",
                    "Eating healthier foods",
                ],
                next_steps=["Continue weekly swimming", "Book next physio appointment"],
            ),
        ]

    @staticmethod
    def create_demo_appointments() -> list[Appointment]:
        """Create demo appointments."""
        base_date = datetime.now()
        return [
            Appointment(
                appointment_id="A001",
                appointment_type=AppointmentType.SUPPORT_WORKER,
                provider_name="Disability Support Services",  # Generic name
                date=(base_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                time="10:00",
                location="Your home",
                notes="Weekly support visit - shopping and cooking",
            ),
            Appointment(
                appointment_id="A002",
                appointment_type=AppointmentType.THERAPY,
                provider_name="Allied Health Group",  # Generic name
                date=(base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
                time="14:30",
                location="15 Sample Street, Exampletown SA 5000",
                notes="Occupational therapy session",
            ),
            Appointment(
                appointment_id="A003",
                appointment_type=AppointmentType.COMMUNITY,
                provider_name="Community Connect",  # Generic name
                date=(base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                time="11:00",
                location="Community Centre, Main Road",
                notes="Art class - bring apron!",
            ),
            Appointment(
                appointment_id="A004",
                appointment_type=AppointmentType.COORDINATOR,
                provider_name="Lisa (Support Coordinator)",  # Generic name
                date=(base_date + timedelta(days=10)).strftime("%Y-%m-%d"),
                time="09:30",
                location="Phone call",
                notes="Catch up about how things are going",
            ),
        ]

    @staticmethod
    def create_demo_providers() -> list[Provider]:
        """Create demo providers."""
        return [
            Provider(
                provider_id="PRV001",
                name="Disability Support Services",  # Generic name
                services=["Personal care", "Community access", "Domestic assistance"],
                location="Metro Area",
                phone="08 1234 5678",
                email="contact@example-provider.com.au",
                rating=4.5,
                wheelchair_accessible=True,
                accepts_new_clients=True,
                plain_description="We help you with everyday things at home and getting out in the community",
            ),
            Provider(
                provider_id="PRV002",
                name="Allied Health Group",  # Generic name
                services=["Occupational therapy", "Physiotherapy", "Speech therapy"],
                location="City Centre",
                phone="08 2345 6789",
                email="info@example-health.com.au",
                rating=4.8,
                wheelchair_accessible=True,
                accepts_new_clients=True,
                plain_description="Therapists who help you improve your skills and stay healthy",
            ),
            Provider(
                provider_id="PRV003",
                name="Community Connect",  # Generic name
                services=["Social skills", "Community groups", "Recreation"],
                location="Various locations",
                phone="08 3456 7890",
                email="hello@example-social.com.au",
                rating=4.7,
                wheelchair_accessible=True,
                accepts_new_clients=True,
                plain_description="Fun activities and groups to help you make friends",
            ),
            Provider(
                provider_id="PRV004",
                name="Support Network Transport",  # Generic name
                services=["Transport", "Travel training"],
                location="Metro Area",
                phone="08 4567 8901",
                email="book@example-transport.com.au",
                rating=4.3,
                wheelchair_accessible=True,
                accepts_new_clients=True,
                plain_description="We drive you where you need to go",
            ),
            Provider(
                provider_id="PRV005",
                name="Independence Plus",  # Generic name
                services=["Assistive technology", "Equipment", "Home modifications"],
                location="Metro Area",
                phone="08 5678 9012",
                email="help@example-assistive.com.au",
                rating=4.6,
                wheelchair_accessible=True,
                accepts_new_clients=True,
                plain_description="Help you find equipment and technology to make life easier",
            ),
        ]


# ══════════════════════════════════════════════════════════════════════════════
# PARTICIPANT PORTAL ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class ParticipantPortalAssistant:
    """
    Accessible assistant for NDIS participants.

    Features:
    - Plain language explanations
    - Screen reader compatible output
    - Simple navigation
    - Audio descriptions (optional)
    """

    def __init__(
        self,
        store: ParticipantPortalStore,
        participant_id: str,
        accessible_mode: bool = True,
    ):
        self.store = store
        self.participant_id = participant_id
        self.accessible_mode = accessible_mode
        self.translator = PlainLanguageTranslator()

    def format_heading(self, text: str) -> str:
        """Format a heading for accessibility."""
        if self.accessible_mode:
            return f"\n{'=' * 60}\n  {text}\n{'=' * 60}\n"
        return f"\n{text}\n{'-' * len(text)}\n"

    def welcome_message(self) -> str:
        """Get personalized welcome message."""
        plan = self.store.get_plan(self.participant_id)
        appointments = self.store.get_upcoming_appointments(self.participant_id, days=7)

        greeting = (
            "Good morning"
            if datetime.now().hour < 12
            else "Good afternoon" if datetime.now().hour < 17 else "Good evening"
        )

        output = f"""
{self.format_heading(f"{greeting}! Welcome to Your NDIS Portal")}

Here's a quick look at what's happening:

📅 COMING UP THIS WEEK
"""
        if appointments:
            for app in appointments[:3]:
                output += f"   • {app.date} at {app.time} - {app.provider_name}\n"
        else:
            output += "   No appointments this week.\n"

        if plan:
            remaining = plan.total_remaining()
            days = plan.days_remaining()
            output += f"""
💰 YOUR PLAN
   Money remaining: ${remaining:,.2f}
   Days until plan review: {days}
"""
            if days < 60:
                output += "   ⚠️  Your plan review is coming up soon!\n"

        output += """
What would you like to do?
   1. Check my budget
   2. See my goals
   3. View appointments
   4. Find a provider
   5. Ask for help
   6. Learn about NDIS

Type a number or just tell me what you need!
"""
        return output

    def explain_plan(self) -> str:
        """Explain the participant's plan in plain language."""
        plan = self.store.get_plan(self.participant_id)

        if not plan:
            return "I couldn't find your plan. Please contact your coordinator."

        output = self.format_heading("Your NDIS Plan Explained")

        output += f"""
🗓️ PLAN DATES
   Your plan started: {plan.start_date}
   Your plan ends: {plan.end_date}
   Days remaining: {plan.days_remaining()}

💼 HOW YOUR PLAN IS MANAGED
   Your plan is "{plan.plan_type}".
"""
        if plan.plan_type == "Plan Managed":
            output += """
   This means a Plan Manager handles the money for you.
   They pay your providers and keep track of spending.
   You don't need to worry about invoices!
"""
        elif plan.plan_type == "Self Managed":
            output += """
   This means you handle your own money.
   You pay providers and claim the money back.
   You have more control but more paperwork.
"""
        else:  # NDIA Managed
            output += """
   This means NDIS pays providers directly.
   You just use your services and NDIS handles the rest.
"""

        output += """
💰 YOUR MONEY

Your plan has ${:,.2f} in total. Here's how it's divided:
""".format(
            plan.total_funding
        )

        category_names = {
            "core_daily": SupportCategory.CORE_DAILY,
            "core_social": SupportCategory.CORE_SOCIAL,
            "core_transport": SupportCategory.CORE_TRANSPORT,
            "cb_coordination": SupportCategory.CB_COORDINATION,
            "cb_health": SupportCategory.CB_HEALTH,
            "capital_at": SupportCategory.CAPITAL_AT,
        }

        for key, budget in plan.budgets.items():
            if key in category_names:
                cat = category_names[key]
                output += self.translator.explain_budget(
                    cat, budget["total"], budget["spent"]
                )

        return output

    def show_budget_summary(self) -> str:
        """Show simple budget summary with visual aids."""
        plan = self.store.get_plan(self.participant_id)

        if not plan:
            return "I couldn't find your plan."

        output = self.format_heading("Your Budget at a Glance")

        total = plan.total_funding
        spent = plan.total_spent()
        remaining = plan.total_remaining()
        percent_used = (spent / total * 100) if total > 0 else 0

        # Visual progress bar
        bar_width = 30
        filled = int(bar_width * percent_used / 100)
        empty = bar_width - filled
        bar = "█" * filled + "░" * empty

        output += f"""
TOTAL PLAN: ${total:,.2f}

[{bar}] {percent_used:.0f}% used

✅ Spent: ${spent:,.2f}
💵 Remaining: ${remaining:,.2f}

"""
        # Simple breakdown
        output += "BY CATEGORY:\n\n"

        category_emojis = {
            "core_daily": "🏠",
            "core_social": "👥",
            "core_transport": "🚗",
            "cb_coordination": "📋",
            "cb_health": "💪",
            "capital_at": "🔧",
        }

        category_names = {
            "core_daily": "Daily Help",
            "core_social": "Social Activities",
            "core_transport": "Transport",
            "cb_coordination": "Coordination",
            "cb_health": "Health",
            "capital_at": "Equipment",
        }

        for key, budget in plan.budgets.items():
            emoji = category_emojis.get(key, "📌")
            name = category_names.get(key, key)
            total_cat = budget["total"]
            spent_cat = budget["spent"]
            remaining_cat = total_cat - spent_cat
            pct = (spent_cat / total_cat * 100) if total_cat > 0 else 0

            small_bar_filled = int(10 * pct / 100)
            small_bar_empty = 10 - small_bar_filled
            small_bar = "█" * small_bar_filled + "░" * small_bar_empty

            output += f"{emoji} {name}\n"
            output += (
                f"   [{small_bar}] ${remaining_cat:,.0f} left of ${total_cat:,.0f}\n\n"
            )

        return output

    def show_goals(self) -> str:
        """Display goals with progress."""
        goals = self.store.get_goals(self.participant_id)

        if not goals:
            return "No goals found in your plan."

        output = self.format_heading("Your Goals")
        output += """
Your goals are the things you want to achieve. 
Here's how you're going:

"""
        for i, goal in enumerate(goals, 1):
            status_emoji = {
                GoalStatus.NOT_STARTED: "⬜",
                GoalStatus.IN_PROGRESS: "🔄",
                GoalStatus.ON_TRACK: "✅",
                GoalStatus.NEEDS_ATTENTION: "⚠️",
                GoalStatus.ACHIEVED: "🎉",
            }.get(goal.status, "📌")

            output += f"""
{status_emoji} GOAL {i}: {goal.plain_description}
   Status: {goal.status.value}
   Progress: {goal.progress_bar()}
   
   What we're doing:
"""
            for activity in goal.activities:
                output += f"     • {activity}\n"

            output += "\n   Next steps:\n"
            for step in goal.next_steps:
                output += f"     → {step}\n"
            output += "\n"

        return output

    def show_appointments(self, days: int = 14) -> str:
        """Show upcoming appointments."""
        appointments = self.store.get_upcoming_appointments(self.participant_id, days)

        output = self.format_heading(f"Your Appointments (Next {days} Days)")

        if not appointments:
            output += """
No appointments scheduled for the next {days} days.

Would you like to:
• Book a new appointment
• See all future appointments
• Contact your coordinator

Type 'book' to schedule something.
"""
            return output

        output += "\n"

        current_date = None
        for app in appointments:
            # Group by date for easier reading
            if app.date != current_date:
                # Parse and format date nicely
                try:
                    date_obj = datetime.strptime(app.date, "%Y-%m-%d")
                    nice_date = date_obj.strftime("%A, %d %B")
                except ValueError:
                    nice_date = app.date

                output += f"\n📅 {nice_date}\n"
                output += "─" * 40 + "\n"
                current_date = app.date

            type_emoji = {
                AppointmentType.THERAPY: "💪",
                AppointmentType.SUPPORT_WORKER: "🏠",
                AppointmentType.COORDINATOR: "📋",
                AppointmentType.MEDICAL: "🏥",
                AppointmentType.COMMUNITY: "👥",
                AppointmentType.REVIEW: "📝",
            }.get(app.appointment_type, "📌")

            output += f"""
   {type_emoji} {app.time} - {app.appointment_type.value}
      Provider: {app.provider_name}
      Where: {app.location}
"""
            if app.notes:
                output += f"      Note: {app.notes}\n"

        output += """
─────────────────────────────────────────

Need to change an appointment? Type 'reschedule'.
"""
        return output

    def search_providers(self, service_type: str = "", location: str = "") -> str:
        """Search for service providers."""
        providers = self.store.search_providers(
            service_type=service_type if service_type else None,
            location=location if location else None,
        )

        output = self.format_heading("Service Providers")

        if not providers:
            output += """
No providers found matching your search.

Try:
• A different service type (e.g., 'therapy', 'transport')
• A different location
• Removing some filters

Or contact your coordinator for help finding providers.
"""
            return output

        output += f"\nFound {len(providers)} providers:\n\n"

        for provider in providers:
            stars = "⭐" * int(provider.rating)
            wheelchair = (
                "♿ Wheelchair accessible" if provider.wheelchair_accessible else ""
            )
            new_clients = (
                "✅ Taking new clients"
                if provider.accepts_new_clients
                else "⏸️ Waitlist"
            )

            output += f"""
{'─' * 50}
🏢 {provider.name}
   {provider.plain_description}
   
   Services: {', '.join(provider.services)}
   Location: {provider.location}
   Phone: {provider.phone}
   Rating: {stars} ({provider.rating}/5)
   
   {wheelchair}
   {new_clients}
"""

        output += f"\n{'─' * 50}\n"
        output += "\nTo contact a provider, type 'contact' followed by their name.\n"

        return output

    def submit_help_request(
        self, request_type: str, description: str, urgency: str = "routine"
    ) -> str:
        """Submit a request for help."""
        request = SupportRequest(
            request_id=f"REQ{secrets.randbelow(100000):05d}",
            participant_id=self.participant_id,
            request_type=request_type,
            description=description,
            urgency=urgency,
            submitted_date=datetime.now().strftime("%Y-%m-%d"),
            status="submitted",
        )

        self.store.submit_request(request)

        return f"""
{self.format_heading("Request Submitted")}

✅ Your request has been submitted!

Request ID: {request.request_id}
Type: {request_type}
Urgency: {urgency}

What happens next:
1. Your coordinator will see this request
2. They will contact you to discuss
3. You'll get help with what you need

{"⚠️ Because you marked this as URGENT, someone will contact you within 24 hours." if urgency == "urgent" else ""}

If you need immediate help, please call your coordinator directly.
"""

    def explain_ndis_term(self, term: str) -> str:
        """Explain an NDIS term in plain language."""
        output = self.format_heading(f"What does '{term}' mean?")

        translation = self.translator.TRANSLATIONS.get(term.lower())

        if translation:
            output += f"""
📖 {term.title()}

In simple words: {translation}

"""
        else:
            output += f"""
I don't have a specific explanation for '{term}'.

Some things to try:
• Ask your coordinator
• Visit ndis.gov.au/glossary
• Call NDIS on 1800 800 110

Would you like me to look up something else?
"""

        return output


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run demonstration."""
    print(PARTICIPANT_DISCLAIMER)
    print(ACCESSIBILITY_NOTICE)

    # Initialize
    print("\n📦 Setting up demo portal...")
    store = ParticipantPortalStore()

    # Load demo data
    participant_id = "DEMO001"
    store.plans[participant_id] = DemoDataGenerator.create_demo_plan()
    store.goals[participant_id] = DemoDataGenerator.create_demo_goals()
    store.appointments[participant_id] = DemoDataGenerator.create_demo_appointments()
    store.providers = DemoDataGenerator.create_demo_providers()

    assistant = ParticipantPortalAssistant(store, participant_id)

    # Demo sequence
    print(assistant.welcome_message())
    input("\nPress Enter to see your budget...")

    print(assistant.show_budget_summary())
    input("\nPress Enter to see your goals...")

    print(assistant.show_goals())
    input("\nPress Enter to see your appointments...")

    print(assistant.show_appointments())
    input("\nPress Enter to search for providers...")

    print(assistant.search_providers(service_type="therapy"))
    input("\nPress Enter to see plan explanation...")

    print(assistant.explain_plan())

    print("\n" + "=" * 60)
    print("🎉 Demo complete!")
    print("=" * 60)


def run_interactive():
    """Run interactive mode."""
    print(PARTICIPANT_DISCLAIMER)
    print(ACCESSIBILITY_NOTICE)

    # Setup
    store = ParticipantPortalStore()
    participant_id = "DEMO001"
    store.plans[participant_id] = DemoDataGenerator.create_demo_plan()
    store.goals[participant_id] = DemoDataGenerator.create_demo_goals()
    store.appointments[participant_id] = DemoDataGenerator.create_demo_appointments()
    store.providers = DemoDataGenerator.create_demo_providers()

    assistant = ParticipantPortalAssistant(store, participant_id)

    print(assistant.welcome_message())

    while True:
        try:
            cmd = input("\n🎤 You: ").strip().lower()

            if not cmd:
                continue

            if cmd in ("quit", "exit", "bye"):
                print("\nGoodbye! Take care. 👋")
                break

            elif cmd in ("1", "budget", "money"):
                print(assistant.show_budget_summary())

            elif cmd in ("2", "goals"):
                print(assistant.show_goals())

            elif cmd in ("3", "appointments", "calendar"):
                print(assistant.show_appointments())

            elif cmd in ("4", "providers", "find"):
                service = input(
                    "What type of service? (or press Enter for all): "
                ).strip()
                print(assistant.search_providers(service_type=service))

            elif cmd in ("5", "help", "support"):
                print(
                    assistant.submit_help_request(
                        request_type="General Support",
                        description="Participant needs assistance",
                        urgency="routine",
                    )
                )

            elif cmd in ("6", "learn", "explain"):
                term = input("What NDIS term would you like explained? ").strip()
                print(assistant.explain_ndis_term(term))

            elif cmd == "plan":
                print(assistant.explain_plan())

            else:
                print(
                    """
I didn't quite understand. Try:
  1 or 'budget' - Check your budget
  2 or 'goals' - See your goals  
  3 or 'appointments' - View calendar
  4 or 'providers' - Find providers
  5 or 'help' - Ask for help
  6 or 'learn' - Learn about NDIS
  'quit' - Exit
"""
                )

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="NDIS Participant Portal Assistant",
        epilog="DISCLAIMER: This is NOT the official NDIS portal.",
    )

    parser.add_argument("--demo", action="store_true", help="Run demonstration")
    parser.add_argument(
        "--accessible", action="store_true", help="Enhanced accessibility"
    )
    parser.add_argument(
        "--audio", action="store_true", help="Enable audio descriptions"
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
