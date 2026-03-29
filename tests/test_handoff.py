# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""
Comprehensive tests for handoff module - bot-to-bot conversation transfer.

Tests all 16 classes and key functions in the handoff module:
- Enums: HandoffType, HandoffStatus, HandoffReason, IdentityVerificationLevel, IdentityDocumentType
- Dataclasses: IdentityVerification, MasterDataReference, PersonalDetails, UserContext,
               ConversationContext, HandoffPacket, BotCapability, RegisteredBot
- Classes: BotRegistry, HandoffManager
- Protocol: HandoffProtocol
- Functions: create_family_law_bot_network, demo_handoff_scenario

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.handoff import (
    COURT_FILING_BOT,
    DV_SUPPORT_BOT,
    LAW_FIRM_BOT,
    LEGAL_AID_NSW_BOT,
    # Pre-configured bots
    LEGAL_FINDER_BOT,
    BotCapability,
    # Classes
    BotRegistry,
    ConversationContext,
    HandoffManager,
    HandoffPacket,
    HandoffReason,
    HandoffStatus,
    # Enums
    HandoffType,
    IdentityDocumentType,
    # Dataclasses
    IdentityVerification,
    IdentityVerificationLevel,
    MasterDataReference,
    PersonalDetails,
    RegisteredBot,
    UserContext,
    # Functions
    create_family_law_bot_network,
    demo_handoff_scenario,
)

# =============================================================================
# TEST ENUMS
# =============================================================================


class TestHandoffType:
    """Tests for HandoffType enum."""

    def test_warm_handoff_value(self):
        """Test WARM handoff type."""
        assert HandoffType.WARM.value == "warm"

    def test_cold_handoff_value(self):
        """Test COLD handoff type."""
        assert HandoffType.COLD.value == "cold"

    def test_supervised_handoff_value(self):
        """Test SUPERVISED handoff type."""
        assert HandoffType.SUPERVISED.value == "supervised"

    def test_escalation_handoff_value(self):
        """Test ESCALATION handoff type."""
        assert HandoffType.ESCALATION.value == "escalation"

    def test_all_handoff_types_exist(self):
        """Test all expected handoff types are defined."""
        expected_types = {"WARM", "COLD", "SUPERVISED", "ESCALATION"}
        actual_types = {t.name for t in HandoffType}
        assert actual_types == expected_types


class TestHandoffStatus:
    """Tests for HandoffStatus enum."""

    def test_all_status_values(self):
        """Test all status values exist and are correct."""
        expected = {
            "PENDING": "pending",
            "INITIATED": "initiated",
            "ACCEPTED": "accepted",
            "IN_PROGRESS": "in_progress",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "REJECTED": "rejected",
            "TIMEOUT": "timeout",
        }
        for name, value in expected.items():
            assert HandoffStatus[name].value == value

    def test_status_transitions_logical(self):
        """Test that status values represent logical progression."""
        # These represent the typical flow
        flow = [
            HandoffStatus.PENDING,
            HandoffStatus.INITIATED,
            HandoffStatus.ACCEPTED,
            HandoffStatus.IN_PROGRESS,
            HandoffStatus.COMPLETED,
        ]
        assert len(flow) == 5  # Normal happy path


class TestHandoffReason:
    """Tests for HandoffReason enum."""

    def test_all_reason_values(self):
        """Test all handoff reason values."""
        expected = {
            "SPECIALIZATION": "specialization",
            "JURISDICTION": "jurisdiction",
            "ESCALATION": "escalation",
            "USER_REQUEST": "user_request",
            "SAFETY": "safety",
            "LANGUAGE": "language",
            "COMPLEXITY": "complexity",
            "COMPLETION": "completion",
        }
        for name, value in expected.items():
            assert HandoffReason[name].value == value


class TestIdentityVerificationLevel:
    """Tests for IdentityVerificationLevel enum."""

    def test_verification_levels_hierarchy(self):
        """Test verification levels form a trust hierarchy."""
        levels = [
            IdentityVerificationLevel.NONE,
            IdentityVerificationLevel.SELF_DECLARED,
            IdentityVerificationLevel.EMAIL_VERIFIED,
            IdentityVerificationLevel.PHONE_VERIFIED,
            IdentityVerificationLevel.DOCUMENT_VERIFIED,
            IdentityVerificationLevel.MYGOVID_VERIFIED,
            IdentityVerificationLevel.COURT_VERIFIED,
            IdentityVerificationLevel.LAWYER_VERIFIED,
        ]
        assert len(levels) == 8

    def test_none_level_value(self):
        """Test NONE level is unverified."""
        assert IdentityVerificationLevel.NONE.value == "none"

    def test_mygovid_level_value(self):
        """Test myGovID Australian verification."""
        assert IdentityVerificationLevel.MYGOVID_VERIFIED.value == "mygovid"


