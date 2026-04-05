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
Retool Integration for Agentic Brain.

Connect agentic-brain to Retool Workflows and Agents for:
- Triggering Retool workflows from Python
- Using agentic-brain as Retool's LLM backend
- Syncing session data to Retool dashboards
- Building accessible admin interfaces

Retool provides low-code internal tools with AI Agents (2025+).
This integration lets agentic-brain power those agents while
also being controlled by Retool workflows.

Example:
    from agentic_brain.integrations import RetoolClient

    # Initialize with API key
    retool = RetoolClient(
        api_key="retool_xxx",
        org_name="your-org"
    )

    # Trigger a workflow
    result = await retool.trigger_workflow(
        workflow_id="refund-processor",
        data={"order_id": "12345", "reason": "damaged"}
    )

    # List available workflows
    workflows = await retool.list_workflows()

    # Register agentic-brain as LLM resource
    await retool.register_llm_resource(
        name="agentic-brain",
        endpoint="http://localhost:8000/api/v1/chat"
    )

Requirements:
    pip install aiohttp pydantic

Environment Variables:
    RETOOL_API_KEY: Your Retool API key
    RETOOL_ORG: Your Retool organization name
    RETOOL_BASE_URL: Custom Retool URL (for self-hosted)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WorkflowStatus(StrEnum):
    """Retool workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RetoolWorkflow(BaseModel):
    """Retool workflow metadata."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_enabled: bool = True
    trigger_type: str = "manual"  # manual, scheduled, webhook


class WorkflowExecution(BaseModel):
    """Result of a workflow execution."""

    execution_id: str
    workflow_id: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int | None = None


class RetoolResource(BaseModel):
    """Retool API resource configuration."""

    id: str | None = None
    name: str
    type: str = "restapi"
    base_url: str
    headers: dict[str, str] = Field(default_factory=dict)
    auth_type: str = "bearer"  # bearer, basic, none


