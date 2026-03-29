# Contributing Regional Voices and Expressions

**Help make Agentic Brain speak like a local everywhere!**

## 🌍 What Are Regional Voices?

Regional voices add authentic local expressions and slang to the brain's speech. This makes interactions feel natural and culturally appropriate wherever users travel.

**Current Coverage:**
- 🇦🇺 Australia (Adelaide, Melbourne, Sydney, Brisbane, Perth, Darwin, Hobart, Canberra)
- 🇯🇵 Japan (via Kyoko)
- 🇨🇳 China (via Tingting)
- 🇰🇷 South Korea (via Yuna)
- 🇻🇳 Vietnam (via Linh)
- 🇵🇱 Poland (via Zosia)
- 🇮🇪 Ireland (via Moira)

**We need YOUR help to expand this!**

---

## 🎯 How to Contribute a New Region

### Step 1: Pick Your Region

Choose a region you know well! This could be:
- Your hometown/city
- A country where you've lived
- A place whose dialect/slang you're fluent in

**Requirements:**
- Must be a native speaker or have deep cultural knowledge
- Must understand local slang, idioms, and expressions
- Must know what tourists/visitors commonly say wrong

### Step 2: Create Your Region File

Create a new Python file in `src/agentic_brain/voice/regions/` following this structure:

```python
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors <agentic-brain@proton.me>

"""
[CITY/REGION NAME] Regional Expressions

Contributed by: [YOUR NAME]
Date: [DATE]
Native Speaker: [Yes/No]
"""

from dataclasses import dataclass
from typing import List, Dict

@dataclass
class [RegionName]Region:
    """Regional expressions for [City/Country]"""
    
    city: str = "[City Name]"
    country: str = "[Country]"
    timezone: str = "[Timezone]"  # e.g., "Europe/London"
    
    # Common expressions (formal → local)
    expressions: Dict[str, List[str]] = None
    
    # Slang terms
    slang: Dict[str, str] = None
    
    # Common tourist mistakes
    tourist_mistakes: Dict[str, str] = None
    
    # Greetings (time-appropriate)
    greetings: Dict[str, List[str]] = None
    
    def __post_init__(self):
        if self.expressions is None:
            self.expressions = {
                # Examples:
                "very good": ["brilliant", "ace", "spot on"],
                "thank you": ["cheers", "ta", "thanks mate"],
                "hello": ["g'day", "hiya", "alright"],
                # Add 20-30 common expressions!
            }
        
        if self.slang is None:
            self.slang = {
                # Examples:
                "friend": "mate",
                "great": "bonzer",
                "tired": "knackered",
                # Add 15-20 slang terms!
            }
        
        if self.tourist_mistakes is None:
            self.tourist_mistakes = {
                # What tourists say WRONG → CORRECT local version
                "Where is the underground?": "Where's the tube?",
                "Can I get a coffee to go?": "Can I get a coffee takeaway?",
                # Add common mistakes!
            }
        
        if self.greetings is None:
            self.greetings = {
                "morning": ["Morning!", "G'day!", "Top of the morning!"],
                "afternoon": ["Afternoon!", "How's it going?"],
                "evening": ["Evening!", "Alright?", "How are ya?"],
                "night": ["Night!", "Sleep well!", "See ya tomorrow!"],
            }


# Register the region
REGION = [RegionName]Region()
```

### Step 3: Real-World Examples

**GOOD Examples** (natural, authentic):
```python
expressions = {
    "very good": ["absolutely brilliant", "smashing", "top drawer"],
    "expensive": ["pricey", "costs a bomb", "daylight robbery"],
    "food": ["scran", "nosh", "grub"],
}
```

**BAD Examples** (stereotypes, offensive):
```python
expressions = {
    "very good": ["super duper"],  # ❌ Too childish
    "hello": ["pip pip cheerio"],  # ❌ Offensive stereotype
    "drunk": ["pissed as a newt"],  # ❌ Inappropriate slang
}
```

### Step 4: Cultural Notes

Add a `CULTURAL_NOTES.md` file:

```markdown
# [Region Name] Cultural Notes

## DO's:
- ✅ Use these phrases in casual settings
- ✅ These greetings are appropriate any time
- ✅ This slang is understood by all ages

## DON'Ts:
- ❌ Don't use [phrase] with elders
- ❌ Avoid [term] in formal settings
- ❌ [Expression] might offend in [context]

## Context:
- 🏙️ Urban vs Rural: [differences]
- 👴 Generational: [what older people say vs younger]
- 🎓 Formality: [when to use formal vs casual]
```

### Step 5: Test Your Region

Create tests in `tests/test_[region]_regions.py`:

