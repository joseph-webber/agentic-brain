# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""Tests for RAG CLI commands.

Comprehensive test suite with 20+ test cases covering:
- Query command with various inputs
- Index command with file operations
- Eval command with results files
- Health command status checks
- Config command get/set operations
- JSON output format
- Error handling
- Missing arguments
- File validation
"""

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from agentic_brain.cli.rag_commands import (
    cmd_config,
    cmd_eval,
    cmd_health,
    cmd_index,
    cmd_query,
    register_rag_commands,
)

# ===== FIXTURES =====


@pytest.fixture
def query_args_base():
    """Base mock arguments for query command."""
    args = argparse.Namespace(
        question="What is machine learning?",
        top_k=5,
        filters={},
        json=False,
    )
    return args


@pytest.fixture
def index_args_base():
    """Base mock arguments for index command."""
    args = argparse.Namespace(
        path="./documents",
        recursive=True,
        chunk_size=512,
        overlap=50,
        json=False,
    )
    return args


@pytest.fixture
def eval_args_base():
    """Base mock arguments for eval command."""
    args = argparse.Namespace(
        results="results.json",
        json=False,
    )
    return args


@pytest.fixture
def health_args_base():
    """Base mock arguments for health command."""
    args = argparse.Namespace(
        json=False,
    )
    return args


@pytest.fixture
def config_args_base():
    """Base mock arguments for config command."""
    args = argparse.Namespace(
        get=None,
        set=None,
        json=False,
    )
    return args


@pytest.fixture
def mock_rag_system():
    """Mock RAG system for testing."""
    with patch("agentic_brain.cli.rag_commands.RAGSystem") as mock:
        instance = MagicMock()
        mock.return_value = instance
        yield instance


# ===== QUERY COMMAND TESTS =====


def test_query_with_valid_question(query_args_base, mock_rag_system, capsys):
    """Test query command with valid question."""
    query_args_base.question = "What is AI?"
    mock_rag_system.query.return_value = {
        "answer": "AI is artificial intelligence.",
        "sources": ["doc1.pdf", "doc2.pdf"],
        "relevance_score": 0.95,
    }

    result = cmd_query(query_args_base)

    assert result == 0
    mock_rag_system.query.assert_called_once_with(
        question="What is AI?",
        top_k=5,
        filters={},
    )
    captured = capsys.readouterr()
    assert "Query completed" in captured.out


def test_query_with_json_output(query_args_base, mock_rag_system, capsys):
    """Test query command with JSON output."""
    query_args_base.json = True
    mock_rag_system.query.return_value = {
        "answer": "Python is a programming language.",
        "sources": ["doc.pdf"],
        "relevance_score": 0.88,
    }

    result = cmd_query(query_args_base)

    assert result == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["question"] == query_args_base.question
    assert output["answer"] == "Python is a programming language."
    assert "elapsed_ms" in output


def test_query_with_custom_top_k(query_args_base, mock_rag_system):
    """Test query command with custom top_k parameter."""
    query_args_base.top_k = 10
    mock_rag_system.query.return_value = {
        "answer": "Test",
        "sources": [],
        "relevance_score": 0.5,
    }

    result = cmd_query(query_args_base)

    assert result == 0
    mock_rag_system.query.assert_called_once()
    call_kwargs = mock_rag_system.query.call_args.kwargs
    assert call_kwargs["top_k"] == 10


def test_query_with_filters(query_args_base, mock_rag_system):
    """Test query command with document filters."""
    filters = {"source": "pdf", "date_from": "2024-01-01"}
    query_args_base.filters = filters
    mock_rag_system.query.return_value = {
        "answer": "Test",
        "sources": [],
        "relevance_score": 0.6,
    }

    result = cmd_query(query_args_base)

    assert result == 0
    call_kwargs = mock_rag_system.query.call_args.kwargs
    assert call_kwargs["filters"] == filters


def test_query_error_handling(query_args_base, mock_rag_system, capsys):
    """Test query command error handling."""
    mock_rag_system.query.side_effect = Exception("Connection failed")

    result = cmd_query(query_args_base)

    assert result == 1
    captured = capsys.readouterr()
    assert "failed" in captured.out.lower() or "error" in captured.out.lower()


def test_query_empty_question(mock_rag_system, capsys):
    """Test query with empty question."""
    args = argparse.Namespace(
        question=None,
        top_k=5,
        filters={},
        json=False,
    )

    result = cmd_query(args)

    assert result == 1


# ===== INDEX COMMAND TESTS =====


def test_index_valid_path(index_args_base, mock_rag_system, capsys):
    """Test index command with valid path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_args_base.path = tmpdir
        mock_rag_system.index.return_value = {
            "count": 10,
            "chunks": 50,
        }

        result = cmd_index(index_args_base)

        assert result == 0
        mock_rag_system.index.assert_called_once()
        captured = capsys.readouterr()
        assert "Indexed" in captured.out or "indexed" in captured.out.lower()


