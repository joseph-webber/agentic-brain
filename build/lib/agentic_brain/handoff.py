# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env python3
"""
Bot Handoff Protocol - Conversation Transfer Between Agents
============================================================

Allows agentic-brain bots to hand over conversations to other bots
seamlessly. Critical for complex multi-organization workflows.

EXAMPLE FLOW:
=============

1. User starts with "Find Legal Help" bot
   ↓
2. Bot identifies user needs family law help in Sydney
   ↓
3. Bot hands conversation to "Legal Aid NSW" bot
   ↓
4. Legal Aid bot provides specific advice
   ↓
5. Legal Aid bot hands to "Court Filing" bot
   ↓
6. Court Filing bot helps tender documents

HANDOFF TYPES:
==============

1. WARM HANDOFF - Both bots briefly overlap
   - Introducing bot stays connected momentarily
   - Ensures smooth transition
   - User sees "Connecting you to..."

2. COLD HANDOFF - Direct transfer
   - Instant switch to new bot
   - Faster but more abrupt
   - Good for internal transfers

3. SUPERVISED HANDOFF - Human in the loop
   - Human agent monitors transition
   - Can intervene if needed
   - For sensitive situations

4. ESCALATION - To human
   - Bot recognizes limits
   - Transfers to human agent
   - With full context

CONTEXT PRESERVATION:
=====================

When handing off, the context packet includes:
- Conversation history
- User identity (if known)
- Case details (if applicable)
- Emotional state assessment
- Safety flags
- What the user needs

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later
"""

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


# =============================================================================
# HANDOFF TYPES AND STATUS
# =============================================================================


class HandoffType(Enum):
    """Type of conversation handoff."""

    WARM = "warm"  # Overlap period
    COLD = "cold"  # Instant transfer
    SUPERVISED = "supervised"  # Human monitors
    ESCALATION = "escalation"  # To human agent


class HandoffStatus(Enum):
    """Status of a handoff operation."""

    PENDING = "pending"
    INITIATED = "initiated"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class HandoffReason(Enum):
    """Why the handoff is happening."""

    SPECIALIZATION = "specialization"  # Target bot is more specialized
    JURISDICTION = "jurisdiction"  # Different org/domain
    ESCALATION = "escalation"  # Needs higher authority
    USER_REQUEST = "user_request"  # User asked to transfer
    SAFETY = "safety"  # Safety concern
    LANGUAGE = "language"  # Language preference
    COMPLEXITY = "complexity"  # Too complex for current bot
    COMPLETION = "completion"  # Task completed, next phase


# =============================================================================
# CONTEXT PACKET - What gets transferred
# =============================================================================

# =============================================================================
# IDENTITY VERIFICATION - Critical for secure handoffs
# =============================================================================


class IdentityVerificationLevel(Enum):
    """Level of identity verification achieved."""

    NONE = "none"  # No verification attempted
    SELF_DECLARED = "self_declared"  # User provided details, unverified
    EMAIL_VERIFIED = "email"  # Email address verified
    PHONE_VERIFIED = "phone"  # Phone number verified (SMS OTP)
    DOCUMENT_VERIFIED = "document"  # ID document verified
    MYGOVID_VERIFIED = "mygovid"  # Australian myGovID verified
    COURT_VERIFIED = "court"  # Court system verified identity
    LAWYER_VERIFIED = "lawyer"  # Law firm verified client


class IdentityDocumentType(Enum):
    """Types of identity documents."""

    DRIVERS_LICENCE = "drivers_licence"
    PASSPORT = "passport"
    MEDICARE_CARD = "medicare"
    BIRTH_CERTIFICATE = "birth_certificate"
    CITIZENSHIP_CERTIFICATE = "citizenship"
    IMMICARD = "immicard"
    PHOTO_ID = "photo_id"
    PROOF_OF_AGE = "proof_of_age"


