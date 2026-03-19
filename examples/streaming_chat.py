# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Streaming Chat Example
======================

Demonstrates real-time token-by-token streaming for instant UX.

Run with:
    python -m examples.streaming_chat

Includes:
- Direct streaming (async generator)
- Server-Sent Events (SSE) with curl
- WebSocket streaming with wscat
- Browser-based example
"""

import asyncio
import json
from typing import Optional, List, Dict, Any

from agentic_brain.streaming import StreamingResponse


async def example_direct_streaming():
    """
    Example 1: Direct async streaming.
    
    Simplest approach - stream tokens directly in Python.
    """
    print("\n" + "="*60)
    print("Example 1: Direct Token Streaming")
    print("="*60)
    
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.7,
    )
    
    print("\nPrompt: What is machine learning?\n")
    print("Response: ", end="", flush=True)
    
    try:
        async for token in streamer.stream("What is machine learning?"):
            # Print token immediately as it arrives
            print(token.token, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\nError: {e}")


async def example_with_history():
    """
    Example 2: Streaming with conversation history.
    
    Demonstrates multi-turn conversation context.
    """
    print("\n" + "="*60)
    print("Example 2: Streaming with Conversation History")
    print("="*60)
    
    # Simulated conversation history
    history = [
        {"role": "user", "content": "What is AI?"},
        {"role": "assistant", "content": "AI (Artificial Intelligence) is the simulation of human intelligence by machines."},
        {"role": "user", "content": "Tell me more."},
    ]
    
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.5,
    )
    
    print("\nConversation history:")
    for msg in history:
        role = "You" if msg["role"] == "user" else "Assistant"
        print(f"  {role}: {msg['content']}")
    
    print(f"\nYou: Tell me more.\n")
    print("Assistant: ", end="", flush=True)
    
    try:
        # Stream with history context
        async for token in streamer.stream("Tell me more.", history):
            print(token.token, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\nError: {e}")


async def example_provider_switching():
    """
    Example 3: Switching between providers.
    
    Shows how to easily switch between Ollama, OpenAI, and Anthropic.
    """
    print("\n" + "="*60)
    print("Example 3: Provider Switching")
    print("="*60)
    
    providers = [
        ("ollama", "llama3.1:8b"),
        # ("openai", "gpt-4"),  # Requires OPENAI_API_KEY
        # ("anthropic", "claude-3-sonnet-20240229"),  # Requires ANTHROPIC_API_KEY
    ]
    
    message = "Explain quantum computing in one sentence."
    
    for provider, model in providers:
        print(f"\n{provider.upper()} ({model}):")
        print("-" * 40)
        
        try:
            streamer = StreamingResponse(
                provider=provider,
                model=model,
                temperature=0.7,
                max_tokens=100,
            )
            
            print("Response: ", end="", flush=True)
            async for token in streamer.stream(message):
                print(token.token, end="", flush=True)
            print()
        except Exception as e:
            print(f"Error: {e}")


async def example_sse_format():
    """
    Example 4: Server-Sent Events format.
    
    Shows how to format tokens as SSE for web frontend consumption.
    """
    print("\n" + "="*60)
    print("Example 4: Server-Sent Events Format")
    print("="*60)
    print("\nSSE Output (as seen in browser):\n")
    
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.7,
        max_tokens=50,
    )
    
    try:
        async for sse_line in streamer.stream_sse("Hello!"):
            # This is what the client receives
            print(sse_line, end="")
    except Exception as e:
        print(f"Error: {e}")


async def example_websocket_format():
    """
    Example 5: WebSocket format.
    
    Shows JSON format for WebSocket clients.
    """
    print("\n" + "="*60)
    print("Example 5: WebSocket JSON Format")
    print("="*60)
    print("\nWebSocket Messages (as seen in browser):\n")
    
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.7,
        max_tokens=50,
    )
    
    try:
        async for json_line in streamer.stream_websocket("Hello!"):
            # Pretty print the JSON
            data = json.loads(json_line)
            print(f"  {json_line}")
    except Exception as e:
        print(f"Error: {e}")


async def example_start_and_end_detection():
    """
    Example 6: Detecting start and end of stream.
    
    Shows how to handle stream lifecycle events.
    """
    print("\n" + "="*60)
    print("Example 6: Start and End Detection")
    print("="*60)
    
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.7,
    )
    
    token_count = 0
    
    try:
        async for token in streamer.stream("What is AI?"):
            if token.is_start:
                print("\n⬇️  Stream started!\n")
            
            print(token.token, end="", flush=True)
            token_count += 1
            
            if token.is_end:
                print(f"\n\n✅ Stream ended!")
                print(f"   Total tokens: {token_count}")
                print(f"   Finish reason: {token.finish_reason}")
                print(f"   Provider: {token.metadata.get('provider')}")
    except Exception as e:
        print(f"\nError: {e}")


async def main():
    """Run all examples."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "   Streaming Chat - Real-time Token Delivery".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    print("\n🚀 Starting streaming examples...\n")
    print("Make sure Ollama is running: ollama serve")
    print("Or configure OPENAI_API_KEY / ANTHROPIC_API_KEY for cloud providers")
    
    # Run examples
    try:
        await example_direct_streaming()
        # Uncomment to run more examples
        # await example_with_history()
        # await example_provider_switching()
        # await example_sse_format()
        # await example_websocket_format()
        # await example_start_and_end_detection()
    except KeyboardInterrupt:
        print("\n\n⏹️  Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# Web Frontend Examples
# ============================================================================

BROWSER_EXAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Streaming Chat - Real-time Demo</title>
    <style>
        * { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
        body { margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 40px; }
        h1 { margin: 0; font-size: 28px; color: #333; }
        p { margin: 10px 0 0 0; color: #666; }
        
        .chat { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .messages { height: 400px; overflow-y: auto; margin-bottom: 20px; }
        .message { margin-bottom: 15px; }
        .message.user { text-align: right; }
        .message.assistant { text-align: left; }
        
        .text { 
            display: inline-block; 
            padding: 10px 15px; 
            border-radius: 18px;
            max-width: 70%;
            word-wrap: break-word;
        }
        .user .text { background: #007AFF; color: white; }
        .assistant .text { background: #e5e5ea; color: black; }
        
        .input-group { display: flex; gap: 10px; }
        input { flex: 1; padding: 10px 15px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; }
        button { padding: 10px 20px; background: #007AFF; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; }
        button:hover { background: #0051d5; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        
        .status { font-size: 12px; color: #666; margin-top: 10px; }
        .loading { display: inline-block; width: 10px; height: 10px; margin: 0 5px; background: #007AFF; border-radius: 50%; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Streaming Chat</h1>
            <p>Real-time token delivery for instant UX</p>
        </div>
        
        <div class="chat">
            <div class="messages" id="messages"></div>
            
            <div class="input-group">
                <input 
                    id="input" 
                    type="text" 
                    placeholder="Ask me anything..." 
                    onkeypress="event.key === 'Enter' && sendMessage()"
                />
                <button onclick="sendMessage()" id="sendBtn">Send</button>
            </div>
            
            <div class="status" id="status"></div>
        </div>
    </div>
    
    <script>
        const messagesEl = document.getElementById('messages');
        const inputEl = document.getElementById('input');
        const sendBtn = document.getElementById('sendBtn');
        const statusEl = document.getElementById('status');
        
        async function sendMessage() {
            const message = inputEl.value.trim();
            if (!message) return;
            
            // Add user message
            addMessage(message, 'user');
            inputEl.value = '';
            sendBtn.disabled = true;
            
            try {
                // Start streaming
                const response = await fetch(`/chat/stream?message=${encodeURIComponent(message)}`);
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                let assistantMessageEl = null;
                
                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\\n\\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                
                                // Create message element on first token
                                if (!assistantMessageEl) {
                                    assistantMessageEl = addMessage('', 'assistant');
                                }
                                
                                // Append token
                                const textEl = assistantMessageEl.querySelector('.text');
                                textEl.textContent += data.token;
                                
                                // Auto-scroll
                                messagesEl.scrollTop = messagesEl.scrollHeight;
                            } catch (e) {
                                console.error('Failed to parse SSE message:', e);
                            }
                        }
                    }
                }
                
                statusEl.textContent = 'Ready';
            } catch (error) {
                statusEl.textContent = '❌ Error: ' + error.message;
                console.error('Error:', error);
            } finally {
                sendBtn.disabled = false;
                inputEl.focus();
            }
        }
        
        function addMessage(text, role) {
            const messageEl = document.createElement('div');
            messageEl.className = `message ${role}`;
            
            const textEl = document.createElement('div');
            textEl.className = 'text';
            textEl.textContent = text;
            
            messageEl.appendChild(textEl);
            messagesEl.appendChild(messageEl);
            messagesEl.scrollTop = messagesEl.scrollHeight;
            
            return messageEl;
        }
        
        // Focus input on load
        inputEl.focus();
    </script>
</body>
</html>
"""

print("\n" + "="*60)
print("Browser Frontend Example")
print("="*60)
print("\nSave the HTML above to index.html and open in browser")
print("Make sure the API server is running on http://localhost:8000")
