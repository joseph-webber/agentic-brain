#!/usr/bin/env python3
"""
WebSocket PTY Bridge Server

Bridges WebSocket clients to pseudo-terminal shells. Each client gets its own
PTY session running a bash shell. Supports terminal resize, input/output
bridging, and graceful shutdown.

JSON Message Protocol:
  Input:  {"type": "input", "data": "<command>"}
  Input:  {"type": "resize", "rows": 24, "cols": 80}
  Output: {"type": "output", "data": "<stdout>"}
  Output: {"type": "error", "data": "<error message>"}
"""

import asyncio
import fcntl
import json
import logging
import os
import pty
import signal
import struct
import subprocess
import sys
import termios
import weakref
from pathlib import Path
from typing import Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol, serve

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PTYSession:
    """Manages a single PTY session with bash shell."""

    def __init__(self, session_id: str, rows: int = 24, cols: int = 80):
        """
        Initialize a PTY session.

        Args:
            session_id: Unique identifier for this session
            rows: Terminal rows
            cols: Terminal columns
        """
        self.session_id = session_id
        self.rows = rows
        self.cols = cols
        self.process: Optional[subprocess.Popen] = None
        self.master_fd: Optional[int] = None
        self.read_task: Optional[asyncio.Task] = None
        self.closed = False

    async def start(self) -> None:
        """Spawn bash shell in PTY."""
        try:
            # Spawn PTY with bash shell
            self.master_fd, slave_fd = pty.openpty()

            # Set terminal size
            self._set_pty_size(self.master_fd, self.rows, self.cols)

            # Start bash process
            self.process = subprocess.Popen(
                ["/bin/bash", "-i", "-l"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,  # Create new session (avoid signals propagating)
            )

            # Close slave fd in parent
            os.close(slave_fd)

            # Set non-blocking mode
            self._set_nonblocking(self.master_fd)

            # Start reading from PTY
            self.read_task = asyncio.create_task(self._read_loop())
            logger.info(
                f"PTY session {self.session_id} started (PID: {self.process.pid})"
            )

        except Exception as e:
            logger.error(f"Failed to start PTY session {self.session_id}: {e}")
            self.closed = True
            raise

    async def _read_loop(self) -> None:
        """Continuously read from PTY master and put data in queue."""
        while not self.closed and self.master_fd is not None:
            try:
                # Read from PTY (non-blocking)
                data = os.read(self.master_fd, 4096)
                if data:
                    # Data is available in the queue for consumers
                    # This is handled by consumers reading from their own tasks
                    pass
                else:
                    # EOF from PTY
                    logger.info(f"PTY session {self.session_id} received EOF")
                    self.closed = True
                    break

            except BlockingIOError:
                # No data available, yield control
                await asyncio.sleep(0.01)

            except OSError as e:
                if self.closed:
                    break
                logger.warning(f"Read error in PTY session {self.session_id}: {e}")
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.error(
                    f"Unexpected error in PTY read loop {self.session_id}: {e}"
                )
                self.closed = True
                break

    async def write_input(self, data: str) -> None:
        """Write input to PTY."""
        if self.closed or self.master_fd is None:
            raise ValueError(f"PTY session {self.session_id} is closed")

        try:
            os.write(self.master_fd, data.encode())
        except OSError as e:
            logger.error(f"Failed to write to PTY {self.session_id}: {e}")
            self.closed = True
            raise

    async def read_output(self, timeout: float = 0.1) -> Optional[str]:
        """Read available output from PTY."""
        if self.closed or self.master_fd is None:
            return None

        try:
            # Use select-like behavior with asyncio
            loop = asyncio.get_event_loop()
            data = await asyncio.wait_for(
                loop.run_in_executor(None, self._read_nonblock), timeout=timeout
            )
            return data
        except TimeoutError:
            return None
        except Exception as e:
            logger.warning(f"Error reading from PTY {self.session_id}: {e}")
            return None

    def _read_nonblock(self) -> Optional[str]:
        """Non-blocking read from PTY master."""
        if self.master_fd is None:
            return None

        try:
            data = os.read(self.master_fd, 4096)
            if data:
                return data.decode("utf-8", errors="replace")
            else:
                self.closed = True
                return None
        except BlockingIOError:
            return None
        except Exception:
            return None

    def resize(self, rows: int, cols: int) -> None:
        """Resize terminal."""
        if self.closed or self.master_fd is None:
            return

        self.rows = rows
        self.cols = cols

        try:
            self._set_pty_size(self.master_fd, rows, cols)
            logger.debug(f"Resized PTY {self.session_id} to {rows}x{cols}")
        except Exception as e:
            logger.error(f"Failed to resize PTY {self.session_id}: {e}")

    @staticmethod
    def _set_pty_size(fd: int, rows: int, cols: int) -> None:
        """Set PTY size using TIOCSWINSZ."""
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    @staticmethod
    def _set_nonblocking(fd: int) -> None:
        """Set file descriptor to non-blocking mode."""
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    async def close(self) -> None:
        """Close PTY session gracefully."""
        if self.closed:
            return

        self.closed = True

        # Cancel read task
        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass

        # Close master fd
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        # Terminate process
        if self.process:
            try:
                # Send SIGHUP to process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGHUP)
                # Give it a moment to exit gracefully
                await asyncio.sleep(0.1)
                # Force kill if still running
                if self.process.poll() is None:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=1)
            except Exception as e:
                logger.warning(f"Error terminating process in {self.session_id}: {e}")

        logger.info(f"PTY session {self.session_id} closed")


