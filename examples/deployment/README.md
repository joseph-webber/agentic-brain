# 🚀 Deployment Examples

> Deploy agentic-brain anywhere - on-premise, hybrid, cloud, or edge.

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 24 | [onpremise_private.py](24_onpremise_private.py) | Private data, no cloud LLMs | 🔴 Advanced |
| 25 | [hybrid_cloud.py](25_hybrid_cloud.py) | Mixed on-prem + cloud | 🔴 Advanced |
| 26 | [cloud_native.py](26_cloud_native.py) | Kubernetes/serverless | 🔴 Advanced |
| 27 | [edge_embedded.py](27_edge_embedded.py) | IoT and edge devices | 🔴 Advanced |

## Quick Start

```bash
# On-premise deployment (privacy-first)
python examples/deployment/24_onpremise_private.py

# Hybrid cloud
python examples/deployment/25_hybrid_cloud.py

# Cloud-native Kubernetes
python examples/deployment/26_cloud_native.py
```

## Deployment Patterns

### On-Premise Private
- **Use case**: Sensitive data, compliance requirements
- **Architecture**: Ollama local LLM + Neo4j on-premise
- **Data**: Never leaves your infrastructure
- **Compliance**: HIPAA, GDPR, Australian Privacy Act

### Hybrid Cloud
- **Use case**: Balance privacy with cloud capabilities
- **Architecture**: Local LLM for sensitive, cloud for general
- **Data routing**: Smart routing based on sensitivity
- **Benefits**: Best of both worlds

### Cloud Native
- **Use case**: Scalability, managed infrastructure
- **Architecture**: Kubernetes pods, serverless functions
- **Scaling**: Horizontal auto-scaling
- **Providers**: AWS, GCP, Azure, Vercel

### Edge/Embedded
- **Use case**: IoT, offline, low-latency
- **Architecture**: Small models on edge devices
- **Hardware**: Raspberry Pi, Jetson, mobile
- **Network**: Works offline, syncs when connected

## Architecture Diagrams

### On-Premise
```
┌─────────────────────────────────┐
│       YOUR INFRASTRUCTURE       │
│  ┌─────────┐  ┌─────────────┐  │
│  │ Ollama  │  │   Neo4j     │  │
│  │ (Local) │◄─┤ (Encrypted) │  │
│  └─────────┘  └─────────────┘  │
│       ▲              ▲         │
│       └──────────────┘         │
│      ALL DATA STAYS LOCAL      │
└─────────────────────────────────┘
```

### Hybrid Cloud
```
┌─────────────────┐     ┌─────────────────┐
│   ON-PREMISE    │     │     CLOUD       │
│  ┌───────────┐  │     │  ┌───────────┐  │
│  │ Sensitive │  │     │  │  General  │  │
│  │   Data    │  │     │  │   Tasks   │  │
│  └───────────┘  │     │  └───────────┘  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────┬───────────────┘
                 │
         ┌───────▼───────┐
         │ Smart Router  │
         └───────────────┘
```

## Common Patterns

### Privacy-First Deployment
```python
from agentic_brain import Agent

# Force local LLM only
agent = Agent(
    provider="ollama",
    model="llama3.1:8b",
    allow_cloud=False  # Never use cloud
)
```

### Hybrid Routing
```python
def is_sensitive(text):
    # Check for PII, confidential keywords
    return any(word in text.lower() for word in ["ssn", "credit card", "password"])

if is_sensitive(user_input):
    response = local_agent.chat(user_input)
else:
    response = cloud_agent.chat(user_input)
```

## Prerequisites

- Python 3.10+
- Ollama (for local deployment)
- Docker/Kubernetes (for cloud-native)
- Edge device SDK (for embedded)
