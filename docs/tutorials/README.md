# Agentic Brain Tutorial Documentation Index

Complete tutorial documentation for building production-ready AI chatbots with persistent memory.

---

## 📚 Quick Navigation

| Document | Duration | Level | What You'll Learn |
|----------|----------|-------|-------------------|
| [**Getting Started**](./getting-started.md) | 5 min | Beginner | Installation, first bot, memory basics |
| [**Tutorial 1: Simple Chatbot**](./tutorials/01-simple-chatbot.md) | 15 min | Beginner | Custom personality, multi-turn conversations, error handling |
| [**Tutorial 2: Adding Memory**](./tutorials/02-adding-memory.md) | 20 min | Intermediate | Neo4j integration, storing facts, semantic search |
| [**Tutorial 3: RAG Chatbot**](./tutorials/03-rag-chatbot.md) | 25 min | Intermediate | Document retrieval, embeddings, grounded responses |
| [**Tutorial 4: Multi-User SaaS**](./tutorials/04-multi-user.md) | 30 min | Advanced | Tenants, access control, rate limiting, multi-tenancy |
| [**Tutorial 5: Production Deployment**](./tutorials/05-deployment.md) | 20 min | Advanced | Docker, Kubernetes, monitoring, security |

**Total Time:** ~115 minutes (less than 2 hours!)  
**Total Coverage:** From zero to production-ready SaaS chatbot

---

## 🎯 Learning Paths

### Path 1: "I just want a chatbot" ⚡
```
Getting Started (5 min)
    ↓
Tutorial 1: Simple Chatbot (15 min)
    ↓
You have a working chatbot!
```

### Path 2: "I want to build a startup" 🚀
```
Getting Started (5 min)
    ↓
Tutorial 1: Simple Chatbot (15 min)
    ↓
Tutorial 2: Adding Memory (20 min)
    ↓
Tutorial 4: Multi-User SaaS (30 min)
    ↓
Tutorial 5: Production Deployment (20 min)
    ↓
You're ready to launch!
```

### Path 3: "I need intelligent document Q&A" 📚
```
Getting Started (5 min)
    ↓
Tutorial 3: RAG Chatbot (25 min)
    ↓
You can answer questions about any documents
```

### Path 4: "I want to master everything" 🏆
```
Follow all tutorials in order (1-5)
    ↓
You're an expert in AI chatbots!
```

---

## 📖 Document Descriptions

### Getting Started (5 minutes)
**File:** `getting-started.md`

Your first step! This quick start covers:
- Installation in 3 commands
- Your first chatbot in 30 seconds
- How to add persistent memory
- Common troubleshooting

**Perfect for:** Anyone new to Agentic Brain

**Prerequisites:** Python 3.9+, Docker

**Expected outcome:** A working chatbot that remembers things between sessions

---

### Tutorial 1: Build Your First Chatbot (15 minutes)
**File:** `tutorials/01-simple-chatbot.md`

Create a production-ready chatbot with:
- System prompts and personality
- Multi-turn conversations
- Error handling
- Conversation logging
- Multiple LLM providers (Ollama, OpenAI, Anthropic)
- Multi-user support

**Perfect for:** Developers building chatbot applications

**Prerequisites:** Completed Getting Started guide

**Expected outcome:** A well-structured chatbot you can extend

**Code example:**
```python
bot = SimpleChatbot(name="assistant", user_id="demo_user_001")
response = bot.chat("Hello! I'm working on a Python project.")
# Bot remembers and references your project in follow-ups
```

---

### Tutorial 2: Adding Neo4j Memory (20 minutes)
**File:** `tutorials/02-adding-memory.md`

Master persistent memory with:
- Memory types (facts, skills, preferences, experiences)
- Neo4j graph database fundamentals
- Semantic search across memories
- User profiles from stored data
- Data export for GDPR compliance
- Memory cleanup and archival

**Perfect for:** Building knowledge-aware AI systems

**Prerequisites:** Tutorial 1 completed

**Expected outcome:** Chatbots that build rich knowledge about users

**Code example:**
```python
memory = AdvancedMemory(uri="bolt://localhost:7687")
memory.store_memory(UserMemory(
    user_id="alice",
    memory_type=MemoryType.SKILL,
    content="Expert in Python and FastAPI"
))

# Later, retrieve and use
profile = memory.get_user_profile("alice")
print(profile.skills)  # ["Expert in Python and FastAPI"]
```

---

### Tutorial 3: RAG Chatbot (25 minutes)
**File:** `tutorials/03-rag-chatbot.md`

Ground responses in documents with:
- Document loading and chunking
- Semantic search with embeddings
- Retrieval-Augmented Generation (RAG) workflow
- Source citation in responses
- Knowledge base management
- Keyword and semantic search fallback

**Perfect for:** Building Q&A systems, knowledge base assistants

