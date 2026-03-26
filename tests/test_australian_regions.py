# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
"""
Tests for Australian Regional Language Database
"""

import pytest

from agentic_brain.voice.australian_regions import (
    AUSTRALIAN_CITIES,
    get_local_greeting,
    get_local_knowledge,
)


def test_cities_exist():
    """Test all major cities are present"""
    expected_cities = [
        "adelaide",
        "brisbane",
        "sydney",
        "melbourne",
        "perth",
        "darwin",
        "hobart",
        "canberra",
    ]
    for city in expected_cities:
        assert city in AUSTRALIAN_CITIES, f"{city} missing from database"


def test_adelaide_data():
    """Test Adelaide specific data"""
    adelaide = AUSTRALIAN_CITIES["adelaide"]
    assert adelaide["state"] == "South Australia"
    assert "heaps good" in adelaide["slang"]["great"]
    assert "FruChocs" in adelaide["local_brands"]
    assert "Crows" in adelaide["sports"]["AFL"]


def test_brisbane_data():
    """Test Brisbane specific data"""
    brisbane = AUSTRALIAN_CITIES["brisbane"]
    assert brisbane["state"] == "Queensland"
    assert "bonzer" in brisbane["slang"]["great"]
    assert "XXXX Gold" in brisbane["local_brands"]


def test_melbourne_data():
    """Test Melbourne specific data"""
    melbourne = AUSTRALIAN_CITIES["melbourne"]
    assert melbourne["state"] == "Victoria"
    assert "potato cake" in melbourne["slang"]["potato cake"]
    assert "MCG" in melbourne["landmarks"]


def test_sydney_data():
    """Test Sydney specific data"""
    sydney = AUSTRALIAN_CITIES["sydney"]
    assert sydney["state"] == "New South Wales"
    assert "middy" in sydney["slang"]["beer glass (285ml)"]
    assert "Opera House" in sydney["landmarks"]


def test_perth_data():
    """Test Perth specific data"""
    perth = AUSTRALIAN_CITIES["perth"]
    assert perth["state"] == "Western Australia"
    assert "middy" in perth["slang"]["beer glass (285ml)"]
    assert "Kings Park" in perth["landmarks"]


def test_darwin_data():
    """Test Darwin specific data"""
    darwin = AUSTRALIAN_CITIES["darwin"]
    assert darwin["state"] == "Northern Territory"
    assert "handle" in darwin["slang"]["beer glass (2L)"]
    assert "Kakadu National Park" in darwin["landmarks"]


def test_hobart_data():
    """Test Hobart specific data"""
    hobart = AUSTRALIAN_CITIES["hobart"]
    assert hobart["state"] == "Tasmania"
    assert "MONA" in hobart["landmarks"]


def test_canberra_data():
    """Test Canberra specific data"""
    canberra = AUSTRALIAN_CITIES["canberra"]
    assert canberra["state"] == "Australian Capital Territory"
    assert "Parliament House" in canberra["landmarks"]


def test_get_local_greeting():
    """Test greeting generation"""
    greeting = get_local_greeting("adelaide")
    assert isinstance(greeting, str)
    assert len(greeting) > 0

    # Test unknown city returns default
    assert get_local_greeting("unknown_city") == "G'day mate"


def test_get_local_knowledge():
    """Test knowledge retrieval"""
    # Test specific topic
    slang = get_local_knowledge("adelaide", "slang")
    assert "heaps good" in slang

    # Test slang topic lookup
    swimsuit = get_local_knowledge("brisbane", "swimsuit")
    assert "togs" in swimsuit

    # Test unknown topic
    unknown = get_local_knowledge("adelaide", "quantum_physics")
    assert "Sorry, I don't have specific info" in unknown
