# Tutorial 6: Business Automation

Build AI-powered business automation tools with Agentic Brain.

## Overview

This tutorial covers three real-world business automation patterns:

1. **Email Automation** - Classify and route emails with AI
2. **Business Brain** - Build a knowledge graph CRM  
3. **Invoice Processing** - Extract data from PDFs

These patterns are inspired by production systems used in e-commerce and retail businesses.

## Prerequisites

```bash
# Install agentic-brain
pip install agentic-brain

# Start Ollama
ollama pull llama3.1:8b
ollama serve
```

## Part 1: Email Automation

### The Problem

A business receives hundreds of emails daily:
- Spam and marketing emails
- Order confirmations
- Customer support requests
- Supplier invoices
- Important correspondence

Manually sorting these is time-consuming and error-prone.

### The Solution

Use AI to classify emails into categories and route them automatically.

```python
from agentic_brain.router import LLMRouter

# Email classification prompt
CLASSIFY_PROMPT = """Classify this email:
From: {sender}
Subject: {subject}

Categories: spam, newsletter, order, support, invoice, important

Return: CATEGORY: <category>"""

async with LLMRouter(providers=["ollama"]) as router:
    result = await router.complete(
        CLASSIFY_PROMPT.format(sender="...", subject="...")
    )
```

### Hybrid Approach

Combine fast rule-based filtering with AI:

```python
# 1. Quick rule-based check for obvious spam
SPAM_PATTERNS = [
    r"(?i)you.*won.*lottery",
    r"@.*\.ru$",
]

def is_obvious_spam(email):
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, email.text):
            return True
    return False

# 2. AI classification for everything else
if is_obvious_spam(email):
    move_to_junk(email)
else:
    category = await ai_classify(email)
    route_to_folder(email, category)
```

### Full Example

See: `examples/13_email_automation.py`

## Part 2: Business Brain (Knowledge Graph CRM)

### The Problem

Business knowledge is scattered:
- Supplier contacts in emails
- Customer history in spreadsheets
- Learned preferences in people's heads

An employee leaving means lost knowledge.

### The Solution

Build a knowledge graph that:
- Stores supplier/customer relationships
- Remembers business rules and preferences
- Provides AI-assisted queries

```python
class BusinessBrain:
    def __init__(self):
        self.suppliers = {}
        self.customers = {}
        self.learnings = []
    
    def remember(self, topic: str, content: str):
        """Store business knowledge."""
        self.learnings.append({
            "topic": topic,
            "content": content,
            "timestamp": datetime.now()
        })
    
    async def query(self, question: str):
        """Natural language query interface."""
        context = self._build_context()
        prompt = f"Knowledge: {context}\n\nQuestion: {question}"
        return await self.router.complete(prompt)
```

### Session Continuity

Don't lose context between sessions:

```python
# On session end
def wrapup(self, summary: str, pending_tasks: list):
    self.remember(
        topic="session_wrapup",
        content=f"Summary: {summary}. Pending: {pending_tasks}"
    )

# On session start
def get_session_summary(self) -> str:
    return f"Last topic: {self.last_topic}\nData: {len(self.suppliers)} suppliers"
```

### Full Example

See: `examples/14_business_brain.py`

## Part 3: Invoice Processing

### The Problem

Invoices arrive as PDF attachments:
- Different formats per supplier
- Manual data entry is slow
- Errors in amounts cause payment issues

### The Solution

Extract invoice data using AI:

```python
EXTRACTION_PROMPT = """Extract from this invoice:
{invoice_text}

Return JSON:
{
    "vendor_name": "...",
    "invoice_number": "...",
    "invoice_date": "YYYY-MM-DD",
    "total": 100.00
}"""

async def extract_invoice(pdf_path: str):
    # 1. Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    
    # 2. Try rule-based extraction first (faster)
    data = extract_with_rules(text)
    if data:
        return data
    
    # 3. Fall back to AI extraction
    response = await router.complete(
        EXTRACTION_PROMPT.format(invoice_text=text)
    )
    return parse_json(response)
```

### Vendor-Specific Profiles

Handle multiple invoice formats:

```python
VENDOR_PROFILES = {
    "innovative": {
        "name": "Innovative Music",
        "date_format": "%d/%m/%Y",
        "total_pattern": r"Total:\s*\$([\d,]+\.?\d*)",
    },
    "ambertech": {
        "name": "Ambertech",
        "date_format": "%d-%m-%Y", 
        "total_pattern": r"TOTAL\s*([\d,]+\.\d{2})",
    },
}
```

### Validation

Always validate extracted data:

```python
def validate_invoice(data):
    errors = []
    
    if data.total <= 0:
        errors.append("Invalid total")
    
    # Math check
    expected = data.subtotal + data.tax
    if abs(expected - data.total) > 0.02:
        errors.append("Total doesn't match subtotal + tax")
    
    return len(errors) == 0, errors
```

### Full Example

See: `examples/15_invoice_processor.py`

## Putting It Together

A complete business automation system:

```
┌─────────────────────────────────────────────────┐
│              Email Automation                    │
│  spam_filter → order_router → support_triage   │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              Invoice Processor                   │
│  PDF extraction → validation → spreadsheet log  │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              Business Brain                      │
│  Neo4j knowledge graph + AI query interface     │
└─────────────────────────────────────────────────┘
```

## Running on Schedule

Use launchd (macOS) or cron (Linux) to run automation:

```xml
<!-- ~/Library/LaunchAgents/com.business.automation.plist -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.business.automation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/run_all.py</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>  <!-- Every 5 minutes -->
</dict>
</plist>
```

## Best Practices

1. **Hybrid approach** - Use rules for speed, AI for edge cases
2. **Validation** - Always validate extracted data
3. **Logging** - Log everything for debugging
4. **Idempotency** - Track processed items (UIDs) to avoid reprocessing
5. **Error handling** - Graceful failures, don't lose data
6. **Testing** - Test with sample data before production

## Next Steps

- Add more vendor profiles
- Integrate with actual IMAP/Google Sheets
- Build a dashboard for monitoring
- Add anomaly detection (unusual invoice amounts)

See the examples folder for complete, runnable code!
