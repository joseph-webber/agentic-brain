# 🤖 Agentic Brain Chatbot Examples

Ready-to-use chatbot implementations for various platforms.

## How It Works

Each chatbot combines **multiple pieces** of the Agentic Brain puzzle:

```
┌─────────────────────────────────────────────────────────────┐
│                    DISCORD CHATBOT                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ RAG Loader  │───▶│ Vector Store │───▶│ LLM Router   │   │
│  │ (History)   │    │ (Semantic)   │    │ (Response)   │   │
│  └─────────────┘    └──────────────┘    └──────────────┘   │
│         │                                       │          │
│         ▼                                       ▼          │
│  ┌─────────────┐                        ┌──────────────┐   │
│  │ Discord.py  │◀──────────────────────▶│   Memory     │   │
│  │ (Platform)  │                        │ (Per-channel)│   │
│  └─────────────┘                        └──────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Available Chatbots

### Discord Bot (`discord_bot.py`)

Full-featured Discord chatbot with:
- ✅ Slash commands (`/ask`, `/search`, `/clear`)
- ✅ RAG context from channel history
- ✅ Per-channel conversation memory
- ✅ Automatic fallback to local LLM
- ✅ Multiple bot variants (Support, Code, Mod, Australian Business)

```bash
# Install dependencies
pip install discord.py agentic-brain

# Set environment variable
export DISCORD_BOT_TOKEN="your-token-here"

# Run the bot
python discord_bot.py
```

#### Bot Variants

| Class | Use Case | Temperature |
|-------|----------|-------------|
| `AgenticBrainBot` | General purpose | 0.7 |
| `CustomerSupportBot` | Customer support | 0.5 |
| `CodingAssistantBot` | Coding help | 0.3 |
| `CommunityModBot` | Moderation assist | 0.4 |
| `AustralianBusinessBot` | AU business + legal | 0.4 |

## The RAG Loader Connection

The **DiscordLoader** (and other platform loaders) are ONE PIECE of the chatbot puzzle:

```python
# The loader fetches historical messages
loader = DiscordLoader(token="...")
docs = loader.load_channel(channel_id, limit=50)

# These become RAG context
vector_store = VectorStore()
vector_store.add_texts([doc.content for doc in docs])

# When user asks a question, we find relevant history
relevant = vector_store.similarity_search(user_query, k=3)

# This context enriches the LLM prompt
response = router.chat([
    {"role": "system", "content": f"Context: {relevant}"},
    {"role": "user", "content": user_query}
])
```

## Adding More Chatbots

Each chatbot follows the same pattern:

1. **Platform Integration** - Discord.py, Slack SDK, Telegram Bot, etc.
2. **RAG Loader** - Load historical messages/data
3. **Vector Store** - Semantic search over history
4. **LLM Router** - Generate intelligent responses
5. **Memory** - Track conversation state

### Coming Soon

- `slack_bot.py` - Slack workspace bot
- `telegram_bot.py` - Telegram bot
- `teams_bot.py` - Microsoft Teams bot
- `whatsapp_bot.py` - WhatsApp Business bot

## Australian Market Features

The `AustralianBusinessBot` includes:

- 🦘 AEST/AEDT timezone awareness
- ⚖️ ACL consumer law compliance
- 📋 ASIC/ACCC regulation awareness
- ⚠️ Automatic legal disclaimers

## License

GPL-3.0 - See main repository license.
