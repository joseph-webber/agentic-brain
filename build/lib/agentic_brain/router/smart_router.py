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

from __future__ import annotations

# SPDX-License-Identifier: GPL-3.0-or-later
"""
Smart routing wrapper for LLM workers.

This module re-exports the smart_router package from agentic_brain.smart_router
so callers can import from agentic_brain.router.smart_router.
"""

from agentic_brain.smart_router import (
    SmartRouter,
    SmashMode,
    SmashResult,
    SecurityPosture,
    PostureMode,
    ludicrous_smash,
    cascade_smash,
)

__all__ = [
    "SmartRouter",
    "SmashMode",
    "SmashResult",
    "SecurityPosture",
    "PostureMode",
    "ludicrous_smash",
    "cascade_smash",
]
