# ♿ NDIS & Disability Services

> AI assistants for Australian NDIS providers, participants, and SDA housing.

## ⚠️ Important Disclaimers

- **NOT official NDIS software** - Educational/demonstration only
- **Privacy-first** - Always use on-premise deployment
- **Human oversight required** - AI assists, humans decide
- Consult NDIS Commission for compliance requirements

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 51 | [ndis_provider.py](51_ndis_provider.py) | Provider management portal | 🔴 Advanced |
| 52 | [ndis_participant.py](52_ndis_participant.py) | Participant self-service | 🔴 Advanced |
| 53 | [ndis_compliance.py](53_ndis_compliance.py) | Compliance tracking | 🔴 Advanced |
| 54 | [ndis_support_coordinator.py](54_ndis_support_coordinator.py) | Support coordination tools | 🔴 Advanced |
| 60 | [sda_housing.py](60_sda_housing.py) | SDA property management | 🔴 Advanced |
| 61 | [sil_provider.py](61_sil_provider.py) | Supported Independent Living | 🔴 Advanced |
| 62 | [ndis_housing_search.py](62_ndis_housing_search.py) | Find SDA properties | 🔴 Advanced |
| 63 | [sda_financial_manager.py](63_sda_financial_manager.py) | SDA financial management | 🔴 Advanced |
| 64 | [sda_dashboard.py](64_sda_dashboard.py) | SDA portfolio dashboard | 🔴 Advanced |
| 65 | [sda_investor_portal.py](65_sda_investor_portal.py) | SDA investor portal | 🔴 Advanced |
| 66 | [sda_compliance_tracker.py](66_sda_compliance_tracker.py) | SDA compliance tracking | 🔴 Advanced |

## Quick Start

```bash
# NDIS provider management
python examples/ndis-disability/51_ndis_provider.py

# SDA housing search
python examples/ndis-disability/62_ndis_housing_search.py

# Support coordinator tools
python examples/ndis-disability/54_ndis_support_coordinator.py
```

## Architecture (Privacy-First)

```
┌──────────────────────────────────────────────────────────────┐
│                    ON-PREMISE DEPLOYMENT                      │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  Ollama  │  │    Neo4j     │  │   NDIS Provider Agent  │  │
│  │  (Local) │◄─┤  (Encrypted) │◄─┤  (This Application)    │  │
│  └──────────┘  └──────────────┘  └────────────────────────┘  │
│       ▲              ▲                      ▲                 │
│       │              │                      │                 │
│       └──────────────┴──────────────────────┘                 │
│              ALL DATA STAYS LOCAL                             │
└──────────────────────────────────────────────────────────────┘
                            │
                            ╳  NO participant data to cloud
                            │
```

## NDIS Terminology

| Term | Description |
|------|-------------|
| **NDIS** | National Disability Insurance Scheme |
| **SDA** | Specialist Disability Accommodation |
| **SIL** | Supported Independent Living |
| **Plan** | Participant's funded support package |
| **Support Coordinator** | Helps participants use their plan |
| **Provider** | Organization delivering NDIS services |

## Use Cases

### Provider Management
- Participant profiles (encrypted)
- Service booking and scheduling
- Progress notes with timestamps
- Funding utilization tracking
- Incident reporting (mandatory)
- Audit trail logging

### Participant Portal
- View plan and goals
- Book services
- Track progress
- Communicate with providers
- Access reports

### Support Coordination
- Multi-provider coordination
- Plan review preparation
- Goal tracking
- Service matching
- Crisis management

### SDA Housing
- Property listings
- Vacancy management
- Tenant matching
- Compliance tracking
- Maintenance requests

## Common Patterns

### Privacy-First Agent
```python
from agentic_brain import Agent

ndis_agent = Agent(
    name="ndis_assistant",
    provider="ollama",        # Local LLM only
    allow_cloud=False,        # Never send to cloud
    memory="neo4j://localhost:7687",
    audit_log=True,           # Required for NDIS audits
    system_prompt="""You are an NDIS support assistant.
    - Protect participant privacy at all times
    - Never share data between participants
    - Log all actions for audit compliance"""
)
```

### Role-Based Access
```python
def get_agent_for_role(role: str):
    if role == "support_worker":
        return Agent(tools=[view_participant, add_note, report_incident])
    elif role == "coordinator":
        return Agent(tools=[view_participant, modify_plan, manage_services])
    elif role == "manager":
        return Agent(tools=[all_tools])  # Full access
```

### Compliance Logging
```python
import logging

audit_logger = logging.getLogger("ndis_audit")

def log_action(user, participant_id, action, details):
    audit_logger.info(f"{user}|{participant_id}|{action}|{details}")
```

## Compliance Requirements

- **Australian Privacy Principles (APP)**
- **NDIS Practice Standards**
- **SDA Design Standards**
- **Quality and Safeguards Commission requirements**
- **Audit trail retention (7 years)**

## Prerequisites

- Python 3.10+
- Ollama running locally (privacy requirement)
- Neo4j with encryption enabled
- Secure, audited infrastructure
