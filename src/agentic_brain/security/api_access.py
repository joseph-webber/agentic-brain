# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
API-based access control for non-admin users.

This module implements Joseph's key insight: customer/user chatbots should ONLY
access external APIs (WordPress REST, WooCommerce REST, etc.), NOT have direct
machine access. Their permissions are controlled by the API's role system.

Security Model:
- ADMIN: Full machine access + API access
- USER/CUSTOMER: API access ONLY (no shell, no files, no YOLO)
- GUEST: Read-only API access (public endpoints only)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from .roles import SecurityRole


class APIScope(Enum):
    """Permission scopes for API access."""
    
    READ = "read"              # GET requests, read-only
    WRITE = "write"            # POST/PUT, create/update
    DELETE = "delete"          # DELETE requests
    ADMIN = "admin"            # Administrative operations
    PUBLIC = "public"          # Unauthenticated public access


class AuthType(Enum):
    """API authentication methods."""
    
    BEARER = "bearer"          # OAuth 2.0 Bearer token
    BASIC = "basic"            # HTTP Basic Auth
    API_KEY = "api_key"        # API key (header or query param)
    JWT = "jwt"                # JSON Web Token
    OAUTH2 = "oauth2"          # Full OAuth 2.0 flow
    WORDPRESS_APP = "wordpress_app"  # WordPress application password
    WOOCOMMERCE = "woocommerce"      # WooCommerce consumer key/secret


@dataclass
class APIEndpoint:
    """Configuration for an external API endpoint."""
    
    name: str                           # Unique identifier (e.g., "wordpress", "woocommerce")
    base_url: str                       # Base URL (e.g., "https://example.com/wp-json/wp/v2")
    auth_type: AuthType                 # Authentication method
    allowed_scopes: List[APIScope]      # What operations are permitted
    rate_limit: int                     # Requests per minute
    timeout: int = 30                   # Request timeout in seconds
    
    # Role mapping (API-specific roles)
    api_role: Optional[str] = None      # WordPress: subscriber/author/editor/admin
                                         # WooCommerce: customer/shop_manager/admin
    
    # Additional metadata
    description: str = ""
    requires_ssl: bool = True
    
    def __post_init__(self):
        """Validate configuration."""
        if self.requires_ssl and not self.base_url.startswith("https://"):
            raise ValueError(f"API endpoint {self.name} requires SSL but URL is not HTTPS")


@dataclass
class RateLimiter:
    """Simple rate limiter for API calls."""
    
    max_requests: int                   # Maximum requests per window
    window_seconds: int = 60            # Time window (default 1 minute)
    requests: List[float] = field(default_factory=list)  # Timestamps of requests
    
    def is_allowed(self) -> bool:
        """Check if a request is allowed under rate limit."""
        now = time.time()
        
        # Remove requests outside the window
        cutoff = now - self.window_seconds
        self.requests = [ts for ts in self.requests if ts > cutoff]
        
        # Check if under limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False
    
    def time_until_available(self) -> float:
        """Get seconds until next request is allowed."""
        if not self.requests:
            return 0.0
        
        oldest = min(self.requests)
        wait_time = (oldest + self.window_seconds) - time.time()
        return max(0.0, wait_time)


class SecurityViolation(Exception):
    """Raised when a security policy is violated."""
    pass


