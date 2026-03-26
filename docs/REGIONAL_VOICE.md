# Regional Voice Intelligence

**Location-aware voice system that adapts to regional language differences**

Joseph lives in Adelaide, South Australia. The voice system knows Adelaide expressions like "heaps good", "bottle-o", and "arvo"!

## Features

### 🌏 Location Awareness
- Automatically detects location from system settings
- Defaults to Adelaide (Joseph's location)
- Easy switching when traveling

### 🗣️ Regional Expressions
- Converts standard English to regional slang
- Adelaide: "very" → "heaps", "bottle shop" → "bottle-o", "afternoon" → "arvo"
- Melbourne: "very" → "bloody", "great" → "ripper"
- Case-insensitive, whole-word matching

### 📚 Local Knowledge
- Stores location-specific information
- Adelaide: Coffee culture, AFL teams, wine regions, beaches
- Helps visitors understand local context

### 🎓 Learning System
- Can learn new regional expressions
- Add custom local knowledge
- Persists across sessions

## Installation

The regional voice module is part of the agentic-brain package:

```bash
cd /Users/joe/brain/agentic-brain
pip install -e .
```

## Usage

### CLI Commands

```bash
# Show current location
ab voice location

# Set location to Adelaide
ab voice location adelaide

# List all regions
ab voice regions

# Show regional expressions
ab voice expressions

# Show local knowledge
ab voice knowledge

# Auto-detect location
ab voice detect

# Convert text to regional
ab voice regionalize "That's very great! Thank you!"
ab voice regionalize "text" --speak  # Speak it too
```

### Python API

```python
from agentic_brain.voice.regional import get_regional_voice

# Get regional voice instance
rv = get_regional_voice()

# Regionalize text
text = "That's very great! Thank you!"
regional = rv.regionalize(text)
# "That's heaps heaps tops! cheers!"

# Get greeting/farewell
greeting = rv.get_greeting()  # "G'day mate!"
farewell = rv.get_farewell()  # "See ya later!"

# Get local knowledge
coffee = rv.get_local_knowledge("coffee_order")
# "Adelaide loves their flat whites and long blacks"

# Learn new expressions
rv.add_expression("friend", "mate")
rv.add_local_knowledge("pub", "The Adelaide Casino")

# Change location
rv.save_location("melbourne")
rv._load_location()
```

### Integration with Voice System

The regional voice system integrates automatically with `speak()`:

```python
from agentic_brain.audio import speak

# Automatically regionalizes
speak("That's very great!")  # Speaks "That's heaps heaps tops!"

# Disable regionalization if needed
speak("Standard text", regionalize=False)
```

## Available Regions

### Australia 🇦🇺
- **adelaide** - Adelaide, South Australia
  - Expressions: heaps good, bottle-o, arvo, servo
  - Knowledge: AFL (Crows/Power), Barossa Valley wines, Glenelg beach
- **melbourne** - Melbourne, Victoria
  - Expressions: ripper, bloody, top notch
  - Knowledge: AFL mad, coffee snobs, four seasons in one day
- **sydney** - Sydney, New South Wales
  - Expressions: sick, fully, choice
  - Knowledge: Bondi Beach, Harbour Bridge
- **queensland** - Brisbane, Queensland
  - Expressions: bonzer, sweet as
  - Knowledge: NRL, Gold Coast beaches
- **perth** - Perth, Western Australia
  - Expressions: tops, grouse
  - Knowledge: Cottesloe Beach, AFL (Eagles/Dockers)

### International
- **uk_london** - London, England 🇬🇧
  - Expressions: brilliant, lovely, cheers
- **us_california** - San Francisco, California 🇺🇸
  - Expressions: awesome, cool, rad
- **ireland** - Dublin, Ireland 🇮🇪
  - Expressions: grand, fierce, lovely

## Regional Expressions

### Adelaide-Specific

| Standard | Adelaide |
|----------|----------|
| very | heaps |
| great | heaps good |
| good | tops |
| thank you | cheers |
| bottle shop | bottle-o |
| service station | servo |
| afternoon | arvo |
| breakfast | brekky |
| barbecue | barbie |
| definitely | for sure |
| delicious | bloody lovely |
| excellent | ripper |
| tired | stuffed |
| broken | cactus |
| genuine | fair dinkum |

### Examples

```python
# Standard → Adelaide
"That's very great!" → "That's heaps heaps tops!"
"Let's go to the bottle shop this afternoon" → "Let's go to the bottle-o this arvo"
"Thank you! That's definitely good" → "cheers! That's for sure tops"
"This breakfast barbecue is delicious" → "This brekky barbie is bloody lovely"
```

## Local Knowledge - Adelaide

### Coffee Culture ☕
Adelaide loves their flat whites and long blacks

### Football 🏈
AFL - Go Crows or Power! (Never mention both together though)

### Wine Regions 🍷
Barossa Valley, McLaren Vale, Adelaide Hills - world class wines

### Beaches 🏖️
Glenelg, Henley Beach, Brighton, Semaphore

### Shopping 🛍️
Rundle Mall, Central Market (best fresh produce)

### Adelaide Hills 🏔️
Mount Lofty, Adelaide Hills, Cleland Wildlife Park

### Events 🎭
Adelaide Fringe (huge arts festival), WOMADelaide, Tour Down Under (cycling)

### Food 🍴
Pie floater (pie in pea soup), fritz (devon), farmers union iced coffee

### Accent 🗣️
South Australian accent is considered the 'clearest' Australian accent

### Nickname 🏙️
City of Churches, Festival State

### Population 👥
Around 1.4 million - small and friendly

### Weather ☀️
Mediterranean climate, dry summers, mild winters

## Configuration

Location is stored in `~/.agentic-brain/location.json`:

```json
{
  "region": "adelaide"
}
```

Custom profiles are saved in the same file:

```json
{
  "region": "custom",
  "custom_profile": {
    "country": "Australia",
    "state": "South Australia",
    "city": "Adelaide",
    "timezone": "Australia/Adelaide",
    "expressions": {
      "great": "heaps good",
      "friend": "mate"
    },
    "greetings": ["G'day!"],
    "farewells": ["See ya!"],
    "local_knowledge": {}
  }
}
```

## Testing

Run the comprehensive test suite:

```bash
cd /Users/joe/brain/agentic-brain
python3 -m pytest tests/test_regional_voice.py -v
```

Run the demo:

```bash
python3 examples/regional_voice_demo.py
```

## Future Enhancements

### Web Learning
Use LLM to research new regional expressions from web:

```python
async def learn_from_web(region: str):
    """Research regional expressions online"""
    from agentic_brain.router import get_router
    router = get_router()
    
    prompt = f"""Research common expressions and slang used in {region}.
    Return as JSON: {{"expressions": {{"standard": "regional"}}}}"""
    
    result = await router.route(prompt)
    # Parse and store
```

### Voice-Specific Accents
Different voices could have different regional profiles:
- Karen speaks Adelaide expressions
- Moira speaks Irish expressions
- Kyoko speaks Japanese-accented English

### Context-Aware Regionalization
Adapt based on who Joseph is talking to:
- Formal contexts: Less slang
- Casual contexts: More regional expressions
- International: Standard English

## Architecture

```
regional.py
├── RegionalProfile (dataclass)
│   ├── country, state, city
│   ├── expressions: Dict[standard, regional]
│   ├── greetings, farewells
│   └── local_knowledge
│
├── RegionalVoice (class)
│   ├── _load_location()
│   ├── regionalize(text) → Apply expressions
│   ├── get_greeting() → Random greeting
│   ├── get_farewell() → Random farewell
│   ├── get_local_knowledge(topic) → Info
│   ├── add_expression(standard, regional)
│   └── add_local_knowledge(topic, info)
│
├── AUSTRALIAN_REGIONS: Dict[key, RegionalProfile]
├── INTERNATIONAL_REGIONS: Dict[key, RegionalProfile]
│
└── Helper functions
    ├── detect_location() → Auto-detect
    ├── get_available_regions()
    ├── list_regions()
    └── get_regional_voice() → Singleton
```

## License

Apache-2.0 - Part of Joseph's Agentic Brain

## Credits

Created for Joseph Webber, Adelaide, South Australia 🇦🇺

Built with ❤️ to make the brain sound local!
