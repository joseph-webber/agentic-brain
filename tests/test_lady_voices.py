# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.lady_voices import (
    LADY_ORDER,
    LADY_VOICE_MAP,
    OFFICIAL_KOKORO_VOICE_CATALOG,
    RESEARCHED_KOKORO_VERSION,
    VOICE_BLEND_CONFIGS,
    SUPPORTED_KOKORO_LANGUAGES,
    get_fallback_chain,
    get_lady_blend,
    get_lady_voice,
    get_official_kokoro_voices,
    is_official_kokoro_voice,
)


REQUIRED_FIELDS = {
    "voice_id",
    "language",
    "native_language",
    "style",
    "rate_adjustment",
    "origin",
    "role",
    "kokoro_supported",
    "fallback_chain",
    "blend",
    "rationale",
    "notes",
}


class TestLadyVoiceCatalog:
    def test_all_14_ladies_are_present(self):
        assert tuple(LADY_VOICE_MAP) == LADY_ORDER
        assert len(LADY_VOICE_MAP) == 14

    def test_every_mapping_has_required_metadata(self):
        for config in LADY_VOICE_MAP.values():
            assert REQUIRED_FIELDS.issubset(config)

    def test_primary_voices_are_unique(self):
        voice_ids = [config["voice_id"] for config in LADY_VOICE_MAP.values()]
        assert len(voice_ids) == len(set(voice_ids))

    def test_primary_voices_are_official_kokoro_voices(self):
        for config in LADY_VOICE_MAP.values():
            assert is_official_kokoro_voice(config["voice_id"]) is True

    def test_supported_language_set_contains_core_languages(self):
        assert {"en-us", "en-gb", "ja", "zh", "fr", "it"}.issubset(
            SUPPORTED_KOKORO_LANGUAGES
        )

    def test_catalog_lookup_for_single_language(self):
        assert get_official_kokoro_voices("ja") == {
            "ja": OFFICIAL_KOKORO_VOICE_CATALOG["ja"]
        }

    def test_unknown_language_lookup_returns_empty_tuple(self):
        assert get_official_kokoro_voices("ko") == {"ko": ()}

    def test_researched_version_is_recorded(self):
        assert RESEARCHED_KOKORO_VERSION == "0.9.4"


class TestLadyVoiceLookup:
    def test_get_lady_voice_returns_copy(self):
        config = get_lady_voice("Karen")
        config["voice_id"] = "changed"
        assert LADY_VOICE_MAP["Karen"]["voice_id"] == "bf_emma"

    def test_get_lady_voice_is_case_insensitive(self):
        assert (
            get_lady_voice("kyoko")["voice_id"] == LADY_VOICE_MAP["Kyoko"]["voice_id"]
        )

    def test_unknown_lady_falls_back_to_karen(self):
        assert (
            get_lady_voice("Unknown")["voice_id"] == LADY_VOICE_MAP["Karen"]["voice_id"]
        )

    def test_fallback_chain_starts_with_primary_voice(self):
        for lady_name, config in LADY_VOICE_MAP.items():
            assert get_fallback_chain(lady_name)[0] == config["voice_id"]

    def test_fallback_chains_have_no_duplicates(self):
        for lady_name in LADY_VOICE_MAP:
            chain = get_fallback_chain(lady_name)
            assert len(chain) == len(set(chain))

    def test_rate_adjustments_stay_in_safe_range(self):
        for config in LADY_VOICE_MAP.values():
            assert 0.85 <= config["rate_adjustment"] <= 1.1

    def test_rationale_and_notes_are_non_empty(self):
        for config in LADY_VOICE_MAP.values():
            assert config["rationale"].strip()
            assert config["notes"].strip()

    def test_unsupported_native_languages_use_proxy_english_languages(self):
        for lady_name in (
            "Yuna",
            "Linh",
            "Kanya",
            "Dewi",
            "Sari",
            "Wayan",
            "Zosia",
            "Moira",
        ):
            config = LADY_VOICE_MAP[lady_name]
            assert config["language"] in {"en-us", "en-gb"}


class TestVoiceBlendConfigs:
    def test_every_lady_has_a_blend_config(self):
        assert set(VOICE_BLEND_CONFIGS) == set(LADY_VOICE_MAP)

    def test_get_lady_blend_returns_copy(self):
        blend = get_lady_blend("Flo")
        blend["voices"][0]["voice_id"] = "changed"
        assert VOICE_BLEND_CONFIGS["Flo"]["voices"][0]["voice_id"] == "ff_siwis"

    def test_blend_voice_ids_are_official(self):
        for blend in VOICE_BLEND_CONFIGS.values():
            for voice in blend["voices"]:
                assert is_official_kokoro_voice(voice["voice_id"]) is True

    def test_blend_weights_sum_to_one(self):
        for blend in VOICE_BLEND_CONFIGS.values():
            total = sum(voice["weight"] for voice in blend["voices"])
            assert abs(total - 1.0) < 1e-9

    def test_blend_use_case_is_documented(self):
        for blend in VOICE_BLEND_CONFIGS.values():
            assert blend["use_case"].strip()
