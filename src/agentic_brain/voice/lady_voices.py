"""Kokoro-82M voice mapping for the 14 Adelaide ladies.

Research notes
--------------
- The installed ``kokoro`` package in this repository's Python 3.12 virtual
  environment is version ``0.9.4``.
- That package exposes ``KPipeline`` but does not currently expose a public
  ``list_voices()`` helper, so the authoritative catalogue is derived from the
  upstream ``VOICES.md`` file for ``hexgrad/Kokoro-82M``.
- Kokoro officially supports voice IDs in American English, British English,
  Japanese, Mandarin Chinese, French, Italian, Spanish, Hindi, and Brazilian
  Portuguese. For unsupported native languages we choose the closest English
  proxy voice and define a deliberate fallback chain.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Final

RESEARCHED_KOKORO_VERSION: Final[str] = "0.9.4"
KOKORO_VOICE_CATALOG_SOURCE: Final[str] = (
    "https://huggingface.co/hexgrad/Kokoro-82M/raw/main/VOICES.md"
)

OFFICIAL_KOKORO_VOICE_CATALOG: Final[dict[str, tuple[str, ...]]] = {
    "en-us": (
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
    ),
    "en-gb": (
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
    ),
    "ja": (
        "jf_alpha",
        "jf_gongitsune",
        "jf_nezumi",
        "jf_tebukuro",
        "jm_kumo",
    ),
    "zh": (
        "zf_xiaobei",
        "zf_xiaoni",
        "zf_xiaoxiao",
        "zf_xiaoyi",
        "zm_yunjian",
        "zm_yunxi",
        "zm_yunxia",
        "zm_yunyang",
    ),
    "fr": ("ff_siwis",),
    "it": ("if_sara", "im_nicola"),
    "es": ("ef_dora", "em_alex", "em_santa"),
    "hi": ("hf_alpha", "hf_beta", "hm_omega", "hm_psi"),
    "pt-br": ("pf_dora", "pm_alex", "pm_santa"),
}

SUPPORTED_KOKORO_LANGUAGES: Final[set[str]] = set(OFFICIAL_KOKORO_VOICE_CATALOG)

LADY_ORDER: Final[tuple[str, ...]] = (
    "Karen",
    "Kyoko",
    "Tingting",
    "Yuna",
    "Linh",
    "Kanya",
    "Dewi",
    "Sari",
    "Wayan",
    "Moira",
    "Alice",
    "Zosia",
    "Flo",
    "Shelley",
)


def _build_mapping() -> dict[str, dict[str, Any]]:
    return {
        "Karen": {
            "voice_id": "bf_emma",
            "language": "en-gb",
            "native_language": "en-au",
            "style": "confident, direct, polished Commonwealth lead host",
            "rate_adjustment": 0.98,
            "origin": "Australian",
            "role": "Lead host",
            "kokoro_supported": True,
            "fallback_chain": ["bf_emma", "af_bella", "bf_lily", "af_heart"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "bf_emma", "weight": 0.7},
                    {"voice_id": "af_bella", "weight": 0.3},
                ],
                "use_case": "Boss mode, onboarding, authoritative guidance",
            },
            "rationale": (
                "bf_emma is the strongest Commonwealth-style female voice in the "
                "official British set and pairs well with af_bella when Karen "
                "needs extra assertive warmth."
            ),
            "notes": (
                "There is no official Australian Kokoro voice yet, so Karen uses "
                "the closest polished English accent with a slight tempo reduction."
            ),
        },
        "Kyoko": {
            "voice_id": "jf_alpha",
            "language": "ja",
            "native_language": "ja",
            "style": "precise, calm, meticulous quality specialist",
            "rate_adjustment": 0.94,
            "origin": "Japanese",
            "role": "Quality focus",
            "kokoro_supported": True,
            "fallback_chain": ["jf_alpha", "jf_tebukuro", "bf_alice", "af_nicole"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "jf_alpha", "weight": 0.8},
                    {"voice_id": "jf_tebukuro", "weight": 0.2},
                ],
                "use_case": "Test readouts, careful confirmations, gentle coaching",
            },
            "rationale": (
                "jf_alpha is the strongest Japanese female base voice in the "
                "official catalogue, while jf_tebukuro softens the delivery."
            ),
            "notes": "Best used for calm QA narration and Japanese phrase teaching.",
        },
        "Tingting": {
            "voice_id": "zf_xiaoxiao",
            "language": "zh",
            "native_language": "zh",
            "style": "fast, efficient, data-driven, solution-focused",
            "rate_adjustment": 1.06,
            "origin": "Chinese",
            "role": "Analytics",
            "kokoro_supported": True,
            "fallback_chain": ["zf_xiaoxiao", "zf_xiaoyi", "af_bella", "bf_emma"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "zf_xiaoxiao", "weight": 0.75},
                    {"voice_id": "zf_xiaoyi", "weight": 0.25},
                ],
                "use_case": "Dashboards, summaries, high-speed recommendations",
            },
            "rationale": (
                "zf_xiaoxiao reads clearly at higher speaking rates and zf_xiaoyi "
                "adds a little extra brightness for energetic analytical output."
            ),
            "notes": "Use with compact phrasing because Mandarin Kokoro voices prefer medium-length chunks.",
        },
        "Yuna": {
            "voice_id": "af_bella",
            "language": "en-us",
            "native_language": "ko",
            "style": "energetic, social, bright tech explainer",
            "rate_adjustment": 1.08,
            "origin": "Korean",
            "role": "Tech and social media",
            "kokoro_supported": True,
            "fallback_chain": ["af_bella", "af_nova", "bf_emma", "af_heart"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "af_bella", "weight": 0.65},
                    {"voice_id": "af_nova", "weight": 0.35},
                ],
                "use_case": "Excited product launches, upbeat walkthroughs",
            },
            "rationale": (
                "Kokoro has no Korean voice, so af_bella gives Yuna the best "
                "high-quality youthful energy and af_nova keeps her sounding agile."
            ),
            "notes": "Use a separate native-language fallback outside Kokoro for Korean phrase teaching.",
        },
        "Linh": {
            "voice_id": "bf_alice",
            "language": "en-gb",
            "native_language": "vi",
            "style": "clear, grounded, practical GitHub expert and city guide",
            "rate_adjustment": 1.0,
            "origin": "Vietnamese",
            "role": "GitHub expert and Adelaide guide",
            "kokoro_supported": True,
            "fallback_chain": ["bf_alice", "af_nicole", "bf_lily", "af_heart"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "bf_alice", "weight": 0.7},
                    {"voice_id": "af_nicole", "weight": 0.3},
                ],
                "use_case": "Repository tutorials, local directions, calm help",
            },
            "rationale": (
                "bf_alice gives Linh a precise Commonwealth cadence that feels "
                "credible for GitHub guidance, while af_nicole adds a warmer edge."
            ),
            "notes": "Vietnamese is not officially supported by Kokoro-82M.",
        },
        "Kanya": {
            "voice_id": "af_nicole",
            "language": "en-us",
            "native_language": "th",
            "style": "calm, caring, wellness-oriented, reassuring",
            "rate_adjustment": 0.92,
            "origin": "Thai",
            "role": "Wellness",
            "kokoro_supported": True,
            "fallback_chain": ["af_nicole", "af_heart", "bf_lily", "bf_alice"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "af_nicole", "weight": 0.75},
                    {"voice_id": "af_heart", "weight": 0.25},
                ],
                "use_case": "Meditation, comfort, soft reminders",
            },
            "rationale": (
                "af_nicole is one of the steadier long-form female voices and "
                "af_heart helps when Kanya should feel extra nurturing."
            ),
            "notes": "Thai is not officially supported by Kokoro-82M.",
        },
        "Dewi": {
            "voice_id": "af_sarah",
            "language": "en-us",
            "native_language": "id",
            "style": "modern, organised, polished project manager",
            "rate_adjustment": 1.01,
            "origin": "Indonesian/Jakarta",
            "role": "Project management",
            "kokoro_supported": True,
            "fallback_chain": ["af_sarah", "bf_emma", "af_bella", "bf_alice"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "af_sarah", "weight": 0.6},
                    {"voice_id": "bf_emma", "weight": 0.4},
                ],
                "use_case": "Stand-ups, scheduling, crisp PM updates",
            },
            "rationale": (
                "af_sarah gives Dewi modern clarity, and bf_emma adds the polished "
                "executive feel needed for project management moments."
            ),
            "notes": "Indonesian is not officially supported by Kokoro-82M.",
        },
        "Sari": {
            "voice_id": "af_kore",
            "language": "en-us",
            "native_language": "id-jv",
            "style": "cultural, reflective, measured documentation voice",
            "rate_adjustment": 0.95,
            "origin": "Indonesian/Java",
            "role": "Culture and documentation",
            "kokoro_supported": True,
            "fallback_chain": ["af_kore", "bf_isabella", "af_heart", "bf_alice"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "af_kore", "weight": 0.65},
                    {"voice_id": "bf_isabella", "weight": 0.35},
                ],
                "use_case": "Documentation, long-form notes, cultural explainers",
            },
            "rationale": (
                "af_kore has a composed neutral base that suits careful writing, "
                "and bf_isabella adds the more literary finish Sari needs."
            ),
            "notes": "Javanese and Indonesian are not officially supported by Kokoro-82M.",
        },
        "Wayan": {
            "voice_id": "af_heart",
            "language": "en-us",
            "native_language": "id-bal",
            "style": "spiritual, creative, airy, meditative",
            "rate_adjustment": 0.9,
            "origin": "Indonesian/Bali",
            "role": "Spiritual and creative",
            "kokoro_supported": True,
            "fallback_chain": ["af_heart", "af_sarah", "af_nicole", "bf_lily"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "af_heart", "weight": 0.8},
                    {"voice_id": "af_sarah", "weight": 0.2},
                ],
                "use_case": "Breathing exercises, reflective prompts, ambient guidance",
            },
            "rationale": (
                "af_heart is the warmest female base in the catalogue and works "
                "well for slower spiritual or creative speech."
            ),
            "notes": "Balinese and Indonesian are not officially supported by Kokoro-82M.",
        },
        "Moira": {
            "voice_id": "bf_isabella",
            "language": "en-gb",
            "native_language": "en-ie",
            "style": "warm, artistic, thoughtful debugger",
            "rate_adjustment": 0.97,
            "origin": "Irish",
            "role": "Debugging expert",
            "kokoro_supported": True,
            "fallback_chain": ["bf_isabella", "bf_lily", "af_heart", "bf_alice"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "bf_isabella", "weight": 0.7},
                    {"voice_id": "af_heart", "weight": 0.3},
                ],
                "use_case": "Gentle debugging, reflective explanations, story-like narration",
            },
            "rationale": (
                "There is no Irish Kokoro voice, so bf_isabella provides a melodic "
                "British proxy and af_heart adds the softness Moira needs."
            ),
            "notes": "Use platform-native fallback outside Kokoro when a distinctly Irish timbre is required.",
        },
        "Alice": {
            "voice_id": "if_sara",
            "language": "it",
            "native_language": "it",
            "style": "expressive, lively, warm food and travel guide",
            "rate_adjustment": 1.03,
            "origin": "Italian",
            "role": "Food tips",
            "kokoro_supported": True,
            "fallback_chain": ["if_sara", "bf_isabella", "af_bella", "af_heart"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "if_sara", "weight": 0.8},
                    {"voice_id": "bf_isabella", "weight": 0.2},
                ],
                "use_case": "Food recommendations, travel banter, expressive reads",
            },
            "rationale": (
                "if_sara is the clear native choice for Alice and keeps her "
                "expressive without sounding rushed."
            ),
            "notes": "Italian is officially supported by Kokoro-82M.",
        },
        "Zosia": {
            "voice_id": "af_aoede",
            "language": "en-us",
            "native_language": "pl",
            "style": "thoughtful, analytical, security-minded",
            "rate_adjustment": 0.96,
            "origin": "Polish",
            "role": "Security",
            "kokoro_supported": True,
            "fallback_chain": ["af_aoede", "bf_emma", "af_kore", "bf_lily"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "af_aoede", "weight": 0.75},
                    {"voice_id": "bf_emma", "weight": 0.25},
                ],
                "use_case": "Threat reviews, policy summaries, careful warnings",
            },
            "rationale": (
                "af_aoede has a more analytical colour than the brighter voices "
                "and works well for calm security explanations."
            ),
            "notes": "Polish is not officially supported by Kokoro-82M.",
        },
        "Flo": {
            "voice_id": "ff_siwis",
            "language": "fr",
            "native_language": "fr",
            "style": "elegant, refined, articulate code reviewer",
            "rate_adjustment": 0.99,
            "origin": "French",
            "role": "Code review",
            "kokoro_supported": True,
            "fallback_chain": ["ff_siwis", "bf_alice", "bf_isabella", "af_heart"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "ff_siwis", "weight": 0.8},
                    {"voice_id": "bf_alice", "weight": 0.2},
                ],
                "use_case": "PR commentary, elegant summaries, refined narration",
            },
            "rationale": (
                "ff_siwis is the only official French female Kokoro voice and its "
                "steady delivery suits Flo's elegant review persona."
            ),
            "notes": "French is officially supported by Kokoro-82M.",
        },
        "Shelley": {
            "voice_id": "bf_lily",
            "language": "en-gb",
            "native_language": "en-gb",
            "style": "friendly, supportive, dependable deployment guide",
            "rate_adjustment": 1.0,
            "origin": "British",
            "role": "Deployment",
            "kokoro_supported": True,
            "fallback_chain": ["bf_lily", "bf_emma", "bf_alice", "af_heart"],
            "blend": {
                "mode": "weighted",
                "voices": [
                    {"voice_id": "bf_lily", "weight": 0.7},
                    {"voice_id": "bf_emma", "weight": 0.3},
                ],
                "use_case": "Release checklists, rollout status, reassuring support",
            },
            "rationale": (
                "bf_lily lands in the sweet spot between friendly and dependable, "
                "which fits Shelley's deployment helper role."
            ),
            "notes": "British English is officially supported by Kokoro-82M.",
        },
    }


LADY_VOICE_MAP: Final[dict[str, dict[str, Any]]] = _build_mapping()

VOICE_BLEND_CONFIGS: Final[dict[str, dict[str, Any]]] = {
    lady_name: deepcopy(config["blend"]) for lady_name, config in LADY_VOICE_MAP.items()
}

_LADY_NAME_INDEX: Final[dict[str, str]] = {
    name.casefold(): name for name in LADY_VOICE_MAP
}


def get_official_kokoro_voices(
    language: str | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return the official Kokoro voice catalogue.

    Args:
        language: Optional language key such as ``"en-us"`` or ``"ja"``.
    """

    if language is None:
        return dict(OFFICIAL_KOKORO_VOICE_CATALOG)

    normalized = language.strip().casefold()
    return {normalized: OFFICIAL_KOKORO_VOICE_CATALOG.get(normalized, ())}


def get_lady_voice(lady_name: str) -> dict[str, Any]:
    """Return voice metadata for a lady.

    Lookup is case-insensitive. Unknown ladies fall back to Karen so callers
    always receive a safe, complete config.
    """

    normalized = lady_name.strip().casefold()
    canonical_name = _LADY_NAME_INDEX.get(normalized, "Karen")
    return deepcopy(LADY_VOICE_MAP[canonical_name])


def get_lady_blend(lady_name: str) -> dict[str, Any]:
    """Return the blend configuration for a lady."""

    return deepcopy(get_lady_voice(lady_name)["blend"])


def get_fallback_chain(lady_name: str) -> list[str]:
    """Return the ordered Kokoro fallback chain for a lady."""

    return list(get_lady_voice(lady_name)["fallback_chain"])


def is_official_kokoro_voice(voice_id: str) -> bool:
    """Return ``True`` when the voice ID exists in the official catalogue."""

    return any(voice_id in voices for voices in OFFICIAL_KOKORO_VOICE_CATALOG.values())
