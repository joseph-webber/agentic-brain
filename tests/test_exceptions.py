"""Comprehensive tests for custom exceptions with actionable error messages.

Tests verify that all exception types provide clear, helpful debugging information.
"""
import pytest
from agentic_brain.exceptions import (
    AgenticBrainError,
    Neo4jConnectionError,
    LLMProviderError,
    MemoryError,
    TransportError,
    ConfigurationError,
    RateLimitError,
    SessionError,
    ValidationError,
    TimeoutError as AgenticTimeoutError,
    APIError,
    ModelNotFoundError,
)


class TestAgenticBrainError:
    """Tests for base exception class."""
    
    def test_base_exception_with_all_fields(self):
        """Test exception with all debugging information."""
        exc = AgenticBrainError(
            message="Test error",
            cause="Root cause analysis",
            fix="Suggested fix",
            debug_info={"key": "value"}
        )
        
        msg = str(exc)
        assert "❌ Test error" in msg
        assert "Cause: Root cause analysis" in msg
        assert "Fix: Suggested fix" in msg
        assert "Debug: {'key': 'value'}" in msg
    
    def test_base_exception_with_minimal_fields(self):
        """Test exception with only required message."""
        exc = AgenticBrainError(message="Simple error")
        msg = str(exc)
        assert "❌ Simple error" in msg
        assert "Cause:" not in msg
        assert "Fix:" not in msg
    
    def test_exception_attributes_accessible(self):
        """Test that exception attributes are accessible."""
        exc = AgenticBrainError(
            message="Test",
            cause="Cause",
            fix="Fix",
            debug_info={"key": "value"}
        )
        
        assert exc.message == "Test"
        assert exc.cause == "Cause"
        assert exc.fix == "Fix"
        assert exc.debug_info == {"key": "value"}
    
    def test_exception_is_catchable_as_exception(self):
        """Test that exceptions can be caught with generic Exception."""
        with pytest.raises(Exception):
            raise AgenticBrainError("test")


class TestNeo4jConnectionError:
    """Tests for Neo4j connection errors."""
    
    def test_neo4j_connection_error_with_original_error(self):
        """Test Neo4j connection error with original exception."""
        original = ConnectionError("Connection refused")
        exc = Neo4jConnectionError("bolt://localhost:7687", original)
        
        msg = str(exc)
        assert "Failed to connect to Neo4j database" in msg
        assert "bolt://localhost:7687" in msg
        assert "Connection refused" in msg
        assert "docker run" in msg
    
    def test_neo4j_connection_error_without_original_error(self):
        """Test Neo4j connection error without original exception."""
        exc = Neo4jConnectionError("bolt://localhost:7687")
        
        msg = str(exc)
        assert "Failed to connect to Neo4j database" in msg
        assert "docker run" in msg
    
    def test_neo4j_debug_info(self):
        """Test that debug info includes URI."""
        exc = Neo4jConnectionError("bolt://localhost:7687")
        assert exc.debug_info["uri"] == "bolt://localhost:7687"


class TestLLMProviderError:
    """Tests for LLM provider errors."""
    
    def test_ollama_provider_error(self):
        """Test error message for Ollama provider."""
        exc = LLMProviderError("ollama", "llama3.2:3b")
        msg = str(exc)
        assert "ollama" in msg
        assert "ollama serve" in msg
        assert "ollama pull" in msg
    
    def test_openai_provider_error(self):
        """Test error message for OpenAI provider."""
        exc = LLMProviderError("openai", "gpt-4o")
        msg = str(exc)
        assert "openai" in msg
        assert "OPENAI_API_KEY" in msg
        assert "platform.openai.com" in msg
    
    def test_anthropic_provider_error(self):
        """Test error message for Anthropic provider."""
        exc = LLMProviderError("anthropic", "claude-3-sonnet")
        msg = str(exc)
        assert "anthropic" in msg
        assert "ANTHROPIC_API_KEY" in msg
        assert "console.anthropic.com" in msg
    
    def test_openrouter_provider_error(self):
        """Test error message for OpenRouter provider."""
        exc = LLMProviderError("openrouter", "meta-llama/llama-3-8b")
        msg = str(exc)
        assert "openrouter" in msg
        assert "OPENROUTER_API_KEY" in msg
        assert "openrouter.ai" in msg
    
    def test_unknown_provider_error(self):
        """Test error message for unknown provider."""
        exc = LLMProviderError("unknown", "model")
        msg = str(exc)
        assert "unknown" in msg
        assert "UNKNOWN_API_KEY" in msg
    
    def test_llm_provider_error_with_original_error(self):
        """Test LLM provider error with original exception."""
        original = ValueError("Invalid API key")
        exc = LLMProviderError("openai", "gpt-4o", original)
        msg = str(exc)
        assert "Invalid API key" in msg
    
    def test_llm_provider_debug_info(self):
        """Test that debug info includes provider and model."""
        exc = LLMProviderError("ollama", "llama3.2:3b")
        assert exc.debug_info["provider"] == "ollama"
        assert exc.debug_info["model"] == "llama3.2:3b"