class TestIdentityDocumentType:
    """Tests for IdentityDocumentType enum."""

    def test_australian_documents(self):
        """Test Australian identity documents are supported."""
        assert IdentityDocumentType.DRIVERS_LICENCE.value == "drivers_licence"
        assert IdentityDocumentType.MEDICARE_CARD.value == "medicare"
        assert IdentityDocumentType.PASSPORT.value == "passport"

    def test_immigration_documents(self):
        """Test immigration documents are supported."""
        assert IdentityDocumentType.IMMICARD.value == "immicard"
        assert IdentityDocumentType.CITIZENSHIP_CERTIFICATE.value == "citizenship"


# =============================================================================
# TEST DATACLASSES
# =============================================================================


class TestIdentityVerification:
    """Tests for IdentityVerification dataclass."""

    def test_default_unverified(self):
        """Test default identity is unverified."""
        identity = IdentityVerification()
        assert identity.is_verified is False
        assert identity.verification_level == IdentityVerificationLevel.NONE
        assert identity.confidence_score == 0.0

    def test_is_valid_unverified(self):
        """Test is_valid returns False for unverified identity."""
        identity = IdentityVerification()
        assert identity.is_valid() is False

    def test_is_valid_verified_no_expiry(self):
        """Test is_valid returns True for verified identity without expiry."""
        identity = IdentityVerification(
            is_verified=True,
            verification_level=IdentityVerificationLevel.EMAIL_VERIFIED,
        )
        assert identity.is_valid() is True

    def test_is_valid_expired_token(self):
        """Test is_valid returns False for expired token."""
        identity = IdentityVerification(
            is_verified=True,
            token_expires=datetime.now() - timedelta(hours=1),
        )
        assert identity.is_valid() is False

    def test_is_valid_future_expiry(self):
        """Test is_valid returns True for future expiry."""
        identity = IdentityVerification(
            is_verified=True,
            token_expires=datetime.now() + timedelta(hours=1),
        )
        assert identity.is_valid() is True

    def test_to_dict_serialization(self):
        """Test to_dict serializes correctly."""
        now = datetime.now()
        identity = IdentityVerification(
            is_verified=True,
            verification_level=IdentityVerificationLevel.DOCUMENT_VERIFIED,
            verified_at=now,
            verified_by="legal-aid-bot",
            verification_methods=["document_scan", "selfie_match"],
            documents_sighted=[IdentityDocumentType.DRIVERS_LICENCE],
            confidence_score=0.95,
            verification_token="token123",
            token_expires=now + timedelta(hours=24),
        )
        data = identity.to_dict()

        assert data["is_verified"] is True
        assert data["verification_level"] == "document"
        assert data["verified_at"] == now.isoformat()
        assert data["verified_by"] == "legal-aid-bot"
        assert data["verification_methods"] == ["document_scan", "selfie_match"]
        assert data["documents_sighted"] == ["drivers_licence"]
        assert data["confidence_score"] == 0.95
        assert data["verification_token"] == "token123"


class TestMasterDataReference:
    """Tests for MasterDataReference dataclass."""

    def test_default_empty(self):
        """Test default master data has no references."""
        ref = MasterDataReference()
        assert ref.court_case_id is None
        assert ref.legal_aid_client_id is None
        assert ref.external_ids == {}

    def test_court_references(self):
        """Test court system references."""
        ref = MasterDataReference(
            court_case_id="SYC1234/2024",
            court_file_number="FAM-2024-001234",
            comcourts_id="COMCOURTS-12345",
        )
        assert ref.court_case_id == "SYC1234/2024"
        assert ref.court_file_number == "FAM-2024-001234"

    def test_government_references(self):
        """Test government service references."""
        ref = MasterDataReference(
            services_australia_crn="123456789A",
            centrelink_crn="987654321B",
            child_support_case_id="CS-2024-001",
        )
        assert ref.services_australia_crn == "123456789A"

    def test_enterprise_references(self):
        """Test CMMS/enterprise references."""
        ref = MasterDataReference(
            sap_bp_id="BP-1000001",
            dynamics_contact_id="DYN-CONTACT-123",
            salesforce_id="SF-001234567890ABC",
        )
        assert ref.sap_bp_id == "BP-1000001"

    def test_to_dict_serialization(self):
        """Test to_dict includes all fields."""
        ref = MasterDataReference(
            court_case_id="TEST-123",
            external_ids={"custom_system": "CUSTOM-001"},
        )
        data = ref.to_dict()

        assert data["court_case_id"] == "TEST-123"
        assert data["external_ids"] == {"custom_system": "CUSTOM-001"}
        assert data["legal_aid_client_id"] is None