@dataclass
class IdentityVerification:
    """
    Identity verification status for handoff.

    When handing off between bots, the receiving bot needs to know:
    1. Has this person been verified?
    2. To what level?
    3. What IDs link to their records?
    """

    # Verification status
    is_verified: bool = False
    verification_level: IdentityVerificationLevel = IdentityVerificationLevel.NONE
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None  # Which system/bot verified

    # Verification methods used
    verification_methods: List[str] = field(default_factory=list)
    documents_sighted: List[IdentityDocumentType] = field(default_factory=list)

    # Confidence score (0.0 to 1.0)
    confidence_score: float = 0.0

    # Verification token (encrypted, for receiving bot to validate)
    verification_token: Optional[str] = None
    token_expires: Optional[datetime] = None

    def is_valid(self) -> bool:
        """Check if verification is still valid."""
        if not self.is_verified:
            return False
        return not (self.token_expires and datetime.now() > self.token_expires)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transmission."""
        return {
            "is_verified": self.is_verified,
            "verification_level": self.verification_level.value,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verified_by": self.verified_by,
            "verification_methods": self.verification_methods,
            "documents_sighted": [d.value for d in self.documents_sighted],
            "confidence_score": self.confidence_score,
            "verification_token": self.verification_token,
            "token_expires": (
                self.token_expires.isoformat() if self.token_expires else None
            ),
        }


@dataclass
class MasterDataReference:
    """
    References to master data records across systems.

    When handing off, the receiving bot may need to look up
    the user's records in various systems.
    """

    # Court systems
    court_case_id: Optional[str] = None  # e.g., "SYC1234/2024"
    court_file_number: Optional[str] = None  # Full file number
    comcourts_id: Optional[str] = None  # Commonwealth Courts Portal ID

    # Legal Aid
    legal_aid_client_id: Optional[str] = None  # Legal Aid client number
    legal_aid_matter_id: Optional[str] = None  # Matter reference
    legal_aid_grant_id: Optional[str] = None  # Grant of aid number

    # Law firm
    law_firm_client_id: Optional[str] = None  # Firm's client ID
    law_firm_matter_id: Optional[str] = None  # Firm's matter number

    # Government services
    services_australia_crn: Optional[str] = None  # Customer Reference Number
    child_support_case_id: Optional[str] = None  # Child Support case
    centrelink_crn: Optional[str] = None  # Centrelink CRN

    # CMMS references (for enterprise integrations)
    sap_bp_id: Optional[str] = None  # SAP Business Partner ID
    dynamics_contact_id: Optional[str] = None  # Dynamics 365 Contact ID
    salesforce_id: Optional[str] = None  # Salesforce ID

    # Child protection
    child_protection_case_id: Optional[str] = None
    child_protection_state: Optional[str] = None

    # Generic external IDs
    external_ids: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transmission."""
        return {
            "court_case_id": self.court_case_id,
            "court_file_number": self.court_file_number,
            "comcourts_id": self.comcourts_id,
            "legal_aid_client_id": self.legal_aid_client_id,
            "legal_aid_matter_id": self.legal_aid_matter_id,
            "legal_aid_grant_id": self.legal_aid_grant_id,
            "law_firm_client_id": self.law_firm_client_id,
            "law_firm_matter_id": self.law_firm_matter_id,
            "services_australia_crn": self.services_australia_crn,
            "child_support_case_id": self.child_support_case_id,
            "centrelink_crn": self.centrelink_crn,
            "sap_bp_id": self.sap_bp_id,
            "dynamics_contact_id": self.dynamics_contact_id,
            "salesforce_id": self.salesforce_id,
            "child_protection_case_id": self.child_protection_case_id,
            "child_protection_state": self.child_protection_state,
            "external_ids": self.external_ids,
        }


