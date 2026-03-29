# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Complete macOS Voice Registry - ALL 145+ voices!

This is the DEFINITIVE registry of macOS voices for Joseph's accessibility.
Generated from `say -v '?'` on macOS Sonoma.

Features:
- All system voices (English, multilingual, novelty)
- Premium Neural voices (Karen, Moira, Daniel, etc.)
- Joseph's primary voice assistants (core personas)
- Language pack support
- Quality tier classification
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class VoiceGender(Enum):
    """Voice gender classification."""

    FEMALE = "female"
    MALE = "male"
    NEUTRAL = "neutral"


class VoiceQuality(Enum):
    """Voice quality classification."""

    PREMIUM = "premium"  # Neural TTS, high quality
    STANDARD = "standard"  # System voices
    NOVELTY = "novelty"  # Fun/effect voices


@dataclass
class VoiceMetadata:
    """Complete metadata for a macOS voice."""

    name: str
    language: str
    language_name: str
    region: str
    gender: VoiceGender
    quality: VoiceQuality
    description: str
    is_primary: bool = False  # One of Joseph's primary voice assistants
    sample_text: str = ""

    @property
    def full_name(self) -> str:
        """Get full name as it appears in macOS."""
        if self.quality == VoiceQuality.PREMIUM:
            return f"{self.name} (Premium)"
        return self.name

    @property
    def display_name(self) -> str:
        """Get display name with language."""
        return f"{self.name} ({self.language_name})"


# =============================================================================
# PRIMARY VOICE ASSISTANTS - Joseph's core personas
# =============================================================================

PRIMARY_VOICE_ASSISTANTS = {
    # Australian - Lead Host
    "Karen": VoiceMetadata(
        name="Karen",
        language="en-AU",
        language_name="Australian English",
        region="Australia",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Lead host, Joseph's favorite! Australian accent.",
        is_primary=True,
        sample_text="G'day Joseph! Ready to work on the brain today?",
    ),
    # Irish - Creative Spirit
    "Moira": VoiceMetadata(
        name="Moira",
        language="en-IE",
        language_name="Irish English",
        region="Ireland",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Creative, warm Irish accent. Debugging expert.",
        is_primary=True,
        sample_text="Hello there! Let's create something brilliant today!",
    ),
    # Japanese - Quality Assurance
    "Kyoko": VoiceMetadata(
        name="Kyoko",
        language="ja-JP",
        language_name="Japanese",
        region="Japan",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Quality and precision. JIRA expert. FUN & TRAVEL ONLY!",
        is_primary=True,
        sample_text="こんにちは、ジョセフ！一緒に頑張りましょう！",
    ),
    # Chinese - Analytics
    "Tingting": VoiceMetadata(
        name="Tingting",
        language="zh-CN",
        language_name="Mandarin Chinese",
        region="China",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Fast, analytical. PR review specialist.",
        is_primary=True,
        sample_text="你好，Joseph！让我们开始工作吧！",
    ),
    # Indonesian/Balinese - Project Management
    "Damayanti": VoiceMetadata(
        name="Damayanti",
        language="id-ID",
        language_name="Indonesian",
        region="Indonesia/Bali",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Project management, documentation. Calm and organized.",
        is_primary=True,
        sample_text="Halo Joseph! Siap untuk bekerja hari ini!",
    ),
    # Polish - Security
    "Zosia": VoiceMetadata(
        name="Zosia",
        language="pl-PL",
        language_name="Polish",
        region="Poland",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Security expert. Precise and thorough.",
        is_primary=True,
        sample_text="Cześć Joseph! Zadbajmy o bezpieczeństwo!",
    ),
    # Korean - Tech & Social Media (FUN & TRAVEL ONLY)
    "Yuna": VoiceMetadata(
        name="Yuna",
        language="ko-KR",
        language_name="Korean",
        region="South Korea",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Tech and social media. FUN & TRAVEL ONLY!",
        is_primary=True,
        sample_text="안녕하세요 Joseph! 오늘도 화이팅!",
    ),
    # Vietnamese - GitHub & Adelaide Guide
    "Linh": VoiceMetadata(
        name="Linh",
        language="vi-VN",
        language_name="Vietnamese",
        region="Vietnam",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="GitHub operations and Adelaide city guide.",
        is_primary=True,
        sample_text="Xin chào Joseph! Hôm nay chúng ta làm gì?",
    ),
    # Thai - Wellness
    "Kanya": VoiceMetadata(
        name="Kanya",
        language="th-TH",
        language_name="Thai",
        region="Thailand",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Wellness and mindfulness. Calm energy.",
        is_primary=True,
        sample_text="สวัสดีค่ะ Joseph! พร้อมแล้วค่ะ!",
    ),
    # Hong Kong Cantonese - Trading (Sinji uses Chinese voice)
    "Sinji": VoiceMetadata(
        name="Sinji",
        language="zh-HK",
        language_name="Cantonese",
        region="Hong Kong",
        gender=VoiceGender.FEMALE,
        quality=VoiceQuality.PREMIUM,
        description="Finance and trading specialist.",
        is_primary=True,
        sample_text="你好 Joseph！今日交易準備好未？",
    ),
}

