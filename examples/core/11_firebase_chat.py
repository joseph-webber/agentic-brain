#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
11 - Firebase Realtime Database Chat
=====================================

Cross-device synchronized chat using Firebase Realtime Database transport.
Messages sync instantly across all connected clients on any device.

Features:
- Real-time message streaming via Firebase listeners
- Session state sync across devices
- Offline support with SQLite persistence
- Automatic reconnection with exponential backoff
- Message history retrieval
- Connection state monitoring

Requirements:
    pip install agentic-brain[firebase]

Firebase Setup:
    1. Create a Firebase project at https://console.firebase.google.com
    2. Enable Realtime Database (not Firestore)
    3. Download service account credentials:
       Firebase Console > Project Settings > Service Accounts > Generate New Private Key
    4. Set environment variables:
       export FIREBASE_PROJECT_ID=your-project-id
       export FIREBASE_DATABASE_URL=https://your-project-id.firebaseio.com
       export FIREBASE_CREDENTIALS_FILE=/path/to/service-account.json

Run:
    python examples/11_firebase_chat.py

Open multiple terminals to see cross-device sync in action!
"""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timezone

# Check for Firebase SDK
try:
    import firebase_admin
except ImportError:
    print("\n❌ Firebase SDK not installed!")
    print("   Run: pip install agentic-brain[firebase]")
    print("   Or:  pip install firebase-admin")
    sys.exit(1)

from agentic_brain.transport import (
    ConnectionState,
    FirebaseTransport,
    TransportConfig,
    TransportMessage,
)
from agentic_brain.transport.firebase_config import (
    create_sample_config,
    load_firebase_config,
)

# ============================================================================
# Configuration
# ============================================================================

# Unique session ID shared across devices
SESSION_ID = os.getenv("FIREBASE_SESSION_ID", "demo-chat-room")

# Unique client ID for this instance
CLIENT_ID = os.getenv("CLIENT_ID", f"client-{uuid.uuid4().hex[:8]}")


# ============================================================================
# Firebase Chat Demo
# ============================================================================


async def receive_messages(transport: FirebaseTransport) -> None:
    """Background task to receive and display messages."""
    print(f"\n📥 Listening for messages in session: {SESSION_ID}")
    print("   (Messages from other clients will appear here)\n")

    try:
        async for message in transport.listen():
            # Skip our own messages
            if message.metadata.get("client_id") == CLIENT_ID:
                continue

            sender = message.metadata.get("client_id", "unknown")[:8]
            timestamp = message.timestamp.strftime("%H:%M:%S")
            print(f"\n[{timestamp}] {sender}: {message.content}")
            print("> ", end="", flush=True)  # Restore prompt
    except asyncio.CancelledError:
        pass


async def receive_state_changes(transport: FirebaseTransport) -> None:
    """Background task to monitor session state changes."""
    try:
        async for state in transport.receive_state_changes():
            clients = state.get("clients", {})
            online_count = sum(1 for c in clients.values() if c.get("online", False))
            if online_count > 0:
                print(f"\n👥 {online_count} client(s) online")
                print("> ", end="", flush=True)
    except asyncio.CancelledError:
        pass


async def update_presence(transport: FirebaseTransport, online: bool) -> None:
    """Update our presence in session state."""
    await transport.update_state(
        {
            "clients": {
                CLIENT_ID: {
                    "online": online,
                    "last_seen": datetime.now(UTC).isoformat(),
                }
            }
        }
    )


async def send_message(transport: FirebaseTransport, content: str) -> None:
    """Send a message to the chat."""
    message = TransportMessage(
        content=content,
        session_id=SESSION_ID,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        metadata={
            "client_id": CLIENT_ID,
            "sent_at": datetime.now(UTC).isoformat(),
        },
    )

    success = await transport.send(message)
    if success:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] You: {content}")
    else:
        print("❌ Failed to send message")


async def show_history(transport: FirebaseTransport) -> None:
    """Show recent message history."""
    history = await transport.get_history(limit=10)

    if not history:
        print("\n📜 No message history yet")
        return

    print(f"\n📜 Recent messages ({len(history)}):")
    print("-" * 40)
    for msg in history:
        sender = msg.metadata.get("client_id", "unknown")[:8]
        timestamp = msg.timestamp.strftime("%H:%M:%S")
        marker = "You" if sender == CLIENT_ID[:8] else sender
        print(f"[{timestamp}] {marker}: {msg.content}")
    print("-" * 40)


async def interactive_chat(transport: FirebaseTransport) -> None:
    """Interactive chat loop."""
    print("\n" + "=" * 50)
    print("💬 Firebase Chat Demo")
    print("=" * 50)
    print(f"\n🔗 Session: {SESSION_ID}")
    print(f"🆔 Client ID: {CLIENT_ID}")
    print("\nCommands:")
    print("  /history  - Show recent messages")
    print("  /state    - Show session state")
    print("  /stats    - Show transport stats")
    print("  /health   - Check connection health")
    print("  /clear    - Clear chat history")
    print("  /quit     - Exit")
    print("\nType a message and press Enter to send.\n")

    # Start background listeners
    receive_task = asyncio.create_task(receive_messages(transport))
    state_task = asyncio.create_task(receive_state_changes(transport))

    # Update presence
    await update_presence(transport, online=True)

    try:
        while True:
            try:
                # Read input (blocking in separate thread)
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("> ")
                )

                if not line.strip():
                    continue

                # Handle commands
                if line.startswith("/"):
                    cmd = line.lower().strip()

                    if cmd == "/quit":
                        print("\n👋 Goodbye!")
                        break

                    elif cmd == "/history":
                        await show_history(transport)

                    elif cmd == "/state":
                        print(f"\n📊 Session State: {transport.session_state}")

                    elif cmd == "/stats":
                        stats = transport.stats
                        print("\n📈 Transport Stats:")
                        print(f"   Messages sent: {stats.messages_sent}")
                        print(f"   Messages received: {stats.messages_received}")
                        print(f"   Reconnections: {stats.reconnection_count}")
                        print(f"   Offline queue: {stats.offline_queue_size}")

                    elif cmd == "/health":
                        healthy = await transport.is_healthy()
                        status = "✅ Healthy" if healthy else "❌ Unhealthy"
                        print(f"\n🏥 Connection: {status}")
                        print(f"   State: {transport.connection_state.value}")

                    elif cmd == "/clear":
                        if await transport.clear_session():
                            print("\n🗑️ Chat history cleared")
                        else:
                            print("\n❌ Failed to clear history")

                    else:
                        print(f"❓ Unknown command: {cmd}")

                    continue

                # Send message
                await send_message(transport, line)

            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break

    finally:
        # Cleanup
        await update_presence(transport, online=False)
        receive_task.cancel()
        state_task.cancel()

        try:
            await receive_task
            await state_task
        except asyncio.CancelledError:
            pass


async def main() -> None:
    """Main entry point."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + "   Firebase Realtime Database Chat Demo".center(58) + "║")
    print("╚" + "═" * 58 + "╝")

    # Load configuration
    try:
        firebase_config = load_firebase_config()

        # Validate configuration
        if not firebase_config.project_id or not firebase_config.database_url:
            raise ValueError("Missing Firebase configuration")

        print(f"\n✅ Firebase Project: {firebase_config.project_id}")
        print(f"✅ Database URL: {firebase_config.database_url}")

    except Exception as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\n📋 Required environment variables:")
        print(create_sample_config())
        sys.exit(1)

    # Create transport config
    transport_config = TransportConfig(
        firebase_url=firebase_config.database_url,
        firebase_credentials=firebase_config.credentials_file,
        timeout=30.0,
    )

    # Use async context manager for clean connect/disconnect
    print("\n🔌 Connecting to Firebase...")

    async with FirebaseTransport(
        transport_config,
        session_id=SESSION_ID,
        enable_offline=True,
        auto_reconnect=True,
        sync_state=True,
    ) as transport:

        if transport.connection_state != ConnectionState.CONNECTED:
            print("❌ Failed to connect to Firebase")
            sys.exit(1)

        print("✅ Connected!")

        # Register callbacks
        transport.on_disconnect(lambda: print("\n⚠️ Disconnected from Firebase"))
        transport.on_connect(lambda: print("\n✅ Reconnected to Firebase"))

        # Run interactive chat
        await interactive_chat(transport)

    print("\n🔌 Disconnected from Firebase")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