class TestMemoryError:
    """Tests for memory operation errors."""
    
    def test_memory_read_error(self):
        """Test memory read operation error."""
        exc = MemoryError("read", "session:123")
        msg = str(exc)
        assert "Memory read failed" in msg
        assert "session:123" in msg
        assert "Neo4j" in msg
    
    def test_memory_write_error(self):
        """Test memory write operation error."""
        exc = MemoryError("write", "memory:456")
        msg = str(exc)
        assert "Memory write failed" in msg
        assert "memory:456" in msg
    
    def test_memory_error_with_original_error(self):
        """Test memory error with original exception."""
        original = Exception("Connection lost")
        exc = MemoryError("delete", "key", original)
        msg = str(exc)
        assert "Connection lost" in msg
    
    def test_memory_debug_info(self):
        """Test that debug info includes operation and key."""
        exc = MemoryError("write", "my_key")
        assert exc.debug_info["operation"] == "write"
        assert exc.debug_info["key"] == "my_key"


class TestTransportError:
    """Tests for transport layer errors."""
    
    def test_firebase_transport_error(self):
        """Test Firebase transport error."""
        exc = TransportError("firebase", "upload")
        msg = str(exc)
        assert "firebase" in msg
        assert "upload" in msg
        assert "GOOGLE_APPLICATION_CREDENTIALS" in msg
    
    def test_websocket_transport_error(self):
        """Test WebSocket transport error."""
        exc = TransportError("websocket", "connect")
        msg = str(exc)
        assert "websocket" in msg
        assert "connect" in msg
    
    def test_transport_error_with_original_error(self):
        """Test transport error with original exception."""
        original = OSError("Network unreachable")
        exc = TransportError("http", "request", original)
        msg = str(exc)
        assert "Network unreachable" in msg
    
    def test_transport_debug_info(self):
        """Test that debug info includes transport and operation."""
        exc = TransportError("ftp", "upload")
        assert exc.debug_info["transport"] == "ftp"
        assert exc.debug_info["operation"] == "upload"


class TestConfigurationError:
    """Tests for configuration errors."""
    
    def test_configuration_error_basic(self):
        """Test basic configuration error."""
        exc = ConfigurationError("DATABASE_URL", "valid database connection string")
        msg = str(exc)
        assert "DATABASE_URL" in msg
        assert "database connection string" in msg
        assert ".env" in msg
    
    def test_configuration_error_with_example(self):
        """Test configuration error with example."""
        exc = ConfigurationError(
            "API_KEY",
            "32-character hex string",
            "a1b2c3d4e5f6..."
        )
        msg = str(exc)
        assert "API_KEY" in msg
        assert "32-character hex string" in msg
        assert "a1b2c3d4e5f6..." in msg
    
    def test_configuration_debug_info(self):
        """Test that debug info includes key and expected format."""
        exc = ConfigurationError("SECRET", "valid JWT secret")
        assert exc.debug_info["key"] == "SECRET"
        assert exc.debug_info["expected"] == "valid JWT secret"


class TestRateLimitError:
    """Tests for rate limit errors."""
    
    def test_rate_limit_error_basic(self):
        """Test basic rate limit error."""
        exc = RateLimitError(100, "minute")
        msg = str(exc)
        assert "Rate limit exceeded" in msg
        assert "100" in msg
        assert "minute" in msg
        assert "60" in msg  # Default retry_after
    
    def test_rate_limit_error_with_retry_after(self):
        """Test rate limit error with retry_after."""
        exc = RateLimitError(50, "hour", retry_after=300)
        msg = str(exc)
        assert "300" in msg  # Retry after value
        assert "exponential backoff" in msg
    
    def test_rate_limit_debug_info(self):
        """Test that debug info includes limit and window."""
        exc = RateLimitError(1000, "day", retry_after=3600)
        assert exc.debug_info["limit"] == 1000
        assert exc.debug_info["window"] == "day"
        assert exc.debug_info["retry_after"] == 3600


