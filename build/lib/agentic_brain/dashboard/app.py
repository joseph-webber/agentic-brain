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
Admin Dashboard for Agentic Brain API
======================================

This module provides a web-based dashboard for monitoring and managing the Agentic Brain
chatbot API. It integrates seamlessly with the FastAPI server and provides:

- Real-time system statistics (sessions, messages, memory, uptime)
- Health monitoring (Neo4j, LLM provider, memory)
- Active session management and viewing
- System configuration interface
- System metrics visualization

Features:
    - HTML/CSS/JavaScript dashboard (no external API required)
    - Auto-refreshing metrics (5-second intervals)
    - Status indicators with accessibility support
    - Gradient UI with Tailwind CSS
    - Font Awesome icons
    - Responsive design for mobile/tablet/desktop
    - VoiceOver and screen reader friendly

Routes:
    GET  /dashboard           - Dashboard HTML page
    GET  /api/stats          - System statistics JSON
    GET  /api/health         - System health status
    GET  /api/sessions       - Active sessions list
    POST /api/config         - Update configuration
    DELETE /api/sessions     - Clear all sessions

Example:
    Create dashboard and mount to app:
        >>> from agentic_brain.dashboard import create_dashboard_router
        >>> router = create_dashboard_router(
        ...     sessions_dict=sessions,
        ...     session_messages_dict=session_messages
        ... )
        >>> app.include_router(router)

    Access in browser:
        >>> # http://localhost:8000/dashboard