**Prerequisites:** Tutorial 1-2 completed

**Expected outcome:** Chatbot that answers questions accurately based on your documents

**Use cases:**
- Customer support (knowledge base)
- Technical documentation
- FAQ assistant
- Legal document Q&A

**Code example:**
```python
bot = RAGChatbot(
    name="support_agent",
    user_id="demo_user",
    documents_dir="./knowledge_base",
    use_embeddings=True
)

response = bot.chat("What's your refund policy?")
# Bot retrieves policy from documents and cites source
# Output: "...30-day refunds... (Source: refund_policy.txt)"
```

---

### Tutorial 4: Multi-User SaaS (30 minutes)
**File:** `tutorials/04-multi-user.md`

Build enterprise-grade multi-tenancy with:
- Tenant models and data isolation
- User roles and access control
- Rate limiting per customer
- Usage analytics
- Billing integration points
- FastAPI endpoints with auth
- SaaS architecture patterns

**Perfect for:** Building chatbot platforms, selling AI services

**Prerequisites:** Tutorials 1-3 completed

**Expected outcome:** A multi-tenant SaaS chatbot backend

**Architecture:**
```
┌─────────────────────────────────────┐
│    Your SaaS API                    │
├─────────────────────────────────────┤
│ Customer A │ Customer B │ Customer C│
│ (isolated) │ (isolated) │ (isolated)│
└─────────────────────────────────────┘
     │           │           │
     └───────────┴───────────┘
            ↓
        Shared Database
        (Neo4j + Redis)
```

**Code example:**
```python
# Create tenants
customer_a = tenant_manager.create_tenant("acme_corp", "ACME", tier=TenantTier.PRO)
customer_b = tenant_manager.create_tenant("widgets_inc", "Widgets", tier=TenantTier.FREE)

# Chat with isolation
response = chatbot.chat(
    tenant_id="acme_corp",
    user_id="alice",
    message="Hello!"
)  # Alice's data is isolated from Widgets' users
```

---

### Tutorial 5: Production Deployment (20 minutes)
**File:** `tutorials/05-deployment.md`

Deploy to production with:
- Multi-stage Docker builds
- Docker Compose full stack
- Kubernetes manifests
- Health checks and readiness probes
- Prometheus + Grafana monitoring
- Security hardening
- Zero-downtime deployments
- Production backup strategies

**Perfect for:** DevOps, platform engineers, production readiness

**Prerequisites:** Tutorials 1-4 completed

**Expected outcome:** Production-ready deployment with monitoring

**Stack includes:**
- Neo4j (graph database)
- Redis (caching)
- Ollama (local LLM)
- Prometheus (metrics)
- Grafana (dashboards)

**Quick start:**
```bash
docker-compose up -d
# All services online with health checks

curl http://localhost:8000/health
# {"status": "ok", "version": "0.1.0"}
```

---

## 🔑 Key Concepts Covered

### Core Architecture
- **Neo4j**: Graph database for persistent knowledge
- **Sessions**: User conversation state
- **Memory**: Facts, preferences, experiences
- **Embeddings**: Semantic search via sentence transformers
- **RAG**: Retrieval-Augmented Generation for grounding

### LLM Providers
- Ollama (local, open-source)
- OpenAI (GPT-3.5, GPT-4)
- Anthropic (Claude)
- Custom providers via LLMRouter

### Deployment
- Docker containerization
- Docker Compose orchestration
- Kubernetes scaling
- Health checks and monitoring
- Production security

### Enterprise Features
- Multi-tenancy with data isolation
- Role-based access control (RBAC)
- Rate limiting and quotas
- Usage analytics
- GDPR data export
- Audit logging

---

## 📋 Prerequisites Progression

| Tutorial | Requires | Time to Setup |
|----------|----------|--------------|
| Getting Started | Python 3.9+, Docker | ~5 min |
| Tutorial 1 | Getting Started complete | 0 min |
| Tutorial 2 | Tutorial 1 complete | 0 min |
| Tutorial 3 | sentence-transformers | ~5 min (first run slow) |
| Tutorial 4 | FastAPI (pip install) | ~2 min |
| Tutorial 5 | Docker Compose | ~1 min |

---

## 🛠️ Common Use Cases & Which Tutorial

| Use Case | Start Here | Why |
|----------|-----------|-----|
| Chatbot for my website | Tutorial 1 | Simple, self-contained |
| Support bot that learns | Tutorial 2 | Memory integration key |
| Q&A over my docs | Tutorial 3 | RAG perfect for this |
| White-label chatbot SaaS | Tutorial 4 | Multi-tenancy required |
| Production deployment | Tutorial 5 | Scale and monitor |
| All of the above | Tutorials 1-5 | Full stack |

---

## 🆘 Troubleshooting

### By Tutorial