class TestSessionError:
    """Tests for session management errors."""
    
    def test_session_error_basic(self):
        """Test basic session error."""
        exc = SessionError("sess_123", "Session expired")
        msg = str(exc)
        assert "Session error: Session expired" in msg
        assert "sess_123" in msg
        assert "new session" in msg
    
    def test_session_error_not_found(self):
        """Test session not found error."""
        exc = SessionError("nonexistent", "Not found")
        msg = str(exc)
        assert "Not found" in msg
    
    def test_session_error_with_original_error(self):
        """Test session error with original exception."""
        original = KeyError("Session key not found")
        exc = SessionError("sess_456", "Concurrent modification", original)
        msg = str(exc)
        assert "Concurrent modification" in msg
    
    def test_session_debug_info(self):
        """Test that debug info includes session_id."""
        exc = SessionError("my_session", "error")
        assert exc.debug_info["session_id"] == "my_session"


class TestValidationError:
    """Tests for input validation errors."""
    
    def test_validation_error_type_mismatch(self):
        """Test validation error for type mismatch."""
        exc = ValidationError("user_id", "UUID string", "123")
        msg = str(exc)
        assert "user_id" in msg
        assert "UUID string" in msg
        assert "123" in msg
    
    def test_validation_error_missing_field(self):
        """Test validation error for missing field."""
        exc = ValidationError("email", "valid email address", "null")
        msg = str(exc)
        assert "email" in msg
        assert "valid email address" in msg
    
    def test_validation_error_with_original_error(self):
        """Test validation error with original exception."""
        original = ValueError("Invalid format")
        exc = ValidationError("timestamp", "ISO 8601 format", "2024-13-45", original)
        msg = str(exc)
        assert "timestamp" in msg
        assert "2024-13-45" in msg
        # Verify debug info includes the field
        assert exc.debug_info["field"] == "timestamp"
    
    def test_validation_debug_info(self):
        """Test that debug info includes field and expected/got."""
        exc = ValidationError("age", "integer >= 0", "-5")
        assert exc.debug_info["field"] == "age"
        assert exc.debug_info["expected"] == "integer >= 0"
        assert exc.debug_info["got"] == "-5"


class TestAgenticTimeoutError:
    """Tests for timeout errors."""
    
    def test_timeout_error_basic(self):
        """Test basic timeout error."""
        exc = AgenticTimeoutError("database query", 30)
        msg = str(exc)
        assert "database query" in msg
        assert "30 seconds" in msg
        assert "network connectivity" in msg
    
    def test_timeout_error_with_original_error(self):
        """Test timeout error with original exception."""
        original = TimeoutError("Connection timed out")
        exc = AgenticTimeoutError("API request", 60, original)
        msg = str(exc)
        assert "API request" in msg
        assert "60 seconds" in msg
    
    def test_timeout_debug_info(self):
        """Test that debug info includes operation and timeout."""
        exc = AgenticTimeoutError("fetch", 120)
        assert exc.debug_info["operation"] == "fetch"
        assert exc.debug_info["timeout"] == 120


class TestAPIError:
    """Tests for API request errors."""
    
    def test_api_error_404(self):
        """Test 404 Not Found error."""
        exc = APIError("/api/users/123", 404, "Not Found")
        msg = str(exc)
        assert "/api/users/123" in msg
        assert "404" in msg
        assert "Not Found" in msg
    
    def test_api_error_500(self):
        """Test 500 Internal Server Error."""
        exc = APIError("/api/process", 500, "Internal Server Error")
        msg = str(exc)
        assert "/api/process" in msg
        assert "500" in msg
    
    def test_api_error_with_original_error(self):
        """Test API error with original exception."""
        original = Exception("Connection reset")
        exc = APIError("https://api.example.com/data", 503, "Service Unavailable", original)
        msg = str(exc)
        assert "https://api.example.com/data" in msg
        assert "503" in msg
    
    def test_api_debug_info(self):
        """Test that debug info includes endpoint and status code."""
        exc = APIError("https://api.example.com/v1/items", 401, "Unauthorized")
        assert exc.debug_info["endpoint"] == "https://api.example.com/v1/items"
        assert exc.debug_info["status_code"] == 401


