#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber

"""
Comprehensive examples for using the Agentic Brain Chatbot API.

This file demonstrates various ways to interact with the API:
1. REST API calls with requests/httpx
2. WebSocket real-time communication
3. Session management
4. Error handling
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

# Optional: Install with: pip install httpx websockets
try:
    import httpx
except ImportError:
    print("Note: Install httpx for sync examples: pip install httpx")

try:
    import websockets
except ImportError:
    print("Note: Install websockets for WebSocket examples: pip install websockets")


# =============================================================================
# Configuration
# =============================================================================

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


# =============================================================================
# Example 1: REST API - Health Check
# =============================================================================

def example_health_check() -> None:
    """Check if the API server is running and healthy."""
    print("\n" + "="*70)
    print("Example 1: Health Check")
    print("="*70)
    
    try:
        response = httpx.get(f"{API_URL}/health")
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Server Status: {data['status']}")
        print(f"  Version: {data['version']}")
        print(f"  Active Sessions: {data['sessions_active']}")
        print(f"  Timestamp: {data['timestamp']}")
    
    except Exception as e:
        print(f"✗ Error: {e}")
        print("  Make sure the server is running: python3 -m agentic_brain.api.server")


# =============================================================================
# Example 2: REST API - Send Chat Message (Auto Session)
# =============================================================================

def example_chat_auto_session() -> Optional[str]:
    """Send a chat message without providing a session ID."""
    print("\n" + "="*70)
    print("Example 2: Chat Message (Auto-Session)")
    print("="*70)
    
    try:
        response = httpx.post(
            f"{API_URL}/chat",
            json={"message": "What's the weather today?"}
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Message sent successfully")
        print(f"  Session ID: {data['session_id']}")
        print(f"  Message ID: {data['message_id']}")
        print(f"  Response: {data['response']}")
        print(f"  Timestamp: {data['timestamp']}")
        
        return data['session_id']
    
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


# =============================================================================
# Example 3: REST API - Send Chat Message (Persistent Session)
# =============================================================================

def example_chat_persistent_session(session_id: str) -> None:
    """Send multiple messages in the same session."""
    print("\n" + "="*70)
    print("Example 3: Chat with Persistent Session")
    print("="*70)
    
    messages = [
        "How are you?",
        "What time is it?",
        "Tell me a joke!"
    ]
    
    try:
        for i, message in enumerate(messages, 1):
            response = httpx.post(
                f"{API_URL}/chat",
                json={
                    "message": message,
                    "session_id": session_id,
                    "user_id": "user_example_01"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            print(f"\n✓ Message {i}:")
            print(f"  Input: {message}")
            print(f"  Output: {data['response']}")
            print(f"  Message ID: {data['message_id']}")
    
    except Exception as e:
        print(f"✗ Error: {e}")


# =============================================================================
# Example 4: REST API - Get Session Information
# =============================================================================

def example_get_session_info(session_id: str) -> None:
    """Retrieve session information."""
    print("\n" + "="*70)
    print("Example 4: Get Session Information")
    print("="*70)
    
    try:
        response = httpx.get(f"{API_URL}/session/{session_id}")
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Session Information:")
        print(f"  ID: {data['id']}")
        print(f"  Message Count: {data['message_count']}")
        print(f"  User ID: {data.get('user_id', 'N/A')}")
        print(f"  Created At: {data['created_at']}")
        print(f"  Last Accessed: {data['last_accessed']}")
    
    except Exception as e:
        print(f"✗ Error: {e}")


# =============================================================================
# Example 5: REST API - Get Session Messages
# =============================================================================

def example_get_session_messages(session_id: str) -> None:
    """Retrieve all messages in a session."""
    print("\n" + "="*70)
    print("Example 5: Get Session Messages")
    print("="*70)
    
    try:
        response = httpx.get(
            f"{API_URL}/session/{session_id}/messages",
            params={"limit": 10}
        )
        response.raise_for_status()
        
        messages = response.json()
        print(f"✓ Retrieved {len(messages)} messages:")
        
        for msg in messages:
            role = msg['role'].upper()
            content = msg['content'][:60] + "..." if len(msg['content']) > 60 else msg['content']
            print(f"  [{role}] {content}")
            print(f"    ID: {msg['id']}, Time: {msg['timestamp']}")
    
    except Exception as e:
        print(f"✗ Error: {e}")


# =============================================================================
# Example 6: REST API - Delete Session
# =============================================================================

def example_delete_session(session_id: str) -> None:
    """Delete a session."""
    print("\n" + "="*70)
    print("Example 6: Delete Session")
    print("="*70)
    
    try:
        response = httpx.delete(f"{API_URL}/session/{session_id}")
        response.raise_for_status()
        
        print(f"✓ Session deleted: {session_id}")
        
        # Verify deletion
        response = httpx.get(f"{API_URL}/session/{session_id}")
        if response.status_code == 404:
            print(f"✓ Confirmed: Session no longer exists")
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"✓ Session already deleted or doesn't exist")
        else:
            print(f"✗ Error: {e}")


# =============================================================================
# Example 7: Error Handling - Invalid Request
# =============================================================================

def example_error_handling() -> None:
    """Demonstrate error handling."""
    print("\n" + "="*70)
    print("Example 7: Error Handling")
    print("="*70)
    
    # Test 1: Empty message
    print("\n1. Testing empty message:")
    try:
        response = httpx.post(
            f"{API_URL}/chat",
            json={"message": ""}
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"  ✓ Caught error {e.response.status_code}: Empty message validation")
        print(f"    Error details: {e.response.json()}")
    
    # Test 2: Non-existent session
    print("\n2. Testing non-existent session:")
    try:
        response = httpx.get(f"{API_URL}/session/sess_nonexistent")
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"  ✓ Caught error {e.response.status_code}: Session not found")
        print(f"    Error details: {e.response.json()}")
    
    # Test 3: Missing required field
    print("\n3. Testing missing required field:")
    try:
        response = httpx.post(
            f"{API_URL}/chat",
            json={"user_id": "test"}  # Missing 'message'
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"  ✓ Caught error {e.response.status_code}: Missing required field")


# =============================================================================
# Example 8: WebSocket - Real-time Communication
# =============================================================================

async def example_websocket_chat() -> None:
    """Demonstrate real-time WebSocket communication."""
    print("\n" + "="*70)
    print("Example 8: WebSocket Real-time Chat")
    print("="*70)
    
    try:
        async with websockets.connect(f"{WS_URL}/ws/chat") as websocket:
            # Receive connection confirmation
            connection_msg = await asyncio.wait_for(websocket.recv(), timeout=5)
            conn_data = json.loads(connection_msg)
            print(f"✓ Connected to WebSocket")
            print(f"  Session ID: {conn_data['session_id']}")
            print(f"  Message: {conn_data['message']}")
            
            # Send messages
            test_messages = [
                "Hello bot!",
                "How are you?",
                "What time is it?"
            ]
            
            for msg in test_messages:
                print(f"\nSending: {msg}")
                
                # Send message
                await websocket.send(json.dumps({"message": msg}))
                
                # Receive response
                response_str = await asyncio.wait_for(websocket.recv(), timeout=5)
                response_data = json.loads(response_str)
                
                if response_data['type'] == 'message':
                    print(f"  Response: {response_data['content']}")
                elif response_data['type'] == 'error':
                    print(f"  Error: {response_data['error']}")
    
    except Exception as e:
        print(f"✗ WebSocket Error: {e}")
        print("  Make sure the server is running on ws://localhost:8000")


# =============================================================================
# Example 9: Advanced - Multi-user Session Management
# =============================================================================

def example_multi_user_sessions() -> None:
    """Demonstrate multi-user session management."""
    print("\n" + "="*70)
    print("Example 9: Multi-user Session Management")
    print("="*70)
    
    try:
        users = [
            {"id": "user_alice", "name": "Alice"},
            {"id": "user_bob", "name": "Bob"},
            {"id": "user_charlie", "name": "Charlie"}
        ]
        
        sessions = {}
        
        # Create messages for each user
        for user in users:
            response = httpx.post(
                f"{API_URL}/chat",
                json={
                    "message": f"Hello, I am {user['name']}",
                    "user_id": user['id']
                }
            )
            response.raise_for_status()
            
            data = response.json()
            sessions[user['id']] = data['session_id']
            print(f"✓ {user['name']} -> Session: {data['session_id']}")
        
        # Get session info for each user
        print("\nSession Information:")
        for user in users:
            session_id = sessions[user['id']]
            response = httpx.get(f"{API_URL}/session/{session_id}")
            response.raise_for_status()
            
            data = response.json()
            print(f"  {user['name']}: {data['message_count']} messages")
    
    except Exception as e:
        print(f"✗ Error: {e}")


# =============================================================================
# Example 10: Advanced - Continuous Conversation
# =============================================================================

def example_continuous_conversation() -> None:
    """Demonstrate a continuous conversation."""
    print("\n" + "="*70)
    print("Example 10: Continuous Conversation")
    print("="*70)
    
    try:
        session_id = None
        
        conversation = [
            "Hello there!",
            "How are you doing?",
            "Tell me something interesting",
            "That's cool! Anything else?",
            "Thanks for chatting!"
        ]
        
        for i, message in enumerate(conversation, 1):
            response = httpx.post(
                f"{API_URL}/chat",
                json={
                    "message": message,
                    "session_id": session_id
                }
            )
            response.raise_for_status()
            
            data = response.json()
            session_id = data['session_id']  # Use same session
            
            print(f"\n{i}. User: {message}")
            print(f"   Bot: {data['response']}")
        
        # Show conversation summary
        if session_id:
            response = httpx.get(f"{API_URL}/session/{session_id}")
            response.raise_for_status()
            
            data = response.json()
            print(f"\n✓ Conversation Summary:")
            print(f"  Total messages exchanged: {data['message_count']}")
            print(f"  Session duration: {data['created_at']} to {data['last_accessed']}")
    
    except Exception as e:
        print(f"✗ Error: {e}")


# =============================================================================
# Main - Run All Examples
# =============================================================================

def main() -> None:
    """Run all examples."""
    print("\n" + "="*70)
    print("AGENTIC BRAIN CHATBOT API - EXAMPLES")
    print("="*70)
    print(f"API URL: {API_URL}")
    print(f"WebSocket URL: {WS_URL}")
    print("\nMake sure the server is running:")
    print("  python3 -m agentic_brain.api.server")
    
    try:
        # REST API Examples
        example_health_check()
        
        session_id = example_chat_auto_session()
        if session_id:
            example_chat_persistent_session(session_id)
            example_get_session_info(session_id)
            example_get_session_messages(session_id)
            example_delete_session(session_id)
        
        example_error_handling()
        example_multi_user_sessions()
        example_continuous_conversation()
        
        # WebSocket Example (async)
        print("\n" + "="*70)
        try:
            asyncio.run(example_websocket_chat())
        except Exception as e:
            print(f"WebSocket example skipped: {e}")
    
    except ImportError as e:
        print(f"\n⚠ Missing dependency: {e}")
        print("\nInstall required packages:")
        print("  pip install httpx websockets")


if __name__ == "__main__":
    main()