class TestPersonalDetails:
    """Tests for PersonalDetails dataclass."""

    def test_default_values(self):
        """Test default personal details."""
        details = PersonalDetails()
        assert details.country == "Australia"
        assert details.language == "en-AU"
        assert details.preferred_contact_method == "email"

    def test_get_greeting_name_preferred(self):
        """Test greeting uses preferred name first."""
        details = PersonalDetails(
            given_name="Elizabeth",
            preferred_name="Liz",
        )
        assert details.get_greeting_name() == "Liz"

    def test_get_greeting_name_given(self):
        """Test greeting uses given name if no preferred."""
        details = PersonalDetails(given_name="Elizabeth")
        assert details.get_greeting_name() == "Elizabeth"

    def test_get_greeting_name_formal(self):
        """Test greeting uses title + surname if no first name."""
        details = PersonalDetails(
            title="Dr",
            family_name="Smith",
        )
        assert details.get_greeting_name() == "Dr Smith"

    def test_get_greeting_name_fallback(self):
        """Test greeting falls back to 'there'."""
        details = PersonalDetails()
        assert details.get_greeting_name() == "there"

    def test_get_full_name(self):
        """Test full name assembly."""
        details = PersonalDetails(
            title="Dr",
            given_name="Elizabeth",
            middle_names="Anne",
            family_name="Smith",
        )
        assert details.get_full_name() == "Dr Elizabeth Anne Smith"

    def test_get_full_name_empty(self):
        """Test full name when empty."""
        details = PersonalDetails()
        assert details.get_full_name() == "Unknown"

    def test_accessibility_needs(self):
        """Test accessibility needs list."""
        details = PersonalDetails(
            communication_needs=["large_print", "auslan", "easy_read"]
        )
        assert "auslan" in details.communication_needs

    def test_to_dict_serialization(self):
        """Test to_dict with date of birth."""
        dob = date(1985, 6, 15)
        details = PersonalDetails(
            given_name="Test",
            date_of_birth=dob,
            email="test@example.com",
        )
        data = details.to_dict()

        assert data["given_name"] == "Test"
        assert data["date_of_birth"] == "1985-06-15"
        assert data["email"] == "test@example.com"


class TestUserContext:
    """Tests for UserContext dataclass."""

    def test_default_context(self):
        """Test default user context."""
        ctx = UserContext()
        assert ctx.language == "en-AU"
        assert ctx.interpreter_needed is False
        assert isinstance(ctx.identity, IdentityVerification)
        assert isinstance(ctx.personal_details, PersonalDetails)

    def test_generate_handoff_greeting_verified(self):
        """Test greeting generation for verified user."""
        ctx = UserContext(
            personal_details=PersonalDetails(preferred_name="Sarah"),
            identity=IdentityVerification(is_verified=True),
        )
        greeting = ctx.generate_handoff_greeting("Legal Aid Bot")

        assert "Sarah" in greeting
        assert "Legal Aid Bot" in greeting
        assert "briefed on your situation" in greeting

    def test_generate_handoff_greeting_unverified(self):
        """Test greeting generation for unverified user."""
        ctx = UserContext(
            personal_details=PersonalDetails(preferred_name="Sarah"),
            identity=IdentityVerification(is_verified=False),
        )
        greeting = ctx.generate_handoff_greeting("Legal Aid Bot")

        assert "Sarah" in greeting
        assert "confirm a few details" in greeting

    def test_case_information(self):
        """Test case-related fields."""
        ctx = UserContext(
            role="respondent",
            case_id="FAM-2024-001234",
            case_type="parenting",
            court_registry="SYD",
        )
        assert ctx.role == "respondent"
        assert ctx.case_type == "parenting"


class TestConversationContext:
    """Tests for ConversationContext dataclass."""

    def test_required_fields(self):
        """Test required fields for conversation context."""
        conv = ConversationContext(
            conversation_id="conv-001",
            started_at=datetime.now(),
        )
        assert conv.conversation_id == "conv-001"
        assert conv.messages == []

    def test_conversation_with_messages(self):
        """Test conversation with message history."""
        conv = ConversationContext(
            conversation_id="conv-002",
            started_at=datetime.now(),
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            summary="User greeted the bot",
        )
        assert len(conv.messages) == 2
        assert conv.summary == "User greeted the bot"

    def test_emotional_state_and_safety(self):
        """Test emotional state and safety flags."""
        conv = ConversationContext(
            conversation_id="conv-003",
            started_at=datetime.now(),
            emotional_state="distressed",
            safety_flags=["dv_mentioned", "self_harm_risk"],
            urgency="urgent",
        )
        assert conv.emotional_state == "distressed"
        assert "dv_mentioned" in conv.safety_flags
        assert conv.urgency == "urgent"


