# Model Guide - Agentic Brain LLM Reference

> **Last Verified: March 2026**  
> **NOTE: AI models and pricing change RAPIDLY. Verify on provider websites before committing.**

> **SOURCE OF TRUTH** - When nothing else makes sense, come here.  
> **Assumption-free** - Every step explained. Nothing skipped.  
> **Accessible** - Screen reader friendly. Works for everyone.  
> **Australian Localised** - Prices in both USD and AUD (1 USD = 1.42 AUD, as of March 2026)

---

## 🗺️ Which Model Should I Use? (Decision Flowchart)

```
                    ┌─────────────────────────┐
                    │   What do you need?     │
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
   ┌─────────┐            ┌─────────┐            ┌─────────┐
   │ PRIVACY │            │  SPEED  │            │ QUALITY │
   │ Offline │            │  Fast   │            │  Best   │
   └────┬────┘            └────┬────┘            └────┬────┘
        │                      │                      │
        ▼                      ▼                      ▼
   ┌─────────┐            ┌─────────┐            ┌─────────┐
   │ LOCAL   │            │  GROQ   │            │ Claude/ │
   │ L1, L2  │            │ GR, GR2 │            │ OpenAI  │
   │  FREE   │            │  FREE   │            │  PAID   │
   └─────────┘            └─────────┘            └─────────┘


         ┌─────────────────────────────────────┐
         │        BUDGET DECISION TREE         │
         └─────────────────────┬───────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
         ┌────────┐       ┌────────┐       ┌────────┐
         │  FREE  │       │ CHEAP  │       │ BEST   │
         │ $0/mo  │       │ <$20   │       │ Any $  │
         └───┬────┘       └───┬────┘       └───┬────┘
             │                │                │
             ▼                ▼                ▼
    ┌────────────────┐ ┌────────────┐ ┌────────────────┐
    │ L1 → L2 → GR   │ │ OP2 → CL2  │ │ CL → OP → CL3  │
    │ → GO (rotate)  │ │ (alternate)│ │ (best quality) │
    └────────────────┘ └────────────┘ └────────────────┘
```

**Don't know? Use a Template** → Jump to [Configuration Templates](#-configuration-templates)

---

## Table of Contents

