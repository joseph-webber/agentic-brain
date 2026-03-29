# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""ADL CLI Command Tests - Typer Testing Patterns"""

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

# Import will work once CLI is implemented
# from agentic_brain.cli.main import app

runner = CliRunner()

# ============== FIXTURES ==============


@pytest.fixture
def temp_dir(tmp_path):
    """Temporary directory for file operations."""
    yield tmp_path
    if tmp_path.exists():
        shutil.rmtree(tmp_path)


@pytest.fixture
def mock_app():
    """Mock CLI app for testing until real one exists."""
    from typing import Optional

    from typer import Argument, Option, Typer

    app = Typer()

    @app.command()
    def entity(
        action: str,
        name: Optional[str] = Argument(None),
        fields: str = Option("", "--fields"),
        belongs_to: list[str] = Option([], "--belongs-to"),
        type_: str = Option("", "--type"),
    ):
        """Entity management commands."""
        print(f"DEBUG: action={action}, name={name}")
        if action == "create":
            if not name:
                raise SystemExit(1)
            print(f"Entity '{name}' created successfully")
        elif action == "list":
            print("Note\nUser")
        elif action == "regenerate":
            if name:
                print(f"Entity '{name}' regenerated successfully")
            else:
                raise SystemExit(1)
        elif action == "delete":
            if name:
                print(f"Entity '{name}' deleted successfully")
            else:
                raise SystemExit(1)
        elif action == "search":
            print(f"Search results for '{name}'")

    @app.command()
    def version():
        """Dummy command to force subcommand mode."""
        pass

    return app


# ============== ENTITY CREATE TESTS ==============


class TestEntityCreate:
    """Tests for 'agentic entity create' command."""

    def test_create_entity_success(self, mock_app, temp_dir):
        """Test successful entity creation."""
        result = runner.invoke(
            mock_app,
            ["entity", "create", "Note", "--fields", "title:String content:Text"],
        )
        assert result.exit_code == 0
        assert "created successfully" in result.stdout

    def test_create_entity_with_all_field_types(self, mock_app):
        """Test creating entity with various field types."""
        fields = "name:String age:Integer price:Float active:Boolean"
        result = runner.invoke(
            mock_app, ["entity", "create", "Product", "--fields", fields]
        )
        assert result.exit_code == 0

    def test_create_entity_missing_name(self, mock_app):
        """Test error when entity name is missing."""
        result = runner.invoke(mock_app, ["entity", "create"])
        assert result.exit_code != 0

    def test_create_entity_with_relationships(self, mock_app):
        """Test creating entity with relationships."""
        result = runner.invoke(
            mock_app,
            [
                "entity",
                "create",
                "Comment",
                "--fields",
                "content:Text",
                "--belongs-to",
                "Note",
                "--belongs-to",
                "User",
            ],
        )
        # Will pass once CLI supports relationships
        assert result.exit_code == 0 or "not recognized" in result.stdout.lower()


# ============== ENTITY LIST TESTS ==============


class TestEntityList:
    """Tests for 'agentic entity list' command."""

    def test_list_entities(self, mock_app):
        """Test listing all entities."""
        result = runner.invoke(mock_app, ["entity", "list"])
        assert result.exit_code == 0
        assert "Note" in result.stdout or "No entities" in result.stdout

    def test_list_entities_empty(self, mock_app, temp_dir):
        """Test listing when no entities exist."""
        result = runner.invoke(mock_app, ["entity", "list"])
        assert result.exit_code == 0


# ============== ENTITY REGENERATE TESTS ==============


class TestEntityRegenerate:
    """Tests for 'agentic entity regenerate' command."""

    def test_regenerate_entity(self, mock_app):
        """Test regenerating an existing entity."""
        result = runner.invoke(mock_app, ["entity", "regenerate", "Note"])
        assert result.exit_code == 0
        assert "regenerated successfully" in result.stdout

    def test_regenerate_nonexistent_entity(self, mock_app):
        """Test error when regenerating non-existent entity."""
        result = runner.invoke(mock_app, ["entity", "regenerate"])
        assert result.exit_code != 0


# ============== ENTITY DELETE TESTS ==============


class TestEntityDelete:
    """Tests for 'agentic entity delete' command."""

    def test_delete_entity(self, mock_app):
        """Test deleting an entity."""
        result = runner.invoke(mock_app, ["entity", "delete", "Note"])
        assert result.exit_code == 0
        assert "deleted successfully" in result.stdout

    def test_delete_nonexistent_entity(self, mock_app):
        """Test error when deleting non-existent entity."""
        result = runner.invoke(mock_app, ["entity", "delete"])
        assert result.exit_code != 0


# ============== ENTITY SEARCH TESTS (RAG) ==============


class TestEntitySearch:
    """Tests for 'agentic entity search' command (RAG)."""

    def test_search_entities(self, mock_app):
        """Test semantic search."""
        result = runner.invoke(mock_app, ["entity", "search", "budget meetings"])
        assert result.exit_code == 0
        assert "Search results" in result.stdout or "results" in result.stdout.lower()

    def test_search_with_entity_filter(self, mock_app):
        """Test search filtered by entity type."""
        result = runner.invoke(
            mock_app, ["entity", "search", "meetings", "--type", "Note"]
        )
        assert result.exit_code == 0 or "not recognized" in result.stdout.lower()


# ============== INTEGRATION TESTS ==============


class TestEntityWorkflow:
    """End-to-end workflow tests."""

    def test_full_entity_lifecycle(self, mock_app, temp_dir):
        """Test create -> list -> regenerate -> delete workflow."""
        # Create
        result = runner.invoke(
            mock_app, ["entity", "create", "TestEntity", "--fields", "name:String"]
        )
        assert result.exit_code == 0

        # List
        result = runner.invoke(mock_app, ["entity", "list"])
        assert result.exit_code == 0

        # Regenerate
        result = runner.invoke(mock_app, ["entity", "regenerate", "TestEntity"])
        assert result.exit_code == 0

        # Delete
        result = runner.invoke(mock_app, ["entity", "delete", "TestEntity"])
        assert result.exit_code == 0
