#!/usr/bin/env python3
"""
Court eFiling Integration - Document Submission via Chatbot
=============================================================

Allows legal firms and self-represented litigants to:
- File documents to the court electronically
- Tender documents DURING hearings via chatbot
- Track filing status
- Receive confirmation and receipts

USES:
=====

1. PRE-HEARING FILING
   - Affidavits, applications, responses
   - Evidence bundles
   - Written submissions

2. DURING HEARING FILING
   - Last-minute evidence
   - Objection documents
   - Tender documents in real-time
   - "May it please the court, tendering document X"

3. POST-HEARING FILING
   - Draft orders
   - Compliance documents
   - Further submissions (if ordered)

INTEGRATION:
============

Commonwealth Courts Portal (ComCourt) integration via:
- REST API for document upload
- Secure authentication (SAML/OAuth)
- Real-time status updates
- WebSocket for hearing integration

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later
"""

import asyncio
import hashlib
import logging
import mimetypes
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# DOCUMENT TYPES
# =============================================================================


class DocumentCategory(Enum):
    """Categories of court documents."""

    # Initiating
    INITIATING_APPLICATION = "initiating_application"
    RESPONSE = "response"
    REPLY = "reply"

    # Interim
    INTERIM_APPLICATION = "interim_application"
    INTERIM_RESPONSE = "interim_response"

    # Evidence
    AFFIDAVIT = "affidavit"
    ANNEXURE = "annexure"
    EXHIBIT = "exhibit"
    SUBPOENA_RESPONSE = "subpoena_response"

    # Expert
    FAMILY_REPORT = "family_report"
    EXPERT_REPORT = "expert_report"
    VALUATION = "valuation"

    # Orders
    CONSENT_ORDERS = "consent_orders"
    DRAFT_ORDERS = "draft_orders"
    MINUTE_OF_ORDERS = "minute_of_orders"

    # Submissions
    WRITTEN_SUBMISSION = "written_submission"
    OUTLINE_OF_ARGUMENT = "outline_of_argument"
    CHRONOLOGY = "chronology"

    # Compliance
    COMPLIANCE_CERTIFICATE = "compliance_certificate"
    FINANCIAL_STATEMENT = "financial_statement"

    # Other
    NOTICE_OF_ADDRESS = "notice_of_address"
    NOTICE_OF_DISCONTINUANCE = "notice_of_discontinuance"
    SUBPOENA = "subpoena"
    SUMMONS = "summons"


class FilingStatus(Enum):
    """Status of a document filing."""

    DRAFT = "draft"
    VALIDATING = "validating"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FILED = "filed"
    SERVED = "served"


class FilingUrgency(Enum):
    """Urgency of filing."""

    STANDARD = "standard"  # Normal processing
    PRIORITY = "priority"  # Within 24 hours
    URGENT = "urgent"  # Same day
    HEARING = "hearing"  # During hearing (immediate)


# =============================================================================
# DOCUMENT STRUCTURES
# =============================================================================


