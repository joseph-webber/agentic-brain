# Admin Dashboard for Agentic Brain

A modern, accessible admin dashboard for monitoring and managing the agentic-brain API server.

## Quick Start

### Access the Dashboard
```
http://localhost:8000/dashboard
```

### Start the Server
```bash
python -m agentic_brain.api.server
# or with auto-reload:
uvicorn agentic_brain.api.server:app --reload
```

## Features

### Real-Time Monitoring
- **Active Sessions**: Track current user sessions
- **Message Count**: Total messages processed
- **Memory Usage**: Real-time memory consumption with visual progress bar
- **Uptime**: Server uptime with formatted display
- **System Health**: Neo4j, LLM provider, and memory status indicators

### System Health Dashboard
- Neo4j connection status (live indicator)
- LLM provider availability
- Memory usage status
- Overall system health summary
- Pulsing status indicators for real-time feedback

### Session Management
- View all active sessions with session IDs
- Message count per session
- Session creation timestamps
- Clear all sessions (with confirmation)

### Quick Actions
- Direct links to API documentation (/docs)
- Neo4j Browser shortcut (http://localhost:7474)
- Session clearing with safety confirmation
- One-click dashboard refresh

## API Endpoints

### GET `/dashboard`
Serves the dashboard HTML page.

**Response:** HTML dashboard page

### GET `/dashboard/api/stats`
Get current system statistics.

**Response:**
```json
{
  "timestamp": "2026-03-20T03:20:00.000000",
  "sessions_active": 5,
  "total_messages": 150,
  "memory_usage_mb": 125.4,
  "uptime_seconds": 3600
}
```

### GET `/dashboard/api/health`
Get system health status.

**Response:**
```json
{
  "status": "healthy",
  "neo4j_connected": true,
  "llm_provider_available": true,
  "memory_ok": true,
  "timestamp": "2026-03-20T03:20:00.000000"
}
```

### GET `/dashboard/api/sessions`
Get list of active sessions.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "sess_abc123def456",
      "created_at": "2026-03-20T03:10:00.000000",
      "messages_count": 12,
      "user_id": null
    },
    ...
  ]
}
```

### DELETE `/dashboard/api/sessions`
Clear all sessions (WARNING: Cannot be undone).

**Response:**
```json
{
  "status": "success",
  "cleared": 5
}
```

### POST `/dashboard/api/config`
Update system configuration.

**Request:**
```json
{
  "key": "setting_name",
  "value": "new_value"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration updated: setting_name"
}
```

## Design & Accessibility

### Technology Stack
- **Backend**: FastAPI (no additional dependencies)
- **Frontend**: HTML5 + Tailwind CSS (CDN)
- **Styling**: Tailwind CSS via CDN
- **Icons**: Font Awesome 6.4.0 CDN
- **Interactivity**: Vanilla JavaScript (no frameworks)

### Accessibility (WCAG 2.1 AA)
✅ Semantic HTML5 structure
✅ Proper heading hierarchy (h1, h2)
✅ ARIA labels on all interactive elements
✅ Focus-visible outlines (3px blue)
✅ Skip to main content link
✅ VoiceOver screen reader support
✅ Color contrast ratios ≥ 4.5:1
✅ Readable font sizes and spacing
✅ Keyboard navigation support

### Responsive Design
- Mobile-first approach
- Tailwind responsive grid (md:, lg: breakpoints)
- Touch-friendly button sizes
- Readable on all screen sizes (360px to 2560px+)

### Dark Theme
- Eye-friendly dark background (gray-900)
- High contrast text (gray-100, white)
- Gradient accents (primary, success, warning, danger)
- Smooth animations and transitions

## Architecture

### File Structure
```
src/agentic_brain/
├── dashboard/
│   ├── __init__.py          # Package exports
│   └── app.py               # FastAPI router + HTML template
└── api/
    └── server.py            # Modified to mount dashboard
```

### How It Works

1. **Dashboard Router Creation**
   ```python
   from agentic_brain.dashboard import create_dashboard_router
   
   router = create_dashboard_router(
       sessions_dict=sessions,
       session_messages_dict=session_messages,
   )
   app.include_router(router)
   ```

2. **Real-Time Updates**
   - JavaScript polls `/dashboard/api/stats` every 5 seconds
   - Updates UI with current statistics
   - Handles errors gracefully with fallback display

3. **Session Management**
   - Accesses in-memory session storage from main API
   - Displays active sessions in real-time
   - Allows administrative actions (clear, etc.)

## Customization

### Add New Metrics
1. Add endpoint to `app.py`:
   ```python
   @router.get("/api/new-metric")
   async def get_new_metric():
       return {"value": 42}
   ```

2. Add UI element to HTML template:
   ```html
   <div id="new-metric-card" class="bg-gray-800 rounded-lg p-6">
       <p id="new-metric-value">-</p>
   </div>
   ```

3. Add update function in JavaScript:
   ```javascript
   async function updateNewMetric() {
       const response = await fetch(`${API_BASE}/new-metric`);
       const data = await response.json();
       document.getElementById('new-metric-value').textContent = data.value;
   }
   ```

### Modify Styling
- Edit Tailwind classes in HTML template (no separate CSS file)
- All styles are inline with Tailwind utility classes
- No build step required

### Change Refresh Interval
```javascript
// In init() function, change:
refreshInterval = setInterval(refreshDashboard, 5000);
// to:
refreshInterval = setInterval(refreshDashboard, 10000); // 10 seconds
```

## Security Considerations

### XSS Protection
- All user-controlled data is HTML-escaped before display
- Session IDs and other values use `.textContent` (not `.innerHTML`)

### CSRF Protection
- No state-changing operations from GET requests
- DELETE operations require explicit action

### Error Handling
- API errors are caught and displayed safely
- No sensitive information in error messages
- Graceful degradation if API is unavailable

## Performance

- **Zero Build Step**: HTML/CSS/JS served directly, no compilation
- **CDN Resources**: Tailwind and Font Awesome from CDN
- **Lightweight Endpoints**: No database queries, in-memory access only
- **Efficient Updates**: 5-second polling interval (configurable)
- **Async Operations**: All I/O is async-ready

## Troubleshooting

### Dashboard not loading
- Ensure server is running on http://localhost:8000
- Check browser console for JavaScript errors
- Verify FastAPI is installed: `pip install 'fastapi>=0.104.0'`

### Stats not updating
- Check network tab in browser DevTools
- Ensure `/dashboard/api/stats` returns valid JSON
- Verify sessions are actually active

### Memory usage always shows high
- If psutil is not installed, memory is estimated (~50MB base)
- Install psutil for accurate readings: `pip install psutil`

## Future Enhancements

Planned improvements:
- WebSocket support for real-time updates (no polling)
- User authentication/authorization
- Configuration management UI
- Performance metrics graphs
- Session playback/analysis
- Log viewer with filtering
- Alert system
- Dark/light theme toggle
- Export stats to CSV/JSON

## License

GPL-3.0-or-later

See LICENSE file in repository for details.