class APIAccessController:
    """
    Controls which APIs users can access based on their role.
    
    This is the core enforcement point for API-only access:
    - USER/CUSTOMER roles can ONLY make API calls, no machine access
    - API permissions are enforced through the external API's role system
    - Rate limiting prevents abuse
    - All access is logged
    """
    
    def __init__(self, role: SecurityRole):
        """
        Initialize API access controller.
        
        Args:
            role: Security role (ADMIN, USER, DEVELOPER, GUEST)
        """
        self.role = role
        self.allowed_apis: Dict[str, APIEndpoint] = {}
        self.api_keys: Dict[str, Dict[str, str]] = {}  # API name -> auth credentials
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.client: Optional[httpx.AsyncClient] = None
        
        # Access log for security auditing
        self.access_log: List[Dict[str, Any]] = []
    
    def register_api(
        self,
        endpoint: APIEndpoint,
        credentials: Dict[str, str]
    ) -> None:
        """
        Register an API that this user can access.
        
        Args:
            endpoint: API endpoint configuration
            credentials: Authentication credentials (varies by auth_type)
                - bearer: {"token": "..."}
                - basic: {"username": "...", "password": "..."}
                - api_key: {"key": "...", "header": "X-API-Key"} or {"key": "...", "param": "api_key"}
                - wordpress_app: {"username": "...", "password": "..."}
                - woocommerce: {"consumer_key": "...", "consumer_secret": "..."}
        
        Raises:
            SecurityViolation: If role doesn't permit API registration
        """
        # GUEST can only access pre-configured public APIs
        if self.role == SecurityRole.GUEST:
            if APIScope.PUBLIC not in endpoint.allowed_scopes:
                raise SecurityViolation("GUEST role can only access public APIs")
        
        self.allowed_apis[endpoint.name] = endpoint
        self.api_keys[endpoint.name] = credentials
        
        # Set up rate limiter
        self.rate_limiters[endpoint.name] = RateLimiter(
            max_requests=endpoint.rate_limit,
            window_seconds=60
        )
    
    def can_access(self, api_name: str, scope: APIScope) -> bool:
        """
        Check if user can access this API with given scope.
        
        Args:
            api_name: Name of the API
            scope: Required scope (READ, WRITE, DELETE, ADMIN)
        
        Returns:
            True if access is allowed
        """
        if api_name not in self.allowed_apis:
            return False
        
        endpoint = self.allowed_apis[api_name]
        
        # Check scope
        if scope not in endpoint.allowed_scopes:
            return False
        
        # GUEST can only use PUBLIC scope
        if self.role == SecurityRole.GUEST and scope != APIScope.PUBLIC:
            return False
        
        return True
    
    def _method_to_scope(self, method: str) -> APIScope:
        """Convert HTTP method to API scope."""
        method = method.upper()
        
        if method == "GET":
            return APIScope.READ
        elif method in ("POST", "PUT", "PATCH"):
            return APIScope.WRITE
        elif method == "DELETE":
            return APIScope.DELETE
        else:
            return APIScope.READ  # Default to most restrictive
    
    def _build_auth_headers(
        self,
        endpoint: APIEndpoint,
        credentials: Dict[str, str]
    ) -> Dict[str, str]:
        """Build authentication headers for the API call."""
        headers = {}
        
        if endpoint.auth_type == AuthType.BEARER:
            headers["Authorization"] = f"Bearer {credentials['token']}"
        
        elif endpoint.auth_type == AuthType.BASIC:
            import base64
            auth_str = f"{credentials['username']}:{credentials['password']}"
            b64 = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {b64}"
        
        elif endpoint.auth_type == AuthType.API_KEY:
            if "header" in credentials:
                headers[credentials["header"]] = credentials["key"]
        
        elif endpoint.auth_type == AuthType.WORDPRESS_APP:
            import base64
            auth_str = f"{credentials['username']}:{credentials['password']}"
            b64 = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {b64}"
        
        elif endpoint.auth_type == AuthType.JWT:
            headers["Authorization"] = f"Bearer {credentials['token']}"
        
        return headers
    
    async def call_api(
        self,
        api_name: str,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Make an API call on behalf of the user.
        
        This is the ONLY way non-admin users interact with external systems.
        No shell access, no file system access - just API calls.
        
        Args:
            api_name: Name of the registered API
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: API path (relative to base_url)
            params: Query parameters
            data: Form data
            json: JSON body
            headers: Additional headers
        
        Returns:
            httpx.Response object
        
        Raises:
            SecurityViolation: If access is denied
            httpx.HTTPError: If API call fails
        """
        # Check if API is registered
        if api_name not in self.allowed_apis:
            raise SecurityViolation(f"API '{api_name}' not registered for this user")
        
        endpoint = self.allowed_apis[api_name]
        scope = self._method_to_scope(method)
        
        # Check permissions
        if not self.can_access(api_name, scope):
            raise SecurityViolation(
                f"Access denied to {api_name} with scope {scope.value}"
            )
        
        # Check rate limit
        rate_limiter = self.rate_limiters[api_name]
        if not rate_limiter.is_allowed():
            wait_time = rate_limiter.time_until_available()
            raise SecurityViolation(
                f"Rate limit exceeded for {api_name}. "
                f"Try again in {wait_time:.1f} seconds."
            )
        
        # Build full URL
        url = f"{endpoint.base_url.rstrip('/')}/{path.lstrip('/')}"
        
        # Build authentication headers
        auth_headers = self._build_auth_headers(
            endpoint,
            self.api_keys[api_name]
        )
        
        # Merge headers
        all_headers = {**auth_headers, **(headers or {})}
        
        # Special handling for WooCommerce (uses query params for auth)
        if endpoint.auth_type == AuthType.WOOCOMMERCE:
            creds = self.api_keys[api_name]
            if params is None:
                params = {}
            params.update({
                "consumer_key": creds["consumer_key"],
                "consumer_secret": creds["consumer_secret"]
            })
        
        # Create client if needed
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=endpoint.timeout)
        
        # Log the access attempt
        log_entry = {
            "timestamp": time.time(),
            "role": self.role.value,
            "api": api_name,
            "method": method,
            "path": path,
            "scope": scope.value,
        }
        
        try:
            # Make the API call
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                headers=all_headers,
            )
            
            # Log success
            log_entry["status"] = response.status_code
            log_entry["success"] = True
            
            return response
        
        except Exception as e:
            # Log failure
            log_entry["error"] = str(e)
            log_entry["success"] = False
            raise
        
        finally:
            self.access_log.append(log_entry)
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def get_access_log(
        self,
        api_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get access log entries.
        
        Args:
            api_name: Filter by API name (optional)
            limit: Maximum entries to return
        
        Returns:
            List of log entries (most recent first)
        """
        logs = self.access_log
        
        if api_name:
            logs = [log for log in logs if log["api"] == api_name]
        
        return logs[-limit:][::-1]  # Most recent first
    
    def get_registered_apis(self) -> List[str]:
        """Get list of registered API names."""
        return list(self.allowed_apis.keys())
    
    def get_api_info(self, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a registered API.
        
        Returns:
            API info dict or None if not registered
        """
        if api_name not in self.allowed_apis:
            return None
        
        endpoint = self.allowed_apis[api_name]
        
        return {
            "name": endpoint.name,
            "base_url": endpoint.base_url,
            "auth_type": endpoint.auth_type.value,
            "allowed_scopes": [s.value for s in endpoint.allowed_scopes],
            "rate_limit": endpoint.rate_limit,
            "api_role": endpoint.api_role,
            "description": endpoint.description,
        }


# Helper function to create API controller for a role
def create_api_controller(role: SecurityRole) -> APIAccessController:
    """
    Create an API access controller for the given role.
    
    Args:
        role: Security role
    
    Returns:
        Configured APIAccessController
    """
    return APIAccessController(role)
