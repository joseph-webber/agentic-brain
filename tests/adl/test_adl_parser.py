# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Comprehensive ADL Parser Tests - CI/CD Ready"""

import pytest

from agentic_brain.adl.entity_parser import ADLEntityParser, ADLParseError

# ============== FIXTURES ==============


@pytest.fixture
def parser():
    """Fresh parser instance for each test."""
    return ADLEntityParser()


@pytest.fixture
def valid_note_adl():
    """Standard Note entity ADL."""
    return """
entity Note {
    title String required maxLength(100)
    content Text searchable
    userId Integer foreignKey(User)
    tags List[String] searchable
    createdAt DateTime default(now)

    relationships {
        belongsTo User as author
        hasMany Comment cascade(delete)
    }

    access {
        read: USER, ADMIN
        write: owner, ADMIN
        delete: ADMIN
    }

    storage {
        dao: sqlite
        rag: chromadb
    }
}
"""


# ============== FIELD TYPE PARSING ==============


@pytest.mark.parametrize(
    "field_def,expected_type",
    [
        ("name String", "String"),
        ("age Integer", "Integer"),
        ("price Float", "Float"),
        ("active Boolean", "Boolean"),
        ("bio Text", "Text"),
        ("created DateTime", "DateTime"),
        ("tags List[String]", "List[String]"),
        ("meta Dict[String,Any]", "Dict[String,Any]"),
    ],
)
def test_parse_field_types(parser, field_def, expected_type):
    """Test all supported field types."""
    adl = f"entity Test {{ {field_def} }}"
    result = parser.parse(adl)
    assert result["Test"]["fields"][0]["type"] == expected_type


# ============== FIELD MODIFIERS ==============


@pytest.mark.parametrize(
    "modifier,expected_key,expected_value",
    [
        ("required", "required", True),
        ("searchable", "searchable", True),
        ("unique", "unique", True),
        ("maxLength(100)", "maxLength", 100),
        ("minLength(5)", "minLength", 5),
        ("default(now)", "default", "now"),
        ("default(0)", "default", "0"),
        ("foreignKey(User)", "foreignKey", "User"),
    ],
)
def test_parse_field_modifiers(parser, modifier, expected_key, expected_value):
    """Test all field modifiers."""
    adl = f"entity Test {{ name String {modifier} }}"
    result = parser.parse(adl)
    field = result["Test"]["fields"][0]
    assert field.get(expected_key) == expected_value


# ============== RELATIONSHIPS ==============


@pytest.mark.parametrize(
    "rel_def,expected",
    [
        ("belongsTo User", {"type": "belongsTo", "target": "User"}),
        (
            "belongsTo User as author",
            {"type": "belongsTo", "target": "User", "alias": "author"},
        ),
        ("hasMany Comment", {"type": "hasMany", "target": "Comment"}),
        (
            "hasMany Comment cascade(delete)",
            {"type": "hasMany", "target": "Comment", "cascade": "delete"},
        ),
        (
            "hasMany Tag through(NoteTags)",
            {"type": "hasMany", "target": "Tag", "through": "NoteTags"},
        ),
        ("manyToMany Category", {"type": "manyToMany", "target": "Category"}),
    ],
)
def test_parse_relationships(parser, rel_def, expected):
    """Test relationship parsing."""
    adl = f"entity Test {{ relationships {{ {rel_def} }} }}"
    result = parser.parse(adl)
    rel = result["Test"]["relationships"][0]
    for key, value in expected.items():
        assert rel.get(key) == value


# ============== ACCESS CONTROL ==============


@pytest.mark.parametrize(
    "access_def,expected",
    [
        ("read: USER", {"read": ["USER"]}),
        ("read: USER, ADMIN", {"read": ["USER", "ADMIN"]}),
        ("write: owner, ADMIN", {"write": ["owner", "ADMIN"]}),
        ("delete: ADMIN", {"delete": ["ADMIN"]}),
    ],
)
def test_parse_access_control(parser, access_def, expected):
    """Test access control rules."""
    adl = f"entity Test {{ access {{ {access_def} }} }}"
    result = parser.parse(adl)
    for op, roles in expected.items():
        assert result["Test"]["access"].get(op) == roles