@dataclass
class PersonalDetails:
    """
    Personal details for greeting and identifying the user.

    The receiving bot uses these to:
    1. Greet the user by name
    2. Confirm identity
    3. Personalize the conversation
    """

    # Name
    title: Optional[str] = None  # Mr, Ms, Mrs, Dr, etc.
    given_name: Optional[str] = None
    middle_names: Optional[str] = None
    family_name: Optional[str] = None
    preferred_name: Optional[str] = None  # What they want to be called

    # Demographics (optional, for service matching)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

    # Contact
    email: Optional[str] = None
    phone_mobile: Optional[str] = None
    phone_home: Optional[str] = None
    phone_work: Optional[str] = None
    preferred_contact_method: str = "email"

    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: str = "Australia"

    # Communication preferences
    language: str = "en-AU"
    interpreter_language: Optional[str] = None
    communication_needs: List[str] = field(
        default_factory=list
    )  # ["large_print", "auslan", "easy_read"]

    def get_greeting_name(self) -> str:
        """Get the name to use when greeting."""
        if self.preferred_name:
            return self.preferred_name
        if self.given_name:
            return self.given_name
        if self.title and self.family_name:
            return f"{self.title} {self.family_name}"
        return "there"

    def get_full_name(self) -> str:
        """Get full name for formal use."""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.given_name:
            parts.append(self.given_name)
        if self.middle_names:
            parts.append(self.middle_names)
        if self.family_name:
            parts.append(self.family_name)
        return " ".join(parts) if parts else "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transmission."""
        return {
            "title": self.title,
            "given_name": self.given_name,
            "middle_names": self.middle_names,
            "family_name": self.family_name,
            "preferred_name": self.preferred_name,
            "date_of_birth": (
                self.date_of_birth.isoformat() if self.date_of_birth else None
            ),
            "gender": self.gender,
            "email": self.email,
            "phone_mobile": self.phone_mobile,
            "phone_home": self.phone_home,
            "phone_work": self.phone_work,
            "preferred_contact_method": self.preferred_contact_method,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "suburb": self.suburb,
            "state": self.state,
            "postcode": self.postcode,
            "country": self.country,
            "language": self.language,
            "interpreter_language": self.interpreter_language,
            "communication_needs": self.communication_needs,
        }


@dataclass
class UserContext:
    """Information about the user being handed off."""

    user_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None  # "applicant", "respondent", "lawyer", etc.

    # IDENTITY VERIFICATION - Critical for secure handoffs
    identity: IdentityVerification = field(default_factory=IdentityVerification)

    # PERSONAL DETAILS - For greeting and identification
    personal_details: PersonalDetails = field(default_factory=PersonalDetails)

    # MASTER DATA REFERENCES - Links to records in other systems
    master_data: MasterDataReference = field(default_factory=MasterDataReference)

    # Contact (legacy - use personal_details instead)
    email: Optional[str] = None
    phone: Optional[str] = None

    # Case info
    case_id: Optional[str] = None
    case_type: Optional[str] = None
    court_registry: Optional[str] = None

    # Accessibility
    accessibility_needs: List[str] = field(default_factory=list)
    language: str = "en-AU"
    interpreter_needed: bool = False

    def generate_handoff_greeting(self, target_bot_name: str) -> str:
        """Generate a greeting for the receiving bot to use."""
        name = self.personal_details.get_greeting_name()

        if self.identity.is_verified:
            # Verified user - confident greeting
            return (
                f"Hi {name}, I'm {target_bot_name}. I've been briefed on your "
                f"situation and I'm ready to help you."
            )
        else:
            # Unverified - need to confirm
            return (
                f"Hi {name}, I'm {target_bot_name}. Before we continue, "
                f"I just need to confirm a few details with you."
            )


@dataclass
class ConversationContext:
    """The conversation being handed off."""

    conversation_id: str
    started_at: datetime

    # History
    messages: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None  # LLM-generated summary

    # Current state
    current_intent: Optional[str] = None
    entities_extracted: Dict[str, Any] = field(default_factory=dict)

    # Emotional/safety
    emotional_state: Optional[str] = None  # "calm", "distressed", "angry"
    safety_flags: List[str] = field(default_factory=list)
    urgency: str = "normal"  # "low", "normal", "high", "urgent"


