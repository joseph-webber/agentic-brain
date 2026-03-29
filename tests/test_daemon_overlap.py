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

import asyncio
import os
import sys
import threading
import time
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.conversation import (
    ConversationalVoice,
    ConversationConfig,
    VoiceMode,
)
from agentic_brain.voice.resilient import ResilientVoice, VoiceDaemon
from agentic_brain.voice.serializer import VoiceMessage, get_voice_serializer


@pytest.fixture
def serializer():
    serializer = get_voice_serializer()
    original_pause = serializer.pause_between
    original_silence = serializer.startup_silence_seconds
    serializer.reset()
    serializer.set_pause_between(0)
    serializer.mark_daemon_ready()
    assert serializer.wait_until_worker_ready(2.0)
    yield serializer
    serializer.reset()
    serializer.set_pause_between(original_pause)
    serializer._startup_silence_seconds = original_silence
    serializer.mark_daemon_ready()


def _make_serialized_executor(duration: float = 0.01):
    calls: list[tuple[float, float]] = []
    active = 0
    max_active = 0
    lock = threading.Lock()

    def executor(message: VoiceMessage) -> bool:
        nonlocal active, max_active
        start = time.monotonic()
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(duration)
        with lock:
            active -= 1
        calls.append((start, time.monotonic(), message.text))
        return True

    return executor, calls, lambda: max_active


def test_serializer_uses_500ms_startup_silence(serializer):
    assert serializer.startup_silence_seconds == pytest.approx(0.5)


def test_serializer_worker_ready_before_speech(serializer):
    assert serializer.is_worker_ready() is True
    assert serializer.wait_until_ready(1.0) is True


def test_serializer_blocks_startup_speech_until_daemon_ready(serializer):
    executed = []
    serializer.mark_daemon_starting()

    def executor(_message: VoiceMessage) -> bool:
        executed.append(time.monotonic())
        return True

    serializer.run_serialized(
        VoiceMessage(text="blocked"), executor=executor, wait=False
    )
    time.sleep(0.05)
    assert executed == []

    serializer.mark_daemon_ready()
    deadline = time.monotonic() + 2.0
    while len(executed) < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(executed) == 1


def test_serializer_never_executes_if_lock_not_acquired(serializer, monkeypatch):
    executed = []

    def executor(_message: VoiceMessage) -> bool:
        executed.append(True)
        return True

    monkeypatch.setattr(serializer._speech_lock, "acquire", lambda timeout=30.0: False)
    monkeypatch.setattr(serializer._speech_lock, "release", lambda: None)

    result = serializer.run_serialized(
        VoiceMessage(text="lock must exist"),
        executor=executor,
        wait=True,
    )

    assert result is False
    assert executed == []


def test_mode_switch_waits_for_current_speech(serializer, monkeypatch):
    config = ConversationConfig(mode=VoiceMode.LIFE)
    monkeypatch.setattr(config, "load_mode", lambda: VoiceMode.LIFE)
    conv = ConversationalVoice(config)
    started = threading.Event()
    release = threading.Event()

    def slow_executor(_message: VoiceMessage) -> bool:
        started.set()
        release.wait(1.0)
        return True

    serializer.run_serialized(
        VoiceMessage(text="current speech"),
        executor=slow_executor,
        wait=False,
    )
    assert started.wait(1.0)

    announcements = []
    monkeypatch.setattr(
        conv,
        "speak",
        lambda *args, **kwargs: announcements.append(serializer.is_speaking()) or True,
    )

    switch_thread = threading.Thread(target=conv.set_mode, args=(VoiceMode.WORK,))
    switch_thread.start()
    time.sleep(0.05)

    assert conv.config.mode == VoiceMode.LIFE
    release.set()
    switch_thread.join(timeout=1.0)

    assert conv.config.mode == VoiceMode.WORK
    assert announcements == [False]


def test_mode_switch_releases_gate_after_switch(serializer, monkeypatch):
    config = ConversationConfig(mode=VoiceMode.LIFE)
    monkeypatch.setattr(config, "load_mode", lambda: VoiceMode.LIFE)
    conv = ConversationalVoice(config)
    announcements = []
    monkeypatch.setattr(
        conv, "speak", lambda *args, **kwargs: announcements.append(True) or True
    )

    conv.set_mode(VoiceMode.WORK)

    assert announcements == [True]
    assert serializer.wait_until_ready(1.0) is True