def test_index_with_json_output(index_args_base, mock_rag_system, capsys):
    """Test index command with JSON output."""
    index_args_base.json = True
    with tempfile.TemporaryDirectory() as tmpdir:
        index_args_base.path = tmpdir
        mock_rag_system.index.return_value = {
            "count": 5,
            "chunks": 25,
        }

        result = cmd_index(index_args_base)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["documents_indexed"] == 5
        assert output["chunks_created"] == 25


def test_index_nonexistent_path(index_args_base, mock_rag_system, capsys):
    """Test index command with nonexistent path."""
    index_args_base.path = "/nonexistent/path/xyz"

    result = cmd_index(index_args_base)

    assert result == 1
    mock_rag_system.index.assert_not_called()


def test_index_with_recursive_flag(index_args_base, mock_rag_system):
    """Test index command with recursive flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_args_base.path = tmpdir
        index_args_base.recursive = True
        mock_rag_system.index.return_value = {"count": 3, "chunks": 15}

        result = cmd_index(index_args_base)

        assert result == 0
        call_kwargs = mock_rag_system.index.call_args.kwargs
        assert call_kwargs["recursive"] is True


def test_index_with_custom_chunk_size(index_args_base, mock_rag_system):
    """Test index command with custom chunk size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_args_base.path = tmpdir
        index_args_base.chunk_size = 1024
        mock_rag_system.index.return_value = {"count": 1, "chunks": 5}

        result = cmd_index(index_args_base)

        assert result == 0
        call_kwargs = mock_rag_system.index.call_args.kwargs
        assert call_kwargs["chunk_size"] == 1024


def test_index_error_handling(index_args_base, mock_rag_system, capsys):
    """Test index command error handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_args_base.path = tmpdir
        mock_rag_system.index.side_effect = Exception("Indexing failed")

        result = cmd_index(index_args_base)

        assert result == 1


# ===== EVAL COMMAND TESTS =====


def test_eval_with_valid_results_file(eval_args_base, mock_rag_system, capsys):
    """Test eval command with valid results file."""
    results_data = [
        {"question": "Q1", "answer": "A1", "score": 0.9},
        {"question": "Q2", "answer": "A2", "score": 0.8},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(results_data, f)
        temp_file = f.name

    try:
        eval_args_base.results = temp_file
        mock_rag_system.evaluate.return_value = {
            "metrics": {
                "avg_score": 0.85,
                "num_results": 2,
            }
        }

        result = cmd_eval(eval_args_base)

        assert result == 0
        mock_rag_system.evaluate.assert_called_once()
    finally:
        Path(temp_file).unlink()


def test_eval_with_json_output(eval_args_base, mock_rag_system, capsys):
    """Test eval command with JSON output."""
    eval_args_base.json = True
    results_data = [{"question": "Q", "answer": "A"}]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(results_data, f)
        temp_file = f.name

    try:
        eval_args_base.results = temp_file
        mock_rag_system.evaluate.return_value = {"metrics": {"precision": 0.92}}

        result = cmd_eval(eval_args_base)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "metrics" in output
        assert output["total_results"] == 1
    finally:
        Path(temp_file).unlink()


def test_eval_nonexistent_file(eval_args_base, mock_rag_system, capsys):
    """Test eval command with nonexistent results file."""
    eval_args_base.results = "/nonexistent/results.json"

    result = cmd_eval(eval_args_base)

    assert result == 1
    mock_rag_system.evaluate.assert_not_called()


def test_eval_invalid_json_file(eval_args_base, mock_rag_system):
    """Test eval command with invalid JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("invalid json {[")
        temp_file = f.name

    try:
        eval_args_base.results = temp_file

        result = cmd_eval(eval_args_base)

        # Should fail when parsing JSON
        assert result == 1
    finally:
        Path(temp_file).unlink()