```python
import pytest
from agentic_brain.voice.regions.[your_file] import REGION

class TestYourRegion:
    """Tests for [Region] regional expressions"""
    
    def test_region_metadata(self):
        """Region has required metadata"""
        assert REGION.city is not None
        assert REGION.country is not None
        assert len(REGION.expressions) > 10
    
    def test_expressions_authentic(self):
        """Expressions are real local phrases"""
        # Test a few key expressions
        assert "very good" in REGION.expressions
        assert len(REGION.expressions["very good"]) >= 2
    
    def test_no_offensive_terms(self):
        """No offensive or inappropriate terms"""
        # Check slang doesn't contain offensive words
        offensive = ["badword1", "badword2"]  # Add known offensive terms
        for term in REGION.slang.values():
            assert term.lower() not in offensive
```

---

## 📋 Checklist Before Submitting

- [ ] Native speaker or deep cultural knowledge
- [ ] At least 20 expressions defined
- [ ] At least 15 slang terms
- [ ] Tourist mistakes section complete
- [ ] Cultural notes documented
- [ ] No offensive or inappropriate terms
- [ ] Tests written and passing
- [ ] Example usage documented
- [ ] Apache 2.0 license header added

---

## 🎓 Region Complexity Levels

### Level 1: Basic (Good for First Contribution)
- One city/region
- 20-30 expressions
- Common tourist mistakes
- Time-appropriate greetings

**Example**: Dublin, Ireland

### Level 2: Intermediate
- Multiple cities in same country
- Regional differences documented
- Formality levels (casual vs formal)
- Generational differences

**Example**: London vs Manchester (both England, different slang)

### Level 3: Advanced
- Country-wide coverage
- Dialect variations
- Historical context
- Cross-cultural notes

**Example**: All of Australia (8 cities, different expressions)

---

## 🌏 Priority Regions (the user's Travel List)

**HIGH PRIORITY** (popular destinations):
- 🇮🇹 Italy (Venice, Rome, Florence)
- 🇹🇭 Thailand (Bangkok, Chiang Mai, Phuket)
- 🇮🇩 Indonesia (Jakarta, Bali, Java)
- 🇭🇰 Hong Kong (Cantonese expressions)
- 🇯🇵 Japan (Tokyo, Kyoto, Osaka) - needs expansion
- 🇨🇳 China (Beijing, Shanghai, Guangzhou) - needs expansion

**MEDIUM PRIORITY**:
- 🇬🇧 UK (London, Manchester, Scotland)
- 🇺🇸 USA (New York, California, Texas)
- 🇫🇷 France (Paris, Nice, Lyon)
- 🇩🇪 Germany (Berlin, Munich, Hamburg)
- 🇪🇸 Spain (Madrid, Barcelona, Valencia)

**LOW PRIORITY** (Nice to have):
- 🇧🇷 Brazil (Portuguese)
- 🇲🇽 Mexico (Spanish)
- 🇦🇪 UAE (Arabic/English)
- 🇿🇦 South Africa (English/Afrikaans)

---

## 💡 Tips for Great Contributions

### 1. Think Like a Local
Don't just translate - capture the VIBE of your region.

**Example**: 
- ❌ "Hello" → "Hello" (boring!)
- ✅ "Hello" → "Alright mate?" (authentic Melbourne)

### 2. Context Matters
Same phrase can mean different things in different contexts.

**Example**:
- "How ya going?" in Adelaide = "How are you?"
- "How ya going?" in Sydney = "What are you up to?"

### 3. Avoid Stereotypes
Real people don't talk like TV characters.

**Example**:
- ❌ "Crikey!" (nobody says this anymore!)
- ✅ "No worries" (actually used daily)

### 4. Test with Locals
Show your contribution to friends/family from that region. Do they cringe or smile?

---

## 🔍 Review Process

1. **Submit PR** with your region file
2. **Native Speaker Review** - We'll find a native speaker to validate
3. **Cultural Sensitivity Check** - Ensure no offensive content
4. **CI Tests** - Automated tests must pass
5. **Merge!** - Your region goes live!

---

## 🏆 Recognition

Contributors will be:
- Listed in `CONTRIBUTORS.md`
- Credited in region file headers
- Mentioned in release notes
- Eligible for "Regional Expert" badge

---

## 📚 Resources

- [Australian Slang Dictionary](https://www.koalajoey.com/slang/)
- [British vs American English](https://www.oxfordinternationalenglish.com/differences-in-british-and-american-english/)
- [Colloquial Language Research](https://www.ethnologue.com/)

---

## ❓ Questions?

- **Discord**: [Join our server](https://discord.gg/agentic-brain)
- **Email**: agentic-brain@proton.me
- **GitHub Issues**: Tag with `regional-voices`

---

## 🙏 Thank You!

By contributing regional expressions, you're helping users:
- Feel at home anywhere in the world
- Communicate naturally with locals
- Avoid embarrassing tourist mistakes
- Build deeper cultural connections

**Every contribution makes the brain more human. Thank you!**

---

*Last updated: 2026-03-22*
*Maintained by: Agentic Brain Contributors & the Agentic Brain community*
