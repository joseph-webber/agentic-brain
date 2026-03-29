# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Voice test fixtures — mock all subprocess calls to prevent real audio.

Every voice test must use these fixtures so that no actual speech or sound
playback occurs during the test suite.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_subprocess_say():
    """Mock subprocess.Popen in the voice serializer so `say` never runs.

    This is autouse — applied to every test in the voice/ package automatically.
    The serializer is the single sanctioned path to ``say``; mocking it here
    prevents any real audio output.
    """
    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.poll.return_value = 0
    mock_proc.pid = 12345

    with patch(
        "agentic_brain.voice.serializer.subprocess.Popen",
        return_value=mock_proc,
    ) as mock_popen:
        # Also mock subprocess.run used by the serializer for pgrep checks
        with patch(
            "agentic_brain.voice.serializer.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=""),
        ):
            yield mock_popen


@pytest.fixture(autouse=True)
def mock_async_subprocess():
    """Mock asyncio.create_subprocess_exec so afplay / say via resilient.py
    never actually launches a process.
    """
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_proc.pid = 12345

    with patch(
        "asyncio.create_subprocess_exec",
        return_value=mock_proc,
    ) as mock_exec:
        yield mock_exec
