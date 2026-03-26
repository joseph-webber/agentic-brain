# Contributing Regional Voice Data 🌍

Agentic Brain supports regional voice expressions to make the AI assistant sound more natural and local.

## 🇦🇺 Australian Regions (Included)

Australian regional data is maintained in the repository:
- Adelaide (South Australia)
- Melbourne (Victoria)
- Sydney (New South Wales)
- Brisbane (Queensland)
- Perth (Western Australia)
- Darwin (Northern Territory)
- Hobart (Tasmania)
- Canberra (ACT)

These are pre-configured and ready to use:
```bash
agentic voice region adelaide
```

## 🌏 International Regions

We welcome contributions from around the world!

### Option 1: Save Locally (Private)

Store your regional data on your own disk:
```bash
# Create your region
agentic region create --city "London" --country "UK" --timezone "Europe/London"

# Add expressions
agentic region add "great" "brilliant"
agentic region add "very" "quite"
agentic region add "thank you" "cheers"

# Add local knowledge
agentic region knowledge "coffee" "Flat white with oat milk"
agentic region knowledge "greeting" "Alright mate?"
```

Your data is stored in `~/.agentic-brain/regions/` and never uploaded.

### Option 2: Create a Pull Request

Share your region with the community!

#### Step 1: Fork the Repository
```bash
git clone https://github.com/YOUR_USERNAME/agentic-brain.git
cd agentic-brain
```

#### Step 2: Add Your Region
Edit `src/agentic_brain/voice/international_regions.py`:

```python
INTERNATIONAL_REGIONS = {
    # Your contribution
    "london": RegionalProfile(
        city="London",
        country="United Kingdom",
        state="England",
        timezone="Europe/London",
        coordinates=(51.5074, -0.1278),  # GPS coordinates
        expressions={
            "great": "brilliant",
            "very": "quite",
            "good": "lovely",
            "thank you": "cheers",
            "hello": "hiya",
            "friend": "mate",
        },
        greetings=[
            "Hiya!",
            "Alright?",
            "How do you do?",
            "Good morning!",
        ],
        farewells=[
            "Cheers!",
            "Ta-ra!",
            "See you later!",
            "Cheerio!",
        ],
        local_knowledge={
            "transport": "Mind the gap on the Tube",
            "weather": "Always bring a brolly",
            "food": "Fish and chips, Sunday roast",
        },
    ),
}
```

#### Step 3: Add Tests
Create a test for your region:
```python
def test_london_expressions():
    rv = get_regional_voice()
    rv.set_region("london")
    result = rv.regionalize("That's very great, thank you!")
    assert "brilliant" in result or "quite" in result
```

#### Step 4: Create the Pull Request
```bash
git checkout -b feat/voice-london-region
git add .
git commit -m "feat(voice): Add London, UK regional data"
git push origin feat/voice-london-region
```

Then create a PR on GitHub with:
- Title: `feat(voice): Add [City], [Country] regional data`
- Description: Include why this region is useful

## ✅ PR Requirements

Your contribution MUST include:

| Requirement | Description |
|-------------|-------------|
| City name | Official city name |
| Country | Full country name |
| Timezone | IANA timezone (e.g., "Europe/London") |
| GPS coordinates | Latitude and longitude |
| 5+ expressions | Common regional expressions |
| 2+ greetings | Regional greetings |
| 2+ farewells | Regional farewells |
| Tests | At least one test case |

## ⚠️ Content Guidelines

All contributions must be:
- ✅ Professional language only
- ✅ Culturally respectful
- ✅ Accurate regional expressions
- ✅ Family-friendly
- ❌ No offensive content
- ❌ No political statements
- ❌ No religious content
- ❌ No stereotypes

## 👤 Review Process

1. **Joseph Webber** reviews all regional PRs
2. Regions are tested for accuracy
3. Content is reviewed for appropriateness
4. If approved, merged into main branch
5. Available in next release

## 📍 Supported Regions

### Current International Regions
- 🇬🇧 United Kingdom (London)
- 🇮🇪 Ireland (Dublin)
- 🇺🇸 United States (California, New York)
- 🇨🇦 Canada (Toronto, Vancouver)
- 🇳🇿 New Zealand (Auckland, Wellington)

### Wanted Contributions
We'd love contributions for:
- 🇮🇳 India (Mumbai, Delhi, Bangalore)
- 🇸🇬 Singapore
- 🇭🇰 Hong Kong
- 🇯🇵 Japan (Tokyo, Osaka)
- 🇰🇷 South Korea (Seoul)
- 🇩🇪 Germany (Berlin, Munich)
- 🇫🇷 France (Paris)
- 🇪🇸 Spain (Madrid, Barcelona)
- 🇧🇷 Brazil (São Paulo, Rio)
- And many more!

## 🎉 Thank You!

Your contributions help make Agentic Brain feel more natural for users worldwide!

---

**Questions?** Open an issue on GitHub or contact the maintainers.

**License:** Apache 2.0 - Your contributions are licensed under the same terms.