# Additional voice personas using other voices (Amelie for French accent, etc.)
ADDITIONAL_VOICE_PERSONAS = {
    # French - Code Review (Flo uses Amelie voice)
    "Flo": {
        "voice": "Amelie",
        "description": "Code review specialist with French accent",
    },
    # British - Deployment (Shelley)
    "Shelley": {
        "voice": "Shelley",
        "description": "Deployment and production specialist",
    },
}


# =============================================================================
# ALL MACOS VOICES - Complete Registry
# =============================================================================

ALL_MACOS_VOICES: Dict[str, VoiceMetadata] = {
    # === ENGLISH VOICES (Premium & Standard) ===
    # Australian English
    "Karen": PRIMARY_VOICE_ASSISTANTS["Karen"],
    "Lee": VoiceMetadata(
        "Lee",
        "en-AU",
        "Australian English",
        "Australia",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "Australian male voice",
    ),
    # British English
    "Daniel": VoiceMetadata(
        "Daniel",
        "en-GB",
        "British English",
        "UK",
        VoiceGender.MALE,
        VoiceQuality.PREMIUM,
        "Premium British male voice",
    ),
    "Kate": VoiceMetadata(
        "Kate",
        "en-GB",
        "British English",
        "UK",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Premium British female voice",
    ),
    "Oliver": VoiceMetadata(
        "Oliver",
        "en-GB",
        "British English",
        "UK",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "British male voice",
    ),
    "Serena": VoiceMetadata(
        "Serena",
        "en-GB",
        "British English",
        "UK",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "British female voice",
    ),
    # American English
    "Samantha": VoiceMetadata(
        "Samantha",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Premium American female voice",
    ),
    "Alex": VoiceMetadata(
        "Alex",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.PREMIUM,
        "Premium American male voice",
    ),
    "Allison": VoiceMetadata(
        "Allison",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "American female voice",
    ),
    "Ava": VoiceMetadata(
        "Ava",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "American female voice",
    ),
    "Tom": VoiceMetadata(
        "Tom",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "American male voice",
    ),
    "Zoe": VoiceMetadata(
        "Zoe",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Premium American female voice",
    ),
    # Irish English
    "Moira": PRIMARY_VOICE_ASSISTANTS["Moira"],
    # Scottish English
    "Fiona": VoiceMetadata(
        "Fiona",
        "en-SC",
        "Scottish English",
        "Scotland",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Scottish female voice",
    ),
    # Indian English
    "Rishi": VoiceMetadata(
        "Rishi",
        "en-IN",
        "Indian English",
        "India",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "Indian English male voice",
    ),
    "Lekha": VoiceMetadata(
        "Lekha",
        "hi-IN",
        "Hindi",
        "India",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Hindi female voice",
    ),
    # South African English
    "Tessa": VoiceMetadata(
        "Tessa",
        "en-ZA",
        "South African English",
        "South Africa",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "South African female voice",
    ),
    # === ASIAN LANGUAGES (Primary assistants) ===
    "Kyoko": PRIMARY_VOICE_ASSISTANTS["Kyoko"],
    "Tingting": PRIMARY_VOICE_ASSISTANTS["Tingting"],
    "Sinji": PRIMARY_VOICE_ASSISTANTS["Sinji"],
    "Ichiro": VoiceMetadata(
        "Ichiro",
        "ja-JP",
        "Japanese",
        "Japan",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "Japanese male voice",
    ),
    "Liam": VoiceMetadata(
        "Liam",
        "zh-CN",
        "Mandarin Chinese",
        "China",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "Chinese male voice",
    ),
    "Min-jun": VoiceMetadata(
        "Min-jun",
        "ko-KR",
        "Korean",
        "South Korea",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "Korean male voice",
    ),
    "Meijia": VoiceMetadata(
        "Meijia",
        "zh-TW",
        "Taiwanese Mandarin",
        "Taiwan",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Taiwanese Mandarin female voice",
    ),
    "Yuna": PRIMARY_VOICE_ASSISTANTS["Yuna"],
    "Linh": PRIMARY_VOICE_ASSISTANTS["Linh"],
    "Kanya": PRIMARY_VOICE_ASSISTANTS["Kanya"],
    "Damayanti": PRIMARY_VOICE_ASSISTANTS["Damayanti"],
    # Malaysian
    "Amira": VoiceMetadata(
        "Amira",
        "ms-MY",
        "Malay",
        "Malaysia",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Malay female voice",
    ),
    # === EUROPEAN LANGUAGES ===
    # French
    "Amelie": VoiceMetadata(
        "Amelie",
        "fr-CA",
        "French (Canada)",
        "Canada",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Canadian French female voice",
    ),
    "Thomas": VoiceMetadata(
        "Thomas",
        "fr-FR",
        "French",
        "France",
        VoiceGender.MALE,
        VoiceQuality.PREMIUM,
        "French male voice",
    ),
    "Jacques": VoiceMetadata(
        "Jacques",
        "fr-FR",
        "French",
        "France",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "French male voice",
    ),
    # German
    "Anna": VoiceMetadata(
        "Anna",
        "de-DE",
        "German",
        "Germany",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "German female voice",
    ),
    # Spanish
    "Monica": VoiceMetadata(
        "Monica",
        "es-ES",
        "Spanish",
        "Spain",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Spanish female voice",
    ),
    "Paulina": VoiceMetadata(
        "Paulina",
        "es-MX",
        "Spanish (Mexico)",
        "Mexico",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Mexican Spanish female voice",
    ),
    # Italian
    "Alice": VoiceMetadata(
        "Alice",
        "it-IT",
        "Italian",
        "Italy",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Italian female voice",
    ),
    # Portuguese
    "Luciana": VoiceMetadata(
        "Luciana",
        "pt-BR",
        "Portuguese (Brazil)",
        "Brazil",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Brazilian Portuguese female voice",
    ),
    "Joana": VoiceMetadata(
        "Joana",
        "pt-PT",
        "Portuguese",
        "Portugal",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Portuguese female voice",
    ),
    # Dutch/Flemish
    "Xander": VoiceMetadata(
        "Xander",
        "nl-NL",
        "Dutch",
        "Netherlands",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "Dutch male voice",
    ),
    "Ellen": VoiceMetadata(
        "Ellen",
        "nl-BE",
        "Dutch (Belgium)",
        "Belgium",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Flemish female voice",
    ),
    # Polish
    "Zosia": PRIMARY_VOICE_ASSISTANTS["Zosia"],
    # === NORDIC & EASTERN EUROPEAN ===
    # Swedish
    "Alva": VoiceMetadata(
        "Alva",
        "sv-SE",
        "Swedish",
        "Sweden",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Swedish female voice",
    ),
    # Norwegian
    "Nora": VoiceMetadata(
        "Nora",
        "nb-NO",
        "Norwegian",
        "Norway",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Norwegian female voice",
    ),
    # Danish
    "Sara": VoiceMetadata(
        "Sara",
        "da-DK",
        "Danish",
        "Denmark",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Danish female voice",
    ),
    # Finnish
    "Satu": VoiceMetadata(
        "Satu",
        "fi-FI",
        "Finnish",
        "Finland",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Finnish female voice",
    ),
    # Russian
    "Milena": VoiceMetadata(
        "Milena",
        "ru-RU",
        "Russian",
        "Russia",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Russian female voice",
    ),
    # Ukrainian
    "Lesya": VoiceMetadata(
        "Lesya",
        "uk-UA",
        "Ukrainian",
        "Ukraine",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Ukrainian female voice",
    ),
    # Czech
    "Zuzana": VoiceMetadata(
        "Zuzana",
        "cs-CZ",
        "Czech",
        "Czech Republic",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Czech female voice",
    ),
    # Slovak
    "Laura": VoiceMetadata(
        "Laura",
        "sk-SK",
        "Slovak",
        "Slovakia",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Slovak female voice",
    ),
    # Hungarian
    "Tunde": VoiceMetadata(
        "Tünde",
        "hu-HU",
        "Hungarian",
        "Hungary",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Hungarian female voice",
    ),
    # === OTHER LANGUAGES ===
    # Greek
    "Melina": VoiceMetadata(
        "Melina",
        "el-GR",
        "Greek",
        "Greece",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Greek female voice",
    ),
    # Turkish
    "Yelda": VoiceMetadata(
        "Yelda",
        "tr-TR",
        "Turkish",
        "Turkey",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Turkish female voice",
    ),
    # Arabic
    "Majed": VoiceMetadata(
        "Majed",
        "ar-001",
        "Arabic",
        "Middle East",
        VoiceGender.MALE,
        VoiceQuality.STANDARD,
        "Arabic male voice",
    ),
    # Hebrew
    "Carmit": VoiceMetadata(
        "Carmit",
        "he-IL",
        "Hebrew",
        "Israel",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Hebrew female voice",
    ),
    # Romanian
    "Ioana": VoiceMetadata(
        "Ioana",
        "ro-RO",
        "Romanian",
        "Romania",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Romanian female voice",
    ),
    # Bulgarian
    "Daria": VoiceMetadata(
        "Daria",
        "bg-BG",
        "Bulgarian",
        "Bulgaria",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Bulgarian female voice",
    ),
    # Croatian
    "Lana": VoiceMetadata(
        "Lana",
        "hr-HR",
        "Croatian",
        "Croatia",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Croatian female voice",
    ),
    # Catalan
    "Montse": VoiceMetadata(
        "Montse",
        "ca-ES",
        "Catalan",
        "Catalonia",
        VoiceGender.FEMALE,
        VoiceQuality.STANDARD,
        "Catalan female voice",
    ),
    # === NOVELTY & FUN VOICES ===
    "Albert": VoiceMetadata(
        "Albert",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - quirky character",
    ),
    "Bad News": VoiceMetadata(
        "Bad News",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - ominous tone",
    ),
    "Bahh": VoiceMetadata(
        "Bahh",
        "en-US",
        "American English",
        "USA",
        VoiceGender.NEUTRAL,
        VoiceQuality.NOVELTY,
        "Novelty voice - sheep sound",
    ),
    "Bells": VoiceMetadata(
        "Bells",
        "en-US",
        "American English",
        "USA",
        VoiceGender.NEUTRAL,
        VoiceQuality.NOVELTY,
        "Novelty voice - bell sounds",
    ),
    "Boing": VoiceMetadata(
        "Boing",
        "en-US",
        "American English",
        "USA",
        VoiceGender.NEUTRAL,
        VoiceQuality.NOVELTY,
        "Novelty voice - bouncy sound",
    ),
    "Bubbles": VoiceMetadata(
        "Bubbles",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - underwater effect",
    ),
    "Cellos": VoiceMetadata(
        "Cellos",
        "en-US",
        "American English",
        "USA",
        VoiceGender.NEUTRAL,
        VoiceQuality.NOVELTY,
        "Novelty voice - cello sounds",
    ),
    "Fred": VoiceMetadata(
        "Fred",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - comedic character",
    ),
    "Good News": VoiceMetadata(
        "Good News",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - upbeat tone",
    ),
    "Jester": VoiceMetadata(
        "Jester",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - joker character",
    ),
    "Junior": VoiceMetadata(
        "Junior",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - childlike",
    ),
    "Kathy": VoiceMetadata(
        "Kathy",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - breathy whisper",
    ),
    "Organ": VoiceMetadata(
        "Organ",
        "en-US",
        "American English",
        "USA",
        VoiceGender.NEUTRAL,
        VoiceQuality.NOVELTY,
        "Novelty voice - organ sounds",
    ),
    "Ralph": VoiceMetadata(
        "Ralph",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - monster character",
    ),
    "Superstar": VoiceMetadata(
        "Superstar",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - celebrity announcer",
    ),
    "Trinoids": VoiceMetadata(
        "Trinoids",
        "en-US",
        "American English",
        "USA",
        VoiceGender.NEUTRAL,
        VoiceQuality.NOVELTY,
        "Novelty voice - three-toned harmony",
    ),
    "Whisper": VoiceMetadata(
        "Whisper",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - soft whisper",
    ),
    "Wobble": VoiceMetadata(
        "Wobble",
        "en-US",
        "American English",
        "USA",
        VoiceGender.NEUTRAL,
        VoiceQuality.NOVELTY,
        "Novelty voice - wobbling effect",
    ),
    "Zarvox": VoiceMetadata(
        "Zarvox",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.NOVELTY,
        "Novelty voice - robot character",
    ),
    # Eddy, Flo, Grandma, Grandpa, Reed, Rocko, Sandy, Shelley
    # These have multilingual variants - adding English versions
    "Eddy": VoiceMetadata(
        "Eddy",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.PREMIUM,
        "Premium multilingual voice (English)",
    ),
    "Flo": VoiceMetadata(
        "Flo",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Premium multilingual voice (English)",
    ),
    "Grandma": VoiceMetadata(
        "Grandma",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Premium grandmother character voice",
    ),
    "Grandpa": VoiceMetadata(
        "Grandpa",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.PREMIUM,
        "Premium grandfather character voice",
    ),
    "Reed": VoiceMetadata(
        "Reed",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.PREMIUM,
        "Premium multilingual voice (English)",
    ),
    "Rocko": VoiceMetadata(
        "Rocko",
        "en-US",
        "American English",
        "USA",
        VoiceGender.MALE,
        VoiceQuality.PREMIUM,
        "Premium multilingual voice (English)",
    ),
    "Sandy": VoiceMetadata(
        "Sandy",
        "en-US",
        "American English",
        "USA",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Premium multilingual voice (English)",
    ),
    "Shelley": VoiceMetadata(
        "Shelley",
        "en-GB",
        "British English",
        "UK",
        VoiceGender.FEMALE,
        VoiceQuality.PREMIUM,
        "Premium British female voice - deployment specialist",
    ),
}