@dataclass
class HandoffPacket:
    """
    Complete context packet for bot-to-bot handoff.

    This is everything the receiving bot needs to continue
    the conversation seamlessly.
    """

    # Identifiers
    handoff_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    # Parties
    source_bot_id: str = ""
    source_bot_name: str = ""
    target_bot_id: str = ""
    target_bot_name: str = ""

    # Handoff details
    handoff_type: HandoffType = HandoffType.WARM
    reason: HandoffReason = HandoffReason.SPECIALIZATION
    reason_detail: str = ""

    # Context
    user: UserContext = field(default_factory=UserContext)
    conversation: ConversationContext = field(
        default_factory=lambda: ConversationContext(
            conversation_id=str(uuid.uuid4()), started_at=datetime.now()
        )
    )

    # What the user needs
    user_need: str = ""
    suggested_response: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transmission."""
        return {
            "handoff_id": self.handoff_id,
            "timestamp": self.timestamp.isoformat(),
            "source_bot": {
                "id": self.source_bot_id,
                "name": self.source_bot_name,
            },
            "target_bot": {
                "id": self.target_bot_id,
                "name": self.target_bot_name,
            },
            "handoff_type": self.handoff_type.value,
            "reason": self.reason.value,
            "reason_detail": self.reason_detail,
            "user_need": self.user_need,
            "conversation_summary": self.conversation.summary,
            "safety_flags": self.conversation.safety_flags,
            "urgency": self.conversation.urgency,
        }


# =============================================================================
# BOT REGISTRY - Track available bots
# =============================================================================


@dataclass
class BotCapability:
    """What a bot can do."""

    capability_id: str
    name: str
    description: str

    # Constraints
    requires_auth: bool = False
    requires_case_id: bool = False
    jurisdictions: List[str] = field(default_factory=list)  # ["NSW", "VIC", ...]


@dataclass
class RegisteredBot:
    """A bot registered in the network."""

    bot_id: str
    name: str
    organization: str
    description: str

    # Endpoint
    endpoint: str  # How to reach this bot
    protocol: str = "http"  # "http", "grpc", "websocket"

    # Capabilities
    capabilities: List[BotCapability] = field(default_factory=list)

    # Availability
    is_available: bool = True
    current_load: float = 0.0  # 0.0 to 1.0
    max_concurrent: int = 100

    # Trust
    trust_level: int = 1  # 1-5
    verified: bool = False

    def can_handle(self, capability_id: str) -> bool:
        """Check if bot has a capability."""
        return any(c.capability_id == capability_id for c in self.capabilities)


class BotRegistry:
    """
    Registry of all available bots in the network.

    Bots register themselves and can discover other bots
    for handoffs.
    """

    def __init__(self):
        self._bots: Dict[str, RegisteredBot] = {}
        self._capability_index: Dict[str, List[str]] = {}  # capability -> bot_ids

    def register(self, bot: RegisteredBot) -> None:
        """Register a bot in the network."""
        self._bots[bot.bot_id] = bot

        # Index by capability
        for cap in bot.capabilities:
            if cap.capability_id not in self._capability_index:
                self._capability_index[cap.capability_id] = []
            self._capability_index[cap.capability_id].append(bot.bot_id)

        logger.info(f"Bot registered: {bot.name} ({bot.bot_id})")

    def unregister(self, bot_id: str) -> None:
        """Remove a bot from the registry."""
        if bot_id in self._bots:
            bot = self._bots[bot_id]
            for cap in bot.capabilities:
                if cap.capability_id in self._capability_index:
                    self._capability_index[cap.capability_id].remove(bot_id)
            del self._bots[bot_id]
            logger.info(f"Bot unregistered: {bot_id}")

    def find_by_capability(
        self,
        capability_id: str,
        jurisdiction: Optional[str] = None,
    ) -> List[RegisteredBot]:
        """Find bots that can handle a capability."""
        bot_ids = self._capability_index.get(capability_id, [])
        bots = [self._bots[bid] for bid in bot_ids if bid in self._bots]

        # Filter by availability
        bots = [b for b in bots if b.is_available]

        # Filter by jurisdiction if specified
        if jurisdiction:
            bots = [
                b
                for b in bots
                if any(
                    jurisdiction in c.jurisdictions or not c.jurisdictions
                    for c in b.capabilities
                    if c.capability_id == capability_id
                )
            ]

        # Sort by load (prefer less loaded bots)
        bots.sort(key=lambda b: b.current_load)

        return bots

    def get_bot(self, bot_id: str) -> Optional[RegisteredBot]:
        """Get a specific bot by ID."""
        return self._bots.get(bot_id)

    def list_all(self) -> List[RegisteredBot]:
        """List all registered bots."""
        return list(self._bots.values())


# =============================================================================
# HANDOFF PROTOCOL
# =============================================================================


class HandoffProtocol(Protocol):
    """Protocol that bots must implement to support handoffs."""

    async def accept_handoff(self, packet: HandoffPacket) -> bool:
        """Accept an incoming handoff."""
        ...

    async def reject_handoff(self, packet: HandoffPacket, reason: str) -> None:
        """Reject an incoming handoff."""
        ...

    async def complete_handoff(self, handoff_id: str) -> None:
        """Signal handoff is complete."""
        ...


class HandoffManager:
    """
    Manages bot-to-bot handoffs.

    Example:
        manager = HandoffManager(registry)

        # Find a bot that can help with eFiling
        target = manager.find_handler("efiling", jurisdiction="NSW")

        # Initiate handoff
        packet = HandoffPacket(
            source_bot_id="legal-finder-bot",
            target_bot_id=target.bot_id,
            user_need="User wants to file an affidavit",
            ...
        )

        result = await manager.initiate_handoff(packet)
    """

    def __init__(self, registry: BotRegistry):
        self.registry = registry
        self._active_handoffs: Dict[str, HandoffPacket] = {}
        self._handoff_callbacks: Dict[str, Callable] = {}

    async def initiate_handoff(
        self,
        packet: HandoffPacket,
        timeout: float = 30.0,
    ) -> HandoffStatus:
        """
        Initiate a handoff to another bot.

        Returns status of the handoff attempt.
        """
        logger.info(
            f"Initiating handoff: {packet.source_bot_name} -> {packet.target_bot_name}"
        )

        # Store active handoff
        self._active_handoffs[packet.handoff_id] = packet

        # Get target bot
        target = self.registry.get_bot(packet.target_bot_id)
        if not target:
            logger.error(f"Target bot not found: {packet.target_bot_id}")
            return HandoffStatus.FAILED

        if not target.is_available:
            logger.warning(f"Target bot not available: {packet.target_bot_id}")
            return HandoffStatus.REJECTED

        # In production, this would make actual API call to target bot
        # For now, simulate the handoff
        try:
            # Simulate network call
            await asyncio.sleep(0.1)

            # Log the handoff
            logger.info(f"Handoff {packet.handoff_id} accepted by {target.name}")

            return HandoffStatus.ACCEPTED

        except asyncio.TimeoutError:
            logger.error(f"Handoff timeout: {packet.handoff_id}")
            return HandoffStatus.TIMEOUT
        except Exception as e:
            logger.error(f"Handoff failed: {e}")
            return HandoffStatus.FAILED

    def find_handler(
        self,
        capability: str,
        jurisdiction: Optional[str] = None,
        exclude_bot: Optional[str] = None,
    ) -> Optional[RegisteredBot]:
        """Find the best bot to handle a capability."""
        bots = self.registry.find_by_capability(capability, jurisdiction)

        if exclude_bot:
            bots = [b for b in bots if b.bot_id != exclude_bot]

        if bots:
            return bots[0]  # Return least loaded available bot
        return None

    async def warm_handoff(
        self,
        packet: HandoffPacket,
        introduction_message: str,
    ) -> HandoffStatus:
        """
        Perform a warm handoff with introduction.

        The source bot introduces the user to the target bot
        before disconnecting.
        """
        packet.handoff_type = HandoffType.WARM

        # Send introduction
        logger.info(f"Warm handoff introduction: {introduction_message}")

        # Brief overlap period
        status = await self.initiate_handoff(packet)

        if status == HandoffStatus.ACCEPTED:
            # Source bot can now disconnect
            logger.info(f"Warm handoff complete: {packet.handoff_id}")

        return status

    async def escalate_to_human(
        self,
        packet: HandoffPacket,
        urgency: str = "normal",
    ) -> HandoffStatus:
        """
        Escalate conversation to a human agent.
        """
        packet.handoff_type = HandoffType.ESCALATION
        packet.reason = HandoffReason.ESCALATION
        packet.conversation.urgency = urgency

        # Find human agent queue (special bot type)
        human_handler = self.find_handler("human_agent")

        if human_handler:
            packet.target_bot_id = human_handler.bot_id
            packet.target_bot_name = human_handler.name
            return await self.initiate_handoff(packet)

        logger.error("No human agents available for escalation")
        return HandoffStatus.FAILED

    def get_handoff_status(self, handoff_id: str) -> Optional[HandoffPacket]:
        """Get status of an active handoff."""
        return self._active_handoffs.get(handoff_id)


# =============================================================================
# FAMILY LAW SPECIFIC BOTS
# =============================================================================

# Pre-configured bots for family law ecosystem

LEGAL_FINDER_BOT = RegisteredBot(
    bot_id="legal-finder-au",
    name="Legal Services Finder",
    organization="Agentic Brain",
    description="Helps users find appropriate legal services in Australia",
    endpoint="https://bot.agentic-brain.ai/legal-finder",
    capabilities=[
        BotCapability(
            capability_id="find_legal_services",
            name="Find Legal Services",
            description="Locate lawyers, Legal Aid, CLCs based on location and need",
            jurisdictions=["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"],
        ),
        BotCapability(
            capability_id="find_court",
            name="Find Court Location",
            description="Find nearest court registry",
            jurisdictions=["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"],
        ),
        BotCapability(
            capability_id="find_fdr",
            name="Find FDR Provider",
            description="Find family dispute resolution services",
            jurisdictions=["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"],
        ),
    ],
    is_available=True,
    verified=True,
    trust_level=5,
)

LEGAL_AID_NSW_BOT = RegisteredBot(
    bot_id="legal-aid-nsw",
    name="Legal Aid NSW Assistant",
    organization="Legal Aid NSW",
    description="Provides legal information and assistance for NSW residents",
    endpoint="https://bot.legalaid.nsw.gov.au",
    capabilities=[
        BotCapability(
            capability_id="legal_advice",
            name="Legal Information",
            description="General legal information (not advice)",
            requires_auth=False,
            jurisdictions=["NSW"],
        ),
        BotCapability(
            capability_id="grant_eligibility",
            name="Grant Eligibility Check",
            description="Check if eligible for Legal Aid grant",
            requires_auth=False,
            jurisdictions=["NSW"],
        ),
        BotCapability(
            capability_id="duty_lawyer",
            name="Duty Lawyer Information",
            description="Information about duty lawyer services",
            jurisdictions=["NSW"],
        ),
    ],
    is_available=True,
    verified=True,
    trust_level=5,
)

COURT_FILING_BOT = RegisteredBot(
    bot_id="fcfcoa-efiling",
    name="Court eFiling Assistant",
    organization="Federal Circuit and Family Court",
    description="Assists with electronic filing of court documents",
    endpoint="https://efiling.fcfcoa.gov.au/bot",
    capabilities=[
        BotCapability(
            capability_id="efiling",
            name="Electronic Filing",
            description="File documents with the court",
            requires_auth=True,
            requires_case_id=True,
            jurisdictions=["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"],
        ),
        BotCapability(
            capability_id="document_tender",
            name="Tender Documents",
            description="Tender documents during hearing",
            requires_auth=True,
            requires_case_id=True,
        ),
        BotCapability(
            capability_id="filing_status",
            name="Filing Status",
            description="Check status of filed documents",
            requires_auth=True,
        ),
    ],
    is_available=True,
    verified=True,
    trust_level=5,
)

DV_SUPPORT_BOT = RegisteredBot(
    bot_id="dv-support-au",
    name="DV Support Navigator",
    organization="1800RESPECT",
    description="Connects users with domestic violence support services",
    endpoint="https://bot.1800respect.org.au",
    capabilities=[
        BotCapability(
            capability_id="dv_support",
            name="DV Support",
            description="Connect with DV support services",
            jurisdictions=["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"],
        ),
        BotCapability(
            capability_id="safety_planning",
            name="Safety Planning",
            description="Help create a safety plan",
        ),
        BotCapability(
            capability_id="crisis_support",
            name="Crisis Support",
            description="Immediate crisis support",
        ),
    ],
    is_available=True,
    verified=True,
    trust_level=5,
)

LAW_FIRM_BOT = RegisteredBot(
    bot_id="familylaw-com-au",
    name="FamilyLaw.com.au Assistant",
    organization="FamilyLaw.com.au",
    description="Family law firm client assistant",
    endpoint="https://bot.familylaw.com.au",
    capabilities=[
        BotCapability(
            capability_id="client_intake",
            name="Client Intake",
            description="New client registration and intake",
        ),
        BotCapability(
            capability_id="case_status",
            name="Case Status",
            description="Check status of existing matter",
            requires_auth=True,
            requires_case_id=True,
        ),
        BotCapability(
            capability_id="appointment_booking",
            name="Book Appointment",
            description="Schedule consultation or meeting",
        ),
    ],
    is_available=True,
    verified=True,
    trust_level=4,
)


def create_family_law_bot_network() -> BotRegistry:
    """
    Create the family law bot network with all standard bots.
    """
    registry = BotRegistry()

    registry.register(LEGAL_FINDER_BOT)
    registry.register(LEGAL_AID_NSW_BOT)
    registry.register(COURT_FILING_BOT)
    registry.register(DV_SUPPORT_BOT)
    registry.register(LAW_FIRM_BOT)

    logger.info(f"Family law bot network created with {len(registry.list_all())} bots")

    return registry


# =============================================================================
# EXAMPLE: HANDOFF SCENARIO
# =============================================================================


async def demo_handoff_scenario():
    """
    Demonstrate a realistic handoff scenario.

    User journey:
    1. Starts with Legal Finder bot
    2. Bot identifies need for Legal Aid
    3. Hands off to Legal Aid NSW bot
    4. Legal Aid helps, then hands to Court Filing bot
    """
    print("=== Bot Handoff Demo ===\n")

    # Create network
    registry = create_family_law_bot_network()
    manager = HandoffManager(registry)

    # Scenario: User needs help filing documents
    print("User: 'I need to file my response to the family court'")
    print()

    # Step 1: Legal Finder identifies need
    print("1. Legal Finder Bot analyzing request...")

    # Create context
    user = UserContext(
        name="Sarah",
        role="respondent",
        case_id="FAM-2024-001234",
        case_type="parenting",
        court_registry="SYD",
    )

    conversation = ConversationContext(
        conversation_id="conv-001",
        started_at=datetime.now(),
        messages=[
            {
                "role": "user",
                "content": "I need to file my response to the family court",
            },
        ],
        summary="User is a respondent needing to file a response to parenting proceedings",
        current_intent="document_filing",
        entities_extracted={
            "document_type": "response",
            "case_type": "parenting",
        },
    )

    # Step 2: Find appropriate bot for eFiling
    print("2. Finding eFiling handler...")
    target = manager.find_handler("efiling", jurisdiction="NSW")

    if target:
        print(f"   Found: {target.name}")

        # Step 3: Create handoff packet
        packet = HandoffPacket(
            source_bot_id=LEGAL_FINDER_BOT.bot_id,
            source_bot_name=LEGAL_FINDER_BOT.name,
            target_bot_id=target.bot_id,
            target_bot_name=target.name,
            handoff_type=HandoffType.WARM,
            reason=HandoffReason.SPECIALIZATION,
            reason_detail="User needs eFiling assistance which Court Filing bot specializes in",
            user=user,
            conversation=conversation,
            user_need="File response to parenting proceedings in case FAM-2024-001234",
        )

        # Step 4: Perform warm handoff
        print("3. Performing warm handoff...")

        introduction = (
            "Sarah, I'm connecting you with the Court Filing Assistant "
            "who can help you file your response. They have all the "
            "details about your case."
        )

        status = await manager.warm_handoff(packet, introduction)

        print(f"   Handoff status: {status.value}")

        if status == HandoffStatus.ACCEPTED:
            print()
            print("4. Court Filing Bot now handling conversation:")
            print("   'Hello Sarah! I can see you need to file a response for")
            print("    case FAM-2024-001234 in the Sydney registry.")
            print("    Let me help you with that...'")

    print()
    print("=== Handoff Complete ===")


if __name__ == "__main__":
    asyncio.run(demo_handoff_scenario())
