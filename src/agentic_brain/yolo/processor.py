# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException

from .handlers import CommandExecutionResult, CommandHandlers, InterpretedCommand

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class YOLOCommand:
    """Normalized command payload consumed from Redpanda."""

    command_id: str
    text: str
    correlation_id: str | None = None
    reply_topic: str = "brain.agent.results"
    received_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "brain.yolo.commands"

    @classmethod
    def from_message(cls, payload: str | bytes | dict[str, Any]) -> YOLOCommand:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        if isinstance(payload, str):
            raw = payload.strip()
            if not raw:
                raise ValueError("Empty YOLO command payload")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"command": raw}

        if not isinstance(payload, dict):
            raise TypeError("YOLO command payload must be a dict, str, or bytes")

        text = (
            payload.get("command")
            or payload.get("text")
            or payload.get("prompt")
            or payload.get("message")
        )
        if not text or not str(text).strip():
            raise ValueError("YOLO command payload missing command text")

        return cls(
            command_id=str(
                payload.get("command_id") or payload.get("id") or uuid.uuid4()
            ),
            text=str(text).strip(),
            correlation_id=(
                str(payload["correlation_id"])
                if payload.get("correlation_id") is not None
                else None
            ),
            reply_topic=str(payload.get("reply_topic") or "brain.agent.results"),
            received_at=str(
                payload.get("received_at") or datetime.now(UTC).isoformat()
            ),
            metadata=dict(payload.get("metadata") or {}),
            source=str(payload.get("source") or "brain.yolo.commands"),
        )


@dataclass(slots=True)
class ProcessorMetrics:
    messages_received: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    messages_published: int = 0
    last_command_at: float = 0.0
    started_at: float = 0.0


