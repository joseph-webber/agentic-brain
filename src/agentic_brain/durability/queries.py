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
Workflow Queries for Agentic Brain

Queries provide read-only access to workflow state.
This provides durable query semantics for AI workflows.

Features:
- Type-safe query definitions
- Sync and async query handlers
- Query validation
- Query history and caching
"""

import asyncio
import inspect
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueryStatus(Enum):
    """Status of query execution"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"


@dataclass
class QueryDefinition:
    """
    Definition of a query type

    Queries are read-only operations that inspect workflow state.
    """

    name: str
    description: str = ""
    return_type: Optional[Type] = None
    arg_type: Optional[Type] = None

    def validate_args(self, args: Any) -> bool:
        """Validate query arguments"""
        if self.arg_type is None:
            return args is None
        return isinstance(args, self.arg_type)


@dataclass
class QueryRequest:
    """
    A query request to a workflow
    """

    query_id: str
    query_name: str
    workflow_id: str
    args: Any = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    requester_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_name": self.query_name,
            "workflow_id": self.workflow_id,
            "args": self.args,
            "created_at": self.created_at.isoformat(),
            "requester_id": self.requester_id,
        }


@dataclass
class QueryResult:
    """
    Result of a query execution
    """

    query_id: str
    query_name: str
    workflow_id: str
    status: QueryStatus
    result: Any = None
    error: Optional[str] = None

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_name": self.query_name,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_ms": self.duration_ms,
        }


class QueryHandler:
    """
    Handler for workflow queries

    Manages query definitions and execution.
    """

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id

        # Registered query handlers
        self._handlers: Dict[str, Callable] = {}

        # Query definitions
        self._definitions: Dict[str, QueryDefinition] = {}

        # Query history
        self._history: List[QueryResult] = []

        # Result cache (optional)
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}

    def define_query(
        self,
        name: str,
        description: str = "",
        return_type: Optional[Type] = None,
        arg_type: Optional[Type] = None,
    ) -> QueryDefinition:
        """Define a new query type"""
        definition = QueryDefinition(
            name=name,
            description=description,
            return_type=return_type,
            arg_type=arg_type,
        )
        self._definitions[name] = definition
        return definition

    def register_handler(
        self,
        query_name: str,
        handler: Callable,
    ) -> None:
        """Register a handler for a query type"""
        self._handlers[query_name] = handler
        logger.debug(f"Registered query handler for '{query_name}'")

    async def execute(
        self,
        request: QueryRequest,
        use_cache: bool = False,
        cache_ttl_seconds: float = 60.0,
    ) -> QueryResult:
        """
        Execute a query

        Args:
            request: The query request
            use_cache: Whether to use cached results
            cache_ttl_seconds: Cache time-to-live

        Returns:
            QueryResult with status and result/error
        """
        start_time = datetime.now(UTC)

        # Check cache
        cache_key = f"{request.query_name}:{request.args}"
        if use_cache and cache_key in self._cache:
            cache_time = self._cache_ttl.get(cache_key)
            if (
                cache_time
                and (datetime.now(UTC) - cache_time).total_seconds() < cache_ttl_seconds
            ):
                cached = self._cache[cache_key]
                return QueryResult(
                    query_id=request.query_id,
                    query_name=request.query_name,
                    workflow_id=request.workflow_id,
                    status=QueryStatus.SUCCESS,
                    result=cached,
                    completed_at=datetime.now(UTC),
                    duration_ms=0,
                )

        # Validate args
        definition = self._definitions.get(request.query_name)
        if definition and not definition.validate_args(request.args):
            result = QueryResult(
                query_id=request.query_id,
                query_name=request.query_name,
                workflow_id=request.workflow_id,
                status=QueryStatus.FAILED,
                error="Invalid query arguments",
                completed_at=datetime.now(UTC),
                duration_ms=(datetime.now(UTC) - start_time).total_seconds() * 1000,
            )
            self._history.append(result)
            return result

        # Find handler
        handler = self._handlers.get(request.query_name)
        if not handler:
            result = QueryResult(
                query_id=request.query_id,
                query_name=request.query_name,
                workflow_id=request.workflow_id,
                status=QueryStatus.NOT_FOUND,
                error=f"No handler for query '{request.query_name}'",
                completed_at=datetime.now(UTC),
                duration_ms=(datetime.now(UTC) - start_time).total_seconds() * 1000,
            )
            self._history.append(result)
            return result

        # Execute handler
        try:
            if inspect.iscoroutinefunction(handler):
                if request.args is not None:
                    query_result = await handler(request.args)
                else:
                    query_result = await handler()
            else:
                if request.args is not None:
                    query_result = handler(request.args)
                else:
                    query_result = handler()

            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - start_time).total_seconds() * 1000

            # Cache result
            if use_cache:
                self._cache[cache_key] = query_result
                self._cache_ttl[cache_key] = completed_at

            result = QueryResult(
                query_id=request.query_id,
                query_name=request.query_name,
                workflow_id=request.workflow_id,
                status=QueryStatus.SUCCESS,
                result=query_result,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )

        except Exception as e:
            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - start_time).total_seconds() * 1000

            result = QueryResult(
                query_id=request.query_id,
                query_name=request.query_name,
                workflow_id=request.workflow_id,
                status=QueryStatus.FAILED,
                error=str(e),
                completed_at=completed_at,
                duration_ms=duration_ms,
            )
            logger.error(f"Query execution error: {e}")

        self._history.append(result)
        return result

    def get_history(
        self,
        query_name: Optional[str] = None,
        status: Optional[QueryStatus] = None,
        limit: int = 100,
    ) -> List[QueryResult]:
        """Get query history with optional filters"""
        history = self._history

        if query_name:
            history = [r for r in history if r.query_name == query_name]

        if status:
            history = [r for r in history if r.status == status]

        return history[-limit:]

    def clear_cache(self) -> int:
        """Clear query cache, returns count cleared"""
        count = len(self._cache)
        self._cache.clear()
        self._cache_ttl.clear()
        return count

    def list_queries(self) -> List[Dict[str, Any]]:
        """List all registered queries"""
        return [
            {
                "name": name,
                "description": defn.description,
                "has_handler": name in self._handlers,
            }
            for name, defn in self._definitions.items()
        ]


