# 💬 Customer Service Examples

> AI-powered customer support - live chat, FAQ, multilingual, voice.

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 33 | [live_chat_support.py](33_live_chat_support.py) | Real-time chat support | 🟡 Intermediate |
| 34 | [faq_escalation.py](34_faq_escalation.py) | Smart FAQ with escalation | 🟡 Intermediate |
| 35 | [multilingual_support.py](35_multilingual_support.py) | Multi-language support | 🔴 Advanced |
| 36 | [voice_ivr.py](36_voice_ivr.py) | Voice assistant / IVR | 🔴 Advanced |

## Quick Start

```bash
# Live chat support
python examples/customer-service/33_live_chat_support.py

# FAQ with human escalation
python examples/customer-service/34_faq_escalation.py

# Voice IVR system
python examples/customer-service/36_voice_ivr.py
```

## Use Cases

### Live Chat Support
- Instant customer responses
- Conversation context tracking
- Sentiment detection
- Agent handoff when needed
- CRM integration

### FAQ & Escalation
- Answer common questions
- Detect frustration/confusion
- Smart escalation triggers
- Human agent handoff
- Post-chat surveys

### Multilingual Support
- Auto-detect customer language
- Real-time translation
- Localized responses
- Cultural awareness
- Language switching

### Voice IVR
- Natural language understanding
- Voice-to-text processing
- Intent classification
- Call routing
- Voice response generation

## Common Patterns

### Live Chat Agent
```python
from agentic_brain import Agent

support_bot = Agent(
    name="support_agent",
    memory="neo4j://localhost:7687",  # Remember conversation
    system_prompt="""You are a helpful customer support agent.
    Be friendly, concise, and helpful.
    If you can't help, offer to connect to a human agent."""
)
```

### Escalation Detection
```python
def needs_escalation(message, response):
    """Detect when to escalate to human."""
    triggers = [
        "speak to human",
        "talk to someone",
        "manager",
        "frustrated",
        "not helpful"
    ]
    return any(t in message.lower() for t in triggers)
```

### Multilingual Support
```python
from langdetect import detect

def get_language_agent(message):
    lang = detect(message)
    return Agent(
        name=f"support_{lang}",
        system_prompt=f"Respond in {lang}. Be helpful and culturally aware."
    )
```

### Voice Processing
```python
import speech_recognition as sr

def process_voice():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        audio = r.listen(source)
    text = r.recognize_google(audio)
    return agent.chat(text)
```

## Integration Points

- **CRM**: Salesforce, HubSpot, Zendesk
- **Chat**: Intercom, Drift, LiveChat
- **Voice**: Twilio, Vonage, Amazon Connect
- **Analytics**: Track CSAT, resolution rates

## Prerequisites

- Python 3.10+
- Ollama running locally
- WebSocket support (for live chat)
- Speech recognition (for voice)