class YOLOCommandProcessor:
    """Consume YOLO commands from Redpanda and publish execution results."""

    COMMAND_TOPIC = "brain.yolo.commands"
    RESULT_TOPIC = "brain.agent.results"

    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        command_topic: str = COMMAND_TOPIC,
        result_topic: str = RESULT_TOPIC,
        consumer_group: str = "yolo-command-processor",
        handlers: CommandHandlers | None = None,
        health_host: str = "127.0.0.1",
        health_port: int = 8091,
        enable_health_server: bool = False,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.command_topic = command_topic
        self.result_topic = result_topic
        self.consumer_group = consumer_group
        self.health_host = health_host
        self.health_port = int(os.getenv("YOLO_HEALTH_PORT", str(health_port)))
        self.enable_health_server = enable_health_server or os.getenv(
            "YOLO_HEALTH_SERVER", "false"
        ).lower() in {"1", "true", "yes", "on"}

        self.handlers = handlers or CommandHandlers(status_provider=self.status)
        if self.handlers.status_provider is None:
            self.handlers.status_provider = self.status

        self._consumer = None
        self._producer = None
        self._consume_task: asyncio.Task[None] | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._health_server = None
        self._running = False
        self._ready = False
        self._stopping = False
        self._shutdown_event = asyncio.Event()
        self._metrics = ProcessorMetrics()
        self._hostname = socket.gethostname()
        self.app = self._create_health_app()

    async def start(self) -> None:
        """Start Kafka clients, health server, and the consumer loop."""
        if self._running:
            return

        AIOKafkaConsumer, AIOKafkaProducer = self._load_aiokafka()
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            )
            await self._producer.start()

            self._consumer = AIOKafkaConsumer(
                self.command_topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=lambda value: value.decode("utf-8"),
            )
            await self._consumer.start()
        except Exception:
            logger.exception("Failed to start YOLO Kafka clients")
            if self._consumer is not None:
                try:
                    await self._consumer.stop()
                except Exception:
                    logger.debug(
                        "Failed stopping consumer after startup error", exc_info=True
                    )
                self._consumer = None
            if self._producer is not None:
                try:
                    await self._producer.stop()
                except Exception:
                    logger.debug(
                        "Failed stopping producer after startup error", exc_info=True
                    )
                self._producer = None
            raise

        self._metrics.started_at = time.time()
        self._running = True
        self._ready = True
        self._shutdown_event.clear()
        self._install_signal_handlers()
        self._consume_task = asyncio.create_task(
            self._consume_loop(), name="yolo-consume"
        )

        if self.enable_health_server:
            self._health_task = asyncio.create_task(
                self._serve_health_app(), name="yolo-health-server"
            )

        logger.info(
            "YOLO command processor started (topic=%s, result_topic=%s, bootstrap=%s)",
            self.command_topic,
            self.result_topic,
            self.bootstrap_servers,
        )

    async def stop(self) -> None:
        """Stop processing and close all resources gracefully."""
        if self._stopping:
            return

        self._stopping = True
        self._running = False
        self._ready = False

        if self._consume_task is not None:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None

        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                logger.exception("Failed to stop YOLO consumer")
            self._consumer = None

        if self._producer is not None:
            try:
                await self._producer.stop()
            except Exception:
                logger.exception("Failed to stop YOLO producer")
            self._producer = None

        if self._health_server is not None:
            self._health_server.should_exit = True

        if self._health_task is not None:
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
            self._health_server = None

        self._shutdown_event.set()
        self._stopping = False
        logger.info("YOLO command processor stopped")

    async def run_forever(self) -> None:
        """Start the processor and block until a shutdown signal is received."""
        await self.start()
        await self._shutdown_event.wait()

    def status(self) -> dict[str, Any]:
        """Return current processor health and metrics."""
        uptime = (
            time.time() - self._metrics.started_at if self._metrics.started_at else 0
        )
        return {
            "status": (
                "ready" if self._ready else ("running" if self._running else "stopped")
            ),
            "running": self._running,
            "ready": self._ready,
            "bootstrap_servers": self.bootstrap_servers,
            "command_topic": self.command_topic,
            "result_topic": self.result_topic,
            "consumer_group": self.consumer_group,
            "hostname": self._hostname,
            "health_server": {
                "enabled": self.enable_health_server,
                "host": self.health_host,
                "port": self.health_port,
            },
            "metrics": {
                "messages_received": self._metrics.messages_received,
                "messages_processed": self._metrics.messages_processed,
                "messages_failed": self._metrics.messages_failed,
                "messages_published": self._metrics.messages_published,
                "last_command_at": (
                    datetime.fromtimestamp(
                        self._metrics.last_command_at, tz=UTC
                    ).isoformat()
                    if self._metrics.last_command_at
                    else None
                ),
                "uptime_seconds": round(uptime, 1),
            },
        }

    async def process_message(
        self, payload: str | bytes | dict[str, Any]
    ) -> dict[str, Any]:
        """Process one YOLO command payload and publish the result."""
        self._metrics.messages_received += 1
        self._metrics.last_command_at = time.time()
        raw_preview = self._payload_preview(payload)

        try:
            command = YOLOCommand.from_message(payload)
        except Exception as exc:
            logger.exception("Failed to parse YOLO command payload")
            self._metrics.messages_failed += 1
            command = YOLOCommand(
                command_id=str(uuid.uuid4()),
                text=raw_preview,
                metadata={"raw_payload": raw_preview},
                reply_topic=self.result_topic,
            )
            error_result = CommandExecutionResult(
                success=False,
                capability="parse_error",
                command=raw_preview,
                error=str(exc),
                exit_code=1,
            )
            envelope = self._build_result_envelope(command, error_result)
            await self._publish_result(self.result_topic, envelope)
            return envelope

        try:
            result, interpreted = await self._execute_command(command)
            envelope = self._build_result_envelope(
                command, result, interpreted=interpreted
            )
            self._metrics.messages_processed += 1
        except Exception as exc:
            logger.exception("Failed to process YOLO command %s", command.command_id)
            self._metrics.messages_failed += 1
            error_result = CommandExecutionResult(
                success=False,
                capability="processor_error",
                command=command.text,
                error=str(exc),
                exit_code=1,
            )
            envelope = self._build_result_envelope(command, error_result)

        await self._publish_result(command.reply_topic or self.result_topic, envelope)
        return envelope

    async def _execute_command(
        self, command: YOLOCommand
    ) -> tuple[CommandExecutionResult, InterpretedCommand | None]:
        interpreted: InterpretedCommand | None = None
        capability = self._infer_capability(command.text)
        normalized_command = command.text

        if capability is None:
            interpreted = await self.handlers.interpret(command.text)
            capability = interpreted.capability
            normalized_command = interpreted.normalized_command
            logger.info(
                "YOLO command %s interpreted by Claude as %s",
                command.command_id,
                capability,
            )

        if capability == "run_tests":
            result = await self.handlers.run_tests(normalized_command)
        elif capability == "deploy":
            result = await self.handlers.deploy(normalized_command)
        elif capability == "check_status":
            result = await self.handlers.check_status(normalized_command)
        elif capability == "search":
            result = await self.handlers.search(normalized_command)
        else:  # pragma: no cover - guarded by interpreter validation
            raise ValueError(f"Unsupported YOLO capability: {capability}")

        return result, interpreted

    async def _publish_result(self, topic: str, payload: dict[str, Any]) -> None:
        if self._producer is None:
            raise RuntimeError("YOLO producer is not running")
        await self._producer.send_and_wait(
            topic,
            payload,
            key=str(payload["command_id"]).encode("utf-8"),
        )
        self._metrics.messages_published += 1

    async def _consume_loop(self) -> None:
        """Main Kafka consumer loop."""
        while self._running:
            try:
                if self._consumer is None:
                    break
                records = await self._consumer.getmany(timeout_ms=500, max_records=25)
                for _topic_partition, messages in records.items():
                    for message in messages:
                        await self.process_message(message.value)
                        await self._consumer.commit()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("YOLO consumer loop error")
                await asyncio.sleep(1.0)

    def _build_result_envelope(
        self,
        command: YOLOCommand,
        result: CommandExecutionResult,
        *,
        interpreted: InterpretedCommand | None = None,
    ) -> dict[str, Any]:
        completed_at = datetime.now(UTC).isoformat()
        envelope = {
            "command_id": command.command_id,
            "correlation_id": command.correlation_id,
            "command": command.text,
            "capability": result.capability,
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "received_at": command.received_at,
            "completed_at": completed_at,
            "processor": {
                "hostname": self._hostname,
                "consumer_group": self.consumer_group,
                "command_topic": self.command_topic,
                "result_topic": self.result_topic,
            },
            "metadata": {
                **command.metadata,
                **result.metadata,
            },
        }
        if interpreted is not None:
            envelope["interpreted"] = {
                "capability": interpreted.capability,
                "normalized_command": interpreted.normalized_command,
                "reasoning": interpreted.reasoning,
            }
        return envelope

    def _infer_capability(self, command_text: str) -> str | None:
        lowered = command_text.strip().lower()
        if (
            lowered.startswith("run tests")
            or lowered.startswith("test ")
            or lowered == "test"
        ):
            return "run_tests"
        if lowered.startswith("deploy"):
            return "deploy"
        if (
            lowered.startswith("check status")
            or lowered == "status"
            or lowered.startswith("status ")
        ):
            return "check_status"
        if lowered.startswith("search"):
            return "search"
        return None

    def _install_signal_handlers(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.create_task(self._handle_signal(s))
                )
            except (NotImplementedError, RuntimeError):
                logger.debug("Signal handlers unavailable for %s", sig.name)

    async def _handle_signal(self, sig: signal.Signals) -> None:
        logger.info("Received %s, shutting down YOLO processor", sig.name)
        await self.stop()

    async def _serve_health_app(self) -> None:
        try:
            import uvicorn
        except ImportError as exc:  # pragma: no cover - dependency issue
            logger.warning("uvicorn not installed, health server disabled: %s", exc)
            return

        config = uvicorn.Config(
            self.app,
            host=self.health_host,
            port=self.health_port,
            log_level="info",
        )
        self._health_server = uvicorn.Server(config)
        await self._health_server.serve()

    def _create_health_app(self) -> FastAPI:
        app = FastAPI(title="YOLO Command Processor", version="1.0.0")

        @app.get("/health")
        async def health() -> dict[str, Any]:
            return self.status()

        @app.get("/readyz")
        async def readyz() -> dict[str, str]:
            if not self._ready:
                raise HTTPException(status_code=503, detail={"status": "not ready"})
            return {"status": "ready"}

        @app.get("/livez")
        async def livez() -> dict[str, str]:
            if not self._running:
                raise HTTPException(status_code=503, detail={"status": "stopped"})
            return {"status": "alive"}

        return app

    @staticmethod
    def _load_aiokafka():
        try:
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
        except ImportError as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "aiokafka is required for YOLOCommandProcessor. Install with 'pip install aiokafka'."
            ) from exc
        return AIOKafkaConsumer, AIOKafkaProducer

    @staticmethod
    def _payload_preview(payload: str | bytes | dict[str, Any]) -> str:
        if isinstance(payload, bytes):
            preview = payload.decode("utf-8", errors="replace")
        elif isinstance(payload, dict):
            preview = json.dumps(payload, default=str)
        else:
            preview = str(payload)
        return preview[:500]


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("YOLO_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    processor = YOLOCommandProcessor()
    try:
        await processor.run_forever()
    finally:
        await processor.stop()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
