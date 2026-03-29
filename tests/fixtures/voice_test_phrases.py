# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Interesting, deterministic phrase fixtures for voice and audio tests."""

from __future__ import annotations

from hashlib import sha256
from itertools import chain
from random import Random

PHRASES_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "technology_quotes": (
        "Any sufficiently advanced technology is indistinguishable from magic.",
        "The most dangerous phrase in the language is, we've always done it this way.",
        "The best way to predict the future is to invent it.",
        "Innovation distinguishes between a leader and a follower.",
        "Talk is cheap. Show me the code.",
        "Programs must be written for people to read, and only incidentally for machines to execute.",
        "Computers are magnificent tools for the realization of our dreams.",
        "Simple things should be simple, and complex things should be possible.",
        "The function of good software is to make the complex appear simple.",
        "The question of whether a computer can think is no more interesting than whether a submarine can swim.",
    ),
    "australia_facts": (
        "Australia is wider than the moon if you measure coast to coast.",
        "The Great Barrier Reef is the largest coral reef system on Earth.",
        "Canberra was purpose-built as Australia's capital city.",
        "Tasmania has some of the cleanest air measured anywhere in the world.",
        "The Australian Alps receive more snow than Switzerland in a typical year.",
        "Wombats produce cube-shaped droppings, which still sounds made up.",
        "Lake Hillier in Western Australia is famous for its bright pink water.",
        "The didgeridoo is one of the world's oldest living musical instruments.",
        "Australia is home to more than ten thousand beaches.",
        "Kangaroos cannot walk backward easily, which is why they appear on the coat of arms.",
    ),
    "poetry_snippets": (
        "Moonlight drifts across the keys like silver rain on sleeping streets.",
        "A quiet engine hums beneath the stars and dreams in cobalt blue.",
        "The sea keeps time with patient hands against the shore of night.",
        "Soft thunder rolls beyond the hills where tomorrow waits awake.",
        "Lantern light trembles gently on the glass of a midnight train.",
        "Morning gathers gold from rooftops and folds it into song.",
        "The wind writes brief poems in the grass, then lets them go.",
        "Clouds unspool slowly over the harbour like ink in water.",
        "A single bell rings clear enough to wake the sleeping dawn.",
        "Winter sunlight leans through the window and warms the page.",
    ),
    "pronunciation_practice": (
        "Six sleek swans swam swiftly south while silver cymbals shimmered.",
        "The turquoise telescope tracked three tiny comets over Thursday harbour.",
        "Crisp citrus slices sparkled beside the cinnamon sugar pastries.",
        "A curious cartographer carefully coloured coastal contours in cobalt.",
        "The virtual violin vibrated warmly beneath the vaulted ceiling.",
        "Fresh focaccia, fig jam, and fennel tea filled the studio kitchen.",
        "Ruby lasers reflected sharply from the polished marble floor.",
        "Twelve velvet jackets jingled softly near the jazz quartet.",
        "The astronomer annotated lunar altitudes with deliberate precision.",
        "Bright paper cranes drifted above the botanical garden fountain.",
    ),
    "tongue_twisters": (
        "She sells seashells by the seashore while the tide ticks time.",
        "Red leather, yellow leather, read loudly with radiant rhythm.",
        "Toy boats bob briskly beside the blue Brisbane boardwalk.",
        "Truly rural libraries rarely require louder rolling r sounds.",
        "Unique New York unicorns use neon umbrellas under moonlight.",
        "Five frantic frogs flipped fresh figs from flimsy flowerpots.",
        "Crisp crusts crackle quickly when clever cooks crowd the kitchen.",
        "Friendly foxes fixed flimsy flags for forty-five festival floats.",
        "Greek grapes glow green when great gusts glide through the grove.",
        "Nine nimble nightingales knitted new neckties near Newcastle.",
    ),
    "multilingual_greetings": (
        "Hello, g'day, bonjour, hola, and kia ora from the same cheerful room.",
        "Bonjour, buongiorno, and guten Tag to every curious listener.",
        "Hola, привет, and hej from a friendly test harness.",
        "Konnichiwa, annyeonghaseyo, ni hao, and sawatdee in one bright breath.",
        "Xin chao, selamat pagi, and mabuhay to the morning shift.",
        "Dia duit, cześć, and hallo from a multilingual sound check.",
        "Merhaba, salam, and namaste from the pronunciation playground.",
        "Aloha, shalom, and marhaba from the global greeting queue.",
        "Olá, vanakkam, and jambo to the adventurous audio suite.",
        "Good evening, bonne soirée, and oyasumi from the late test run.",
    ),
    "status_updates": (
        "Thinking through the next graceful fallback before the chorus begins.",
        "Task complete, and the orchestra of tiny robots can take a bow.",
        "Processing the request while the harbour lights shimmer outside.",
        "The daemon is awake and listening for the next sparkling sentence.",
        "A friendly notification arrives like a postcard from tomorrow.",
        "Queueing the next phrase with calm confidence and clear enunciation.",
        "The voice system initialized with a warm hum and ready cadence.",
        "A resilient narrator steps forward even when the first plan wobbles.",
    ),
    "thinking_updates": (
        "Thinking through the next graceful fallback before the chorus begins.",
        "Thinking carefully while the queue lines up its next delightful phrase.",
        "Thinking aloud like a patient navigator charting stars over Adelaide.",
    ),
}

ALL_VOICE_TEST_PHRASES: tuple[str, ...] = tuple(
    chain.from_iterable(PHRASES_BY_CATEGORY.values())
)


def _get_phrase_pool(categories: tuple[str, ...]) -> tuple[str, ...]:
    if not categories:
        return ALL_VOICE_TEST_PHRASES

    invalid = [
        category for category in categories if category not in PHRASES_BY_CATEGORY
    ]
    if invalid:
        raise KeyError(f"Unknown voice test categories: {', '.join(sorted(invalid))}")

    return tuple(
        chain.from_iterable(PHRASES_BY_CATEGORY[category] for category in categories)
    )


def _rng_for(test_id: str, categories: tuple[str, ...]) -> Random:
    seed_material = "::".join((test_id, *categories))
    seed = int(sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16)
    return Random(seed)


def pick_voice_phrase(test_id: str, *categories: str) -> str:
    """Pick one deterministic phrase from the requested categories."""
    normalized_categories = tuple(categories)
    pool = _get_phrase_pool(normalized_categories)
    return _rng_for(test_id, normalized_categories).choice(pool)


def pick_voice_phrases(test_id: str, count: int, *categories: str) -> list[str]:
    """Pick several deterministic phrases from the requested categories."""
    if count < 1:
        raise ValueError("count must be at least 1")

    normalized_categories = tuple(categories)
    pool = list(_get_phrase_pool(normalized_categories))
    rng = _rng_for(test_id, normalized_categories)

    if count <= len(pool):
        return rng.sample(pool, count)

    return [rng.choice(pool) for _ in range(count)]


__all__ = [
    "ALL_VOICE_TEST_PHRASES",
    "PHRASES_BY_CATEGORY",
    "pick_voice_phrase",
    "pick_voice_phrases",
]
