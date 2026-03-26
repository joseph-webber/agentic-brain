# Dashboard

Web-based admin dashboard for monitoring and managing the Agentic Brain system.

## Components

- **app.py** - FastAPI router and dashboard HTML/CSS/JavaScript
- **stats** - Real-time system statistics
- **health** - System health monitoring
- **sessions** - Active session management

## Key Features

- Real-time system statistics (sessions, messages, memory, uptime)
- Health monitoring (Neo4j, LLM provider, memory)
- Active session management and viewing
- System configuration interface
- Responsive design (mobile, tablet, desktop)
- Accessibility support (VoiceOver, screen readers)
- Font Awesome icons and Tailwind CSS styling
- Auto-refreshing metrics (5-second intervals)

## Quick Start

```python
from fastapi import FastAPI
from agentic_brain.dashboard import create_dashboard_router

app = FastAPI()

# Mount dashboard
router = create_dashboard_router(
    sessions_dict=sessions,
    session_messages_dict=session_messages
)
app.include_router(router)

# Access in browser
# http://localhost:8000/dashboard
```

## Available Endpoints

- `GET /dashboard` - Dashboard HTML page
- `GET /api/stats` - System statistics (JSON)
- `GET /api/health` - System health status
- `GET /api/sessions` - List active sessions
- `POST /api/config` - Update configuration
- `DELETE /api/sessions` - Clear all sessions

## Configuration

```python
# Environment variables
DASHBOARD_REFRESH_INTERVAL=5000  # milliseconds
DASHBOARD_SESSION_LIMIT=100
```

## See Also

- [Chat Module](../chat/README.md) - Chat sessions displayed in dashboard
- [API Reference](../../../docs/api/dashboard.md)