class WebSocketTerminalServer:
    """WebSocket server managing multiple PTY sessions."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        """
        Initialize WebSocket terminal server.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        self.host = host
        self.port = port
        self.sessions: Dict[str, PTYSession] = {}
        self.clients: Dict[WebSocketServerProtocol, str] = weakref.WeakKeyDictionary()
        self.server = None
        self._shutdown = False

    async def handle_client(
        self, websocket: WebSocketServerProtocol, path: str
    ) -> None:
        """Handle WebSocket client connection."""
        session_id = f"session_{id(websocket)}"
        pty_session = None

        try:
            # Create PTY session
            pty_session = PTYSession(session_id)
            await pty_session.start()
            self.sessions[session_id] = pty_session
            self.clients[websocket] = session_id

            logger.info(f"Client connected: {session_id}")

            # Send initial welcome message
            await websocket.send(
                json.dumps(
                    {
                        "type": "output",
                        "data": "Terminal session started. Type 'exit' to close.\n",
                    }
                )
            )

            # Start output reader task
            reader_task = asyncio.create_task(
                self._read_output_loop(websocket, pty_session)
            )

            # Handle incoming messages
            async for message in websocket:
                try:
                    msg_data = json.loads(message)
                    await self._handle_message(websocket, pty_session, msg_data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {session_id}")
                    await websocket.send(
                        json.dumps({"type": "error", "data": "Invalid JSON message"})
                    )
                except Exception as e:
                    logger.error(f"Error handling message from {session_id}: {e}")
                    await websocket.send(json.dumps({"type": "error", "data": str(e)}))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {session_id}")

        except Exception as e:
            logger.error(f"Error in client handler {session_id}: {e}")

        finally:
            # Cleanup
            if pty_session:
                await pty_session.close()
                self.sessions.pop(session_id, None)
            if websocket in self.clients:
                del self.clients[websocket]

            try:
                await websocket.close()
            except Exception:
                pass

            logger.info(f"Session cleaned up: {session_id}")

    async def _read_output_loop(
        self, websocket: WebSocketServerProtocol, pty_session: PTYSession
    ) -> None:
        """Continuously read output from PTY and send to client."""
        while not pty_session.closed:
            try:
                data = await pty_session.read_output(timeout=0.1)
                if data:
                    await websocket.send(json.dumps({"type": "output", "data": data}))
                else:
                    await asyncio.sleep(0.01)

            except websockets.exceptions.ConnectionClosed:
                logger.debug("Client disconnected in output loop")
                break

            except Exception as e:
                logger.warning(f"Error in output loop: {e}")
                await asyncio.sleep(0.1)

    async def _handle_message(
        self,
        websocket: WebSocketServerProtocol,
        pty_session: PTYSession,
        msg_data: dict,
    ) -> None:
        """Handle incoming message from client."""
        msg_type = msg_data.get("type")

        if msg_type == "input":
            data = msg_data.get("data", "")
            await pty_session.write_input(data)

        elif msg_type == "resize":
            rows = msg_data.get("rows", 24)
            cols = msg_data.get("cols", 80)
            pty_session.resize(rows, cols)

        else:
            logger.warning(f"Unknown message type: {msg_type}")
            await websocket.send(
                json.dumps(
                    {"type": "error", "data": f"Unknown message type: {msg_type}"}
                )
            )

    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket Terminal Server on {self.host}:{self.port}")

        try:
            self.server = await serve(
                self.handle_client,
                self.host,
                self.port,
                # Security settings
                max_size=10_000,  # Max message size
                max_queue=32,  # Max buffered messages
                compression=None,
                close_timeout=10,
            )

            logger.info(f"✓ Server running on ws://{self.host}:{self.port}")

            # Keep server running
            await asyncio.Future()

        except OSError as e:
            logger.error(f"Failed to start server: {e}")
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown server and all sessions."""
        logger.info("Shutting down server...")
        self._shutdown = True

        # Close all sessions
        for session_id, pty_session in list(self.sessions.items()):
            try:
                await pty_session.close()
            except Exception as e:
                logger.warning(f"Error closing session {session_id}: {e}")

        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logger.info("Server shutdown complete")


async def run_server(host: str = "localhost", port: int = 8765):
    """Run the WebSocket terminal server."""
    server = WebSocketTerminalServer(host, port)

    # Handle signals
    loop = asyncio.get_event_loop()

    def handle_signal(signum):
        logger.info(f"Received signal {signum}")
        loop.create_task(server.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await server.start()
    except KeyboardInterrupt:
        await server.shutdown()
    except Exception as e:
        logger.error(f"Server error: {e}")
        await server.shutdown()
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WebSocket PTY Bridge Server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Port to bind to (default: 8765)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    try:
        asyncio.run(run_server(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
