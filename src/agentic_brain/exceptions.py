"""Custom exceptions with debugging context.

Provides actionable error messages with:
- Clear problem description
- Root cause analysis
- Suggested fixes
- Debug context for troubleshooting
"""
from typing import Optional, Dict, Any


class AgenticBrainError(Exception):
    """Base exception with actionable debugging information."""
    
    def __init__(
        self,
        message: str,
        cause: Optional[str] = None,
        fix: Optional[str] = None,
        debug_info: Optional[Dict[str, Any]] = None,
    ):
        """Initialize exception with debugging context.
        
        Args:
            message: User-friendly error description
            cause: Root cause analysis
            fix: Suggested fix or action
            debug_info: Additional debug information
        """
        self.message = message
        self.cause = cause
        self.fix = fix
        self.debug_info = debug_info or {}
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """Format exception message with debugging context."""
        parts = [f"❌ {self.message}"]
        if self.cause:
            parts.append(f"  └─ Cause: {self.cause}")
        if self.fix:
            parts.append(f"  └─ Fix: {self.fix}")
        if self.debug_info:
            parts.append(f"  └─ Debug: {self.debug_info}")
        return "\n".join(parts)


class Neo4jConnectionError(AgenticBrainError):
    """Failed to connect to Neo4j database.
    
    This error occurs when the Neo4j connection cannot be established.
    Common causes:
    - Neo4j is not running
    - Wrong connection URI
    - Authentication failed
    - Network issues
    """
    
    def __init__(self, uri: str, original_error: Optional[Exception] = None):
        super().__init__(
            message="Failed to connect to Neo4j database",
            cause=str(original_error) if original_error else "Connection refused",
            fix=f"✓ Check Neo4j is running at {uri}\n"
                f"✓ Try: docker run -d -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest\n"
                f"✓ Verify credentials and URI format",
            debug_info={"uri": uri, "error_type": type(original_error).__name__},
        )


class LLMProviderError(AgenticBrainError):
    """LLM provider failed to respond.
    
    This error occurs when an LLM provider (OpenAI, Anthropic, Ollama, etc.)
    cannot process the request. Common causes:
    - API key not set or invalid
    - Rate limit exceeded
    - Model not available
    - Network connectivity issues
    - Service is down
    """
    
    def __init__(self, provider: str, model: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"LLM provider '{provider}' failed",
            cause=str(original_error) if original_error else "No response from provider",
            fix=self._get_fix(provider),
            debug_info={"provider": provider, "model": model, "error_type": type(original_error).__name__},
        )
    
    @staticmethod
    def _get_fix(provider: str) -> str:
        """Get provider-specific troubleshooting steps."""
        fixes = {
            "ollama": "✓ Check Ollama is running: ollama serve\n"
                     "✓ Pull model: ollama pull llama3.2\n"
                     "✓ Verify at http://localhost:11434/api/tags",
            "openai": "✓ Set OPENAI_API_KEY environment variable\n"
                     "✓ Verify key at platform.openai.com/account/api-keys\n"
                     "✓ Check billing and usage at https://platform.openai.com/account/billing/overview",
            "anthropic": "✓ Set ANTHROPIC_API_KEY environment variable\n"
                        "✓ Verify key at console.anthropic.com/account/keys\n"
                        "✓ Check usage limits",
            "openrouter": "✓ Set OPENROUTER_API_KEY environment variable\n"
                         "✓ Create key at openrouter.ai/keys\n"
                         "✓ Check credits and usage at openrouter.ai",
        }
        default = f"✓ Set {provider.upper()}_API_KEY environment variable\n✓ Verify credentials are correct"
        return fixes.get(provider, default)


class MemoryError(AgenticBrainError):
    """Memory operation failed.
    
    This error occurs when Neo4j memory operations fail. Common causes:
    - Database connection lost
    - Invalid query
    - Data corruption
    - Session expired
    """
    
    def __init__(self, operation: str, key: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Memory {operation} failed for key '{key}'",
            cause=str(original_error) if original_error else "Unknown memory error",
            fix="✓ Check Neo4j connection (see Neo4jConnectionError)\n"
                "✓ Verify Neo4j is responding: curl bolt://localhost:7687\n"
                "✓ Check network connectivity",
            debug_info={"operation": operation, "key": key, "error_type": type(original_error).__name__},
        )


class TransportError(AgenticBrainError):
    """Transport layer error.
    
    This error occurs during data transport operations. Common causes:
    - Network connection lost
    - Invalid endpoint
    - Authentication failed
    - Serialization error
    """
    
    def __init__(self, transport: str, operation: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Transport '{transport}' {operation} failed",
            cause=str(original_error) if original_error else "Connection lost",
            fix="✓ Check network connectivity\n"
                "✓ Verify transport configuration\n"
                "✓ For Firebase: verify credentials in ~/.firebase or GOOGLE_APPLICATION_CREDENTIALS",
            debug_info={"transport": transport, "operation": operation, "error_type": type(original_error).__name__},
        )


