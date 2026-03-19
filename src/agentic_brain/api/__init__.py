# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Agentic Brain Chatbot API module."""

from .models import ChatRequest, ChatResponse, SessionInfo, ErrorResponse
from .server import app, create_app, run_server
from .routes import register_routes
from .middleware import setup_cors, setup_exception_handlers
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
]
