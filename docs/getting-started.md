# Getting Started with Agentic Brain

**5-Minute Quick Start Guide**

Build your first AI chatbot with persistent memory in under 5 minutes.

---

## Prerequisites

- **Python 3.9+** installed
- **Docker** (for Neo4j) or Neo4j running locally
- **pip** package manager

---

## 1️⃣ Installation (1 minute)

### Step 1: Install Agentic Brain

```bash
pip install agentic-brain
```

### Step 2: Start Neo4j (for persistent memory)

**Option A: Docker (Recommended)**
```bash
docker run -d \
  --name neo4j \
  -p 7687:7687 \
  -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

**Option B: Local Installation**
```bash
# macOS
brew install neo4j

# Ubuntu/Debian
sudo apt-get install neo4j

# Start the service
sudo systemctl start neo4j
```

✅ **Neo4j is ready when you see:**
```
Starting Neo4j...
INFO  Started neo4j (pid 12345)
```

---

## 2️⃣ Create Your First Chatbot (2 minutes)

Create a new file `my_first_bot.py`:

```python
from agentic_brain import Agent, Neo4jMemory

# Initialize memory (connects to Neo4j)
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password"
)

# Create a chatbot agent
bot = Agent(
    name="assistant",
    memory=memory,
    llm_provider="ollama",  # or "openai", "anthropic"
    llm_model="mistral"      # or your preferred model
)

# Have a conversation
print("🤖 Bot is ready! Let's chat...\n")

# First turn: Chat with a fact
response = bot.chat(
    "Hello! Remember this: I work in marketing and love data-driven campaigns.",
    user_id="user_123"
)
print(f"Bot: {response}\n")

# Second turn: Bot recalls the fact
response = bot.chat(
    "What do I work in? What do I love?",
    user_id="user_123"
)
print(f"Bot: {response}")
```

### Run Your Bot

```bash
python my_first_bot.py
```

**Expected Output:**
```
🤖 Bot is ready! Let's chat...

Bot: Hello! I've remembered that you work in marketing and love data-driven campaigns. How can I help you today?

Bot: You work in marketing and you love data-driven campaigns. That's a great combination! With your focus on data-driven strategies, I can help you analyze campaign performance, identify trends, and optimize your marketing efforts.
```

✅ **Success!** Your bot remembered context between messages!

---

## 3️⃣ Add Memory (1 minute)

By default, memory persists across bot restarts. Here's how to leverage it:

### Save Important Context

```python
from agentic_brain import Agent, Neo4jMemory

memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password"
)

bot = Agent(
    name="assistant",
    memory=memory,
    llm_provider="ollama",
    llm_model="mistral"
)

# Store a personal preference
bot.chat(
    "I prefer detailed explanations with examples.",
    user_id="user_456"
)

# Store work context
bot.chat(
    "I'm building a Python API using FastAPI.",
    user_id="user_456"
)

# Later session - even after restart!
bot = Agent(name="assistant", memory=memory, ...)
response = bot.chat(
    "Help me structure my project",
    user_id="user_456"
)
# Bot will remember your preferences and tech stack!
```

### Query Memory

```python
# Retrieve all facts about a user
facts = memory.get_user_facts("user_456")
print(f"Stored facts: {facts}")

# Get conversation history
history = memory.get_conversation_history("user_456", limit=10)
for msg in history:
    print(f"{msg['role']}: {msg['content']}")
```

---

## 4️⃣ Next Steps

### 📚 Learn More

| Goal | Tutorial | Time |
|------|----------|------|
| Build a more sophisticated chatbot | [Simple Chatbot Tutorial](./tutorials/01-simple-chatbot.md) | 15 min |
| Integrate Neo4j memory deeply | [Adding Memory](./tutorials/02-adding-memory.md) | 20 min |
| Answer questions about documents | [RAG Chatbot](./tutorials/03-rag-chatbot.md) | 25 min |
| Serve multiple users/customers | [Multi-User SaaS](./tutorials/04-multi-user.md) | 30 min |
| Deploy to production | [Docker Deployment](./tutorials/05-deployment.md) | 20 min |

### 🎯 Quick Examples

**Example 1: Customer Support Bot**
```python
bot = Agent(
    name="support_agent",
    memory=memory,
    system_prompt="""You are a friendly customer support agent.
    Remember customer preferences and past issues.
    Always provide helpful, detailed responses."""
)

# Handle customer queries across sessions
response = bot.chat(
    "I'm having trouble with my account",
    user_id="customer_789"
)
```

**Example 2: Knowledge Assistant**
```python
# RAG: Ground responses in documents
documents = [
    {"content": "Our API returns JSON responses", "title": "API Guide"},
    {"content": "Use Bearer tokens for authentication", "title": "Auth"},
]

response = bot.chat(
    "How do I authenticate?",
    user_id="dev_001",
    context_docs=documents  # Bot uses these to ground response
)
```

**Example 3: Multi-User Bot**
```python
# Each user gets their own memory/context
for user_id in ["alice_001", "bob_002", "charlie_003"]:
    response = bot.chat(
        "Tell me about yourself",
        user_id=user_id
    )
    print(f"{user_id}: {response}")
```

---

## 🆘 Troubleshooting

### ❌ "Connection refused" error

**Problem:** Neo4j isn't running
```
Connection error: Failed to connect to bolt://localhost:7687
```

**Solution:**
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# If not, start it
docker run -d -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

### ❌ "Authentication failed"

**Problem:** Wrong Neo4j password
```
AuthError: Invalid username or password
```

**Solution:**
```python
# Use the correct credentials
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="your_actual_password"  # Check docker-compose.yml
)
```

### ❌ "Ollama not running"

**Problem:** LLM model not available
```
LLMError: Failed to connect to Ollama
```

**Solution:**
```bash
# Install Ollama: https://ollama.ai
# Then pull a model
ollama pull mistral

# Or use cloud provider
agent = Agent(
    name="assistant",
    memory=memory,
    llm_provider="openai",
    llm_model="gpt-3.5-turbo",
    api_key="sk-..."
)
```

### ❌ "No memories saved"

**Problem:** Chatbot not storing facts
```
# After restart, bot doesn't remember
response = bot.chat("Do you remember what I said?")
# "I don't have any previous context about you"
```

**Solution:**
```python
# Ensure memory is initialized
if memory is None:
    memory = Neo4jMemory(...)
    bot = Agent(name="assistant", memory=memory)

# Verify Neo4j has data
facts = memory.get_user_facts(user_id)
print(f"Stored facts: {facts}")
if not facts:
    print("Memory not being saved. Check Neo4j connection.")
```

---

## 🚀 What's Next?

You now have:
- ✅ A working chatbot
- ✅ Persistent memory
- ✅ Multi-user support

Ready to level up? Check out the [Simple Chatbot Tutorial](./tutorials/01-simple-chatbot.md) to learn advanced features like:
- Custom system prompts
- Conversation templates
- Error handling
- Production deployment

---

## 💡 Pro Tips

1. **Always pass `user_id`** — It's how the bot isolates memories
2. **Neo4j persists everything** — Even if you restart the bot, memories stay
3. **Test locally first** — Use Ollama before deploying with cloud APIs
4. **Monitor token usage** — Set limits if using paid LLMs

---

**Questions?** Check [tutorials/](./tutorials/) or see [README.md](../README.md)

Happy building! 🧠
