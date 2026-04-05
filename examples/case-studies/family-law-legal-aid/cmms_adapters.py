#!/usr/bin/env python3
"""
CMMS Adapter Layer - Case Management System Integration

Lightweight adapter pattern for integration with major case management systems.
Designed to be compatible with ALL major vendors through simple interfaces.

Supported Systems (via adapters):
=================================
- Alfresco Process Services (Activiti)
- IBM FileNet P8
- IBM Business Automation Workflow (BAW)
- Microsoft Dynamics 365
- Salesforce Service Cloud
- ServiceNow
- LEAP Legal Software
- Actionstep
- Clio Manage
- PracticePanther

Design Philosophy:
==================
1. LIGHTWEIGHT - Minimal dependencies, simple interfaces
2. UNIVERSAL - Standard patterns that map to any CMMS
3. EXTENSIBLE - Easy to add new vendor adapters
4. RAG-FOCUSED - Integrates with agentic-brain RAG pipeline

Standard Operations:
====================
- Matter/Case CRUD (Create, Read, Update, Delete)
- Workflow state transitions (BPM-style)
- Document management hooks
- Calendar/deadline sync
- Contact/party management
- Audit trail logging

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


# =============================================================================
# STANDARD CMMS DATA STRUCTURES
# =============================================================================


class CaseStatus(Enum):
    """Universal case status mapping."""

    DRAFT = "draft"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"


class WorkflowAction(Enum):
    """Standard BPM workflow actions."""

    CREATE = "create"
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    ASSIGN = "assign"
    COMPLETE = "complete"
    CANCEL = "cancel"
    REOPEN = "reopen"


@dataclass
class CMMSCase:
    """
    Universal case representation compatible with all CMMS platforms.

    This maps to:
    - Alfresco: Process Instance / Case
    - IBM FileNet: Case object
    - IBM BAW: Business Object
    - Dynamics 365: Case entity
    - Salesforce: Case object
    - LEAP: Matter
    - Clio: Matter
    """

    # Core identifiers
    id: str
    external_id: Optional[str] = None  # Vendor-specific ID
    reference: str = ""  # Human-readable reference (e.g., "SMITH-2024-001")

    # Classification
    case_type: str = "family_law"
    sub_type: str = ""  # e.g., "parenting", "property", "divorce"

    # Status
    status: CaseStatus = CaseStatus.DRAFT
    phase: str = ""  # Custom phase within workflow

    # Parties
    parties: List[Dict[str, Any]] = field(default_factory=list)
    primary_contact_id: Optional[str] = None

    # Dates
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None

    # Assignments
    owner_id: Optional[str] = None
    team_id: Optional[str] = None
    assigned_to: List[str] = field(default_factory=list)

    # Content
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # Custom fields (vendor-specific)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        return {
            "id": self.id,
            "external_id": self.external_id,
            "reference": self.reference,
            "case_type": self.case_type,
            "sub_type": self.sub_type,
            "status": self.status.value,
            "phase": self.phase,
            "parties": self.parties,
            "primary_contact_id": self.primary_contact_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "owner_id": self.owner_id,
            "team_id": self.team_id,
            "assigned_to": self.assigned_to,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "custom_fields": self.custom_fields,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CMMSCase":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            external_id=data.get("external_id"),
            reference=data.get("reference", ""),
            case_type=data.get("case_type", "family_law"),
            sub_type=data.get("sub_type", ""),
            status=CaseStatus(data.get("status", "draft")),
            phase=data.get("phase", ""),
            parties=data.get("parties", []),
            primary_contact_id=data.get("primary_contact_id"),
            owner_id=data.get("owner_id"),
            team_id=data.get("team_id"),
            assigned_to=data.get("assigned_to", []),
            title=data.get("title", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            custom_fields=data.get("custom_fields", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CMMSDocument:
    """Universal document representation."""

    id: str
    case_id: str
    name: str
    document_type: str  # e.g., "affidavit", "consent_order", "evidence"
    mime_type: str = "application/pdf"
    size_bytes: int = 0

    # Location
    storage_path: Optional[str] = None
    external_url: Optional[str] = None

    # Status
    status: str = "draft"  # draft, pending_review, approved, filed
    version: int = 1

    # Dates
    created_at: datetime = field(default_factory=datetime.now)
    filed_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CMMSEvent:
    """Workflow event for audit trail."""

    id: str
    case_id: str
    event_type: str  # e.g., "status_change", "document_added", "deadline_set"
    action: WorkflowAction

    # Actor
    user_id: Optional[str] = None
    user_name: str = "System"

    # Details
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    description: str = ""

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)

    # Additional data
    data: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ABSTRACT CMMS ADAPTER INTERFACE
# =============================================================================


class CMMSAdapter(ABC):
    """
    Abstract base class for CMMS integrations.

    Implement this interface to connect to any case management system.
    The interface is designed to map cleanly to BPM/CMMS standards.

    Example:
        class MyCMSAdapter(CMMSAdapter):
            def create_case(self, case: CMMSCase) -> str:
                # Map to your CMS API
                response = my_cms_api.cases.create(case.to_dict())
                return response.id
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter name (e.g., 'alfresco', 'dynamics365')."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Adapter version."""
        pass

    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------

    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> bool:
        """
        Connect to the CMMS.

        Args:
            config: Connection configuration (URL, credentials, etc.)

        Returns:
            True if connected successfully
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the CMMS."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check connection health."""
        pass

    # -------------------------------------------------------------------------
    # Case CRUD
    # -------------------------------------------------------------------------

    @abstractmethod
    def create_case(self, case: CMMSCase) -> str:
        """
        Create a new case.

        Args:
            case: Case to create

        Returns:
            External case ID from the CMMS
        """
        pass

    @abstractmethod
    def get_case(self, case_id: str) -> Optional[CMMSCase]:
        """
        Retrieve a case by ID.

        Args:
            case_id: Case ID (internal or external)

        Returns:
            Case or None if not found
        """
        pass

    @abstractmethod
    def update_case(self, case: CMMSCase) -> bool:
        """
        Update an existing case.

        Args:
            case: Case with updated fields

        Returns:
            True if updated successfully
        """
        pass

    @abstractmethod
    def delete_case(self, case_id: str) -> bool:
        """
        Delete a case (or mark as deleted).

        Args:
            case_id: Case ID

        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    def search_cases(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[CMMSCase]:
        """
        Search for cases.

        Args:
            query: Search query
            filters: Optional filters
            limit: Max results

        Returns:
            List of matching cases
        """
        pass

    # -------------------------------------------------------------------------
    # Workflow
    # -------------------------------------------------------------------------

    @abstractmethod
    def transition_case(
        self,
        case_id: str,
        action: WorkflowAction,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Perform a workflow transition.

        Args:
            case_id: Case ID
            action: Workflow action to perform
            data: Additional data for the transition

        Returns:
            True if transition successful
        """
        pass

    @abstractmethod
    def get_available_actions(self, case_id: str) -> List[WorkflowAction]:
        """
        Get available workflow actions for a case.

        Args:
            case_id: Case ID

        Returns:
            List of available actions
        """
        pass

    # -------------------------------------------------------------------------
    # Documents
    # -------------------------------------------------------------------------

    @abstractmethod
    def add_document(self, document: CMMSDocument, content: bytes) -> str:
        """
        Add a document to a case.

        Args:
            document: Document metadata
            content: Document content

        Returns:
            External document ID
        """
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[CMMSDocument]:
        """Get document metadata."""
        pass

    @abstractmethod
    def get_document_content(self, document_id: str) -> Optional[bytes]:
        """Get document content."""
        pass

    @abstractmethod
    def list_documents(self, case_id: str) -> List[CMMSDocument]:
        """List all documents for a case."""
        pass

    # -------------------------------------------------------------------------
    # Events / Audit
    # -------------------------------------------------------------------------

    @abstractmethod
    def log_event(self, event: CMMSEvent) -> str:
        """Log a workflow event."""
        pass

    @abstractmethod
    def get_case_history(self, case_id: str) -> List[CMMSEvent]:
        """Get audit history for a case."""
        pass

    # -------------------------------------------------------------------------
    # Deadlines / Calendar
    # -------------------------------------------------------------------------

    def set_deadline(
        self,
        case_id: str,
        deadline_type: str,
        due_date: datetime,
        reminder_days: int = 3,
    ) -> str:
        """
        Set a deadline for a case.

        Default implementation stores in case metadata.
        Override for CMMS-specific calendar integration.
        """
        case = self.get_case(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        deadlines = case.metadata.get("deadlines", [])
        deadline_id = f"dl_{len(deadlines)}"

        deadlines.append(
            {
                "id": deadline_id,
                "type": deadline_type,
                "due_date": due_date.isoformat(),
                "reminder_days": reminder_days,
                "status": "pending",
            }
        )

        case.metadata["deadlines"] = deadlines
        self.update_case(case)

        return deadline_id

    def get_deadlines(self, case_id: str) -> List[Dict[str, Any]]:
        """Get all deadlines for a case."""
        case = self.get_case(case_id)
        if not case:
            return []
        return case.metadata.get("deadlines", [])


# =============================================================================
# WEBHOOK SUPPORT
# =============================================================================


class CMMSWebhookHandler:
    """
    Handle incoming webhooks from CMMS platforms.

    Maps vendor-specific webhook payloads to standard CMMSEvents.
    """

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}

    def register_handler(
        self,
        event_type: str,
        handler: Callable[[CMMSEvent], None],
    ) -> None:
        """Register a handler for an event type."""
        self.handlers[event_type] = handler

    def process_webhook(
        self,
        vendor: str,
        payload: Dict[str, Any],
    ) -> CMMSEvent:
        """
        Process incoming webhook and dispatch to handlers.

        Args:
            vendor: Vendor name (alfresco, dynamics365, etc.)
            payload: Raw webhook payload

        Returns:
            Normalized CMMSEvent
        """
        # Normalize to standard event
        event = self._normalize_payload(vendor, payload)

        # Dispatch to handler
        if event.event_type in self.handlers:
            self.handlers[event.event_type](event)

        return event

    def _normalize_payload(
        self,
        vendor: str,
        payload: Dict[str, Any],
    ) -> CMMSEvent:
        """Normalize vendor-specific payload to CMMSEvent."""

        # Vendor-specific mapping
        if vendor == "dynamics365":
            return self._normalize_dynamics(payload)
        elif vendor == "salesforce":
            return self._normalize_salesforce(payload)
        elif vendor == "alfresco":
            return self._normalize_alfresco(payload)
        else:
            # Generic mapping
            return CMMSEvent(
                id=payload.get("id", "unknown"),
                case_id=payload.get("case_id", payload.get("record_id", "")),
                event_type=payload.get("event_type", payload.get("type", "unknown")),
                action=WorkflowAction.SUBMIT,
                description=str(payload),
                data=payload,
            )

    def _normalize_dynamics(self, payload: Dict[str, Any]) -> CMMSEvent:
        """Normalize Dynamics 365 webhook."""
        return CMMSEvent(
            id=payload.get("MessageId", ""),
            case_id=payload.get("PrimaryEntityId", ""),
            event_type=payload.get("MessageName", ""),  # Create, Update, Delete
            action=self._map_dynamics_action(payload.get("MessageName", "")),
            description=f"Dynamics 365: {payload.get('MessageName')}",
            data=payload,
        )

    def _normalize_salesforce(self, payload: Dict[str, Any]) -> CMMSEvent:
        """Normalize Salesforce webhook."""
        return CMMSEvent(
            id=payload.get("event", {}).get("replayId", ""),
            case_id=payload.get("sobject", {}).get("Id", ""),
            event_type=payload.get("event", {}).get("type", ""),
            action=WorkflowAction.SUBMIT,
            description=f"Salesforce: {payload.get('event', {}).get('type')}",
            data=payload,
        )

    def _normalize_alfresco(self, payload: Dict[str, Any]) -> CMMSEvent:
        """Normalize Alfresco webhook."""
        return CMMSEvent(
            id=payload.get("id", ""),
            case_id=payload.get("processInstanceId", payload.get("caseId", "")),
            event_type=payload.get("eventType", ""),
            action=self._map_alfresco_action(payload.get("eventType", "")),
            description=f"Alfresco: {payload.get('eventType')}",
            data=payload,
        )

    def _map_dynamics_action(self, message_name: str) -> WorkflowAction:
        """Map Dynamics message to workflow action."""
        mapping = {
            "Create": WorkflowAction.CREATE,
            "Update": WorkflowAction.SUBMIT,
            "Delete": WorkflowAction.CANCEL,
            "Assign": WorkflowAction.ASSIGN,
        }
        return mapping.get(message_name, WorkflowAction.SUBMIT)

    def _map_alfresco_action(self, event_type: str) -> WorkflowAction:
        """Map Alfresco event to workflow action."""
        mapping = {
            "PROCESS_STARTED": WorkflowAction.CREATE,
            "PROCESS_COMPLETED": WorkflowAction.COMPLETE,
            "PROCESS_CANCELLED": WorkflowAction.CANCEL,
            "TASK_ASSIGNED": WorkflowAction.ASSIGN,
            "TASK_COMPLETED": WorkflowAction.COMPLETE,
        }
        return mapping.get(event_type, WorkflowAction.SUBMIT)


