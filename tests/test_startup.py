# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Tests for startup greeting context helpers."""

from datetime import UTC, datetime

from agentic_brain.core.startup import build_startup_snapshot, startup_greeting


class TestStartupGreeting:
    """Test startup greeting formatting and fallback behavior."""

    def test_build_startup_snapshot_formats_expected_greeting(self):
        """Greeting should include last session, pending count, and recent summary."""
        rows = [
            {
                "content": "Discussed startup greeting rollout for the public CLI release",
                "timestamp": datetime(2026, 3, 28, 10, 15, tzinfo=UTC),
                "metadata": "{'topic': 'startup greeting rollout'}",
            },
            {
                "content": "Pending: wire spoken greeting into the CLI command",
                "timestamp": datetime(2026, 3, 28, 10, 10, tzinfo=UTC),
                "metadata": "{}",
            },
        ]

        snapshot = build_startup_snapshot(rows, pending_count=2)

        assert "Welcome back! Here's what I remember:" in snapshot.greeting
        assert "- Last session: startup greeting rollout at " in snapshot.greeting
        assert "- Pending: 2 items" in snapshot.greeting
        assert "Discussed startup greeting rollout" in snapshot.greeting
        assert snapshot.proof_lines
        assert snapshot.proof_lines[0].startswith("- ")

    def test_startup_greeting_falls_back_without_context(self, monkeypatch):
        """Greeting should remain friendly when Neo4j context is unavailable."""
        monkeypatch.setattr(
            "agentic_brain.core.startup.get_startup_snapshot",
            lambda **_: build_startup_snapshot([], pending_count=0),
        )

        greeting = startup_greeting()

        assert "- Last session: No recent context found at just now" in greeting
        assert "- Pending: 0 items" in greeting
        assert "- Recent: No recent context stored yet." in greeting
