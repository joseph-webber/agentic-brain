#!/usr/bin/env python3
"""
QUICKSTART - WebSocket PTY Bridge Server

This script demonstrates how to use the server locally with auto-installation.
"""

import subprocess
import sys
import os
from pathlib import Path


def install_dependencies():
    """Install required packages."""
    print("📦 Installing dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "websockets"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"❌ Failed to install dependencies")
        print(result.stderr.decode())
        sys.exit(1)
    print("✓ Dependencies installed")


def show_banner():
    """Show welcome banner."""
    print(
        """
╔════════════════════════════════════════════════════════════╗
║   WebSocket PTY Bridge Server - Quickstart                 ║
╚════════════════════════════════════════════════════════════╝
"""
    )


def show_menu():
    """Show interactive menu."""
    menu = """
What would you like to do?

1. ▶️  Start server (localhost:8765)
2. 🌐 Start server (0.0.0.0:8765)  - accessible from other machines
3. 🧪 Run tests
4. 📖 Show README
5. ❌ Exit

Choose [1-5]: """
    return input(menu).strip()


def start_server(host="localhost"):
    """Start the server."""
    port = 8765
    script_dir = Path(__file__).parent
    server_script = script_dir / "server.py"

    print(f"\n🚀 Starting server on {host}:{port}")
    print(f"📂 Directory: {script_dir}")
    print(f"🔗 WebSocket URL: ws://{host}:{port}")
    print("\n" + "=" * 60)
    print("Server starting... (Press Ctrl+C to stop)")
    print("=" * 60 + "\n")

    try:
        subprocess.run(
            [sys.executable, str(server_script), "--host", host, "--port", str(port)],
            cwd=str(script_dir),
        )
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")


def run_tests():
    """Run the test suite."""
    script_dir = Path(__file__).parent
    test_script = script_dir / "test_server.py"

    print("\n🧪 Running tests...\n")
    try:
        subprocess.run([sys.executable, str(test_script)], cwd=str(script_dir))
    except Exception as e:
        print(f"❌ Test failed: {e}")


def show_readme():
    """Show README."""
    script_dir = Path(__file__).parent
    readme = script_dir / "README.md"

    if readme.exists():
        with open(readme) as f:
            print(f"\n{f.read()}")
    else:
        print("❌ README.md not found")


def show_connection_info():
    """Show how to connect."""
    print(
        """
📱 To connect to the server:

Option 1 - Direct File (Easiest)
  • Open in your browser: file://$HOME/brain/agentic-brain/tools/web_terminal/client.html
  • The WebSocket will connect to localhost:8765

Option 2 - Via HTTP Server
  • Start an HTTP server in the directory:
    cd $HOME/brain/agentic-brain/tools/web_terminal
    python3 -m http.server 8000
  • Open: http://localhost:8000/client.html
  • Connect to: ws://localhost:8765

Option 3 - Remote Connection
  • Start server with: ./quickstart.py → Option 2
  • From another machine, connect to: ws://<your-ip>:8765

🔧 JSON Message Examples:

Send command:
  {"type": "input", "data": "ls -la\\n"}

Resize terminal:
  {"type": "resize", "rows": 24, "cols": 80}

Receive output:
  {"type": "output", "data": "drwxr-xr-x  12 user  staff  384 Apr  1 12:00 \\n"}
"""
    )


def main():
    """Run the interactive quickstart."""
    show_banner()

    # Check and install dependencies
    try:
        import websockets
    except ImportError:
        install_dependencies()

    # Main loop
    while True:
        choice = show_menu()

        if choice == "1":
            start_server("localhost")
        elif choice == "2":
            show_connection_info()
            start_server("0.0.0.0")
        elif choice == "3":
            run_tests()
        elif choice == "4":
            show_readme()
        elif choice == "5":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice, try again")

        if choice in ["1", "2"]:
            print("\n" + "=" * 60)
            show_connection_info()
            print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
