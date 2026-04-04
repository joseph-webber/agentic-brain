# Agentic Brain Security vs Industry Standards

## Scope

This comparison reviews Agentic Brain's current implementation against leading 2026 agent-security patterns:

- Microsoft Agent Governance Toolkit
- Microsoft Agent Framework (MAF)
- Protecto
- Google Zanzibar / Warrant-style fine-grained authorization
- IETF AI agent auth drafts built on OAuth 2.0

Internal implementation reviewed:

- `src/agentic_brain/security/roles.py`
- `src/agentic_brain/security/guards.py`
- `src/agentic_brain/security/llm_guard.py`
- `src/agentic_brain/security/prompt_filter.py`
- `docs/SECURITY_IMPLEMENTATION.md`
- `docs/WORDPRESS_ROLE_MAPPING.md`

## Executive Summary

Agentic Brain already has a strong **practical runtime security model** for a product that mixes coding, LLM access, and WordPress/WooCommerce integrations. Its biggest strengths are:

- clear four-tier RBAC
- strong separation between machine-capable and API-only users
- built-in shell/file/code restrictions
- role-aware LLM prompt filtering
- context-dependent guest behavior for commerce/public sites

Compared with industry leaders, the main gaps are not basic RBAC. The main gaps are **enterprise-grade identity, policy, and authorization depth**:

- no external policy engine or policy-as-code layer
- no fine-grained tuple/relationship-based authorization
- no workload identity / short-lived agent credentials
- no OAuth-based delegated agent authorization model
- no inter-agent authentication and trust model
- no centralized anomaly detection, kill switch, or quarantine workflow

## Feature Comparison

| Feature | Agentic Brain | MS Agent Toolkit | MAF | Protecto | Zanzibar / Warrant | IETF Drafts |
|---|---|---|---|---|---|---|
| Multi-tier RBAC | ✅ 4 tiers | ✅ | ✅ | ✅ | ✅ | ⚠️ Model, not product RBAC |
| Runtime policy enforcement | ✅ In-process guards | ✅ Strong | ✅ Strong | ✅ Strong | ⚠️ Authz engine only | ⚠️ Delegation patterns |
| Context-aware access | ✅ Guest mirrors platform context | ✅ | ✅ | ✅ | ✅ | ✅ claims/scopes |
| API-only user isolation | ✅ USER role | ❌ | ❌ | ✅ | ❌ | ❌ |
| Help-only anonymous mode | ✅ GUEST role | ❌ | ❌ | ❌ | ❌ | ❌ |
| Prompt injection filtering | ✅ Built in | ⚠️ Depends on stack | ⚠️ Guardrails-oriented | ⚠️ Data/runtime focus | ❌ | ❌ |
| Shell / code execution tiering | ✅ FULL_ADMIN vs SAFE_ADMIN | ❌ | ❌ | ❌ | ❌ | ❌ |
| Guest commerce flows | ✅ WooCommerce guest cart / checkout | N/A | N/A | N/A | N/A | N/A |
| Audit log of allow/deny decisions | ✅ Local audit events | ✅ | ✅ | ✅ | ✅ decision logs | ✅ expected |
| Fine-grained resource authorization | ❌ Coarse role/path/scope based | ⚠️ Policy driven | ✅ Azure scope-based | ✅ Fine grained | ✅ Core strength | ✅ scopes/claims |
| External IdP / AD integration | ❌ | ✅ Entra | ✅ Entra | ✅ AD / SSO | ⚠️ Via surrounding stack | ✅ IdP aligned |
| Policy as code | ❌ | ✅ YAML / Rego / Cedar | ✅ Azure policy patterns | ✅ Policy plane | ✅ relationship model | ⚠️ Standards building blocks |
| Agent/workload identity | ❌ | ✅ Agent identity | ✅ service principal / managed identity | ✅ enterprise identity | ❌ not identity-native | ✅ key design goal |
| OAuth delegated authorization | ❌ | ⚠️ via Entra ecosystem | ⚠️ via Entra ecosystem | ✅/⚠️ via SSO stack | ❌ | ✅ core focus |
| Inter-agent trust / secure messaging | ❌ not evident | ✅ | ⚠️ architecture dependent | ⚠️ platform dependent | ❌ | ⚠️ emerging |
| Kill switch / rogue-agent containment | ❌ not evident | ✅ stronger governance posture | ⚠️ partial | ✅ stronger governance posture | ❌ | ⚠️ draft guidance |

## What Agentic Brain Already Does Well

### 1. Simple, explicit role boundaries

The four canonical roles are clear and easy to reason about:

- `FULL_ADMIN`
- `SAFE_ADMIN`
- `USER`
- `GUEST`

That is stronger than many agent systems that start with vague "admin/user" distinctions and add exceptions later.

