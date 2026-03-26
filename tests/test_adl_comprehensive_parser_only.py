# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""
Comprehensive CI tests for ADL Parser (Agentic Definition Language).

Parser-only test suite (generator tests pending generator.py implementation):
- 30+ lexer and parser tests
- 10+ edge case tests
- Performance tests

Total: 50+ tests covering ADL parsing.
"""

import os
import tempfile
import time
from pathlib import Path

import pytest

from agentic_brain.adl import parse_adl, parse_adl_file
from agentic_brain.adl.parser import (
    ADLParseError,
    Block,
    Lexer,
    Parser,
    Token,
    TokenKind,
)

# =============================================================================
# PARSER TESTS (30+ tests)
# =============================================================================


class TestLexer:
    """Test tokenization of ADL source."""

    def test_lex_simple_tokens(self):
        """Test basic token recognition."""
        lexer = Lexer("{}")
        tokens = lexer.tokens()
        assert len(tokens) >= 2  # At least LBRACE, RBRACE (+ possibly NEWLINE, EOF)
        assert any(t.kind == TokenKind.LBRACE for t in tokens)
        assert any(t.kind == TokenKind.RBRACE for t in tokens)

    def test_lex_string_literal(self):
        """Test string literal tokenization."""
        lexer = Lexer('"hello world"')
        tokens = lexer.tokens()
        string_tokens = [t for t in tokens if t.kind == TokenKind.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "hello world"

    def test_lex_string_with_escapes(self):
        """Test string escape sequences."""
        lexer = Lexer(r'"hello\nworld\ttab"')
        tokens = lexer.tokens()
        string_tokens = [t for t in tokens if t.kind == TokenKind.STRING]
        assert string_tokens[0].value == "hello\nworld\ttab"

    def test_lex_unterminated_string_error(self):
        """Test error on unterminated string."""
        lexer = Lexer('"hello')
        with pytest.raises(ADLParseError, match="Unterminated string"):
            lexer.tokens()

    def test_lex_identifier(self):
        """Test identifier tokenization."""
        lexer = Lexer("myIdentifier")
        tokens = lexer.tokens()
        ident_tokens = [t for t in tokens if t.kind == TokenKind.IDENT]
        assert len(ident_tokens) == 1
        assert ident_tokens[0].value == "myIdentifier"

    def test_lex_identifier_with_dash_dot(self):
        """Test identifiers with dashes and dots (gpt-4, llama3.2)."""
        lexer = Lexer("gpt-4 llama3.2:8b")
        tokens = lexer.tokens()
        ident_tokens = [t for t in tokens if t.kind == TokenKind.IDENT]
        assert any(t.value == "gpt-4" for t in ident_tokens)
        assert any(t.value == "llama3.2:8b" for t in ident_tokens)

    def test_lex_integer(self):
        """Test integer tokenization."""
        lexer = Lexer("42")
        tokens = lexer.tokens()
        number_tokens = [t for t in tokens if t.kind == TokenKind.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == "42"

    def test_lex_float(self):
        """Test float tokenization."""
        lexer = Lexer("3.14159")
        tokens = lexer.tokens()
        number_tokens = [t for t in tokens if t.kind == TokenKind.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == "3.14159"

    def test_lex_list_tokens(self):
        """Test list bracket tokenization."""
        lexer = Lexer("[a, b, c]")
        tokens = lexer.tokens()
        assert any(t.kind == TokenKind.LBRACKET for t in tokens)
        assert any(t.kind == TokenKind.RBRACKET for t in tokens)
        assert any(t.kind == TokenKind.COMMA for t in tokens)

    def test_lex_comments(self):
        """Test comment handling."""
        lexer = Lexer("// This is a comment\nidentifier")
        tokens = lexer.tokens()
        # Comments should be skipped
        ident_tokens = [t for t in tokens if t.kind == TokenKind.IDENT]
        assert len(ident_tokens) == 1
        assert ident_tokens[0].value == "identifier"

    def test_lex_line_column_tracking(self):
        """Test accurate line/column tracking."""
        lexer = Lexer("line1\nline2")
        tokens = lexer.tokens()
        # Get identifier tokens only
        idents = [t for t in tokens if t.kind == TokenKind.IDENT]
        assert len(idents) == 2
        assert idents[0].line == 1
        assert idents[1].line == 2

    def test_lex_whitespace_handling(self):
        """Test whitespace is properly skipped."""
        lexer = Lexer("  \t\n  identifier  \n  ")
        tokens = lexer.tokens()
        ident_tokens = [t for t in tokens if t.kind == TokenKind.IDENT]
        assert len(ident_tokens) == 1

    def test_lex_unexpected_character_error(self):
        """Test error on unexpected character."""
        lexer = Lexer("@#$%")
        with pytest.raises(ADLParseError, match="Unexpected character"):
            lexer.tokens()


class TestParser:
    """Test ADL parsing."""

    def test_parse_empty_file(self):
        """Test parsing empty ADL file.

        ADL applies sensible defaults, so even an empty file produces a runnable
        configuration.
        """
        config = parse_adl("")
        assert config.application is not None
        assert config.application.values["name"]
        assert "Primary" in config.llms
        assert "REST" in config.apis
        assert config.security is not None

    def test_parse_application_block(self):
        """Test parsing application block."""
        adl = """
        application MyApp {
            name "Test Application"
            version "1.0.0"
        }
        """
        config = parse_adl(adl)
        assert config.application is not None
        assert config.application.values["name"] == "Test Application"
        assert config.application.values["version"] == "1.0.0"

    def test_parse_llm_block_requires_name(self):
        """Test that llm block requires a name."""
        adl = """
        llm {
            provider OpenAI
        }
        """
        with pytest.raises(ADLParseError, match="llm block requires a name"):
            parse_adl(adl)

    def test_parse_llm_block_with_name(self):
        """Test parsing named llm block."""
        adl = """
        llm GPT4 {
            provider OpenAI
            model gpt-4
            temperature 0.7
        }
        """
        config = parse_adl(adl)
        assert "GPT4" in config.llms
        assert config.llms["GPT4"].values["provider"] == "OpenAI"
        assert config.llms["GPT4"].values["model"] == "gpt-4"
        assert config.llms["GPT4"].values["temperature"] == 0.7

    def test_parse_multiple_llm_blocks(self):
        """Test parsing multiple LLM blocks."""
        adl = """
        llm GPT4 {
            provider OpenAI
            model gpt-4
        }
        llm Claude {
            provider Anthropic
            model claude-3-opus
        }
        """
        config = parse_adl(adl)
        assert len(config.llms) == 2
        assert "GPT4" in config.llms
        assert "Claude" in config.llms

    def test_parse_rag_block(self):
        """Test parsing RAG block."""
        adl = """
        rag MyRAG {
            vectorStore Neo4j
            embeddingModel all-MiniLM-L6-v2
            chunkSize 512
            chunkOverlap 50
        }
        """
        config = parse_adl(adl)
        assert "MyRAG" in config.rags
        rag = config.rags["MyRAG"].values
        assert rag["vectorStore"] == "Neo4j"
        assert rag["chunkSize"] == 512
        assert rag["chunkOverlap"] == 50

    def test_parse_voice_block(self):
        """Test parsing voice block."""
        adl = """
        voice MyVoice {
            provider system
            defaultVoice Samantha
            rate 175
        }
        """
        config = parse_adl(adl)
        assert "MyVoice" in config.voices
        voice = config.voices["MyVoice"].values
        assert voice["provider"] == "system"
        assert voice["defaultVoice"] == "Samantha"
        assert voice["rate"] == 175

    def test_parse_api_block(self):
        """Test parsing API block."""
        adl = """
        api MyAPI {
            port 8000
            cors ["http://localhost:3000", "https://example.com"]
        }
        """
        config = parse_adl(adl)
        assert "MyAPI" in config.apis
        api = config.apis["MyAPI"].values
        assert api["port"] == 8000
        assert isinstance(api["cors"], list)
        assert len(api["cors"]) == 2

    def test_parse_list_values(self):
        """Test parsing list values."""
        adl = """
        application Test {
            tags ["ai", "brain", "rag"]
            numbers [1, 2, 3]
        }
        """
        config = parse_adl(adl)
        assert config.application.values["tags"] == ["ai", "brain", "rag"]
        assert config.application.values["numbers"] == [1, 2, 3]

    def test_parse_nested_block(self):
        """Test parsing nested blocks."""
        adl = """
        api MyAPI {
            rateLimit {
                requests 100
                window "1m"
            }
        }
        """
        config = parse_adl(adl)
        api = config.apis["MyAPI"].values
        assert "rateLimit" in api
        assert api["rateLimit"]["requests"] == 100
        assert api["rateLimit"]["window"] == "1m"

    def test_parse_security_block(self):
        """Test parsing security block (no name required)."""
        adl = """
        security {
            authentication JWT
            sso ["google", "github"]
        }
        """
        config = parse_adl(adl)
        assert config.security is not None
        assert config.security.values["authentication"] == "JWT"
        assert config.security.values["sso"] == ["google", "github"]

    def test_parse_modes_block(self):
        """Test parsing modes block."""
        adl = """
        modes {
            default production
            available ["development", "staging", "production"]
        }
        """
        config = parse_adl(adl)
        assert config.modes is not None
        assert config.modes.values["default"] == "production"

    def test_parse_deployment_block(self):
        """Test parsing deployment block."""
        adl = """
        deployment {
            type Docker
            replicas 3
        }
        """
        config = parse_adl(adl)
        assert config.deployment is not None
        assert config.deployment.values["type"] == "Docker"
        assert config.deployment.values["replicas"] == 3

    def test_parse_boolean_values(self):
        """Test parsing boolean values."""
        adl = """
        application Test {
            enabled true
            debug false
        }
        """
        config = parse_adl(adl)
        assert config.application.values["enabled"] is True
        assert config.application.values["debug"] is False

    def test_parse_comments_ignored(self):
        """Test that comments are properly ignored."""
        adl = """
        // This is a comment
        application Test { // inline comment
            name "Test" // another comment
        }
        // Final comment
        """
        config = parse_adl(adl)
        assert config.application is not None
        assert config.application.values["name"] == "Test"

    def test_parse_error_helpful_message(self):
        """Test error messages include line/column info."""
        adl = """
        application Test {
            name "Test"
        """  # Missing closing brace
        with pytest.raises(ADLParseError, match="line"):
            parse_adl(adl)

    def test_parse_unexpected_token_error(self):
        """Test error on unexpected token."""
        adl = """
        application Test {
            123
        }
        """
        with pytest.raises(ADLParseError):
            parse_adl(adl)

    def test_parse_complex_real_world_example(self):
        """Test parsing a complex real-world ADL file."""
        adl = """
        application BrainAI {
            name "Production Brain"
            version "2.0.0"
            license "Apache-2.0"
        }

        llm Primary {
            provider OpenAI
            model gpt-4o
            temperature 0.8
            maxTokens 4096
        }

        llm Fallback {
            provider Ollama
            model llama3.2:8b
            baseUrl "http://localhost:11434"
        }

        rag ProductionRAG {
            vectorStore Neo4j
            embeddingModel all-MiniLM-L6-v2
            chunkSize 512
            chunkOverlap 50
            loaders ["pdf", "markdown", "html"]
        }

        voice Assistant {
            provider system
            defaultVoice Karen
            rate 160
            region en-US
        }

        api REST {
            port 8080
            cors ["http://localhost:3000"]
            rateLimit {
                requests 100
                window "1m"
                burstLimit 150
            }
        }

        security {
            authentication JWT
            sso ["google", "github", "microsoft"]
            saml true
        }

        deployment {
            type Docker
            replicas 3
            composeVersion "3.8"
        }
        """
        config = parse_adl(adl)

        # Verify all blocks parsed
        assert config.application is not None
        assert len(config.llms) == 2
        assert len(config.rags) == 1
        assert len(config.voices) == 1
        assert len(config.apis) == 1
        assert config.security is not None
        assert config.deployment is not None

        # Verify specific values
        assert config.application.values["name"] == "Production Brain"
        assert config.llms["Primary"].values["model"] == "gpt-4o"
        assert config.rags["ProductionRAG"].values["chunkSize"] == 512
        assert len(config.security.values["sso"]) == 3


# =============================================================================
# EDGE CASE TESTS (10+ tests)
# =============================================================================


class TestEdgeCases:
    """Test edge cases and corner cases."""

    def test_empty_blocks(self):
        """Test parsing empty blocks."""
        adl = """
        application Test {
        }
        """
        config = parse_adl(adl)
        assert config.application is not None
        assert config.application.values["name"] == "Test"

    def test_unicode_in_strings(self):
        """Test unicode characters in string values."""
        adl = """
        application Test {
            name "智能大脑 🧠"
            description "AI Brain with émojis and 中文"
        }
        """
        config = parse_adl(adl)
        assert "🧠" in config.application.values["name"]
        assert "中文" in config.application.values["description"]

    def test_very_long_string(self):
        """Test handling very long string values."""
        long_string = "A" * 10000
        adl = f"""
        application Test {{
            longField "{long_string}"
        }}
        """
        config = parse_adl(adl)
        assert config.application.values["longField"] == long_string

    def test_deeply_nested_blocks(self):
        """Test deeply nested block structures."""
        adl = """
        api MyAPI {
            level1 {
                level2 {
                    level3 {
                        deepValue "nested"
                    }
                }
            }
        }
        """
        config = parse_adl(adl)
        api = config.apis["MyAPI"].values
        assert api["level1"]["level2"]["level3"]["deepValue"] == "nested"

    def test_special_characters_in_identifiers(self):
        """Test special characters allowed in identifiers."""
        adl = """
        llm gpt-4o-mini {
            model llama3.2:8b
            provider Ollama
        }
        """
        config = parse_adl(adl)
        assert "gpt-4o-mini" in config.llms

    def test_numbers_as_identifiers(self):
        """Test identifiers starting with letters but containing numbers."""
        adl = """
        llm Model123 {
            provider Ollama
        }
        """
        config = parse_adl(adl)
        assert "Model123" in config.llms
        assert config.llms["Model123"].values["provider"] == "Ollama"

    def test_large_numbers(self):
        """Test handling large integer and float values."""
        adl = """
        application Test {
            bigInt 999999999999
            bigFloat 3.141592653589793
        }
        """
        config = parse_adl(adl)
        assert config.application.values["bigInt"] == 999999999999
        assert isinstance(config.application.values["bigFloat"], float)

    def test_empty_lists(self):
        """Test empty list values."""
        adl = """
        application Test {
            emptyList []
        }
        """
        config = parse_adl(adl)
        assert config.application.values["emptyList"] == []

    def test_mixed_type_lists(self):
        """Test lists with mixed types."""
        adl = """
        application Test {
            mixed ["string", 123, 45.6, true]
        }
        """
        config = parse_adl(adl)
        lst = config.application.values["mixed"]
        assert lst[0] == "string"
        assert lst[1] == 123
        assert lst[2] == 45.6
        assert lst[3] is True

    def test_trailing_commas_in_lists(self):
        """Test lists with trailing commas."""
        adl = """
        application Test {
            tags ["a", "b", "c",]
        }
        """
        # Should parse successfully (trailing comma allowed)
        config = parse_adl(adl)
        assert len(config.application.values["tags"]) == 3

    def test_whitespace_variations(self):
        """Test various whitespace patterns."""
        adl = """
        application    Test   {
            name     "TestApp"
            version"1.0.0"
        }
        """
        config = parse_adl(adl)
        assert config.application.values["name"] == "TestApp"

    def test_multiple_comments_styles(self):
        """Test comment handling edge cases."""
        adl = """
        // Start comment
        application Test { // Inline comment
            name "TestApp" // End of line comment
            // Middle comment
        } // Final comment
        // Multiple
        // Sequential
        // Comments
        """
        config = parse_adl(adl)
        assert config.application.values["name"] == "TestApp"

    def test_parse_file_not_found(self):
        """Test parse_adl_file with non-existent file."""
        with pytest.raises(FileNotFoundError):
            parse_adl_file("/nonexistent/path.adl")

    def test_case_sensitivity(self):
        """Test case sensitivity in keywords and identifiers."""
        adl = """
        application TestApp {
            name "Test"
        }
        APPLICATION TestApp2 {
            name "Test2"
        }
        """
        # Keywords are case-insensitive, should parse both
        config = parse_adl(adl)
        # Only first should be stored (case-insensitive keyword matching)
        assert config.application is not None

    def test_boolean_case_variations(self):
        """Test boolean value case variations."""
        adl = """
        application Test {
            a true
            b True
            c TRUE
            d false
            e False
            f FALSE
        }
        """
        config = parse_adl(adl)
        vals = config.application.values
        assert vals["a"] is True
        assert vals["b"] is True
        assert vals["c"] is True
        assert vals["d"] is False
        assert vals["e"] is False
        assert vals["f"] is False

    def test_zero_values(self):
        """Test handling of zero values."""
        adl = """
        application Test {
            zeroInt 0
            zeroFloat 0.0
        }
        """
        config = parse_adl(adl)
        assert config.application.values["zeroInt"] == 0
        assert config.application.values["zeroFloat"] == 0.0

    def test_quotes_in_strings(self):
        """Test escaped quotes in strings."""
        adl = r"""
        application Test {
            quote "He said \"hello\""
        }
        """
        config = parse_adl(adl)
        assert config.application.values["quote"] == 'He said "hello"'


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestPerformance:
    """Test ADL performance characteristics."""

    def test_large_file_parsing(self):
        """Test parsing a large ADL file."""
        # Generate large ADL file
        blocks = []
        for i in range(100):
            blocks.append(
                f"""
            llm LLM{i} {{
                provider Ollama
                model model-{i}
                temperature 0.{i % 10}
            }}
            """
            )

        adl = "\n".join(blocks)

        start = time.time()
        config = parse_adl(adl)
        elapsed = time.time() - start

        assert len(config.llms) == 100
        # Should parse in reasonable time (< 1 second)
        assert elapsed < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
