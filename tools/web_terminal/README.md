# WebSocket PTY Bridge Server

A production-ready Python WebSocket server that bridges WebSocket clients to pseudo-terminal (PTY) shells, allowing remote terminal access through a web browser.

## Features

✅ **Multiple Concurrent Sessions** - Each client gets its own isolated PTY shell  
✅ **Terminal Resize Support** - Handles SIGWINCH for dynamic terminal resizing  
✅ **JSON Message Protocol** - Structured communication between client and server  
✅ **Graceful Shutdown** - Proper cleanup of all sessions and processes  
✅ **Error Handling** - Comprehensive error handling and logging  
✅ **Non-Blocking I/O** - Uses async/await for efficient resource usage  
✅ **Security** - Process isolation, message size limits, connection timeouts  

## Requirements

- Python 3.7+
- `websockets` library (`pip install -r requirements.txt`)
- Unix-like OS with PTY support (Linux, macOS)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make server executable
chmod +x server.py
```

## Usage

### Start the Server

```bash
# Default (localhost:8765)
python3 server.py

# Custom host/port
python3 server.py --host 0.0.0.0 --port 9000

# Debug logging
python3 server.py --log-level DEBUG
```

### Connect via Web Browser

1. Serve the `client.html` file via HTTP
2. Open in browser: `http://localhost:8080/client.html` (or wherever you're serving from)
3. Or open directly if you're running server on same machine: `file:///path/to/client.html`

### JSON Message Protocol

#### Client → Server

**Input Message:**
```json
{
  "type": "input",
  "data": "ls -la\n"
}
```

**Resize Message:**
```json
{
  "type": "resize",
  "rows": 24,
  "cols": 80
}
```

#### Server → Client

**Output Message:**
```json
{
  "type": "output",
  "data": "user@host:~$ "
}
```

**Error Message:**
```json
{
  "type": "error",
  "data": "Connection lost"
}
```

## Architecture

### Server Components

- **PTYSession** - Manages individual PTY instances
  - Spawns bash shell with proper session isolation
  - Handles I/O bridging (stdin/stdout)
  - Manages process lifecycle
  
- **WebSocketTerminalServer** - Manages WebSocket connections
  - Handles client connections/disconnections
  - Routes messages to appropriate PTY sessions
  - Manages graceful shutdown

- **Signal Handling**
  - SIGTERM/SIGINT for graceful shutdown
  - SIGWINCH (terminal resize) propagated to shell processes

### Data Flow

```
WebSocket Client
       ↓
  [JSON Messages]
       ↓
WebSocketTerminalServer
       ↓
  PTYSession
       ↓
  [bash shell process]
```

## Example Usage

### Terminal Commands

```bash
# List files
ls -la

# Navigate directories
cd /tmp
pwd

# Run programs
python3 --version

# Interactive programs
vim
top
htop

# Exit terminal
exit
```

### Command Line Options

```bash
python3 server.py --help

Options:
  --host HOST              Host to bind to (default: 0.0.0.0)
  --port PORT              Port to bind to (default: 8765)
  --log-level {DEBUG,INFO,WARNING,ERROR}
                          Logging level (default: INFO)
```

## Performance Considerations

- **Max message size**: 10 KB (configurable)
- **Max buffered messages**: 32 (configurable)
- **Read buffer**: 4 KB per read
- **Non-blocking I/O**: Prevents blocking on slow connections

## Security Considerations

⚠️ **IMPORTANT**: This server does not include authentication. For production use:

1. Add authentication (JWT, OAuth, API keys)
2. Use WSS (WebSocket Secure) with TLS/SSL
3. Rate limiting on message throughput
4. Resource limits (process CPU, memory)
5. Restricted shell environment
6. Input validation and sanitization

Example with TLS:
```python
import ssl
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("cert.pem", "key.pem")

server = await serve(..., ssl=ssl_context)
```

## Troubleshooting

### Connection refused
- Check if server is running: `lsof -i :8765`
- Verify host/port: `python3 server.py --host 0.0.0.0`

### Terminal not responding
- Check server logs for errors
- Ensure bash is available: `which bash`
- Verify PTY support on your system

### Permission denied
- Run without sudo (avoid privilege elevation)
- Check directory permissions for log files

### Process cleanup issues
- Processes are cleaned up with SIGHUP/SIGKILL
- Check `ps aux | grep bash` for orphaned processes

## Logging

Server logs include:
- Connection/disconnection events
- Terminal resize operations
- Input/output errors
- Session lifecycle events

Set log level via `--log-level` argument.

## Development

### Running Tests

```bash
# Basic functionality test
python3 -c "
import asyncio
from server import WebSocketTerminalServer

async def test():
    server = WebSocketTerminalServer('localhost', 9999)
    print('✓ Server initialized')

asyncio.run(test())
```

### Performance Tuning

Modify in `server.py`:
```python
self.server = await serve(
    self.handle_client,
    self.host,
    self.port,
    max_size=10_000,      # Increase for large outputs
    max_queue=32,         # Buffer size
    compression=None,
)
```

## License

MIT License - Feel free to use and modify

## Contributing

Improvements welcome! Consider:
- Terminal color support (xterm-256color)
- Session persistence
- Recording/playback
- Multiple shell types
- Plugin system
