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
Durability package for fault-tolerant workflow execution.

This package provides durable execution for AI agent workflows,
enabling them to survive crashes, restarts, and network failures.

Key Features:
- Event Sourcing: All state changes recorded as immutable events
- Durable Execution: Workflows survive process restarts
- Activity Retries: Automatic retry with exponential backoff
- Signals & Queries: External input and state inspection
- Checkpoints: Faster recovery from snapshots
- Child Workflows: Hierarchical workflow composition
- Schedules: Cron and interval-based workflow execution
- Timers: Durable sleep with persistence
- Sagas: Compensating transactions with automatic rollback
- Search Attributes: Custom searchable workflow fields
- Cancellation Scopes: Structured cancellation
- Interceptors: Middleware for cross-cutting concerns

Architecture:
- events.py: Event type definitions (30+ event types)
- event_store.py: Redpanda-based event storage
- replay.py: Event replay engine for recovery
- state_machine.py: Durable workflow base class

Usage:
    from agentic_brain.durability import (
        DurableWorkflow,
        workflow,
        activity,
        EventStore,
    )

    @workflow(name="ai-analysis")
    class AnalysisWorkflow(DurableWorkflow):
        async def run(self, query: str) -> dict:
            result = await self.execute_activity(
                "llm_call",
                args={"prompt": query}
            )
            return {"analysis": result}

    # Run workflow
    wf = AnalysisWorkflow()
    result = await wf.start(args={"query": "Analyze this data"})

    # Resume after crash
    wf2 = AnalysisWorkflow(workflow_id=wf.workflow_id)
    result = await wf2.resume()
