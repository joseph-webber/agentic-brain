# 🚀 Agentic Brain - Quick Setup Guide

Get up and running in 15 minutes with the recommended stack.

## 📋 Prerequisites

| Tool | Why | Cost |
|------|-----|------|
| **GitHub Account** | Code hosting, authentication | Free |
| **GitHub Copilot Pro+** | AI pair programming, agents | $39/month (recommended) |
| **Python 3.11+** | Runtime | Free |
| **Neo4j** | Knowledge graph memory (optional) | Free (Community) |

---

# 🍎 macOS Setup

## 1️⃣ Install Homebrew (if not installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

## 2️⃣ Install All Tools

```bash
# Install everything in one go
brew install gh python@3.11 git

# Verify
gh --version
python3 --version
git --version
```

## 3️⃣ GitHub CLI Auth

```bash
gh auth login
```
- Select: **GitHub.com**
- Select: **SSH**
- Generate new SSH key: **Yes**
- Passphrase: **[Press Enter - leave empty]**
- Auth method: **Login with a web browser**

## 4️⃣ Install Copilot

```bash
gh extension install github/gh-copilot
gh copilot --version
```

## 5️⃣ Clone & Run

```bash
gh repo clone agentic-brain-project/agentic-brain
cd agentic-brain
python3 -m venv venv
source venv/bin/activate
pip install -e ".[all]"
pytest tests/ -v
```

---

# 🪟 Windows Setup

## 1️⃣ Install Windows Terminal (Recommended)

Download from Microsoft Store: **Windows Terminal**

## 2️⃣ Install Git Bash

Download: https://git-scm.com/download/win

During install, choose:
- ✅ Git Bash Here
- ✅ Use Git from Windows Command Prompt
- ✅ Use OpenSSH
- ✅ Checkout as-is, commit Unix-style

## 3️⃣ Install Python

Download: https://www.python.org/downloads/

During install:
- ✅ **Add Python to PATH** (IMPORTANT!)
- ✅ Install pip

Verify in Git Bash:
```bash
python --version
pip --version
```

## 4️⃣ Install GitHub CLI

**Option A - Winget (Windows 11):**
```powershell
winget install GitHub.cli
```

**Option B - Download installer:**
https://cli.github.com/

Verify:
```bash
gh --version
```

## 5️⃣ GitHub CLI Auth (in Git Bash)

```bash
gh auth login
```
- Select: **GitHub.com**
- Select: **SSH**
- Generate new SSH key: **Yes**
- Passphrase: **[Press Enter - leave empty]**
- Auth method: **Login with a web browser**

## 6️⃣ Install Copilot

```bash
gh extension install github/gh-copilot
gh copilot --version
```

## 7️⃣ Clone & Run (Git Bash)

```bash
gh repo clone agentic-brain-project/agentic-brain
cd agentic-brain
python -m venv venv
source venv/Scripts/activate
pip install -e ".[all]"
pytest tests/ -v
```

### Windows PowerShell Alternative

```powershell
gh repo clone agentic-brain-project/agentic-brain
cd agentic-brain
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[all]"
pytest tests/ -v
```

---

# 🐧 Linux Setup

## Ubuntu/Debian

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y git python3 python3-pip python3-venv curl

# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Verify
gh --version
python3 --version
```

## Fedora/RHEL/CentOS

```bash
# Install dependencies
sudo dnf install -y git python3 python3-pip curl

# Install GitHub CLI
sudo dnf install 'dnf-command(config-manager)'
sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
sudo dnf install gh

# Verify
gh --version
```

## Arch Linux

```bash
sudo pacman -S git python python-pip github-cli
```

## All Linux - Auth & Clone

```bash
# GitHub auth
gh auth login
# Select: GitHub.com → SSH → Yes → [Enter for no passphrase] → Web browser

# Install Copilot
gh extension install github/gh-copilot

