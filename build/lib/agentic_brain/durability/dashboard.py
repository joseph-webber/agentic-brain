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
Workflow Monitoring Dashboard API for Agentic Brain

REST API endpoints for workflow monitoring and management.
This provides durable dashboard capabilities.

Features:
- List running/completed/failed workflows
- Workflow search and filtering
- Workflow state inspection
- Signal sending
- Query execution
- Workflow cancellation
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowSummary:
    """Summary of a workflow for dashboard display"""

    workflow_id: str
    workflow_type: str
    status: str  # running, completed, failed, cancelled

    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # Progress
    current_activity: Optional[str] = None
    activities_completed: int = 0
    activities_total: int = 0

    # Result
    result: Optional[Any] = None
    error: Optional[str] = None

    # Metadata
    version: Optional[str] = None
    worker_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_ms": self.duration_ms,
            "current_activity": self.current_activity,
            "activities_completed": self.activities_completed,
            "activities_total": self.activities_total,
            "result": self.result,
            "error": self.error,
            "version": self.version,
            "worker_id": self.worker_id,
        }


@dataclass
class WorkflowFilter:
    """Filter for workflow queries"""

    workflow_type: Optional[str] = None
    status: Optional[str] = None
    started_after: Optional[datetime] = None
    started_before: Optional[datetime] = None
    has_error: Optional[bool] = None
    worker_id: Optional[str] = None
    version: Optional[str] = None
    search_term: Optional[str] = None


@dataclass
class DashboardStats:
    """Aggregated statistics for dashboard"""

    total_workflows: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0

    # Performance
    avg_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0

    # Activity stats
    total_activities: int = 0
    activities_per_workflow: float = 0.0

    # Time range
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_workflows": self.total_workflows,
            "running": self.running,
            "completed": self.completed,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "avg_duration_ms": self.avg_duration_ms,
            "p50_duration_ms": self.p50_duration_ms,
            "p95_duration_ms": self.p95_duration_ms,
            "p99_duration_ms": self.p99_duration_ms,
            "total_activities": self.total_activities,
            "activities_per_workflow": self.activities_per_workflow,
            "period_start": (
                self.period_start.isoformat() if self.period_start else None
            ),
            "period_end": self.period_end.isoformat() if self.period_end else None,
        }