"""

from __future__ import annotations

# Activity timeouts
from .activity_timeouts import (
    DEFAULT_TIMEOUTS,
    LLM_TIMEOUTS,
    LONG_TIMEOUTS,
    RAG_TIMEOUTS,
    SHORT_TIMEOUTS,
    ActivityExecution,
    ActivityTimeoutError,
    ActivityTimeouts,
    TimeoutEvent,
    TimeoutMonitor,
    TimeoutType,
    create_timeouts,
)

# Async completion (activities completed by external callbacks)
from .async_completion import (
    ActivityToken,
    AsyncActivityContext,
    AsyncCompletionError,
    AsyncCompletionManager,
    AsyncCompletionStatus,
    TokenAlreadyCompletedError,
    TokenExpiredError,
    TokenInvalidError,
    TokenNotFoundError,
    async_activity,
    get_activity_token,
    get_async_completion_manager,
    get_current_async_context,
)

# Cancellation scopes
from .cancellation import (
    CancellationError,
    CancellationScope,
    CancellationScopeManager,
    CancellationState,
    check_cancelled,
    is_cancelled,
)

# Checkpoints
from .checkpoints import (
    CheckpointConfig,
    CheckpointInfo,
    CheckpointManager,
    get_checkpoint_manager,
)

# Child workflows
from .child_workflows import (
    ChildWorkflowHandle,
    ChildWorkflowManager,
    ChildWorkflowOptions,
    ChildWorkflowPolicy,
    ParentClosePolicy,
    child_workflow,
)

# Continue-as-new
from .continue_as_new import (
    ContinueAsNewError,
    ContinueAsNewManager,
    ContinueAsNewOptions,
    WorkflowRun,
    continue_as_new,
    with_continue_as_new,
)

# Dashboard
from .dashboard import (
    DashboardStats,
    WorkflowDashboard,
    WorkflowFilter,
    WorkflowSummary,
    create_dashboard_routes,
    get_workflow_dashboard,
)

# Event store
from .event_store import (
    EventMetadata,
    EventStore,
    EventStoreConfig,
    EventStoreContext,
    get_event_store,
)

# Event types
from .events import (
    EVENT_TYPE_MAP,
    ActivityCompleted,
    ActivityFailed,
    ActivityHeartbeat,
    ActivityScheduled,
    ActivityStarted,
    BaseEvent,
    CheckpointCreated,
    CheckpointLoaded,
    EventType,
    WorkflowEvent,
    LLMFallbackTriggered,
    LLMRequestCompleted,
    LLMRequestStarted,
    RAGDocumentsRetrieved,
    RAGQueryStarted,
    SignalProcessed,
    SignalReceived,
    TimerFired,
    TimerStarted,
    WorkflowCancelled,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
    WorkflowTimedOut,
)

# Heartbeats
from .heartbeats import (
    HeartbeatContext,
    HeartbeatMonitor,
    heartbeat,
)

# Interceptors
from .interceptors import (
    ActivityInterceptor,
    AuthenticationInterceptor,
    InterceptorChain,
    InterceptorContext,
    LoggingInterceptor,
    MetricsInterceptor,
    RateLimitInterceptor,
    RetryInterceptor,
    TracingInterceptor,
    WorkflowInterceptor,
    default_interceptors,
    production_interceptors,
    with_interceptors,
)

# Local activities
from .local_activities import (
    LocalActivityExecution,
    LocalActivityExecutor,
    LocalActivityOptions,
    hash_data,
    local_activity,
    parse_json,
    validate_email,
)

# Memos (non-indexed workflow metadata)
from .memos import (
    MEMO_KEYS,
    MemoEntry,
    MemoMixin,
    MemoRegistry,
    MemoStore,
    get_memo_registry,
    with_memo,
)

# Namespaces (multi-tenant workflow isolation)
from .namespaces import (
    Namespace,
    NamespaceConfig,
    NamespaceError,
    NamespaceNotFoundError,
    NamespaceQuotaExceededError,
    NamespaceRegistry,
    NamespaceState,
    NamespaceStats,
    NamespaceSuspendedError,
    get_namespace,
    get_namespace_registry,
    namespace_workflow,
)

# Payload converters (custom serialization)
from .payload_converters import (
    ChainedConverter,
    CompressedConverter,
    ConverterRegistry,
    EncryptedConverter,
    JSONConverter,
    MessagePackConverter,
    Payload,
    PayloadConverter,
    PayloadEncoding,
    PickleConverter,
    ProtobufConverter,
    create_efficient_converter,
    create_secure_converter,
    from_payload,
    get_converter,
    get_converter_registry,
    register_converter,
    to_payload,
    with_converter,
)

# Queries
from .queries import (
    METRICS_QUERY,
    PROGRESS_QUERY,
    STATE_QUERY,
    STATUS_QUERY,
    QueryDefinition,
    QueryDispatcher,
    QueryHandler,
    QueryRequest,
    QueryResult,
    QueryStatus,
    extract_query_handlers,
    get_query_dispatcher,
    query_handler,
    query_workflow,
)

# Recovery
from .recovery import (
    RecoveryManager,
    RecoveryResult,
    get_recovery_manager,
)

# Replay engine
from .replay import (
    ReplayEngine,
    ReplayResult,
    WorkflowState,
)
from .retry import (
    AGGRESSIVE_POLICY,
    API_RETRY_POLICY,
    CONSERVATIVE_POLICY,
    DB_RETRY_POLICY,
    DEFAULT_POLICY,
    LLM_RETRY_POLICY,
    with_retry,
)

# Retry policies
from .retry import (
    RetryPolicy as AdvancedRetryPolicy,
)

# Saga pattern
from .saga import (
    Saga,
    SagaExecution,
    SagaExecutor,
    SagaState,
    SagaStep,
    create_compensation,
    saga_step,
)

# Schedules
from .schedules import (
    DAILY_MIDNIGHT,
    EVERY_HOUR,
    EVERY_MINUTE,
    CronExpression,
    ScheduleAction,
    ScheduleDescription,
    ScheduleHandle,
    ScheduleOverlapPolicy,
    ScheduleSpec,
    ScheduleState,
    WorkflowScheduler,
    every_day,
    every_hour,
    every_interval,
    every_minute,
    every_week,
)

# Search attributes
from .search_attributes import (
    SearchAttributeDefinition,
    SearchAttributeIndex,
    SearchAttributeType,
    SearchAttributeValue,
    SearchQuery,
    WorkflowSearchAttributes,
    create_standard_index,
)
from .search_attributes import (
    query as search_query,
)

# Side effects
from .side_effects import (
    SideEffectManager,
    SideEffectResult,
    memoized,
    side_effect,
)

# Signals
from .signals import (
    APPROVAL_SIGNAL,
    CANCEL_SIGNAL,
    PAUSE_SIGNAL,
    RESUME_SIGNAL,
    Signal,
    SignalDefinition,
    SignalDeliveryStatus,
    SignalDispatcher,
    SignalHandler,
    extract_signal_handlers,
    get_signal_dispatcher,
    signal_handler,
)

# State machine
from .state_machine import (
    ActivityOptions,
    DurableWorkflow,
    RetryPolicy,
    WorkflowContext,
    activity,
    query,
    signal,
    workflow,
)

# Task queues
from .task_queue import (
    ACTIVITY_QUEUE,
    LLM_QUEUE,
    RAG_QUEUE,
    WORKFLOW_QUEUE,
    Task,
    TaskPriority,
    TaskQueue,
    TaskQueueManager,
    TaskStatus,
)

# Timers
from .timers import (
    FIVE_MINUTES,
    ONE_DAY,
    ONE_HOUR,
    ONE_MINUTE,
    Timer,
    TimerManager,
    TimerState,
    timer_for,
)

# Updates (synchronous mutations - unlike fire-and-forget signals)
from .updates import (
    ADD_CONTEXT_UPDATE,
    SET_CONFIG_UPDATE,
    SET_PRIORITY_UPDATE,
    SET_RATE_LIMIT_UPDATE,
    SET_TIMEOUT_UPDATE,
    UpdateDefinition,
    UpdateDispatcher,
    UpdateHandler,
    UpdateRequest,
    UpdateResult,
    UpdateStatus,
    UpdateTimeoutError,
    UpdateValidationError,
    extract_update_handlers,
    get_update_dispatcher,
    update_handler,
)

# Versioning
from .versioning import (
    VersionCompatibility,
    WorkflowVersion,
    WorkflowVersionManager,
    get_version_manager,
    migration_handler,
    version_gate,
    workflow_version,
)

# Worker pool
from .worker_pool import (
    ActivityWorker,
    WorkerConfig,
    WorkerPool,
    WorkerStatus,
    get_activities_from_module,
)
from .worker_pool import (
    activity as activity_decorator,
)

__all__ = [
    # Event types
    "EventType",
    "BaseEvent",
    "WorkflowEvent",
    "WorkflowStarted",
    "WorkflowCompleted",
    "WorkflowFailed",
    "WorkflowCancelled",
    "WorkflowTimedOut",
    "ActivityScheduled",
    "ActivityStarted",
    "ActivityCompleted",
    "ActivityFailed",
    "ActivityHeartbeat",
    "SignalReceived",
    "SignalProcessed",
    "TimerStarted",
    "TimerFired",
    "CheckpointCreated",
    "CheckpointLoaded",
    "LLMRequestStarted",
    "LLMRequestCompleted",
    "LLMFallbackTriggered",
    "RAGQueryStarted",
    "RAGDocumentsRetrieved",
    "EVENT_TYPE_MAP",
    # Event store
    "EventStore",
    "EventStoreConfig",
    "EventStoreContext",
    "EventMetadata",
    "get_event_store",
    # Replay
    "ReplayEngine",
    "ReplayResult",
    "WorkflowState",
    # State machine
    "DurableWorkflow",
    "WorkflowContext",
    "RetryPolicy",
    "ActivityOptions",
    "workflow",
    "activity",
    "signal",
    "query",
    # Checkpoints
    "CheckpointManager",
    "CheckpointInfo",
    "CheckpointConfig",
    "get_checkpoint_manager",
    # Recovery
    "RecoveryManager",
    "RecoveryResult",
    "get_recovery_manager",
    # Retry policies
    "AdvancedRetryPolicy",
    "DEFAULT_POLICY",
    "AGGRESSIVE_POLICY",
    "CONSERVATIVE_POLICY",
    "LLM_RETRY_POLICY",
    "DB_RETRY_POLICY",
    "API_RETRY_POLICY",
    "with_retry",
    # Heartbeats
    "HeartbeatMonitor",
    "HeartbeatContext",
    "heartbeat",
    # Task queues
    "TaskQueue",
    "TaskQueueManager",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "WORKFLOW_QUEUE",
    "ACTIVITY_QUEUE",
    "LLM_QUEUE",
    "RAG_QUEUE",
    # Worker pool
    "WorkerPool",
    "ActivityWorker",
    "WorkerConfig",
    "WorkerStatus",
    "activity_decorator",
    "get_activities_from_module",
    # Signals
    "Signal",
    "SignalDefinition",
    "SignalHandler",
    "SignalDispatcher",
    "SignalDeliveryStatus",
    "get_signal_dispatcher",
    "signal_handler",
    "extract_signal_handlers",
    "CANCEL_SIGNAL",
    "PAUSE_SIGNAL",
    "RESUME_SIGNAL",
    "APPROVAL_SIGNAL",
    # Queries
    "QueryRequest",
    "QueryResult",
    "QueryDefinition",
    "QueryHandler",
    "QueryDispatcher",
    "QueryStatus",
    "get_query_dispatcher",
    "query_handler",
    "extract_query_handlers",
    "query_workflow",
    "STATUS_QUERY",
    "PROGRESS_QUERY",
    "STATE_QUERY",
    "METRICS_QUERY",
    # Versioning
    "WorkflowVersion",
    "WorkflowVersionManager",
    "VersionCompatibility",
    "get_version_manager",
    "workflow_version",
    "migration_handler",
    "version_gate",
    # Dashboard
    "WorkflowDashboard",
    "WorkflowSummary",
    "WorkflowFilter",
    "DashboardStats",
    "get_workflow_dashboard",
    "create_dashboard_routes",
    # Child workflows
    "ChildWorkflowHandle",
    "ChildWorkflowOptions",
    "ChildWorkflowManager",
    "ChildWorkflowPolicy",
    "ParentClosePolicy",
    "child_workflow",
    # Continue-as-new
    "ContinueAsNewError",
    "ContinueAsNewOptions",
    "ContinueAsNewManager",
    "WorkflowRun",
    "continue_as_new",
    "with_continue_as_new",
    # Schedules
    "WorkflowScheduler",
    "ScheduleSpec",
    "ScheduleAction",
    "ScheduleDescription",
    "ScheduleHandle",
    "ScheduleOverlapPolicy",
    "ScheduleState",
    "CronExpression",
    "every_minute",
    "every_hour",
    "every_day",
    "every_week",
    "every_interval",
    "EVERY_MINUTE",
    "EVERY_HOUR",
    "DAILY_MIDNIGHT",
    # Timers
    "Timer",
    "TimerManager",
    "TimerState",
    "timer_for",
    "ONE_MINUTE",
    "FIVE_MINUTES",
    "ONE_HOUR",
    "ONE_DAY",
    # Search attributes
    "SearchAttributeIndex",
    "SearchAttributeType",
    "SearchAttributeValue",
    "SearchAttributeDefinition",
    "WorkflowSearchAttributes",
    "SearchQuery",
    "search_query",
    "create_standard_index",
    # Cancellation scopes
    "CancellationScope",
    "CancellationScopeManager",
    "CancellationError",
    "CancellationState",
    "is_cancelled",
    "check_cancelled",
    # Activity timeouts
    "ActivityTimeouts",
    "TimeoutMonitor",
    "TimeoutType",
    "TimeoutEvent",
    "ActivityExecution",
    "ActivityTimeoutError",
    "DEFAULT_TIMEOUTS",
    "SHORT_TIMEOUTS",
    "LONG_TIMEOUTS",
    "LLM_TIMEOUTS",
    "RAG_TIMEOUTS",
    "create_timeouts",
    # Local activities
    "LocalActivityOptions",
    "LocalActivityExecutor",
    "LocalActivityExecution",
    "local_activity",
    "validate_email",
    "parse_json",
    "hash_data",
    # Side effects
    "SideEffectManager",
    "SideEffectResult",
    "side_effect",
    "memoized",
    # Saga pattern
    "Saga",
    "SagaStep",
    "SagaExecutor",
    "SagaExecution",
    "SagaState",
    "saga_step",
    "create_compensation",
    # Interceptors
    "WorkflowInterceptor",
    "ActivityInterceptor",
    "InterceptorChain",
    "InterceptorContext",
    "LoggingInterceptor",
    "MetricsInterceptor",
    "TracingInterceptor",
    "RetryInterceptor",
    "RateLimitInterceptor",
    "AuthenticationInterceptor",
    "with_interceptors",
    "default_interceptors",
    "production_interceptors",
    # Updates (synchronous mutations)
    "UpdateHandler",
    "UpdateDispatcher",
    "UpdateDefinition",
    "UpdateRequest",
    "UpdateResult",
    "UpdateStatus",
    "UpdateValidationError",
    "UpdateTimeoutError",
    "update_handler",
    "get_update_dispatcher",
    "extract_update_handlers",
    "SET_CONFIG_UPDATE",
    "SET_PRIORITY_UPDATE",
    "SET_TIMEOUT_UPDATE",
    "SET_RATE_LIMIT_UPDATE",
    "ADD_CONTEXT_UPDATE",
    # Async completion
    "ActivityToken",
    "AsyncCompletionManager",
    "AsyncActivityContext",
    "AsyncCompletionStatus",
    "AsyncCompletionError",
    "TokenNotFoundError",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenAlreadyCompletedError",
    "async_activity",
    "get_activity_token",
    "get_async_completion_manager",
    "get_current_async_context",
    # Namespaces (multi-tenant isolation)
    "Namespace",
    "NamespaceConfig",
    "NamespaceRegistry",
    "NamespaceState",
    "NamespaceStats",
    "NamespaceError",
    "NamespaceNotFoundError",
    "NamespaceSuspendedError",
    "NamespaceQuotaExceededError",
    "namespace_workflow",
    "get_namespace_registry",
    "get_namespace",
    # Memos (non-indexed metadata)
    "MemoEntry",
    "MemoStore",
    "MemoMixin",
    "MemoRegistry",
    "with_memo",
    "get_memo_registry",
    "MEMO_KEYS",
    # Payload converters
    "Payload",
    "PayloadEncoding",
    "PayloadConverter",
    "JSONConverter",
    "CompressedConverter",
    "EncryptedConverter",
    "ProtobufConverter",
    "MessagePackConverter",
    "PickleConverter",
    "ChainedConverter",
    "ConverterRegistry",
    "with_converter",
    "get_converter_registry",
    "get_converter",
    "register_converter",
    "to_payload",
    "from_payload",
    "create_secure_converter",
    "create_efficient_converter",
]