# =============================================================================
# EXAMPLE ADAPTER: LOCAL/MEMORY (for testing)
# =============================================================================


class LocalCMMSAdapter(CMMSAdapter):
    """
    Local in-memory CMMS adapter for testing and development.

    Stores everything in memory - no external dependencies.
    Perfect for unit tests and local development.
    """

    def __init__(self):
        self.cases: Dict[str, CMMSCase] = {}
        self.documents: Dict[str, CMMSDocument] = {}
        self.document_content: Dict[str, bytes] = {}
        self.events: List[CMMSEvent] = []
        self.connected = False

    @property
    def name(self) -> str:
        return "local"

    @property
    def version(self) -> str:
        return "1.0.0"

    def connect(self, config: Dict[str, Any]) -> bool:
        self.connected = True
        logger.info("LocalCMMSAdapter connected")
        return True

    def disconnect(self) -> None:
        self.connected = False

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.connected else "disconnected",
            "cases": len(self.cases),
            "documents": len(self.documents),
        }

    def create_case(self, case: CMMSCase) -> str:
        self.cases[case.id] = case
        self._log_event(case.id, "case_created", WorkflowAction.CREATE)
        return case.id

    def get_case(self, case_id: str) -> Optional[CMMSCase]:
        return self.cases.get(case_id)

    def update_case(self, case: CMMSCase) -> bool:
        if case.id not in self.cases:
            return False
        case.updated_at = datetime.now()
        self.cases[case.id] = case
        self._log_event(case.id, "case_updated", WorkflowAction.SUBMIT)
        return True

    def delete_case(self, case_id: str) -> bool:
        if case_id in self.cases:
            del self.cases[case_id]
            self._log_event(case_id, "case_deleted", WorkflowAction.CANCEL)
            return True
        return False

    def search_cases(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[CMMSCase]:
        results = []
        query_lower = query.lower()

        for case in self.cases.values():
            if (
                query_lower in case.title.lower()
                or query_lower in case.description.lower()
                or query_lower in case.reference.lower()
            ):

                # Apply filters
                if filters:
                    if "status" in filters and case.status.value != filters["status"]:
                        continue
                    if (
                        "case_type" in filters
                        and case.case_type != filters["case_type"]
                    ):
                        continue

                results.append(case)

                if len(results) >= limit:
                    break

        return results

    def transition_case(
        self,
        case_id: str,
        action: WorkflowAction,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        case = self.get_case(case_id)
        if not case:
            return False

        # Simple state machine
        transitions = {
            (CaseStatus.DRAFT, WorkflowAction.SUBMIT): CaseStatus.OPEN,
            (CaseStatus.OPEN, WorkflowAction.ASSIGN): CaseStatus.IN_PROGRESS,
            (
                CaseStatus.IN_PROGRESS,
                WorkflowAction.COMPLETE,
            ): CaseStatus.PENDING_REVIEW,
            (CaseStatus.PENDING_REVIEW, WorkflowAction.APPROVE): CaseStatus.RESOLVED,
            (CaseStatus.PENDING_REVIEW, WorkflowAction.REJECT): CaseStatus.IN_PROGRESS,
            (CaseStatus.RESOLVED, WorkflowAction.COMPLETE): CaseStatus.CLOSED,
            (CaseStatus.CLOSED, WorkflowAction.REOPEN): CaseStatus.OPEN,
        }

        key = (case.status, action)
        if key in transitions:
            old_status = case.status
            case.status = transitions[key]
            self.update_case(case)
            self._log_event(
                case_id,
                "status_change",
                action,
                from_state=old_status.value,
                to_state=case.status.value,
            )
            return True

        return False

    def get_available_actions(self, case_id: str) -> List[WorkflowAction]:
        case = self.get_case(case_id)
        if not case:
            return []

        # What actions are available from current status
        action_map = {
            CaseStatus.DRAFT: [WorkflowAction.SUBMIT, WorkflowAction.CANCEL],
            CaseStatus.OPEN: [WorkflowAction.ASSIGN, WorkflowAction.CANCEL],
            CaseStatus.IN_PROGRESS: [WorkflowAction.COMPLETE, WorkflowAction.ESCALATE],
            CaseStatus.PENDING_REVIEW: [WorkflowAction.APPROVE, WorkflowAction.REJECT],
            CaseStatus.RESOLVED: [WorkflowAction.COMPLETE, WorkflowAction.REOPEN],
            CaseStatus.CLOSED: [WorkflowAction.REOPEN],
        }

        return action_map.get(case.status, [])

    def add_document(self, document: CMMSDocument, content: bytes) -> str:
        self.documents[document.id] = document
        self.document_content[document.id] = content
        self._log_event(document.case_id, "document_added", WorkflowAction.SUBMIT)
        return document.id

    def get_document(self, document_id: str) -> Optional[CMMSDocument]:
        return self.documents.get(document_id)

    def get_document_content(self, document_id: str) -> Optional[bytes]:
        return self.document_content.get(document_id)

    def list_documents(self, case_id: str) -> List[CMMSDocument]:
        return [doc for doc in self.documents.values() if doc.case_id == case_id]

    def log_event(self, event: CMMSEvent) -> str:
        self.events.append(event)
        return event.id

    def get_case_history(self, case_id: str) -> List[CMMSEvent]:
        return [e for e in self.events if e.case_id == case_id]

    def _log_event(
        self,
        case_id: str,
        event_type: str,
        action: WorkflowAction,
        **kwargs,
    ) -> None:
        """Internal event logging."""
        event = CMMSEvent(
            id=f"evt_{len(self.events)}",
            case_id=case_id,
            event_type=event_type,
            action=action,
            **kwargs,
        )
        self.events.append(event)


# =============================================================================
# EXAMPLE ADAPTER: DYNAMICS 365 (Skeleton)
# =============================================================================


class Dynamics365Adapter(CMMSAdapter):
    """
    Microsoft Dynamics 365 adapter.

    Requires: requests, msal (for auth)

    Configuration:
        {
            "tenant_id": "your-tenant-id",
            "client_id": "your-app-client-id",
            "client_secret": "your-client-secret",
            "environment_url": "https://yourorg.crm.dynamics.com"
        }
    """

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.access_token: Optional[str] = None
        self.base_url: Optional[str] = None

    @property
    def name(self) -> str:
        return "dynamics365"

    @property
    def version(self) -> str:
        return "1.0.0"

    def connect(self, config: Dict[str, Any]) -> bool:
        """
        Connect to Dynamics 365 using OAuth2.

        Requires msal library for authentication.
        """
        self.config = config
        self.base_url = config.get("environment_url", "").rstrip("/")

        try:
            # Would use msal for real auth
            # from msal import ConfidentialClientApplication
            # app = ConfidentialClientApplication(...)
            # result = app.acquire_token_for_client(scopes=[...])
            # self.access_token = result["access_token"]

            logger.info(f"Dynamics365Adapter: Would connect to {self.base_url}")
            return True

        except Exception as e:
            logger.error(f"Dynamics365 connection failed: {e}")
            return False

    def disconnect(self) -> None:
        self.access_token = None

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "connected" if self.access_token else "disconnected",
            "environment": self.base_url,
        }

    def create_case(self, case: CMMSCase) -> str:
        """
        Create case in Dynamics 365.

        Maps to: POST /api/data/v9.2/incidents
        """
        # Would make API call
        # response = requests.post(
        #     f"{self.base_url}/api/data/v9.2/incidents",
        #     headers={"Authorization": f"Bearer {self.access_token}"},
        #     json={
        #         "title": case.title,
        #         "description": case.description,
        #         "ticketnumber": case.reference,
        #         ...
        #     }
        # )

        logger.info(f"Dynamics365: Would create case {case.reference}")
        return f"dynamics_{case.id}"

    def get_case(self, case_id: str) -> Optional[CMMSCase]:
        """GET /api/data/v9.2/incidents({case_id})"""
        logger.info(f"Dynamics365: Would get case {case_id}")
        return None  # Would return mapped case

    def update_case(self, case: CMMSCase) -> bool:
        """PATCH /api/data/v9.2/incidents({case_id})"""
        logger.info(f"Dynamics365: Would update case {case.id}")
        return True

    def delete_case(self, case_id: str) -> bool:
        """DELETE /api/data/v9.2/incidents({case_id})"""
        logger.info(f"Dynamics365: Would delete case {case_id}")
        return True

    def search_cases(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[CMMSCase]:
        """GET /api/data/v9.2/incidents?$filter=contains(title,'{query}')"""
        logger.info(f"Dynamics365: Would search for '{query}'")
        return []

    def transition_case(
        self,
        case_id: str,
        action: WorkflowAction,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Use Dynamics workflow actions."""
        logger.info(f"Dynamics365: Would transition {case_id} with {action}")
        return True

    def get_available_actions(self, case_id: str) -> List[WorkflowAction]:
        return [WorkflowAction.SUBMIT, WorkflowAction.COMPLETE]

    def add_document(self, document: CMMSDocument, content: bytes) -> str:
        """POST to SharePoint or Dynamics annotations."""
        logger.info(f"Dynamics365: Would upload document {document.name}")
        return f"dynamics_doc_{document.id}"

    def get_document(self, document_id: str) -> Optional[CMMSDocument]:
        return None

    def get_document_content(self, document_id: str) -> Optional[bytes]:
        return None

    def list_documents(self, case_id: str) -> List[CMMSDocument]:
        return []

    def log_event(self, event: CMMSEvent) -> str:
        """Log to Dynamics audit."""
        return f"dynamics_evt_{event.id}"

    def get_case_history(self, case_id: str) -> List[CMMSEvent]:
        return []


# =============================================================================
# EXAMPLE ADAPTER: ALFRESCO (Skeleton)
# =============================================================================


class AlfrescoAdapter(CMMSAdapter):
    """
    Alfresco Process Services / Content Services adapter.

    Configuration:
        {
            "base_url": "https://your-alfresco.com",
            "username": "admin",
            "password": "password",
            "process_definition_key": "family-law-case"
        }
    """

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.session_cookie: Optional[str] = None

    @property
    def name(self) -> str:
        return "alfresco"

    @property
    def version(self) -> str:
        return "1.0.0"

    def connect(self, config: Dict[str, Any]) -> bool:
        self.config = config
        logger.info(f"Alfresco: Would connect to {config.get('base_url')}")
        return True

    def disconnect(self) -> None:
        self.session_cookie = None

    def health_check(self) -> Dict[str, Any]:
        return {"status": "skeleton", "adapter": "alfresco"}

    def create_case(self, case: CMMSCase) -> str:
        """Start Alfresco process instance."""
        # POST /activiti-app/api/enterprise/process-instances
        logger.info(f"Alfresco: Would start process for {case.reference}")
        return f"alfresco_{case.id}"

    def get_case(self, case_id: str) -> Optional[CMMSCase]:
        return None

    def update_case(self, case: CMMSCase) -> bool:
        return True

    def delete_case(self, case_id: str) -> bool:
        return True

    def search_cases(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[CMMSCase]:
        return []

    def transition_case(
        self,
        case_id: str,
        action: WorkflowAction,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Complete Alfresco task."""
        return True

    def get_available_actions(self, case_id: str) -> List[WorkflowAction]:
        return []

    def add_document(self, document: CMMSDocument, content: bytes) -> str:
        """Upload to Alfresco Content Services."""
        return f"alfresco_doc_{document.id}"

    def get_document(self, document_id: str) -> Optional[CMMSDocument]:
        return None

    def get_document_content(self, document_id: str) -> Optional[bytes]:
        return None

    def list_documents(self, case_id: str) -> List[CMMSDocument]:
        return []

    def log_event(self, event: CMMSEvent) -> str:
        return f"alfresco_evt_{event.id}"

    def get_case_history(self, case_id: str) -> List[CMMSEvent]:
        return []


# =============================================================================
# ADAPTER REGISTRY
# =============================================================================


class CMMSRegistry:
    """
    Registry of available CMMS adapters.

    Example:
        registry = CMMSRegistry()
        adapter = registry.get_adapter("dynamics365")
        adapter.connect(config)
    """

    _adapters: Dict[str, type] = {
        "local": LocalCMMSAdapter,
        "dynamics365": Dynamics365Adapter,
        "alfresco": AlfrescoAdapter,
    }

    @classmethod
    def register(cls, name: str, adapter_class: type) -> None:
        """Register a custom adapter."""
        cls._adapters[name] = adapter_class

    @classmethod
    def get_adapter(cls, name: str) -> CMMSAdapter:
        """Get an adapter instance by name."""
        if name not in cls._adapters:
            raise ValueError(
                f"Unknown CMMS adapter: {name}. Available: {list(cls._adapters.keys())}"
            )
        return cls._adapters[name]()

    @classmethod
    def list_adapters(cls) -> List[str]:
        """List available adapters."""
        return list(cls._adapters.keys())


# =============================================================================
# RAG INTEGRATION HELPER
# =============================================================================


class CMMSRAGBridge:
    """
    Bridge between CMMS and RAG pipeline.

    Enables:
    - Loading case documents into RAG knowledge base
    - Semantic search across case history
    - Context injection from case data

    Example:
        bridge = CMMSRAGBridge(adapter, vector_store)
        bridge.index_case_documents(case_id)
        context = bridge.get_case_context(case_id, "parenting arrangements")
    """

    def __init__(
        self,
        adapter: CMMSAdapter,
        vector_store: Optional[Any] = None,
        embedding_model: Optional[Any] = None,
    ):
        self.adapter = adapter
        self.vector_store = vector_store
        self.embedding_model = embedding_model

    def index_case_documents(self, case_id: str) -> int:
        """
        Index all documents from a case into the RAG vector store.

        Returns:
            Number of documents indexed
        """
        documents = self.adapter.list_documents(case_id)
        indexed = 0

        for doc in documents:
            content = self.adapter.get_document_content(doc.id)
            if content and self.vector_store:
                # Would add to vector store
                # self.vector_store.add_texts([content.decode()], metadatas=[{...}])
                indexed += 1

        logger.info(f"Indexed {indexed} documents from case {case_id}")
        return indexed

    def get_case_context(
        self,
        case_id: str,
        query: str,
        top_k: int = 5,
    ) -> str:
        """
        Get relevant context from case for RAG injection.

        Combines:
        - Case metadata
        - Relevant document snippets
        - Case history highlights
        """
        case = self.adapter.get_case(case_id)
        if not case:
            return ""

        context_parts = [
            f"Case: {case.reference}",
            f"Type: {case.case_type} - {case.sub_type}",
            f"Status: {case.status.value}",
            f"Phase: {case.phase}",
        ]

        # Add relevant documents from vector search
        if self.vector_store:
            # results = self.vector_store.similarity_search(query, k=top_k)
            # for result in results:
            #     context_parts.append(result.page_content[:500])
            pass

        return "\n".join(context_parts)

    def build_case_summary(self, case_id: str) -> str:
        """Build a VoiceOver-friendly case summary."""
        case = self.adapter.get_case(case_id)
        if not case:
            return "Case not found."

        history = self.adapter.get_case_history(case_id)
        docs = self.adapter.list_documents(case_id)

        summary = f"""
Case Summary: {case.reference}

Status: {case.status.value.replace('_', ' ').title()}
Phase: {case.phase or 'Not set'}
Type: {case.case_type.replace('_', ' ').title()}

Documents: {len(docs)} on file
History: {len(history)} events recorded

{case.description[:500] if case.description else 'No description.'}
"""
        return summary.strip()


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("CMMS Adapter Layer - Case Management Integration")
    print("=" * 50)

    # Use local adapter for demo
    adapter = CMMSRegistry.get_adapter("local")
    adapter.connect({})

    # Create a test case
    case = CMMSCase(
        id="case_001",
        reference="SMITH-2024-001",
        case_type="family_law",
        sub_type="parenting",
        title="Smith Parenting Matter",
        description="Parenting arrangements for two children",
    )

    # CRUD operations
    adapter.create_case(case)
    print(f"Created case: {case.reference}")

    # Workflow transition
    adapter.transition_case("case_001", WorkflowAction.SUBMIT)
    adapter.transition_case("case_001", WorkflowAction.ASSIGN)

    retrieved = adapter.get_case("case_001")
    print(f"Case status: {retrieved.status.value}")

    # Check available actions
    actions = adapter.get_available_actions("case_001")
    print(f"Available actions: {[a.value for a in actions]}")

    # View history
    history = adapter.get_case_history("case_001")
    print(f"Case history: {len(history)} events")

    # List available adapters
    print(f"\nAvailable adapters: {CMMSRegistry.list_adapters()}")

    # Health check
    print(f"Health: {adapter.health_check()}")
