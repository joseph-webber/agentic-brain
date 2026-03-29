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

"""
Authentication constants following JHipster conventions.

Roles use the ROLE_ prefix as per Spring Security conventions.
Authorities represent fine-grained permissions without prefix.
"""

# Standard roles (JHipster convention: ROLE_ prefix)
ROLE_ADMIN = "ROLE_ADMIN"
ROLE_USER = "ROLE_USER"
ROLE_ANONYMOUS = "ROLE_ANONYMOUS"
ROLE_MODERATOR = "ROLE_MODERATOR"
ROLE_MANAGER = "ROLE_MANAGER"

# Standard authorities (fine-grained permissions)
AUTHORITY_ADMIN = "ADMIN"
AUTHORITY_USER = "USER"
AUTHORITY_READ = "READ"
AUTHORITY_WRITE = "WRITE"
AUTHORITY_DELETE = "DELETE"

# User management authorities
AUTHORITY_USER_MANAGEMENT = "USER_MANAGEMENT"
AUTHORITY_USER_CREATE = "USER_CREATE"
AUTHORITY_USER_UPDATE = "USER_UPDATE"
AUTHORITY_USER_DELETE = "USER_DELETE"
AUTHORITY_USER_VIEW = "USER_VIEW"

# System authorities
AUTHORITY_SYSTEM_ADMIN = "SYSTEM_ADMIN"
AUTHORITY_AUDIT_VIEW = "AUDIT_VIEW"
AUTHORITY_CONFIG_MANAGE = "CONFIG_MANAGE"

# Agent authorities
AUTHORITY_AGENT_MANAGE = "AGENT_MANAGE"
AUTHORITY_AGENT_EXECUTE = "AGENT_EXECUTE"
AUTHORITY_AGENT_VIEW = "AGENT_VIEW"

# Memory/RAG authorities
AUTHORITY_MEMORY_READ = "MEMORY_READ"
AUTHORITY_MEMORY_WRITE = "MEMORY_WRITE"
AUTHORITY_RAG_QUERY = "RAG_QUERY"
AUTHORITY_RAG_INDEX = "RAG_INDEX"

# JWT claim names
CLAIM_AUTHORITIES = "auth"
CLAIM_SUBJECT = "sub"
CLAIM_ISSUED_AT = "iat"
CLAIM_EXPIRATION = "exp"
CLAIM_NOT_BEFORE = "nbf"
CLAIM_JWT_ID = "jti"
CLAIM_ISSUER = "iss"
CLAIM_AUDIENCE = "aud"

# OAuth2 scopes
SCOPE_OPENID = "openid"
SCOPE_PROFILE = "profile"
SCOPE_EMAIL = "email"
SCOPE_OFFLINE_ACCESS = "offline_access"

# Session constants
SESSION_COOKIE_NAME = "AGENTIC_SESSION"
REMEMBER_ME_COOKIE_NAME = "AGENTIC_REMEMBER_ME"
SESSION_TIMEOUT_SECONDS = 3600  # 1 hour
REMEMBER_ME_TIMEOUT_SECONDS = 2592000  # 30 days

# Token types
TOKEN_TYPE_BEARER = "Bearer"
TOKEN_TYPE_BASIC = "Basic"

# Password encoding
PASSWORD_ENCODER_BCRYPT = "bcrypt"
PASSWORD_ENCODER_ARGON2 = "argon2"
PASSWORD_ENCODER_PBKDF2 = "pbkdf2"

# Default algorithm
DEFAULT_JWT_ALGORITHM = "HS512"
DEFAULT_JWT_EXPIRY_SECONDS = 86400  # 24 hours
DEFAULT_REFRESH_TOKEN_EXPIRY_SECONDS = 604800  # 7 days

# OAuth2 security
OAUTH2_STATE_EXPIRY_SECONDS = 600  # 10 minutes for state parameter
OAUTH2_NONCE_EXPIRY_SECONDS = 600  # 10 minutes for nonce

# Rate limiting defaults
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 100
DEFAULT_LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
DEFAULT_LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minutes

# Minimum password requirements
MIN_PASSWORD_LENGTH = 8
MIN_JWT_SECRET_LENGTH = 32

# Audit event types
AUDIT_EVENT_LOGIN_SUCCESS = "LOGIN_SUCCESS"
AUDIT_EVENT_LOGIN_FAILURE = "LOGIN_FAILURE"
AUDIT_EVENT_LOGOUT = "LOGOUT"
AUDIT_EVENT_TOKEN_REFRESH = "TOKEN_REFRESH"
AUDIT_EVENT_TOKEN_REVOKE = "TOKEN_REVOKE"
AUDIT_EVENT_PASSWORD_CHANGE = "PASSWORD_CHANGE"
AUDIT_EVENT_MFA_CHALLENGE = "MFA_CHALLENGE"
AUDIT_EVENT_MFA_SUCCESS = "MFA_SUCCESS"
AUDIT_EVENT_MFA_FAILURE = "MFA_FAILURE"
