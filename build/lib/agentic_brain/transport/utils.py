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

"""Common transport utilities.

Shared helper functions used across transport modules to avoid duplication.
"""

from datetime import UTC, datetime, timezone


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime.

    Returns:
        datetime: Current time in UTC with timezone info
    """
    return datetime.now(UTC)
