# Clock MCP Server

**Location**: `/Users/joe/brain/agentic-brain/src/agentic_brain/mcp/clock_server.py`

## Purpose

The Clock MCP Server provides reliable date/time tools that AI agents can use to **ALWAYS get correct dates**. This solves a critical problem: AI models have training data that is ~2 years out of date, causing them to frequently confuse the current year.

## The Problem

- AI models trained in 2024 think it's 2024, not 2026
- Stale training data leads to incorrect date assumptions
- Users (and AI agents) need **real-time, accurate** date/time info

## The Solution

This MCP server uses the thread-safe `Clock` singleton from `agentic_brain.utils.clock` to provide:

✅ **Always current dates** - No stale data  
✅ **Adelaide timezone aware** - the user's local time (ACDT/ACST)  
✅ **Business hours detection** - Know when it's work time  
✅ **Smart greetings** - Based on actual time of day  
✅ **Timezone conversions** - Convert between any timezones  
✅ **Custom formatting** - Format dates any way needed  

## Available Tools

### 1. `clock_now`
Get current Adelaide datetime in various formats.

```python
clock_now("iso")       # "2026-03-22T15:30:45.123456+10:30"
clock_now("human")     # "3:30 PM"
clock_now("timestamp") # "1774752670"
clock_now("full")      # "Friday, March 22, 2026 at 3:30 PM"
```

