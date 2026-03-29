# 🧠 Agentic Brain Examples

> **94 production-ready examples** demonstrating everything agentic-brain can do.

[![Examples](https://img.shields.io/badge/Examples-94-blue)](.)
[![Categories](https://img.shields.io/badge/Categories-10-green)](.)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow)](.)

---

## 🚀 Quick Start

```bash
# Install agentic-brain
pip install -e ".[dev,api]"

# Run the interactive launcher
python examples/00_kitchen_sink.py

# Or jump straight to the simplest example
python examples/core/01_simple_chat.py
```

---

## 📂 Example Categories

### 🎯 Core (13 examples)
**Foundational patterns every developer should know.**

| Example | Description | Level |
|---------|-------------|-------|
| `01_simple_chat.py` | Minimal chatbot - 5 lines! | 🟢 Beginner |
| `02_with_memory.py` | Neo4j persistent memory | 🟢 Beginner |
| `03_streaming.py` | Real-time token streaming | 🟡 Intermediate |
| `04_multi_user.py` | Isolated user sessions | 🟡 Intermediate |
| `05_rag_basic.py` | Document Q&A retrieval | 🟡 Intermediate |
| `06_custom_prompts.py` | Personas and system prompts | 🟡 Intermediate |
| `06_cloud_loaders.py` | Load docs from S3/GCS/Azure | 🟡 Intermediate |
| `07_multi_agent.py` | Crews and workflows | 🔴 Advanced |
| `08_api_server.py` | FastAPI REST deployment | 🔴 Advanced |
| `09_websocket.py` | Real-time WebSocket chat | 🔴 Advanced |
| `10_with_auth.py` | JWT authentication | 🔴 Advanced |
| `11_firebase_chat.py` | Firebase real-time sync | 🔴 Advanced |
| `12_with_tracing.py` | Observability & tracing | 🔴 Advanced |

```bash
cd examples/core && python 01_simple_chat.py
```

---

### 💼 Business (7 examples)
**Automate business operations with AI.**

| Example | Description | Level |
|---------|-------------|-------|
| `13_email_automation.py` | Email classification & routing | 🟡 Intermediate |
| `14_business_brain.py` | Knowledge graph CRM | 🟡 Intermediate |
| `15_invoice_processor.py` | PDF invoice extraction | 🟡 Intermediate |
| `16_warehouse_assistant.py` | Stock queries & picking | 🟡 Intermediate |
| `17_qa_assistant.py` | Quality control workflows | 🟡 Intermediate |
| `18_packing_assistant.py` | Order packing workflows | 🟡 Intermediate |
| `19_store_manager.py` | Sales & inventory dashboard | 🟡 Intermediate |

```bash
cd examples/business && python 13_email_automation.py
```

---

### 🏢 Enterprise (17 examples)
**Professional-grade enterprise solutions.**

| Example | Description | Level |
|---------|-------------|-------|
| `28_it_helpdesk.py` | IT support automation | 🔴 Advanced |
| `29_hr_assistant.py` | HR query & onboarding | 🔴 Advanced |
| `30_legal_compliance.py` | Legal document review | 🔴 Advanced |
| `31_knowledge_wiki.py` | Enterprise knowledge base | 🔴 Advanced |
| `32_meeting_assistant.py` | Meeting notes & actions | 🔴 Advanced |
| `skills_graph.py` | Workforce capability mapping | 🔴 Advanced |
| `career_opportunity_matcher.py` | Internal mobility platform | 🔴 Advanced |
| `professional_community.py` | Internal talent network | 🔴 Advanced |
| `defence_contractor.py` | Classified document handling (PSPF) | 🔴 Advanced |
| `government_portal.py` | Citizen services (Essential Eight) | 🔴 Advanced |
| `payment_assistant.py` | PCI DSS payment support | 🔴 Advanced |
| `pci_compliant_agent.py` | PCI compliance patterns | 🔴 Advanced |
| `submarine_maintenance_assistant.py` | Naval vessel maintenance (air-gapped) | 🔴 Advanced |

```bash
cd examples/enterprise && python skills_graph.py
```

---

### 🛒 WordPress & WooCommerce (15 examples)
**Content and e-commerce AI assistants.**

| Example | Description | Level |
|---------|-------------|-------|
| `20_wordpress_assistant.py` | Content management AI | 🟡 Intermediate |
| `21_woocommerce_orders.py` | Order processing | 🟡 Intermediate |
| `22_woocommerce_inventory.py` | Stock management | 🟡 Intermediate |
| `23_woocommerce_analytics.py` | Sales analytics | 🟡 Intermediate |
| `67_woo_electronics_catalog.py` | Electronics catalog | 🔴 Advanced |
| `71_woo_warehouse_ops.py` | Warehouse operations | 🔴 Advanced |
| `72_woo_shipping_logistics.py` | Shipping & tracking | 🔴 Advanced |
| `73_woo_inventory_sync.py` | Multi-channel sync | 🔴 Advanced |
| `75_wordpress_content_manager.py` | AI content creation | 🔴 Advanced |
| `76_divi_page_builder.py` | Divi builder integration | 🔴 Advanced |
| `77_wordpress_seo_assistant.py` | SEO optimisation | 🔴 Advanced |
| `78_divi_ecommerce_theme.py` | Theme builder | 🔴 Advanced |
| `79_woo_sales_dashboard.py` | Real-time sales | 🔴 Advanced |
| `80_woo_marketing_automation.py` | Marketing campaigns | 🔴 Advanced |
| `81_woo_pricing_optimizer.py` | Dynamic pricing | 🔴 Advanced |

```bash
cd examples/wordpress && python 20_wordpress_assistant.py
```

---

### ♿ NDIS & Disability (11 examples)
**Australian disability services - Privacy-first design.**

| Example | Description | Level |
|---------|-------------|-------|
| `51_ndis_provider.py` | Provider management portal | 🔴 Advanced |
| `52_ndis_participant.py` | Participant self-service | 🔴 Advanced |
| `53_ndis_compliance.py` | Compliance automation | 🔴 Advanced |
| `54_ndis_support_coordinator.py` | Support coordination | 🔴 Advanced |
| `60_sda_housing.py` | SDA housing finder | 🔴 Advanced |
| `61_sil_provider.py` | SIL provider tools | 🔴 Advanced |
| `62_ndis_housing_search.py` | Housing search assistant | 🔴 Advanced |
| `63_sda_financial_manager.py` | SDA financial planning | 🔴 Advanced |
| `64_sda_dashboard.py` | SDA provider dashboard | 🔴 Advanced |
| `65_sda_investor_portal.py` | SDA investment analysis | 🔴 Advanced |
| `66_sda_compliance_tracker.py` | Compliance tracking | 🔴 Advanced |

⚠️ **Privacy Note**: These examples use on-premise deployment patterns with local LLMs only. No participant data should ever be sent to cloud APIs.

```bash
cd examples/ndis-disability && python 51_ndis_provider.py
```

---

### 🏭 Industry (9 examples)
**Sector-specific AI solutions.**

| Example | Description | Level |
|---------|-------------|-------|
| `43_real_estate.py` | Property search & listings | 🔴 Advanced |
| `44_travel_booking.py` | Travel assistant | 🔴 Advanced |
| `45_education_tutor.py` | AI tutoring system | 🔴 Advanced |
| `46_finance_banking.py` | Banking assistant | 🔴 Advanced |
| `47_healthcare_portal.py` | Healthcare portal | 🔴 Advanced |
| `48_hospitality.py` | Hotel & restaurant | 🔴 Advanced |
| `49_automotive.py` | Automotive assistant | 🔴 Advanced |
| `50_insurance.py` | Insurance claims | 🔴 Advanced |
| `aged_care_compliance.py` | Aged Care Act 2024 compliance | 🔴 Advanced |

```bash
cd examples/industry && python 43_real_estate.py
```

---

### 🏠 Property (5 examples)
**Property management AI assistants.**

| Example | Description | Level |
|---------|-------------|-------|
| `55_property_manager.py` | Property portfolio management | 🔴 Advanced |
| `56_tenant_portal.py` | Tenant self-service | 🔴 Advanced |
| `57_landlord_portal.py` | Landlord dashboard | 🔴 Advanced |
| `58_property_maintenance.py` | Maintenance workflows | 🔴 Advanced |
| `59_strata_manager.py` | Strata management | 🔴 Advanced |

```bash
cd examples/property && python 55_property_manager.py
```

---

### 📚 RAG (6 examples)
**Retrieval-Augmented Generation patterns.**

| Example | Description | Level |
|---------|-------------|-------|
| `37_rag_documents.py` | Production document Q&A | 🔴 Advanced |
| `38_rag_codebase.py` | Code understanding | 🔴 Advanced |
| `39_rag_research.py` | Research assistant | 🔴 Advanced |
| `40_rag_catalog.py` | Product catalog | 🔴 Advanced |
| `41_rag_contracts.py` | Contract analysis | 🔴 Advanced |
| `42_rag_medical.py` | Medical knowledge | 🔴 Advanced |

```bash
cd examples/rag && python 37_rag_documents.py
```

---

### 💬 Customer Service (4 examples)
**Customer-facing AI assistants.**

| Example | Description | Level |
|---------|-------------|-------|
| `33_live_chat_support.py` | Live chat integration | 🔴 Advanced |
| `34_faq_escalation.py` | FAQ with human handoff | 🔴 Advanced |
| `35_multilingual_support.py` | Multi-language support | 🔴 Advanced |
| `36_voice_ivr.py` | Voice IVR system | 🔴 Advanced |

```bash
cd examples/customer-service && python 33_live_chat_support.py
```

---

### 🚀 Deployment (4 examples)
**Deploy agentic-brain anywhere.**

| Example | Description | Level |
|---------|-------------|-------|
| `24_onpremise_private.py` | On-premise/air-gapped | 🔴 Advanced |
| `25_hybrid_cloud.py` | Hybrid on-prem + cloud | 🔴 Advanced |
| `26_cloud_native.py` | Kubernetes/serverless | 🔴 Advanced |
| `27_edge_embedded.py` | IoT and edge devices | 🔴 Advanced |

```bash
cd examples/deployment && python 24_onpremise_private.py
```

---

## 🎮 Interactive Launcher

The `00_kitchen_sink.py` launcher lets you browse and run any example:

```bash
# Interactive menu
python examples/00_kitchen_sink.py

# List all examples
python examples/00_kitchen_sink.py --list

# Run a random example
python examples/00_kitchen_sink.py --random

# Browse specific category
python examples/00_kitchen_sink.py --category enterprise
```

---

## 🎯 Which Example Should I Start With?

```
New to agentic-brain?
  └── core/01_simple_chat.py ← Start here! (5 lines)

Want persistent memory?
  └── core/02_with_memory.py (requires Neo4j)

Building a chatbot?
  ├── core/03_streaming.py → Real-time UX
  ├── core/04_multi_user.py → Multi-tenant
  └── core/09_websocket.py → WebSocket

Document Q&A / RAG?
  ├── core/05_rag_basic.py → Simple RAG
  └── rag/37_rag_documents.py → Production

Production deployment?
  ├── core/08_api_server.py → REST API
  ├── core/10_with_auth.py → JWT auth
  └── deployment/26_cloud_native.py → Kubernetes

Australian NDIS?
  ├── ndis-disability/51_ndis_provider.py → Provider
  └── ndis-disability/60_sda_housing.py → SDA

Enterprise workforce?
  ├── enterprise/skills_graph.py → Skills mapping
  └── enterprise/career_opportunity_matcher.py → Mobility
```

---

## 📋 Prerequisites

### Required for All Examples

```bash
# Python 3.10+
python --version

# Install package
pip install -e "."
```

### Ollama (Most Examples)

```bash
# Install from https://ollama.ai
ollama pull llama3.1:8b
ollama pull nomic-embed-text  # For RAG
ollama serve
```

### Neo4j (Memory Examples)

```bash
# Docker (easiest)
docker run -d \
  --name neo4j \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### FastAPI (API Examples)

```bash
pip install fastapi uvicorn websockets pyjwt passlib[bcrypt]
```

---

## ✅ Verify Examples Work

```bash
# Syntax check all examples
python -m py_compile examples/**/*.py

# Test imports
cd /Users/joe/brain/agentic-brain
python -c "from agentic_brain import Agent; print('✓ Imports OK')"
```

---

## 📖 Example Levels

| Level | Badge | Description |
|-------|-------|-------------|
| Beginner | 🟢 | Simple, minimal dependencies |
| Intermediate | 🟡 | More features, some setup required |
| Advanced | 🔴 | Production patterns, full setup |

---

## 🔧 Troubleshooting

### "Connection refused" errors
```bash
# Ensure Ollama is running
ollama serve
```

### Neo4j connection issues
```bash
# Check Neo4j is accessible
curl http://localhost:7474
```

### Import errors
```bash
# Reinstall package
pip install -e ".[dev,api]"
```

---

## 📬 Contributing

1. Fork the repo
2. Create feature branch
3. Add example following naming convention: `XX_name.py`
4. Include proper docstring with SPDX header
5. Update category README.md
6. Submit PR

---

## 📖 More Resources

- [Full Documentation](../docs/)
- [API Reference](../docs/api/)
- [GitHub Issues](https://github.com/agentic-brain-project/agentic-brain/issues)

---

**Built with 💜 for the Australian AI community**
