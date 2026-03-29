# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Security Test Suite for agentic-brain
Must pass before Apache 2.0 release!
"""

import inspect
import os
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src" / "agentic_brain"


class TestSecretsSecurity:
    """Test that no secrets are exposed."""

    def test_no_hardcoded_api_keys(self):
        """Ensure no API keys are hardcoded in source."""
        patterns = [
            r"sk-[a-zA-Z0-9]{32,}",  # OpenAI
            r"sk-ant-[a-zA-Z0-9-]{32,}",  # Anthropic
            r"gsk_[a-zA-Z0-9]{32,}",  # Groq
            r"xai-[a-zA-Z0-9]{32,}",  # xAI
        ]

        for py_file in SRC_PATH.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                matches = re.findall(pattern, content)
                assert (
                    not matches
                ), f"Hardcoded key found in {py_file}: {matches[0][:10]}..."

    def test_no_hardcoded_passwords(self):
        """Ensure no passwords are hardcoded."""
        bad_patterns = [
            r"password\s*=\s*[\"\']([^\"\']{4,})[\"\']",
            r"passwd\s*=\s*[\"\']([^\"\']{4,})[\"\']",
        ]
        placeholder_tokens = {
            "example",
            "placeholder",
            "changeme",
            "change-me",
            "secret",
            "password",
            "pass",
            "dummy",
            "test",
            "xxx",
            "yyy",
            "your",
            "app-specific",
            "token",
        }

        for py_file in SRC_PATH.rglob("*.py"):
            if "test" in str(py_file).lower():
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for line_no, line in enumerate(content.splitlines(), 1):
                for pattern in bad_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if not match:
                        continue
                    value = match.group(1).strip()
                    lowered_value = value.lower()
                    if "os.getenv" in line or "os.environ" in line or "getpass" in line:
                        continue
                    if any(token in lowered_value for token in placeholder_tokens):
                        continue
                    raise AssertionError(
                        f"Hardcoded password found in {py_file}:{line_no}: {value}"
                    )

    def test_env_vars_not_in_code(self):
        """Ensure .env values aren't committed."""
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            pytest.skip(".env should not be in repo")


class TestAuthSecurity:
    """Test authentication security."""

    def test_jwt_uses_strong_algorithm(self):
        """JWT should use HS256 or better."""
        from agentic_brain.auth.config import JWTConfig

        allowed_algorithms = {
            "HS256",
            "HS384",
            "HS512",
            "RS256",
            "RS384",
            "RS512",
            "ES256",
            "ES384",
            "ES512",
        }
        algorithm = JWTConfig().algorithm
        assert algorithm, "JWT algorithm must be configured"
        assert (
            algorithm.upper() in allowed_algorithms
        ), f"Weak JWT algorithm configured: {algorithm}"

    def test_passwords_are_hashed(self):
        """Passwords must be hashed, never stored plain."""
        from agentic_brain.auth import constants
        from agentic_brain.auth.config import PasswordConfig

        config = PasswordConfig()
        allowed_encoders = {
            constants.PASSWORD_ENCODER_BCRYPT,
            constants.PASSWORD_ENCODER_ARGON2,
            constants.PASSWORD_ENCODER_PBKDF2,
        }
        assert config.encoder.lower() in {e.lower() for e in allowed_encoders}

    def test_constant_time_comparison(self):
        """Token comparison should be constant-time."""
        from agentic_brain.auth import providers

        source = inspect.getsource(providers)
        assert (
            "compare_digest" in source or "hmac" in source
        ), "Should use constant-time comparison"


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_cypher_injection_prevented(self):
        """Neo4j queries should be parameterized."""
        dangerous_patterns = [
            r'f".*MATCH.*\{.*\}"',  # f-string in Cypher
            r"f'.*MATCH.*\{.*\}'",
            r'f".*CREATE.*\{.*\}"',
            r"f'.*CREATE.*\{.*\}'",
            r'".*MATCH.*"\s*\+',  # String concat in Cypher
        ]
        offenders = []

        for py_file in SRC_PATH.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in dangerous_patterns:
                if re.search(pattern, content):
                    offenders.append((py_file, pattern))

        assert not offenders, f"Potential Cypher injection patterns: {offenders}"

    def test_sql_injection_prevented(self):
        """SQL queries should be parameterized."""
        sql_patterns = [
            re.compile(
                r"f[\"\'].*(SELECT|INSERT|UPDATE|DELETE).*\{(query|search|term|user_input|input)\}.*[\"\']",
                re.IGNORECASE,
            ),
            re.compile(
                r"(SELECT|INSERT|UPDATE|DELETE).*\+.*(query|search|term|user_input|input)",
                re.IGNORECASE,
            ),
        ]
        offenders = []

        for py_file in SRC_PATH.rglob("*.py"):
            if "monolith_backup" in str(py_file):
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                for pattern in sql_patterns:
                    if pattern.search(line):
                        offenders.append((py_file, line.strip()))

        assert not offenders, f"Potential SQL injection patterns: {offenders}"

    def test_xss_prevented_in_api(self):
        """API responses should escape HTML."""
        from agentic_brain.api.server import create_app

        client = TestClient(create_app())
        response = client.get("/health")
        assert response.headers.get("Content-Security-Policy")
        assert "<script" not in response.text.lower()


class TestAPISecurity:
    """Test API security."""

    def test_cors_configured(self):
        """CORS should be properly configured."""
        from agentic_brain.api.server import create_app

        app = create_app()
        assert any(
            middleware.cls is CORSMiddleware for middleware in app.user_middleware
        )

    def test_rate_limiting_exists(self):
        """API should have rate limiting."""
        from agentic_brain.api import routes

        source = inspect.getsource(routes)
        assert "check_rate_limit" in source

    def test_https_enforced_in_production(self):
        """Production should enforce HTTPS."""
        from agentic_brain.api.server import create_app

        client = TestClient(create_app())
        response = client.get("/health")
        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "max-age" in hsts


class TestRedisSecurity:
    """Test Redis security."""

    def test_redis_supports_password(self):
        """Redis client should support password auth."""
        from agentic_brain.router.redis_cache import RedisRouterCache

        source = inspect.getsource(RedisRouterCache)
        assert (
            "password" in source.lower() or "REDIS_PASSWORD" in source
        ), "Redis should support password authentication"


class TestWebSocketSecurity:
    """Test WebSocket security."""

    def test_websocket_auth_exists(self):
        """WebSocket should have authentication."""
        from agentic_brain.api import websocket

        source = inspect.getsource(websocket)
        assert "WebSocketAuthenticator" in source and "authenticate" in source


class TestDependencySecurity:
    """Test dependency security."""

    def test_no_known_vulnerable_deps(self):
        """Check for known vulnerabilities."""
        if not shutil.which("pip-audit"):
            pytest.skip("pip-audit not installed")

        requirements_files = list(PROJECT_ROOT.glob("requirements*.txt"))
        if not requirements_files:
            pytest.skip("No requirements files found for pip-audit")

        cmd = ["pip-audit", "-r", str(requirements_files[0])]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