### 2. `clock_adelaide`
Get comprehensive Adelaide time information (the user's timezone).

Returns JSON with:
- Current datetime
- Date and time
- Timezone info (Australia/Adelaide)
- UTC offset
- Current year
- Day of week
- Appropriate greeting
- Business hours status
- Weekend detection

```json
{
  "datetime": "2026-03-22T15:30:45.123456+10:30",
  "date": "2026-03-22",
  "time": "3:30 PM",
  "timezone": "Australia/Adelaide",
  "offset": "+1030",
  "year": 2026,
  "day": "Friday",
  "greeting": "Good afternoon",
  "is_business_hours": true,
  "is_weekend": false
}
```

### 3. `clock_utc`
Get current UTC time.

```json
{
  "datetime": "2026-03-22T05:00:45.123456+00:00",
  "date": "2026-03-22",
  "time": "05:00:45",
  "timezone": "UTC",
  "timestamp": 1774752645
}
```

### 4. `clock_year` ⚡ CRITICAL
Get the current year. **Prevents stale year confusion!**

```json
{
  "year": 2026,
  "message": "The current year is 2026",
  "warning": "AI training data is ~2 years stale. Use web search for current info."
}
```

### 5. `clock_date`
Get current date in ISO format (YYYY-MM-DD).

```
"2026-03-22"
```

### 6. `clock_greeting`
Get appropriate greeting based on Adelaide time of day.

```json
{
  "greeting": "Good afternoon",
  "time": "3:30 PM",
  "hour": 15,
  "reason": "Between 12:00 and 18:00"
}
```

**Greeting Rules:**
- **Morning** (5:00-11:59): "Good morning"
- **Afternoon** (12:00-17:59): "Good afternoon"
- **Evening** (18:00-4:59): "Good evening"

### 7. `clock_is_business_hours`
Check if it's currently business hours in Adelaide.

Business hours: Monday-Friday, 9 AM - 5 PM

```json
{
  "is_business_hours": true,
  "is_weekend": false,
  "time": "3:30 PM",
  "day": "Friday",
  "hour": 15
}
```

### 8. `clock_convert`
Convert time between timezones.

```python
clock_convert("UTC", "Australia/Adelaide", "2026-03-22T05:00:00Z")
```

Returns:
```json
{
  "from": {
    "datetime": "2026-03-22T05:00:00+00:00",
    "timezone": "UTC"
  },
  "to": {
    "datetime": "2026-03-22T15:30:00+10:30",
    "timezone": "Australia/Adelaide"
  },
  "offset_hours": 10.5
}
```

**Supported timezones** (from config):
- Australia: Adelaide, Sydney, Melbourne, Brisbane, Perth
- International: UTC, London, New York, Los Angeles, Tokyo, Singapore

### 9. `clock_format`
Format current Adelaide time with custom strftime format.

```python
clock_format("%A, %B %d, %Y")     # "Friday, March 22, 2026"
clock_format("%Y-%m-%d")          # "2026-03-22"
clock_format("%I:%M %p")          # "03:30 PM"
clock_format("%Y-%m-%d %H:%M:%S") # "2026-03-22 15:30:45"
```

## Configuration

Location: `/Users/joe/brain/agentic-brain/config/timezone.yaml`

Key settings:
```yaml
default_timezone: Australia/Adelaide
user_timezone: Australia/Adelaide
display_format: 12h  # or 24h

business_hours:
  start: 9   # 9 AM
  end: 17    # 5 PM

greetings:
  morning:
    start: 5
    end: 12
    message: "Good morning"
  afternoon:
    start: 12
    end: 18
    message: "Good afternoon"
  evening:
    start: 18
    end: 5
    message: "Good evening"

current_year: 2026  # Update annually!
training_data_year: 2024
staleness_warning: "AI training data is ~2 years out of date. Use web search for current info."
```

## Usage

### In MCP Server

The clock tools are automatically registered when the MCP server initializes. They're merged with other tools in `tools.py`:

```python
from agentic_brain.mcp.clock_server import get_clock_tools

clock_tools = get_clock_tools()
# Returns dict of 9 clock tools ready for MCP registration
```

### Direct Python Usage

```python
from agentic_brain.mcp.clock_server import (
    clock_now, clock_adelaide, clock_year, clock_date,
    clock_greeting, clock_is_business_hours,
    clock_convert, clock_format, clock_utc
)

# Get current year (NEVER stale!)
print(clock_year())

# Get Adelaide time
print(clock_adelaide())

# Check if business hours
print(clock_is_business_hours())

# Custom format
print(clock_format("%A, %B %d, %Y"))
```

### Via Clock Singleton

All tools use the same thread-safe Clock singleton:

```python
from agentic_brain.utils.clock import get_clock

clock = get_clock()
print(f"Year: {clock.year()}")
print(f"Date: {clock.iso_date()}")
print(f"Time: {clock.human_time()}")
print(f"Greeting: {clock.greeting()}")
```

## Testing

Run the included tests:

```bash
cd /Users/joe/brain/agentic-brain

# Test clock singleton
python3 -c "
from agentic_brain.utils.clock import get_clock
clock = get_clock()
print(f'Year: {clock.year()}')
print(f'Date: {clock.iso_date()}')
print(f'Time: {clock.human_time()}')
print(f'Greeting: {clock.greeting()}')
"

# Test MCP server tools
python3 -c "
from agentic_brain.mcp.clock_server import (
    clock_year, clock_date, clock_adelaide,
    clock_greeting, clock_is_business_hours
)

print('Year:', clock_year())
print('Date:', clock_date())
print('Adelaide:', clock_adelaide())
print('Greeting:', clock_greeting())
print('Business hours:', clock_is_business_hours())
"
```

## Why This Matters

### The Year Problem

AI models trained in 2024 will default to thinking it's 2024 unless explicitly corrected. This causes:

- ❌ Incorrect date calculations
- ❌ Wrong assumptions about "current" events
- ❌ Confusion about software versions, releases, etc.
- ❌ Broken time-based logic

### The Solution

By calling `clock_year()` or any clock tool, agents get **real system time** that's:

- ✅ Always current (not from training data)
- ✅ Timezone-aware (Adelaide-specific)
- ✅ Thread-safe (singleton pattern)
- ✅ Persistent across sessions

## Architecture

```
Clock Singleton (utils/clock.py)
    ↓
Clock MCP Server (mcp/clock_server.py)
    ↓ (registered by)
MCP Tools Registry (mcp/tools.py)
    ↓ (used by)
AgenticMCPServer (mcp/server.py)
    ↓ (exposed to)
AI Agents (Claude, GPT, Ollama, etc.)
```

## Important Notes

1. **Thread-safe**: Uses double-checked locking singleton pattern
2. **Adelaide-first**: All times default to the user's timezone
3. **Business logic**: Built-in awareness of weekdays/weekends
4. **Lazy loading**: Clock instance created on first use
5. **No external deps**: Uses only Python stdlib (datetime, zoneinfo)

## License

Apache-2.0 (same as agentic-brain)

## Author

Agentic Brain Contributors <agentic-brain@proton.me>

---

**BURNED TO ROM**: Clock tools are now part of the core MCP server toolkit. AI agents MUST use these for accurate date/time information.
