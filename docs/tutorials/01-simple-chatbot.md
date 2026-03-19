# Tutorial 1: Build Your First Chatbot

**Objective:** Create a production-ready chatbot with custom personality, conversation templates, and error handling.

**Time:** 15 minutes  
**Difficulty:** Beginner  
**Prerequisites:** Python 3.9+, Neo4j running locally or in Docker

---

## What You'll Build

A helpful assistant chatbot that:
- Has a defined personality and system prompt
- Handles multi-turn conversations naturally
- Manages errors gracefully
- Logs interactions for debugging

---

## Prerequisites Checklist

```bash
# 1. Verify Python
python3 --version  # Should be 3.9+

# 2. Install agentic-brain (if not already)
pip install agentic-brain

# 3. Verify Neo4j is running
docker ps | grep neo4j

# If Neo4j isn't running:
docker run -d \
  --name neo4j \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 4. Verify Ollama or set up API key
# Option A: Use Ollama locally
ollama pull mistral

# Option B: Use OpenAI
export OPENAI_API_KEY="sk-your-key-here"
```

---

## Step 1: Create Project Structure

```bash
mkdir my_chatbot
cd my_chatbot
touch bot.py config.py requirements.txt
```

**Directory layout:**
```
my_chatbot/
├── bot.py           # Main bot logic
├── config.py        # Configuration
├── requirements.txt # Dependencies
└── conversation_log.txt  # Chat history
```

---

## Step 2: Set Up Configuration

Create `config.py`:

```python
"""
Configuration for the chatbot.

Manages LLM provider, Neo4j connection, and bot personality.
"""

import os
from enum import Enum

# LLM Configuration
class LLMProvider(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

# Choose your LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", LLMProvider.OLLAMA.value)
LLM_MODEL = os.getenv("LLM_MODEL", "mistral")

# For OpenAI/Anthropic
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Neo4j Connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Bot Personality
SYSTEM_PROMPT = """You are a helpful, knowledgeable assistant.

Your traits:
- Friendly and professional tone
- Concise but thorough explanations
- Ask clarifying questions when needed
- Remember context from earlier in the conversation
- Admit when you don't know something
- Provide examples when helpful

Always prioritize being helpful and accurate."""

# Logging
LOG_FILE = "conversation_log.txt"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
```

---

## Step 3: Build the Chatbot

Create `bot.py`:

```python
"""
Simple Chatbot with Neo4j Memory

Features:
- Multi-turn conversations
- Persistent memory
- Error handling
- Conversation logging
"""

import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from agentic_brain import Agent, Neo4jMemory
import config

# Set up logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleChatbot:
    """A friendly chatbot with memory."""
    
    def __init__(self, name: str = "assistant", user_id: str = "default_user"):
        """
        Initialize the chatbot.
        
        Args:
            name: Bot's name (used for identification)
            user_id: Unique user identifier (for multi-user scenarios)
        """
        self.name = name
        self.user_id = user_id
        self.conversation_history: List[Dict[str, str]] = []
        
        # Initialize memory
        try:
            self.memory = Neo4jMemory(
                uri=config.NEO4J_URI,
                username=config.NEO4J_USERNAME,
                password=config.NEO4J_PASSWORD
            )
            logger.info(f"✅ Connected to Neo4j at {config.NEO4J_URI}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {e}")
            self.memory = None
            raise
        
        # Initialize bot agent
        try:
            self.agent = Agent(
                name=name,
                memory=self.memory,
                llm_provider=config.LLM_PROVIDER,
                llm_model=config.LLM_MODEL,
                system_prompt=config.SYSTEM_PROMPT
            )
            logger.info(f"✅ Bot '{name}' initialized with {config.LLM_PROVIDER}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize agent: {e}")
            raise
    
    def chat(self, user_message: str) -> Optional[str]:
        """
        Send a message and get a response.
        
        Args:
            user_message: The user's input
            
        Returns:
            The bot's response, or None if an error occurred
        """
        try:
            # Log incoming message
            logger.info(f"User ({self.user_id}): {user_message}")
            self.conversation_history.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })
            
            # Get response from agent
            response = self.agent.chat(
                message=user_message,
                user_id=self.user_id
            )
            
            if not response:
                logger.warning("Empty response from agent")
                return "I apologize, I couldn't generate a response. Please try again."
            
            # Log response
            logger.info(f"Bot ({self.name}): {response}")
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Save to log file
            self._save_conversation()
            
            return response
            
        except Exception as e:
            logger.error(f"Error during chat: {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}"
    
    def get_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get recent conversation history.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        return self.conversation_history[-limit:]
    
    def get_stored_facts(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve facts stored about the user.
        
        Returns:
            Dictionary of stored facts, or None if memory is unavailable
        """
        if not self.memory:
            logger.warning("Memory not available")
            return None
        
        try:
            facts = self.memory.get_user_facts(self.user_id)
            logger.info(f"Retrieved {len(facts) if facts else 0} facts for {self.user_id}")
            return facts
        except Exception as e:
            logger.error(f"Failed to retrieve facts: {e}")
            return None
    
    def clear_history(self) -> None:
        """Clear local conversation history (memory persists in Neo4j)."""
        self.conversation_history = []
        logger.info(f"Conversation history cleared for {self.user_id}")
    
    def _save_conversation(self) -> None:
        """Save conversation to log file."""
        try:
            with open(config.LOG_FILE, "a") as f:
                f.write(json.dumps(self.conversation_history[-1]) + "\n")
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")


def main():
    """Main entry point - demonstrate the chatbot."""
    
    print("\n" + "="*60)
    print("🤖 Simple Chatbot Demo")
    print("="*60 + "\n")
    
    # Create bot
    bot = SimpleChatbot(
        name="assistant",
        user_id="demo_user_001"
    )
    
    # Example conversation
    messages = [
        "Hello! I'm working on a Python project and need advice on database design.",
        "I need to store user profiles, conversation history, and preferences. What would you recommend?",
        "That's helpful! Should I use relationships in the database?"
    ]
    
    for user_input in messages:
        print(f"👤 You: {user_input}")
        response = bot.chat(user_input)
        print(f"🤖 Bot: {response}\n")
    
    # Show what the bot remembers
    print("\n" + "-"*60)
    print("💾 Stored Facts About You:")
    print("-"*60)
    facts = bot.get_stored_facts()
    if facts:
        for fact in facts:
            print(f"  • {fact}")
    else:
        print("  No facts stored yet")
    
    # Show conversation history
    print("\n" + "-"*60)
    print("📝 Conversation History:")
    print("-"*60)
    for msg in bot.get_history():
        role = msg["role"].upper()
        print(f"{role}: {msg['content'][:80]}...")
    
    print("\n✅ Demo complete! Check 'conversation_log.txt' for full history.\n")


if __name__ == "__main__":
    main()
```

---

## Step 4: Create Requirements File

Create `requirements.txt`:

```
agentic-brain>=0.1.0
neo4j>=5.14.0
openai>=1.0.0  # Optional: for OpenAI support
anthropic>=0.7.0  # Optional: for Anthropic support
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Step 5: Run Your Chatbot

```bash
python bot.py
```

**Expected Output:**

```
============================================================
🤖 Simple Chatbot Demo
============================================================

👤 You: Hello! I'm working on a Python project and need advice on database design.
🤖 Bot: Hello! I'd be happy to help with your Python database design question. To give you the best advice, could you tell me:

1. What type of data are you storing (user data, transactions, etc.)?
2. How much data do you expect to handle?
3. Do you need complex relationships between data entities?
4. What's your preference for SQL vs. NoSQL databases?

Knowing these details will help me recommend the best approach for your project.

👤 You: I need to store user profiles, conversation history, and preferences. What would you recommend?
🤖 Bot: Based on your requirements to store user profiles, conversation history, and preferences, here's my recommendation:

**Best Option: Neo4j (Graph Database)**

Neo4j is excellent for your use case because:
- User relationships are naturally expressed as graph connections
- Preference relationships can be easily modeled
- Fast queries for finding connected entities
- Natural representation of conversation threads