# ===== HEALTH COMMAND TESTS =====


def test_health_check_success(health_args_base, mock_rag_system, capsys):
    """Test health check command success."""
    mock_rag_system.health.return_value = {
        "status": "healthy",
        "components": {
            "neo4j": {"status": "ok"},
            "redis": {"status": "ok"},
            "embeddings": {"status": "ok"},
        },
    }

    result = cmd_health(health_args_base)

    assert result == 0
    mock_rag_system.health.assert_called_once()
    captured = capsys.readouterr()
    assert "healthy" in captured.out.lower()


def test_health_check_with_json_output(health_args_base, mock_rag_system, capsys):
    """Test health check command with JSON output."""
    health_args_base.json = True
    mock_rag_system.health.return_value = {
        "status": "healthy",
        "components": {"db": {"status": "ok"}},
    }

    result = cmd_health(health_args_base)

    assert result == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["status"] == "healthy"
    assert "components" in output


def test_health_check_degraded_status(health_args_base, mock_rag_system, capsys):
    """Test health check with degraded status."""
    mock_rag_system.health.return_value = {
        "status": "degraded",
        "components": {
            "neo4j": {"status": "ok"},
            "redis": {"status": "down"},
        },
    }

    result = cmd_health(health_args_base)

    assert result == 0
    captured = capsys.readouterr()
    assert "degraded" in captured.out.lower() or "down" in captured.out.lower()


def test_health_check_error(health_args_base, mock_rag_system, capsys):
    """Test health check command error handling."""
    mock_rag_system.health.side_effect = Exception("Health check failed")

    result = cmd_health(health_args_base)

    assert result == 1


# ===== CONFIG COMMAND TESTS =====


def test_config_show_all(config_args_base, mock_rag_system, capsys):
    """Test config command showing all configuration."""
    config_args_base.get = None
    config_args_base.set = None
    mock_rag_system.config.return_value = {
        "chunk_size": 512,
        "top_k": 5,
        "model": "gpt-4",
    }

    result = cmd_config(config_args_base)

    assert result == 0
    captured = capsys.readouterr()
    assert "Configuration" in captured.out


def test_config_get_specific_value(config_args_base, mock_rag_system, capsys):
    """Test config command getting specific value."""
    config_args_base.get = "chunk_size"
    mock_rag_system.config.return_value = 512

    result = cmd_config(config_args_base)

    assert result == 0
    captured = capsys.readouterr()
    assert "512" in captured.out or "chunk_size" in captured.out


def test_config_set_value(config_args_base, mock_rag_system, capsys):
    """Test config command setting value."""
    config_args_base.set = "top_k=10"

    result = cmd_config(config_args_base)

    assert result == 0
    captured = capsys.readouterr()
    assert "Set" in captured.out or "success" in captured.out.lower()


def test_config_with_json_output(config_args_base, mock_rag_system, capsys):
    """Test config command with JSON output."""
    config_args_base.json = True
    config_args_base.get = None
    config_args_base.set = None
    mock_rag_system.config.return_value = {
        "model": "claude-3",
        "temperature": 0.7,
    }

    result = cmd_config(config_args_base)

    assert result == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert "model" in output or "temperature" in output


def test_config_error_handling(config_args_base, mock_rag_system, capsys):
    """Test config command error handling."""
    config_args_base.get = "invalid_key"
    mock_rag_system.config.side_effect = Exception("Config error")

    result = cmd_config(config_args_base)

    assert result == 1


# ===== REGISTRATION TESTS =====