@dataclass
class RetoolConfig:
    """Retool client configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("RETOOL_API_KEY", ""))
    org_name: str = field(default_factory=lambda: os.getenv("RETOOL_ORG", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv("RETOOL_BASE_URL", "https://api.retool.com")
    )
    timeout: int = 30
    max_retries: int = 3


class RetoolClient:
    """
    Retool API client for workflow automation.

    Enables bidirectional integration:
    1. Trigger Retool workflows from agentic-brain
    2. Register agentic-brain as Retool's LLM resource
    3. Sync data for Retool dashboards

    Example:
        client = RetoolClient(api_key="retool_xxx")

        # Trigger workflow
        result = await client.trigger_workflow(
            "process-order",
            {"order_id": "123"}
        )

        # Check status
        status = await client.get_execution_status(result.execution_id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        org_name: str | None = None,
        base_url: str | None = None,
        config: RetoolConfig | None = None,
    ):
        """
        Initialize Retool client.

        Args:
            api_key: Retool API key (or set RETOOL_API_KEY env var)
            org_name: Organization name (or set RETOOL_ORG env var)
            base_url: Custom base URL for self-hosted Retool
            config: Full configuration object (overrides other params)
        """
        if config:
            self.config = config
        else:
            self.config = RetoolConfig(
                api_key=api_key or os.getenv("RETOOL_API_KEY", ""),
                org_name=org_name or os.getenv("RETOOL_ORG", ""),
                base_url=base_url
                or os.getenv("RETOOL_BASE_URL", "https://api.retool.com"),
            )

        self._session: aiohttp.ClientSession | None = None
        self._workflows_cache: dict[str, RetoolWorkflow] = {}

        if not self.config.api_key:
            logger.warning("No Retool API key configured")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> RetoolClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()

    # ==================== Workflow Operations ====================

    async def list_workflows(self) -> list[RetoolWorkflow]:
        """
        List all workflows in the organization.

        Returns:
            List of workflow metadata
        """
        session = await self._get_session()

        try:
            async with session.get("/api/v1/workflows") as resp:
                resp.raise_for_status()
                data = await resp.json()

                workflows = [
                    RetoolWorkflow(
                        id=w["id"],
                        name=w["name"],
                        description=w.get("description"),
                        is_enabled=w.get("enabled", True),
                        trigger_type=w.get("triggerType", "manual"),
                    )
                    for w in data.get("workflows", [])
                ]

                # Cache for quick lookup
                for wf in workflows:
                    self._workflows_cache[wf.id] = wf
                    self._workflows_cache[wf.name] = wf

                logger.info(f"Listed {len(workflows)} Retool workflows")
                return workflows

        except aiohttp.ClientError as e:
            logger.error(f"Failed to list workflows: {e}")
            raise

    async def trigger_workflow(
        self,
        workflow_id: str,
        data: dict[str, Any] | None = None,
        wait: bool = True,
        timeout: int = 60,
    ) -> WorkflowExecution:
        """
        Trigger a Retool workflow.

        Args:
            workflow_id: Workflow ID or name
            data: Input data for the workflow
            wait: Wait for completion (default True)
            timeout: Max seconds to wait (default 60)

        Returns:
            Workflow execution result

        Example:
            result = await client.trigger_workflow(
                "process-refund",
                data={"order_id": "123", "amount": 50.00}
            )
            print(f"Status: {result.status}")
        """
        session = await self._get_session()

        payload = {
            "data": data or {},
        }

        try:
            started_at = datetime.now(UTC)

            async with session.post(
                f"/api/v1/workflows/{workflow_id}/run",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()

                execution = WorkflowExecution(
                    execution_id=result.get("executionId", ""),
                    workflow_id=workflow_id,
                    status=WorkflowStatus.RUNNING,
                    started_at=started_at,
                )

                logger.info(
                    f"Triggered workflow {workflow_id}: {execution.execution_id}"
                )

                if wait:
                    execution = await self._wait_for_completion(
                        execution.execution_id,
                        timeout=timeout,
                    )

                return execution

        except aiohttp.ClientError as e:
            logger.error(f"Failed to trigger workflow {workflow_id}: {e}")
            return WorkflowExecution(
                execution_id="",
                workflow_id=workflow_id,
                status=WorkflowStatus.FAILED,
                started_at=datetime.now(UTC),
                error=str(e),
            )

    async def _wait_for_completion(
        self,
        execution_id: str,
        timeout: int = 60,
        poll_interval: float = 1.0,
    ) -> WorkflowExecution:
        """Poll for workflow completion."""
        session = await self._get_session()
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            try:
                async with session.get(
                    f"/api/v1/workflows/executions/{execution_id}"
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                    status = WorkflowStatus(data.get("status", "running"))

                    if status in (
                        WorkflowStatus.COMPLETED,
                        WorkflowStatus.FAILED,
                        WorkflowStatus.CANCELLED,
                    ):
                        return WorkflowExecution(
                            execution_id=execution_id,
                            workflow_id=data.get("workflowId", ""),
                            status=status,
                            started_at=datetime.fromisoformat(
                                data.get("startedAt", datetime.now(UTC).isoformat())
                            ),
                            completed_at=(
                                datetime.fromisoformat(data["completedAt"])
                                if data.get("completedAt")
                                else None
                            ),
                            result=data.get("result"),
                            error=data.get("error"),
                            duration_ms=data.get("durationMs"),
                        )

            except aiohttp.ClientError as e:
                logger.warning(f"Error polling execution {execution_id}: {e}")

            await asyncio.sleep(poll_interval)

        # Timeout
        return WorkflowExecution(
            execution_id=execution_id,
            workflow_id="",
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(UTC),
            error=f"Timeout after {timeout}s",
        )

    async def get_execution_status(
        self,
        execution_id: str,
    ) -> WorkflowExecution:
        """
        Get status of a workflow execution.

        Args:
            execution_id: The execution ID from trigger_workflow

        Returns:
            Current execution status
        """
        session = await self._get_session()

        try:
            async with session.get(
                f"/api/v1/workflows/executions/{execution_id}"
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

                return WorkflowExecution(
                    execution_id=execution_id,
                    workflow_id=data.get("workflowId", ""),
                    status=WorkflowStatus(data.get("status", "running")),
                    started_at=datetime.fromisoformat(
                        data.get("startedAt", datetime.now(UTC).isoformat())
                    ),
                    completed_at=(
                        datetime.fromisoformat(data["completedAt"])
                        if data.get("completedAt")
                        else None
                    ),
                    result=data.get("result"),
                    error=data.get("error"),
                    duration_ms=data.get("durationMs"),
                )

        except aiohttp.ClientError as e:
            logger.error(f"Failed to get execution status: {e}")
            raise

    # ==================== Resource Management ====================

    async def register_llm_resource(
        self,
        name: str = "agentic-brain",
        endpoint: str = "http://localhost:8000/api/v1/chat",
        api_key: str | None = None,
    ) -> RetoolResource:
        """
        Register agentic-brain as a Retool REST API resource.

        This allows Retool Agents to use agentic-brain's LLM routing.

        Args:
            name: Resource name in Retool
            endpoint: Agentic-brain chat endpoint URL
            api_key: Optional API key for authentication

        Returns:
            Created resource configuration

        Example:
            resource = await client.register_llm_resource(
                name="brain-llm",
                endpoint="https://api.mycompany.com/brain/chat",
                api_key="secret"
            )
        """
        session = await self._get_session()

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resource = RetoolResource(
            name=name,
            type="restapi",
            base_url=endpoint.rsplit("/", 1)[0],  # Strip endpoint path
            headers=headers,
            auth_type="bearer" if api_key else "none",
        )

        payload = {
            "name": resource.name,
            "type": resource.type,
            "options": {
                "baseUrl": resource.base_url,
                "headers": resource.headers,
                "authType": resource.auth_type,
            },
        }

        try:
            async with session.post(
                "/api/v1/resources",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                resource.id = data.get("id")

                logger.info(f"Registered LLM resource: {name} -> {endpoint}")
                return resource

        except aiohttp.ClientError as e:
            logger.error(f"Failed to register resource: {e}")
            raise

    async def list_resources(self) -> list[RetoolResource]:
        """List all API resources in Retool."""
        session = await self._get_session()

        try:
            async with session.get("/api/v1/resources") as resp:
                resp.raise_for_status()
                data = await resp.json()

                return [
                    RetoolResource(
                        id=r["id"],
                        name=r["name"],
                        type=r.get("type", "restapi"),
                        base_url=r.get("options", {}).get("baseUrl", ""),
                    )
                    for r in data.get("resources", [])
                ]

        except aiohttp.ClientError as e:
            logger.error(f"Failed to list resources: {e}")
            raise

    # ==================== Data Sync ====================

    async def push_session_data(
        self,
        table_name: str,
        sessions: list[dict[str, Any]],
    ) -> int:
        """
        Push session data to Retool DB for dashboards.

        Args:
            table_name: Target table in Retool DB
            sessions: List of session records

        Returns:
            Number of records pushed
        """
        session = await self._get_session()

        payload = {
            "table": table_name,
            "records": sessions,
        }

        try:
            async with session.post(
                "/api/v1/db/upsert",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

                count = data.get("count", len(sessions))
                logger.info(f"Pushed {count} sessions to Retool DB")
                return count

        except aiohttp.ClientError as e:
            logger.error(f"Failed to push session data: {e}")
            raise

    async def sync_metrics(
        self,
        metrics: dict[str, Any],
    ) -> None:
        """
        Sync agentic-brain metrics to Retool for monitoring.

        Args:
            metrics: Dict of metric name -> value

        Example:
            await client.sync_metrics({
                "total_sessions": 1234,
                "active_sessions": 56,
                "tokens_used": 987654,
                "cost_usd": 12.34,
            })
        """
        await self.push_session_data(
            "brain_metrics",
            [{"timestamp": datetime.now(UTC).isoformat(), **metrics}],
        )


# ==================== Convenience Functions ====================


async def create_retool_client(
    api_key: str | None = None,
) -> RetoolClient:
    """
    Create and validate a Retool client.

    Args:
        api_key: Optional API key (uses env var if not provided)

    Returns:
        Configured RetoolClient
    """
    client = RetoolClient(api_key=api_key)

    # Validate connection
    try:
        await client.list_workflows()
        logger.info("Retool connection validated")
    except Exception as e:
        logger.warning(f"Retool connection check failed: {e}")

    return client
