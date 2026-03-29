# 📖 API Reference

This document outlines the core API surface for the Agentic Brain.

## 📡 Core API

The brain exposes a RESTful API (FastAPI) and a WebSocket interface for real-time interactions.

### Base URL
`http://localhost:8000/api/v1`

### 🔑 Authentication
Bearer Token required for protected endpoints.
`Authorization: Bearer <your_token>`

## 🧠 Brain Endpoints

### 1. `POST /chat/completions`
Send a message to the brain and get a response.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Hello, brain!"}
  ],
  "model": "gpt-4-turbo"
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      }
    }
  ]
}
```

### 2. `POST /memory/store`
Store a fact or memory explicitly.

**Request:**
```json
{
  "content": "The user prefers dark mode.",
  "type": "preference"
}
```

### 3. `GET /memory/query`
Retrieve relevant memories.

**Query Parameters:**
- `q`: Search query (e.g., "preferences")
- `limit`: Max results (default 5)

## 🛠️ Tool Usage

### `POST /tools/execute`
Execute a registered tool.

**Request:**
```json
{
  "tool_name": "web_search",
  "arguments": {"query": "latest AI news"}
}
```

## websockets

### `/ws/chat`
Real-time streaming chat.

**Message Format:**
```json
{"type": "chat", "content": "..."}
```

For detailed internal module documentation, see the source code docstrings.