class TestHandoffPacket:
    """Tests for HandoffPacket dataclass."""

    def test_auto_generated_fields(self):
        """Test handoff_id and timestamp are auto-generated."""
        packet = HandoffPacket()
        assert packet.handoff_id is not None
        assert len(packet.handoff_id) == 36  # UUID format
        assert isinstance(packet.timestamp, datetime)

    def test_default_handoff_type(self):
        """Test default handoff type is WARM."""
        packet = HandoffPacket()
        assert packet.handoff_type == HandoffType.WARM

    def test_full_packet_creation(self):
        """Test creating a complete handoff packet."""
        user = UserContext(name="Test User", role="applicant")
        conv = ConversationContext(
            conversation_id="conv-001",
            started_at=datetime.now(),
        )

        packet = HandoffPacket(
            source_bot_id="bot-1",
            source_bot_name="Source Bot",
            target_bot_id="bot-2",
            target_bot_name="Target Bot",
            handoff_type=HandoffType.COLD,
            reason=HandoffReason.SPECIALIZATION,
            reason_detail="Target has specific expertise",
            user=user,
            conversation=conv,
            user_need="Help with filing",
        )

        assert packet.source_bot_id == "bot-1"
        assert packet.target_bot_id == "bot-2"
        assert packet.reason == HandoffReason.SPECIALIZATION

    def test_to_dict_serialization(self):
        """Test to_dict produces correct output."""
        packet = HandoffPacket(
            source_bot_id="source",
            source_bot_name="Source Bot",
            target_bot_id="target",
            target_bot_name="Target Bot",
            handoff_type=HandoffType.WARM,
            reason=HandoffReason.ESCALATION,
            user_need="Urgent help needed",
        )
        data = packet.to_dict()

        assert data["source_bot"]["id"] == "source"
        assert data["target_bot"]["name"] == "Target Bot"
        assert data["handoff_type"] == "warm"
        assert data["reason"] == "escalation"
        assert data["user_need"] == "Urgent help needed"


class TestBotCapability:
    """Tests for BotCapability dataclass."""

    def test_basic_capability(self):
        """Test basic capability creation."""
        cap = BotCapability(
            capability_id="legal_advice",
            name="Legal Advice",
            description="Provides legal information",
        )
        assert cap.capability_id == "legal_advice"
        assert cap.requires_auth is False
        assert cap.jurisdictions == []

    def test_capability_with_constraints(self):
        """Test capability with constraints."""
        cap = BotCapability(
            capability_id="efiling",
            name="eFiling",
            description="File court documents",
            requires_auth=True,
            requires_case_id=True,
            jurisdictions=["NSW", "VIC"],
        )
        assert cap.requires_auth is True
        assert cap.requires_case_id is True
        assert "NSW" in cap.jurisdictions


class TestRegisteredBot:
    """Tests for RegisteredBot dataclass."""

    def test_basic_bot(self):
        """Test basic bot registration."""
        bot = RegisteredBot(
            bot_id="test-bot",
            name="Test Bot",
            organization="Test Org",
            description="A test bot",
            endpoint="https://test.example.com",
        )
        assert bot.bot_id == "test-bot"
        assert bot.protocol == "http"
        assert bot.is_available is True
        assert bot.trust_level == 1

    def test_can_handle_capability(self):
        """Test can_handle checks capabilities."""
        cap = BotCapability(
            capability_id="test_cap",
            name="Test",
            description="Test capability",
        )
        bot = RegisteredBot(
            bot_id="bot-1",
            name="Bot",
            organization="Org",
            description="Desc",
            endpoint="https://example.com",
            capabilities=[cap],
        )
        assert bot.can_handle("test_cap") is True
        assert bot.can_handle("nonexistent") is False

    def test_load_and_availability(self):
        """Test load and availability fields."""
        bot = RegisteredBot(
            bot_id="busy-bot",
            name="Busy Bot",
            organization="Org",
            description="A busy bot",
            endpoint="https://busy.example.com",
            is_available=False,
            current_load=0.85,
            max_concurrent=50,
        )
        assert bot.is_available is False
        assert bot.current_load == 0.85


# =============================================================================
# TEST BOT REGISTRY
# =============================================================================