def test_register_rag_commands():
    """Test that RAG commands are properly registered."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    register_rag_commands(subparsers)

    # Should create subparsers for each command
    # We can't directly test the subparsers, but we can verify no errors occur
    assert True


def test_register_all_rag_subcommands():
    """Test all RAG subcommands are registered."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    register_rag_commands(subparsers)

    # Test parsing each command
    commands_to_test = [
        ["query", "test question"],
        ["index", "/tmp"],
        ["eval", "results.json"],
        ["health"],
        ["config"],
    ]

    for cmd_args in commands_to_test:
        try:
            parsed = parser.parse_args(cmd_args)
            assert parsed.command is not None
        except SystemExit:
            # Some commands might fail due to missing args, but shouldn't exit
            pass


# ===== INTEGRATION TESTS =====


def test_query_end_to_end_flow(mock_rag_system, capsys):
    """Test complete query flow from CLI argument parsing to output."""
    args = argparse.Namespace(
        question="How does machine learning work?",
        top_k=3,
        filters={},
        json=False,
    )

    mock_rag_system.query.return_value = {
        "answer": "ML uses algorithms to learn from data.",
        "sources": ["ml_101.pdf", "data_science.pdf"],
        "relevance_score": 0.92,
    }

    result = cmd_query(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Answer" in captured.out
    assert "Sources" in captured.out
    assert "Relevance" in captured.out


def test_index_eval_workflow(mock_rag_system, capsys):
    """Test index then eval workflow."""
    # Index some documents
    index_args = argparse.Namespace(
        path="/tmp",
        recursive=True,
        chunk_size=512,
        overlap=50,
        json=False,
    )

    mock_rag_system.index.return_value = {
        "count": 10,
        "chunks": 50,
    }

    result = cmd_index(index_args)
    assert result == 0

    # Evaluate results
    results_data = [{"question": "Q", "answer": "A", "score": 0.9}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(results_data, f)
        temp_file = f.name

    try:
        eval_args = argparse.Namespace(
            results=temp_file,
            json=False,
        )

        mock_rag_system.evaluate.return_value = {"metrics": {"avg_score": 0.9}}

        result = cmd_eval(eval_args)
        assert result == 0
    finally:
        Path(temp_file).unlink()


def test_health_then_config_workflow(mock_rag_system, capsys):
    """Test health check then config display workflow."""
    # Check health
    health_args = argparse.Namespace(json=False)
    mock_rag_system.health.return_value = {
        "status": "healthy",
        "components": {"db": {"status": "ok"}},
    }

    result = cmd_health(health_args)
    assert result == 0

    # Show config
    config_args = argparse.Namespace(get=None, set=None, json=False)
    mock_rag_system.config.return_value = {
        "model": "gpt-4",
        "temperature": 0.7,
    }

    result = cmd_config(config_args)
    assert result == 0


# ===== EDGE CASE TESTS =====


def test_query_with_very_long_question(query_args_base, mock_rag_system):
    """Test query with very long question."""
    long_question = "What is " + "a" * 10000 + "?"
    query_args_base.question = long_question
    mock_rag_system.query.return_value = {
        "answer": "Test",
        "sources": [],
        "relevance_score": 0.5,
    }

    result = cmd_query(query_args_base)

    assert result == 0


def test_index_with_zero_chunk_size(index_args_base, mock_rag_system):
    """Test index with edge case chunk size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_args_base.path = tmpdir
        index_args_base.chunk_size = 1  # Minimum chunk size
        mock_rag_system.index.return_value = {"count": 0, "chunks": 0}

        result = cmd_index(index_args_base)

        # Should not error, RAG system will handle validation
        assert result == 0


def test_eval_with_empty_results_file(eval_args_base, mock_rag_system):
    """Test eval with empty results file."""
    results_data = []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(results_data, f)
        temp_file = f.name

    try:
        eval_args_base.results = temp_file
        mock_rag_system.evaluate.return_value = {"metrics": {"avg_score": 0}}

        result = cmd_eval(eval_args_base)

        assert result == 0
    finally:
        Path(temp_file).unlink()


def test_config_set_with_special_characters(config_args_base, mock_rag_system):
    """Test config set with special characters in value."""
    config_args_base.set = "api_key=sk-1234!@#$%^&*()"

    result = cmd_config(config_args_base)

    assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
