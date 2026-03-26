# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
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
JHipster-style Configuration Management

Provides environment-based configuration profiles similar to Spring Boot's
application-{profile}.yml pattern. Supports dev, staging, and prod environments.

Usage:
    from agentic_brain.config import settings

    print(settings.environment)  # "dev", "staging", or "prod"
    print(settings.neo4j.uri)    # Database URI for current environment
"""

from .settings import (
    CacheSettings,
    Environment,
    LLMSettings,
    Neo4jSettings,
    ObservabilitySettings,
    SecuritySettings,
    Settings,
    get_settings,
    settings,
)

__all__ = [
    "Settings",
    "get_settings",
    "settings",
    "Environment",
    "Neo4jSettings",
    "LLMSettings",
    "SecuritySettings",
    "ObservabilitySettings",
    "CacheSettings",
]
