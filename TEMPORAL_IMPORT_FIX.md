# Temporal Import Error Fix Summary

## Problem
Files importing `temporalio` library were causing ImportError when temporalio was not installed, even though it's an optional dependency.

## Solution
Made ALL temporal imports lazy/optional with try/except blocks and appropriate stubs.

## Files Fixed

### 1. src/agentic_brain/workflows/temporal/activities.py
- Wrapped `from temporalio import activity` in try/except
- Created `_ActivityStub` with defn decorator, logger, and heartbeat
- Added `TEMPORALIO_AVAILABLE` flag

### 2. src/agentic_brain/workflows/temporal/worker.py
- Wrapped `from temporalio.client import Client` and `from temporalio.worker import Worker` in try/except
- Added runtime check in `start()` method to raise helpful error if temporalio not available
- Added `TEMPORALIO_AVAILABLE` flag

### 3. src/agentic_brain/workflows/temporal/workflows.py
- Wrapped `from temporalio import workflow` and `from temporalio.common import RetryPolicy` in try/except
- Created `_WorkflowStub` with defn, run, signal, and query decorators
- Added `TEMPORALIO_AVAILABLE` flag

### 4. src/agentic_brain/workflows/temporal/patterns.py
- Wrapped `from temporalio import workflow` and `from temporalio.common import RetryPolicy` in try/except
- Created `_WorkflowStub` with defn, run, signal, and query decorators
- Added `TEMPORALIO_AVAILABLE` flag

## Already Protected (No Changes Needed)
- `src/agentic_brain/workflows/temporal/client.py` - Already had try/except
- `src/agentic_brain/cli/temporal_commands.py` - Already had lazy imports
- `src/agentic_brain/integrations/temporal.py` - Already had lazy imports

## Test Results
All modules now import successfully without temporalio installed:
```
✅ agentic_brain.workflows.temporal
✅ agentic_brain.workflows.temporal.activities
✅ agentic_brain.workflows.temporal.workflows
✅ agentic_brain.workflows.temporal.patterns
✅ agentic_brain.workflows.temporal.worker
✅ agentic_brain.workflows.temporal.client
✅ agentic_brain.cli.temporal_commands
✅ agentic_brain.integrations.temporal
```

## Pattern Used

```python
# Optional dependency - graceful fallback if not installed
try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy
    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    # Create stub for workflow decorators
    class _WorkflowStub:
        @staticmethod
        def defn(cls):
            return cls
        @staticmethod
        def run(fn):
            return fn
        @staticmethod
        def signal(name=None):
            def decorator(fn):
                return fn
            return decorator
    workflow = _WorkflowStub()
    RetryPolicy = None  # type: ignore
```

## Benefits
- ✅ No import errors when temporalio not installed
- ✅ Code remains readable and maintainable
- ✅ Helpful error messages when trying to use temporal features without installation
- ✅ Stubs preserve decorator syntax for type checking

## Date
2026-03-22 (ACDT)