class ConfigurationError(AgenticBrainError):
    """Configuration is invalid or missing.
    
    This error occurs when required configuration is not found or invalid.
    Common causes:
    - Missing environment variable
    - Invalid configuration format
    - Missing .env file
    - Invalid file path
    """
    
    def __init__(self, config_key: str, expected: str, example: Optional[str] = None):
        fix_parts = [f"✓ Set {config_key} in .env or environment"]
        if example:
            fix_parts.append(f"✓ Example: {config_key}={example}")
        fix_parts.append("✓ See .env.example for configuration format")
        
        super().__init__(
            message=f"Invalid configuration: {config_key}",
            cause=f"Expected {expected}",
            fix="\n".join(fix_parts),
            debug_info={"key": config_key, "expected": expected},
        )


class RateLimitError(AgenticBrainError):
    """Rate limit exceeded.
    
    This error occurs when API rate limits are exceeded.
    Common causes:
    - Too many requests in short time
    - Quota exceeded
    - Plan limits reached
    """
    
    def __init__(self, limit: int, window: str, retry_after: Optional[int] = None):
        retry_seconds = retry_after or 60
        super().__init__(
            message="Rate limit exceeded",
            cause=f"More than {limit} requests per {window}",
            fix=f"✓ Wait at least {retry_seconds} seconds before retrying\n"
                "✓ Implement exponential backoff for retries\n"
                "✓ Consider upgrading your plan or API tier",
            debug_info={"limit": limit, "window": window, "retry_after": retry_seconds},
        )


class SessionError(AgenticBrainError):
    """Session management error.
    
    This error occurs when session operations fail. Common causes:
    - Session expired
    - Invalid session ID
    - Session not found
    - Concurrent modification
    """
    
    def __init__(self, session_id: str, reason: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Session error: {reason}",
            cause=f"Session '{session_id}' operation failed",
            fix="✓ Create a new session with valid parameters\n"
                "✓ Check session_id is in correct format (UUID)\n"
                "✓ Verify session hasn't expired",
            debug_info={"session_id": session_id, "error_type": type(original_error).__name__},
        )


class ValidationError(AgenticBrainError):
    """Input validation failed.
    
    This error occurs when input doesn't meet requirements. Common causes:
    - Missing required fields
    - Invalid data type
    - Out of range values
    - Format mismatch
    """
    
    def __init__(self, field: str, expected: str, got: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Validation failed for '{field}'",
            cause=f"Expected {expected}, got {got}",
            fix=f"✓ Check {field} is {expected}\n"
                "✓ Verify data format matches schema\n"
                "✓ See documentation for valid values",
            debug_info={"field": field, "expected": expected, "got": got},
        )


class TimeoutError(AgenticBrainError):
    """Operation timed out.
    
    This error occurs when operations exceed time limits. Common causes:
    - Network is slow
    - Service is unresponsive
    - Timeout value too low
    - Server overloaded
    """
    
    def __init__(self, operation: str, timeout_seconds: int, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Operation '{operation}' timed out",
            cause=f"No response within {timeout_seconds} seconds",
            fix=f"✓ Check network connectivity\n"
                f"✓ Verify service is running\n"
                f"✓ Increase timeout (currently {timeout_seconds}s)\n"
                "✓ Check server logs for issues",
            debug_info={"operation": operation, "timeout": timeout_seconds, "error_type": type(original_error).__name__},
        )


class APIError(AgenticBrainError):
    """API request failed.
    
    This error occurs when API calls fail. Common causes:
    - Invalid request
    - Server error
    - Authentication failed
    - Bad response format
    """
    
    def __init__(self, endpoint: str, status_code: int, response: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"API call failed to {endpoint}",
            cause=f"HTTP {status_code}: {response}",
            fix="✓ Check endpoint URL is correct\n"
                "✓ Verify request format and parameters\n"
                "✓ Check authentication credentials\n"
                "✓ See API documentation for error codes",
            debug_info={"endpoint": endpoint, "status_code": status_code},
        )


class ModelNotFoundError(AgenticBrainError):
    """Model not found or unavailable.
    
    This error occurs when a requested model is not available. Common causes:
    - Model not installed
    - Model name wrong
    - Model not supported by provider
    - Model is deprecated
    """
    
    def __init__(self, model: str, provider: str, available: Optional[list] = None):
        available_str = ", ".join(available) if available else "See provider documentation"
        super().__init__(
            message=f"Model '{model}' not found in {provider}",
            cause="Model is not available in this provider",
            fix=f"✓ Available models: {available_str}\n"
                f"✓ For Ollama: ollama pull {model}\n"
                "✓ Check model name spelling",
            debug_info={"model": model, "provider": provider, "available": available},
        )