1. [🔒 Data Privacy - READ FIRST](#-data-privacy---read-first)
2. [🎯 Configuration Templates](#-configuration-templates) ← **Start here if unsure!**
3. [Quick Start - 2 Minutes to Running](#quick-start---2-minutes-to-running)
4. [Model Codes - Fast Switching](#model-codes---fast-switching)
5. [Provider Setup - Windows/Mac/Linux](#provider-setup---windowsmaclinux)
6. [Pricing Tables - USD and AUD](#pricing-tables---usd-and-aud)
7. [Capability Matrix](#capability-matrix)
8. [Recommended Defaults](#recommended-defaults)
9. [Fallback System](#fallback-system)
10. [Troubleshooting](#troubleshooting)
11. [Pros and Cons](#pros-and-cons)

---

## 🔒 Data Privacy - READ FIRST

> **This is the most important section.** Your data is YOUR data. 
> We hide nothing. Here's exactly what each provider does with your prompts.

### Quick Privacy Summary (March 2026)

| Provider | Code | Trains on API Data? | Data Shared Publicly? | Data Retention | Privacy Rating |
|----------|------|---------------------|----------------------|----------------|----------------|
| **Ollama (Local)** | L1-L4 | ❌ NO - runs on YOUR machine | ❌ NO - never leaves your computer | You control | ⭐⭐⭐⭐⭐ BEST |
| **Groq** | GR, GR2 | ❌ NO | ❌ NO | 30 days max | ⭐⭐⭐⭐ Great |
| **Google Gemini API** | GO, GO2 | ❌ NO (API) | ❌ NO | Processing only | ⭐⭐⭐⭐ Great |
| **Anthropic Claude API** | CL, CL2, CL3 | ❌ NO | ❌ NO | Processing only | ⭐⭐⭐⭐ Great |
| **OpenAI API** | OP, OP2, OP3 | ❌ NO (API default) | ❌ NO | 30 days (abuse monitoring) | ⭐⭐⭐⭐ Great |
| **X.AI Grok API** | XK, XK2 | ❌ NO (API default) | ❌ NO | 30 days | ⭐⭐⭐ Good |
| **X.AI Grok via X/Twitter** | - | ⚠️ YES (default) | ⚠️ Public posts used | Indefinite | ⭐⭐ Caution |

### Detailed Privacy Breakdown

#### 🟢 LOCAL (Ollama) - MAXIMUM PRIVACY
```
✅ Data NEVER leaves your computer
✅ No internet connection required
✅ No account needed
✅ No logging, no tracking
✅ You own everything
✅ Works offline forever

Perfect for: Medical data, legal documents, financial info, trade secrets
```

#### 🟢 GROQ - Very Private
```
✅ API data NOT used for training
✅ Data deleted after 30 days max
✅ No public sharing
✅ GDPR compliant
⚠️ Requires internet connection
⚠️ Data passes through Groq servers

Perfect for: General business use, development, testing
```

#### 🟢 GOOGLE GEMINI API - Very Private  
```
✅ API data NOT used for training
✅ Encrypted in transit and at rest
✅ Only used to deliver your request
⚠️ Consumer Gemini app DOES use data (different product!)
⚠️ Must use API, not the free web app

Perfect for: Enterprise, business applications
```

#### 🟢 ANTHROPIC CLAUDE API - Very Private
```
✅ API data NOT used for training (confirmed)
✅ No manual review unless security issue
✅ Deleted after processing
✅ Enterprise has zero retention option
⚠️ Consumer Claude chat MAY use data (opt-out available)

Perfect for: Sensitive business data, confidential work
```

#### 🟢 OPENAI API - Very Private (API only)
```
✅ API data NOT used for training by default
✅ Zero data retention available for Enterprise
⚠️ Data retained up to 30 days for abuse monitoring
⚠️ Free ChatGPT DOES use data for training (different!)
⚠️ ChatGPT Plus uses data unless you opt out

Perfect for: Business use via API
```

#### 🟡 X.AI GROK API - Good (with caveats)
```
✅ Enterprise/API data NOT used for training by default
⚠️ No public free tier for new users - assume pay-as-you-go via console.x.ai
⚠️ 30 day retention
⚠️ If using via X/Twitter, your PUBLIC posts ARE used for training
❌ X platform data shared with third parties by default

Be careful: Separate your API use from X/Twitter account
```

### ⚠️ WARNING: Consumer Apps vs APIs

**THIS IS CRITICAL TO UNDERSTAND:**

| Product | Uses Your Data for Training? |
|---------|------------------------------|
| **ChatGPT Free** | ⚠️ YES (opt-out in settings) |
| **ChatGPT Plus** | ⚠️ YES by default (opt-out available) |
| **OpenAI API** | ❌ NO |
| **Claude Chat Free** | ⚠️ May use (opt-out available) |
| **Claude API** | ❌ NO |
| **Gemini App Free** | ⚠️ YES |
| **Gemini API** | ❌ NO |
| **Grok via X/Twitter** | ⚠️ YES (public posts) |
| **Grok API** | ❌ NO |

**Rule: Always use the API, not the free consumer app, for private data.**

### 🛡️ Our Recommendation for Maximum Privacy

1. **Most sensitive data** → Use LOCAL only (L1, L2, L3)
2. **Business confidential** → Use API providers (not consumer apps)
3. **General work** → Any API provider is fine
4. **Never** → Put secrets in free consumer chat apps

### Data Privacy Settings Checklist

Before using any provider, verify these settings:

- [ ] **OpenAI**: Settings → Data Controls → Turn OFF "Improve the model"
- [ ] **Anthropic**: Review privacy settings at console.anthropic.com
- [ ] **Google**: Use API (aistudio.google.com), NOT consumer app
- [ ] **X.AI/Grok**: Settings → Privacy → Turn OFF data sharing
- [ ] **X/Twitter**: Privacy → Grok → Turn OFF "Allow your posts to train Grok"

### Australian Privacy Note (Privacy Act 1988)

Under Australian law, you have rights regarding your personal information:
- Right to know what data is collected
- Right to access your data
- Right to correct inaccurate data
- Right to complain to OAIC (oaic.gov.au)

If using AI for Australian clients, ensure your provider's data handling meets Privacy Act requirements. **Local models (Ollama) are the safest choice for regulated industries.**

---

## 🎯 Configuration Templates - Choose Your Profile

> **Pick the template that matches you.** Copy the `.env` config and you're done.
> Each template has sensible defaults for fallback, privacy, and cost.

### Template Overview

| Template | Best For | Privacy | Cost | Internet Required? |
|----------|----------|---------|------|-------------------|
| 🔒 **Privacy First** | Lawyers, doctors, finance | ⭐⭐⭐⭐⭐ | FREE | ❌ No |
| 💰 **Budget Zero** | Students, hobbyists | ⭐⭐⭐⭐ | FREE | ✅ Yes |
| ⚡ **Speed Demon** | High volume, real-time | ⭐⭐⭐⭐ | FREE | ✅ Yes |
| 💼 **Business Standard** | SMB, consultants | ⭐⭐⭐⭐ | $20-50/mo | ✅ Yes |
| 🏢 **Enterprise** | Large orgs, compliance | ⭐⭐⭐⭐⭐ | $100+/mo | ✅ Yes |
| 👨‍💻 **Developer** | Coding, debugging | ⭐⭐⭐⭐ | $10-30/mo | ✅ Yes |
| 🎨 **Creative** | Writing, content | ⭐⭐⭐⭐ | $10-30/mo | ✅ Yes |
| 🌏 **Aussie Default** | Joseph's recommended | ⭐⭐⭐⭐⭐ | FREE-$20 | Optional |

---

### 🔒 Template: Privacy First

**For:** Lawyers, doctors, accountants, anyone handling sensitive client data

**Philosophy:** Data NEVER leaves your machine. No cloud. No exceptions.

```bash
# .env - Privacy First Template
# Last verified: March 2026

# === ONLY LOCAL MODELS ===
OLLAMA_HOST=http://localhost:11434
DEFAULT_MODEL=L2
FALLBACK_CHAIN=L2,L1,L3

# === NO CLOUD PROVIDERS ===
# (intentionally empty - we don't use cloud)

# === PRIVACY SETTINGS ===
ALLOW_CLOUD_FALLBACK=false
OFFLINE_MODE=true
LOG_PROMPTS=false
```

**Fallback chain:** `L2 → L1 → L3` (all local, all private)

**RAM required:** 8GB minimum (for L2)

**Pros:** 
- Maximum privacy - data never leaves your computer
- Works offline (planes, outback, anywhere)
- No monthly costs ever
- Compliant with Privacy Act, HIPAA, GDPR

**Cons:**
- Need decent hardware (8GB+ RAM)
- Not as smart as cloud models
- No internet features

---

### 💰 Template: Budget Zero

**For:** Students, hobbyists, learners, anyone who can't spend money

**Philosophy:** Get the best AI possible without spending a cent.

```bash
# .env - Budget Zero Template
# Last verified: March 2026

# === FREE LOCAL ===
OLLAMA_HOST=http://localhost:11434

# === FREE CLOUD ===
GROQ_API_KEY=gsk_your_key_here
GOOGLE_API_KEY=your_key_here

# === SETTINGS ===
DEFAULT_MODEL=GR
FALLBACK_CHAIN=GR,GR2,GO,L1,L2
COST_LIMIT=0
ALLOW_PAID=false
```

**Fallback chain:** `GR → GR2 → GO → L1 → L2` (all FREE)

**RAM required:** 4GB minimum

**Monthly cost:** $0 (forever)

**Pros:**
- Completely free
- Access to powerful cloud models
- Good fallback to local if internet down

**Cons:**
- Rate limits on free tiers
- Must accept provider privacy policies
- Internet required for cloud models

---

### ⚡ Template: Speed Demon

**For:** Real-time apps, chatbots, high-volume processing

**Philosophy:** Fastest possible response, cost secondary.

```bash
# .env - Speed Demon Template
# Last verified: March 2026

# === FAST LOCAL ===
OLLAMA_HOST=http://localhost:11434

# === FAST CLOUD ===
GROQ_API_KEY=gsk_your_key_here
GOOGLE_API_KEY=your_key_here
OPENAI_API_KEY=sk-your_key_here

# === SETTINGS ===
DEFAULT_MODEL=GR
FALLBACK_CHAIN=GR,L1,GR2,GO,OP2
PREFER_SPEED=true
MAX_LATENCY_MS=2000
```

**Fallback chain:** `GR → L1 → GR2 → GO → OP2` (speed-optimized)

**Why this order:**
- GR (Groq): 300+ tokens/sec - fastest cloud
- L1: Local = no network latency
- GR2: Groq smaller model = even faster
- GO: Gemini Flash = fast
- OP2: GPT-4o-mini = fast fallback

**Expected latency:** <500ms first token

---

### 💼 Template: Business Standard

**For:** Small business, consultants, freelancers

**Philosophy:** Balance quality, cost, and reliability for professional use.

```bash
# .env - Business Standard Template
# Last verified: March 2026

# === LOCAL BACKUP ===
OLLAMA_HOST=http://localhost:11434

# === CLOUD PROVIDERS ===
GROQ_API_KEY=gsk_your_key_here
GOOGLE_API_KEY=your_key_here
OPENAI_API_KEY=sk-your_key_here
ANTHROPIC_API_KEY=sk-ant-your_key_here

# === SETTINGS ===
DEFAULT_MODEL=CL
FALLBACK_CHAIN=CL,OP,GR,GO,CL2,OP2,L2,L1
MONTHLY_BUDGET_USD=50
MONTHLY_BUDGET_AUD=71
```

**Fallback chain:** `CL → OP → GR → GO → CL2 → OP2 → L2 → L1`

**Why this order:**
- Start with quality (Claude, OpenAI)
- Fall back to free cloud (Groq, Gemini)
- Fall back to cheap paid (Haiku, Mini)
- Last resort: local (always works)

**Expected cost:** $20-50 USD / $28-71 AUD per month

---

### 🏢 Template: Enterprise

**For:** Large organisations, compliance-heavy industries, government

**Philosophy:** Maximum quality, full audit trail, zero data leakage.

```bash
# .env - Enterprise Template
# Last verified: March 2026

# === LOCAL (air-gapped option) ===
OLLAMA_HOST=http://localhost:11434

# === ENTERPRISE CLOUD ===
OPENAI_API_KEY=sk-your_key_here
ANTHROPIC_API_KEY=sk-ant-your_key_here
# Note: Use enterprise agreements with zero data retention

# === SETTINGS ===
DEFAULT_MODEL=CL3
FALLBACK_CHAIN=CL3,CL,OP,OP3,L2
ENABLE_AUDIT_LOG=true
LOG_ALL_REQUESTS=true
ZERO_DATA_RETENTION=true
REQUIRE_ENTERPRISE_AGREEMENT=true
```

**Fallback chain:** `CL3 → CL → OP → OP3 → L2`

**Why this order:**
- Best quality first (Opus, Sonnet)
- Trusted providers only
- Local backup for outages

**Compliance features:**
- ✅ SOC 2 Type II (OpenAI, Anthropic)
- ✅ GDPR compliant
- ✅ Zero data retention available
- ✅ BAA for HIPAA (request from provider)
- ✅ Audit logging

---

### 👨‍💻 Template: Developer

**For:** Programmers, debugging, code review, technical work

**Philosophy:** Best coding models, fast iteration, good error messages.

```bash
# .env - Developer Template
# Last verified: March 2026

# === LOCAL ===
OLLAMA_HOST=http://localhost:11434

# === CLOUD ===
GROQ_API_KEY=gsk_your_key_here
OPENAI_API_KEY=sk-your_key_here
ANTHROPIC_API_KEY=sk-ant-your_key_here

# === SETTINGS ===
DEFAULT_MODEL=CL
FALLBACK_CHAIN=CL,OP,GR,L2,OP2,CL2
CODING_MODE=true
INCLUDE_LINE_NUMBERS=true
SYNTAX_HIGHLIGHTING=true
```

**Fallback chain:** `CL → OP → GR → L2 → OP2 → CL2`

**Why this order:**
- Claude: Best at understanding codebases
- OpenAI: Great at code generation
- Groq: Fast for quick questions
- L2 (8B): Good local coding model
- Mini/Haiku: Budget fallback

**Best for:**
- Code review
- Debugging
- Refactoring
- Documentation
- Test writing

---

### 🎨 Template: Creative

**For:** Writers, content creators, marketing, brainstorming

**Philosophy:** Best prose quality, creative expression, varied outputs.

```bash
# .env - Creative Template
# Last verified: March 2026

# === LOCAL ===
OLLAMA_HOST=http://localhost:11434

# === CLOUD ===
ANTHROPIC_API_KEY=sk-ant-your_key_here
OPENAI_API_KEY=sk-your_key_here
GOOGLE_API_KEY=your_key_here

# === SETTINGS ===
DEFAULT_MODEL=CL3
FALLBACK_CHAIN=CL3,CL,OP,GO2,L3
CREATIVE_MODE=true
TEMPERATURE=0.8
```

**Fallback chain:** `CL3 → CL → OP → GO2 → L3`

**Why this order:**
- Claude Opus: Best creative writing
- Claude Sonnet: Great prose
- GPT-4o: Creative and fast
- Gemini Pro: Good for brainstorming
- Mistral (L3): Good European language model

---

### 🌏 Template: Aussie Default (Joseph's Recommended)

**For:** Australian users who want a sensible, balanced setup

**Philosophy:** Privacy-conscious, cost-effective, works offline, good quality when online.

```bash
# .env - Aussie Default Template
# Last verified: March 2026
# Recommended by Joseph Webber, Adelaide SA

# === LOCAL FIRST (Privacy + Offline) ===
OLLAMA_HOST=http://localhost:11434

# === FREE CLOUD (No Credit Card) ===
GROQ_API_KEY=gsk_your_key_here
GOOGLE_API_KEY=your_key_here

# === PAID CLOUD (Optional - for quality) ===
# Uncomment if you want paid models:
# ANTHROPIC_API_KEY=sk-ant-your_key_here
# OPENAI_API_KEY=sk-your_key_here

# === SETTINGS ===
DEFAULT_MODEL=L2
FALLBACK_CHAIN=L2,L1,GR,GO,GR2
PREFER_LOCAL=true
OFFLINE_CAPABLE=true

# === AUSTRALIAN SETTINGS ===
TIMEZONE=Australia/Adelaide
CURRENCY=AUD
GST_RATE=0.10
LOCALE=en-AU
```

**Fallback chain:** `L2 → L1 → GR → GO → GR2`

**Why this order:**
1. **L2 first**: Quality local, private, works offline
2. **L1 fallback**: Faster local if L2 busy
3. **GR**: Best free cloud (super fast)
4. **GO**: Google free tier backup
5. **GR2**: High-volume Groq fallback

**Monthly cost:** $0 (unless you enable paid providers)

**Why this is the Aussie default:**
- ✅ Works in the outback (offline mode)
- ✅ No credit card required
- ✅ Privacy-first (local preferred)
- ✅ Free cloud backup when online
- ✅ GST-aware for paid services
- ✅ Adelaide timezone by default 😊

---

### 🔧 How to Use a Template

1. **Copy the `.env` block** from your chosen template
2. **Paste into** `/Users/you/brain/agentic-brain/.env`
3. **Replace API keys** with your actual keys
4. **Run:** `agentic chat` - it will use your defaults

### Switching Templates

You can switch templates anytime:
```bash
# Backup current config
cp .env .env.backup

# Copy new template
cp templates/privacy-first.env .env

# Restart agentic-brain
agentic restart
```

---

### Absolute Fastest Path (No Credit Card Required)

**Step 1: Install Ollama** (60 seconds)
```bash
# Mac
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows - download from https://ollama.com/download
```

**Step 2: Pull a Model** (60 seconds)
```bash
ollama pull llama3.2:3b
```

**Step 3: Test It** (10 seconds)
```bash
ollama run llama3.2:3b "Say hello"
```

**Done! You now have a working AI on your machine.**

---

### Which Model Should I Use?

| Your Situation | Use This | Why |
|----------------|----------|-----|
| Just want it to work | **L1** | Free, runs on your computer, no internet needed |
| Have 4GB RAM or less | **GR** or **GO** | Free cloud, no local install |
| Want best quality | **CL** | Claude is smartest for reasoning |
| Writing code | **OP** | OpenAI best for coding |
| Need speed | **GR** | Groq is fastest (300+ tokens/sec) |
| Privacy matters | **L1** or **L2** | Data never leaves your computer |
| On a budget | **L1**, **GO**, **GR** | All completely FREE |
| Need reasoning | **DeepSeek-R1** | Dedicated reasoning model |

---

## Model Codes - Fast Switching

We use short codes so you can switch models fast. Type the code, hit enter.

### The Pattern

```
[PROVIDER][TIER]

Provider = Where it runs
Tier = Quality level (1=best value, 2=budget, 3=premium)
```

### All Models (March 2026 - Verified)

#### LOCAL Models (Ollama - FREE Forever)

| Code | Full Name | RAM Needed | Speed | Best For |
|------|-----------|------------|-------|----------|
| **L1** | llama3.2:3b | 4GB | ⚡⚡⚡⚡ | Quick tasks, drafts, low-spec machines |
| **L2** | llama3.1:8b | 8GB | ⚡⚡⚡ | Quality coding, analysis |
| **L3** | mistral:7b | 8GB | ⚡⚡⚡ | European languages, creative writing |
| **L4** | llama3.3:70b | 32GB+ | ⚡⚡ | Maximum local quality (optional) |
| **DSR** | DeepSeek-R1 | Varies | ⚡⚡ | Reasoning, logic, math |

#### CLOUD Models - FREE Tier

| Code | Full Name | Provider | Limits | Best For |
|------|-----------|----------|--------|----------|
| **GR** | llama-3.3-70b-versatile | Groq | 30 req/min, 6K tok/min, 100K tok/day | Speed |
| **GR2** | llama-3.1-8b-instant | Groq | 30 req/min, 6K tok/min, 500K tok/day | High volume |
| **GO** | gemini-2.5-flash | Google | 15 req/min, 1M context | Long documents |
| **GO2** | gemini-2.5-pro | Google | Free tier available | Advanced reasoning |
> **Note:** Groq ≠ Grok! 
> - **Groq** (GR) = Fast inference company, runs Llama models at 300+ tokens/sec
> - **Grok** (XK) = Elon Musk's X.AI model, integrates with Twitter/X

#### CLOUD Models - PAID

| Code | Full Name | Provider | Input Cost | Output Cost |
|------|-----------|----------|------------|-------------|
| **OP** | gpt-4o | OpenAI | $2.50/1M | $10.00/1M |
| **OP2** | gpt-4o-mini | OpenAI | $0.15/1M | $0.60/1M |
| **OP3** | gpt-5-mini | OpenAI | $0.25/1M | $2.00/1M |
| **CL** | claude-sonnet-4-6 | Anthropic | $3.00/1M | $15.00/1M |
| **CL2** | claude-haiku-4-5 | Anthropic | ~$0.25/1M | ~$1.25/1M |
| **CL3** | claude-opus-4-6 | Anthropic | $5.00/1M | $25.00/1M |
| **XK** | grok-4.1-fast | X.AI (Grok) | ~$3.00/1M | ~$15.00/1M |
| **XK2** | grok-3-mini | X.AI (Grok) | ~$0.20/1M | ~$0.50/1M |

> **Grok note:** Requires X Premium for API access via console.x.ai. No free tier or monthly free credits for new users.

### Cost Key (USD Monthly - Heavy Use)

| Symbol | Meaning | Typical Cost |
|--------|---------|--------------|
| FREE | No charge ever | $0 |
| $ | Budget | $5-20 USD / $7-28 AUD |
| $$ | Moderate | $20-50 USD / $28-71 AUD |
| $$$ | Expensive | $50-200 USD / $71-284 AUD |
| $$$$ | Premium | $200+ USD / $284+ AUD |

### 🔌 Works Offline Badges

| Code | Model | Works Offline? | Internet Required? |
|------|-------|----------------|-------------------|
| L1 | llama3.2:3b | ✅ YES | Never |
| L2 | llama3.1:8b | ✅ YES | Never |
| L3 | mistral:7b | ✅ YES | Never |
| L4 | llama3.3:70b | ✅ YES | Never |
| DSR | DeepSeek-R1 | ✅ YES | Never |
| GR | Groq Llama 70B | ❌ NO | Always |
| GR2 | Groq Llama 8B | ❌ NO | Always |
| GO | Gemini Flash | ❌ NO | Always |
| GO2 | Gemini Pro | ❌ NO | Always |
| XK | Grok 4.1 | ❌ NO | Always |
| XK2 | Grok 3 mini | ❌ NO | Always |
| OP | GPT-4o | ❌ NO | Always |
| OP2 | GPT-4o-mini | ❌ NO | Always |
| OP3 | GPT-5-mini | ❌ NO | Always |
| CL | Claude Sonnet | ❌ NO | Always |
| CL2 | Claude Haiku | ❌ NO | Always |
| CL3 | Claude Opus | ❌ NO | Always |

**🛫 Key insight**: Local models (L1-L4, DSR) work on planes, trains, outback - anywhere!

---

## Provider Setup - Windows/Mac/Linux

### Overview - What You Need

| Provider | Difficulty | Time | Credit Card? | Sign-up URL |
|----------|------------|------|--------------|-------------|
| **Ollama (L1-L4, DSR)** | Easy | 5 min | No | ollama.com |
| **Groq (GR, GR2)** | Easy | 2 min | No | console.groq.com |
| **Google Gemini (GO, GO2)** | Easy | 3 min | No | aistudio.google.com |
| **OpenAI (OP, OP2, OP3)** | Medium | 5 min | Yes | platform.openai.com |
| **Anthropic (CL, CL2, CL3)** | Medium | 5 min | Yes | console.anthropic.com |

---

### Setup: Ollama (Local Models - FREE Forever)

**What is Ollama?** Software that runs AI models on YOUR computer. Free forever. Works offline. Your data never leaves your machine.

#### Step 1: Install Ollama

**🍎 macOS:**
```bash
# Option A: Homebrew (recommended if you have it)
brew install ollama

# Option B: Direct download
# 1. Open browser, go to: https://ollama.com/download
# 2. Click "Download for macOS"
# 3. Open the downloaded .dmg file
# 4. Drag Ollama to Applications folder
# 5. Open Ollama from Applications
# 6. You'll see the Ollama icon (llama) in your menu bar
```

**🪟 Windows:**
```
1. Open your browser
2. Go to: https://ollama.com/download
3. Click "Download for Windows"
4. Run the downloaded OllamaSetup.exe
5. Click "Next" through the installer
6. Restart your terminal/PowerShell after installation
```

**🐧 Linux:**
```bash
# One command install (works on Ubuntu, Debian, Fedora, etc.)
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

#### Step 2: Start Ollama Service

**macOS:** Ollama starts automatically when you open it. Look for the llama icon in your menu bar.

**Windows:** Ollama starts automatically after installation. Check System Tray.

**Linux:** 
```bash
# Start Ollama service
ollama serve

# Or run in background
ollama serve &
```

#### Step 3: Download Models

Open Terminal (Mac/Linux) or PowerShell (Windows):

```bash
# L1 - Fast model (2GB download) - 4GB RAM required
ollama pull llama3.2:3b

# L2 - Quality model (5GB download) - 8GB RAM required
ollama pull llama3.1:8b

# L3 - European alternative (5GB download) - 8GB RAM required
ollama pull mistral:7b

# L4 - Flagship (Optional, 40GB download) - 32GB+ RAM required
ollama pull llama3.3:70b

# DSR - DeepSeek Reasoning (various sizes)
ollama pull deepseek-r1:7b    # 7B version - 8GB RAM
ollama pull deepseek-r1:32b   # 32B version - 20GB RAM
```

#### Step 4: Test It Works

```bash
# Test the model
ollama run llama3.2:3b "Say hello in Australian slang"

# You should see a response. Press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows) to exit.
```

#### Step 5: Configure for Agentic Brain

The default Ollama endpoint is `http://localhost:11434`. No environment variable needed unless you change it.

**Optional:** Custom port
```bash
# Mac/Linux - add to ~/.zshrc or ~/.bashrc
export OLLAMA_HOST="http://localhost:11434"

# Windows PowerShell - add to $PROFILE
$env:OLLAMA_HOST = "http://localhost:11434"
```

#### Ollama Common Issues

| Problem | Solution |
|---------|----------|
| "ollama: command not found" | Restart your terminal. On Linux, run `source ~/.bashrc` |
| Download stuck | Check internet connection. Try: `ollama pull --verbose MODEL` |
| "out of memory" | Use smaller model (L1). Close other apps. |
| "model not found" | Run `ollama list` to see installed models |
| Slow responses | Normal for first run (model loading). Subsequent runs are faster. |
| Port 11434 in use | Stop existing Ollama: `pkill ollama` then `ollama serve` |

---

### Setup: Groq (FREE Cloud - Fastest)

**What is Groq?** The FASTEST AI inference in the world. Free tier is generous. No credit card needed.

**Sign-up URL:** https://console.groq.com

#### Step 1: Create Account

1. Go to: https://console.groq.com
2. Click "Sign Up"  
3. Use Google account OR email + password
4. Verify your email (check inbox and spam folder)
5. Complete any onboarding prompts

#### Step 2: Get API Key

1. After login, you'll see the GroqCloud Console
2. Click "API Keys" in the left sidebar
3. Click "Create API Key"
4. Name it something memorable: `agentic-brain` or `my-ai-key`
5. Click "Create"
6. **⚠️ COPY THE KEY IMMEDIATELY** - You only see it once!

The key looks like: `gsk_xxxxxxxxxxxxxxxxxxxxxxxxxx`

#### Step 3: Save the Key

**🍎 macOS:**
```bash
# Add to your shell config (one-time setup)
echo 'export GROQ_API_KEY="gsk_your_key_here"' >> ~/.zshrc

# Apply immediately
source ~/.zshrc

# Verify it's set
echo $GROQ_API_KEY
```

**🪟 Windows (PowerShell as Administrator):**
```powershell
# Set permanent environment variable
[System.Environment]::SetEnvironmentVariable('GROQ_API_KEY', 'gsk_your_key_here', 'User')

# Restart PowerShell, then verify
echo $env:GROQ_API_KEY
```

**🪟 Windows (Command Prompt as Administrator):**
```cmd
setx GROQ_API_KEY "gsk_your_key_here"
:: Close and reopen Command Prompt, then verify
echo %GROQ_API_KEY%
```

**🐧 Linux:**
```bash
# Add to your shell config
echo 'export GROQ_API_KEY="gsk_your_key_here"' >> ~/.bashrc

# Apply immediately
source ~/.bashrc

# Verify
echo $GROQ_API_KEY
```

#### Step 4: Test It Works

**macOS/Linux:**
```bash
curl -X POST "https://api.groq.com/openai/v1/chat/completions" \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Say G'day mate!"}]}'
```

**Windows PowerShell:**
```powershell
$headers = @{
    "Authorization" = "Bearer $env:GROQ_API_KEY"
    "Content-Type" = "application/json"
}
$body = '{"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Say G''day mate!"}]}'
Invoke-RestMethod -Uri "https://api.groq.com/openai/v1/chat/completions" -Method POST -Headers $headers -Body $body
```

#### Groq Free Tier Limits (March 2026 - Verified)

| Model | Requests/Min | Tokens/Min | Tokens/Day |
|-------|--------------|------------|------------|
| llama-3.3-70b-versatile | 30 | 6,000 | 100,000 |
| llama-3.1-8b-instant | 30 | 6,000 | 500,000 |
| mixtral-8x7b-32768 | 30 | 5,000 | 500,000 |
| gemma2-9b-it | 30 | 15,000 | 500,000 |

**These limits are very generous for personal use and small teams.**

---

### Setup: Google Gemini (FREE Cloud - 1M Context)

**What is Gemini?** Google's AI. The free tier includes the incredible 1 million token context window. No credit card needed.

**Sign-up URL:** https://aistudio.google.com

#### Step 1: Get API Key

1. Go to: https://aistudio.google.com
2. Sign in with your Google account (or create one)
3. Click "Get API Key" (top-left button or sidebar)
4. Click "Create API Key"
5. Select "Create API key in new project" 
6. **⚠️ COPY THE KEY IMMEDIATELY**

The key looks like: `AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxx`

#### Step 2: Save the Key

**🍎 macOS:**
```bash
echo 'export GOOGLE_API_KEY="AIzaSy_your_key_here"' >> ~/.zshrc
source ~/.zshrc
echo $GOOGLE_API_KEY
```

**🪟 Windows (PowerShell as Administrator):**
```powershell
[System.Environment]::SetEnvironmentVariable('GOOGLE_API_KEY', 'AIzaSy_your_key_here', 'User')
# Restart PowerShell, then verify
echo $env:GOOGLE_API_KEY
```

**🪟 Windows (Command Prompt as Administrator):**
```cmd
setx GOOGLE_API_KEY "AIzaSy_your_key_here"
:: Close and reopen, then verify
echo %GOOGLE_API_KEY%
```

**🐧 Linux:**
```bash
echo 'export GOOGLE_API_KEY="AIzaSy_your_key_here"' >> ~/.bashrc
source ~/.bashrc
echo $GOOGLE_API_KEY
```

#### Step 3: Test It Works

**macOS/Linux:**
```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$GOOGLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Say G'\''day mate!"}]}]}'
```

**Windows PowerShell:**
```powershell
$url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$env:GOOGLE_API_KEY"
$body = '{"contents":[{"parts":[{"text":"Say G''day mate!"}]}]}'
Invoke-RestMethod -Uri $url -Method POST -Headers @{"Content-Type"="application/json"} -Body $body
```

#### Gemini Free Tier Limits (March 2026 - Verified)

| Limit | Value |
|-------|-------|
| Requests per minute | 15 |
| Requests per day | 1,500 |
| Tokens per minute | 32,000 |
| Context window | **1,000,000 tokens** |

**The 1 million token context is incredible for free! Use it for long documents, entire codebases, or massive analysis tasks.**

---

### Setup: OpenAI (PAID - Best for Coding)

**What is OpenAI?** Makers of ChatGPT. Their API is excellent for coding tasks. **Requires credit card and pay-as-you-go billing.**

**Sign-up URL:** https://platform.openai.com

#### Step 1: Create Account

1. Go to: https://platform.openai.com
2. Click "Sign Up" (top right)
3. Use Google, Microsoft, Apple account OR email
4. Verify your phone number (required)
5. Complete onboarding

#### Step 2: Add Payment Method

1. Go to: https://platform.openai.com/account/billing
2. Click "Add payment details"
3. Enter credit/debit card
4. **Set a spending limit** - recommend starting with:
   - $20 USD ($28.40 AUD) for testing
   - $50 USD ($71 AUD) for regular use
5. Enable "Auto recharge" only if you want continuous use

#### Step 3: Get API Key

1. Go to: https://platform.openai.com/api-keys
2. Click "+ Create new secret key"
3. Give it a name: `agentic-brain`
4. Click "Create secret key"
5. **⚠️ COPY THE KEY IMMEDIATELY** - You only see it once!

The key looks like: `sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxx`

#### Step 4: Save the Key

**🍎 macOS:**
```bash
echo 'export OPENAI_API_KEY="sk-proj-your_key_here"' >> ~/.zshrc
source ~/.zshrc
echo $OPENAI_API_KEY
```

**🪟 Windows (PowerShell as Administrator):**
```powershell
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-proj-your_key_here', 'User')
# Restart PowerShell
echo $env:OPENAI_API_KEY
```

**🪟 Windows (Command Prompt as Administrator):**
```cmd
setx OPENAI_API_KEY "sk-proj-your_key_here"
:: Restart terminal
echo %OPENAI_API_KEY%
```

**🐧 Linux:**
```bash
echo 'export OPENAI_API_KEY="sk-proj-your_key_here"' >> ~/.bashrc
source ~/.bashrc
echo $OPENAI_API_KEY
```

#### Step 5: Test It Works

**macOS/Linux:**
```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Say G'\''day mate!"}]}'
```

**Windows PowerShell:**
```powershell
$headers = @{
    "Authorization" = "Bearer $env:OPENAI_API_KEY"
    "Content-Type" = "application/json"
}
$body = '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Say G''day mate!"}]}'
Invoke-RestMethod -Uri "https://api.openai.com/v1/chat/completions" -Method POST -Headers $headers -Body $body
```

---

### Setup: Anthropic Claude (PAID - Best Reasoning)

**What is Claude?** Anthropic's AI. Best for complex reasoning and safety-critical tasks. **Requires credit card and pay-as-you-go billing.**

**Sign-up URL:** https://console.anthropic.com

#### Step 1: Create Account

1. Go to: https://console.anthropic.com
2. Click "Sign Up"
3. Enter email and password (or use Google/GitHub)
4. Verify your email
5. **Note:** Account approval is usually instant, but can take 1-3 days

#### Step 2: Add Payment Method

1. Go to: Console → Settings → Billing
2. Click "Add payment method"
3. Enter credit/debit card
4. **Set a spending limit** - recommend:
   - $20 USD ($28.40 AUD) for testing
   - $50 USD ($71 AUD) for regular use

#### Step 3: Get API Key

1. Go to: https://console.anthropic.com/settings/keys
2. Click "Create Key"
3. Give it a name: `agentic-brain`
4. Click "Create Key"
5. **⚠️ COPY THE KEY IMMEDIATELY** - You only see it once!

The key looks like: `sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxx`

#### Step 4: Save the Key

**🍎 macOS:**
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-your_key_here"' >> ~/.zshrc
source ~/.zshrc
echo $ANTHROPIC_API_KEY
```

**🪟 Windows (PowerShell as Administrator):**
```powershell
[System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-ant-api03-your_key_here', 'User')
# Restart PowerShell
echo $env:ANTHROPIC_API_KEY
```

**🪟 Windows (Command Prompt as Administrator):**
```cmd
setx ANTHROPIC_API_KEY "sk-ant-api03-your_key_here"
:: Restart terminal
echo %ANTHROPIC_API_KEY%
```

**🐧 Linux:**
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-your_key_here"' >> ~/.bashrc
source ~/.bashrc
echo $ANTHROPIC_API_KEY
```

#### Step 5: Test It Works

**macOS/Linux:**
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-sonnet-4-6-20250514", "max_tokens": 100, "messages": [{"role": "user", "content": "Say G'\''day mate!"}]}'
```

**Windows PowerShell:**
```powershell
$headers = @{
    "x-api-key" = $env:ANTHROPIC_API_KEY
    "anthropic-version" = "2023-06-01"
    "content-type" = "application/json"
}
$body = '{"model": "claude-sonnet-4-6-20250514", "max_tokens": 100, "messages": [{"role": "user", "content": "Say G''day mate!"}]}'
Invoke-RestMethod -Uri "https://api.anthropic.com/v1/messages" -Method POST -Headers $headers -Body $body
```

### Setup: xAI Grok (PAID - Reasoning & X Integration)

**Requirements:** X (Twitter) Premium subscription required for API access.

**Steps:**
1. Subscribe to X Premium at https://x.com/premium
2. Go to https://console.x.ai
3. Sign in with your X account
4. Navigate to API Keys section
5. Create a new API key
6. Copy the key and add to your `.env` file:

```bash
XAI_API_KEY=xai-your-key-here
```

**Available Models:**
| Model | Code | Best For | Pricing |
|-------|------|----------|---------|
| grok-4.1-fast | XK | Reasoning, X integration | $3.00/$15.00 per M tokens |
| grok-3-mini | XK2 | Budget tasks | $0.20/$0.50 per M tokens |

**Note:** There is no free tier. Pay-as-you-go billing only.

---

## Pricing Tables - USD and AUD

> **Last Verified: March 2026**  
> **Exchange Rate:** 1 USD = 1.42 AUD (check xe.com for current rate)  
> **⚠️ Australian GST:** 10% GST applies to paid services for Australian residents

### FREE Providers (No Credit Card Required)

| Provider | Models | Cost | Limits | Rating |
|----------|--------|------|--------|--------|
| **Ollama** | L1, L2, L3, L4, DSR | **$0 FOREVER** | Unlimited (your hardware) | ⭐⭐⭐⭐⭐ |
| **Groq** | GR, GR2 | **$0** | 30 req/min, 100K-500K tok/day | ⭐⭐⭐⭐ |
| **Google Gemini** | GO, GO2 | **$0** | 15 req/min, 1.5K req/day | ⭐⭐⭐⭐⭐ |

**Verdict:** Start here. These are genuinely FREE and extremely capable.

---

### OpenAI Pricing (March 2026)

| Model | Code | Input (USD) | Input (AUD) | Output (USD) | Output (AUD) |
|-------|------|-------------|-------------|--------------|--------------|
| gpt-4o-mini | **OP2** | $0.15/1M | $0.21/1M | $0.60/1M | $0.85/1M |
| gpt-5-mini | **OP3** | $0.25/1M | $0.36/1M | $2.00/1M | $2.84/1M |
| gpt-4o | **OP** | $2.50/1M | $3.55/1M | $10.00/1M | $14.20/1M |

#### OpenAI Monthly Cost Estimates

| Usage Level | Tokens/Month | OP2 Cost (USD/AUD) | OP Cost (USD/AUD) |
|-------------|--------------|--------------------|--------------------|
| Light | 1M | $0.75 / $1.07 | $12.50 / $17.75 |
| Moderate | 10M | $7.50 / $10.65 | $125 / $177.50 |
| Heavy | 50M | $37.50 / $53.25 | $625 / $887.50 |

**Recommendation:** Start with OP2 (gpt-4o-mini). It's 95% as good as OP for 95% less cost.

**🇦🇺 Australian Note:** Add 10% GST to these prices. $10 USD becomes ~$15.62 AUD after GST.

---

### Anthropic Claude Pricing (March 2026)

| Model | Code | Input (USD) | Input (AUD) | Output (USD) | Output (AUD) |
|-------|------|-------------|-------------|--------------|--------------|
| claude-haiku-4-5 | **CL2** | ~$0.25/1M | ~$0.36/1M | ~$1.25/1M | ~$1.78/1M |
| claude-sonnet-4-6 | **CL** | $3.00/1M | $4.26/1M | $15.00/1M | $21.30/1M |
| claude-opus-4-6 | **CL3** | $5.00/1M | $7.10/1M | $25.00/1M | $35.50/1M |

#### Claude Monthly Cost Estimates

| Usage Level | Tokens/Month | CL2 Cost (USD/AUD) | CL Cost (USD/AUD) |
|-------------|--------------|--------------------|--------------------|
| Light | 1M | $1.50 / $2.13 | $18.00 / $25.56 |
| Moderate | 10M | $15.00 / $21.30 | $180 / $255.60 |
| Heavy | 50M | $75.00 / $106.50 | $900 / $1,278 |

**Recommendation:** CL2 (Haiku) for everyday tasks. CL (Sonnet) for reasoning/analysis.

**🇦🇺 Australian Note:** Add 10% GST. Anthropic bills in USD, your bank may add currency conversion fees (typically 1-3%).

---

### Cost Comparison Table (1M Tokens, 50/50 Input/Output)

| Provider | Model | Code | USD Cost | AUD Cost | AUD + GST |
|----------|-------|------|----------|----------|-----------|
| Ollama | Any | L1-L4 | **$0** | **$0** | **$0** |
| Groq | llama-3.3-70b | GR | **$0** | **$0** | **$0** |
| Google | gemini-2.5-flash | GO | **$0** | **$0** | **$0** |
| OpenAI | gpt-4o-mini | OP2 | $0.38 | $0.53 | $0.59 |
| Anthropic | claude-haiku-4-5 | CL2 | $0.75 | $1.07 | $1.17 |
| OpenAI | gpt-5-mini | OP3 | $1.13 | $1.60 | $1.76 |
| OpenAI | gpt-4o | OP | $6.25 | $8.88 | $9.76 |
| Anthropic | claude-sonnet-4-6 | CL | $9.00 | $12.78 | $14.06 |
| Anthropic | claude-opus-4-6 | CL3 | $15.00 | $21.30 | $23.43 |

---

### Budget Planning Guide

#### "I have $0/month" (FREE tier only)

```
Use: L1 → GR → GO
Capabilities: 
✅ Basic chat, Q&A, drafts
✅ Code suggestions (limited)
✅ Summarization
✅ Translation
❌ Complex reasoning
❌ Long code generation
```

#### "I have $10 USD ($14.20 AUD)/month"

```
Use: L1 → GR → GO → OP2
Budget allocation:
- $0: Most tasks (FREE)
- $10: ~13M tokens of OP2 for important tasks
Capabilities: All basic + good coding
```

#### "I have $25 USD ($35.50 AUD)/month"

```
Use: L1 → GR → GO → OP2 → CL2
Budget allocation:
- $0: Routine tasks (FREE)
- $15: OP2 for coding (~20M tokens)
- $10: CL2 for reasoning (~6M tokens)
Capabilities: All tasks handled well
```

#### "I have $50 USD ($71 AUD)/month"

```
Use: Full fallback chain
Budget allocation:
- $0: Quick tasks (FREE)
- $20: OP2 (coding) 
- $15: CL (reasoning)
- $15: Buffer/emergency
Capabilities: Professional-grade AI
```

#### "I have $100 USD ($142 AUD)/month"

```
Use: Full chain with premium access
Budget allocation:
- $0: Quick tasks (FREE)
- $30: OP for coding
- $30: CL for reasoning  
- $20: CL3 for critical tasks
- $20: Buffer
Capabilities: Enterprise-grade AI
```

---

## Capability Matrix

### What ALL LLMs Can Do (Baseline)

Every model in the system can handle these tasks:

| Task | Description | Quality Varies? |
|------|-------------|-----------------|
| **Chat** | Basic conversation | No |
| **Q&A** | Answer simple questions | No |
| **Summarize** | Condense text | Slightly |
| **Translate** | Basic language translation | Yes |
| **Grammar** | Fix spelling/grammar | No |
| **Format** | Convert formats (JSON, CSV, etc.) | No |
| **Explain** | Explain concepts simply | Slightly |
| **Draft** | Write first drafts | Yes |
| **List** | Generate lists, brainstorm | No |
| **Math** | Basic arithmetic | No |

**Bottom line**: For simple tasks, use the CHEAPEST model (L1, GR, GO).

---

### What SOME LLMs Excel At (Specialized)

| Task | Best Models | Acceptable | Avoid |
|------|-------------|------------|-------|
| **Complex Reasoning** | CL, CL3, DSR | OP, OP3 | L1, GR |
| **Code Generation** | OP, CL, L2 | GO, GR | L1 |
| **Code Review** | CL, OP | L2, GO | L1, GR |
| **Long Context (100k+)** | GO (1M!), CL3, GO2 | CL | L1, L2, GR |
| **Function Calling** | OP, CL, GO | - | L1, L2, L3 |
| **Vision/Images** | OP, CL, GO | GO2 | L1, L2, GR |
| **Structured Output** | OP, CL, GO | L2 | L1, L3 |
| **Multi-step Plans** | CL, OP, DSR | L2 | L1, GR |
| **Safety/Ethics** | CL, CL3 | OP | L1, GR |
| **Creative Writing** | CL, L3 | OP, L2 | L1 |
| **Technical Docs** | CL, OP | L2, GO | L1, GR |
| **Mathematics** | DSR, OP3 | CL, OP | L1, GR |

---

### Model Specialty Summary

| Model | Primary Strength | Use When |
|-------|------------------|----------|
| **L1** | Speed + Privacy | Quick drafts, offline work |
| **L2** | Quality + Privacy | Complex tasks offline |
| **L3** | European languages | French, German, Italian content |
| **DSR** | Reasoning + Math | Logic puzzles, proofs, analysis |
| **GR** | Fastest inference | Need speed, not depth |
| **GO** | FREE + Long context | Long documents, budget work |
| **OP** | Best coding | Writing/debugging code |
| **OP2** | Budget coding | Coding on a budget |
| **OP3** | Latest OpenAI | Cutting-edge needs |
| **CL** | Best reasoning | Complex analysis |
| **CL2** | Budget Claude | Quick reasoning tasks |
| **CL3** | Most capable | Safety-critical, nuanced work |

---

### What NO LLM Can Do (Limitations)

**EVERY model has these limitations:**

| Limitation | Description | Workaround |
|------------|-------------|------------|
| **Real Internet** | Cannot browse live web | Use tools/APIs |
| **True Memory** | Forgets after session | Use Neo4j memory |
| **Execute Code** | Cannot run code directly | Use sandbox/tools |
| **Access Files** | Cannot read your files | Use file tools |
| **100% Accuracy** | All can hallucinate | Verify important facts |
| **Real Creativity** | Recombines, doesn't create | Human review |
| **Current Events** | Training cutoff varies | Use web search |
| **Personal Data** | Doesn't know you | Provide context |
| **Physical Actions** | Cannot click/type | Use automation |

---

## Task Routing Guide

### Use This Model For...

| Task Type | Recommended | Why |
|-----------|-------------|-----|
| **Quick question** | L1, GR | Fast, free |
| **Draft email** | L1, GO | Good enough, free |
| **Code writing** | OP, CL | Best quality |
| **Code review** | CL, OP | Catches bugs |
| **Debug error** | OP, CL, L2 | Understands context |
| **Explain concept** | GO, GR, L2 | Clear, free |
| **Summarize doc** | GO, GR, L1 | Fast, free |
| **Creative writing** | CL, L3 | Nuanced |
| **Safety-critical** | CL, CL3 | Most careful |
| **Math problem** | OP3, CL | Reasoning |
| **Private data** | L1, L2 | Stays local |
| **Long document** | CL3, GO2 | 100k+ context |

---

## Recommended Defaults

> **Safe, sensible defaults for consulting and professional work**

### For Individuals / Freelancers

```
Primary:     L1 (llama3.2:3b) - Local, free, fast
Secondary:   GR (Groq) - When L1 can't handle it
Coding:      L2 (llama3.1:8b) - Better quality, still local
Emergency:   GO (Gemini) - Backup if local models fail
```

**Monthly cost: $0 AUD**

### For Small Business / Consultants

```
Primary:     GO (Gemini) - Free, capable, 1M context
Secondary:   GR (Groq) - Fast responses
Coding:      OP2 (gpt-4o-mini) - Best value for code
Reasoning:   CL2 (Claude Haiku) - Best value for analysis
Premium:     CL (Claude Sonnet) - Complex client work only
```

**Monthly cost: ~$20-50 AUD**

### For Enterprise / High-Stakes Work

```
Primary:     CL (Claude Sonnet) - Best reasoning
Coding:      OP (gpt-4o) - Best code quality
Analysis:    CL (Claude Sonnet) - Complex documents
Critical:    CL3 (Claude Opus) - Safety-critical only
Backup:      L2 → GR → GO - If primary fails
```

**Monthly cost: ~$100-300 AUD**

### Environment Variable Summary

```bash
# REQUIRED for paid providers
export OPENAI_API_KEY="sk-proj-..."      # For OP, OP2, OP3
export ANTHROPIC_API_KEY="sk-ant-..."    # For CL, CL2, CL3

# REQUIRED for free cloud providers  
export GROQ_API_KEY="gsk_..."            # For GR, GR2
export GOOGLE_API_KEY="AIzaSy..."        # For GO, GO2

# OPTIONAL - defaults to localhost:11434
export OLLAMA_HOST="http://localhost:11434"  # For L1, L2, L3, L4, DSR
```

---

## Fallback System

### How Automatic Failover Works

When a model fails (error, timeout, rate limit), the system automatically tries the next model:

```
┌─────────────────────────────────────────────────────────────────┐
│                    FALLBACK CHAIN (March 2026)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   L1 → L2 → DSR → GO → GR → OP2 → CL2 → OP → CL → OP3 → CL3   │
│   │     │    │     │    │     │     │    │    │     │     │    │
│   └─────┴────┴─────┴────┘     └─────┴────┴────┴─────┴─────┘    │
│         FREE (local+cloud)          PAID (cheap→expensive)     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Order?

| Position | Models | Reason |
|----------|--------|--------|
| 1-2 | L1, L2 | FREE + LOCAL - No cost, no internet, no rate limits |
| 3 | DSR | FREE + LOCAL - Reasoning specialist |
| 4-5 | GO, GR | FREE CLOUD - No cost, but needs internet |
| 6-7 | OP2, CL2 | CHEAP - Minimal cost, good capability |
| 8-9 | OP, CL | STANDARD - Full capability |
| 10-11 | OP3, CL3 | PREMIUM - Maximum capability, last resort |

### Credit Preservation Rules

| Task Type | Models Allowed | Reason |
|-----------|---------------|--------|
| **Routine** | L1, L2, GO, GR only | Saves all paid credits |
| **Important** | + OP2, CL2 | Small cost for quality |
| **Critical** | + OP, CL | Full power when needed |
| **Emergency** | + OP3, CL3 | No holds barred recovery |

### Failure Types and Responses

| Failure Type | Action | Retry Delay |
|--------------|--------|-------------|
| **Rate limited (429)** | Skip provider | 1 minute |
| **Server error (500-503)** | Try next model | Immediate |
| **Timeout** | Try next model | Immediate |
| **Auth error (401/403)** | Skip provider | 1 hour |
| **Model not found** | Try next model | Immediate |
| **Content filter** | Try different provider | Immediate |

### Circuit Breaker Pattern

```
Model fails once   → Try again
Model fails twice  → Try again (last chance)
Model fails 3x     → CIRCUIT OPENS → Skip for 5 minutes
After 5 minutes    → HALF-OPEN → Try ONE request
If success         → CIRCUIT CLOSES → Normal operation
If fail            → CIRCUIT STAYS OPEN → Wait another 5 minutes
```

---

## Troubleshooting

### Quick Diagnosis

**Model won't respond?**
```
1. Is Ollama running?     → ollama serve
2. Is model downloaded?   → ollama list
3. Is API key set?        → echo $OPENAI_API_KEY (or relevant key)
4. Is internet working?   → ping api.openai.com
5. Check rate limits      → Wait 1 minute, try again
```

---

### Ollama Issues (L1, L2, L3, DSR)

| Problem | Cause | Solution |
|---------|-------|----------|
| `ollama: command not found` | Not installed or not in PATH | **Mac:** Restart terminal. **Linux:** `source ~/.bashrc`. **Windows:** Restart PowerShell. |
| `model not found` | Model not downloaded | `ollama pull MODEL_NAME` |
| `out of memory` | Model too big for RAM | Use smaller model (L1 instead of L2) or close other apps |
| `connection refused` | Ollama service not running | Run `ollama serve` in a terminal (keep it open) |
| Slow first response | Model loading into memory | Normal. Wait ~10-30 seconds. Subsequent responses fast. |
| GPU not being used | Metal/CUDA not detected | **Mac:** Should auto-detect Metal. **Linux/Windows:** Check CUDA installation. |

**Check Ollama status:**
```bash
# See what's running
curl http://localhost:11434/api/tags

# Test model directly
ollama run llama3.2:3b "test"
```

---

### Groq Issues (GR, GR2)

| Problem | Cause | Solution |
|---------|-------|----------|
| `401 Unauthorized` | API key invalid/missing | Check `echo $GROQ_API_KEY`. Get new key from console.groq.com |
| `429 Rate Limited` | Hit free tier limits | Wait 1 minute, or reduce request frequency |
| `503 Service Unavailable` | Groq servers overloaded | Wait 30 seconds, try again. Use different model as fallback. |
| Timeout errors | Network issues | Check internet connection. Try different network. |

**Check Groq status:**
```bash
# Verify key works
curl -X POST "https://api.groq.com/openai/v1/chat/completions" \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Hi"}]}'
```

---

### Google Gemini Issues (GO, GO2)

| Problem | Cause | Solution |
|---------|-------|----------|
| `400 Bad Request` | Invalid API key | Regenerate key at aistudio.google.com |
| `429 Rate Limited` | Exceeded 15 req/min | Slow down requests, or wait 1 minute |
| `403 Forbidden` | Gemini not enabled | Enable Gemini API in Google Cloud Console |
| Region blocked | Your country restricted | Use VPN or different provider |

**Check Gemini status:**
```bash
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY"
```

---

### OpenAI Issues (OP, OP2, OP3)

| Problem | Cause | Solution |
|---------|-------|----------|
| `401 Unauthorized` | Invalid/expired API key | Generate new key at platform.openai.com/api-keys |
| `429 Rate Limited` | Hit rate or spend limit | Check billing, increase limits, or wait |
| `insufficient_quota` | No credits left | Add payment method, add credits |
| `model_not_found` | Old model name | Check current model names at platform.openai.com |
| High latency | Server load | Normal for complex models (OP3 can take 30+ seconds) |

**Check OpenAI status:**
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

### Anthropic Claude Issues (CL, CL2, CL3)

| Problem | Cause | Solution |
|---------|-------|----------|
| `401 Authentication error` | Invalid API key | Regenerate at console.anthropic.com/settings/keys |
| `403 Forbidden` | Account not approved | Wait for approval (can take 1-3 days for new accounts) |
| `429 Rate Limited` | Hit rate limits | Reduce request frequency, wait 1 minute |
| `overloaded` | High demand | Wait 30 seconds, retry. Use CL2 instead of CL3. |
| Response refused | Content policy | Rephrase request, avoid edge cases |

**Check Claude status:**
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-sonnet-4-6-20250514", "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]}'
```

---

### Environment Variable Issues

**Variables not being read:**

| OS | Problem | Solution |
|----|---------|----------|
| **Mac** | Variable not persisting | Add to `~/.zshrc` not `~/.bashrc`. Run `source ~/.zshrc`. |
| **Linux** | Variable not persisting | Add to `~/.bashrc`. Run `source ~/.bashrc`. |
| **Windows** | Variable not persisting | Use `setx` (permanent) not `set` (temporary). Restart terminal. |

**Test all variables at once:**

**Mac/Linux:**
```bash
echo "OLLAMA: $(curl -s http://localhost:11434/api/tags | head -c 50)"
echo "GROQ_API_KEY: ${GROQ_API_KEY:0:10}..."
echo "GOOGLE_API_KEY: ${GOOGLE_API_KEY:0:10}..."
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..."
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
```

**Windows PowerShell:**
```powershell
Write-Host "GROQ_API_KEY: $($env:GROQ_API_KEY.Substring(0,10))..."
Write-Host "GOOGLE_API_KEY: $($env:GOOGLE_API_KEY.Substring(0,10))..."
Write-Host "OPENAI_API_KEY: $($env:OPENAI_API_KEY.Substring(0,10))..."
Write-Host "ANTHROPIC_API_KEY: $($env:ANTHROPIC_API_KEY.Substring(0,10))..."
```

---

### Network Issues

| Problem | Test | Solution |
|---------|------|----------|
| No internet | `ping google.com` | Fix internet connection |
| DNS issues | `nslookup api.openai.com` | Use different DNS (8.8.8.8) |
| Firewall blocking | `curl https://api.openai.com` | Whitelist API domains |
| Proxy required | - | Set `HTTP_PROXY` and `HTTPS_PROXY` environment variables |
| VPN interfering | Try without VPN | Some VPNs block API traffic |

---

### Still Stuck?

1. **Check provider status pages:**
   - Groq: status.groq.com
   - OpenAI: status.openai.com  
   - Anthropic: status.anthropic.com
   - Google: status.cloud.google.com

2. **Try a different model:**
   - If cloud fails → try local (L1)
   - If paid fails → try free (GR, GO)
   - If one provider fails → try another

3. **Reset and retry:**
   ```bash
   # Restart Ollama
   pkill ollama && ollama serve
   
   # Re-source environment
   source ~/.zshrc  # or ~/.bashrc on Linux
   ```

---

## Pros and Cons

### Local Models (L1, L2, L3, DSR)

| Pros | Cons |
|------|------|
| ✅ FREE forever | ❌ Need local setup |
| ✅ Works offline | ❌ Uses RAM/CPU |
| ✅ Private - data stays local | ❌ Slower than cloud |
| ✅ No rate limits | ❌ Less capable |
| ✅ No API keys | ❌ No vision |

**Best for**: Privacy, offline work, unlimited use

### Claude (CL, CL2, CL3)

| Pros | Cons |
|------|------|
| ✅ Best reasoning | ❌ Costs money |
| ✅ Most careful/safe | ❌ Can be slow |
| ✅ Long context (CL3) | ❌ Rate limits |
| ✅ Excellent writing | ❌ Needs API key |
| ✅ Honest about limits | ❌ Sometimes refuses |

**Best for**: Reasoning, safety-critical, analysis

### OpenAI (OP, OP2, OP3)

| Pros | Cons |
|------|------|
| ✅ Best for coding | ❌ Costs money |
| ✅ Great function calling | ❌ Rate limits |
| ✅ Wide tool support | ❌ Less safe than Claude |
| ✅ Fast (OP2) | ❌ OP3 is slow |
| ✅ Reliable API | ❌ Needs API key |

**Best for**: Coding, tools, structured tasks

### Gemini (GO, GO2)

| Pros | Cons |
|------|------|
| ✅ FREE tier (GO) | ❌ Less tested |
| ✅ Fast | ❌ Quality varies |
| ✅ Good all-rounder | ❌ Newer, less docs |
| ✅ Google integration | ❌ Rate limits on free |
| ✅ Long context (GO2) | ❌ GO2 costs money |

**Best for**: Budget work, general tasks

### DeepSeek-R1 (DSR) - Reasoning Specialist

| Pros | Cons |
|------|------|
| ✅ FREE (local) | ❌ Large download (~7-40GB) |
| ✅ Excellent reasoning | ❌ Slower than L1/L2 |
| ✅ Math and logic strength | ❌ Less general-purpose |
| ✅ Private | ❌ Needs good hardware |
| ✅ Open weights | ❌ Newer, less tested |

**Best for**: Mathematical proofs, logic puzzles, chain-of-thought reasoning

---

### Groq (GR, GR2)

| Pros | Cons |
|------|------|
| ✅ FASTEST cloud | ❌ Less capable |
| ✅ FREE | ❌ Strict rate limits |
| ✅ Low latency | ❌ No vision |
| ✅ Good for drafts | ❌ Limited models |
| ✅ No API key hassle | ❌ Can timeout |

**Best for**: Speed, quick answers, drafts

---

## Decision Flowchart

```
START: What do you need?
│
├─ Private/Offline? → L1 or L2
│
├─ FREE required? → L1 → GR → GO
│
├─ Speed critical? → GR → L1 → GO
│
├─ Code task? → OP → CL → L2
│
├─ Reasoning task? → CL → OP → OP3
│
├─ Safety critical? → CL → CL3
│
├─ Long document? → CL3 → GO2
│
└─ General task? → GO → GR → L1
```

---

## Cost Tiers

| Tier | Models | Monthly Cost (Heavy Use) |
|------|--------|-------------------------|
| **FREE** | L1, L2, L3, L4, GO, GR | $0 |
| **CHEAP** | OP2, CL2 | ~$5-20 |
| **MODERATE** | GO2 | ~$20-50 |
| **EXPENSIVE** | OP, CL | ~$50-200 |
| **PREMIUM** | OP3, CL3 | ~$200+ |

---

## Speed Comparison

| Model | Time to First Token | Full Response |
|-------|--------------------:|-------------:|
| **GR** | ~50ms | ~1s |
| **L1** | ~100ms | ~2s |
| **GO** | ~200ms | ~2s |
| **OP2** | ~300ms | ~3s |
| **CL2** | ~300ms | ~3s |
| **L2** | ~200ms | ~4s |
| **OP** | ~500ms | ~5s |
| **CL** | ~500ms | ~5s |
| **GO2** | ~500ms | ~5s |
| **CL3** | ~1s | ~10s |
| **OP3** | ~2s | ~30s+ |

*Times vary by prompt length and system load.*

---

## Health & Reliability

### Circuit Breaker

If a model fails 3 times in a row:
- Circuit **OPENS** - skip this model for 5 minutes
- After 5 minutes, try ONE request (half-open)
- If success, circuit **CLOSES** - normal operation
- If fails, circuit stays **OPEN** another 5 minutes

### Rate Limit Handling

When rate limited:
- Skip provider for 1 minute
- Try different provider immediately
- Log which provider is rate limited

### Auth Error Handling

When API key is invalid:
- Skip provider for 1 hour
- Alert user to fix key
- Use other providers meanwhile

---

## Quick Commands

### In Chatbot

```
/models     - List all models
/L1         - Switch to local fast
/CL         - Switch to Claude
/OP         - Switch to OpenAI
/current    - Show current model
/fallback   - Test fallback chain
```

### In CLI

```bash
agentic models              # List all
agentic switch L1           # Switch model
agentic test-model CL       # Test model
agentic status              # Show health
```

---

## Summary

1. **Start with FREE** (L1, GR, GO) - no cost
2. **Upgrade for quality** (CL, OP) - when needed
3. **Fallback works automatically** - never fails
4. **Neo4j shares memory** - all models same brain
5. **Circuit breaker protects** - skips broken models

**The brain is ALWAYS running** - pick the model that fits your task!

---

*Last verified: March 2026*  
*Exchange rate: 1 USD = 1.42 AUD*  
*Part of Agentic Brain - Universal AI Assistant*

---

## Changelog

| Date | Change |
|------|--------|
| March 2026 | Major update: Added DeepSeek-R1, updated all pricing to AUD, added Windows/Mac/Linux setup, comprehensive troubleshooting |
| 2025 | Initial version |

---

## Quick Reference Card

**Print this out or keep handy:**

```
╔═══════════════════════════════════════════════════════════════════╗
║  AGENTIC BRAIN - MODEL QUICK REFERENCE (March 2026)               ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  FREE MODELS (use these first!)                                   ║
║  ─────────────────────────────────────────────────────────────── ║
║  L1  = llama3.2:3b    → Fast, 4GB RAM, local                     ║
║  L2  = llama3.1:8b    → Quality, 8GB RAM, local                  ║
║  L3  = mistral:7b     → European, 8GB RAM, local                 ║
║  DSR = DeepSeek-R1    → Reasoning, various sizes, local          ║
║  GR  = Groq 70b       → FASTEST cloud, 30 req/min                ║
║  GO  = Gemini Flash   → 1M context (!), 15 req/min               ║
║                                                                   ║
║  PAID MODELS (when you need more)                                 ║
║  ─────────────────────────────────────────────────────────────── ║
║  OP2 = gpt-4o-mini    → Budget coding, ~$0.21 AUD/1M in          ║
║  OP  = gpt-4o         → Best coding, ~$3.55 AUD/1M in            ║
║  OP3 = gpt-5-mini     → Latest OpenAI, ~$0.36 AUD/1M in          ║
║  CL2 = Haiku          → Budget reasoning, ~$0.36 AUD/1M in       ║
║  CL  = Sonnet         → Best reasoning, ~$4.26 AUD/1M in         ║
║  CL3 = Opus           → Most capable, ~$7.10 AUD/1M in           ║
║                                                                   ║
║  FALLBACK ORDER                                                   ║
║  ─────────────────────────────────────────────────────────────── ║
║  L1 → L2 → DSR → GO → GR → OP2 → CL2 → OP → CL → OP3 → CL3      ║
║  ^^^^^^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ║
║        FREE                           PAID                        ║
║                                                                   ║
║  ENVIRONMENT VARIABLES                                            ║
║  ─────────────────────────────────────────────────────────────── ║
║  GROQ_API_KEY       = gsk_xxx...        (console.groq.com)       ║
║  GOOGLE_API_KEY     = AIzaSy...         (aistudio.google.com)    ║
║  OPENAI_API_KEY     = sk-proj-...       (platform.openai.com)    ║
║  ANTHROPIC_API_KEY  = sk-ant-...        (console.anthropic.com)  ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```
