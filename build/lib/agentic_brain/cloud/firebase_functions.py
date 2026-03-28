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

"""Firebase Cloud Functions deployment helpers."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(slots=True)
class FirebaseFunctionDefinition:
    """Declarative definition for a Firebase function deployment."""

    name: str
    entry_point: Optional[str] = None
    trigger: str = "http"
    region: str = "us-central1"
    runtime: str = "python311"
    source_dir: str = "functions"
    event_type: Optional[str] = None
    topic: Optional[str] = None
    schedule: Optional[str] = None
    time_zone: str = "UTC"
    memory: str = "256MiB"
    timeout_seconds: int = 60
    environment: dict[str, str] = field(default_factory=dict)

    def selector(self) -> str:
        return f"functions:{self.name}"


@dataclass(slots=True)
class FirebaseFunctionDeploymentResult:
    """Result of a Firebase function deployment."""

    success: bool
    command: list[str]
    stdout: str = ""
    stderr: str = ""


class FirebaseFunctionsManager:
    """Manage Firebase Cloud Functions deployment workflows."""

    def __init__(
        self,
        project_id: str,
        functions_dir: str,
        firebase_bin: str = "firebase",
        codebase: str = "default",
    ):
        self.project_id = project_id
        self.functions_dir = Path(functions_dir)
        self.firebase_bin = firebase_bin
        self.codebase = codebase

    def build_deploy_command(
        self,
        definition: FirebaseFunctionDefinition,
        *,
        only: bool = True,
        force: bool = False,
    ) -> list[str]:
        command = [
            self.firebase_bin,
            "deploy",
            "--project",
            self.project_id,
            "--config",
            str(self.functions_dir / "firebase.json"),
        ]
        if only:
            command.extend(["--only", definition.selector()])
        if force:
            command.append("--force")
        return command

    def deploy(
        self, definition: FirebaseFunctionDefinition, *, force: bool = False
    ) -> FirebaseFunctionDeploymentResult:
        command = self.build_deploy_command(definition, force=force)
        completed = subprocess.run(
            command,
            cwd=self.functions_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        return FirebaseFunctionDeploymentResult(
            success=completed.returncode == 0,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def render_manifest(
        self, definitions: list[FirebaseFunctionDefinition]
    ) -> dict[str, Any]:
        return {
            "projectId": self.project_id,
            "codebase": self.codebase,
            "functions": [
                {
                    "name": definition.name,
                    "entryPoint": definition.entry_point or definition.name,
                    "trigger": definition.trigger,
                    "region": definition.region,
                    "runtime": definition.runtime,
                    "memory": definition.memory,
                    "timeoutSeconds": definition.timeout_seconds,
                    "eventType": definition.event_type,
                    "topic": definition.topic,
                    "schedule": definition.schedule,
                    "timeZone": definition.time_zone,
                    "environment": definition.environment,
                }
                for definition in definitions
            ],
        }

    def write_manifest(
        self,
        definitions: list[FirebaseFunctionDefinition],
        output_path: Optional[str] = None,
    ) -> Path:
        manifest_path = (
            Path(output_path)
            if output_path
            else self.functions_dir / "agentic-functions.json"
        )
        manifest_path.write_text(
            json.dumps(self.render_manifest(definitions), indent=2), encoding="utf-8"
        )
        return manifest_path

    @staticmethod
    def http_function(name: str, **kwargs: Any) -> FirebaseFunctionDefinition:
        return FirebaseFunctionDefinition(name=name, trigger="http", **kwargs)

    @staticmethod
    def event_function(
        name: str, event_type: str, **kwargs: Any
    ) -> FirebaseFunctionDefinition:
        return FirebaseFunctionDefinition(
            name=name, trigger="event", event_type=event_type, **kwargs
        )

    @staticmethod
    def pubsub_function(
        name: str, topic: str, **kwargs: Any
    ) -> FirebaseFunctionDefinition:
        return FirebaseFunctionDefinition(
            name=name, trigger="pubsub", topic=topic, **kwargs
        )

    @staticmethod
    def scheduled_function(
        name: str, schedule: str, **kwargs: Any
    ) -> FirebaseFunctionDefinition:
        return FirebaseFunctionDefinition(
            name=name, trigger="schedule", schedule=schedule, **kwargs
        )
