# Location Services

**Timezone detection, distance calculations, and service filtering for Australian users.**

---

## Overview

The Location Services module provides:

- 🕐 **Timezone detection** from state, postcode, or GPS coordinates
- 📏 **Distance calculations** using Haversine formula
- 🔍 **Service filtering** by proximity
- 🌅 **Local time formatting** for user-friendly display
- 🇦🇺 **Australian-focused** with DST awareness

All operations are performed locally with no external API calls, making it privacy-respecting and fast.

---

## Quick Start

```python
from agentic_brain.location import LocationService

# Create location service
ls = LocationService()

# Set user location from state
location = ls.set_location_from_state("SA")
print(f"Timezone: {location.timezone_id}")  # Australia/Adelaide
print(f"UTC Offset: {location.utc_offset_hours}")  # 9.5

# Get local time
local_time = ls.get_local_time()
print(f"Local time: {ls.format_time_for_user(local_time)}")
```

---

## Setting Location

### From State

```python
location = ls.set_location_from_state("NSW")
# Returns UserLocation with Australia/Sydney timezone
```

| State | Timezone | UTC Offset | DST? |
|-------|----------|------------|------|
| NSW | Australia/Sydney | +10 (+11 DST) | ✅ |
| VIC | Australia/Melbourne | +10 (+11 DST) | ✅ |
| QLD | Australia/Brisbane | +10 | ❌ |
| SA | Australia/Adelaide | +9.5 (+10.5 DST) | ✅ |
| WA | Australia/Perth | +8 | ❌ |
| TAS | Australia/Hobart | +10 (+11 DST) | ✅ |
| NT | Australia/Darwin | +9.5 | ❌ |
| ACT | Australia/Sydney | +10 (+11 DST) | ✅ |

### From Postcode

```python
location = ls.set_location_from_postcode("5000")
# Detects SA from postcode range, returns Australia/Adelaide timezone
```

**Postcode Ranges:**

| Range | State |
|-------|-------|
| 0200-0299 | ACT |
| 2000-2999 | NSW |
| 3000-3999 | VIC |
| 4000-4999 | QLD |
| 5000-5999 | SA |
| 6000-6999 | WA |
| 7000-7999 | TAS |
| 0800-0999 | NT |

### From GPS Coordinates

```python
location = ls.set_location_from_coordinates(-34.9285, 138.6007)
# Adelaide coordinates → Australia/Adelaide timezone
```

---

## Distance Calculations

### Calculate Distance Between Points

```python
# Distance from Adelaide to Melbourne
distance = ls.calculate_distance_km(
    lat1=-34.9285, lon1=138.6007,  # Adelaide
    lat2=-37.8136, lon2=144.9631   # Melbourne
)
print(f"Distance: {distance:.0f} km")  # ~650 km
```

### Filter Services by Distance

```python
from agentic_brain.location import LocationService

ls = LocationService()
ls.set_location_from_state("SA")

# Services with location data
services = [
    {"name": "Legal Aid SA", "lat": -34.92, "lon": 138.60},
    {"name": "Legal Aid VIC", "lat": -37.81, "lon": 144.96},
    {"name": "Legal Aid NSW", "lat": -33.87, "lon": 151.21},
]

# Find services within 100km
nearby = ls.filter_services_by_distance(
    services,
    max_distance_km=100,
    lat_key="lat",
    lon_key="lon"
)
# Returns: [{"name": "Legal Aid SA", ...}]
```

### Filter by State

```python
services = ls.filter_services_by_state(services, "SA")
```

---

## Time Formatting

### Get Local Time

```python
local_time = ls.get_local_time()
```

### Format for User

```python
formatted = ls.format_time_for_user(local_time)
# "Monday 15 March 2026 at 2:30 PM"
```

### Get Timezone Abbreviation

```python
abbrev = ls.get_timezone_abbrev()
# "ACDT" (SA daylight saving) or "ACST" (SA standard)
```

### Check Business Hours

```python
if ls.is_business_hours():
    print("We're open! Call us now.")
else:
    print("We're closed. Leave a message.")
```

### Time-Appropriate Greeting

```python
greeting = ls.get_greeting()
# "Good morning" / "Good afternoon" / "Good evening"
```

---

## User Location Object

