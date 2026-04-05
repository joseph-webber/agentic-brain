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

"""Temporal client wrapper for workflow management."""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Optional dependency - graceful fallback if not installed
try:
    from temporalio.client import Client, TLSConfig

    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    Client = None  # type: ignore
    TLSConfig = None  # type: ignore


@dataclass
class TemporalConfig:
    """Configuration for Temporal client."""

    host: str = "localhost:7233"
    namespace: str = "default"
    tls_enabled: bool = False
    tls_cert_path: Optional[Path] = None
    tls_key_path: Optional[Path] = None
    tls_ca_path: Optional[Path] = None


def _check_temporalio() -> None:
    """Check if temporalio is available."""
    if not TEMPORALIO_AVAILABLE:
        raise ImportError(
            "temporalio is not installed. Install with: pip install temporalio"
        )


class TemporalClient:
    """Wrapper for Temporal client with connection management."""

    def __init__(self, config: Optional[TemporalConfig] = None):
        """Initialize Temporal client wrapper.

        Args:
            config: Temporal configuration. If None, uses defaults.
        """
        _check_temporalio()
        self.config = config or TemporalConfig()
        self._client: Optional[Client] = None

    async def connect(self) -> Client:
        """Connect to Temporal server.

        Returns:
            Connected Temporal client.
        """
        if self._client is not None:
            return self._client

        tls_config = None
        if self.config.tls_enabled:
            tls_config = await self._create_tls_config()

        self._client = await Client.connect(
            self.config.host,
            namespace=self.config.namespace,
            tls=tls_config,
        )
        return self._client

    async def _create_tls_config(self) -> TLSConfig:
        """Create TLS configuration from config paths.

        Returns:
            TLS configuration for secure connection.
        """
        ssl_context = ssl.create_default_context()

        if self.config.tls_ca_path:
            ssl_context.load_verify_locations(str(self.config.tls_ca_path))

        if self.config.tls_cert_path and self.config.tls_key_path:
            ssl_context.load_cert_chain(
                str(self.config.tls_cert_path),
                str(self.config.tls_key_path),
            )

        return TLSConfig(ssl_context=ssl_context)

    async def start_workflow(
        self,
        workflow: str,
        workflow_id: str,
        task_queue: str,
        args: list[Any],
        **kwargs: Any,
    ) -> Any:
        """Start a workflow execution.

        Args:
            workflow: Workflow class name or reference.
            workflow_id: Unique ID for this workflow execution.
            task_queue: Task queue to execute on.
            args: Positional arguments for workflow.
            **kwargs: Additional workflow options.

        Returns:
            Workflow handle.
        """
        client = await self.connect()
        return await client.start_workflow(
            workflow,
            *args,
            id=workflow_id,
            task_queue=task_queue,
            **kwargs,
        )

    async def get_workflow_handle(self, workflow_id: str) -> Any:
        """Get handle to existing workflow.

        Args:
            workflow_id: Workflow execution ID.

        Returns:
            Workflow handle.
        """
        client = await self.connect()
        return client.get_workflow_handle(workflow_id)

    async def list_workflows(
        self,
        query: Optional[str] = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """List workflow executions.

        Args:
            query: Optional filter query.
            max_results: Maximum workflows to return.

        Returns:
            List of workflow execution info.
        """
        client = await self.connect()
        workflows = []

        async for workflow in client.list_workflows(query):
            workflows.append(
                {
                    "id": workflow.id,
                    "type": workflow.workflow_type,
                    "status": workflow.status,
                    "start_time": workflow.start_time,
                }
            )
            if len(workflows) >= max_results:
                break

        return workflows

    async def close(self) -> None:
        """Close client connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Global client instance
_global_client: Optional[TemporalClient] = None


def get_temporal_client(config: Optional[TemporalConfig] = None) -> TemporalClient:
    """Get or create global Temporal client.

    Args:
        config: Optional configuration for new client.

    Returns:
        Global Temporal client instance.
    """
    global _global_client
    if _global_client is None:
        _global_client = TemporalClient(config)
    return _global_client


async def close_global_client() -> None:
    """Close global client connection."""
    global _global_client
    if _global_client:
        await _global_client.close()
        _global_client = None
