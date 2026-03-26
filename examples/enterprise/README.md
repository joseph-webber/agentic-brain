# 🏢 Enterprise Examples

> Enterprise-grade AI assistants - IT, HR, legal, knowledge management, and Australian industry-specific solutions.

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 28 | [it_helpdesk.py](28_it_helpdesk.py) | IT support automation | 🔴 Advanced |
| 29 | [hr_assistant.py](29_hr_assistant.py) | HR queries & onboarding | 🔴 Advanced |
| 30 | [legal_compliance.py](30_legal_compliance.py) | Legal document analysis | 🔴 Advanced |
| 31 | [knowledge_wiki.py](31_knowledge_wiki.py) | Enterprise knowledge base | 🔴 Advanced |
| 32 | [meeting_assistant.py](32_meeting_assistant.py) | Meeting notes & actions | 🔴 Advanced |

## 🇦🇺 Australian Industry Examples

| Example | Description | Regulatory Context |
|---------|-------------|-------------------|
| [defence_contractor_assistant.py](defence_contractor_assistant.py) | AUKUS/submarine contractor assistant | AGSVA clearances, PSPF classification |
| [ndis_provider_bot.py](ndis_provider_bot.py) | NDIS service provider management | NDIS Price Guide, Quality & Safeguards |
| [aged_care_assistant.py](aged_care_assistant.py) | Aged Care Act 2024 compliant | SIRS, Quality Indicators, ACQSC |
| [aml_compliance_bot.py](aml_compliance_bot.py) | Anti-Money Laundering compliance | AUSTRAC, AML/CTF Act 2006 |
| [healthcare_triage_bot.py](healthcare_triage_bot.py) | Healthcare triage assistant | Australasian Triage Scale, Medicare/PBS |

## Quick Start

```bash
# IT helpdesk automation
python examples/enterprise/28_it_helpdesk.py

# HR assistant
python examples/enterprise/29_hr_assistant.py

# Knowledge wiki
python examples/enterprise/31_knowledge_wiki.py
```

## Use Cases

### IT Helpdesk
- Ticket classification and routing
- Password reset automation
- Common issue resolution
- Escalation management
- Knowledge base integration

### HR Assistant
- Policy questions
- Leave balance queries
- Onboarding workflows
- Benefits information
- Training recommendations

### Legal Compliance
- Contract review
- Policy compliance checking
- Risk identification
- Regulatory updates
- Audit preparation

### Knowledge Wiki
- Search across documents
- Q&A with context
- Document summarization
- Knowledge discovery
- Expert finding

### Meeting Assistant
- Transcription
- Action item extraction
- Summary generation
- Follow-up reminders
- Decision tracking

## Common Patterns

### Ticket Classification
```python
from agentic_brain import Agent

classifier = Agent(
    name="ticket_classifier",
    system_prompt="""Classify IT tickets into:
    - hardware: Physical equipment issues
    - software: Application problems
    - network: Connectivity issues
    - access: Permission/account issues
    - other: Everything else
    
    Return JSON: {"category": "...", "priority": "low/medium/high"}"""
)
```

### Policy Q&A
```python
from agentic_brain import Agent

hr_bot = Agent(
    name="hr_assistant",
    rag_source="./company_policies/",
    system_prompt="Answer HR policy questions using company documentation."
)
```

### Meeting Summarization
```python
agent = Agent(name="meeting_assistant")
summary = agent.chat(f"""
Summarize this meeting transcript:
{transcript}

Extract:
1. Key decisions
2. Action items (with owners)
3. Next steps
""")
```

## Security Considerations

- **Data Privacy**: Use on-premise deployment for sensitive data
- **Access Control**: Implement role-based access
- **Audit Logging**: Track all AI interactions
- **Compliance**: Meet industry regulations (SOC2, GDPR, etc.)

## 🇦🇺 Australian Regulatory Context

### Defence Contractor Assistant
- **AGSVA Clearances**: Baseline, NV1, NV2, PV (Positive Vetting)
- **PSPF Classification**: OFFICIAL, PROTECTED, SECRET, TOP SECRET
- **AUKUS**: Information sharing protocols for submarine program
- **Air-Gapped**: Designed for deployment without network connectivity

### NDIS Provider Bot
- **NDIS Price Guide**: Line item validation and cost calculation
- **Quality & Safeguards Commission**: Compliance frameworks
- **SIRS**: Serious Incident Response Scheme reporting
- **Privacy**: Australian Privacy Principles (APP) compliant

### Aged Care Assistant
- **Aged Care Act 2024**: New reforms effective July 2025
- **SIRS**: Serious Incident Response Scheme (24-hour reporting)
- **Quality Indicators**: National QI Program metrics
- **Medication Safety**: High-risk medication double-signing

### AML Compliance Bot
- **AUSTRAC**: SMR, TTR, IFTI reporting requirements
- **CDD/EDD**: Customer Due Diligence workflows
- **PEP Screening**: Politically Exposed Persons checks
- **Sanctions**: DFAT, UN, OFAC screening integration

### Healthcare Triage Bot
- **ATS**: Australasian Triage Scale (1-5)
- **Medicare**: MBS item number awareness
- **PBS**: Pharmaceutical Benefits Scheme eligibility
- **After-Hours**: 13 HEALTH, GP helplines integration

## Prerequisites

- Python 3.10+
- Ollama running locally
- Neo4j (for knowledge graph)
- Document storage (for RAG)