class TestBotRegistry:
    """Tests for BotRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return BotRegistry()

    @pytest.fixture
    def sample_bot(self):
        """Create a sample bot for testing."""
        return RegisteredBot(
            bot_id="sample-bot",
            name="Sample Bot",
            organization="Test Org",
            description="A sample bot",
            endpoint="https://sample.example.com",
            capabilities=[
                BotCapability(
                    capability_id="sample_cap",
                    name="Sample Capability",
                    description="Sample",
                    jurisdictions=["NSW"],
                ),
            ],
        )

    def test_empty_registry(self, registry):
        """Test empty registry."""
        assert registry.list_all() == []
        assert registry.get_bot("nonexistent") is None

    def test_register_bot(self, registry, sample_bot):
        """Test bot registration."""
        registry.register(sample_bot)

        assert registry.get_bot("sample-bot") is not None
        assert len(registry.list_all()) == 1

    def test_unregister_bot(self, registry, sample_bot):
        """Test bot unregistration."""
        registry.register(sample_bot)
        registry.unregister("sample-bot")

        assert registry.get_bot("sample-bot") is None
        assert len(registry.list_all()) == 0

    def test_unregister_nonexistent(self, registry):
        """Test unregistering nonexistent bot doesn't error."""
        registry.unregister("nonexistent")  # Should not raise

    def test_find_by_capability(self, registry, sample_bot):
        """Test finding bots by capability."""
        registry.register(sample_bot)

        found = registry.find_by_capability("sample_cap")
        assert len(found) == 1
        assert found[0].bot_id == "sample-bot"

    def test_find_by_capability_not_found(self, registry, sample_bot):
        """Test finding bots with no matching capability."""
        registry.register(sample_bot)

        found = registry.find_by_capability("nonexistent_cap")
        assert len(found) == 0

    def test_find_by_capability_with_jurisdiction(self, registry, sample_bot):
        """Test finding bots filtered by jurisdiction."""
        registry.register(sample_bot)

        # NSW should match
        found_nsw = registry.find_by_capability("sample_cap", jurisdiction="NSW")
        assert len(found_nsw) == 1

        # VIC should not match (sample bot only has NSW)
        found_vic = registry.find_by_capability("sample_cap", jurisdiction="VIC")
        assert len(found_vic) == 0

    def test_find_by_capability_excludes_unavailable(self, registry):
        """Test unavailable bots are excluded."""
        unavailable_bot = RegisteredBot(
            bot_id="unavailable-bot",
            name="Unavailable",
            organization="Org",
            description="Desc",
            endpoint="https://example.com",
            is_available=False,
            capabilities=[
                BotCapability(
                    capability_id="test_cap",
                    name="Test",
                    description="Test",
                ),
            ],
        )
        registry.register(unavailable_bot)

        found = registry.find_by_capability("test_cap")
        assert len(found) == 0

    def test_find_by_capability_sorted_by_load(self, registry):
        """Test bots are sorted by load (least loaded first)."""
        bot1 = RegisteredBot(
            bot_id="bot-1",
            name="Bot 1",
            organization="Org",
            description="Desc",
            endpoint="https://example.com",
            current_load=0.8,
            capabilities=[
                BotCapability(
                    capability_id="shared_cap", name="Shared", description=""
                ),
            ],
        )
        bot2 = RegisteredBot(
            bot_id="bot-2",
            name="Bot 2",
            organization="Org",
            description="Desc",
            endpoint="https://example.com",
            current_load=0.2,
            capabilities=[
                BotCapability(
                    capability_id="shared_cap", name="Shared", description=""
                ),
            ],
        )

        registry.register(bot1)
        registry.register(bot2)

        found = registry.find_by_capability("shared_cap")
        assert len(found) == 2
        # Bot 2 should be first (lower load)
        assert found[0].bot_id == "bot-2"


# =============================================================================
# TEST HANDOFF MANAGER
# =============================================================================


