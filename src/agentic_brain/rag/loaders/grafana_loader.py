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

"""Grafana loader for RAG pipelines.

Load dashboards, panels, alerts, and data sources from Grafana.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, List, Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class GrafanaLoader(BaseLoader):
    """Load dashboards and alerts from Grafana.

    Features:
    - Dashboard definitions
    - Panel configurations
    - Alert rules
    - Data source configs
    - Annotations
    - Snapshot data

    Requirements:
        pip install requests

    Environment variables:
        GRAFANA_URL: Grafana server URL
        GRAFANA_API_KEY: Grafana API key or service account token
        GRAFANA_USERNAME: Basic auth username (alternative)
        GRAFANA_PASSWORD: Basic auth password (alternative)

    Example:
        loader = GrafanaLoader(
            url="https://grafana.company.com",
            api_key="xxx"
        )
        loader.authenticate()
        docs = loader.load_dashboards()
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ):
        """Initialize Grafana loader.

        Args:
            url: Grafana server URL
            api_key: Grafana API key (preferred)
            username: Basic auth username (alternative)
            password: Basic auth password (alternative)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required: pip install requests")

        self.url = (url or os.environ.get("GRAFANA_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("GRAFANA_API_KEY")
        self.username = username or os.environ.get("GRAFANA_USERNAME")
        self.password = password or os.environ.get("GRAFANA_PASSWORD")
        self._session = None

        if not self.url:
            raise ValueError("Grafana URL required")

        if not self.api_key and not (self.username and self.password):
            raise ValueError("Either API key or username/password required")

    @property
    def source_name(self) -> str:
        return "grafana"

    def authenticate(self) -> bool:
        """Initialize Grafana API session."""
        try:
            self._session = requests.Session()

            if self.api_key:
                # Use API key auth
                self._session.headers.update(
                    {"Authorization": f"Bearer {self.api_key}"}
                )
            else:
                # Use basic auth
                self._session.auth = (self.username, self.password)

            self._session.headers["Content-Type"] = "application/json"

            # Test connection
            resp = self._session.get(f"{self.url}/api/org")
            resp.raise_for_status()

            logger.info("Grafana authentication successful")
            return True
        except Exception as e:
            logger.error(f"Grafana authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Grafana")

    @with_rate_limit(requests_per_minute=60)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single dashboard by UID.

        Args:
            doc_id: Dashboard UID
        """
        self._ensure_authenticated()
        try:
            resp = self._session.get(f"{self.url}/api/dashboards/uid/{doc_id}")
            resp.raise_for_status()
            data = resp.json()

            dashboard = data.get("dashboard", {})
            meta = data.get("meta", {})

            content = self._format_dashboard(dashboard, meta)

            return LoadedDocument(
                id=f"grafana://dashboard/{doc_id}",
                content=content,
                metadata={
                    "source": "grafana",
                    "dashboard_uid": doc_id,
                    "title": dashboard.get("title", ""),
                    "folder": meta.get("folderTitle", ""),
                    "tags": dashboard.get("tags", []),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                source="grafana",
            )
        except Exception as e:
            logger.error(f"Failed to load Grafana dashboard {doc_id}: {e}")
            return None

    def load_folder(self, folder_path: str = "dashboards") -> List[LoadedDocument]:
        """Load Grafana resources.

        Args:
            folder_path: Resource type (dashboards, alerts, datasources)
        """
        if folder_path == "dashboards":
            return self.load_dashboards()
        elif folder_path == "alerts":
            return self.load_alerts()
        elif folder_path == "datasources":
            return self.load_datasources()
        else:
            logger.warning(f"Unknown folder type: {folder_path}")
            return []

    def load_dashboards(
        self, folder_id: Optional[int] = None, tags: Optional[List[str]] = None
    ) -> List[LoadedDocument]:
        """Load all dashboards.

        Args:
            folder_id: Filter by folder ID (None = all folders)
            tags: Filter by tags
        """
        self._ensure_authenticated()
        docs = []

        try:
            params = {"type": "dash-db"}
            if folder_id:
                params["folderIds"] = folder_id
            if tags:
                params["tag"] = tags

            resp = self._session.get(f"{self.url}/api/search", params=params)
            resp.raise_for_status()
            dashboards = resp.json()

            logger.info(f"Found {len(dashboards)} Grafana dashboards")

            for dashboard in dashboards:
                uid = dashboard.get("uid")
                if uid:
                    doc = self.load_document(uid)
                    if doc:
                        docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load Grafana dashboards: {e}")

        return docs

    def load_alerts(self) -> List[LoadedDocument]:
        """Load all alert rules."""
        self._ensure_authenticated()
        docs = []

        try:
            # Get all alert rules (Grafana 9+)
            resp = self._session.get(f"{self.url}/api/ruler/grafana/api/v1/rules")
            resp.raise_for_status()
            data = resp.json()

            for folder_name, groups in data.items():
                for group in groups:
                    for rule in group.get("rules", []):
                        content = self._format_alert_rule(
                            rule, folder_name, group.get("name")
                        )

                        docs.append(
                            LoadedDocument(
                                id=f"grafana://alert/{rule.get('uid', 'unknown')}",
                                content=content,
                                metadata={
                                    "source": "grafana",
                                    "alert_name": rule.get("title", ""),
                                    "folder": folder_name,
                                    "group": group.get("name", ""),
                                    "state": rule.get("state", ""),
                                    "timestamp": datetime.utcnow().isoformat(),
                                },
                                source="grafana",
                            )
                        )

            logger.info(f"Found {len(docs)} Grafana alert rules")

        except Exception as e:
            logger.error(f"Failed to load Grafana alerts: {e}")

        return docs

    def load_datasources(self) -> List[LoadedDocument]:
        """Load all data source configurations."""
        self._ensure_authenticated()
        docs = []

        try:
            resp = self._session.get(f"{self.url}/api/datasources")
            resp.raise_for_status()
            datasources = resp.json()

            logger.info(f"Found {len(datasources)} Grafana data sources")

            for ds in datasources:
                content = self._format_datasource(ds)

                docs.append(
                    LoadedDocument(
                        id=f"grafana://datasource/{ds.get('uid', 'unknown')}",
                        content=content,
                        metadata={
                            "source": "grafana",
                            "datasource_name": ds.get("name", ""),
                            "type": ds.get("type", ""),
                            "uid": ds.get("uid", ""),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        source="grafana",
                    )
                )

        except Exception as e:
            logger.error(f"Failed to load Grafana data sources: {e}")

        return docs

    def _format_dashboard(self, dashboard: dict, meta: dict) -> str:
        """Format dashboard as text."""
        content_parts = [
            f"# Grafana Dashboard: {dashboard.get('title', 'Unknown')}",
            "",
            "## Overview",
            f"- **UID**: {dashboard.get('uid', 'Unknown')}",
            f"- **Folder**: {meta.get('folderTitle', 'General')}",
            f"- **Created**: {meta.get('created', 'Unknown')}",
            f"- **Updated**: {meta.get('updated', 'Unknown')}",
            f"- **Version**: {dashboard.get('version', 0)}",
            "",
        ]

        # Add tags
        tags = dashboard.get("tags", [])
        if tags:
            content_parts.append("## Tags")
            content_parts.append(", ".join(tags))
            content_parts.append("")

        # Add panels
        panels = dashboard.get("panels", [])
        if panels:
            content_parts.append(f"## Panels ({len(panels)})")
            for panel in panels:
                title = panel.get("title", "Untitled")
                panel_type = panel.get("type", "unknown")
                content_parts.append(f"- **{title}** ({panel_type})")

                # Add queries if present
                targets = panel.get("targets", [])
                if targets:
                    for target in targets[:3]:  # Limit to 3
                        expr = target.get("expr") or target.get("query", "")
                        if expr:
                            content_parts.append(f"  - Query: `{expr[:100]}`")
            content_parts.append("")

        # Add variables
        templating = dashboard.get("templating", {})
        variables = templating.get("list", [])
        if variables:
            content_parts.append("## Variables")
            for var in variables:
                name = var.get("name", "?")
                var_type = var.get("type", "?")
                content_parts.append(f"- **${name}**: {var_type}")

        return "\n".join(content_parts)

    def _format_alert_rule(self, rule: dict, folder: str, group: str) -> str:
        """Format alert rule as text."""
        content_parts = [
            f"# Grafana Alert: {rule.get('title', 'Unknown')}",
            "",
            "## Configuration",
            f"- **UID**: {rule.get('uid', 'Unknown')}",
            f"- **Folder**: {folder}",
            f"- **Group**: {group}",
            f"- **State**: {rule.get('state', 'unknown')}",
            f"- **For**: {rule.get('for', '0s')}",
            "",
        ]

        # Add condition
        condition = rule.get("condition", "")
        if condition:
            content_parts.append("## Condition")
            content_parts.append("```")
            content_parts.append(condition)
            content_parts.append("```")
            content_parts.append("")

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

    def _format_datasource(self, ds: dict) -> str:
        """Format data source as text."""
        return f"""# Grafana Data Source: {ds.get('name', 'Unknown')}

## Configuration
- **Type**: {ds.get('type', 'unknown')}
- **UID**: {ds.get('uid', 'Unknown')}
- **URL**: {ds.get('url', 'Not configured')}
- **Access**: {ds.get('access', 'unknown')}
- **Default**: {ds.get('isDefault', False)}

## Database
{ds.get('database', 'Not specified')}

## Version
{ds.get('version', 'Unknown')}
"""