@pytest.mark.asyncio
async def test_daemon_start_blocks_processing_until_ready(serializer, monkeypatch):
    daemon = VoiceDaemon()
    daemon._startup_silence_seconds = 0.05
    invoked = asyncio.Event()
    call_times = []

    async def fake_speak(text: str, voice: str = "Karen", rate: int = 155) -> bool:
        call_times.append((text, time.monotonic()))
        invoked.set()
        return True

    monkeypatch.setattr(ResilientVoice, "speak", AsyncMock(side_effect=fake_speak))

    start_task = asyncio.create_task(daemon.start())
    await asyncio.sleep(0)
    await daemon.speak("startup blocked")
    await asyncio.sleep(0.02)

    assert call_times == []
    await start_task
    await asyncio.wait_for(invoked.wait(), timeout=1.0)
    await daemon.stop()

    assert len(call_times) == 1


@pytest.mark.asyncio
async def test_daemon_ready_signal_set_after_startup_gate(serializer, monkeypatch):
    daemon = VoiceDaemon()
    daemon._startup_silence_seconds = 0.02
    monkeypatch.setattr(ResilientVoice, "speak", AsyncMock(return_value=True))

    assert daemon.get_stats()["ready"] is False
    await daemon.start()

    assert daemon._ready.is_set() is True
    assert daemon.get_stats()["ready"] is True
    assert serializer.is_daemon_ready() is True

    await daemon.stop()


def test_rapid_mode_toggles_do_not_overlap(serializer, monkeypatch):
    config = ConversationConfig(mode=VoiceMode.LIFE)
    monkeypatch.setattr(config, "load_mode", lambda: VoiceMode.LIFE)
    conv = ConversationalVoice(config)
    serializer._audit_enabled = False
    active = 0
    max_active = 0
    messages = []
    lock = threading.Lock()

    def fake_speak_with_say(message: VoiceMessage) -> bool:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.01)
        with lock:
            active -= 1
            messages.append(message.text)
        return True

    monkeypatch.setattr(serializer, "_speak_with_say", fake_speak_with_say)

    threads = [
        threading.Thread(
            target=conv.set_mode,
            args=(VoiceMode.WORK if i % 2 == 0 else VoiceMode.LIFE,),
        )
        for i in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1.0)

    assert serializer.wait_until_idle(2.0) is True
    assert max_active == 1
    assert len(messages) == 6


def test_concurrent_startup_speech_attempts_do_not_overlap(serializer, monkeypatch):
    serializer._audit_enabled = False
    serializer.mark_daemon_starting()
    executor, calls, max_active = _make_serialized_executor(duration=0.01)
    monkeypatch.setattr(serializer, "_speak_with_say", executor)

    threads = [
        threading.Thread(
            target=serializer.speak,
            args=(f"startup {i}",),
            kwargs={"wait": False},
        )
        for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1.0)

    time.sleep(0.05)
    assert calls == []

    serializer.mark_daemon_ready()
    assert serializer.wait_until_idle(2.0) is True
    assert len(calls) == 8
    assert max_active() == 1


@pytest.mark.asyncio
async def test_daemon_concurrent_startup_queue_remains_serialized(
    serializer, monkeypatch
):
    daemon = VoiceDaemon()
    daemon._startup_silence_seconds = 0.02
    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def fake_speak(_text: str, voice: str = "Karen", rate: int = 155) -> bool:
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        async with lock:
            active -= 1
        return True

    monkeypatch.setattr(ResilientVoice, "speak", AsyncMock(side_effect=fake_speak))

    start_task = asyncio.create_task(daemon.start())
    await asyncio.sleep(0)
    await asyncio.gather(*(daemon.speak(f"queued {i}") for i in range(5)))
    await start_task
    await asyncio.sleep(0.15)
    await daemon.stop()

    assert daemon.processed == 5
    assert max_active == 1