class WorkflowDashboard:
    """
    Dashboard service for workflow monitoring

    Provides:
    - Workflow listing and search
    - Statistics and metrics
    - Signal and query operations
    - Workflow management (cancel, retry)
    """

    def __init__(self):
        # In-memory storage for demo (would use Neo4j in production)
        self._workflows: Dict[str, WorkflowSummary] = {}
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def register_workflow(
        self,
        workflow_id: str,
        workflow_type: str,
        version: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> WorkflowSummary:
        """Register a new workflow"""
        summary = WorkflowSummary(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            status="running",
            started_at=datetime.now(UTC),
            version=version,
            worker_id=worker_id,
        )
        self._workflows[workflow_id] = summary
        self._events[workflow_id] = []
        return summary

    def update_workflow(
        self,
        workflow_id: str,
        status: Optional[str] = None,
        current_activity: Optional[str] = None,
        activities_completed: Optional[int] = None,
        activities_total: Optional[int] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> Optional[WorkflowSummary]:
        """Update workflow status"""
        summary = self._workflows.get(workflow_id)
        if not summary:
            return None

        if status:
            summary.status = status
            if status in ("completed", "failed", "cancelled"):
                summary.completed_at = datetime.now(UTC)
                summary.duration_ms = (
                    summary.completed_at - summary.started_at
                ).total_seconds() * 1000

        if current_activity is not None:
            summary.current_activity = current_activity
        if activities_completed is not None:
            summary.activities_completed = activities_completed
        if activities_total is not None:
            summary.activities_total = activities_total
        if result is not None:
            summary.result = result
        if error is not None:
            summary.error = error

        return summary

    def record_event(
        self,
        workflow_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Record a workflow event"""
        if workflow_id not in self._events:
            self._events[workflow_id] = []

        self._events[workflow_id].append(
            {
                "type": event_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "data": data,
            }
        )

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowSummary]:
        """Get a single workflow"""
        return self._workflows.get(workflow_id)

    def list_workflows(
        self,
        filter: Optional[WorkflowFilter] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WorkflowSummary]:
        """List workflows with optional filtering"""
        workflows = list(self._workflows.values())

        if filter:
            if filter.workflow_type:
                workflows = [
                    w for w in workflows if w.workflow_type == filter.workflow_type
                ]
            if filter.status:
                workflows = [w for w in workflows if w.status == filter.status]
            if filter.started_after:
                workflows = [
                    w for w in workflows if w.started_at >= filter.started_after
                ]
            if filter.started_before:
                workflows = [
                    w for w in workflows if w.started_at <= filter.started_before
                ]
            if filter.has_error is not None:
                if filter.has_error:
                    workflows = [w for w in workflows if w.error]
                else:
                    workflows = [w for w in workflows if not w.error]
            if filter.worker_id:
                workflows = [w for w in workflows if w.worker_id == filter.worker_id]
            if filter.version:
                workflows = [w for w in workflows if w.version == filter.version]
            if filter.search_term:
                term = filter.search_term.lower()
                workflows = [
                    w
                    for w in workflows
                    if term in w.workflow_id.lower()
                    or term in w.workflow_type.lower()
                    or (w.error and term in w.error.lower())
                ]

        # Sort by started_at descending
        workflows.sort(key=lambda w: w.started_at, reverse=True)

        return workflows[offset : offset + limit]

    def get_workflow_events(
        self,
        workflow_id: str,
        event_types: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get events for a workflow"""
        events = self._events.get(workflow_id, [])

        if event_types:
            events = [e for e in events if e["type"] in event_types]

        return events[-limit:]

    def get_stats(
        self,
        period_hours: int = 24,
        workflow_type: Optional[str] = None,
    ) -> DashboardStats:
        """Get aggregated statistics"""
        cutoff = datetime.now(UTC) - timedelta(hours=period_hours)

        workflows = [w for w in self._workflows.values() if w.started_at >= cutoff]

        if workflow_type:
            workflows = [w for w in workflows if w.workflow_type == workflow_type]

        stats = DashboardStats(
            total_workflows=len(workflows),
            running=len([w for w in workflows if w.status == "running"]),
            completed=len([w for w in workflows if w.status == "completed"]),
            failed=len([w for w in workflows if w.status == "failed"]),
            cancelled=len([w for w in workflows if w.status == "cancelled"]),
            period_start=cutoff,
            period_end=datetime.now(UTC),
        )

        # Calculate duration percentiles
        durations = [w.duration_ms for w in workflows if w.duration_ms]
        if durations:
            durations.sort()
            stats.avg_duration_ms = sum(durations) / len(durations)
            stats.p50_duration_ms = durations[len(durations) // 2]
            stats.p95_duration_ms = durations[int(len(durations) * 0.95)]
            stats.p99_duration_ms = durations[int(len(durations) * 0.99)]

        # Activity stats
        stats.total_activities = sum(w.activities_completed for w in workflows)
        if workflows:
            stats.activities_per_workflow = stats.total_activities / len(workflows)

        return stats

    async def send_signal(
        self,
        workflow_id: str,
        signal_name: str,
        payload: Any = None,
    ) -> Dict[str, Any]:
        """Send a signal to a workflow"""
        from .signals import get_signal_dispatcher

        dispatcher = get_signal_dispatcher()
        signal = await dispatcher.send_signal(
            workflow_id=workflow_id,
            signal_name=signal_name,
            payload=payload,
        )

        self.record_event(
            workflow_id,
            "signal_sent",
            {
                "signal_name": signal_name,
                "payload": payload,
            },
        )

        return signal.to_dict()

    async def execute_query(
        self,
        workflow_id: str,
        query_name: str,
        args: Any = None,
    ) -> Dict[str, Any]:
        """Execute a query on a workflow"""
        from .queries import get_query_dispatcher

        dispatcher = get_query_dispatcher()
        result = await dispatcher.query(
            workflow_id=workflow_id,
            query_name=query_name,
            args=args,
        )

        return result.to_dict()

    async def cancel_workflow(
        self,
        workflow_id: str,
        reason: str = "",
    ) -> bool:
        """Cancel a running workflow"""
        summary = self._workflows.get(workflow_id)
        if not summary or summary.status != "running":
            return False

        # Send cancel signal
        await self.send_signal(
            workflow_id=workflow_id,
            signal_name="cancel",
            payload={"reason": reason},
        )

        self.update_workflow(
            workflow_id=workflow_id,
            status="cancelled",
            error=f"Cancelled: {reason}",
        )

        return True

    async def retry_workflow(
        self,
        workflow_id: str,
    ) -> Optional[str]:
        """Retry a failed workflow"""
        summary = self._workflows.get(workflow_id)
        if not summary or summary.status != "failed":
            return None

        # Create new workflow with same parameters
        from .recovery import recover_workflow

        result = await recover_workflow(workflow_id)
        if result and result.recovered:
            return result.workflow_id

        return None

    def get_workflow_types(self) -> List[Dict[str, Any]]:
        """Get list of workflow types with counts"""
        types: Dict[str, Dict[str, int]] = {}

        for w in self._workflows.values():
            if w.workflow_type not in types:
                types[w.workflow_type] = {
                    "total": 0,
                    "running": 0,
                    "completed": 0,
                    "failed": 0,
                }

            types[w.workflow_type]["total"] += 1
            types[w.workflow_type][w.status] = (
                types[w.workflow_type].get(w.status, 0) + 1
            )

        return [{"workflow_type": wt, **counts} for wt, counts in types.items()]

    def get_worker_stats(self) -> List[Dict[str, Any]]:
        """Get statistics by worker"""
        workers: Dict[str, Dict[str, Any]] = {}

        for w in self._workflows.values():
            worker_id = w.worker_id or "unknown"
            if worker_id not in workers:
                workers[worker_id] = {
                    "worker_id": worker_id,
                    "workflows_total": 0,
                    "workflows_running": 0,
                    "workflows_completed": 0,
                    "workflows_failed": 0,
                    "avg_duration_ms": 0.0,
                    "durations": [],
                }

            workers[worker_id]["workflows_total"] += 1
            if w.status == "running":
                workers[worker_id]["workflows_running"] += 1
            elif w.status == "completed":
                workers[worker_id]["workflows_completed"] += 1
                if w.duration_ms:
                    workers[worker_id]["durations"].append(w.duration_ms)
            elif w.status == "failed":
                workers[worker_id]["workflows_failed"] += 1

        # Calculate averages
        for worker in workers.values():
            durations = worker.pop("durations")
            if durations:
                worker["avg_duration_ms"] = sum(durations) / len(durations)

        return list(workers.values())


# Global dashboard instance
_dashboard: Optional[WorkflowDashboard] = None


def get_workflow_dashboard() -> WorkflowDashboard:
    """Get the global workflow dashboard"""
    global _dashboard
    if _dashboard is None:
        _dashboard = WorkflowDashboard()
    return _dashboard


# FastAPI routes for dashboard (if FastAPI is available)
def create_dashboard_routes():
    """Create FastAPI routes for the dashboard"""
    try:
        from fastapi import APIRouter, HTTPException, Query
        from pydantic import BaseModel

        router = APIRouter(prefix="/api/workflows", tags=["workflows"])

        class SignalRequest(BaseModel):
            signal_name: str
            payload: Optional[Any] = None

        class QueryRequest(BaseModel):
            query_name: str
            args: Optional[Any] = None

        class CancelRequest(BaseModel):
            reason: str = ""

        @router.get("/")
        async def list_workflows(
            workflow_type: Optional[str] = None,
            status: Optional[str] = None,
            limit: int = Query(default=100, le=1000),
            offset: int = 0,
        ):
            """List workflows with optional filters"""
            dashboard = get_workflow_dashboard()
            filter = WorkflowFilter(
                workflow_type=workflow_type,
                status=status,
            )
            workflows = dashboard.list_workflows(filter, limit, offset)
            return {"workflows": [w.to_dict() for w in workflows]}

        @router.get("/stats")
        async def get_stats(
            period_hours: int = 24,
            workflow_type: Optional[str] = None,
        ):
            """Get workflow statistics"""
            dashboard = get_workflow_dashboard()
            stats = dashboard.get_stats(period_hours, workflow_type)
            return stats.to_dict()

        @router.get("/types")
        async def get_workflow_types():
            """Get workflow types with counts"""
            dashboard = get_workflow_dashboard()
            return {"types": dashboard.get_workflow_types()}

        @router.get("/workers")
        async def get_worker_stats():
            """Get worker statistics"""
            dashboard = get_workflow_dashboard()
            return {"workers": dashboard.get_worker_stats()}

        @router.get("/{workflow_id}")
        async def get_workflow(workflow_id: str):
            """Get a single workflow"""
            dashboard = get_workflow_dashboard()
            workflow = dashboard.get_workflow(workflow_id)
            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")
            return workflow.to_dict()

        @router.get("/{workflow_id}/events")
        async def get_workflow_events(
            workflow_id: str,
            limit: int = 100,
        ):
            """Get workflow events"""
            dashboard = get_workflow_dashboard()
            events = dashboard.get_workflow_events(workflow_id, limit=limit)
            return {"events": events}

        @router.post("/{workflow_id}/signal")
        async def send_signal(workflow_id: str, request: SignalRequest):
            """Send a signal to a workflow"""
            dashboard = get_workflow_dashboard()
            result = await dashboard.send_signal(
                workflow_id, request.signal_name, request.payload
            )
            return result

        @router.post("/{workflow_id}/query")
        async def execute_query(workflow_id: str, request: QueryRequest):
            """Execute a query on a workflow"""
            dashboard = get_workflow_dashboard()
            result = await dashboard.execute_query(
                workflow_id, request.query_name, request.args
            )
            return result

        @router.post("/{workflow_id}/cancel")
        async def cancel_workflow(workflow_id: str, request: CancelRequest):
            """Cancel a running workflow"""
            dashboard = get_workflow_dashboard()
            success = await dashboard.cancel_workflow(workflow_id, request.reason)
            if not success:
                raise HTTPException(
                    status_code=400, detail="Workflow not running or not found"
                )
            return {"cancelled": True}

        @router.post("/{workflow_id}/retry")
        async def retry_workflow(workflow_id: str):
            """Retry a failed workflow"""
            dashboard = get_workflow_dashboard()
            new_id = await dashboard.retry_workflow(workflow_id)
            if not new_id:
                raise HTTPException(
                    status_code=400, detail="Workflow not failed or not found"
                )
            return {"new_workflow_id": new_id}

        return router

    except ImportError:
        logger.warning("FastAPI not available, dashboard routes not created")
        return None