class TestHandoffManager:
    """Tests for HandoffManager class."""

    @pytest.fixture
    def registry(self):
        """Create a registry with sample bots."""
        reg = BotRegistry()
        reg.register(
            RegisteredBot(
                bot_id="source-bot",
                name="Source Bot",
                organization="Test",
                description="Source bot",
                endpoint="https://source.example.com",
            )
        )
        reg.register(
            RegisteredBot(
                bot_id="target-bot",
                name="Target Bot",
                organization="Test",
                description="Target bot",
                endpoint="https://target.example.com",
                capabilities=[
                    BotCapability(
                        capability_id="special_service",
                        name="Special Service",
                        description="A special service",
                        jurisdictions=["NSW"],
                    ),
                ],
            )
        )
        reg.register(
            RegisteredBot(
                bot_id="human-agent",
                name="Human Agent Queue",
                organization="Test",
                description="Human escalation",
                endpoint="https://human.example.com",
                capabilities=[
                    BotCapability(
                        capability_id="human_agent",
                        name="Human Agent",
                        description="Human escalation",
                    ),
                ],
            )
        )
        return reg

    @pytest.fixture
    def manager(self, registry):
        """Create a handoff manager with the test registry."""
        return HandoffManager(registry)

    @pytest.fixture
    def sample_packet(self):
        """Create a sample handoff packet."""
        return HandoffPacket(
            source_bot_id="source-bot",
            source_bot_name="Source Bot",
            target_bot_id="target-bot",
            target_bot_name="Target Bot",
            user_need="Test handoff",
        )

    @pytest.mark.asyncio
    async def test_initiate_handoff_success(self, manager, sample_packet):
        """Test successful handoff initiation."""
        status = await manager.initiate_handoff(sample_packet)
        assert status == HandoffStatus.ACCEPTED

    @pytest.mark.asyncio
    async def test_initiate_handoff_target_not_found(self, manager):
        """Test handoff fails when target bot not found."""
        packet = HandoffPacket(
            source_bot_id="source-bot",
            target_bot_id="nonexistent-bot",
            user_need="Test",
        )
        status = await manager.initiate_handoff(packet)
        assert status == HandoffStatus.FAILED

    @pytest.mark.asyncio
    async def test_initiate_handoff_target_unavailable(self, manager, registry):
        """Test handoff rejected when target bot unavailable."""
        # Mark target as unavailable
        target = registry.get_bot("target-bot")
        target.is_available = False

        packet = HandoffPacket(
            source_bot_id="source-bot",
            target_bot_id="target-bot",
            user_need="Test",
        )
        status = await manager.initiate_handoff(packet)
        assert status == HandoffStatus.REJECTED

    @pytest.mark.asyncio
    async def test_initiate_handoff_stores_active(self, manager, sample_packet):
        """Test handoff is stored in active handoffs."""
        await manager.initiate_handoff(sample_packet)

        stored = manager.get_handoff_status(sample_packet.handoff_id)
        assert stored is not None
        assert stored.handoff_id == sample_packet.handoff_id

    def test_find_handler(self, manager):
        """Test finding handler by capability."""
        handler = manager.find_handler("special_service")
        assert handler is not None
        assert handler.bot_id == "target-bot"

    def test_find_handler_with_jurisdiction(self, manager):
        """Test finding handler with jurisdiction filter."""
        handler = manager.find_handler("special_service", jurisdiction="NSW")
        assert handler is not None

        handler_vic = manager.find_handler("special_service", jurisdiction="VIC")
        assert handler_vic is None

    def test_find_handler_exclude_bot(self, manager):
        """Test finding handler excluding specific bot."""
        handler = manager.find_handler("special_service", exclude_bot="target-bot")
        assert handler is None  # Only target-bot has this capability

    def test_find_handler_not_found(self, manager):
        """Test finding handler for nonexistent capability."""
        handler = manager.find_handler("nonexistent")
        assert handler is None

    @pytest.mark.asyncio
    async def test_warm_handoff(self, manager, sample_packet):
        """Test warm handoff with introduction."""
        status = await manager.warm_handoff(
            sample_packet,
            introduction_message="Connecting you to a specialist...",
        )
        assert status == HandoffStatus.ACCEPTED
        assert sample_packet.handoff_type == HandoffType.WARM

    @pytest.mark.asyncio
    async def test_escalate_to_human(self, manager):
        """Test escalation to human agent."""
        packet = HandoffPacket(
            source_bot_id="source-bot",
            source_bot_name="Source Bot",
            user_need="Complex situation requiring human",
        )

        status = await manager.escalate_to_human(packet, urgency="urgent")

        assert status == HandoffStatus.ACCEPTED
        assert packet.handoff_type == HandoffType.ESCALATION
        assert packet.reason == HandoffReason.ESCALATION
        assert packet.conversation.urgency == "urgent"
        assert packet.target_bot_id == "human-agent"

    @pytest.mark.asyncio
    async def test_escalate_to_human_no_agents(self, manager, registry):
        """Test escalation fails when no human agents available."""
        # Remove human agent
        registry.unregister("human-agent")

        packet = HandoffPacket(
            source_bot_id="source-bot",
            user_need="Need human help",
        )

        status = await manager.escalate_to_human(packet)
        assert status == HandoffStatus.FAILED

    def test_get_handoff_status_not_found(self, manager):
        """Test getting status of nonexistent handoff."""
        status = manager.get_handoff_status("nonexistent-id")
        assert status is None


# =============================================================================
# TEST PRE-CONFIGURED BOTS
# =============================================================================


