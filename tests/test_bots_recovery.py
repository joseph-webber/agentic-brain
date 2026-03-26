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
Tests for agentic-brain bots recovery module.

Tests RetryConfig, @retry decorator, and RecoveryManager.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agentic_brain.bots import RecoveryManager, RetryConfig, retry


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    @pytest.mark.parametrize(
        "attr,expected",
        [
            ("max_attempts", 3),
            ("initial_delay", 1.0),
            ("max_delay", 60.0),
            ("exponential_base", 2.0),
            ("jitter", True),
        ],
    )
    def test_default_values(self, attr, expected):
        """Test default configuration values."""
        config = RetryConfig()
        assert getattr(config, attr) == expected

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    @pytest.mark.parametrize(
        "field,value,error_msg",
        [
            ("max_attempts", 0, "max_attempts must be at least 1"),
            ("max_attempts", -1, "max_attempts must be at least 1"),
            ("initial_delay", -0.5, "initial_delay must be non-negative"),
            ("exponential_base", 0.5, "exponential_base must be >= 1"),
        ],
    )
    def test_validation_errors(self, field, value, error_msg):
        """Test validation errors for invalid values."""
        with pytest.raises(ValueError, match=error_msg):
            RetryConfig(**{field: value})

    def test_max_delay_less_than_initial_delay_fails(self):
        """Test that max_delay < initial_delay raises error."""
        with pytest.raises(ValueError, match="max_delay must be >= initial_delay"):
            RetryConfig(initial_delay=10.0, max_delay=5.0)

    @pytest.mark.parametrize(
        "attempt,expected_min",
        [
            (0, 1.0),  # 1.0 * 2^0 = 1.0
            (1, 2.0),  # 1.0 * 2^1 = 2.0
            (2, 4.0),  # 1.0 * 2^2 = 4.0
            (3, 8.0),  # 1.0 * 2^3 = 8.0
        ],
    )
    def test_calculate_delay_exponential(self, attempt, expected_min):
        """Test exponential backoff calculation without jitter."""
        config = RetryConfig(jitter=False)
        delay = config.calculate_delay(attempt)
        assert delay == expected_min

    def test_calculate_delay_respects_max(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(initial_delay=1.0, max_delay=5.0, jitter=False)
        delay = config.calculate_delay(10)  # Would be 1024 without cap
        assert delay == 5.0

    def test_calculate_delay_with_jitter(self):
        """Test that jitter adds randomness."""
        config = RetryConfig(jitter=True)
        delays = [config.calculate_delay(0) for _ in range(10)]
        # With jitter, not all delays should be exactly the same
        assert len(set(delays)) > 1


class TestRetryDecorator:
    """Tests for @retry decorator."""

    def test_retry_success_first_try(self):
        """Test function succeeds on first try."""
        call_count = 0

        @retry(config=RetryConfig(max_attempts=3))
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failures(self):
        """Test function succeeds after initial failures."""
        call_count = 0

        @retry(config=RetryConfig(max_attempts=3, initial_delay=0.01))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausts_all_attempts(self):
        """Test that exception is raised after all attempts exhausted."""

        @retry(config=RetryConfig(max_attempts=3, initial_delay=0.01))
        def always_fails():
            raise RuntimeError("Always fails")

        with pytest.raises(RuntimeError, match="Always fails"):
            always_fails()

    def test_retry_specific_exceptions(self):
        """Test retry only on specific exception types."""
        call_count = 0

        @retry(
            config=RetryConfig(max_attempts=3, initial_delay=0.01),
            on_exceptions=(ValueError,),
        )
        def specific_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Wrong type")

        # TypeError should not trigger retry
        with pytest.raises(TypeError, match="Wrong type"):
            specific_error()
        assert call_count == 1

    def test_retry_on_result_condition(self):
        """Test retry when result meets condition."""
        call_count = 0

        @retry(
            config=RetryConfig(max_attempts=3, initial_delay=0.01),
            on_result=lambda x: x < 10,  # Retry while result < 10
        )
        def increasing_result():
            nonlocal call_count
            call_count += 1
            return call_count * 5

        result = increasing_result()
        assert result == 10
        assert call_count == 2  # First: 5, Second: 10

    @pytest.mark.asyncio
    async def test_retry_async_success(self):
        """Test async function retry succeeds."""
        call_count = 0

        @retry(config=RetryConfig(max_attempts=3, initial_delay=0.01))
        async def async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Not ready")
            return "async_success"

        result = await async_func()
        assert result == "async_success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_async_exhausts_attempts(self):
        """Test async function exhausts all retry attempts."""

        @retry(config=RetryConfig(max_attempts=2, initial_delay=0.01))
        async def always_fails_async():
            raise ConnectionError("Cannot connect")

        with pytest.raises(ConnectionError, match="Cannot connect"):
            await always_fails_async()

    def test_retry_no_parentheses(self):
        """Test @retry without parentheses uses defaults."""

        @retry
        def simple_func():
            return "works"

        result = simple_func()
        assert result == "works"


class TestRecoveryManager:
    """Tests for RecoveryManager class."""

    @pytest.fixture
    def recovery(self, tmp_path):
        """Create RecoveryManager with temp directory."""
        with patch.object(Path, "home", return_value=tmp_path):
            return RecoveryManager("test_bot")

    def test_init_creates_checkpoint_dir(self, tmp_path):
        """Test initialization creates checkpoint directory."""
        with patch.object(Path, "home", return_value=tmp_path):
            RecoveryManager("my_bot")
            expected_dir = tmp_path / ".agentic-brain" / "checkpoints" / "my_bot"
            assert expected_dir.exists()

    def test_checkpoint_saves_data(self, recovery):
        """Test checkpoint saves data to file."""
        data = {"items": [1, 2, 3], "status": "in_progress"}
        recovery.checkpoint("step_1", data)

        checkpoint_file = recovery.checkpoint_dir / "step_1.json"
        assert checkpoint_file.exists()

        saved = json.loads(checkpoint_file.read_text())
        assert saved["name"] == "step_1"
        assert saved["data"] == data
        assert "timestamp" in saved

    def test_recover_loads_data(self, recovery):
        """Test recover loads previously saved data."""
        data = {"key": "value", "count": 42}
        recovery.checkpoint("saved_state", data)

        recovered = recovery.recover("saved_state")
        assert recovered == data

    def test_recover_nonexistent_returns_none(self, recovery):
        """Test recover returns None for non-existent checkpoint."""
        result = recovery.recover("does_not_exist")
        assert result is None

    def test_checkpoint_exists_after_save(self, recovery):
        """Test checkpoint exists after saving."""
        recovery.checkpoint("existing", {"data": "here"})
        checkpoints = recovery.list_checkpoints()
        assert "existing" in checkpoints

    def test_checkpoint_not_exists_before_save(self, recovery):
        """Test checkpoint doesn't exist before saving."""
        checkpoints = recovery.list_checkpoints()
        assert "missing" not in checkpoints

    def test_clear_checkpoints_removes_all(self, recovery):
        """Test clear_checkpoints removes all checkpoint files."""
        recovery.checkpoint("to_delete", {"temp": "data"})
        assert "to_delete" in recovery.list_checkpoints()

        recovery.clear_checkpoints()
        assert recovery.list_checkpoints() == {}

    def test_clear_checkpoints_empty_dir_no_error(self, recovery):
        """Test clearing empty checkpoint dir doesn't raise."""
        recovery.clear_checkpoints()  # Should not raise

    def test_attempt_success(self, recovery):
        """Test attempt executes function successfully."""

        def add(a, b):
            return a + b

        result = recovery.attempt(add, 2, 3)
        assert result == 5

    def test_attempt_with_retry(self, recovery):
        """Test attempt retries on failure."""
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "done"

        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        result = recovery.attempt(flaky, config=config)
        assert result == "done"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_attempt_async_success(self, recovery):
        """Test attempt_async executes async function."""

        async def async_add(a, b):
            return a + b

        result = await recovery.attempt_async(async_add, 2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_checkpoint_async(self, recovery):
        """Test async checkpoint saves data."""
        data = {"async_key": "async_value"}
        await recovery.checkpoint_async("async_state", data)

        # Verify it's saved (using sync recover)
        recovered = recovery.recover("async_state")
        assert recovered == data

    @pytest.mark.asyncio
    async def test_recover_async(self, recovery):
        """Test async recover loads data."""
        data = {"for_async": True}
        recovery.checkpoint("for_async_recover", data)

        recovered = await recovery.recover_async("for_async_recover")
        assert recovered == data

    def test_list_checkpoints(self, recovery):
        """Test listing all checkpoints."""
        recovery.checkpoint("first", {"n": 1})
        recovery.checkpoint("second", {"n": 2})
        recovery.checkpoint("third", {"n": 3})

        checkpoints = recovery.list_checkpoints()
        assert len(checkpoints) == 3
        assert "first" in checkpoints
        assert "second" in checkpoints
        assert "third" in checkpoints

    def test_list_checkpoints_empty(self, recovery):
        """Test listing checkpoints when none exist."""
        checkpoints = recovery.list_checkpoints()
        assert checkpoints == {}


class TestRecoveryManagerEdgeCases:
    """Edge case tests for RecoveryManager."""

    @pytest.fixture
    def recovery(self, tmp_path):
        """Create RecoveryManager with temp directory."""
        with patch.object(Path, "home", return_value=tmp_path):
            return RecoveryManager("edge_case_bot")

    def test_checkpoint_overwrites_existing(self, recovery):
        """Test checkpoint overwrites existing checkpoint."""
        recovery.checkpoint("state", {"version": 1})
        recovery.checkpoint("state", {"version": 2})

        recovered = recovery.recover("state")
        assert recovered["version"] == 2

    def test_checkpoint_complex_data(self, recovery):
        """Test checkpoint handles complex nested data."""
        complex_data = {
            "list": [1, 2, [3, 4]],
            "nested": {"a": {"b": {"c": "deep"}}},
            "mixed": [{"key": "value"}, None, True, 123.45],
        }
        recovery.checkpoint("complex", complex_data)

        recovered = recovery.recover("complex")
        assert recovered == complex_data

    def test_checkpoint_special_characters_in_name(self, recovery):
        """Test checkpoint handles special characters safely."""
        # Should sanitize or handle special characters
        recovery.checkpoint("state_v1.0", {"data": "test"})
        assert "state_v1.0" in recovery.list_checkpoints()

    def test_clear_all_checkpoints(self, recovery):
        """Test clearing all checkpoints."""
        recovery.checkpoint("a", {"n": 1})
        recovery.checkpoint("b", {"n": 2})
        recovery.checkpoint("c", {"n": 3})

        recovery.clear_checkpoints()

        assert recovery.list_checkpoints() == {}