# ============== STORAGE CONFIG ==============


@pytest.mark.parametrize(
    "storage_def,expected",
    [
        ("dao: sqlite", {"dao": "sqlite"}),
        ("rag: chromadb", {"rag": "chromadb"}),
        ("rag: lancedb", {"rag": "lancedb"}),
        ("graph: neo4j", {"graph": "neo4j"}),
    ],
)
def test_parse_storage_config(parser, storage_def, expected):
    """Test storage configuration."""
    adl = f"entity Test {{ storage {{ {storage_def} }} }}"
    result = parser.parse(adl)
    for key, value in expected.items():
        assert result["Test"]["storage"].get(key) == value


# ============== FULL ENTITY PARSING ==============


def test_parse_complete_entity(parser, valid_note_adl):
    """Test parsing a complete entity with all features."""
    result = parser.parse(valid_note_adl)

    assert "Note" in result
    entity = result["Note"]

    # Check fields
    field_names = [f["name"] for f in entity["fields"]]
    assert "title" in field_names
    assert "content" in field_names
    assert "userId" in field_names
    assert "tags" in field_names

    # Check searchable fields
    searchable = [f["name"] for f in entity["fields"] if f.get("searchable")]
    assert "content" in searchable
    assert "tags" in searchable

    # Check relationships
    assert len(entity["relationships"]) == 2

    # Check access
    assert "USER" in entity["access"]["read"]
    assert "ADMIN" in entity["access"]["write"]

    # Check storage
    assert entity["storage"]["dao"] == "sqlite"
    assert entity["storage"]["rag"] == "chromadb"


# ============== MULTIPLE ENTITIES ==============


def test_parse_multiple_entities(parser):
    """Test parsing multiple entities in one ADL file."""
    adl = """
entity User {
    name String required
    email String unique
}

entity Note {
    title String
    belongsTo User
}
"""
    result = parser.parse(adl)
    assert "User" in result
    assert "Note" in result
    assert len(result["User"]["fields"]) == 2
    assert len(result["Note"]["fields"]) == 1


# ============== ERROR HANDLING ==============


@pytest.mark.parametrize(
    "invalid_adl,error_type",
    [
        ("", "EmptyInput"),
        ("entity {}", "MissingEntityName"),
        ("entity Note", "MissingBody"),
        ("entity Note { name }", "InvalidFieldDefinition"),
        ("entity Note { name UnknownType }", "UnknownFieldType"),
        ("entity Note { relationships { invalid } }", "InvalidRelationship"),
    ],
)
def test_invalid_syntax_raises_error(parser, invalid_adl, error_type):
    """Test that invalid ADL raises appropriate errors."""
    with pytest.raises(ADLParseError) as exc_info:
        parser.parse(invalid_adl)
    assert error_type in str(exc_info.value) or exc_info.value is not None


# ============== EDGE CASES ==============


def test_empty_entity(parser):
    """Test parsing entity with no fields."""
    adl = "entity Empty {}"
    result = parser.parse(adl)
    assert "Empty" in result
    assert result["Empty"]["fields"] == []


def test_entity_with_comments(parser):
    """Test that comments are ignored."""
    adl = """
entity Note {
    // This is a comment
    title String  // inline comment
    /* Multi-line
       comment */
    content Text
}
"""
    result = parser.parse(adl)
    assert len(result["Note"]["fields"]) == 2


def test_special_characters_in_names(parser):
    """Test handling of special characters."""
    adl = "entity UserProfile { firstName String lastName String }"
    result = parser.parse(adl)
    assert "UserProfile" in result


def test_whitespace_handling(parser):
    """Test various whitespace formats."""
    adl = "entity   Note   {   title   String   required   }"
    result = parser.parse(adl)
    assert "Note" in result
    assert result["Note"]["fields"][0]["name"] == "title"