class TestModelNotFoundError:
    """Tests for model not found errors."""
    
    def test_model_not_found_ollama(self):
        """Test model not found error for Ollama."""
        exc = ModelNotFoundError("llama3.2:custom", "ollama")
        msg = str(exc)
        assert "llama3.2:custom" in msg
        assert "ollama" in msg
        assert "ollama pull" in msg
    
    def test_model_not_found_openai(self):
        """Test model not found error for OpenAI."""
        exc = ModelNotFoundError("gpt-5", "openai", ["gpt-4o", "gpt-4-turbo"])
        msg = str(exc)
        assert "gpt-5" in msg
        assert "openai" in msg
        assert "gpt-4o" in msg
        assert "gpt-4-turbo" in msg
    
    def test_model_not_found_without_available_list(self):
        """Test model not found error without available models list."""
        exc = ModelNotFoundError("unknown-model", "anthropic")
        msg = str(exc)
        assert "unknown-model" in msg
        assert "documentation" in msg
    
    def test_model_not_found_debug_info(self):
        """Test that debug info includes model and provider."""
        exc = ModelNotFoundError("custom-model", "provider", ["model1", "model2"])
        assert exc.debug_info["model"] == "custom-model"
        assert exc.debug_info["provider"] == "provider"
        assert exc.debug_info["available"] == ["model1", "model2"]


class TestExceptionFormatting:
    """Tests for exception message formatting."""
    
    def test_formatting_with_special_characters(self):
        """Test that special characters are preserved in messages."""
        exc = AgenticBrainError(
            message="Error with 'quotes' and \"double quotes\"",
            fix="Use --flag='value' in command"
        )
        msg = str(exc)
        assert "quotes" in msg
        assert "--flag" in msg
    
    def test_formatting_with_unicode(self):
        """Test that unicode characters are preserved."""
        exc = AgenticBrainError(
            message="Erreur avec caractères spéciaux: éàü",
            fix="Vérifiez la configuration"
        )
        msg = str(exc)
        assert "éàü" in msg
        assert "Vérifiez" in msg
    
    def test_formatting_with_multiline_fix(self):
        """Test that multiline fixes are properly formatted."""
        exc = LLMProviderError("ollama", "llama3.2:3b")
        msg = str(exc)
        assert "\n" in msg  # Contains newlines
        assert "✓" in msg  # Contains checkmarks


class TestExceptionInheritance:
    """Tests for exception inheritance and hierarchy."""
    
    def test_all_custom_exceptions_inherit_from_agentic_brain_error(self):
        """Test that all custom exceptions inherit from base."""
        exceptions = [
            Neo4jConnectionError("uri"),
            LLMProviderError("provider", "model"),
            MemoryError("op", "key"),
            TransportError("trans", "op"),
            ConfigurationError("key", "expected"),
            RateLimitError(10, "minute"),
            SessionError("id", "reason"),
            ValidationError("field", "expected", "got"),
            AgenticTimeoutError("op", 30),
            APIError("endpoint", 500, "error"),
            ModelNotFoundError("model", "provider"),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, AgenticBrainError)
            assert isinstance(exc, Exception)
    
    def test_exception_can_be_raised_and_caught(self):
        """Test that exceptions can be raised and caught properly."""
        with pytest.raises(AgenticBrainError):
            raise LLMProviderError("test", "model")
        
        with pytest.raises(Exception):
            raise ConfigurationError("key", "expected")


class TestExceptionMessages:
    """Tests for exception message quality and actionability."""
    
    def test_all_exceptions_have_actionable_fixes(self):
        """Test that all exceptions contain actionable fix suggestions."""
        exceptions_with_fixes = [
            Neo4jConnectionError("uri"),
            LLMProviderError("ollama", "model"),
            MemoryError("op", "key"),
            TransportError("trans", "op"),
            ConfigurationError("key", "expected", "example"),
            RateLimitError(10, "minute"),
            SessionError("id", "reason"),
            ValidationError("field", "expected", "got"),
            AgenticTimeoutError("op", 30),
            APIError("endpoint", 500, "error"),
            ModelNotFoundError("model", "provider"),
        ]
        
        for exc in exceptions_with_fixes:
            assert exc.fix is not None
            assert len(exc.fix) > 0
            # Check for actionable keywords
            assert any(keyword in exc.fix.lower() for keyword in ["check", "verify", "try", "set", "ensure", "✓"])
    
    def test_all_exceptions_contain_debug_info(self):
        """Test that all exceptions contain useful debug information."""
        exceptions_with_debug = [
            Neo4jConnectionError("bolt://localhost:7687"),
            LLMProviderError("ollama", "llama3.2:3b"),
            MemoryError("read", "session:123"),
            TransportError("firebase", "upload"),
            ConfigurationError("API_KEY", "string"),
            RateLimitError(100, "minute", 60),
            SessionError("sess_123", "error"),
            ValidationError("field", "type", "value"),
            AgenticTimeoutError("query", 30),
            APIError("endpoint", 500, "error"),
            ModelNotFoundError("model", "provider"),
        ]
        
        for exc in exceptions_with_debug:
            assert exc.debug_info is not None
            assert isinstance(exc.debug_info, dict)
            assert len(exc.debug_info) > 0