### 2. Strong machine-vs-API separation

`USER` and `GUEST` are explicitly prevented from shell access, file writes, and code execution. That is a good "least agency" design and directly reduces blast radius.

### 3. Safety-aware YOLO model

Agentic Brain supports a capability most enterprise platforms avoid entirely: high-trust code/shell execution. The split between unrestricted `FULL_ADMIN` and guarded `SAFE_ADMIN` is a real differentiator.

### 4. Context-dependent guest access

The guest model is unusually practical. Instead of a blanket deny, it mirrors what the connected platform already exposes to anonymous users. For WooCommerce, that includes guest shopping flows such as browsing, cart, coupon, and checkout.

### 5. LLM-specific controls, not just platform RBAC

The LLM layer adds provider allowlists, per-role rate limits, prompt filtering, consensus restrictions, and file/code/YOLO gating. Many systems stop at API auth and never apply the same rigor to prompt handling.

## What Agentic Brain Has That Others Usually Don't

- **A true YOLO/admin execution model** with security tiering instead of a blanket ban on code execution.
- **A first-class API-only role** for authenticated customers.
- **A first-class help-only role** for anonymous traffic.
- **Commerce-aware guest authorization** that mirrors WooCommerce storefront permissions instead of treating all guests as identical.
- **Role-coupled LLM prompt filtering** alongside runtime RBAC.
- **A security model simple enough to explain to operators quickly**, which is a real operational advantage.

## What Is Missing vs Industry Best Practice

### High priority gaps

1. **Fine-grained authorization**
   - Current model is mostly role-based plus path and API-scope checks.
   - Missing resource-level decisions like "this agent can read order 123 but not order 124" or relationship-based checks like Zanzibar/Warrant.

2. **External identity federation**
   - No built-in Entra/AD/Okta style mapping for agent identities, admins, or service principals.
   - Enterprise frameworks increasingly treat agents as first-class identities.

3. **Policy-as-code / centralized policy engine**
   - Current rules are embedded in Python.
   - Best practice is a separate policy layer with versioning, testing, dry-run, and centralized governance.

4. **Delegated agent authorization**
   - No clear OAuth 2.0 on-behalf-of / actor-token / target-resource model for agents acting for users.
   - This is a major direction in the IETF drafts.

5. **Workload identity and short-lived credentials**
   - No visible agent identity issuance, attestation, or short-lived credentials for machine-to-machine actions.
   - Modern platforms avoid long-lived shared secrets wherever possible.

### Medium priority gaps

6. **Inter-agent authentication and message integrity**
   - Not evident in the reviewed security layer.
   - Important for multi-agent workflows and OWASP insecure inter-agent communication risk.

7. **Rogue-agent containment**
   - Audit logs exist, but there is no visible quarantine, kill switch, or automated disable path.

8. **Centralized anomaly detection**
   - Deny/allow logging exists, but not a richer behavioral analytics layer for unusual tool use, escalation, or data access.

9. **Human approval workflows for sensitive operations**
   - `SAFE_ADMIN` has confirmation semantics, but there is no generalized approval framework for high-risk actions, thresholds, or dual control.

10. **Tamper-evident audit and SIEM export**
    - Local audit buffers are useful, but enterprise practice expects durable export to centralized monitoring.

### Lower priority but still valuable

11. **Tenant-aware authorization model**
    - Especially important if Agentic Brain becomes multi-tenant SaaS.

12. **RAG provenance and memory-poisoning defenses**
    - Prompt filtering is good, but OWASP 2026 also pushes hard on memory/context poisoning and source provenance.

13. **Policy simulation / explainability tooling**
    - Useful for answering "why was this action allowed?" before rollout.

## Recommendations

### Recommended next step 1: Add policy-as-code

Introduce a policy engine for high-risk decisions:

- OPA/Rego, Cedar, or a lightweight internal policy DSL
- keep current Python guards as enforcement hooks
- move final allow/deny logic for sensitive actions into versioned policies

This gives Agentic Brain stronger parity with Microsoft-style runtime governance without losing its current simplicity.

### Recommended next step 2: Add fine-grained authz for business data

For WordPress/WooCommerce and future business APIs, add resource-scoped authorization checks such as:

- subject
- tenant/site/store
- resource type
- resource owner
- requested action
- acting-on-behalf-of user

This is the biggest gap relative to Zanzibar/Warrant-style systems.

### Recommended next step 3: Add agent identity and delegated auth

Adopt an agent identity model for automation flows:

- unique agent IDs
- short-lived credentials
- explicit user-delegation records
- on-behalf-of token exchange
- revocation support

This aligns with IETF direction and enterprise buyer expectations.

### Recommended next step 4: Add containment controls

Add operational controls for unsafe or compromised agents:

- emergency pause / disable
- quarantine mode
- disable specific tools/providers
- freeze YOLO for a role/session
- forced step-up approval

### Recommended next step 5: Strengthen audit and monitoring

Persist security events to a durable store and emit to centralized monitoring with fields like:

- user or agent identity
- delegated identity
- role
- tool or API invoked
- resource touched
- prompt-filter action
- policy matched
- allow/deny outcome
- risk score

## OWASP Agentic AI Top 10 Compliance Snapshot

| OWASP 2026 risk | Current status | Notes |
|---|---|---|
| Agent goal hijacking | ⚠️ Partial | Prompt filtering helps, but there is no broader runtime intent validation or policy engine. |
| Tool misuse and exploitation | ✅ / ⚠️ Partial | Stronger than average because shell/code access is role-gated, but still lacks richer per-tool policy and anomaly detection. |
| Identity and privilege abuse | ⚠️ Partial | Good role separation, but missing first-class agent identity, delegated auth, and external IdP integration. |
| Unexpected code execution | ✅ / ⚠️ Partial | Better than most because execution is explicit and gated, but sandboxing/isolation is not evident here. |
| Insecure inter-agent communication | ❌ Gap | Not addressed in the reviewed files. |
| Human-agent trust exploitation | ⚠️ Partial | Some safety exists, but no explicit explainability, consent, or phishing-resistant approval UX. |
| Agentic supply chain vulnerabilities | ❌ Gap | Not addressed in the reviewed security layer. |
| Memory and context poisoning | ⚠️ Partial | Prompt filtering helps, but RAG/memory provenance and poisoning controls are not evident here. |
| Cascading failures | ❌ / ⚠️ Gap | No visible containment, dependency isolation, or circuit-breaker logic in this layer. |
| Rogue agents | ❌ Gap | Audit exists, but no kill switch, attestation, or continuous trust evaluation. |

## Practical Positioning

### Where Agentic Brain is stronger than expected

Agentic Brain is ahead of many early-stage agent systems because it already combines:

- runtime RBAC
- LLM-layer restrictions
- shell/code execution controls
- guest/public commerce context
- audit logging

That is a serious foundation.

### Where industry leaders are ahead

The leading frameworks go further in three areas:

1. **enterprise identity**
2. **fine-grained authorization**
3. **centralized runtime governance**

If Agentic Brain adds those three capabilities, it will move from a strong project-level security model to a more enterprise-grade agent governance model.

## Suggested Roadmap

### Phase 1

- durable audit logging
- risk scoring for sensitive actions
- emergency pause / quarantine
- explicit approval workflow for high-risk operations

### Phase 2

- policy-as-code for sensitive actions
- resource-level authorization for commerce/business APIs
- tenant-aware authorization context

### Phase 3

- agent identity issuance
- OAuth delegated auth / on-behalf-of support
- inter-agent auth and signed message flows
- provenance checks for memory/RAG sources

## Evidence from Current Implementation

- Four-tier role model and permission matrix: `src/agentic_brain/security/roles.py`
- Runtime checks, rate limiting, and audit events: `src/agentic_brain/security/guards.py`
- LLM provider restrictions, role inference, and rate limiting: `src/agentic_brain/security/llm_guard.py`
- Prompt injection and code/file request filtering: `src/agentic_brain/security/prompt_filter.py`
- Security architecture and WordPress/WooCommerce mapping: `docs/SECURITY_IMPLEMENTATION.md`, `docs/WORDPRESS_ROLE_MAPPING.md`

## External Reference Points

This document was informed by current 2026 web research on:

- Microsoft Agent Governance Toolkit runtime policy model
- Microsoft Agent Framework / Azure Foundry RBAC and agent identity
- Protecto runtime RBAC and AD integration
- Zanzibar / Warrant fine-grained authorization patterns
- IETF AI agent auth drafts using OAuth 2.0 and workload identity
- OWASP Top 10 for Agentic Applications (2026)

Representative references:

- Microsoft Agent Governance Toolkit: <https://github.com/microsoft/agent-governance-toolkit>
- Microsoft announcement: <https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/>
- Microsoft Foundry agent identity: <https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity>
- Protecto RBAC for agents: <https://www.protecto.ai/solutions/agentic-ai-rbac-for-agents/>
- Warrant: <https://warrant.dev/>
- Warrant GitHub: <https://github.com/warrant-dev/warrant>
- IETF AI agent auth draft: <https://www.ietf.org/archive/id/draft-klrc-aiagent-auth-00.html>
- IETF OAuth on-behalf-of draft for AI agents: <https://datatracker.ietf.org/doc/draft-oauth-ai-agents-on-behalf-of-user/02/>
- OWASP Top 10 for Agentic Applications for 2026: <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>