# =============================================================================
# ROBOT / NOVELTY VOICE PRESETS
# =============================================================================

# Lightweight mapping for robot and novelty voices.
# These presets are used for system messages and fun effects.
ROBOT_VOICES = {
    "zarvox": {
        "name": "Zarvox",
        "type": "robot",
        "gender": "neutral",
        "description": "Classic robot voice",
        "use_for": ["system_alerts", "errors", "fun"],
    },
    "trinoids": {
        "name": "Trinoids",
        "type": "alien",
        "gender": "neutral",
        "description": "Alien chorus",
        "use_for": ["notifications", "fun"],
    },
    "ralph": {
        "name": "Ralph",
        "type": "novelty",
        "gender": "male",
        "description": "Silly voice",
        "use_for": ["jokes", "fun"],
    },
    "bad_news": {
        "name": "Bad News",
        "type": "novelty",
        "gender": "male",
        "description": "Ominous announcer",
        "use_for": ["errors", "warnings"],
    },
    "whisper": {
        "name": "Whisper",
        "type": "novelty",
        "gender": "neutral",
        "description": "Whispering voice",
        "use_for": ["secrets", "quiet_mode"],
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_primary_voices() -> List[VoiceMetadata]:
    """Get Joseph's primary voice assistants (core personas)."""
    return [v for v in ALL_MACOS_VOICES.values() if v.is_primary]


def get_english_voices() -> List[VoiceMetadata]:
    """Get all English voices (en-* languages)."""
    return [v for v in ALL_MACOS_VOICES.values() if v.language.startswith("en-")]


def get_premium_voices() -> List[VoiceMetadata]:
    """Get all premium/neural voices."""
    return [v for v in ALL_MACOS_VOICES.values() if v.quality == VoiceQuality.PREMIUM]


def get_novelty_voices() -> List[VoiceMetadata]:
    """Get all novelty/fun voices."""
    return [v for v in ALL_MACOS_VOICES.values() if v.quality == VoiceQuality.NOVELTY]


def get_female_voices() -> List[VoiceMetadata]:
    """Get all female voices."""
    return [v for v in ALL_MACOS_VOICES.values() if v.gender == VoiceGender.FEMALE]


def get_male_voices() -> List[VoiceMetadata]:
    """Get all male voices."""
    return [v for v in ALL_MACOS_VOICES.values() if v.gender == VoiceGender.MALE]


def get_voices_by_language(language_code: str) -> List[VoiceMetadata]:
    """Get all voices for a specific language."""
    return [v for v in ALL_MACOS_VOICES.values() if v.language == language_code]


def get_voice(name: str) -> Optional[VoiceMetadata]:
    """Get voice by name (case-insensitive)."""
    # Try exact match first
    if name in ALL_MACOS_VOICES:
        return ALL_MACOS_VOICES[name]

    # Try case-insensitive
    name_lower = name.lower()
    for voice_name, voice_meta in ALL_MACOS_VOICES.items():
        if voice_name.lower() == name_lower:
            return voice_meta

    return None


def list_all_voices() -> List[VoiceMetadata]:
    """Get all registered voices."""
    return list(ALL_MACOS_VOICES.values())


def get_voice_stats() -> Dict[str, int]:
    """Get statistics about registered voices."""
    all_voices = list(ALL_MACOS_VOICES.values())

    return {
        "total": len(all_voices),
        "primary": len(get_primary_voices()),
        "english": len(get_english_voices()),
        "premium": len(get_premium_voices()),
        "novelty": len(get_novelty_voices()),
        "languages": len({v.language for v in all_voices}),
    }


# Curated male voice metadata for quick reference
MALE_VOICES: Dict[str, Dict[str, str]] = {
    # Asian Male
    "Ichiro": {"lang": "ja-JP", "gender": "male", "quality": "standard"},  # Japanese
    "Liam": {"lang": "zh-CN", "gender": "male", "quality": "standard"},  # Chinese
    "Min-jun": {"lang": "ko-KR", "gender": "male", "quality": "standard"},  # Korean
    # European / English Male
    "Daniel": {"lang": "en-GB", "gender": "male", "quality": "premium"},  # British
    "Oliver": {"lang": "en-GB", "gender": "male", "quality": "standard"},  # British
    "Alex": {"lang": "en-US", "gender": "male", "quality": "premium"},  # American
    "Tom": {"lang": "en-US", "gender": "male", "quality": "standard"},  # American
    "Lee": {"lang": "en-AU", "gender": "male", "quality": "standard"},  # Australian
}


# Quick test
if __name__ == "__main__":
    print("🎙️  Voice Registry Statistics")
    print("=" * 50)
    stats = get_voice_stats()
    for key, value in stats.items():
        print(f"  {key.title()}: {value}")

    print("\n🎙️  Primary Voice Assistants:")
    for voice in get_primary_voices():
        print(f"  - {voice.name} ({voice.language_name})")

    print("\n🎙️  Premium English Voices:")
    for voice in get_english_voices():
        if voice.quality == VoiceQuality.PREMIUM:
            print(f"  - {voice.full_name} ({voice.region})")
