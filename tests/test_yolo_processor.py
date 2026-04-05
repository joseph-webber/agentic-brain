# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentic_brain.yolo.handlers import CommandExecutionResult, InterpretedCommand
from agentic_brain.yolo.processor import YOLOCommand, YOLOCommandProcessor


class DummyProducer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict, bytes | None]] = []

    async def send_and_wait(
        self, topic: str, value: dict, key: bytes | None = None
    ) -> None:
        self.messages.append((topic, value, key))


class StubHandlers:
    def __init__(self) -> None:
        self.status_provider = None
        self.called: list[str] = []

    async def run_tests(self, command_text: str) -> CommandExecutionResult:
        self.called.append(f"tests:{command_text}")
        return CommandExecutionResult(
            True, "run_tests", command_text, output="tests ok"
        )

    async def deploy(self, command_text: str) -> CommandExecutionResult:
        self.called.append(f"deploy:{command_text}")
        return CommandExecutionResult(True, "deploy", command_text, output="deploy ok")

    async def check_status(self, command_text: str) -> CommandExecutionResult:
        self.called.append(f"status:{command_text}")
        return CommandExecutionResult(
            True, "check_status", command_text, output="status ok"
        )

    async def search(self, command_text: str) -> CommandExecutionResult:
        self.called.append(f"search:{command_text}")
        return CommandExecutionResult(True, "search", command_text, output="search ok")

    async def interpret(self, command_text: str) -> InterpretedCommand:
        self.called.append(f"interpret:{command_text}")
        return InterpretedCommand(
            capability="search",
            normalized_command="search YOLOCommandProcessor",
            reasoning="Unknown command best matches code search",
        )


def test_yolo_command_parses_plain_text() -> None:
    command = YOLOCommand.from_message("run tests -q")
    assert command.text == "run tests -q"
    assert command.reply_topic == "brain.agent.results"


@pytest.mark.asyncio
async def test_processor_routes_known_commands_and_publishes_results() -> None:
    handlers = StubHandlers()
    processor = YOLOCommandProcessor(handlers=handlers)
    producer = DummyProducer()
    processor._producer = producer

    envelope = await processor.process_message(
        {"id": "cmd-1", "command": "run tests -q"}
    )

    assert handlers.called == ["tests:run tests -q"]
    assert envelope["success"] is True
    assert envelope["capability"] == "run_tests"
    assert producer.messages[0][0] == "brain.agent.results"
    assert producer.messages[0][1]["command_id"] == "cmd-1"


@pytest.mark.asyncio
async def test_processor_uses_claude_interpretation_for_unknown_commands() -> None:
    handlers = StubHandlers()
    processor = YOLOCommandProcessor(handlers=handlers)
    producer = DummyProducer()
    processor._producer = producer

    envelope = await processor.process_message(
        {"id": "cmd-2", "command": "find the processor class"}
    )

    assert handlers.called == [
        "interpret:find the processor class",
        "search:search YOLOCommandProcessor",
    ]
    assert envelope["capability"] == "search"
    assert (
        envelope["interpreted"]["normalized_command"] == "search YOLOCommandProcessor"
    )


@pytest.mark.asyncio
async def test_processor_publishes_parse_errors() -> None:
    processor = YOLOCommandProcessor(handlers=StubHandlers())
    producer = DummyProducer()
    processor._producer = producer

    envelope = await processor.process_message({"id": "cmd-3"})

    assert envelope["capability"] == "parse_error"
    assert envelope["success"] is False
    assert producer.messages[0][1]["capability"] == "parse_error"


def test_health_endpoints_report_readiness() -> None:
    processor = YOLOCommandProcessor()
    client = TestClient(processor.app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"

    ready = client.get("/readyz")
    assert ready.status_code == 503