# Clone and run
gh repo clone agentic-brain-project/agentic-brain
cd agentic-brain
python3 -m venv venv
source venv/bin/activate
pip install -e ".[all]"
pytest tests/ -v
```

---

# 🔧 All Platforms - GitHub Auth Defaults

When running `gh auth login`, use these settings for the easiest setup:

| Prompt | Choose |
|--------|--------|
| What account? | **GitHub.com** |
| Preferred protocol? | **SSH** |
| Generate new SSH key? | **Yes** |
| Passphrase? | **[Press Enter - empty]** |
| Title for SSH key? | **[Press Enter - default]** |
| How to authenticate? | **Login with a web browser** |

This creates an SSH key with NO passphrase (easiest) and adds it to GitHub automatically.

### Authenticate with GitHub

```bash
gh auth login
```

Choose these options (press Enter for defaults):
```
? What account do you want to log into? GitHub.com
? What is your preferred protocol for Git operations? SSH
? Generate a new SSH key to add to your GitHub account? Yes
? Enter a passphrase for your new SSH key (Optional): [PRESS ENTER - no passphrase]
? Title for your SSH key: GitHub CLI
? How would you like to authenticate GitHub CLI? Login with a web browser
```

✅ **Done!** Your SSH key is created and added to GitHub automatically.

### Verify it works

```bash
gh auth status
```

You should see:
```
✓ Logged in to github.com as YOUR-USERNAME
✓ Git operations configured to use ssh protocol
✓ Token: gho_xxxx
```

---

## 2️⃣ GitHub Copilot Setup (5 min)

### Install Copilot CLI Extension

```bash
gh extension install github/gh-copilot
```

### Verify installation

```bash
gh copilot --version
```

### Start using Copilot

```bash
# Ask questions
gh copilot suggest "how to create a Python virtual environment"

# Explain code
gh copilot explain "git rebase -i HEAD~3"
```

---

## 3️⃣ Recommended GitHub Plan

### GitHub Copilot Pro+ ($39/month) ⭐ RECOMMENDED

| Feature | Pro ($10) | Pro+ ($39) |
|---------|-----------|------------|
| Premium AI requests | 300/month | **1,500/month** |
| Claude & GPT-4.5 | ✅ | ✅ |
| Agent mode | ✅ | ✅ |
| Priority support | ❌ | ✅ |

**Why Pro+?**
- 5x more AI requests than Pro
- Never hit rate limits during heavy coding sessions
- Access to ALL premium models (Claude Opus, GPT-4.5)
- Best value for professional developers

**Sign up:** https://github.com/settings/copilot

---

## 4️⃣ Clone Agentic Brain

```bash
# Clone the repo
gh repo clone agentic-brain-project/agentic-brain

# Enter directory
cd agentic-brain

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[all]"
```

---

## 5️⃣ Neo4j Setup (Optional but Recommended)

### Quick Install (Docker)

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:5
```

### Or Download Desktop

https://neo4j.com/download/

### Connect in Python

```python
from agentic_brain import Memory

memory = Memory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your-password"
)
```

---

## 6️⃣ Environment Variables

Create `.env` file:

```bash
# Neo4j (optional - uses in-memory if not set)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# OpenAI (optional - for LLM features)
OPENAI_API_KEY=sk-...

# Ollama (optional - for local LLM)
OLLAMA_HOST=http://localhost:11434
```

---

## 7️⃣ Verify Installation

```bash
# Run tests
pytest tests/ -v

# Quick check
python -c "from agentic_brain import Memory, Agent; print('✅ Ready!')"
```

---

## 🎯 Quick Start Code

```python
from agentic_brain import Memory, Agent, LLMRouter

# Initialize memory (Neo4j knowledge graph)
memory = Memory()

# Create an agent
agent = Agent(
    name="assistant",
    memory=memory,
    skills=["search", "summarize"]
)

# Use the agent
response = agent.run("What do you know about Python?")
print(response)
```

---

## 🆘 Troubleshooting

### "gh: command not found"
```bash
# macOS
brew install gh

# Or add to PATH
export PATH="$PATH:/usr/local/bin"
```

### SSH key issues
```bash
# Regenerate
gh auth refresh
gh auth setup-git
```

### Neo4j connection refused
```bash
# Check if running
docker ps | grep neo4j

# Restart
docker restart neo4j
```

### Python version issues
```bash
# Check version (need 3.9+)
python3 --version

# Use pyenv if needed
pyenv install 3.11
pyenv global 3.11
```

---

## 📚 Next Steps

1. **Read the README** - Core concepts and examples
2. **Explore examples/** - Working code samples
3. **Join discussions** - GitHub Discussions for questions
4. **Build something!** - Start with a simple agent

---

## 🔗 Resources

- **GitHub Copilot:** https://github.com/features/copilot
- **Neo4j Docs:** https://neo4j.com/docs/
- **Ollama (Local LLM):** https://ollama.ai
- **OpenAI API:** https://platform.openai.com

---

*Made with 💜 by Agentic Brain Contributors*