**Getting Started Issues?**
→ See "Troubleshooting" section in [getting-started.md](./getting-started.md#troubleshooting)

**Tutorial 1 Issues?**
→ See "Troubleshooting" section in [01-simple-chatbot.md](./tutorials/01-simple-chatbot.md#troubleshooting)

**Tutorial 2 Issues?**
→ See "Troubleshooting" section in [02-adding-memory.md](./tutorials/02-adding-memory.md#troubleshooting)

**Tutorial 3 Issues?**
→ See "Troubleshooting" section in [03-rag-chatbot.md](./tutorials/03-rag-chatbot.md#troubleshooting)

**Tutorial 4 Issues?**
→ See "Troubleshooting" section in [04-multi-user.md](./tutorials/04-multi-user.md#troubleshooting)

**Tutorial 5 Issues?**
→ See "Troubleshooting" section in [05-deployment.md](./tutorials/05-deployment.md#troubleshooting)

### Common Issues Across All Tutorials

```
Neo4j connection refused
→ docker ps | grep neo4j
→ docker run -d -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest

Ollama not responding
→ ollama serve (if local) or use OpenAI/Anthropic

Python version too old
→ python3 --version should be 3.9+

Import errors
→ pip install -r requirements.txt
```

---

## 💡 Pro Tips

### 1. Development vs Production
- **Dev:** Use Ollama locally (free, no API keys)
- **Prod:** Use cloud LLMs (faster, better models) or large Ollama instances

### 2. Memory Best Practices
- Always pass `user_id` for proper isolation
- Don't store sensitive data in memories (compliance!)
- Regularly archive old conversations
- Use `confidence` field to weight memories

### 3. RAG Best Practices
- Test with your actual documents first
- Chunk size of 500-1000 characters usually works well
- Enable embeddings for better retrieval
- Monitor query performance

### 4. Multi-Tenancy Best Practices
- Always scope user IDs by tenant: `f"{tenant_id}#{user_id}"`
- Enforce rate limits strictly
- Audit all administrative actions
- Test data isolation thoroughly

### 5. Production Best Practices
- Use Docker Compose locally, Kubernetes in prod
- Monitor CPU/memory constantly
- Set up alerting for service failures
- Test disasters recovery regularly

---

## 📚 Additional Resources

### Official Documentation
- [Agentic Brain README](../../README.md)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [LangChain RAG Guide](https://python.langchain.com/docs/modules/data_connection/retrieval/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

### Related Tools & Libraries
- [sentence-transformers](https://www.sbert.net/) - Embeddings
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [LangChain](https://python.langchain.com/) - LLM orchestration
- [FastAPI](https://fastapi.tiangolo.com/) - API framework

### Learning Resources
- [RAG explained](https://blogs.nvidia.com/blog/what-is-retrieval-augmented-generation/)
- [Graph databases guide](https://neo4j.com/developer/graph-database/)
- [Multi-tenancy patterns](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/)
- [Docker security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)

---

## 🎓 Your Learning Journey

```
START HERE
    ↓
[Getting Started] - 5 minutes
    ↓
[Tutorial 1] Simple Chatbot - 15 minutes
    ↓
[Tutorial 2] Memory - 20 minutes
    ✓ You can build chatbots with memory!
    ↓
[Tutorial 3] RAG - 25 minutes
    ✓ You can answer Q&A over documents!
    ↓
[Tutorial 4] SaaS - 30 minutes
    ✓ You can serve multiple customers!
    ↓
[Tutorial 5] Deployment - 20 minutes
    ✓ You can run in production!
    ↓
YOU ARE AN AGENTIC BRAIN EXPERT! 🎉
```

---

## 🤝 Contributing

Found an issue or improvement? 
- Check existing docs for answers
- File issues on GitHub
- Submit PRs for improvements
- Share your use cases in discussions

---

## 📞 Support

**Questions about a specific tutorial?**
- Check the troubleshooting section in that tutorial
- Look for the PRE-REQUISITES section to verify setup

**General questions?**
- Check the main [README](../../README.md)
- See the [FAQ](../faq.md) if it exists
- Open an issue on GitHub

**Having trouble following along?**
- Start with Getting Started, don't skip steps
- Make sure each prerequisite is installed
- Run health checks frequently
- Check service logs: `docker-compose logs service_name`

---

## 📄 License

All tutorials and documentation are part of Agentic Brain, licensed under GPL-3.0.

---

**Ready to build?** Start with [Getting Started](./getting-started.md) →

**Want to contribute?** See [CONTRIBUTING.md](../../CONTRIBUTING.md)

**Have feedback?** [Open an issue](https://github.com/yourusername/agentic-brain/issues)

---

<div align="center">

**Made with ❤️ for developers building intelligent systems**

[Getting Started](./getting-started.md) • [Tutorials](./tutorials/) • [README](../../README.md) • [Issues](https://github.com/yourusername/agentic-brain/issues)

</div>