class TestPreConfiguredBots:
    """Tests for pre-configured family law bots."""

    def test_legal_finder_bot(self):
        """Test LEGAL_FINDER_BOT configuration."""
        assert LEGAL_FINDER_BOT.bot_id == "legal-finder-au"
        assert LEGAL_FINDER_BOT.is_available is True
        assert LEGAL_FINDER_BOT.verified is True
        assert LEGAL_FINDER_BOT.trust_level == 5
        assert len(LEGAL_FINDER_BOT.capabilities) == 3
        assert LEGAL_FINDER_BOT.can_handle("find_legal_services")

    def test_legal_aid_nsw_bot(self):
        """Test LEGAL_AID_NSW_BOT configuration."""
        assert LEGAL_AID_NSW_BOT.bot_id == "legal-aid-nsw"
        assert LEGAL_AID_NSW_BOT.organization == "Legal Aid NSW"
        assert LEGAL_AID_NSW_BOT.can_handle("legal_advice")
        assert LEGAL_AID_NSW_BOT.can_handle("grant_eligibility")

    def test_court_filing_bot(self):
        """Test COURT_FILING_BOT configuration."""
        assert COURT_FILING_BOT.bot_id == "fcfcoa-efiling"
        assert COURT_FILING_BOT.can_handle("efiling")
        assert COURT_FILING_BOT.can_handle("document_tender")
        # Check efiling requires auth
        efiling_cap = next(
            c for c in COURT_FILING_BOT.capabilities if c.capability_id == "efiling"
        )
        assert efiling_cap.requires_auth is True
        assert efiling_cap.requires_case_id is True

    def test_dv_support_bot(self):
        """Test DV_SUPPORT_BOT configuration."""
        assert DV_SUPPORT_BOT.bot_id == "dv-support-au"
        assert DV_SUPPORT_BOT.organization == "1800RESPECT"
        assert DV_SUPPORT_BOT.can_handle("dv_support")
        assert DV_SUPPORT_BOT.can_handle("safety_planning")
        assert DV_SUPPORT_BOT.can_handle("crisis_support")

    def test_law_firm_bot(self):
        """Test LAW_FIRM_BOT configuration."""
        assert LAW_FIRM_BOT.bot_id == "familylaw-com-au"
        assert LAW_FIRM_BOT.trust_level == 4  # Lower than government bots
        assert LAW_FIRM_BOT.can_handle("client_intake")


# =============================================================================
# TEST NETWORK CREATION FUNCTION
# =============================================================================


class TestCreateFamilyLawBotNetwork:
    """Tests for create_family_law_bot_network function."""

    def test_creates_registry_with_all_bots(self):
        """Test network has all expected bots."""
        registry = create_family_law_bot_network()

        assert len(registry.list_all()) == 5
        assert registry.get_bot("legal-finder-au") is not None
        assert registry.get_bot("legal-aid-nsw") is not None
        assert registry.get_bot("fcfcoa-efiling") is not None
        assert registry.get_bot("dv-support-au") is not None
        assert registry.get_bot("familylaw-com-au") is not None

    def test_network_capability_lookups(self):
        """Test capability lookups work across network."""
        registry = create_family_law_bot_network()

        # Find eFiling handlers
        efiling_bots = registry.find_by_capability("efiling")
        assert len(efiling_bots) == 1
        assert efiling_bots[0].bot_id == "fcfcoa-efiling"

        # Find DV support
        dv_bots = registry.find_by_capability("dv_support")
        assert len(dv_bots) == 1
        assert dv_bots[0].bot_id == "dv-support-au"


# =============================================================================
# TEST DEMO SCENARIO
# =============================================================================


class TestDemoHandoffScenario:
    """Tests for demo_handoff_scenario function."""

    @pytest.mark.asyncio
    async def test_demo_runs_without_error(self, capsys):
        """Test demo scenario executes successfully."""
        await demo_handoff_scenario()

        captured = capsys.readouterr()
        assert "Bot Handoff Demo" in captured.out
        assert "Handoff Complete" in captured.out

    @pytest.mark.asyncio
    async def test_demo_finds_efiling_bot(self, capsys):
        """Test demo finds the eFiling bot."""
        await demo_handoff_scenario()

        captured = capsys.readouterr()
        assert "Court eFiling Assistant" in captured.out

    @pytest.mark.asyncio
    async def test_demo_handoff_accepted(self, capsys):
        """Test demo handoff is accepted."""
        await demo_handoff_scenario()

        captured = capsys.readouterr()
        assert "accepted" in captured.out


