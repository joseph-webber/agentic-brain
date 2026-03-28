# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class VoiceQuality(Enum):
    STANDARD = "standard"  # System voices
    PREMIUM = "premium"  # macOS Premium voices
    NEURAL = "neural"  # Cloud neural TTS


@dataclass
class VoiceConfig:
    voice_name: str = os.getenv(
        "AGENTIC_BRAIN_VOICE", "Karen"
    )  # Australian - Joseph's favorite!
    language: str = os.getenv("AGENTIC_BRAIN_LANGUAGE", "en-AU")
    rate: int = int(os.getenv("AGENTIC_BRAIN_RATE", "160"))  # words per minute
    pitch: float = float(os.getenv("AGENTIC_BRAIN_PITCH", "1.0"))
    volume: float = float(os.getenv("AGENTIC_BRAIN_VOLUME", "0.8"))
    provider: str = os.getenv(
        "AGENTIC_BRAIN_VOICE_PROVIDER", "system"
    )  # system, azure, google, aws, elevenlabs
    enabled: bool = (
        os.getenv("AGENTIC_BRAIN_VOICE_ENABLED", "true").lower() == "true"
    )  # False for CI/servers
    fallback_voice: str = "Samantha"
    quality: VoiceQuality = VoiceQuality(
        os.getenv("AGENTIC_BRAIN_VOICE_QUALITY", "premium")
    )
    regional_map: Dict[str, str] = field(default_factory=dict)
    robot_voices: List[str] = field(default_factory=list)


@dataclass
class LanguagePack:
    code: str
    name: str
    native_name: str
    default_voice: str
    fallback_voice: str
    flag: str


# Defined language packs
LANGUAGE_PACKS = {
    "en-AU": LanguagePack(
        "en-AU", "English (Australia)", "Australian", "Karen", "Karen", "🇦🇺"
    ),
    "en-US": LanguagePack(
        "en-US", "English (US)", "American", "Samantha", "Samantha", "🇺🇸"
    ),
    "en-GB": LanguagePack("en-GB", "English (UK)", "British", "Daniel", "Daniel", "🇬🇧"),
    "en-IE": LanguagePack(
        "en-IE", "English (Ireland)", "Irish", "Moira", "Moira", "🇮🇪"
    ),
    "ga-IE": LanguagePack("ga-IE", "Irish (Gaelic)", "Gaeilge", "Moira", "Moira", "🇮🇪"),
    "ja-JP": LanguagePack("ja-JP", "Japanese", "日本語", "Kyoko", "Kyoko", "🇯🇵"),
    "ko-KR": LanguagePack("ko-KR", "Korean", "한국어", "Yuna", "Yuna", "🇰🇷"),
    "zh-CN": LanguagePack(
        "zh-CN", "Chinese (Mandarin)", "中文", "Tingting", "Tingting", "🇨🇳"
    ),
    "vi-VN": LanguagePack("vi-VN", "Vietnamese", "Tiếng Việt", "Linh", "Linh", "🇻🇳"),
    "th-TH": LanguagePack("th-TH", "Thai", "ไทย", "Kanya", "Kanya", "🇹🇭"),
    "id-ID": LanguagePack(
        "id-ID", "Indonesian", "Bahasa Indonesia", "Damayanti", "Damayanti", "🇮🇩"
    ),
    "es-ES": LanguagePack(
        "es-ES", "Spanish (Spain)", "Español", "Monica", "Monica", "🇪🇸"
    ),
    "es-MX": LanguagePack(
        "es-MX", "Spanish (Mexico)", "Español", "Paulina", "Paulina", "🇲🇽"
    ),
    "fr-FR": LanguagePack("fr-FR", "French", "Français", "Amelie", "Thomas", "🇫🇷"),
    "de-DE": LanguagePack("de-DE", "German", "Deutsch", "Anna", "Anna", "🇩🇪"),
    "it-IT": LanguagePack("it-IT", "Italian", "Italiano", "Alice", "Alice", "🇮🇹"),
    "pt-BR": LanguagePack(
        "pt-BR", "Portuguese (Brazil)", "Português", "Luciana", "Luciana", "🇧🇷"
    ),
    "pl-PL": LanguagePack("pl-PL", "Polish", "Polski", "Zosia", "Zosia", "🇵🇱"),
}
