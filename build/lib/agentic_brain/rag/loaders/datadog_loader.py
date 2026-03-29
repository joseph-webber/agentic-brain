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

"""Datadog loader for RAG pipelines.

Load metrics, logs, monitors, and dashboards from Datadog.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, List, Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

try:
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v1.api.logs_api import LogsApi
    from datadog_api_client.v1.api.metrics_api import MetricsApi
    from datadog_api_client.v1.api.monitors_api import MonitorsApi
    from datadog_api_client.v2.api.logs_api import LogsApi as LogsApiV2

    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False


class DatadogLoader(BaseLoader):
    """Load monitoring data from Datadog.

    Features:
    - Metrics queries
    - Log searches
    - Monitor configurations
    - Dashboard definitions
    - Incidents and events

    Requirements:
        pip install datadog-api-client

    Environment variables:
        DD_API_KEY: Datadog API key
        DD_APP_KEY: Datadog application key
        DD_SITE: Datadog site (default: datadoghq.com)

    Example:
        loader = DatadogLoader(
            api_key="xxx",
            app_key="yyy"
        )
        loader.authenticate()
        docs = loader.load_monitors()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        app_key: Optional[str] = None,
        site: str = "datadoghq.com",
        **kwargs,
    ):
        """Initialize Datadog loader.

        Args:
            api_key: Datadog API key
            app_key: Datadog application key
            site: Datadog site (datadoghq.com, datadoghq.eu, etc.)
        """
        if not DATADOG_AVAILABLE:
            raise ImportError(
                "datadog-api-client required: pip install datadog-api-client"
            )

        self.api_key = api_key or os.environ.get("DD_API_KEY")
        self.app_key = app_key or os.environ.get("DD_APP_KEY")
        self.site = site or os.environ.get("DD_SITE", "datadoghq.com")
        self._config = None

        if not self.api_key or not self.app_key:
            raise ValueError("Datadog API key and app key required")

    @property
    def source_name(self) -> str:
        return "datadog"

    def authenticate(self) -> bool:
        """Initialize Datadog API client."""
        try:
            self._config = Configuration()
            self._config.api_key["apiKeyAuth"] = self.api_key
            self._config.api_key["appKeyAuth"] = self.app_key
            self._config.server_variables["site"] = self.site

            # Test connection by listing monitors
            with ApiClient(self._config) as api_client:
                api = MonitorsApi(api_client)
                api.list_monitors(page_size=1)

            logger.info("Datadog authentication successful")
            return True
        except Exception as e:
            logger.error(f"Datadog authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._config and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Datadog")

    @with_rate_limit(requests_per_minute=300)  # Datadog has high limits
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Datadog monitor.

        Args:
            doc_id: Monitor ID
        """
        self._ensure_authenticated()
        try:
            with ApiClient(self._config) as api_client:
                api = MonitorsApi(api_client)
                monitor = api.get_monitor(int(doc_id))

            content = self._format_monitor(monitor)

            return LoadedDocument(
                id=f"datadog://monitor/{doc_id}",
                content=content,
                metadata={
                    "source": "datadog",
                    "monitor_id": doc_id,
                    "type": monitor.get("type", "unknown"),
                    "name": monitor.get("name", ""),
                    "priority": monitor.get("priority", 0),
                    "tags": monitor.get("tags", []),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                source="datadog",
            )
        except Exception as e:
            logger.error(f"Failed to load Datadog monitor {doc_id}: {e}")
            return None

    def load_folder(self, folder_path: str = "monitors") -> List[LoadedDocument]:
        """Load Datadog resources.

        Args:
            folder_path: Resource type (monitors, logs, metrics)
        """
        if folder_path == "monitors":
            return self.load_monitors()
        elif folder_path == "logs":
            return self.load_logs()
        else:
            logger.warning(f"Unknown folder type: {folder_path}")
            return []

    def load_monitors(self, tags: Optional[List[str]] = None) -> List[LoadedDocument]:
        """Load all monitors.

        Args:
            tags: Filter by tags (e.g., ["env:prod", "service:api"])
        """
        self._ensure_authenticated()
        docs = []

        try:
            with ApiClient(self._config) as api_client:
                api = MonitorsApi(api_client)
                monitors = api.list_monitors(tags=",".join(tags) if tags else None)

            logger.info(f"Found {len(monitors)} Datadog monitors")

            for monitor in monitors:
                monitor_id = str(monitor.get("id", ""))
                if monitor_id:
                    doc = self.load_document(monitor_id)
                    if doc:
                        docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load Datadog monitors: {e}")

        return docs

    def load_logs(
        self, query: str = "status:error", hours: int = 24, limit: int = 100
    ) -> List[LoadedDocument]:
        """Load recent logs.

        Args:
            query: Log search query
            hours: Hours to look back
            limit: Max logs to return
        """
        self._ensure_authenticated()
        docs = []

        try:
            with ApiClient(self._config) as api_client:
                api = LogsApiV2(api_client)

                from_time = datetime.utcnow() - timedelta(hours=hours)
                to_time = datetime.utcnow()

                from datadog_api_client.v2.model.logs_list_request import (
                    LogsListRequest,
                )
                from datadog_api_client.v2.model.logs_query_filter import (
                    LogsQueryFilter,
                )

                body = LogsListRequest(
                    filter=LogsQueryFilter(
                        query=query,
                        from_=from_time.isoformat() + "Z",
                        to=to_time.isoformat() + "Z",
                    ),
                    page={"limit": min(limit, 1000)},
                )

                response = api.list_logs(body=body)
                logs = response.get("data", [])

            logger.info(f"Found {len(logs)} Datadog logs")

            for idx, log in enumerate(logs[:limit]):
                attributes = log.get("attributes", {})
                content = self._format_log(attributes)

                docs.append(
                    LoadedDocument(
                        id=f"datadog://log/{idx}",
                        content=content,
                        metadata={
                            "source": "datadog",
                            "status": attributes.get("status", ""),
                            "service": attributes.get("service", ""),
                            "host": attributes.get("host", ""),
                            "timestamp": attributes.get("timestamp", ""),
                        },
                        source="datadog",
                    )
                )

        except Exception as e:
            logger.error(f"Failed to load Datadog logs: {e}")

        return docs

    def _format_monitor(self, monitor: dict) -> str:
        """Format monitor data as text."""
        content_parts = [
            f"# Datadog Monitor: {monitor.get('name', 'Unknown')}",
            "",
            "## Configuration",
            f"- **ID**: {monitor.get('id', 'Unknown')}",
            f"- **Type**: {monitor.get('type', 'unknown')}",
            f"- **Priority**: {monitor.get('priority', 0)}",
            f"- **Status**: {monitor.get('overall_state', 'unknown')}",
            "",
            "## Query",
            "```",
            f"{monitor.get('query', 'No query')}",
            "```",
            "",
            "## Message",
            f"{monitor.get('message', 'No message')}",
            "",
        ]

        # Add tags
        tags = monitor.get("tags", [])
        if tags:
            content_parts.append("## Tags")
            for tag in tags:
                content_parts.append(f"- {tag}")
            content_parts.append("")

        # Add thresholds
        options = monitor.get("options", {})
        thresholds = options.get("thresholds", {})
        if thresholds:
            content_parts.append("## Thresholds")
            for key, value in thresholds.items():
                content_parts.append(f"- **{key}**: {value}")

        return "\n".join(content_parts)

    def _format_log(self, attributes: dict) -> str:
        """Format log entry as text."""
        timestamp = attributes.get("timestamp", "Unknown")
        status = attributes.get("status", "info")
        service = attributes.get("service", "unknown")
        message = attributes.get("message", "No message")

        content_parts = [
            f"# Datadog Log: {timestamp}",
            "",
            f"- **Status**: {status}",
            f"- **Service**: {service}",
            f"- **Host**: {attributes.get('host', 'unknown')}",
            "",
            "## Message",
            "```",
            f"{message}",
            "```",
        ]

        # Add custom attributes
        custom = attributes.get("attributes", {})
        if custom:
            content_parts.append("")
            content_parts.append("## Attributes")
            for key, value in list(custom.items())[:20]:  # Limit to 20
                content_parts.append(f"- **{key}**: {value}")

        return "\n".join(content_parts)
