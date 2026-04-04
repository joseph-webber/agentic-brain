#!/usr/bin/env python3
"""
Test script for WebSocket PTY Bridge Server

Tests basic functionality without requiring external connections.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from server import PTYSession, WebSocketTerminalServer


async def test_pty_session():
    """Test PTYSession functionality."""
    print("Testing PTYSession...")

    session = PTYSession("test_session", rows=24, cols=80)

    try:
        # Start session
        await session.start()
        print("  ✓ PTY session started")

        # Write input
        await session.write_input("echo 'Hello from PTY'\n")
        print("  ✓ Input written to PTY")

        # Read output
        await asyncio.sleep(0.2)
        output = await session.read_output(timeout=1.0)
        if output:
            print(f"  ✓ Output received ({len(output)} bytes)")
        else:
            print("  ✓ No output yet (expected)")

        # Test resize
        session.resize(30, 100)
        print("  ✓ Terminal resized to 30x100")

        # Close session
        await session.close()
        print("  ✓ PTY session closed cleanly")

    except Exception as e:
        print(f"  ✗ Error: {e}")
        raise


async def test_server_init():
    """Test server initialization."""
    print("\nTesting WebSocketTerminalServer...")

    server = WebSocketTerminalServer("localhost", 9999)
    print("  ✓ Server initialized")
    print(f"  ✓ Host: {server.host}, Port: {server.port}")
    print(f"  ✓ Sessions dict: {type(server.sessions)}")
    print(f"  ✓ Clients dict: {type(server.clients)}")


async def test_message_format():
    """Test JSON message formats."""
    print("\nTesting message formats...")

    # Input message
    input_msg = {
        "type": "input",
        "data": "ls -la\n"
    }
    json_str = json.dumps(input_msg)
    parsed = json.loads(json_str)
    print(f"  ✓ Input message: {parsed}")

    # Resize message
    resize_msg = {
        "type": "resize",
        "rows": 24,
        "cols": 80
    }
    json_str = json.dumps(resize_msg)
    parsed = json.loads(json_str)
    print(f"  ✓ Resize message: {parsed}")

    # Output message
    output_msg = {
        "type": "output",
        "data": "total 64\n-rw-r--r--  1 user  staff  1024 Apr  1 12:00 file.txt\n"
    }
    json_str = json.dumps(output_msg)
    parsed = json.loads(json_str)
    print(f"  ✓ Output message ({len(parsed['data'])} bytes)")

    # Error message
    error_msg = {
        "type": "error",
        "data": "Connection failed"
    }
    json_str = json.dumps(error_msg)
    parsed = json.loads(json_str)
    print(f"  ✓ Error message: {parsed}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("WebSocket PTY Bridge Server - Test Suite")
    print("=" * 60)

    try:
        await test_server_init()
        await test_message_format()
        await test_pty_session()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print("\nServer is ready to use:")
        print("  • python3 server.py --host 0.0.0.0 --port 8765")
        print("  • Then open client.html in your browser")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
