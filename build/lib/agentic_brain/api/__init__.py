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

"""Agentic Brain Chatbot API module."""

from .auth import (
    AuthContext,
    TokenData,
    get_optional_auth,
    is_auth_enabled,
    require_api_key,
    require_auth,
    require_current_user,
    require_role,
)
from .middleware import setup_cors, setup_exception_handlers
from .models import ChatRequest, ChatResponse, ErrorResponse, SessionInfo
from .routes import register_routes
from .server import app, create_app, run_server
from .sessions import (
    InMemorySessionBackend,
    RedisSessionBackend,
    Session,
    SessionBackend,
    generate_message_id,
    generate_session_id,
    get_session_backend,
    reset_session_backend,
)
from .websocket import register_websocket_routes

__all__ = [
    # Models
    "ChatRequest",
    "ChatResponse",
    "SessionInfo",
    "ErrorResponse",
    # Server
    "app",
    "create_app",
    "run_server",
    # Routes
    "register_routes",
    # Middleware
    "setup_cors",
    "setup_exception_handlers",
    # WebSocket
    "register_websocket_routes",
    # Auth
    "AuthContext",
    "TokenData",
    "get_optional_auth",
    "require_auth",
    "require_api_key",
    "require_current_user",
    "require_role",
    "is_auth_enabled",
    # Sessions
    "Session",
    "SessionBackend",
    "InMemorySessionBackend",
    "RedisSessionBackend",
    "get_session_backend",
    "reset_session_backend",
    "generate_session_id",
    "generate_message_id",
]
