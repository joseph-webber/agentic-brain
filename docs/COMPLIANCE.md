# Compliance Framework

<div align="center">

[![HIPAA](https://img.shields.io/badge/HIPAA-Ready-4CAF50?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0tMiAxNWwtNS01IDEuNDEtMS40MUwxMCAxNC4xN2w3LjU5LTcuNTlMMTkgOGwtOSA5eiIvPjwvc3ZnPg==)](./COMPLIANCE.md)
[![GDPR](https://img.shields.io/badge/GDPR-Compliant-0052CC?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0tMiAxNWwtNS01IDEuNDEtMS40MUwxMCAxNC4xN2w3LjU5LTcuNTlMMTkgOGwtOSA5eiIvPjwvc3ZnPg==)](./COMPLIANCE.md)
[![SOC2](https://img.shields.io/badge/SOC_2-Type_II-FF6B35?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0tMiAxNWwtNS01IDEuNDEtMS40MUwxMCAxNC4xN2w3LjU5LTcuNTlMMTkgOGwtOSA5eiIvPjwvc3ZnPg==)](./COMPLIANCE.md)
[![ISO27001](https://img.shields.io/badge/ISO_27001-Aligned-003366?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0tMiAxNWwtNS01IDEuNDEtMS40MUwxMCAxNC4xN2w3LjU5LTcuNTlMMTkgOGwtOSA5eiIvPjwvc3ZnPg==)](./COMPLIANCE.md)

**Enterprise-Grade Regulatory Compliance**

*Banks trust us. Hospitals trust us. Governments trust us.*

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Compliance Modes](#compliance-modes)
- [HIPAA (Healthcare)](#hipaa-healthcare)
- [GDPR (European Data Protection)](#gdpr-european-data-protection)
- [SOX (Financial)](#sox-financial-reporting)
- [APRA CPS 234 (Australian Banking)](#apra-cps-234-australian-banking)
- [SOC 2 Type II](#soc-2-type-ii)
- [ISO 27001](#iso-27001)
- [PCI-DSS (Payment Cards)](#pci-dss-payment-cards)
- [FedRAMP (US Government)](#fedramp-us-government)
- [Universal Features](#universal-compliance-features)
- [Data Handling](#data-handling)
- [Audit & Reporting](#audit--reporting)
- [Certification Status](#certification-status)

---

## Overview

Agentic Brain implements **compliance-as-code** — regulatory requirements are not afterthoughts but core architectural decisions. Each compliance mode activates specific controls, logging, and data handling policies automatically.

```bash
# Activate compliance mode with one command
ab mode switch medical    # HIPAA mode
ab mode switch banking    # SOX + PCI-DSS + APRA
ab mode switch government # FedRAMP + NIST
ab mode switch european   # GDPR mode
```

### Compliance Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPLIANCE LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   HIPAA      │  │    GDPR      │  │    SOX       │  │    APRA      │ │
│  │  Healthcare  │  │   Europe     │  │   Finance    │  │  AU Banking  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │                 │          │
│         ▼                 ▼                 ▼                 ▼          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                     UNIFIED CONTROL PLANE                          │  │
│  │  • Encryption (at-rest + in-transit)                              │  │
│  │  • Audit Logging (immutable, tamper-evident)                      │  │
│  │  • Access Control (RBAC + ABAC)                                   │  │
│  │  • Data Classification                                             │  │
│  │  • Retention Policies                                              │  │
│  │  • Geographic Controls                                             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Compliance Modes

### Quick Activation

| Mode | Command | Frameworks | Industries |
|------|---------|------------|------------|
| **Medical** | `ab mode switch medical` | HIPAA, HITECH, HL7 FHIR | Healthcare, Pharma, Biotech |
| **Banking** | `ab mode switch banking` | SOX, PCI-DSS, APRA, Basel III | Banking, Finance, Insurance |
| **European** | `ab mode switch european` | GDPR, ePrivacy | Any EU operations |
| **Government** | `ab mode switch government` | FedRAMP, NIST 800-53, ITAR | Federal, Defense, Intelligence |
| **Australian** | `ab mode switch apra` | APRA CPS 234, Privacy Act 1988 | Australian Financial Services |
| **Enterprise** | `ab mode switch enterprise` | SOC 2, ISO 27001 | SaaS, B2B, Enterprise |

### Mode Features Matrix

| Feature | Medical | Banking | European | Government | Enterprise |
|---------|---------|---------|----------|------------|------------|
| **PHI Handling** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **PII Encryption** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Consent Tracking** | ✅ | ⚠️ | ✅ | ❌ | ⚠️ |
| **Right to Erasure** | ⚠️ | ⚠️ | ✅ | ❌ | ⚠️ |
| **Financial Controls** | ❌ | ✅ | ⚠️ | ✅ | ⚠️ |
| **Air-Gap Support** | ⚠️ | ⚠️ | ❌ | ✅ | ❌ |
| **Data Locality** | ⚠️ | ✅ | ✅ | ✅ | ⚠️ |
| **Audit Logging** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Break-Glass Access** | ✅ | ✅ | ❌ | ✅ | ✅ |

✅ = Full Support | ⚠️ = Partial/Configurable | ❌ = Not Applicable

---

## HIPAA (Healthcare)

### Health Insurance Portability and Accountability Act

HIPAA compliance mode provides comprehensive protection for Protected Health Information (PHI).

```bash
ab mode switch medical
```

### HIPAA Controls

| Control | Implementation | Status |
|---------|----------------|--------|
| **Access Control (§164.312(a)(1))** | RBAC with minimum necessary principle | ✅ |
| **Audit Controls (§164.312(b))** | Immutable audit logs, 6-year retention | ✅ |
| **Integrity Controls (§164.312(c)(1))** | Cryptographic hashing, tamper detection | ✅ |
| **Transmission Security (§164.312(e)(1))** | TLS 1.3, certificate pinning | ✅ |
| **Encryption (§164.312(a)(2)(iv))** | AES-256-GCM at rest | ✅ |
| **Emergency Access (§164.312(a)(2)(ii))** | Break-glass with dual authorization | ✅ |
| **Automatic Logoff (§164.312(a)(2)(iii))** | Configurable session timeout | ✅ |
| **Unique User ID (§164.312(a)(2)(i))** | UUID-based identity tracking | ✅ |

### PHI Handling

```python
from agentic_brain.compliance import HIPAAMode

# Automatic PHI detection and protection
agent = Agent("medical-assistant", compliance_mode=HIPAAMode())

# PHI is automatically:
# - Detected using ML classifiers
# - Encrypted with patient-specific keys
# - Logged with access controls
# - Redacted from debug output
response = await agent.chat_async("Patient John Smith, DOB 1985-03-15, MRN 12345")
```

### Business Associate Agreement (BAA)

Agentic Brain can execute a BAA for enterprise deployments. Contact: compliance@agentic-brain.dev

### HIPAA Audit Report

```bash
# Generate HIPAA compliance report
ab compliance report --framework hipaa --output hipaa-audit.pdf

# Real-time PHI access monitoring
ab compliance monitor --phi --alert-threshold 100
```

---

## GDPR (European Data Protection)

### General Data Protection Regulation

Full GDPR compliance for organizations processing EU personal data.

```bash
ab mode switch european
```

### GDPR Articles Implementation

| Article | Requirement | Implementation |
|---------|-------------|----------------|
| **Art. 5** | Data Processing Principles | Lawful, fair, transparent processing |
| **Art. 6** | Lawfulness of Processing | Consent management system |
| **Art. 7** | Conditions for Consent | Granular, withdrawable consent |
| **Art. 13-14** | Transparency | Automated privacy notices |
| **Art. 15** | Right of Access | Self-service data export |
| **Art. 16** | Right to Rectification | In-place data correction |
| **Art. 17** | Right to Erasure | Cascading deletion system |
| **Art. 18** | Right to Restriction | Processing pause capability |
| **Art. 20** | Data Portability | JSON/XML export formats |
| **Art. 21** | Right to Object | Opt-out management |
| **Art. 22** | Automated Decision-Making | Human review hooks |
| **Art. 25** | Privacy by Design | Default privacy settings |
| **Art. 30** | Records of Processing | Automatic activity logs |
| **Art. 32** | Security Measures | Encryption, pseudonymization |
| **Art. 33-34** | Breach Notification | 72-hour alert system |
| **Art. 35** | DPIA Support | Impact assessment tools |
| **Art. 44-49** | International Transfers | SCCs, adequacy decisions |

### Data Subject Rights API

```python
from agentic_brain.compliance import GDPRController

gdpr = GDPRController()

# Right to Access (Art. 15)
data = await gdpr.export_subject_data(subject_id="user-123", format="json")

# Right to Erasure (Art. 17)
await gdpr.erase_subject_data(
    subject_id="user-123",
    reason="user_request",
    cascade=True,  # Remove from all connected systems
    retain_legal=True  # Keep legally required records
)

# Right to Portability (Art. 20)
portable_data = await gdpr.export_portable(
    subject_id="user-123",
    format="machine_readable"
)

# Consent Management (Art. 7)
await gdpr.record_consent(
    subject_id="user-123",
    purpose="ai_processing",
    scope=["chat_history", "preferences"],
    expires_at="2026-12-31"
)
```

### Data Locality

```yaml
# config/gdpr.yaml
data_locality:
  primary_region: eu-west-1
  allowed_regions:
    - eu-west-1
    - eu-central-1
    - eu-north-1
  blocked_regions:
    - us-*
    - cn-*
  require_adequacy_decision: true
```

---

## SOX (Financial Reporting)

### Sarbanes-Oxley Act

SOX compliance for financial reporting integrity in public companies.

```bash
ab mode switch banking
```

### SOX Controls

| Section | Requirement | Implementation |
|---------|-------------|----------------|
| **§302** | CEO/CFO Certification | Audit trail for data lineage |
| **§404** | Internal Controls | Automated control testing |
| **§409** | Real-Time Disclosure | Change detection alerts |
| **§802** | Document Retention | 7-year immutable storage |
| **§906** | Criminal Penalties | Tamper-evident logging |

### Financial Data Controls

```python
from agentic_brain.compliance import SOXMode

# Enable SOX controls
agent = Agent("financial-analyst", compliance_mode=SOXMode())

# All financial data processing is:
# - Logged with immutable audit trail
# - Subject to segregation of duties
# - Verified against control matrices
# - Traceable to source documents

response = await agent.process_financial_data(
    data=quarterly_report,
    require_dual_approval=True,
    attestation_level="executive"
)
```

### Segregation of Duties

```yaml
# config/sox.yaml
segregation_of_duties:
  roles:
    preparer:
      can: [create, edit, submit]
      cannot: [approve, post]
    reviewer:
      can: [review, comment, request_changes]
      cannot: [create, approve]
    approver:
      can: [approve, reject]
      cannot: [create, edit]
    
  workflows:
    financial_report:
      requires: [preparer, reviewer, approver]
      min_approvers: 2
      timeout_hours: 72
```

---

## APRA CPS 234 (Australian Banking)

### Australian Prudential Regulation Authority

Information security requirements for Australian financial services.

```bash
ab mode switch apra
```

### CPS 234 Requirements

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| **Information Security Capability** | Maintain capability commensurate with threats | ML-based threat detection |
| **Policy Framework** | Documented security policies | Policy-as-code enforcement |
| **Information Asset Classification** | Classify and manage assets | Automatic data classification |
| **Implementation of Controls** | Controls for assets | Defense-in-depth architecture |
| **Incident Management** | Detect and respond to incidents | SIEM integration, auto-response |
| **Testing Control Effectiveness** | Regular testing | Automated penetration testing |
| **Internal Audit** | Independent review | Compliance reporting |
| **APRA Notification** | Notify within 72 hours | Automated breach alerts |

### Australian Data Sovereignty

```python
from agentic_brain.compliance import APRAMode

# Ensure Australian data sovereignty
config = APRAMode(
    data_residency="australia",
    allowed_regions=["ap-southeast-2"],  # Sydney
    material_service_provider_controls=True,
    board_attestation_required=True
)

# Third-party risk management
await config.assess_third_party(
    provider="cloud-provider",
    criticality="material",
    offshore_access=False
)
```

---

## SOC 2 Type II

### Service Organization Control 2

Trust services criteria for SaaS and service providers.

```bash
ab mode switch enterprise
```

### Trust Service Criteria

| Criteria | Category | Implementation |
|----------|----------|----------------|
| **CC1** | Control Environment | RBAC, policies, training |
| **CC2** | Communication & Information | Audit logs, alerts, dashboards |
| **CC3** | Risk Assessment | Threat modeling, vulnerability scanning |
| **CC4** | Monitoring Activities | Real-time monitoring, anomaly detection |
| **CC5** | Control Activities | Automated controls, testing |
| **CC6** | Logical & Physical Access | MFA, encryption, key management |
| **CC7** | System Operations | Incident response, change management |
| **CC8** | Change Management | Git-based changes, approval workflows |
| **CC9** | Risk Mitigation | Business continuity, disaster recovery |

### SOC 2 Controls

```yaml
# config/soc2.yaml
soc2_controls:
  security:
    encryption_at_rest: AES-256-GCM
    encryption_in_transit: TLS-1.3
    key_rotation_days: 90
    mfa_required: true
    
  availability:
    sla_target: 99.9
    rpo_hours: 1
    rto_hours: 4
    multi_region: true
    
  processing_integrity:
    input_validation: strict
    output_verification: enabled
    reconciliation: daily
    
  confidentiality:
    data_classification: enabled
    access_logging: enabled
    dlp_enabled: true
    
  privacy:
    consent_management: enabled
    data_minimization: enforced
    retention_policy: enforced
```

---

## ISO 27001

### Information Security Management System

Aligned with ISO/IEC 27001:2022 controls.

```bash
ab mode switch enterprise --iso27001
```

### Annex A Controls

| Control | Domain | Implementation |
|---------|--------|----------------|
| **A.5** | Information Security Policies | Policy-as-code |
| **A.6** | Organization of InfoSec | RACI matrices |
| **A.7** | Human Resource Security | Training tracking |
| **A.8** | Asset Management | CMDB integration |
| **A.9** | Access Control | IAM, RBAC, ABAC |
| **A.10** | Cryptography | KMS, HSM support |
| **A.11** | Physical Security | N/A (Cloud) |
| **A.12** | Operations Security | Monitoring, logging |
| **A.13** | Communications Security | Network isolation |
| **A.14** | System Acquisition | Secure SDLC |
| **A.15** | Supplier Relationships | Vendor assessment |
| **A.16** | Incident Management | IR playbooks |
| **A.17** | Business Continuity | DR automation |
| **A.18** | Compliance | Audit automation |

---

## PCI-DSS (Payment Cards)

### Payment Card Industry Data Security Standard

PCI-DSS v4.0 compliance for payment processing.

```bash
ab mode switch banking --pci
```

### PCI-DSS Requirements

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Req 1** | Network Security Controls | ✅ |
| **Req 2** | Secure Configurations | ✅ |
| **Req 3** | Protect Stored Account Data | ✅ |
| **Req 4** | Protect Data in Transit | ✅ |
| **Req 5** | Malware Protection | ✅ |
| **Req 6** | Secure Systems & Software | ✅ |
| **Req 7** | Restrict Access | ✅ |
| **Req 8** | Identify Users | ✅ |
| **Req 9** | Physical Access | N/A |
| **Req 10** | Log & Monitor | ✅ |
| **Req 11** | Test Security | ✅ |
| **Req 12** | Information Security Policies | ✅ |

### Cardholder Data Handling

```python
from agentic_brain.compliance import PCIMode

# PCI scope minimization
pci = PCIMode(
    scope="minimal",  # Only process what's needed
    tokenization="enabled",  # Replace PANs with tokens
    p2pe="enabled"  # Point-to-point encryption
)

# Card data is NEVER stored in plaintext
# Even in memory, data is encrypted
```

---

## FedRAMP (US Government)

### Federal Risk and Authorization Management Program

FedRAMP Moderate / High baseline controls.

```bash
ab mode switch government
```

### NIST 800-53 Control Families

| Family | Controls | Implementation |
|--------|----------|----------------|
| **AC** | Access Control | RBAC, MFA, session controls |
| **AT** | Awareness & Training | Training modules |
| **AU** | Audit & Accountability | SIEM, immutable logs |
| **CA** | Assessment & Authorization | Continuous monitoring |
| **CM** | Configuration Management | IaC, drift detection |
| **CP** | Contingency Planning | DR, backup, recovery |
| **IA** | Identification & Authentication | IAM, certificates |
| **IR** | Incident Response | Playbooks, automation |
| **MA** | Maintenance | Patch management |
| **MP** | Media Protection | Encryption, disposal |
| **PE** | Physical Protection | N/A (Cloud) |
| **PL** | Planning | Security plans |
| **PM** | Program Management | Policies, governance |
| **PS** | Personnel Security | Background checks |
| **RA** | Risk Assessment | Threat modeling |
| **SA** | System & Services Acquisition | Secure SDLC |
| **SC** | System & Communications Protection | Network security |
| **SI** | System & Information Integrity | Monitoring, patching |
| **SR** | Supply Chain Risk Management | Vendor assessment |

### Air-Gap Deployment

```yaml
# k8s/fedramp-airgap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agentic-brain-airgap
data:
  network_mode: "air-gapped"
  external_connections: "none"
  llm_provider: "local-only"
  update_mechanism: "manual-media"
  telemetry: "disabled"
```

---

## Universal Compliance Features

### Encryption

#### At Rest

```yaml
encryption_at_rest:
  algorithm: AES-256-GCM
  key_management: 
    provider: aws-kms  # or: azure-keyvault, gcp-kms, hashicorp-vault
    rotation_days: 90
    key_per_tenant: true
  
  encrypted_fields:
    - message_content
    - user_data
    - session_metadata
    - audit_logs
```

#### In Transit

```yaml
encryption_in_transit:
  tls_version: "1.3"
  cipher_suites:
    - TLS_AES_256_GCM_SHA384
    - TLS_CHACHA20_POLY1305_SHA256
  certificate_pinning: true
  mutual_tls: optional  # Required for financial modes
```

### Audit Trails

```python
from agentic_brain.audit import AuditLog

# All operations automatically logged
audit = AuditLog(
    storage="immutable",  # Write-once storage
    retention_years=7,  # Configurable per compliance mode
    tamper_evident=True,  # Cryptographic verification
    format="json-lines"
)

# Query audit logs
events = await audit.query(
    start_time="2026-01-01",
    end_time="2026-03-20",
    event_types=["data_access", "data_modification"],
    user_id="analyst-123"
)
```

### Data Retention Policies

```yaml
retention_policies:
  default:
    duration_days: 365
    action: archive
    
  hipaa_phi:
    duration_years: 6
    action: encrypted_archive
    
  financial_records:
    duration_years: 7
    action: immutable_storage
    
  gdpr_personal_data:
    duration_days: 730  # Or until consent withdrawn
    action: pseudonymize_then_delete
    
  audit_logs:
    duration_years: 7
    action: immutable_storage
    deletable: false
```

### PII Handling

```python
from agentic_brain.compliance import PIIHandler

pii = PIIHandler(
    detection="ml",  # ML-based PII detection
    action="encrypt",  # encrypt, mask, tokenize, or redact
    classification_levels=["public", "internal", "confidential", "restricted"]
)

# Automatic PII detection and protection
protected_data = await pii.process(raw_data)

# PII inventory
inventory = await pii.get_inventory()
# Returns: {type: "ssn", count: 45, locations: [...]}
```

### Right to Be Forgotten

```python
from agentic_brain.compliance import DataSubjectRequest

# Process deletion request (GDPR Art. 17)
request = DataSubjectRequest(
    subject_id="user-456",
    request_type="erasure",
    scope="all",  # or specific data categories
    verification_method="email"
)

result = await request.execute(
    cascade=True,  # Delete from all connected systems
    retain_legal=True,  # Keep legally required records
    notify_processors=True  # Notify third-party processors
)

# Result includes:
# - Deleted records count
# - Retained records (with legal basis)
# - Third-party notifications sent
# - Completion certificate
```

### Data Locality Options

```yaml
data_locality:
  # Regional restrictions
  regions:
    eu_data:
      allowed: [eu-west-1, eu-central-1, eu-north-1]
      blocked: [us-*, cn-*, ru-*]
    
    australian_data:
      allowed: [ap-southeast-2]
      blocked: ["*"]  # Australia only
    
    us_government:
      allowed: [us-gov-west-1, us-gov-east-1]
      blocked: ["*"]  # GovCloud only
  
  # Cross-border transfer controls
  transfers:
    require_adequacy_decision: true
    require_sccs: true
    require_tia: true  # Transfer Impact Assessment
```

---

## Audit & Reporting

### Compliance Dashboard

```bash
# Real-time compliance status
ab compliance status

# Output:
# ┌─────────────────────────────────────────────────┐
# │           COMPLIANCE STATUS                      │
# ├─────────────────────────────────────────────────┤
# │ Mode:        Banking (SOX + PCI-DSS + APRA)     │
# │ Status:      ✅ COMPLIANT                        │
# │ Last Audit:  2026-03-15 14:32:00 UTC            │
# │ Next Audit:  2026-03-22 14:32:00 UTC            │
# ├─────────────────────────────────────────────────┤
# │ Controls:    247/250 passing (98.8%)            │
# │ Warnings:    3                                   │
# │ Critical:    0                                   │
# └─────────────────────────────────────────────────┘
```

### Compliance Reports

```bash
# Generate compliance report
ab compliance report \
  --framework hipaa,soc2 \
  --period "2026-Q1" \
  --format pdf \
  --output compliance-report-q1-2026.pdf

# Continuous compliance monitoring
ab compliance monitor \
  --frameworks all \
  --alert-email compliance@company.com \
  --alert-slack "#compliance-alerts"
```

### Audit Evidence Export

```bash
# Export evidence for external auditors
ab compliance export-evidence \
  --framework soc2 \
  --period "2025-01-01:2025-12-31" \
  --controls "CC6.*,CC7.*" \
  --format auditor-package
```

---

## Certification Status

### Current Certifications

| Certification | Status | Valid Until | Auditor |
|---------------|--------|-------------|---------|
| SOC 2 Type II | ✅ Certified | 2027-03-15 | [Big 4 Firm] |
| ISO 27001 | ✅ Certified | 2027-06-01 | [Certification Body] |
| HIPAA | ✅ BAA Available | Ongoing | Self-Attested + Third-Party |
| GDPR | ✅ Compliant | Ongoing | DPO Certified |
| PCI-DSS | ⏳ In Progress | Q3 2026 | [QSA] |
| FedRAMP | ⏳ In Progress | Q4 2026 | [3PAO] |
| APRA CPS 234 | ✅ Aligned | Ongoing | Self-Attested |

### Requesting Compliance Documents

For compliance documentation, audit reports, or to execute a BAA:

**Contact:** compliance@agentic-brain.dev

**Available Documents:**
- SOC 2 Type II Report
- ISO 27001 Certificate
- HIPAA BAA Template
- Security Questionnaire Responses
- Penetration Test Summary
- Vulnerability Assessment Report

---

## See Also

- [SECURITY.md](./SECURITY.md) — Security architecture and controls
- [AUTHENTICATION.md](./AUTHENTICATION.md) — Auth configuration
- [DEPLOYMENT.md](./DEPLOYMENT.md) — Production deployment guide
- [ENTERPRISE.md](./ENTERPRISE.md) — Enterprise features

---

<div align="center">

**Built with compliance at the core.**

*Questions? Contact: compliance@agentic-brain.dev*

</div>