class QueryDispatcher:
    """
    Central dispatcher for workflow queries

    Routes queries to appropriate workflow handlers.
    """

    def __init__(self):
        self._handlers: Dict[str, QueryHandler] = {}

    def register_workflow(self, workflow_id: str) -> QueryHandler:
        """Register a workflow for query handling"""
        if workflow_id not in self._handlers:
            handler = QueryHandler(workflow_id)
            self._handlers[workflow_id] = handler
        return self._handlers[workflow_id]

    def unregister_workflow(self, workflow_id: str) -> None:
        """Unregister a workflow"""
        self._handlers.pop(workflow_id, None)

    async def query(
        self,
        workflow_id: str,
        query_name: str,
        args: Any = None,
        requester_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> QueryResult:
        """
        Execute a query on a workflow

        Args:
            workflow_id: Target workflow ID
            query_name: Name of the query
            args: Optional query arguments
            requester_id: Optional requester identifier
            timeout: Query timeout in seconds

        Returns:
            QueryResult with status and result/error
        """
        handler = self._handlers.get(workflow_id)
        if not handler:
            return QueryResult(
                query_id=str(uuid.uuid4()),
                query_name=query_name,
                workflow_id=workflow_id,
                status=QueryStatus.NOT_FOUND,
                error=f"Workflow {workflow_id} not found",
            )

        request = QueryRequest(
            query_id=str(uuid.uuid4()),
            query_name=query_name,
            workflow_id=workflow_id,
            args=args,
            requester_id=requester_id,
        )

        try:
            return await asyncio.wait_for(
                handler.execute(request),
                timeout=timeout,
            )
        except TimeoutError:
            return QueryResult(
                query_id=request.query_id,
                query_name=query_name,
                workflow_id=workflow_id,
                status=QueryStatus.TIMEOUT,
                error=f"Query timed out after {timeout}s",
            )

    def get_handler(self, workflow_id: str) -> Optional[QueryHandler]:
        """Get query handler for a workflow"""
        return self._handlers.get(workflow_id)


# Global query dispatcher
_dispatcher: Optional[QueryDispatcher] = None


def get_query_dispatcher() -> QueryDispatcher:
    """Get the global query dispatcher"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = QueryDispatcher()
    return _dispatcher


# Decorator for query handlers
def query_handler(query_name: str):
    """
    Decorator to mark a method as a query handler

    Usage:
        class MyWorkflow(DurableWorkflow):
            @query_handler("get_progress")
            def get_progress(self):
                return {"completed": self.completed, "total": self.total}
    """

    def decorator(func: Callable) -> Callable:
        func._query_name = query_name
        func._is_query_handler = True
        return func

    return decorator


def extract_query_handlers(obj: Any) -> Dict[str, Callable]:
    """
    Extract all query handlers from an object

    Returns dict of query_name -> handler method
    """
    handlers = {}
    for name in dir(obj):
        method = getattr(obj, name)
        if callable(method) and hasattr(method, "_is_query_handler"):
            handlers[method._query_name] = method
    return handlers


# Common query definitions for AI workflows
STATUS_QUERY = QueryDefinition(
    name="status",
    description="Get current workflow status",
    return_type=dict,
)

PROGRESS_QUERY = QueryDefinition(
    name="progress",
    description="Get workflow progress",
    return_type=dict,
)

STATE_QUERY = QueryDefinition(
    name="state",
    description="Get full workflow state",
    return_type=dict,
)

HISTORY_QUERY = QueryDefinition(
    name="history",
    description="Get workflow event history",
    return_type=list,
)

METRICS_QUERY = QueryDefinition(
    name="metrics",
    description="Get workflow metrics (LLM calls, tokens, etc.)",
    return_type=dict,
)

RESULT_QUERY = QueryDefinition(
    name="result",
    description="Get workflow result (if completed)",
    return_type=Any,
)


# Convenience function for quick queries
async def query_workflow(
    workflow_id: str,
    query_name: str,
    args: Any = None,
) -> Any:
    """
    Quick way to query a workflow

    Returns the result directly, raises exception on error.
    """
    dispatcher = get_query_dispatcher()
    result = await dispatcher.query(workflow_id, query_name, args)

    if result.status == QueryStatus.SUCCESS:
        return result.result
    elif result.status == QueryStatus.NOT_FOUND:
        raise KeyError(f"Workflow {workflow_id} or query {query_name} not found")
    elif result.status == QueryStatus.TIMEOUT:
        raise TimeoutError(result.error)
    else:
        raise RuntimeError(result.error or "Query failed")
