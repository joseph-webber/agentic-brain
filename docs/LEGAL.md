# Legal Compliance Guide for Agentic Brain

**Document Version:** 1.0.0  
**Last Updated:** 2026-03-22  
**Jurisdiction:** Australia (Commonwealth)  
**Prepared in style of:** LegalVision Australia commercial legal review

---

## ⚠️ IMPORTANT NOTICE

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  THIS DOCUMENT PROVIDES GENERAL LEGAL INFORMATION ONLY.                      ║
║                                                                              ║
║  It does not constitute legal advice and should not be relied upon as such. ║
║  For specific legal advice tailored to your circumstances, consult a        ║
║  qualified Australian legal practitioner.                                   ║
║                                                                              ║
║  Laws and regulations change. Always verify current requirements.           ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Table of Contents

1. [Overview](#overview)
2. [Software License](#software-license)
3. [Terms of Service](#terms-of-service)
4. [Privacy Policy Requirements](#privacy-policy-requirements)
5. [Australian Consumer Law](#australian-consumer-law)
6. [Industry-Specific Disclaimers](#industry-specific-disclaimers)
7. [Data Protection & Privacy Act 1988](#data-protection--privacy-act-1988)
8. [API Terms of Use](#api-terms-of-use)
9. [Third-Party Integrations](#third-party-integrations)
10. [Limitation of Liability](#limitation-of-liability)
11. [Intellectual Property](#intellectual-property)
12. [Dispute Resolution](#dispute-resolution)
13. [Compliance Checklists](#compliance-checklists)

---

## 1. Overview

### What This Document Covers

Agentic Brain is an open-source AI framework that may be used to build:
- Conversational AI agents and chatbots
- Enterprise automation systems
- Healthcare triage systems (with appropriate disclaimers)
- Financial advisory tools (with appropriate disclaimers)
- Payment processing integrations
- NDIS provider management systems
- Defence and government applications

Each use case has specific legal requirements under Australian law.

### Key Australian Legislation

| Legislation | Relevance |
|-------------|-----------|
| **Privacy Act 1988 (Cth)** | Data collection, storage, use, disclosure |
| **Australian Consumer Law** (Schedule 2, CCA) | Consumer guarantees, unfair terms |
| **Spam Act 2003** | Electronic communications |
| **Health Records Act** (State-based) | Medical information handling |
| **My Health Records Act 2012** | Digital health records |
| **NDIS Act 2013** | Disability services |
| **AML/CTF Act 2006** | Anti-money laundering |
| **Security of Critical Infrastructure Act 2018** | Defence/infrastructure |
| **Corporations Act 2001** | Financial services, AFSL |

---

## 2. Software License

### Apache License 2.0

Agentic Brain is licensed under **Apache License, Version 2.0**.

#### What This Means for Users

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  APACHE 2.0 PERMISSIONS                                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ✅ You CAN:                                                                 ║
║     • Use commercially without restrictions                                  ║
║     • Modify the source code                                                ║
║     • Distribute copies                                                      ║
║     • Sublicense under different terms                                      ║
║     • Place warranty (additional terms)                                     ║
║     • Use in proprietary/closed-source products                            ║
║                                                                              ║
║  ⚠️ You MUST:                                                                ║
║     • Include original license notice                                       ║
║     • Include NOTICE file (if present)                                      ║
║     • State significant changes made                                        ║
║     • Retain copyright notices                                              ║
║                                                                              ║
║  ❌ You CANNOT:                                                              ║
║     • Hold authors liable                                                   ║
║     • Use trademarks without permission                                     ║
║     • Imply endorsement                                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

#### Key Differences from GPL

| Feature | Apache 2.0 | GPL 3.0 |
|---------|------------|---------|
| **Philosophy** | Permissive | Copyleft |
| **Source disclosure** | NOT required | Required if distributing |
| **Derivative licensing** | Any license (including proprietary) | Must use GPL |
| **Patent grant** | ✅ Explicit | ✅ Explicit |
| **Trademark protection** | ✅ Explicit | ❌ Not covered |
| **Commercial use** | ✅ Unrestricted | ✅ With conditions |

#### Patent Grant

Apache 2.0 includes an **explicit patent license** from contributors:
- Each contributor grants you a perpetual, worldwide patent license
- Covers patents necessarily infringed by their contribution
- Protects users from patent litigation
- **Defensive termination**: Patent license terminates if you sue for patent infringement

#### Trademark Notice

Apache 2.0 does **not** grant rights to use trademarks, service marks, or product names, except:
- Describing the origin of the work
- Reproducing content of the NOTICE file

#### Warranty Disclaimer (Per Apache 2.0 Section 7)

> Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Work and assume any risks associated with Your exercise of permissions under this License.

#### Why Apache 2.0?

Apache 2.0 was chosen for Agentic Brain because:
1. **Enterprise-friendly**: Allows integration into proprietary products
2. **Patent protection**: Explicit patent grant protects users and contributors
3. **Trademark protection**: Prevents unauthorized use of project name
4. **Maximum adoption**: Compatible with more licenses than GPL
5. **Commercial flexibility**: No requirement to disclose modifications
6. **OSI-approved**: Recognized by Open Source Initiative

---

## 3. Terms of Service

### Recommended SaaS Terms Structure

If deploying Agentic Brain as a hosted service, include these clauses:

#### 3.1 Service Description
```
The Service provides [AI chatbot / automation / etc.] capabilities.
- Uptime target: [99.9%] (excluding scheduled maintenance)
- Maintenance windows: [Sundays 02:00-06:00 AEST]
- Support response: [Business hours / 24x7]
```

#### 3.2 User Obligations
```
Users agree to:
- Provide accurate registration information
- Maintain security of access credentials
- Not use the Service for unlawful purposes
- Not attempt to reverse engineer the Service
- Comply with acceptable use policy
- Not exceed rate limits or abuse the Service
```

#### 3.3 Subscription and Payment
```
- Pricing: As published on [website/agreement]
- Billing: [Monthly/Annual] in advance
- Currency: Australian Dollars (AUD)
- GST: All prices exclusive of GST unless stated
- Late payment: [Interest at RBA cash rate + 4%]
- Price changes: 30 days written notice
```

#### 3.4 Term and Termination
```
- Initial term: [12 months / month-to-month]
- Renewal: Automatic unless [30 days] notice
- Termination for convenience: [30 days] written notice
- Termination for cause: Immediate upon material breach
- Effect of termination: [Data export period, deletion]
```

#### 3.5 Data Handling on Termination
```
Upon termination:
1. Customer may export data for [30 days]
2. After [30 days], all customer data deleted
3. Provider retains anonymised analytics only
4. Backups purged per retention policy [90 days]
```

---

## 4. Privacy Policy Requirements

### Privacy Act 1988 Compliance

Australian Privacy Principles (APPs) that apply:

#### APP 1 - Open and Transparent Management
```
You MUST have a clearly expressed and up-to-date privacy policy that includes:
- Types of personal information collected
- How information is collected
- Purposes of collection
- How individuals can access/correct their information
- Whether information disclosed overseas (and to which countries)
- How to complain about privacy breaches
```

#### APP 3 - Collection of Solicited Personal Information
```
Only collect personal information that is:
- Reasonably necessary for your functions
- Collected by lawful and fair means
- Collected directly from the individual (where reasonable)
```

#### APP 5 - Notification of Collection
```
At or before collection, notify individuals of:
- Your identity and contact details
- Purpose of collection
- Consequences if not collected
- Third parties to whom you usually disclose
- Rights to access and correct
- Overseas disclosure (if any)
```

#### APP 6 - Use or Disclosure
```
Only use/disclose personal information for:
- Primary purpose of collection, OR
- Secondary purpose individual would reasonably expect, OR
- With consent, OR
- Required/authorised by law
```

#### APP 11 - Security
```
You MUST take reasonable steps to:
- Protect information from misuse, interference, loss
- Protect from unauthorised access, modification, disclosure
- Destroy or de-identify when no longer needed
```

### Privacy Policy Template Sections

```markdown
## Privacy Policy

### 1. About This Policy
[Who we are, what this policy covers]

### 2. Information We Collect
- Information you provide (name, email, etc.)
- Information collected automatically (IP, device info)
- Information from third parties (if applicable)

### 3. How We Use Your Information
- To provide the Service
- To communicate with you
- To improve our Service
- To comply with legal obligations

### 4. Disclosure of Information
- Service providers (hosting, analytics)
- Legal requirements
- Business transfers
- With your consent

### 5. Overseas Disclosure
[List countries where data may be processed]
- United States (cloud hosting)
- [Other jurisdictions]

### 6. Data Security
[Security measures implemented]

### 7. Access and Correction
[How to request access/correction]

### 8. Complaints
[Process for privacy complaints]
[OAIC contact details]

### 9. Changes to This Policy
[How changes are communicated]

### 10. Contact Us
[Privacy officer contact details]
```

---

## 5. Australian Consumer Law

### Consumer Guarantees

The Australian Consumer Law provides **automatic guarantees** that cannot be excluded for consumer transactions:

#### Guarantees for Goods
```
╔══════════════════════════════════════════════════════════════════════════════╗
║  CONSUMER GUARANTEE                    YOU CANNOT EXCLUDE                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Acceptable quality                    ❌ Cannot exclude                     ║
║  Fit for disclosed purpose             ❌ Cannot exclude                     ║
║  Match description                     ❌ Cannot exclude                     ║
║  Match sample/demo                     ❌ Cannot exclude                     ║
║  Clear title                           ❌ Cannot exclude                     ║
║  Undisturbed possession                ❌ Cannot exclude                     ║
║  No undisclosed securities             ❌ Cannot exclude                     ║
║  Spare parts/repair available          ❌ Cannot exclude                     ║
║  Express warranties honoured           ❌ Cannot exclude                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

#### Guarantees for Services
```
╔══════════════════════════════════════════════════════════════════════════════╗
║  CONSUMER GUARANTEE                    YOU CANNOT EXCLUDE                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Due care and skill                    ❌ Cannot exclude                     ║
║  Fit for disclosed purpose             ❌ Cannot exclude                     ║
║  Supplied within reasonable time       ❌ Cannot exclude                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

#### Unfair Contract Terms

Terms may be **void** if they are:
1. **Unfair** (causes significant imbalance)
2. **Not reasonably necessary** to protect legitimate interests
3. **Would cause detriment** if relied upon

**Examples of potentially unfair terms:**
- Unilateral variation without notice
- Automatic renewal without clear disclosure
- Excessive termination fees
- Limiting one party's right to sue
- Assigning contract without consent

### Required Disclosure

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  MANDATORY CONSUMER RIGHTS NOTICE (for B2C transactions)                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Our goods and services come with guarantees that cannot be excluded        ║
║  under the Australian Consumer Law. For major failures with the service,    ║
║  you are entitled:                                                          ║
║                                                                              ║
║  • to cancel your service contract with us; and                             ║
║  • to a refund for the unused portion, or to compensation for its           ║
║    reduced value.                                                           ║
║                                                                              ║
║  You are also entitled to choose a refund or replacement for major          ║
║  failures with goods. If a failure with the goods or a service does not     ║
║  amount to a major failure, you are entitled to have the failure            ║
║  rectified in a reasonable time. If this is not done you are entitled       ║
║  to a refund for the goods and to cancel the contract for the service       ║
║  and obtain a refund of any unused portion. You are also entitled to        ║
║  be compensated for any other reasonably foreseeable loss or damage         ║
║  from a failure in the goods or service.                                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 6. Industry-Specific Disclaimers

### 6.1 Medical/Healthcare Disclaimer

**REQUIRED** for any healthcare-related AI applications:

```python
MEDICAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ⚠️  IMPORTANT MEDICAL DISCLAIMER  ⚠️                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software is NOT a substitute for professional medical advice,         ║
║  diagnosis, or treatment.                                                   ║
║                                                                              ║
║  • This is an AI triage SUPPORT tool only                                   ║
║  • All outputs must be reviewed by qualified healthcare professionals       ║
║  • Never delay seeking medical advice because of this software             ║
║  • In emergency, call 000 (Triple Zero) immediately                        ║
║  • This software does not create a doctor-patient relationship             ║
║                                                                              ║
║  The developers, contributors, and deployers of this software accept       ║
║  no liability for any decisions made based on its outputs.                 ║
║                                                                              ║
║  REGULATORY STATUS:                                                         ║
║  This software is not registered as a medical device with the TGA          ║
║  (Therapeutic Goods Administration). It is intended as a decision          ║
║  support tool only, not for primary diagnosis.                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
```

### 6.2 Financial Services Disclaimer

**REQUIRED** if providing financial guidance:

```python
FINANCIAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                   ⚠️  IMPORTANT FINANCIAL DISCLAIMER  ⚠️                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software provides GENERAL INFORMATION ONLY.                           ║
║  It is NOT personal financial advice.                                       ║
║                                                                              ║
║  • We do not hold an Australian Financial Services Licence (AFSL)          ║
║  • We are not authorised to provide personal financial advice              ║
║  • This information does not consider your personal circumstances          ║
║  • You should seek advice from a licensed financial adviser                ║
║  • Past performance is not indicative of future results                    ║
║                                                                              ║
║  CREDIT PRODUCTS:                                                           ║
║  If credit products are mentioned, we are not licensed credit providers    ║
║  under the National Consumer Credit Protection Act 2009.                   ║
║                                                                              ║
║  The developers accept no liability for financial decisions made based     ║
║  on information provided by this software.                                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
```

### 6.3 Legal Information Disclaimer

**REQUIRED** if providing legal information:

```python
LEGAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ⚠️  IMPORTANT LEGAL DISCLAIMER  ⚠️                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software provides GENERAL LEGAL INFORMATION ONLY.                     ║
║  It is NOT legal advice and should not be relied upon as such.             ║
║                                                                              ║
║  • We are not a law firm or legal practice                                 ║
║  • Information may not reflect current law                                 ║
║  • Laws vary by jurisdiction - verify local requirements                   ║
║  • This information does not create a lawyer-client relationship          ║
║  • For legal advice, consult a qualified Australian legal practitioner    ║
║                                                                              ║
║  The developers accept no liability for any actions taken based on         ║
║  legal information provided by this software.                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
```

### 6.4 NDIS Provider Disclaimer

**REQUIRED** for NDIS-related applications:

```python
NDIS_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ⚠️  IMPORTANT NDIS DISCLAIMER  ⚠️                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software is a MANAGEMENT SUPPORT TOOL only.                           ║
║                                                                              ║
║  • This software does not replace qualified NDIS plan management           ║
║  • All service agreements require proper NDIS-compliant documentation      ║
║  • Pricing information may not reflect current NDIS Price Guide            ║
║  • Always verify information with the official NDIS Price Guide            ║
║  • Service bookings should be confirmed through official myplace portal    ║
║                                                                              ║
║  QUALITY & SAFEGUARDS:                                                      ║
║  This software does not replace NDIS Quality and Safeguards Commission     ║
║  compliance obligations. Providers must maintain separate compliance       ║
║  with all NDIS Practice Standards.                                         ║
║                                                                              ║
║  PRIVACY:                                                                   ║
║  NDIS participant information is subject to the Privacy Act 1988 and       ║
║  NDIS-specific privacy requirements. Ensure appropriate data handling.     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
```

### 6.5 Defence/Government Disclaimer

**REQUIRED** for defence applications:

```python
DEFENCE_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                   ⚠️  DEFENCE SECURITY DISCLAIMER  ⚠️                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software is provided for DEMONSTRATION PURPOSES ONLY.                 ║
║                                                                              ║
║  SECURITY CLASSIFICATION:                                                   ║
║  • This software has NOT been security assessed by AGSVA or ASD            ║
║  • This software is NOT approved for classified information                ║
║  • Do NOT process OFFICIAL, PROTECTED, or CLASSIFIED data                  ║
║                                                                              ║
║  COMPLIANCE:                                                                 ║
║  • Defence applications require ISM compliance assessment                   ║
║  • ITAR/EAR restrictions may apply to certain use cases                    ║
║  • AUKUS information handling requires specific approvals                  ║
║                                                                              ║
║  For operational deployment, obtain appropriate security accreditation     ║
║  through your organisation's security authority.                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
```

### 6.6 AI/Machine Learning Disclaimer

**RECOMMENDED** for all AI applications:

```python
AI_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                  ⚠️  ARTIFICIAL INTELLIGENCE DISCLAIMER  ⚠️                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software uses artificial intelligence and machine learning.           ║
║                                                                              ║
║  IMPORTANT LIMITATIONS:                                                      ║
║  • AI outputs may contain errors, hallucinations, or inaccuracies          ║
║  • AI does not understand context the way humans do                        ║
║  • Outputs should be verified by qualified humans before reliance          ║
║  • AI may produce different outputs for similar inputs                     ║
║  • AI training data has a knowledge cutoff date                            ║
║                                                                              ║
║  BIAS AND FAIRNESS:                                                         ║
║  • AI systems may reflect biases present in training data                  ║
║  • Critical decisions should not rely solely on AI outputs                 ║
║  • Human oversight is recommended for consequential decisions              ║
║                                                                              ║
║  DATA USAGE:                                                                 ║
║  • Inputs may be processed by third-party AI services                      ║
║  • Do not input sensitive personal information unless documented           ║
║  • Review data handling policies of underlying AI providers                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
```

---

## 7. Data Protection & Privacy Act 1988

### Notifiable Data Breaches Scheme

Under the **Privacy Amendment (Notifiable Data Breaches) Act 2017**, you must:

#### When to Notify

```
Notification required when:
1. There is unauthorised access, disclosure, or loss of personal information
2. A reasonable person would conclude serious harm is likely
3. You have not been able to prevent the likely risk of serious harm

Timeline:
- Assess breach within 30 days (or as soon as practicable)
- Notify OAIC and affected individuals promptly
```

#### Data Breach Response Plan

```
1. CONTAIN
   - Limit the breach
   - Secure systems
   - Preserve evidence

2. ASSESS
   - What data was affected?
   - How many individuals?
   - What is the risk of serious harm?

3. NOTIFY (if required)
   - OAIC notification
   - Individual notification
   - Consider public notification

4. REVIEW
   - How did it happen?
   - What can prevent recurrence?
   - Update policies and training
```

### Cross-Border Data Transfers

If using cloud services that process data overseas:

```
You MUST:
- Inform individuals of overseas disclosure (APP 5)
- Take reasonable steps to ensure overseas recipient complies with APPs (APP 8)
- OR obtain consent
- OR rely on prescribed exceptions

Common destinations for cloud services:
- United States (AWS, Azure, GCP)
- Singapore (regional data centres)
- European Union (GDPR-compliant services)
```

---

## 8. API Terms of Use

### Standard API Terms

```markdown
## API Terms of Use

### 1. License Grant
We grant you a limited, non-exclusive, non-transferable license to 
access our API solely for the purpose of integrating with our Service.

### 2. Acceptable Use
You agree NOT to:
- Exceed rate limits
- Share API credentials
- Attempt to circumvent security measures
- Use the API for competing products
- Reverse engineer the API
- Store data beyond what is necessary

### 3. Rate Limits
- Standard: 100 requests/minute
- Pro: 1,000 requests/minute
- Enterprise: Custom

Exceeding limits may result in temporary suspension.

### 4. Authentication
- API keys are confidential
- You are responsible for all use under your credentials
- Report compromised credentials immediately
- Keys may be rotated at our discretion

### 5. Data Handling
- Minimise data collection
- Do not store personal information unnecessarily
- Comply with Privacy Act 1988
- Delete data upon user request

### 6. Changes
We may modify the API with [30 days] notice for breaking changes.
Non-breaking changes may be made without notice.

### 7. Termination
We may suspend or terminate API access:
- For violation of these terms
- For suspected fraud or abuse
- With [30 days] notice for convenience

### 8. No SLA (unless separately agreed)
API access is provided "as is" unless you have a separate SLA.
```

---

## 9. Third-Party Integrations

### Disclosure Requirements

When integrating third-party services, disclose:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  THIRD-PARTY SERVICES                                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This software may integrate with third-party services including:           ║
║                                                                              ║
║  AI PROVIDERS:                                                               ║
║  • OpenAI (GPT models) - USA - openai.com/privacy                           ║
║  • Anthropic (Claude) - USA - anthropic.com/privacy                         ║
║  • Google (Gemini) - USA - policies.google.com/privacy                      ║
║  • Ollama (Local) - Local processing, no external data transfer             ║
║                                                                              ║
║  CLOUD INFRASTRUCTURE:                                                       ║
║  • AWS - Various regions - aws.amazon.com/privacy                           ║
║  • Google Cloud - Various regions - cloud.google.com/privacy                ║
║  • Azure - Various regions - privacy.microsoft.com                          ║
║                                                                              ║
║  PAYMENT PROCESSORS:                                                         ║
║  • Stripe - USA/Global - stripe.com/au/privacy                              ║
║  • PayPal - USA/Global - paypal.com/privacy                                 ║
║  • Afterpay - USA (Block) - afterpay.com/privacy                            ║
║                                                                              ║
║  Your use of these services is subject to their respective terms and        ║
║  privacy policies. We are not responsible for third-party practices.        ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Subprocessor Agreements

For GDPR compliance (if serving EU customers):

```
Maintain a list of subprocessors and:
- Ensure adequate data processing agreements
- Notify customers of subprocessor changes
- Conduct due diligence on subprocessor security
```

---

## 10. Limitation of Liability

### B2B Limitation Clause

```
LIMITATION OF LIABILITY (B2B TRANSACTIONS)

To the maximum extent permitted by law:

1. EXCLUSION OF CONSEQUENTIAL LOSS
   We are not liable for any indirect, incidental, special, consequential,
   or punitive damages, including but not limited to:
   - Loss of profits
   - Loss of revenue
   - Loss of data
   - Loss of business opportunity
   - Loss of goodwill

2. CAP ON LIABILITY
   Our total aggregate liability arising from or related to this agreement
   shall not exceed the greater of:
   - Fees paid by you in the 12 months preceding the claim; or
   - AUD $1,000

3. EXCEPTIONS
   Nothing in this agreement limits liability for:
   - Fraud or fraudulent misrepresentation
   - Death or personal injury caused by negligence
   - Any liability that cannot be excluded by law

4. TIME LIMIT
   Any claim must be brought within 12 months of the cause of action arising.
```

### B2C Limitations

**NOTE:** Consumer guarantees under Australian Consumer Law **CANNOT** be excluded. Any limitation clause must include:

```
Nothing in these terms excludes, restricts, or modifies any consumer 
guarantee, right, or remedy conferred by the Competition and Consumer 
Act 2010 (Cth) or any other applicable law that cannot be excluded, 
restricted, or modified by agreement.
```

---

## 11. Intellectual Property

### Open Source Compliance

```
OPEN SOURCE COMPONENTS

This software incorporates open source components under various licenses:

Component                License         Obligations
─────────────────────────────────────────────────────────────────────
agentic-brain           Apache-2.0      Attribution, state changes
Python                  PSF License     Attribution
FastAPI                 MIT             Attribution
Pydantic                MIT             Attribution
NumPy                   BSD-3           Attribution
PyTorch                 BSD-3           Attribution
Transformers (HF)       Apache 2.0      Attribution, state changes
Anthropic SDK           MIT             Attribution
OpenAI SDK              MIT             Attribution

Full license texts available in /licenses directory.
```

### Trademark Usage

```
TRADEMARK NOTICE

• "Agentic Brain" and the Agentic Brain logo are trademarks of [Owner]
• All third-party trademarks are property of their respective owners
• Use of trademarks does not imply endorsement
```

---

## 12. Dispute Resolution

### Australian Jurisdiction

```
GOVERNING LAW AND JURISDICTION

1. GOVERNING LAW
   This agreement is governed by the laws of [New South Wales / Victoria / 
   Queensland], Australia.

2. JURISDICTION
   The parties submit to the exclusive jurisdiction of the courts of 
   [State] and any courts entitled to hear appeals from those courts.

3. DISPUTE RESOLUTION PROCESS
   Before commencing litigation, parties agree to:
   
   a) NEGOTIATION (14 days)
      Senior representatives meet to attempt resolution
      
   b) MEDIATION (if negotiation fails)
      Mediation under ACDC Mediation Guidelines
      Costs shared equally
      Location: [City], Australia
      
   c) LITIGATION (if mediation fails)
      Either party may commence court proceedings

4. URGENT RELIEF
   Nothing prevents a party from seeking urgent injunctive relief.
```

---

## 13. Compliance Checklists

### Pre-Launch Checklist

```
□ Privacy Policy published and accessible
□ Terms of Service published and accessible
□ Cookie consent banner (if using cookies)
□ Consumer guarantee notice (for B2C)
□ Appropriate industry disclaimers implemented
□ Data breach response plan documented
□ Subprocessor list maintained
□ Security measures documented
□ Accessibility statement (recommended)
□ Contact information clearly displayed
```

### Ongoing Compliance

```
□ Annual privacy policy review
□ Regular security assessments
□ Data retention policy enforcement
□ Subprocessor monitoring
□ Staff training on privacy/security
□ Incident response testing
□ Consumer law compliance review
□ License compliance audit
```

### NDIS Provider Checklist

```
□ NDIS registration current
□ Worker screening checks
□ Quality and Safeguards compliance
□ SIRS reporting capability
□ Participant consent processes
□ Plan management documentation
□ Progress note templates
□ Incident reporting procedures
```

### Healthcare Application Checklist

```
□ Medical disclaimer prominently displayed
□ Not marketed as medical device (unless TGA registered)
□ Health records handled per relevant Health Records Act
□ Qualified healthcare professional review processes
□ Emergency escalation procedures
□ My Health Record integration compliance (if applicable)
□ Telehealth regulations compliance (if applicable)
```

---

## Resources

### Australian Regulators

| Regulator | Jurisdiction | Website |
|-----------|--------------|---------|
| OAIC | Privacy | oaic.gov.au |
| ACCC | Consumer Law | accc.gov.au |
| ASIC | Financial Services | asic.gov.au |
| APRA | Prudential | apra.gov.au |
| AUSTRAC | AML/CTF | austrac.gov.au |
| TGA | Medical Devices | tga.gov.au |
| NDIS Commission | Disability | ndiscommission.gov.au |

### Legal Service Providers (Australia)

- **LegalVision**: legalvision.com.au
- **Lawpath**: lawpath.com.au
- **Sprintlaw**: sprintlaw.com.au
- **Legal123**: legal123.com.au
- **Prosper Law**: prosperlaw.com.au

### Templates & Guides

- OAIC Privacy Policy Guide: oaic.gov.au/privacy/privacy-guidance
- ACCC Consumer Guarantees: accc.gov.au/consumers/consumer-rights-guarantees
- ASIC ePayments Code: asic.gov.au/regulatory-resources/financial-services

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-22 | Initial release |

---

## License

This document is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

You are free to share and adapt this material with attribution.

---

*Prepared in the style of a LegalVision Australia commercial legal review. This is general information, not legal advice. Consult a qualified Australian legal practitioner for advice specific to your circumstances.*