@dataclass
class CourtDocument:
    """A document to be filed with the court."""

    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Document details
    category: DocumentCategory = DocumentCategory.AFFIDAVIT
    title: str = ""
    description: str = ""

    # File
    filename: str = ""
    file_path: Optional[Path] = None
    file_size: int = 0
    mime_type: str = "application/pdf"
    checksum: str = ""  # SHA-256

    # Case
    case_number: str = ""
    court_registry: str = ""

    # Parties
    filing_party: str = ""  # "applicant" or "respondent"
    filed_by: str = ""  # Name of person filing

    # Status
    status: FilingStatus = FilingStatus.DRAFT
    filed_at: Optional[datetime] = None
    receipt_number: Optional[str] = None

    # For hearing tenders
    is_tender: bool = False
    tender_number: Optional[str] = None  # e.g., "Exhibit A-1"
    tendered_at: Optional[datetime] = None

    def calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA-256 checksum of document content."""
        self.checksum = hashlib.sha256(content).hexdigest()
        return self.checksum


@dataclass
class FilingReceipt:
    """Receipt for a filed document."""

    receipt_number: str
    document_id: str
    case_number: str
    filed_at: datetime
    document_category: DocumentCategory
    document_title: str
    filing_party: str
    court_registry: str

    # Fee
    fee_amount: float = 0.0
    fee_paid: bool = False
    fee_receipt: Optional[str] = None

    def format_for_display(self) -> str:
        """Format receipt for display."""
        return (
            f"FILING RECEIPT\n"
            f"==============\n"
            f"Receipt Number: {self.receipt_number}\n"
            f"Case Number: {self.case_number}\n"
            f"Document: {self.document_title}\n"
            f"Category: {self.document_category.value}\n"
            f"Filed: {self.filed_at.strftime('%d/%m/%Y %H:%M')}\n"
            f"Registry: {self.court_registry}\n"
            f"Filing Party: {self.filing_party}\n"
        )


@dataclass
class HearingSession:
    """An active hearing session for real-time document tenders."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_number: str = ""
    hearing_date: date = field(default_factory=date.today)

    # Hearing details
    hearing_type: str = ""  # "interim", "final", "mention", etc.
    judicial_officer: str = ""
    courtroom: str = ""

    # Session state
    is_active: bool = False
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    # Documents tendered this hearing
    tendered_documents: List[CourtDocument] = field(default_factory=list)
    tender_counter: int = 0

    # Participants connected
    participants: List[str] = field(default_factory=list)

    def next_tender_number(self, party: str) -> str:
        """Generate next tender/exhibit number."""
        self.tender_counter += 1
        prefix = "A" if party == "applicant" else "R"
        return f"Exhibit {prefix}-{self.tender_counter}"


# =============================================================================
# EFILING SERVICE
# =============================================================================


