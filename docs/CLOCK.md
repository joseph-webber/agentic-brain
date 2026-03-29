# Brain Clock — Single Source of Truth for Time

The `Clock` singleton provides Adelaide-aware time throughout the entire
agentic-brain codebase. **Always use it instead of raw `datetime.now()`**
so timestamps are consistent and timezone-correct.

## Quick Start

```python
from agentic_brain.utils.clock import clock

# Current Adelaide datetime
now = clock.now()           # alias for now_adelaide()
now = clock.now_adelaide()  # explicit

# Current UTC datetime
utc = clock.now_utc()

# Current year (Adelaide)
year = clock.year()         # e.g. 2026

# ISO-formatted strings
clock.iso_date()            # "2026-07-12"
clock.iso_datetime()        # "2026-07-12T14:30:00+09:30"
```

## Top-Level Import

The clock is re-exported from the package root for convenience:

```python
from agentic_brain import clock, get_clock, Clock
```

## Human-Friendly Output

```python
clock.human_time()   # "2:30 PM"
clock.human_date()   # "Saturday, July 12, 2026"
clock.greeting()     # "Good afternoon"
clock.format("%A")   # "Saturday"
```

## Business Logic Helpers

```python
clock.is_business_hours()  # True during weekday 9 AM–5 PM Adelaide
clock.is_weekend()         # True on Saturday/Sunday
```

## Converting Other Datetimes

```python
from datetime import datetime, timezone

server_time = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
adelaide = clock.to_adelaide(server_time)  # 2026-07-12 13:30:00+09:30
back_utc = clock.to_utc(adelaide)
```

## Voice Integration

The conversational voice system uses the clock for greetings:

```python
from agentic_brain.voice.conversation import greet

greet()           # "Good morning, Joseph!" (based on Adelaide time)
greet("Karen")    # "Good afternoon, Karen!"
```

## When NOT to Use the Clock

| Situation | Use Instead |
|-----------|-------------|
| Measuring elapsed wall time | `time.time()` or `time.monotonic()` |
| Performance benchmarks | `time.perf_counter()` |
| OAuth token expiry checks | `time.time()` |
| UTC timestamps for server records | `clock.now_utc()` is fine, or keep `datetime.now(UTC)` |

## Singleton Guarantee

`Clock` is a thread-safe singleton. Every call to `Clock()` or
`get_clock()` returns the **same instance**. The module-level `clock`
variable is the canonical reference.

```python
from agentic_brain.utils.clock import clock, get_clock, Clock

assert clock is get_clock()
assert clock is Clock()
```