```python
@dataclass
class UserLocation:
    timezone_id: str          # "Australia/Adelaide"
    utc_offset_hours: float   # 9.5
    is_dst: bool              # True during daylight saving
    state: Optional[str]      # "SA"
    postcode: Optional[str]   # "5000"
    coordinates: Optional[Coordinates]  # (lat, lon)
    address: Optional[Address]
    detection_method: str     # "state" / "postcode" / "coordinates"
```

---

## Integration Examples

### Family Law Chatbot

```python
from agentic_brain.location import LocationService
from agentic_brain.plugins.address_validation import AddressValidationPlugin

class FamilyLawBot:
    def __init__(self):
        self.location = LocationService()
        self.address_plugin = AddressValidationPlugin()
    
    def find_local_help(self, user_state: str) -> str:
        self.location.set_location_from_state(user_state)
        
        greeting = self.location.get_greeting()
        local_time = self.location.format_time_for_user(
            self.location.get_local_time()
        )
        
        return f"{greeting}! It's {local_time} in {user_state}. " \
               f"Let me find services near you..."
```

### Customer Service Bot

```python
class CustomerServiceBot:
    def __init__(self):
        self.location = LocationService()
    
    def estimate_delivery(self, customer_postcode: str, warehouse_coords: tuple) -> str:
        self.location.set_location_from_postcode(customer_postcode)
        
        if self.location.current_location:
            customer_state = self.location.current_location.state
            
            # Estimate based on state
            if customer_state in ["NSW", "VIC"]:
                return "Estimated delivery: 1-2 business days"
            elif customer_state in ["QLD", "SA"]:
                return "Estimated delivery: 2-3 business days"
            else:
                return "Estimated delivery: 3-5 business days"
```

---

## Australian Timezone Reference

### Daylight Saving Time

DST applies to:
- ✅ NSW, VIC, SA, TAS, ACT

DST does NOT apply to:
- ❌ QLD, WA, NT

**DST Period:** First Sunday in October → First Sunday in April

### Timezone IDs

```python
STATE_TIMEZONES = {
    "NSW": "Australia/Sydney",
    "VIC": "Australia/Melbourne",
    "QLD": "Australia/Brisbane",
    "SA": "Australia/Adelaide",
    "WA": "Australia/Perth",
    "TAS": "Australia/Hobart",
    "NT": "Australia/Darwin",
    "ACT": "Australia/Sydney",  # ACT uses Sydney timezone
}
```

---

## Privacy Considerations

The Location Services module is designed to be privacy-respecting:

1. **No external API calls** - All geolocation is done locally
2. **No IP geolocation** - Location must be explicitly set
3. **No tracking** - Location is not stored permanently
4. **User control** - User provides their own location data

For applications requiring IP-based geolocation or GPS access, integrate with appropriate browser/mobile APIs and feed the data into this module.

---

## API Reference

### LocationService

| Method | Description | Returns |
|--------|-------------|---------|
| `set_location_from_state(state)` | Set location from AU state code | `UserLocation` |
| `set_location_from_postcode(postcode)` | Set location from postcode | `UserLocation` |
| `set_location_from_coordinates(lat, lon)` | Set location from GPS | `UserLocation` |
| `get_local_time()` | Get current local time | `datetime` |
| `get_timezone_abbrev()` | Get timezone abbreviation | `str` |
| `format_time_for_user(dt)` | Format datetime nicely | `str` |
| `calculate_distance_km(lat1, lon1, lat2, lon2)` | Calculate distance | `float` |
| `filter_services_by_distance(services, max_km)` | Filter nearby services | `List` |
| `filter_services_by_state(services, state)` | Filter by state | `List` |
| `is_business_hours()` | Check if 9am-5pm weekday | `bool` |
| `get_greeting()` | Time-appropriate greeting | `str` |
| `format_location_context()` | Full context string | `str` |

### Data Classes

```python
@dataclass
class Coordinates:
    latitude: float
    longitude: float

@dataclass
class Address:
    street: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: str = "Australia"

@dataclass
class UserLocation:
    timezone_id: str
    utc_offset_hours: float
    is_dst: bool
    state: Optional[str]
    postcode: Optional[str]
    coordinates: Optional[Coordinates]
    address: Optional[Address]
    detection_method: str
```
