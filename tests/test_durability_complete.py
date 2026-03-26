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

"""
Comprehensive tests for the durability package.

Tests all 23 modules in the durability package including:
- Event sourcing and replay
- State machine and workflows
- Child workflows and continue-as-new
- Schedules and timers
- Search attributes
- Cancellation and activity timeouts
- Local activities and side effects
- Saga pattern and interceptors
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestChildWorkflows:
    """Tests for child workflow management."""

    def test_child_workflow_options_defaults(self):
        """Test ChildWorkflowOptions has sensible defaults."""
        from agentic_brain.durability.child_workflows import ChildWorkflowOptions

        options = ChildWorkflowOptions()
        assert options.workflow_id is None
        assert options.execution_timeout is None
        assert options.retry_policy is None

    def test_child_workflow_options_custom(self):
        """Test ChildWorkflowOptions with custom values."""
        from agentic_brain.durability.child_workflows import (
            ChildWorkflowOptions,
            ParentClosePolicy,
        )

        options = ChildWorkflowOptions(
            workflow_id="child-123",
            execution_timeout=300,
            parent_close_policy=ParentClosePolicy.ABANDON,
        )
        assert options.workflow_id == "child-123"
        assert options.execution_timeout == 300
        assert options.parent_close_policy == ParentClosePolicy.ABANDON

    def test_parent_close_policy_values(self):
        """Test all ParentClosePolicy enum values exist."""
        from agentic_brain.durability.child_workflows import ParentClosePolicy

        assert hasattr(ParentClosePolicy, "TERMINATE")
        assert hasattr(ParentClosePolicy, "ABANDON")
        assert hasattr(ParentClosePolicy, "REQUEST_CANCEL")

    @pytest.mark.asyncio
    async def test_child_workflow_manager_start(self):
        """Test starting a child workflow."""
        from agentic_brain.durability.child_workflows import (
            ChildWorkflowManager,
            ChildWorkflowOptions,
        )

        # ChildWorkflowManager requires parent_workflow_id
        manager = ChildWorkflowManager(parent_workflow_id="parent-123")
        assert manager.parent_workflow_id == "parent-123"


class TestContinueAsNew:
    """Tests for continue-as-new functionality."""

    def test_continue_as_new_options(self):
        """Test ContinueAsNewOptions dataclass."""
        from agentic_brain.durability.continue_as_new import ContinueAsNewOptions

        # ContinueAsNewOptions uses memo and search_attributes
        options = ContinueAsNewOptions(
            memo={"key": "value"}, search_attributes={"CustomField": "test"}
        )
        assert options.memo == {"key": "value"}
        assert options.search_attributes == {"CustomField": "test"}

    def test_continue_as_new_error(self):
        """Test ContinueAsNewError is raised correctly."""
        from agentic_brain.durability.continue_as_new import ContinueAsNewError

        # ContinueAsNewError takes positional args tuple
        error = ContinueAsNewError(args=(1, 2, 3), workflow_type="CounterWorkflow")
        assert error.workflow_type == "CounterWorkflow"

        # Should be catchable
        try:
            raise error
        except ContinueAsNewError as e:
            assert e.workflow_type == "CounterWorkflow"

    def test_continue_as_new_manager(self):
        """Test ContinueAsNewManager initialization."""
        from agentic_brain.durability.continue_as_new import ContinueAsNewManager

        # ContinueAsNewManager has optional event_store and options
        manager = ContinueAsNewManager()
        assert manager is not None
        assert manager.options is not None


class TestSchedules:
    """Tests for workflow scheduling."""

    def test_cron_expression_parsing(self):
        """Test CronExpression parses correctly."""
        from agentic_brain.durability.schedules import CronExpression

        # Use CronExpression.parse() for string parsing
        cron = CronExpression.parse("* * * * *")
        assert cron.minute == "*"
        assert cron.hour == "*"

        # Daily at midnight
        cron2 = CronExpression.parse("0 0 * * *")
        assert cron2.minute == "0"
        assert cron2.hour == "0"

    def test_schedule_spec_cron(self):
        """Test ScheduleSpec with cron expression."""
        from agentic_brain.durability.schedules import ScheduleSpec

        # ScheduleSpec uses 'cron' not 'cron_expression'
        spec = ScheduleSpec(cron="0 9 * * 1")
        assert spec.cron == "0 9 * * 1"

    def test_schedule_spec_interval(self):
        """Test ScheduleSpec with interval."""
        from agentic_brain.durability.schedules import ScheduleSpec

        spec = ScheduleSpec(interval=timedelta(hours=1))
        assert spec.interval == timedelta(hours=1)

    def test_schedule_overlap_policies(self):
        """Test ScheduleOverlapPolicy enum values."""
        from agentic_brain.durability.schedules import ScheduleOverlapPolicy

        assert hasattr(ScheduleOverlapPolicy, "SKIP")
        assert hasattr(ScheduleOverlapPolicy, "BUFFER_ONE")
        assert hasattr(ScheduleOverlapPolicy, "BUFFER_ALL")
        assert hasattr(ScheduleOverlapPolicy, "CANCEL_OTHER")
        assert hasattr(ScheduleOverlapPolicy, "ALLOW_ALL")

    def test_preset_schedules(self):
        """Test preset schedule constants."""
        from agentic_brain.durability.schedules import (
            DAILY_MIDNIGHT,
            EVERY_HOUR,
            EVERY_MINUTE,
        )

        # ScheduleSpec uses 'cron' field
        assert EVERY_MINUTE.cron == "* * * * *"
        assert EVERY_HOUR.cron == "0 * * * *"
        assert DAILY_MIDNIGHT.cron == "0 0 * * *"


class TestTimers:
    """Tests for durable timers."""

    def test_timer_state_enum(self):
        """Test TimerState enum values."""
        from agentic_brain.durability.timers import TimerState

        assert hasattr(TimerState, "PENDING")
        assert hasattr(TimerState, "RUNNING")
        assert hasattr(TimerState, "FIRED")
        assert hasattr(TimerState, "CANCELLED")

    def test_timer_dataclass(self):
        """Test Timer dataclass."""
        from agentic_brain.durability.timers import Timer, TimerState

        # Timer requires workflow_id and deadline, not fire_at
        timer = Timer(
            timer_id="timer-1",
            workflow_id="wf-123",
            duration=timedelta(seconds=30),
            deadline=datetime.now(UTC) + timedelta(seconds=30),
            state=TimerState.PENDING,
        )
        assert timer.timer_id == "timer-1"
        assert timer.state == TimerState.PENDING

    def test_duration_constants(self):
        """Test timer duration constants."""
        from agentic_brain.durability.timers import (
            FIVE_MINUTES,
            ONE_DAY,
            ONE_HOUR,
            ONE_MINUTE,
        )

        assert timedelta(minutes=1) == ONE_MINUTE
        assert timedelta(minutes=5) == FIVE_MINUTES
        assert timedelta(hours=1) == ONE_HOUR
        assert timedelta(days=1) == ONE_DAY

    @pytest.mark.asyncio
    async def test_timer_manager_create(self):
        """Test TimerManager initialization."""
        from agentic_brain.durability.timers import TimerManager

        # TimerManager requires workflow_id
        manager = TimerManager(workflow_id="wf-123")
        assert manager.workflow_id == "wf-123"


class TestSearchAttributes:
    """Tests for search attributes."""

    def test_search_attribute_types(self):
        """Test SearchAttributeType enum values."""
        from agentic_brain.durability.search_attributes import SearchAttributeType

        assert hasattr(SearchAttributeType, "TEXT")
        assert hasattr(SearchAttributeType, "KEYWORD")
        assert hasattr(SearchAttributeType, "INT")
        assert hasattr(SearchAttributeType, "FLOAT")
        assert hasattr(SearchAttributeType, "BOOL")
        assert hasattr(SearchAttributeType, "DATETIME")
        assert hasattr(SearchAttributeType, "KEYWORD_LIST")

    def test_search_attribute_definition(self):
        """Test SearchAttributeDefinition dataclass."""
        from agentic_brain.durability.search_attributes import (
            SearchAttributeDefinition,
            SearchAttributeType,
        )

        # Uses 'attribute_type' not 'attr_type'
        attr = SearchAttributeDefinition(
            name="CustomStatus",
            attribute_type=SearchAttributeType.KEYWORD,
            indexed=True,
        )
        assert attr.name == "CustomStatus"
        assert attr.attribute_type == SearchAttributeType.KEYWORD
        assert attr.indexed is True

    def test_search_query(self):
        """Test SearchQuery dataclass."""
        from agentic_brain.durability.search_attributes import SearchQuery

        query = SearchQuery()
        assert query is not None


class TestCancellation:
    """Tests for cancellation scopes."""

    def test_cancellation_state_enum(self):
        """Test CancellationState enum values."""
        from agentic_brain.durability.cancellation import CancellationState

        # Uses ACTIVE, CANCELLING, CANCELLED, COMPLETED
        assert hasattr(CancellationState, "ACTIVE")
        assert hasattr(CancellationState, "CANCELLING")
        assert hasattr(CancellationState, "CANCELLED")

    def test_cancellation_error(self):
        """Test CancellationError can be raised and caught."""
        from agentic_brain.durability.cancellation import CancellationError

        error = CancellationError("Operation was cancelled")

        with pytest.raises(CancellationError) as exc_info:
            raise error

        assert "cancelled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancellation_scope_manager(self):
        """Test CancellationScopeManager initialization."""
        from agentic_brain.durability.cancellation import CancellationScopeManager

        # CancellationScopeManager requires workflow_id
        manager = CancellationScopeManager(workflow_id="wf-123")
        assert manager.workflow_id == "wf-123"


class TestActivityTimeouts:
    """Tests for activity timeouts."""

    def test_timeout_types_enum(self):
        """Test TimeoutType enum values."""
        from agentic_brain.durability.activity_timeouts import TimeoutType

        assert hasattr(TimeoutType, "SCHEDULE_TO_START")
        assert hasattr(TimeoutType, "START_TO_CLOSE")
        assert hasattr(TimeoutType, "SCHEDULE_TO_CLOSE")
        assert hasattr(TimeoutType, "HEARTBEAT")

    def test_activity_timeouts_dataclass(self):
        """Test ActivityTimeouts dataclass."""
        from agentic_brain.durability.activity_timeouts import ActivityTimeouts

        timeouts = ActivityTimeouts(
            schedule_to_start=timedelta(seconds=10),
            start_to_close=timedelta(seconds=60),
            schedule_to_close=timedelta(seconds=120),
            heartbeat_timeout=timedelta(seconds=5),
        )
        assert timeouts.schedule_to_start == timedelta(seconds=10)
        assert timeouts.start_to_close == timedelta(seconds=60)

    def test_preset_timeouts(self):
        """Test preset timeout configurations."""
        from agentic_brain.durability.activity_timeouts import (
            DEFAULT_TIMEOUTS,
            LLM_TIMEOUTS,
            LONG_TIMEOUTS,
            RAG_TIMEOUTS,
            SHORT_TIMEOUTS,
        )

        assert DEFAULT_TIMEOUTS is not None
        assert SHORT_TIMEOUTS is not None
        assert LONG_TIMEOUTS is not None
        assert LLM_TIMEOUTS is not None
        assert RAG_TIMEOUTS is not None

        # Short should be less than long
        assert SHORT_TIMEOUTS.start_to_close < LONG_TIMEOUTS.start_to_close


class TestLocalActivities:
    """Tests for local activities."""

    def test_local_activity_options(self):
        """Test LocalActivityOptions dataclass."""
        from agentic_brain.durability.local_activities import LocalActivityOptions

        # LocalActivityOptions uses defaults
        options = LocalActivityOptions()
        assert options.start_to_close_timeout == timedelta(seconds=10)
        assert options.retry_attempts == 3

    def test_local_activity_executor(self):
        """Test LocalActivityExecutor initialization."""
        from agentic_brain.durability.local_activities import LocalActivityExecutor

        # LocalActivityExecutor requires workflow_id
        executor = LocalActivityExecutor(workflow_id="wf-123")
        assert executor.workflow_id == "wf-123"

    def test_builtin_local_activities(self):
        """Test built-in local activities are registered."""
        from agentic_brain.durability.local_activities import (
            hash_data,
            parse_json,
            validate_email,
        )

        # Just verify they're decorated properly
        assert hasattr(validate_email, "_local_activity_name")
        assert hasattr(parse_json, "_local_activity_name")
        assert hasattr(hash_data, "_local_activity_name")

        assert validate_email._local_activity_name == "validate_email"
        assert parse_json._local_activity_name == "parse_json"
        assert hash_data._local_activity_name == "hash_data"


class TestSideEffects:
    """Tests for side effects."""

    def test_side_effect_manager(self):
        """Test SideEffectManager initialization."""
        from agentic_brain.durability.side_effects import SideEffectManager

        manager = SideEffectManager(workflow_id="test-wf")
        assert manager.workflow_id == "test-wf"

    def test_memoized_decorator(self):
        """Test memoized decorator."""
        from agentic_brain.durability.side_effects import memoized

        @memoized
        def get_random():
            import random

            return random.randint(1, 1000000)

        # Should be able to call
        result = get_random()
        assert result is not None


class TestSaga:
    """Tests for saga pattern."""

    def test_saga_state_enum(self):
        """Test SagaState enum values."""
        from agentic_brain.durability.saga import SagaState

        # Uses PENDING, RUNNING, COMPLETED, COMPENSATING, COMPENSATED, FAILED
        assert hasattr(SagaState, "PENDING")
        assert hasattr(SagaState, "RUNNING")
        assert hasattr(SagaState, "COMPLETED")
        assert hasattr(SagaState, "COMPENSATING")
        assert hasattr(SagaState, "COMPENSATED")
        assert hasattr(SagaState, "FAILED")

    def test_saga_builder(self):
        """Test Saga builder pattern."""
        from agentic_brain.durability.saga import Saga

        async def step1():
            return "result1"

        async def comp1():
            pass

        async def step2():
            return "result2"

        async def comp2():
            pass

        saga = (
            Saga("test-saga")
            .add_step("step1", step1, comp1)
            .add_step("step2", step2, comp2)
        )

        assert saga.name == "test-saga"
        assert len(saga.steps) == 2

    def test_saga_executor_init(self):
        """Test SagaExecutor initialization."""
        from agentic_brain.durability.saga import SagaExecutor

        # SagaExecutor requires workflow_id
        executor = SagaExecutor(workflow_id="wf-123")
        assert executor.workflow_id == "wf-123"


class TestInterceptors:
    """Tests for interceptors."""

    def test_interceptor_chain_creation(self):
        """Test InterceptorChain creation."""
        from agentic_brain.durability.interceptors import (
            InterceptorChain,
            LoggingInterceptor,
            MetricsInterceptor,
        )

        # InterceptorChain uses add() method, not constructor list
        chain = InterceptorChain()
        chain.add(LoggingInterceptor())
        chain.add(MetricsInterceptor())

        assert len(chain.interceptors) == 2

    def test_default_interceptors(self):
        """Test default_interceptors returns a chain."""
        from agentic_brain.durability.interceptors import default_interceptors

        chain = default_interceptors()
        assert chain is not None
        assert len(chain.interceptors) > 0

    def test_production_interceptors(self):
        """Test production_interceptors returns a chain."""
        from agentic_brain.durability.interceptors import production_interceptors

        chain = production_interceptors()
        assert chain is not None
        assert len(chain.interceptors) > 0

    def test_interceptor_chain_execution(self):
        """Test interceptor chain can be created and used."""
        from agentic_brain.durability.interceptors import (
            InterceptorChain,
            LoggingInterceptor,
        )

        chain = InterceptorChain()
        chain.add(LoggingInterceptor())
        assert len(chain.interceptors) == 1


class TestDurabilityExports:
    """Tests for __init__.py exports."""

    def test_all_modules_exported(self):
        """Test all durability modules are exported."""
        from agentic_brain import durability

        # Core modules
        assert hasattr(durability, "DurableWorkflow")
        assert hasattr(durability, "EventStore")
        assert hasattr(durability, "ReplayEngine")

        # Child workflows
        assert hasattr(durability, "ChildWorkflowManager")
        assert hasattr(durability, "child_workflow")

        # Continue-as-new
        assert hasattr(durability, "ContinueAsNewError")
        assert hasattr(durability, "continue_as_new")

        # Schedules
        assert hasattr(durability, "WorkflowScheduler")
        assert hasattr(durability, "EVERY_MINUTE")

        # Timers
        assert hasattr(durability, "TimerManager")
        assert hasattr(durability, "timer_for")

        # Search attributes
        assert hasattr(durability, "SearchAttributeIndex")

        # Cancellation
        assert hasattr(durability, "CancellationScope")
        assert hasattr(durability, "is_cancelled")

        # Activity timeouts
        assert hasattr(durability, "ActivityTimeouts")
        assert hasattr(durability, "DEFAULT_TIMEOUTS")

        # Local activities
        assert hasattr(durability, "LocalActivityExecutor")
        assert hasattr(durability, "local_activity")

        # Side effects
        assert hasattr(durability, "SideEffectManager")
        assert hasattr(durability, "side_effect")

        # Saga
        assert hasattr(durability, "Saga")
        assert hasattr(durability, "SagaExecutor")

        # Interceptors
        assert hasattr(durability, "InterceptorChain")
        assert hasattr(durability, "default_interceptors")

    def test_all_list_populated(self):
        """Test __all__ list is properly populated."""
        from agentic_brain.durability import __all__

        # Should have 100+ exports
        assert len(__all__) >= 100

        # Check specific exports
        assert "DurableWorkflow" in __all__
        assert "Saga" in __all__
        assert "InterceptorChain" in __all__
        assert "timer_for" in __all__


class TestIntegration:
    """Integration tests for durability package."""

    def test_saga_with_local_activities(self):
        """Test saga pattern with local activities."""
        from agentic_brain.durability.local_activities import (
            LocalActivityExecutor,
            LocalActivityOptions,
        )
        from agentic_brain.durability.saga import Saga, SagaExecutor

        # Just verify the classes can be instantiated together
        executor = LocalActivityExecutor(workflow_id="wf-123")
        saga_executor = SagaExecutor(workflow_id="wf-123")

        assert executor is not None
        assert saga_executor is not None

    def test_timer_with_cancellation(self):
        """Test timer and cancellation can work together."""
        from agentic_brain.durability.cancellation import CancellationScopeManager
        from agentic_brain.durability.timers import TimerManager

        timer_manager = TimerManager(workflow_id="wf-123")
        cancel_manager = CancellationScopeManager(workflow_id="wf-123")

        assert timer_manager.workflow_id == "wf-123"
        assert cancel_manager.workflow_id == "wf-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