class EFilingService:
    """
    Service for electronic filing of court documents.

    Integrates with Commonwealth Courts Portal (ComCourt).

    Example Usage:
        service = EFilingService()

        # Create document
        doc = CourtDocument(
            category=DocumentCategory.AFFIDAVIT,
            title="Affidavit of Sarah Smith",
            case_number="FAM-2024-001234",
            filing_party="applicant",
        )

        # Upload and file
        with open("affidavit.pdf", "rb") as f:
            receipt = await service.file_document(doc, f)

        print(f"Filed! Receipt: {receipt.receipt_number}")
    """

    def __init__(
        self,
        api_endpoint: str = "https://efiling.fcfcoa.gov.au/api",
        auth_token: Optional[str] = None,
    ):
        self.api_endpoint = api_endpoint
        self.auth_token = auth_token
        self._active_hearings: Dict[str, HearingSession] = {}

    async def validate_document(
        self, document: CourtDocument
    ) -> Tuple[bool, List[str]]:
        """
        Validate document before filing.

        Checks:
        - Required fields present
        - File format acceptable
        - File size within limits
        - Case number valid

        Returns (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        if not document.case_number:
            errors.append("Case number is required")

        if not document.title:
            errors.append("Document title is required")

        if not document.filing_party:
            errors.append("Filing party must be specified")

        if not document.filename:
            errors.append("Document filename is required")

        # Check file format
        allowed_formats = [".pdf", ".doc", ".docx", ".rtf"]
        ext = Path(document.filename).suffix.lower()
        if ext not in allowed_formats:
            errors.append(f"File format {ext} not accepted. Use: {allowed_formats}")

        # Check file size (max 25MB per document)
        max_size = 25 * 1024 * 1024
        if document.file_size > max_size:
            errors.append("File too large. Maximum size is 25MB")

        # Check consent orders format (must have signed + unsigned)
        if document.category == DocumentCategory.CONSENT_ORDERS:
            # Consent orders need both signed PDF and unsigned DOCX
            logger.info(
                "Consent orders detected - ensure both signed PDF "
                "and unsigned DOCX are filed"
            )

        is_valid = len(errors) == 0
        return is_valid, errors

    async def file_document(
        self,
        document: CourtDocument,
        file_content: BinaryIO,
        urgency: FilingUrgency = FilingUrgency.STANDARD,
    ) -> Optional[FilingReceipt]:
        """
        File a document with the court.

        Args:
            document: Document metadata
            file_content: File content (binary)
            urgency: Filing urgency level

        Returns:
            FilingReceipt on success, None on failure
        """
        # Read and hash content
        content = file_content.read()
        document.file_size = len(content)
        document.calculate_checksum(content)

        # Validate
        document.status = FilingStatus.VALIDATING
        is_valid, errors = await self.validate_document(document)

        if not is_valid:
            logger.error(f"Document validation failed: {errors}")
            document.status = FilingStatus.REJECTED
            return None

        # Submit to court
        document.status = FilingStatus.SUBMITTED
        logger.info(f"Submitting {document.title} to {document.court_registry}")

        # In production, this would call the ComCourt API
        # POST to /api/v1/documents/file
        # with multipart/form-data containing the document

        await asyncio.sleep(0.5)  # Simulate API call

        # Generate receipt
        document.status = FilingStatus.FILED
        document.filed_at = datetime.now()
        document.receipt_number = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        receipt = FilingReceipt(
            receipt_number=document.receipt_number,
            document_id=document.document_id,
            case_number=document.case_number,
            filed_at=document.filed_at,
            document_category=document.category,
            document_title=document.title,
            filing_party=document.filing_party,
            court_registry=document.court_registry,
        )

        logger.info(f"Document filed successfully: {receipt.receipt_number}")

        return receipt

    async def check_filing_status(self, receipt_number: str) -> FilingStatus:
        """Check the status of a filed document."""
        # In production, this would query the ComCourt API
        logger.info(f"Checking status of {receipt_number}")
        return FilingStatus.FILED

    # =========================================================================
    # HEARING INTEGRATION - Real-time document tenders
    # =========================================================================

    async def join_hearing(
        self,
        case_number: str,
        participant_id: str,
        participant_role: str,
    ) -> Optional[HearingSession]:
        """
        Join an active hearing session.

        Allows real-time document tenders during the hearing.
        """
        # Check if hearing exists
        if case_number in self._active_hearings:
            session = self._active_hearings[case_number]
        else:
            # Create new hearing session
            session = HearingSession(
                case_number=case_number,
                is_active=True,
                started_at=datetime.now(),
            )
            self._active_hearings[case_number] = session

        session.participants.append(f"{participant_id}:{participant_role}")
        logger.info(f"Participant {participant_id} joined hearing {case_number}")

        return session

    async def tender_document(
        self,
        session: HearingSession,
        document: CourtDocument,
        file_content: BinaryIO,
        party: str,
    ) -> Tuple[bool, str]:
        """
        Tender a document during a hearing.

        This is for real-time submission during court proceedings.

        Args:
            session: Active hearing session
            document: Document to tender
            file_content: File content
            party: "applicant" or "respondent"

        Returns:
            (success, tender_number_or_error)
        """
        if not session.is_active:
            return False, "Hearing session is not active"

        # Read content
        content = file_content.read()
        document.file_size = len(content)
        document.calculate_checksum(content)

        # Validate quickly (hearings need fast processing)
        if document.file_size > 10 * 1024 * 1024:  # 10MB limit for tenders
            return False, "Tender documents must be under 10MB"

        # Mark as tender
        document.is_tender = True
        document.tender_number = session.next_tender_number(party)
        document.tendered_at = datetime.now()
        document.status = FilingStatus.FILED

        # Add to hearing record
        session.tendered_documents.append(document)

        logger.info(
            f"Document tendered as {document.tender_number} "
            f"in case {session.case_number}"
        )

        # Notify court (in production, via WebSocket to judge's screen)
        notification = (
            f"TENDER: {document.tender_number}\n"
            f"Document: {document.title}\n"
            f"Filed by: {party}\n"
            f"Time: {document.tendered_at.strftime('%H:%M:%S')}"
        )
        logger.info(notification)

        return True, document.tender_number

    async def leave_hearing(
        self,
        session: HearingSession,
        participant_id: str,
    ) -> None:
        """Leave an active hearing session."""
        session.participants = [
            p for p in session.participants if not p.startswith(f"{participant_id}:")
        ]

        if not session.participants:
            session.is_active = False
            session.ended_at = datetime.now()
            logger.info(f"Hearing session {session.case_number} ended")


# =============================================================================
# CHATBOT FILING ASSISTANT
# =============================================================================


class FilingAssistant:
    """
    Chatbot assistant for filing documents.

    Guides users through the filing process with
    conversational interface.

    Example:
        assistant = FilingAssistant(efiling_service)

        # Start filing flow
        response = await assistant.start_filing(
            case_number="FAM-2024-001234",
            user_role="applicant"
        )

        # User interaction
        response = await assistant.process_message(
            session_id="xxx",
            message="I want to file an affidavit"
        )
    """

    def __init__(self, efiling_service: EFilingService):
        self.service = efiling_service
        self._sessions: Dict[str, Dict[str, Any]] = {}

    async def start_filing(
        self,
        case_number: str,
        user_role: str,
        user_name: str,
    ) -> Dict[str, Any]:
        """Start a new filing session."""
        session_id = str(uuid.uuid4())

        self._sessions[session_id] = {
            "case_number": case_number,
            "user_role": user_role,
            "user_name": user_name,
            "state": "choose_document_type",
            "document": None,
        }

        response = {
            "session_id": session_id,
            "message": (
                f"I can help you file documents for case {case_number}.\n\n"
                "What type of document would you like to file?\n\n"
                "1. Affidavit\n"
                "2. Response to Application\n"
                "3. Consent Orders\n"
                "4. Written Submissions\n"
                "5. Financial Statement\n"
                "6. Other document\n"
            ),
            "options": [
                "Affidavit",
                "Response to Application",
                "Consent Orders",
                "Written Submissions",
                "Financial Statement",
                "Other",
            ],
        }

        return response

    async def process_message(
        self,
        session_id: str,
        message: str,
        file_content: Optional[BinaryIO] = None,
    ) -> Dict[str, Any]:
        """Process a message in the filing flow."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        state = session["state"]

        if state == "choose_document_type":
            return await self._handle_document_type(session_id, message)

        elif state == "confirm_details":
            return await self._handle_confirm(session_id, message)

        elif state == "upload_file":
            if file_content:
                return await self._handle_file_upload(session_id, file_content)
            else:
                return {
                    "message": "Please upload your document file (PDF, DOC, or DOCX).",
                    "awaiting": "file_upload",
                }

        elif state == "final_confirm":
            return await self._handle_final_confirm(session_id, message)

        return {"message": "I didn't understand. Can you try again?"}

    async def _handle_document_type(
        self,
        session_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Handle document type selection."""
        session = self._sessions[session_id]
        message_lower = message.lower()

        # Map input to document category
        category_map = {
            "affidavit": DocumentCategory.AFFIDAVIT,
            "1": DocumentCategory.AFFIDAVIT,
            "response": DocumentCategory.RESPONSE,
            "2": DocumentCategory.RESPONSE,
            "consent": DocumentCategory.CONSENT_ORDERS,
            "3": DocumentCategory.CONSENT_ORDERS,
            "submission": DocumentCategory.WRITTEN_SUBMISSION,
            "4": DocumentCategory.WRITTEN_SUBMISSION,
            "financial": DocumentCategory.FINANCIAL_STATEMENT,
            "5": DocumentCategory.FINANCIAL_STATEMENT,
        }

        category = None
        for key, cat in category_map.items():
            if key in message_lower:
                category = cat
                break

        if not category:
            return {
                "message": "I didn't recognize that document type. Please choose from the options above.",
            }

        # Create document
        session["document"] = CourtDocument(
            category=category,
            case_number=session["case_number"],
            filing_party=session["user_role"],
            filed_by=session["user_name"],
        )
        session["state"] = "confirm_details"

        return {
            "message": (
                f"You want to file a {category.value.replace('_', ' ').title()}.\n\n"
                f"Please provide the title for this document.\n"
                f"For example: 'Affidavit of {session['user_name']} sworn [date]'"
            ),
            "awaiting": "text_input",
        }

    async def _handle_confirm(
        self,
        session_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Handle document title and confirm."""
        session = self._sessions[session_id]
        doc = session["document"]

        doc.title = message
        session["state"] = "upload_file"

        return {
            "message": (
                f"Document title: {doc.title}\n\n"
                "Please upload your document file.\n"
                "Accepted formats: PDF (preferred), DOC, DOCX\n"
                "Maximum size: 25MB"
            ),
            "awaiting": "file_upload",
        }

    async def _handle_file_upload(
        self,
        session_id: str,
        file_content: BinaryIO,
    ) -> Dict[str, Any]:
        """Handle file upload."""
        session = self._sessions[session_id]
        doc = session["document"]

        # Read file info
        content = file_content.read()
        file_content.seek(0)  # Reset for later use

        doc.file_size = len(content)
        doc.calculate_checksum(content)

        # Validate
        is_valid, errors = await self.service.validate_document(doc)

        if not is_valid:
            return {
                "message": "Document validation failed:\n- " + "\n- ".join(errors),
                "awaiting": "file_upload",
            }

        session["file_content"] = file_content
        session["state"] = "final_confirm"

        return {
            "message": (
                f"Ready to file:\n\n"
                f"📄 {doc.title}\n"
                f"📁 Type: {doc.category.value.replace('_', ' ').title()}\n"
                f"⚖️ Case: {doc.case_number}\n"
                f"👤 Filing party: {doc.filing_party}\n"
                f"📦 File size: {doc.file_size / 1024:.1f} KB\n\n"
                "Shall I file this document now?\n"
                "Reply YES to file, or NO to cancel."
            ),
            "options": ["Yes, file it", "No, cancel"],
        }

    async def _handle_final_confirm(
        self,
        session_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Handle final confirmation and file."""
        session = self._sessions[session_id]

        if message.lower() in ["yes", "y", "file it", "yes, file it"]:
            doc = session["document"]
            file_content = session["file_content"]
            file_content.seek(0)

            receipt = await self.service.file_document(doc, file_content)

            if receipt:
                # Clean up session
                del self._sessions[session_id]

                return {
                    "message": (
                        "✅ DOCUMENT FILED SUCCESSFULLY\n\n"
                        f"{receipt.format_for_display()}\n"
                        "You will receive email confirmation shortly.\n\n"
                        "Is there anything else I can help you with?"
                    ),
                    "receipt": receipt,
                    "complete": True,
                }
            else:
                return {
                    "message": "❌ Filing failed. Please try again or contact court registry.",
                    "error": True,
                }

        else:
            del self._sessions[session_id]
            return {
                "message": "Filing cancelled. Let me know if you need help with anything else.",
                "complete": True,
            }


# =============================================================================
# EXAMPLE USAGE
# =============================================================================


async def demo_efiling():
    """Demonstrate the eFiling service."""
    print("=== Court eFiling Demo ===\n")

    service = EFilingService()
    assistant = FilingAssistant(service)

    # Start filing session
    print("1. Starting filing session...")
    response = await assistant.start_filing(
        case_number="FAM-2024-001234",
        user_role="applicant",
        user_name="Sarah Smith",
    )
    session_id = response["session_id"]
    print(f"   {response['message'][:100]}...")

    # Select document type
    print("\n2. Selecting affidavit...")
    response = await assistant.process_message(session_id, "affidavit")
    print(f"   {response['message'][:100]}...")

    # Provide title
    print("\n3. Setting title...")
    response = await assistant.process_message(
        session_id, "Affidavit of Sarah Smith sworn 15 March 2024"
    )
    print(f"   {response['message'][:100]}...")

    print("\n=== Filing Demo Complete ===")

    # Demo hearing tender
    print("\n\n=== Hearing Tender Demo ===\n")

    # Join hearing
    session = await service.join_hearing(
        case_number="FAM-2024-001234",
        participant_id="lawyer-001",
        participant_role="applicant_lawyer",
    )
    print(f"1. Joined hearing session: {session.session_id[:8]}...")

    # Simulate tendering a document
    print("2. Tendering document during hearing...")
    doc = CourtDocument(
        category=DocumentCategory.EXHIBIT,
        title="Text messages between parties",
        case_number="FAM-2024-001234",
        filing_party="applicant",
        filename="text_messages.pdf",
    )

    # In real usage, would have actual file content
    import io

    fake_content = io.BytesIO(b"fake PDF content for demo")

    success, tender_num = await service.tender_document(
        session, doc, fake_content, "applicant"
    )

    if success:
        print(f"   ✅ Document tendered as {tender_num}")

    print("\n=== Hearing Tender Complete ===")


if __name__ == "__main__":
    asyncio.run(demo_efiling())