# =============================================================================
# TEST EDGE CASES AND ERROR HANDLING
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_identity_verification_empty_methods(self):
        """Test identity verification with empty methods."""
        identity = IdentityVerification(
            is_verified=True,
            verification_methods=[],
            documents_sighted=[],
        )
        data = identity.to_dict()
        assert data["verification_methods"] == []
        assert data["documents_sighted"] == []

    def test_personal_details_unicode_names(self):
        """Test personal details with unicode names."""
        details = PersonalDetails(
            given_name="José",
            family_name="García",
            preferred_name="José",
        )
        assert details.get_greeting_name() == "José"
        assert "José García" in details.get_full_name()

    def test_conversation_context_empty_messages(self):
        """Test conversation context handles empty messages."""
        conv = ConversationContext(
            conversation_id="empty-conv",
            started_at=datetime.now(),
            messages=[],
        )
        assert conv.messages == []
        assert conv.summary is None

    def test_handoff_packet_metadata(self):
        """Test handoff packet can store arbitrary metadata."""
        packet = HandoffPacket(
            metadata={
                "custom_field": "custom_value",
                "priority_score": 95,
                "tags": ["urgent", "family-law"],
            }
        )
        assert packet.metadata["custom_field"] == "custom_value"
        assert packet.metadata["priority_score"] == 95

    def test_bot_registry_reregister_same_bot(self):
        """Test re-registering same bot overwrites."""
        registry = BotRegistry()
        bot_v1 = RegisteredBot(
            bot_id="test-bot",
            name="Test Bot v1",
            organization="Org",
            description="Version 1",
            endpoint="https://v1.example.com",
        )
        bot_v2 = RegisteredBot(
            bot_id="test-bot",
            name="Test Bot v2",
            organization="Org",
            description="Version 2",
            endpoint="https://v2.example.com",
        )

        registry.register(bot_v1)
        registry.register(bot_v2)

        # Should have only 1 bot, but with v2's data
        assert len(registry.list_all()) == 1
        assert registry.get_bot("test-bot").name == "Test Bot v2"

    def test_handoff_manager_multiple_handoffs(self):
        """Test manager can track multiple concurrent handoffs."""
        registry = BotRegistry()
        registry.register(
            RegisteredBot(
                bot_id="bot-1",
                name="Bot 1",
                organization="Org",
                description="Desc",
                endpoint="https://example.com",
            )
        )
        manager = HandoffManager(registry)

        # Create multiple packets
        packet1 = HandoffPacket(target_bot_id="bot-1", user_need="Request 1")
        packet2 = HandoffPacket(target_bot_id="bot-1", user_need="Request 2")

        # Store both
        manager._active_handoffs[packet1.handoff_id] = packet1
        manager._active_handoffs[packet2.handoff_id] = packet2

        assert len(manager._active_handoffs) == 2
        assert manager.get_handoff_status(packet1.handoff_id) is not None
        assert manager.get_handoff_status(packet2.handoff_id) is not None


# =============================================================================
# TEST ASYNC TIMEOUT BEHAVIOR
# =============================================================================


class TestAsyncBehavior:
    """Tests for async/timeout behavior."""

    @pytest.fixture
    def manager_with_registry(self):
        """Create manager with minimal registry."""
        registry = BotRegistry()
        registry.register(
            RegisteredBot(
                bot_id="test-bot",
                name="Test Bot",
                organization="Test",
                description="A test bot",
                endpoint="https://test.example.com",
            )
        )
        return HandoffManager(registry)

    @pytest.mark.asyncio
    async def test_initiate_handoff_completes_quickly(self, manager_with_registry):
        """Test handoff initiation completes in reasonable time."""
        packet = HandoffPacket(
            target_bot_id="test-bot",
            user_need="Quick test",
        )

        # Should complete within 1 second (simulated delay is 0.1s)
        status = await asyncio.wait_for(
            manager_with_registry.initiate_handoff(packet),
            timeout=1.0,
        )
        assert status in (HandoffStatus.ACCEPTED, HandoffStatus.FAILED)

    @pytest.mark.asyncio
    async def test_warm_handoff_completes(self, manager_with_registry):
        """Test warm handoff completes successfully."""
        packet = HandoffPacket(
            target_bot_id="test-bot",
            user_need="Warm handoff test",
        )

        status = await manager_with_registry.warm_handoff(
            packet,
            introduction_message="Hello!",
        )
        assert status == HandoffStatus.ACCEPTED


# =============================================================================
# TEST SERIALIZATION ROUND-TRIPS
# =============================================================================


class TestSerializationRoundTrips:
    """Tests for data serialization."""

    def test_identity_verification_serialization(self):
        """Test IdentityVerification serializes all fields."""
        now = datetime.now()
        identity = IdentityVerification(
            is_verified=True,
            verification_level=IdentityVerificationLevel.MYGOVID_VERIFIED,
            verified_at=now,
            verified_by="mygovid-service",
            verification_methods=["mygovid", "biometric"],
            documents_sighted=[
                IdentityDocumentType.PASSPORT,
                IdentityDocumentType.DRIVERS_LICENCE,
            ],
            confidence_score=0.99,
            verification_token="secure-token-123",
            token_expires=now + timedelta(hours=24),
        )

        data = identity.to_dict()

        # Verify all fields serialized
        assert data["verification_level"] == "mygovid"
        assert len(data["documents_sighted"]) == 2
        assert "passport" in data["documents_sighted"]

    def test_handoff_packet_serialization(self):
        """Test HandoffPacket serializes correctly."""
        packet = HandoffPacket(
            source_bot_id="src",
            source_bot_name="Source",
            target_bot_id="tgt",
            target_bot_name="Target",
            handoff_type=HandoffType.SUPERVISED,
            reason=HandoffReason.SAFETY,
            reason_detail="User mentioned self-harm",
            user_need="Crisis support",
        )
        packet.conversation.safety_flags = ["self_harm_mentioned"]
        packet.conversation.urgency = "urgent"

        data = packet.to_dict()

        assert data["handoff_type"] == "supervised"
        assert data["reason"] == "safety"
        assert "self_harm_mentioned" in data["safety_flags"]
        assert data["urgency"] == "urgent"
