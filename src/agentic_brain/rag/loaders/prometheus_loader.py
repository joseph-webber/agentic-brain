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

"""Prometheus loader for RAG pipelines.

Load metrics, alerts, and recording rules from Prometheus.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class PrometheusLoader(BaseLoader):
    """Load monitoring data from Prometheus.

    Features:
    - Metric queries (PromQL)
    - Alert rules
    - Recording rules
    - Target health status
    - Time series data

    Requirements:
        pip install requests

    Environment variables:
        PROMETHEUS_URL: Prometheus server URL
        PROMETHEUS_USERNAME: Basic auth username (optional)
        PROMETHEUS_PASSWORD: Basic auth password (optional)

    Example:
        loader = PrometheusLoader(
            url="http://prometheus:9090"
        )
        loader.authenticate()
        docs = loader.query_metrics("up")
    """

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ):
        """Initialize Prometheus loader.

        Args:
            url: Prometheus server URL
            username: Basic auth username (optional)
            password: Basic auth password (optional)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required: pip install requests")

        self.url = (url or os.environ.get("PROMETHEUS_URL", "")).rstrip("/")
        self.username = username or os.environ.get("PROMETHEUS_USERNAME")
        self.password = password or os.environ.get("PROMETHEUS_PASSWORD")
        self._session = None

        if not self.url:
            raise ValueError("Prometheus URL required")

    @property
    def source_name(self) -> str:
        return "prometheus"

    def authenticate(self) -> bool:
        """Initialize Prometheus API session."""
        try:
            self._session = requests.Session()

            if self.username and self.password:
                self._session.auth = (self.username, self.password)

            # Test connection
            resp = self._session.get(f"{self.url}/api/v1/status/config")
            resp.raise_for_status()

            logger.info("Prometheus authentication successful")
            return True
        except Exception as e:
            logger.error(f"Prometheus authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Prometheus")

    @with_rate_limit(requests_per_minute=60)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single metric or alert.

        Args:
            doc_id: PromQL query or alert name
        """
        self._ensure_authenticated()

        # Check if it's an alert name
        if doc_id.startswith("alert:"):
            alert_name = doc_id[6:]
            return self._load_alert(alert_name)
        else:
            # Treat as PromQL query
            return self._query_metric(doc_id)

    def _query_metric(self, query: str) -> Optional[LoadedDocument]:
        """Execute PromQL query."""
        try:
            resp = self._session.get(
                f"{self.url}/api/v1/query", params={"query": query}
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "success":
                logger.error(f"Query failed: {data.get('error', 'Unknown error')}")
                return None

            result = data.get("data", {}).get("result", [])
            content = self._format_query_result(query, result)

            return LoadedDocument(
                id=f"prometheus://query/{hash(query)}",
                content=content,
                metadata={
                    "source": "prometheus",
                    "query": query,
                    "result_count": len(result),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                source="prometheus",
            )
        except Exception as e:
            logger.error(f"Failed to query Prometheus: {e}")
            return None

    def _load_alert(self, alert_name: str) -> Optional[LoadedDocument]:
        """Load alert rule by name."""
        try:
            resp = self._session.get(f"{self.url}/api/v1/rules")
            resp.raise_for_status()
            data = resp.json()

            # Find alert in rules
            for group in data.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if (
                        rule.get("name") == alert_name
                        and rule.get("type") == "alerting"
                    ):
                        content = self._format_alert_rule(rule)

                        return LoadedDocument(
                            id=f"prometheus://alert/{alert_name}",
                            content=content,
                            metadata={
                                "source": "prometheus",
                                "alert_name": alert_name,
                                "state": rule.get("state", "unknown"),
                                "severity": rule.get("labels", {}).get("severity", ""),
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            source="prometheus",
                        )

            logger.warning(f"Alert not found: {alert_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to load alert {alert_name}: {e}")
            return None

    def load_folder(self, folder_path: str = "alerts") -> List[LoadedDocument]:
        """Load Prometheus resources.

        Args:
            folder_path: Resource type (alerts, targets, rules)
        """
        if folder_path == "alerts":
            return self.load_alerts()
        elif folder_path == "targets":
            return self.load_targets()
        elif folder_path == "rules":
            return self.load_rules()
        else:
            logger.warning(f"Unknown folder type: {folder_path}")
            return []

    def load_alerts(self) -> List[LoadedDocument]:
        """Load all alert rules."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(f"{self.url}/api/v1/rules")
            resp.raise_for_status()
            data = resp.json()

            for group in data.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule.get("type") == "alerting":
                        content = self._format_alert_rule(rule)

                        docs.append(
                            LoadedDocument(
                                id=f"prometheus://alert/{rule.get('name', 'unknown')}",
                                content=content,
                                metadata={
                                    "source": "prometheus",
                                    "alert_name": rule.get("name", ""),
                                    "state": rule.get("state", "unknown"),
                                    "group": group.get("name", ""),
                                    "timestamp": datetime.utcnow().isoformat(),
                                },
                                source="prometheus",
                            )
                        )

            logger.info(f"Found {len(docs)} Prometheus alerts")

        except Exception as e:
            logger.error(f"Failed to load Prometheus alerts: {e}")

        return docs

    def load_rules(self) -> List[LoadedDocument]:
        """Load all recording rules."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(f"{self.url}/api/v1/rules")
            resp.raise_for_status()
            data = resp.json()

            for group in data.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule.get("type") == "recording":
                        content = self._format_recording_rule(rule)

                        docs.append(
                            LoadedDocument(
                                id=f"prometheus://rule/{rule.get('name', 'unknown')}",
                                content=content,
                                metadata={
                                    "source": "prometheus",
                                    "rule_name": rule.get("name", ""),
                                    "group": group.get("name", ""),
                                    "timestamp": datetime.utcnow().isoformat(),
                                },
                                source="prometheus",
                            )
                        )

            logger.info(f"Found {len(docs)} Prometheus recording rules")

        except Exception as e:
            logger.error(f"Failed to load Prometheus rules: {e}")

        return docs

    def load_targets(self) -> List[LoadedDocument]:
        """Load scrape targets and their health."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(f"{self.url}/api/v1/targets")
            resp.raise_for_status()
            data = resp.json()

            for target in data.get("data", {}).get("activeTargets", []):
                content = self._format_target(target)

                docs.append(
                    LoadedDocument(
                        id=f"prometheus://target/{target.get('scrapeUrl', 'unknown')}",
                        content=content,
                        metadata={
                            "source": "prometheus",
                            "job": target.get("labels", {}).get("job", ""),
                            "instance": target.get("labels", {}).get("instance", ""),
                            "health": target.get("health", "unknown"),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        source="prometheus",
                    )
                )

            logger.info(f"Found {len(docs)} Prometheus targets")

        except Exception as e:
            logger.error(f"Failed to load Prometheus targets: {e}")

        return docs

    def query_metrics(
        self,
        query: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step: str = "15s",
    ) -> List[LoadedDocument]:
        """Query metrics over time range.

        Args:
            query: PromQL query
            start: Start time (default: 1 hour ago)
            end: End time (default: now)
            step: Query resolution (default: 15s)
        """
        if not end:
            end = datetime.utcnow()
        if not start:
            start = end - timedelta(hours=1)

        self._ensure_authenticated()

        try:
            resp = self._session.get(
                f"{self.url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": step,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "success":
                logger.error(f"Query failed: {data.get('error', 'Unknown')}")
                return []

            result = data.get("data", {}).get("result", [])
            content = self._format_range_query_result(query, result, start, end)

            return [
                LoadedDocument(
                    id=f"prometheus://query_range/{hash(query)}",
                    content=content,
                    metadata={
                        "source": "prometheus",
                        "query": query,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "result_count": len(result),
                    },
                    source="prometheus",
                )
            ]

        except Exception as e:
            logger.error(f"Failed to query Prometheus range: {e}")
            return []

    def _format_query_result(self, query: str, result: list) -> str:
        """Format instant query result."""
        content_parts = [
            f"# Prometheus Query: {query}",
            "",
            f"## Results ({len(result)} series)",
            "",
        ]

        for series in result[:50]:  # Limit to 50
            metric = series.get("metric", {})
            value = series.get("value", [None, "N/A"])

            metric_str = ", ".join(f"{k}={v}" for k, v in metric.items())
            content_parts.append(f"- **{metric_str}**: {value[1]}")

        if len(result) > 50:
            content_parts.append(f"- ... and {len(result) - 50} more")

        return "\n".join(content_parts)

    def _format_range_query_result(
        self, query: str, result: list, start: datetime, end: datetime
    ) -> str:
        """Format range query result."""
        content_parts = [
            f"# Prometheus Range Query: {query}",
            "",
            f"- **Period**: {start.isoformat()} to {end.isoformat()}",
            f"- **Series**: {len(result)}",
            "",
        ]

        for series in result[:10]:  # Limit to 10 series
            metric = series.get("metric", {})
            values = series.get("values", [])

            metric_str = ", ".join(f"{k}={v}" for k, v in metric.items())
            content_parts.append(f"## Series: {metric_str}")
            content_parts.append(f"- **Data points**: {len(values)}")

            if values:
                first_val = values[0][1]
                last_val = values[-1][1]
                content_parts.append(f"- **First value**: {first_val}")
                content_parts.append(f"- **Last value**: {last_val}")
            content_parts.append("")

        return "\n".join(content_parts)

    def _format_alert_rule(self, rule: dict) -> str:
        """Format alert rule."""
        content_parts = [
            f"# Alert: {rule.get('name', 'Unknown')}",
            "",
            "## Configuration",
            f"- **State**: {rule.get('state', 'unknown')}",
            f"- **Duration**: {rule.get('duration', 0)}s",
            "",
            "## Query",
            "```promql",
            f"{rule.get('query', 'No query')}",
            "```",
            "",
        ]

        # Add labels
        labels = rule.get("labels", {})
        if labels:
            content_parts.append("## Labels")
            for key, value in labels.items():
                content_parts.append(f"- **{key}**: {value}")
            content_parts.append("")

        # Add annotations
        annotations = rule.get("annotations", {})
        if annotations:
            content_parts.append("## Annotations")
            for key, value in annotations.items():
                content_parts.append(f"- **{key}**: {value}")

        return "\n".join(content_parts)

    def _format_recording_rule(self, rule: dict) -> str:
        """Format recording rule."""
        return f"""# Recording Rule: {rule.get('name', 'Unknown')}

## Query
```promql
{rule.get('query', 'No query')}
```

## Labels
{json.dumps(rule.get('labels', {}), indent=2)}
"""

    def _format_target(self, target: dict) -> str:
        """Format scrape target."""
        labels = target.get("labels", {})

        return f"""# Prometheus Target: {target.get('scrapeUrl', 'Unknown')}

## Status
- **Health**: {target.get('health', 'unknown')}
- **Last Scrape**: {target.get('lastScrape', 'Unknown')}
- **Scrape Duration**: {target.get('lastScrapeDuration', 0)}s

## Labels
{json.dumps(labels, indent=2)}

## Error
{target.get('lastError', 'None')}
"""
