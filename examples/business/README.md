# 💼 Business Automation Examples

> Automate business operations - email, invoices, warehouse, retail.

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 13 | [email_automation.py](13_email_automation.py) | AI email classification & routing | 🟡 Intermediate |
| 14 | [business_brain.py](14_business_brain.py) | Knowledge graph CRM | 🟡 Intermediate |
| 15 | [invoice_processor.py](15_invoice_processor.py) | PDF invoice data extraction | 🟡 Intermediate |
| 16 | [warehouse_assistant.py](16_warehouse_assistant.py) | Stock queries, picking, receiving | 🟡 Intermediate |
| 17 | [qa_assistant.py](17_qa_assistant.py) | Quality control workflows | 🟡 Intermediate |
| 18 | [packing_assistant.py](18_packing_assistant.py) | Order packing workflows | 🟡 Intermediate |
| 19 | [store_manager.py](19_store_manager.py) | Sales & inventory dashboard | 🟡 Intermediate |

## Quick Start

```bash
# Email classification
python examples/business/13_email_automation.py

# Warehouse operations
python examples/business/16_warehouse_assistant.py

# Store management
python examples/business/19_store_manager.py
```

## Use Cases

### Email Automation
- Classify incoming emails (support, sales, spam)
- Route to appropriate teams
- Auto-draft responses
- Extract action items

### Invoice Processing
- Extract data from PDF invoices
- Validate against purchase orders
- Flag discrepancies
- Prepare for accounting

### Warehouse Operations
- Natural language stock queries
- Pick list generation
- Receiving and put-away
- Inventory counts

### Quality Assurance
- Inspection checklists
- Defect tracking
- Quality reports
- Compliance monitoring

### Store Management
- Sales dashboards
- Staff scheduling queries
- Inventory alerts
- Customer insights

## Common Patterns

### Email Classification
```python
from agentic_brain import Agent

classifier = Agent(
    name="email_classifier",
    system_prompt="Classify emails into: support, sales, billing, spam"
)

category = classifier.chat(email_content)
```

### Document Processing
```python
# Extract structured data from documents
agent = Agent(name="extractor")
data = agent.chat(f"Extract invoice data: {document_text}")
```

## Prerequisites

- Python 3.10+
- Ollama running locally
- Neo4j (for CRM example)
