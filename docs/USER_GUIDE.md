# 🧠 Agentic Brain User Guide

Welcome to **Agentic Brain**, the universal AI platform built for accessibility, voice interaction, and enterprise-grade intelligence.

This guide will help you install, configure, and use the brain's features, from chatting with AI to running complex RAG (Retrieval Augmented Generation) workflows.

---

## 1. What is Agentic Brain?

Agentic Brain is a modular AI system that combines:
- **Multiple LLMs**: Switch between Claude, GPT-4, Llama 3, and Groq instantly.
- **Memory**: Remembers conversations using a Neo4j knowledge graph.
- **Voice**: Speaks with 145+ high-quality voices (Karen, Moira, etc.) and respects VoiceOver.
- **Accessibility**: Built-in support for screen readers and keyboard navigation.

It's designed to be your personal AI companion that grows smarter with every interaction.

---

## 2. Installation

### Prerequisites
- macOS, Linux, or Windows (WSL2)
- Python 3.11 or higher
- [Ollama](https://ollama.ai) (optional, for local AI)
- [Neo4j](https://neo4j.com) (optional, for long-term memory)

### Quick Install

1. Open your terminal.
2. Navigate to the project folder:
   ```bash
   cd ~/brain/agentic-brain
   ```
3. Run the setup wizard:
   ```bash
   ./setup.sh
   ```
   *This script checks your system, installs dependencies, and helps you configure initial settings.*

### Manual Install (Advanced)

If you prefer `pip`:
```bash
pip install -e ".[all]"
```

---

## 3. Configuration

The brain needs to know your preferences and API keys.

### Interactive Setup
Run the configuration wizard:
```bash
agentic new-config
```
This will ask you about:
- Your name and role
- Preferred AI models (Cloud vs Local)
- Voice settings
- Memory options

### Environment Variables
You can also create a `.env` file in the `agentic-brain` directory:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=your_password
```

---

## 4. Using the Chat Interface

Start a conversation immediately from your terminal.

### Start Chat
```bash
agentic chat
```

### Manage Models
List all available models (Cloud & Local):
```bash
agentic models
```

Switch your default model:
```bash
agentic switch <model_id>
# Example: agentic switch L1  (for Llama 3 Local)
# Example: agentic switch C3  (for Claude 3.5 Sonnet)
```

Check model status:
```bash
agentic check
```

---

## 5. Using the API

Agentic Brain provides a production-ready REST API for building your own apps.

### Start the Server
```bash
agentic serve --port 8000
```
The API will be available at `http://localhost:8000`.

### Documentation
Visit `http://localhost:8000/docs` to see the interactive Swagger UI and test endpoints.

### Example Request
```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello, brain!"}'
```

---

## 6. Voice Features 🎙️

The brain features a world-class voice system designed for accessibility.

### Commands
- **List Voices**: See all 145+ available voices.
  ```bash
  agentic voice list
  ```
- **Test a Voice**: Hear what a voice sounds like.
  ```bash
  agentic voice test "Karen"
  ```
- **Speak Text**: Make the brain say something.
  ```bash
  agentic voice speak "Hello there, ready to work."
  ```

### Voice Modes
- **Work Mode**: Professional voice (Karen). No slang.
  ```bash
  agentic voice mode work
  ```
- **Life Mode**: Fun, multi-personality voices (Karen, Moira, Tingting, etc.).
  ```bash
  agentic voice mode life
  ```
- **Quiet Mode**: Disables automatic speech (for CI/CD or quiet environments).
  ```bash
  agentic voice mode quiet
  ```

*Note: The system automatically detects VoiceOver and will pause speaking to let your screen reader finish.*

---

## 7. RAG (Retrieval Augmented Generation)

RAG allows the brain to answer questions based on your own data (documents, code, notes).

### How it Works
1. **Ingest**: You load documents into the brain.
2. **Store**: The brain saves them in Neo4j (Knowledge Graph) and Vector Database.
3. **Retrieve**: When you ask a question, it finds relevant info.
4. **Answer**: The AI uses that info to give a precise answer.

### Setup
Initialize the knowledge graph schema:
```bash
agentic schema
```

*Note: Full RAG document ingestion features are currently available via the Python API.*

---

## 8. Troubleshooting

### "Command not found: agentic"
- Ensure you activated the virtual environment: `source venv/bin/activate`
- Try reinstalling: `pip install -e .`

### "Connection refused" (Neo4j)
- Check if Neo4j is running: `docker ps` or check the Neo4j Desktop app.
- Verify `NEO4J_URI` in your config matches your running instance.

### "Model not found" or "API Error"
- Run `agentic check` to diagnose API connections.
- Verify your API keys in the `.env` file.
- If using local models, ensure Ollama is running (`ollama serve`).

---

## 9. FAQ

**Q: Is Agentic Brain free?**
A: The software is open source. However, using cloud models (GPT-4, Claude) requires API keys which may have costs. Local models via Ollama are free.

**Q: Can I run this offline?**
A: Yes! Use local models (Llama 3, Mistral) via Ollama and a local Neo4j instance. The brain will work fully offline.

**Q: How do I back up my memory?**
A: Your memory is stored in Neo4j. Use standard Neo4j backup tools or the `agentic neo4j backup` command (if available in your version).

**Q: I'm blind. Is this accessible?**
A: Yes. All CLI tools support screen readers. The `agentic setup` wizard has a `--no-color` mode for better compatibility, and the voice system is designed to work *with* VoiceOver, not against it.

---

**Need more help?**
Check the `docs/` folder for detailed technical documentation or raise an issue on GitHub.