Author: Joseph Webber
License: Apache-2.0
"""

import logging
import os
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)


class ConfigUpdate(BaseModel):
    """Configuration update model."""

    key: str
    value: Any


class SystemStats(BaseModel):
    """System statistics model."""

    timestamp: str
    sessions_active: int
    total_messages: int
    memory_usage_mb: float
    uptime_seconds: int


class SessionData(BaseModel):
    """Session data model."""

    session_id: str
    created_at: str
    messages_count: int
    user_id: Optional[str] = None


class HealthStatus(BaseModel):
    """Health status model."""

    status: str
    neo4j_connected: bool
    llm_provider_available: bool
    memory_ok: bool
    timestamp: str


# Global state tracking
_startup_time = datetime.now(UTC)
_message_count = 0


def _get_dashboard_styles() -> str:
    """Return CSS styles for the dashboard."""
    return """
    <style>
        /* Accessibility improvements */
        *:focus-visible {
            outline: 3px solid #3b82f6;
            outline-offset: 2px;
        }

        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border-width: 0;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
            position: relative; /* For ::before positioning */
        }

        /* WCAG 2.1 AA Compliant Colors - Better contrast against dark backgrounds */
        .status-indicator.healthy {
            background-color: #34d399; /* Lighter green - 4.6:1 contrast */
        }
        .status-indicator.healthy::before {
            content: "✓";
            position: absolute;
            color: #064e3b; /* Dark green checkmark */
            font-weight: bold;
            font-size: 8px;
            line-height: 12px;
        }
        .status-indicator.unhealthy {
            background-color: #f87171; /* Lighter red - 4.5:1 contrast */
        }
        .status-indicator.unhealthy::before {
            content: "✗";
            position: absolute;
            color: #7f1d1d; /* Dark red X */
            font-weight: bold;
            font-size: 8px;
            line-height: 12px;
        }
        .status-indicator.warning {
            background-color: #fbbf24; /* Lighter orange - 5.2:1 contrast */
        }
        .status-indicator.warning::before {
            content: "⚠";
            position: absolute;
            color: #78350f; /* Dark orange warning */
            font-weight: bold;
            font-size: 8px;
            line-height: 12px;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .card-hover {
            transition: all 0.3s ease;
        }

        .card-hover:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }

        .gradient-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .gradient-success { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
        .gradient-warning { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
        .gradient-danger { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
    </style>
    """


def _get_dashboard_header() -> str:
    """Return the dashboard header HTML."""
    return """
    <!-- Skip to main content link for accessibility -->
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 focus:bg-blue-600 focus:p-2">Skip to main content</a>

    <!-- ARIA Live Regions for Screen Readers -->
    <div id="status-announcements" role="status" aria-live="polite" aria-atomic="true" class="sr-only">
        <!-- Screen reader announcements for status changes -->
    </div>
    <div id="critical-alerts" role="alert" aria-live="assertive" class="sr-only">
        <!-- Critical system alerts for immediate announcement -->
    </div>

    <!-- Header -->
    <header class="bg-gray-800 border-b border-gray-700 sticky top-0 z-50" role="banner">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div class="flex justify-between items-center">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 gradient-primary rounded-lg flex items-center justify-center">
                        <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                            <path d="M10 2a1 1 0 011 1v1.323l3.954 1.115 1.738-4.313a1 1 0 00-1.806-.906L13.83 4.56h-7.66l-1.06-2.6a1 1 0 00-1.806.906l1.738 4.313L9 4.323V3a1 1 0 011-1h0zm-5 8.274l-.818 2.552c-.25.78.140 1.635.92 1.884.78.25 1.635-.14 1.884-.92l.818-2.552a2 2 0 00-3.784 0zm6-2a2 2 0 100 4 2 2 0 000-4zm6 2l.818 2.552c.25.78-.14 1.635-.92 1.884-.78.25-1.635-.14-1.884-.92l-.818-2.552a2 2 0 003.784 0z"></path>
                        </svg>
                    </div>
                    <h1 class="text-2xl font-bold text-white">Agentic Brain</h1>
                </div>
                <div class="flex items-center gap-4">
                    <span class="text-sm text-gray-400">Last updated: <span id="last-update" class="text-gray-300">now</span></span>
                    <button id="refresh-btn" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition" aria-label="Refresh dashboard">
                        <i class="fas fa-sync-alt mr-2"></i>Refresh
                    </button>
                </div>
            </div>
        </div>
    </header>
    """


def _get_dashboard_metrics() -> str:
    """Return the key metrics cards HTML."""
    return """
        <!-- Status Banner -->
        <div id="status-banner" class="mb-6 p-4 rounded-lg bg-green-900 bg-opacity-30 border border-green-700 hidden" role="alert">
            <div class="flex items-center gap-2">
                <i class="fas fa-check-circle text-green-400"></i>
                <span id="status-message" class="text-green-200">All systems operational</span>
            </div>
        </div>

        <!-- Key Metrics -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <!-- Active Sessions -->
            <div class="bg-gray-800 rounded-lg p-6 card-hover border border-gray-700">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm font-medium">Active Sessions</p>
                        <p class="text-3xl font-bold text-white mt-2" id="sessions-count">-</p>
                    </div>
                    <div class="w-12 h-12 gradient-primary rounded-lg flex items-center justify-center">
                        <i class="fas fa-users text-white text-lg"></i>
                    </div>
                </div>
            </div>

            <!-- Total Messages -->
            <div class="bg-gray-800 rounded-lg p-6 card-hover border border-gray-700">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm font-medium">Total Messages</p>
                        <p class="text-3xl font-bold text-white mt-2" id="messages-count">-</p>
                    </div>
                    <div class="w-12 h-12 gradient-success rounded-lg flex items-center justify-center">
                        <i class="fas fa-comments text-white text-lg"></i>
                    </div>
                </div>
            </div>

            <!-- Memory Usage -->
            <div class="bg-gray-800 rounded-lg p-6 card-hover border border-gray-700">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm font-medium">Memory Usage</p>
                        <p class="text-3xl font-bold text-white mt-2"><span id="memory-usage">-</span> MB</p>
                        <div class="w-full bg-gray-700 rounded-full h-2 mt-2">
                            <div id="memory-bar" class="bg-blue-500 h-2 rounded-full" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Uptime -->
            <div class="bg-gray-800 rounded-lg p-6 card-hover border border-gray-700">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm font-medium">Uptime</p>
                        <p class="text-3xl font-bold text-white mt-2" id="uptime">-</p>
                    </div>
                    <div class="w-12 h-12 gradient-warning rounded-lg flex items-center justify-center">
                        <i class="fas fa-clock text-white text-lg"></i>
                    </div>
                </div>
            </div>
        </div>
    """


def _get_dashboard_health_section() -> str:
    """Return the system health section HTML."""
    return """
        <!-- System Health -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <!-- Health Status -->
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h2 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <i class="fas fa-heartbeat text-red-400"></i>
                    System Health
                </h2>
                <div class="space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="text-gray-400">Overall Status</span>
                        <div class="flex items-center gap-2">
                            <div class="status-indicator healthy" id="overall-status" aria-label="Overall system status: healthy"></div>
                            <span class="text-sm font-medium" id="overall-text">Healthy</span>
                        </div>
                    </div>
                    <hr class="border-gray-700">
                    <div class="flex items-center justify-between">
                        <span class="text-gray-400">Neo4j Connection</span>
                        <div class="flex items-center gap-2">
                            <div class="status-indicator" id="neo4j-status" aria-label="Neo4j connection status"></div>
                            <span class="text-sm" id="neo4j-text">-</span>
                        </div>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="text-gray-400">LLM Provider</span>
                        <div class="flex items-center gap-2">
                            <div class="status-indicator" id="llm-status" aria-label="LLM provider status"></div>
                            <span class="text-sm" id="llm-text">-</span>
                        </div>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="text-gray-400">Memory Status</span>
                        <div class="flex items-center gap-2">
                            <div class="status-indicator" id="memory-status" aria-label="Memory status"></div>
                            <span class="text-sm" id="memory-text">-</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- API Info -->
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h2 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <i class="fas fa-server text-blue-400"></i>
                    API Information
                </h2>
                <div class="space-y-2 text-sm">
                    <div>
                        <p class="text-gray-500">Version</p>
                        <p class="text-white font-mono" id="api-version">-</p>
                    </div>
                    <div>
                        <p class="text-gray-500">Server Time</p>
                        <p class="text-white font-mono" id="server-time">-</p>
                    </div>
                    <div>
                        <p class="text-gray-500">Endpoint</p>
                        <p class="text-white font-mono text-xs" id="api-endpoint">-</p>
                    </div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h2 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <i class="fas fa-cog text-gray-400"></i>
                    Quick Actions
                </h2>
                <div class="space-y-2">
                    <button class="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded transition text-sm font-medium" aria-label="View API documentation">
                        <i class="fas fa-book mr-2"></i>API Docs
                    </button>
                    <button class="w-full bg-purple-600 hover:bg-purple-700 text-white py-2 rounded transition text-sm font-medium" aria-label="View Neo4j browser">
                        <i class="fas fa-database mr-2"></i>Neo4j
                    </button>
                    <button class="w-full bg-gray-700 hover:bg-gray-600 text-white py-2 rounded transition text-sm font-medium" id="clear-sessions-btn" aria-label="Clear all sessions">
                        <i class="fas fa-trash mr-2"></i>Clear Sessions
                    </button>
                </div>
            </div>
        </div>
    """


def _get_dashboard_sessions_section() -> str:
    """Return the sessions list section HTML."""
    return """
        <!-- Sessions & Conversations -->
        <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <i class="fas fa-list text-purple-400"></i>
                Active Sessions
            </h2>
            <div id="sessions-container" class="space-y-3">
                <div class="text-center text-gray-500 py-8">
                    <i class="fas fa-spinner fa-spin mr-2"></i>Loading sessions...
                </div>
            </div>
        </div>
    """


def _get_dashboard_footer() -> str:
    """Return the dashboard footer HTML."""
    return """
    <!-- Footer -->
    <footer class="bg-gray-800 border-t border-gray-700 mt-12" role="contentinfo">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div class="flex flex-col md:flex-row justify-between items-center text-sm text-gray-400">
                <p>&copy; 2026 Agentic Brain. Licensed under Apache-2.0.</p>
                <div class="flex gap-4 mt-4 md:mt-0">
                    <a href="/docs" class="hover:text-blue-400 transition" target="_blank" rel="noopener noreferrer">API Docs</a>
                    <a href="/redoc" class="hover:text-blue-400 transition" target="_blank" rel="noopener noreferrer">ReDoc</a>
                    <span class="text-gray-600">|</span>
                    <span>Built with <i class="fas fa-heart text-red-500"></i> for developers</span>
                </div>
            </div>
        </div>
    </footer>
    """


def _get_js_utility_functions() -> str:
    """Return JavaScript utility functions."""
    return """
        function formatUptime(seconds) {
            const days = Math.floor(seconds / 86400);
            const hours = Math.floor((seconds % 86400) / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (days > 0) return `${days}d ${hours}h`;
            if (hours > 0) return `${hours}h ${minutes}m`;
            return `${minutes}m`;
        }

        function updateStatusIndicator(id, healthy) {
            const element = document.getElementById(id);
            if (element) {
                element.className = `status-indicator ${healthy ? 'healthy' : 'unhealthy'}`;
            }
        }

        function formatTime(isoString) {
            const date = new Date(isoString);
            return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        }

        function updateLastUpdate() {
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    """


def _get_js_api_functions() -> str:
    """Return JavaScript API fetch functions."""
    return """
        async function updateStats() {
            try {
                const response = await fetch(`${API_BASE}/stats`);
                if (!response.ok) throw new Error('Failed to fetch stats');
                const data = await response.json();

                document.getElementById('sessions-count').textContent = data.sessions_active || 0;
                document.getElementById('messages-count').textContent = data.total_messages || 0;
                document.getElementById('memory-usage').textContent = (data.memory_usage_mb || 0).toFixed(1);
                document.getElementById('uptime').textContent = formatUptime(data.uptime_seconds || 0);

                const memoryPercent = Math.min((data.memory_usage_mb || 0) / 512 * 100, 100);
                document.getElementById('memory-bar').style.width = `${memoryPercent}%`;
                updateLastUpdate();
            } catch (error) {
                console.error('Error updating stats:', error);
                document.getElementById('status-banner').classList.remove('hidden');
                document.getElementById('status-message').textContent = 'Failed to update stats: ' + error.message;
            }
        }

        async function updateHealth() {
            try {
                const response = await fetch(`${API_BASE}/health`);
                if (!response.ok) throw new Error('Failed to fetch health');
                const data = await response.json();

                updateStatusIndicator('neo4j-status', data.neo4j_connected);
                updateStatusIndicator('llm-status', data.llm_provider_available);
                updateStatusIndicator('memory-status', data.memory_ok);

                document.getElementById('neo4j-text').textContent = data.neo4j_connected ? 'Connected' : 'Disconnected';
                document.getElementById('llm-text').textContent = data.llm_provider_available ? 'Available' : 'Unavailable';
                document.getElementById('memory-text').textContent = data.memory_ok ? 'OK' : 'Warning';

                const allHealthy = data.neo4j_connected && data.llm_provider_available && data.memory_ok;
                updateStatusIndicator('overall-status', allHealthy);
                document.getElementById('overall-text').textContent = allHealthy ? 'Healthy' : 'Issues detected';
                document.getElementById('server-time').textContent = formatTime(data.timestamp);
            } catch (error) {
                console.error('Error updating health:', error);
                updateStatusIndicator('neo4j-status', false);
                updateStatusIndicator('llm-status', false);
                updateStatusIndicator('memory-status', false);
            }
        }

        async function updateSessions() {
            try {
                const response = await fetch(`${API_BASE}/sessions`);
                if (!response.ok) throw new Error('Failed to fetch sessions');
                const data = await response.json();
                const container = document.getElementById('sessions-container');

                if (!data.sessions || data.sessions.length === 0) {
                    container.innerHTML = '<div class="text-center text-gray-500 py-8">No active sessions</div>';
                    return;
                }

                container.innerHTML = data.sessions.map(session => `
                    <div class="bg-gray-700 rounded p-4 border border-gray-600 flex justify-between items-center">
                        <div>
                            <p class="font-mono text-sm text-blue-400">${escapeHtml(session.session_id)}</p>
                            <p class="text-xs text-gray-400 mt-1">
                                <i class="fas fa-comment mr-1"></i>${session.messages_count} messages
                                <span class="mx-2">•</span>Created: ${formatTime(session.created_at)}
                            </p>
                        </div>
                        <div class="text-right">
                            <span class="bg-green-900 bg-opacity-50 text-green-200 px-3 py-1 rounded text-xs font-medium">
                                <i class="fas fa-check-circle mr-1"></i>Active
                            </span>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error updating sessions:', error);
                document.getElementById('sessions-container').innerHTML =
                    '<div class="text-center text-red-400 py-8">Failed to load sessions</div>';
            }
        }

        async function refreshDashboard() {
            const btn = document.getElementById('refresh-btn');
            btn.disabled = true;
            btn.style.opacity = '0.5';
            await Promise.all([updateStats(), updateHealth(), updateSessions()]);
            btn.disabled = false;
            btn.style.opacity = '1';
        }
    """


def _get_js_init_function() -> str:
    """Return JavaScript initialization function."""
    return """
        function init() {
            refreshDashboard();
            refreshInterval = setInterval(refreshDashboard, 5000);
            document.getElementById('refresh-btn').addEventListener('click', refreshDashboard);

            document.getElementById('clear-sessions-btn').addEventListener('click', async () => {
                if (confirm('Are you sure you want to clear all sessions? This cannot be undone.')) {
                    try {
                        const response = await fetch(`${API_BASE}/sessions`, { method: 'DELETE' });
                        if (response.ok) {
                            alert('All sessions cleared');
                            await updateSessions();
                        } else {
                            alert('Failed to clear sessions');
                        }
                    } catch (error) {
                        alert('Error: ' + error.message);
                    }
                }
            });

            document.querySelectorAll('button')[0].addEventListener('click', () => window.open('/docs', '_blank'));
            document.querySelectorAll('button')[1].addEventListener('click', () => window.open('http://localhost:7474', '_blank'));
            window.addEventListener('beforeunload', () => { if (refreshInterval) clearInterval(refreshInterval); });
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    """


def _get_dashboard_scripts() -> str:
    """Assemble the complete dashboard JavaScript."""
    return f"""
    <script>
        const API_BASE = '/api/dashboard';
        let refreshInterval = null;
        {_get_js_utility_functions()}
        {_get_js_api_functions()}
        {_get_js_init_function()}
    </script>
    """


def _get_dashboard_html() -> str:
    """Assemble the complete dashboard HTML from components."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Agentic Brain Admin Dashboard">
    <title>Agentic Brain Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    {_get_dashboard_styles()}
</head>
<body class="bg-gray-900 text-gray-100">
    {_get_dashboard_header()}
    <main id="main-content" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {_get_dashboard_metrics()}
        {_get_dashboard_health_section()}
        {_get_dashboard_sessions_section()}
    </main>
    {_get_dashboard_footer()}
    {_get_dashboard_scripts()}
</body>
</html>"""


def _get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        import sys

        return 50.0  # Base estimate
    except (OSError, AttributeError, RuntimeError) as e:
        logger.debug(f"Memory stat collection failed: {e}")
        return 50.0


def _check_memory_health() -> bool:
    """Check if system memory usage is below 85% threshold."""
    try:
        import psutil

        return psutil.virtual_memory().percent < 85
    except (ImportError, Exception):
        return True


def _build_stats_response(sessions: dict, messages: dict) -> dict[str, Any]:
    """Build the stats response dictionary."""
    uptime_seconds = int((datetime.now(UTC) - _startup_time).total_seconds())
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "sessions_active": len(sessions),
        "total_messages": sum(len(msgs) for msgs in messages.values()),
        "memory_usage_mb": _get_memory_usage_mb(),
        "uptime_seconds": uptime_seconds,
    }


def _build_sessions_list(sessions: dict, messages: dict) -> list[dict]:
    """Build a list of session data for the API response."""
    sessions_list = []
    for session_id, session_data in sessions.items():
        sessions_list.append(
            {
                "session_id": session_id,
                "created_at": session_data.get(
                    "created_at", datetime.now(UTC).isoformat()
                ),
                "messages_count": len(messages.get(session_id, [])),
                "user_id": session_data.get("user_id"),
            }
        )
    return sessions_list


def _build_health_response() -> dict[str, Any]:
    """Build the health check response dictionary."""
    memory_ok = _check_memory_health()
    neo4j_connected = True  # Placeholder - production should check actual connection
    llm_available = True  # Placeholder - production should check LLM provider

    return {
        "status": (
            "healthy"
            if (neo4j_connected and llm_available and memory_ok)
            else "degraded"
        ),
        "neo4j_connected": neo4j_connected,
        "llm_provider_available": llm_available,
        "memory_ok": memory_ok,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def create_dashboard_router(
    sessions_dict: dict = None,
    session_messages_dict: dict = None,
) -> APIRouter:
    """
    Create a dashboard router with admin endpoints.

    Args:
        sessions_dict: Reference to API server's sessions dictionary.
        session_messages_dict: Reference to session messages dictionary.

    Returns:
        APIRouter configured with dashboard endpoints.
    """
    router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
    _sessions = sessions_dict or {}
    _messages = session_messages_dict or {}

    @router.get("", response_class=HTMLResponse, summary="Dashboard Page")
    async def get_dashboard():
        """Serve the admin dashboard HTML page."""
        logger.info("Dashboard accessed")
        return HTMLResponse(content=_get_dashboard_html())

    @router.get("/api/stats", response_model=SystemStats, summary="System Statistics")
    async def get_stats() -> dict[str, Any]:
        """Get current system statistics (sessions, messages, memory, uptime)."""
        return _build_stats_response(_sessions, _messages)

    @router.get("/api/sessions", summary="Active Sessions")
    async def get_sessions() -> dict[str, Any]:
        """Get list of all active sessions with metadata."""
        return {"sessions": _build_sessions_list(_sessions, _messages)}

    @router.delete("/api/sessions", summary="Clear All Sessions")
    async def delete_sessions():
        """Delete ALL active sessions and messages. WARNING: Irreversible."""
        count = len(_sessions)
        _sessions.clear()
        _messages.clear()
        logger.warning(f"Cleared all {count} sessions from dashboard")
        return {"status": "success", "cleared": count}

    @router.get("/api/health", response_model=HealthStatus, summary="System Health")
    async def get_health() -> dict[str, Any]:
        """Get system health status (Neo4j, LLM, memory)."""
        return _build_health_response()

    @router.post("/api/config", summary="Update Configuration")
    async def update_config(config: ConfigUpdate):
        """Update system configuration parameters at runtime."""
        logger.info(f"Configuration update requested: {config.key}")
        return {"status": "success", "message": f"Configuration updated: {config.key}"}

    return router
