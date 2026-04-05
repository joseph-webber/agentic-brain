#!/usr/bin/env python3
"""
Multi-Domain Agentic Brain Architecture
========================================

Complex enterprise architecture showing how multiple agentic-brain instances
operate across different organizations, each with their own:
- Case management systems (SAP, Dynamics, LEAP, etc.)
- Deployment modes (on-premise, cloud, edge)
- Security domains and trust levels
- Data sovereignty requirements

DEPLOYMENT SCENARIOS
====================

1. FEDERAL COURT (On-Premise)
   - SAP Case Manager (ABAP/ERP)
   - High security government network
   - Strict data sovereignty
   - Edge devices for remote registries

2. LAW FIRMS (Cloud/On-Premise Mix)
   - Dynamics 365, LEAP, Clio, Actionstep
   - Client-attorney privilege protection
   - Cloud for small firms, on-prem for large

3. LEGAL AID (Cloud)
   - High volume, limited resources
   - Needs cost-effective cloud deployment
   - Integration with court systems

4. SUPPORT SERVICES (Edge/Cloud)
   - DV shelters, social workers
   - Mobile/edge deployment
   - High sensitivity data

CROSS-DOMAIN COMMUNICATION
==========================

Each domain has its own agentic-brain instance. They communicate via:
- Secure API gateways
- Federated identity (SAML/OAuth)
- Encrypted message queues
- Document exchange standards (eFiling)

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

logger = logging.getLogger(__name__)


# =============================================================================
# DEPLOYMENT MODES
# =============================================================================


class DeploymentMode(Enum):
    """Where the agentic-brain instance runs."""

    ON_PREMISE = "on_premise"  # Local servers, full control
    CLOUD = "cloud"  # AWS/Azure/GCP
    HYBRID = "hybrid"  # Mix of on-prem and cloud
    EDGE = "edge"  # Mobile/remote devices
    SOVEREIGN_CLOUD = "sovereign"  # Government-approved cloud (e.g., Azure Gov)


class SecurityLevel(Enum):
    """Security classification of the domain."""

    PUBLIC = "public"  # General information
    INTERNAL = "internal"  # Organization internal
    CONFIDENTIAL = "confidential"  # Client/case data
    RESTRICTED = "restricted"  # Sensitive (DV, children)
    CLASSIFIED = "classified"  # Government restricted


class TrustLevel(Enum):
    """Trust relationship between domains."""

    UNTRUSTED = 0  # No data sharing
    VERIFIED = 1  # Identity verified, limited sharing
    TRUSTED = 2  # Established relationship
    PRIVILEGED = 3  # Full access (e.g., same organization)
    FEDERATED = 4  # Cross-organization trust agreement


# =============================================================================
# DOMAIN DEFINITIONS
# =============================================================================


@dataclass
class Domain:
    """
    A domain represents an organization or system boundary.
    Each domain runs its own agentic-brain instance.
    """

    domain_id: str
    name: str
    organization: str
    deployment_mode: DeploymentMode
    security_level: SecurityLevel

    # Case management system
    cmms_type: str  # "sap", "dynamics", "leap", "salesforce", etc.
    cmms_version: Optional[str] = None

    # Network configuration
    api_endpoint: Optional[str] = None
    auth_provider: Optional[str] = None  # "saml", "oauth2", "api_key"

    # Data sovereignty
    data_jurisdiction: str = "AU"  # ISO country code
    data_residency: Optional[str] = None  # Specific region

    # Trust relationships with other domains
    trusted_domains: Dict[str, TrustLevel] = field(default_factory=dict)

    # Capabilities this domain exposes
    capabilities: Set[str] = field(default_factory=set)

    def can_share_with(self, other_domain_id: str, data_type: str) -> bool:
        """Check if this domain can share data type with another domain."""
        trust = self.trusted_domains.get(other_domain_id, TrustLevel.UNTRUSTED)

        # Define what can be shared at each trust level
        sharing_rules = {
            TrustLevel.UNTRUSTED: set(),
            TrustLevel.VERIFIED: {"case_reference", "hearing_dates"},
            TrustLevel.TRUSTED: {
                "case_reference",
                "hearing_dates",
                "party_names",
                "orders",
            },
            TrustLevel.PRIVILEGED: {
                "case_reference",
                "hearing_dates",
                "party_names",
                "orders",
                "documents",
                "notes",
            },
            TrustLevel.FEDERATED: {
                "case_reference",
                "hearing_dates",
                "party_names",
                "orders",
                "documents",
                "notes",
                "sealed_documents",
            },
        }

        allowed = sharing_rules.get(trust, set())
        return data_type in allowed


# =============================================================================
# PRE-CONFIGURED DOMAINS FOR FAMILY LAW
# =============================================================================

# Federal Circuit and Family Court of Australia
FCFCOA_DOMAIN = Domain(
    domain_id="fcfcoa",
    name="Federal Circuit and Family Court",
    organization="Commonwealth of Australia",
    deployment_mode=DeploymentMode.SOVEREIGN_CLOUD,
    security_level=SecurityLevel.RESTRICTED,
    cmms_type="sap_case_manager",
    cmms_version="7.52",  # SAP NetWeaver version
    api_endpoint="https://api.comcourts.gov.au",
    auth_provider="saml",  # Government SAML federation
    data_jurisdiction="AU",
    data_residency="australia-southeast1",  # Sydney region
    capabilities={
        "efiling",
        "case_lookup",
        "hearing_schedule",
        "orders_registry",
        "subpoena_management",
    },
)

# State Family Court (e.g., WA Family Court)
STATE_COURT_DOMAIN = Domain(
    domain_id="wa_family_court",
    name="Family Court of Western Australia",
    organization="Government of Western Australia",
    deployment_mode=DeploymentMode.ON_PREMISE,
    security_level=SecurityLevel.RESTRICTED,
    cmms_type="dynamics_365",
    cmms_version="9.2",
    api_endpoint="https://api.justice.wa.gov.au",
    auth_provider="oauth2",
    data_jurisdiction="AU",
    data_residency="australia-west",
    capabilities={
        "efiling",
        "case_lookup",
        "hearing_schedule",
    },
)

# Legal Aid organization
LEGAL_AID_DOMAIN = Domain(
    domain_id="legal_aid_nsw",
    name="Legal Aid NSW",
    organization="Legal Aid NSW",
    deployment_mode=DeploymentMode.CLOUD,
    security_level=SecurityLevel.CONFIDENTIAL,
    cmms_type="salesforce",
    cmms_version="Spring '24",
    api_endpoint="https://legalaid-nsw.my.salesforce.com/api",
    auth_provider="oauth2",
    data_jurisdiction="AU",
    capabilities={
        "client_intake",
        "case_management",
        "billing",
        "grants_assessment",
        "duty_lawyer_roster",
    },
)

# Large family law firm
LAW_FIRM_DOMAIN = Domain(
    domain_id="familylaw_com_au",
    name="FamilyLaw.com.au",
    organization="FamilyLaw.com.au Pty Ltd",
    deployment_mode=DeploymentMode.HYBRID,
    security_level=SecurityLevel.CONFIDENTIAL,
    cmms_type="leap",
    cmms_version="2024.1",
    api_endpoint="https://api.familylaw.com.au",
    auth_provider="oauth2",
    data_jurisdiction="AU",
    capabilities={
        "client_management",
        "matter_management",
        "billing",
        "document_automation",
        "trust_accounting",
    },
)

# Small law firm (cloud-first)
SMALL_FIRM_DOMAIN = Domain(
    domain_id="smith_family_law",
    name="Smith Family Law",
    organization="Smith Family Law Pty Ltd",
    deployment_mode=DeploymentMode.CLOUD,
    security_level=SecurityLevel.CONFIDENTIAL,
    cmms_type="clio",
    cmms_version="2024",
    api_endpoint="https://app.clio.com/api/v4",
    auth_provider="oauth2",
    data_jurisdiction="AU",
    capabilities={
        "matter_management",
        "billing",
        "client_portal",
    },
)

# Domestic violence support service
DV_SUPPORT_DOMAIN = Domain(
    domain_id="dv_connect",
    name="DV Connect Queensland",
    organization="DV Connect",
    deployment_mode=DeploymentMode.EDGE,  # Mobile workers
    security_level=SecurityLevel.RESTRICTED,
    cmms_type="custom",
    api_endpoint="https://secure.dvconnect.org/api",
    auth_provider="oauth2",
    data_jurisdiction="AU",
    capabilities={
        "safety_planning",
        "risk_assessment",
        "referrals",
        "crisis_support",
        "accommodation",
    },
)

# Independent Children's Lawyer panel
ICL_PANEL_DOMAIN = Domain(
    domain_id="icl_panel_nsw",
    name="ICL Panel NSW",
    organization="Legal Aid NSW ICL Panel",
    deployment_mode=DeploymentMode.CLOUD,
    security_level=SecurityLevel.RESTRICTED,
    cmms_type="actionstep",
    api_endpoint="https://ap-southeast-2.actionstep.com/api",
    auth_provider="oauth2",
    data_jurisdiction="AU",
    capabilities={
        "icl_appointments",
        "child_interviews",
        "family_reports",
    },
)


# =============================================================================
# SAP CASE MANAGER ADAPTER (Government/Enterprise)
# =============================================================================


@dataclass
class SAPCaseManagerConfig:
    """
    Configuration for SAP Case Manager integration.

    SAP Case Manager (part of SAP ERP) is used by:
    - Federal courts
    - State government agencies
    - Large enterprises

    Uses ABAP (Advanced Business Application Programming) on
    SAP NetWeaver platform.
    """

    # Connection
    sap_host: str
    sap_client: str  # SAP client number (e.g., "100")
    sap_system_number: str  # System number (e.g., "00")

    # Authentication
    auth_method: str = "saml"  # "basic", "saml", "x509"
    saml_idp: Optional[str] = None

    # RFC/BAPI configuration
    rfc_destination: str = "SAP_DEFAULT"

    # Case Manager specific
    case_type: str = "ZFAM"  # Custom case type for family law
    workflow_template: str = "WS91000001"

    # Document management
    content_repository: str = "Z1"  # SAP Content Repository
    archive_link_enabled: bool = True


class SAPCaseManagerAdapter:
    """
    Adapter for SAP Case Manager.

    Implements standard CMMS interface using SAP RFC/BAPI calls.

    SAP Case Manager Structure:
    - Case (SCASE) -> Matter
    - Case Documents -> Attachments via ArchiveLink
    - Workflow (SAP Business Workflow) -> Case phases
    - Business Partners -> Parties

    ABAP Function Modules used:
    - BAPI_CASE_CREATE
    - BAPI_CASE_CHANGE
    - BAPI_CASE_GETDETAIL
    - BAPI_DOCUMENT_CREATE
    - SAP_WAPI_* for workflow

    Example Usage:
        config = SAPCaseManagerConfig(
            sap_host="sapapp.courts.gov.au",
            sap_client="100",
            sap_system_number="00",
            saml_idp="https://idp.courts.gov.au",
        )
        adapter = SAPCaseManagerAdapter(config)
        case = adapter.get_case("FAM-2024-001234")
    """

    def __init__(self, config: SAPCaseManagerConfig):
        self.config = config
        self._connection = None

    def connect(self) -> bool:
        """
        Establish connection to SAP system.

        In production, this would use:
        - PyRFC for RFC connections
        - SAP SAML2 for authentication
        - SAP NetWeaver Gateway for REST APIs
        """
        logger.info(f"Connecting to SAP Case Manager at {self.config.sap_host}")

        # Production code would use pyrfc:
        # from pyrfc import Connection
        # self._connection = Connection(
        #     ashost=self.config.sap_host,
        #     sysnr=self.config.sap_system_number,
        #     client=self.config.sap_client,
        #     # ... auth params
        # )

        # For demo, simulate connection
        self._connection = {"connected": True, "host": self.config.sap_host}
        logger.info("SAP Case Manager connection established")
        return True

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve case from SAP Case Manager.

        Calls BAPI_CASE_GETDETAIL function module.
        """
        if not self._connection:
            self.connect()

        # Production: self._connection.call('BAPI_CASE_GETDETAIL', ...)
        logger.info(f"Fetching case {case_id} from SAP")

        # Simulated response matching SAP structure
        return {
            "CASE_GUID": case_id,
            "CASE_ID": case_id,
            "CASE_TYPE": self.config.case_type,
            "DESCRIPTION": "Family Law Matter",
            "STATUS": "E0002",  # SAP status code
            "STATUS_TEXT": "In Progress",
            "CREATED_AT": "20240315",
            "CREATED_BY": "SYSTEM",
            "CHANGED_AT": "20240520",
            "CHANGED_BY": "REGISTRAR1",
            # Parties (Business Partners)
            "PARTIES": [
                {"PARTNER": "BP001", "ROLE": "APPLICANT", "NAME": "[Applicant Name]"},
                {"PARTNER": "BP002", "ROLE": "RESPONDENT", "NAME": "[Respondent Name]"},
            ],
            # Documents via ArchiveLink
            "DOCUMENTS": [
                {
                    "DOC_ID": "DOC001",
                    "DOC_TYPE": "INIT_APP",
                    "DESCRIPTION": "Initiating Application",
                },
            ],
            # Workflow status
            "WORKFLOW": {
                "WI_ID": "WI12345",
                "TASK": "TS91000001",
                "STATUS": "READY",
            },
        }

    def create_case(
        self,
        case_type: str,
        description: str,
        parties: List[Dict[str, str]],
    ) -> Optional[str]:
        """
        Create new case in SAP Case Manager.

        Calls BAPI_CASE_CREATE function module.
        """
        if not self._connection:
            self.connect()

        # Production: self._connection.call('BAPI_CASE_CREATE', ...)
        logger.info(f"Creating new {case_type} case in SAP")

        # Generate case ID (SAP would do this)
        case_id = f"FAM-{datetime.now().year}-{hash(description) % 100000:05d}"

        return case_id

    def update_case_status(self, case_id: str, new_status: str) -> bool:
        """
        Update case status via SAP workflow.

        Triggers SAP Business Workflow transition.
        """
        if not self._connection:
            self.connect()

        logger.info(f"Updating case {case_id} status to {new_status}")

        # Production: Trigger workflow via SAP_WAPI_WORKITEM_COMPLETE
        return True

    def get_hearing_schedule(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Get hearing schedule from SAP.

        Reads from custom Z-table for court scheduling.
        """
        if not self._connection:
            self.connect()

        # Production: RFC call to custom function module
        return [
            {
                "HEARING_ID": "H001",
                "CASE_ID": case_id,
                "HEARING_TYPE": "INTERIM",
                "DATE": "20240601",
                "TIME": "100000",  # SAP time format
                "LOCATION": "Sydney Registry",
                "JUDICIAL_OFFICER": "Registrar Smith",
            }
        ]

    def file_document(
        self,
        case_id: str,
        document_type: str,
        document_content: bytes,
        filename: str,
    ) -> Optional[str]:
        """
        File document via SAP ArchiveLink.

        Uses Content Repository integration.
        """
        if not self._connection:
            self.connect()

        logger.info(f"Filing {document_type} to case {case_id}")

        # Production: BAPI_DOCUMENT_CREATE + ArchiveLink
        doc_id = f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return doc_id


# =============================================================================
# FEDERATED BRAIN NETWORK
# =============================================================================


class BrainMessage:
    """
    Secure message between agentic-brain instances.

    Messages are:
    - Encrypted in transit
    - Signed by source domain
    - Contain routing information
    - Respect data sovereignty
    """

    def __init__(
        self,
        source_domain: str,
        target_domain: str,
        message_type: str,
        payload: Dict[str, Any],
        security_level: SecurityLevel = SecurityLevel.INTERNAL,
    ):
        self.message_id = hashlib.sha256(
            f"{source_domain}{target_domain}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        self.source_domain = source_domain
        self.target_domain = target_domain
        self.message_type = message_type
        self.payload = payload
        self.security_level = security_level

        self.timestamp = datetime.now()
        self.signature: Optional[str] = None

    def sign(self, private_key: str) -> None:
        """Sign message with domain's private key."""
        # Production: Use proper cryptographic signing
        content = json.dumps(
            {
                "id": self.message_id,
                "source": self.source_domain,
                "target": self.target_domain,
                "type": self.message_type,
                "payload": self.payload,
            },
            sort_keys=True,
        )

        self.signature = hashlib.sha256(f"{content}{private_key}".encode()).hexdigest()

    def verify(self, public_key: str) -> bool:
        """Verify message signature."""
        # Production: Use proper cryptographic verification
        return self.signature is not None


class FederatedBrainNetwork:
    """
    Network of agentic-brain instances across organizations.

    Enables:
    - Cross-domain case queries
    - Secure document exchange
    - Hearing schedule coordination
    - Federated authentication

    Example Architecture:

        ┌─────────────────┐     ┌─────────────────┐
        │   FCFCOA        │     │   Legal Aid     │
        │  (SAP CM)       │◄───►│  (Salesforce)   │
        │  Agentic-Brain  │     │  Agentic-Brain  │
        └────────┬────────┘     └────────┬────────┘
                 │                       │
                 │    Federation Hub     │
                 │    (API Gateway)      │
                 │                       │
        ┌────────┴────────┐     ┌────────┴────────┐
        │   Law Firm      │     │   DV Support    │
        │   (LEAP)        │     │   (Edge)        │
        │  Agentic-Brain  │     │  Agentic-Brain  │
        └─────────────────┘     └─────────────────┘
    """

    def __init__(self):
        self.domains: Dict[str, Domain] = {}
        self.message_queue: List[BrainMessage] = []
        self._routing_table: Dict[str, str] = {}  # domain -> endpoint

    def register_domain(self, domain: Domain) -> None:
        """Register a domain in the federation."""
        self.domains[domain.domain_id] = domain
        if domain.api_endpoint:
            self._routing_table[domain.domain_id] = domain.api_endpoint

        logger.info(f"Domain {domain.name} registered in federation")

    def establish_trust(
        self,
        domain_a: str,
        domain_b: str,
        trust_level: TrustLevel,
        bidirectional: bool = True,
    ) -> None:
        """Establish trust relationship between domains."""
        if domain_a in self.domains:
            self.domains[domain_a].trusted_domains[domain_b] = trust_level

        if bidirectional and domain_b in self.domains:
            self.domains[domain_b].trusted_domains[domain_a] = trust_level

        logger.info(
            f"Trust established: {domain_a} <-> {domain_b} at level {trust_level.name}"
        )

    def send_message(self, message: BrainMessage) -> bool:
        """
        Send message between domains.

        Validates:
        1. Source and target exist
        2. Trust relationship allows this message type
        3. Data sovereignty is respected
        """
        source = self.domains.get(message.source_domain)
        target = self.domains.get(message.target_domain)

        if not source or not target:
            logger.error(
                f"Unknown domain in message: {message.source_domain} -> {message.target_domain}"
            )
            return False

        # Check trust
        if not source.can_share_with(message.target_domain, message.message_type):
            logger.warning(
                f"Trust violation: {source.name} cannot share {message.message_type} "
                f"with {target.name}"
            )
            return False

        # Check data sovereignty
        if source.data_jurisdiction != target.data_jurisdiction:
            if message.security_level.value >= SecurityLevel.RESTRICTED.value:
                logger.warning(
                    f"Data sovereignty block: Cannot send {message.security_level.name} "
                    f"data from {source.data_jurisdiction} to {target.data_jurisdiction}"
                )
                return False

        # Queue message for delivery
        self.message_queue.append(message)
        logger.info(
            f"Message queued: {message.message_id} " f"({source.name} -> {target.name})"
        )

        return True

    def route_query(
        self,
        query: str,
        source_domain: str,
        target_capability: str,
    ) -> Optional[str]:
        """
        Route a query to the domain with required capability.

        Example: Route "case status" query to court domain that has
        "case_lookup" capability.
        """
        for domain_id, domain in self.domains.items():
            if target_capability in domain.capabilities:
                # Check if source can communicate with this domain
                source = self.domains.get(source_domain)
                if source and source.can_share_with(domain_id, "case_reference"):
                    return domain_id

        logger.warning(f"No reachable domain with capability: {target_capability}")
        return None


# =============================================================================
# EDGE DEPLOYMENT CONFIGURATION
# =============================================================================


@dataclass
class EdgeDeploymentConfig:
    """
    Configuration for edge deployment of agentic-brain.

    Edge deployments are used by:
    - Mobile social workers
    - Remote court registries
    - DV support workers in the field
    - Lawyers visiting clients

    Features:
    - Offline-first with sync
    - Lightweight RAG (local embeddings)
    - Secure local storage
    - Intermittent connectivity handling
    """

    # Device
    device_id: str
    device_type: str  # "mobile", "laptop", "tablet"

    # Storage
    local_db_path: str = "~/.agentic-brain/edge.db"
    max_cache_size_mb: int = 500

    # Sync
    sync_endpoint: str = ""
    sync_interval_minutes: int = 15
    offline_capable: bool = True

    # Security
    encryption_enabled: bool = True
    biometric_auth: bool = True
    auto_wipe_days: int = 30  # Wipe if not synced

    # RAG
    local_embedding_model: str = "all-MiniLM-L6-v2"
    max_documents_cached: int = 1000

    # LLM
    local_llm_model: str = "phi-3-mini"  # Small model for edge
    fallback_to_cloud: bool = True


class EdgeBrain:
    """
    Edge-deployed agentic-brain instance.

    Optimized for:
    - Low connectivity environments
    - Mobile devices
    - Sensitive field work (DV support, etc.)
    """

    def __init__(self, config: EdgeDeploymentConfig, parent_domain: Domain):
        self.config = config
        self.parent_domain = parent_domain
        self.is_online = False
        self._pending_sync: List[Dict[str, Any]] = []

    def check_connectivity(self) -> bool:
        """Check if we can reach the parent domain."""
        # Production: Actually check network connectivity
        return self.is_online

    def query_local(self, query: str) -> Optional[str]:
        """
        Answer query using local RAG and LLM.

        Used when offline or for sensitive queries.
        """
        logger.info(f"Edge query (local): {query[:50]}...")

        # Production: Use local embedding model + local LLM
        return "Local response based on cached knowledge..."

    def query_with_sync(self, query: str) -> Optional[str]:
        """
        Query with cloud sync if connected.
        """
        if self.check_connectivity():
            # Sync pending changes first
            self._sync_pending()

            # Then query cloud
            logger.info(f"Edge query (cloud): {query[:50]}...")
            return "Cloud-enhanced response..."
        else:
            return self.query_local(query)

    def record_interaction(
        self,
        interaction_type: str,
        content: Dict[str, Any],
    ) -> str:
        """
        Record interaction locally, queue for sync.
        """
        interaction_id = hashlib.sha256(
            f"{self.config.device_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        self._pending_sync.append(
            {
                "id": interaction_id,
                "type": interaction_type,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "device": self.config.device_id,
            }
        )

        logger.info(f"Interaction recorded locally: {interaction_id}")
        return interaction_id

    def _sync_pending(self) -> int:
        """Sync pending interactions to cloud."""
        if not self._pending_sync:
            return 0

        count = len(self._pending_sync)
        logger.info(
            f"Syncing {count} pending interactions to {self.parent_domain.name}"
        )

        # Production: Actually sync to parent domain
        self._pending_sync.clear()

        return count


# =============================================================================
# EXAMPLE: SETTING UP THE FAMILY LAW FEDERATION
# =============================================================================


def setup_family_law_federation() -> FederatedBrainNetwork:
    """
    Set up the complete family law federation.

    This creates the network of agentic-brain instances
    with appropriate trust relationships.
    """
    network = FederatedBrainNetwork()

    # Register all domains
    network.register_domain(FCFCOA_DOMAIN)
    network.register_domain(STATE_COURT_DOMAIN)
    network.register_domain(LEGAL_AID_DOMAIN)
    network.register_domain(LAW_FIRM_DOMAIN)
    network.register_domain(SMALL_FIRM_DOMAIN)
    network.register_domain(DV_SUPPORT_DOMAIN)
    network.register_domain(ICL_PANEL_DOMAIN)

    # Establish trust relationships

    # Courts trust each other at highest level
    network.establish_trust("fcfcoa", "wa_family_court", TrustLevel.FEDERATED)

    # Legal Aid has trust with courts
    network.establish_trust("fcfcoa", "legal_aid_nsw", TrustLevel.TRUSTED)
    network.establish_trust("wa_family_court", "legal_aid_nsw", TrustLevel.TRUSTED)

    # Law firms have verified status with courts (for eFiling)
    network.establish_trust("fcfcoa", "familylaw_com_au", TrustLevel.VERIFIED)
    network.establish_trust("fcfcoa", "smith_family_law", TrustLevel.VERIFIED)

    # ICL panel trusted by courts
    network.establish_trust("fcfcoa", "icl_panel_nsw", TrustLevel.TRUSTED)

    # DV support has limited trust (sensitive data)
    network.establish_trust("legal_aid_nsw", "dv_connect", TrustLevel.TRUSTED)
    network.establish_trust("icl_panel_nsw", "dv_connect", TrustLevel.VERIFIED)

    logger.info("Family Law Federation established with 7 domains")

    return network


def demonstrate_cross_domain_query():
    """Demonstrate a cross-domain query."""
    network = setup_family_law_federation()

    # Law firm queries court for case status
    print("=== Cross-Domain Query Demo ===\n")

    # Find which domain can handle case lookup
    target = network.route_query(
        query="What is the status of case FAM-2024-001234?",
        source_domain="familylaw_com_au",
        target_capability="case_lookup",
    )

    print(f"Query routed to: {target}")

    if target:
        # Create message
        msg = BrainMessage(
            source_domain="familylaw_com_au",
            target_domain=target,
            message_type="case_reference",
            payload={"case_id": "FAM-2024-001234", "query": "status"},
        )

        # Send message
        success = network.send_message(msg)
        print(f"Message sent successfully: {success}")


if __name__ == "__main__":
    # Demo the architecture
    demonstrate_cross_domain_query()

    print("\n=== SAP Case Manager Demo ===\n")

    # Demo SAP integration
    sap_config = SAPCaseManagerConfig(
        sap_host="sapapp.courts.gov.au",
        sap_client="100",
        sap_system_number="00",
        saml_idp="https://idp.courts.gov.au",
    )

    sap_adapter = SAPCaseManagerAdapter(sap_config)
    case = sap_adapter.get_case("FAM-2024-001234")

    print(f"Case ID: {case['CASE_ID']}")
    print(f"Status: {case['STATUS_TEXT']}")
    print(f"Parties: {len(case['PARTIES'])}")
    print(f"Documents: {len(case['DOCUMENTS'])}")
