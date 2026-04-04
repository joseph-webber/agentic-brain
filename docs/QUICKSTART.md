# 🚀 Quick Start Guide

Get your Agentic Brain up and running in 5 minutes.

## ⏱️ 5-Minute Setup

1. **Clone the repository**
2. **Install dependencies**
3. **Configure environment**
4. **Run the brain**

## 📋 Prerequisites

- **Python 3.11+**
- **Neo4j 5.x** (for memory graph)
- **Docker** (optional, for containerized run)

## 📦 Installation

### 1. Clone & Enter
```bash
git clone https://github.com/agentic-brain-project/brain.git
cd brain/agentic-brain
```

### 2. Set up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install agentic-brain
```

### 3. Set up Environment Variables
```bash
cp .env.example .env
# Edit .env with your keys (OpenAI, Neo4j, etc.)
```

## 🏃 First Run

### Start the Brain Core
```bash
python -m agentic_brain
```

## ⚠️ Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Ensure `venv` is activated and `pip install agentic-brain` ran successfully. |
| Neo4j Connection Failed | Check `NEO4J_URI` and credentials in `.env`. Ensure Neo4j is running. |
| API Key Errors | Verify your `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`. |

For more details, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