...

✅ Demo complete! Check 'conversation_log.txt' for full history.
```

---

## Step 6: Use Different LLM Providers

### Option A: OpenAI

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

bot = SimpleChatbot(
    name="assistant",
    user_id="demo_user"
)

# Modify in config.py:
LLM_PROVIDER = "openai"
LLM_MODEL = "gpt-3.5-turbo"
```

### Option B: Anthropic (Claude)

```python
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-your-key-here"

# Modify in config.py:
LLM_PROVIDER = "anthropic"
LLM_MODEL = "claude-3-sonnet"
```

### Option C: Local Ollama

```bash
# No API key needed! Install Ollama first
ollama pull mistral

# Use default config.py settings
LLM_PROVIDER = "ollama"
LLM_MODEL = "mistral"
```

---

## Step 7: Multi-User Support

Modify `main()` to handle multiple users:

```python
def multi_user_demo():
    """Demonstrate multi-user conversation."""
    
    users = [
        {
            "id": "alice_001",
            "name": "Alice",
            "messages": [
                "Hi! I'm learning Python.",
                "What's the best way to structure a web app?"
            ]
        },
        {
            "id": "bob_002", 
            "name": "Bob",
            "messages": [
                "I work with data analysis.",
                "What pandas functions should I master first?"
            ]
        }
    ]
    
    for user_info in users:
        print(f"\n{'='*60}")
        print(f"👤 {user_info['name']} ({user_info['id']})")
        print('='*60)
        
        bot = SimpleChatbot(
            name="assistant",
            user_id=user_info["id"]
        )
        
        for msg in user_info["messages"]:
            print(f"You: {msg}")
            response = bot.chat(msg)
            print(f"Bot: {response}\n")

if __name__ == "__main__":
    multi_user_demo()
```

---

## Expected Output

```
============================================================
👤 Alice (alice_001)
============================================================

You: Hi! I'm learning Python.
Bot: Hello Alice! It's great that you're learning Python. It's a fantastic language for beginners and professionals alike...

You: What's the best way to structure a web app?
Bot: For Python web apps, I'd recommend starting with one of these frameworks...

============================================================
👤 Bob (bob_002)
============================================================

You: I work with data analysis.
Bot: Excellent! Data analysis with Python is a powerful field...

You: What pandas functions should I master first?
Bot: Here are the essential pandas functions...
```

---

## 🆘 Troubleshooting

### ❌ "ModuleNotFoundError: No module named 'agentic_brain'"

```bash
pip install agentic-brain
```

### ❌ "Connection refused" (Neo4j)

```bash
# Check if Neo4j is running
docker ps | grep neo4j

# If not, start it
docker run -d \
  --name neo4j \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### ❌ "Ollama not responding"

```bash
# Check if Ollama is running
curl http://localhost:11434

# If not, start Ollama (macOS)
ollama serve

# Pull model if needed
ollama pull mistral
```

### ❌ Empty conversation log

This is normal for the first run. The log file is created as you chat.

### ❌ Bot responses are slow

- **Ollama:** May be downloading the model. Wait for first message.
- **API-based:** Check your internet connection
- **System:** Free up CPU/RAM for LLM inference

---

## ✅ What You've Learned

- ✅ Initialize a chatbot with memory
- ✅ Handle multi-turn conversations
- ✅ Log interactions for debugging
- ✅ Support multiple users simultaneously
- ✅ Switch between LLM providers
- ✅ Retrieve stored facts from memory

---

## 🚀 Next Steps

1. **[Tutorial 2: Adding Memory](./02-adding-memory.md)** - Deep dive into Neo4j integration
2. **[Tutorial 3: RAG Chatbot](./03-rag-chatbot.md)** - Ground responses in documents
3. **[Tutorial 4: Multi-User SaaS](./04-multi-user.md)** - Tenant isolation patterns
4. **[Tutorial 5: Production Deployment](./05-deployment.md)** - Docker and cloud setup

---

**Questions?** See the [getting-started guide](../getting-started.md) or check [README.md](../../README.md)

Happy coding! 🚀
