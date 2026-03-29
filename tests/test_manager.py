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

"""Import tests for agentic_brain modules named 'manager'."""

import importlib
from unittest.mock import patch

MODULES = [
    "agentic_brain.pooling.manager",
    "agentic_brain.transport.manager",
    "agentic_brain.modes.manager",
    "agentic_brain.secrets.manager",
    "agentic_brain.personas.manager",
]


def test_module_imports():
    """Test module can be imported."""
    for module_path in MODULES:
        module = importlib.import_module(module_path)
        assert module is not None


def test_basic_functionality():
    """Test basic functionality placeholder."""
    assert MODULES


def test_mode_manager_announcements_use_serializer():
    """Mode announcements must route through the shared voice serializer."""
    from agentic_brain.modes.manager import ModeManager
    from agentic_brain.modes.registry import get_mode

    manager = ModeManager()
    mode = get_mode("developer")

    with patch("agentic_brain.modes.manager.speak_serialized") as mock_speak:
        manager._announce_mode_change(mode)

    mock_speak.assert_called_once_with(
        "Switched to Developer mode",
        voice=mode.config.voice.primary_voice,
        rate=mode.config.voice.speech_rate,
        wait=False,
    )
