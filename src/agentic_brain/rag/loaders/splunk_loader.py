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

"""Splunk loader for RAG pipelines.

Load searches, dashboards, and data from Splunk Enterprise/Cloud.
"""

import logging
import os
from datetime import datetime
from typing import List, Optional
from xml.etree import ElementTree as ET

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class SplunkLoader(BaseLoader):
    """Load data from Splunk Enterprise or Splunk Cloud.

    Features:
    - Run saved searches
    - Execute SPL queries
    - Load dashboards
    - Export search results
    - Access knowledge objects

    Requirements:
        pip install requests

    Environment variables:
        SPLUNK_HOST: Splunk server URL
        SPLUNK_PORT: Splunk port (default: 8089)
        SPLUNK_USERNAME: Splunk username
        SPLUNK_PASSWORD: Splunk password
        SPLUNK_TOKEN: Splunk auth token (alternative to username/password)

    Example:
        loader = SplunkLoader(
            host="splunk.company.com",
            username="admin",
            password="xxx"
        )
        loader.authenticate()
        docs = loader.run_search("index=main error")
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 8089,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        scheme: str = "https",
        verify_ssl: bool = True,
        **kwargs,
    ):
        """Initialize Splunk loader.

        Args:
            host: Splunk server hostname
            port: Splunk management port (default: 8089)
            username: Splunk username
            password: Splunk password
            token: Splunk auth token (alternative to username/password)
            scheme: https or http
            verify_ssl: Verify SSL certificates
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required: pip install requests")

        self.host = host or os.environ.get("SPLUNK_HOST")
        self.port = port or int(os.environ.get("SPLUNK_PORT", "8089"))
        self.username = username or os.environ.get("SPLUNK_USERNAME")
        self.password = password or os.environ.get("SPLUNK_PASSWORD")
        self.token = token or os.environ.get("SPLUNK_TOKEN")
        self.scheme = scheme
        self.verify_ssl = verify_ssl
        self._session = None
        self._session_key = None

        if not self.host:
            raise ValueError("Splunk host required")

        if not self.token and not (self.username and self.password):
            raise ValueError("Either token or username/password required")

    @property
    def source_name(self) -> str:
        return "splunk"

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    def authenticate(self) -> bool:
        """Authenticate with Splunk and get session key."""
        try:
            self._session = requests.Session()
            self._session.verify = self.verify_ssl

            if self.token:
                # Use token auth
                self._session.headers.update({"Authorization": f"Bearer {self.token}"})
                self._session_key = self.token
            else:
                # Get session key with username/password
                resp = self._session.post(
                    f"{self.base_url}/services/auth/login",
                    data={
                        "username": self.username,
                        "password": self.password,
                        "output_mode": "json",
                    },
                    verify=self.verify_ssl,
                )
                resp.raise_for_status()

                self._session_key = resp.json().get("sessionKey")
                self._session.headers.update(
                    {"Authorization": f"Splunk {self._session_key}"}
                )

            # Test connection
            resp = self._session.get(
                f"{self.base_url}/services/server/info", params={"output_mode": "json"}
            )
            resp.raise_for_status()

            logger.info("Splunk authentication successful")
            return True
        except Exception as e:
            logger.error(f"Splunk authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Splunk")

    @with_rate_limit(requests_per_minute=60)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a saved search by name.

        Args:
            doc_id: Saved search name
        """
        self._ensure_authenticated()
        try:
            # Get saved search config
            resp = self._session.get(
                f"{self.base_url}/servicesNS/-/-/saved/searches/{doc_id}",
                params={"output_mode": "json"},
            )
            resp.raise_for_status()
            search_config = resp.json().get("entry", [{}])[0]

            content = self._format_saved_search(search_config)

            return LoadedDocument(
                id=f"splunk://savedsearch/{doc_id}",
                content=content,
                metadata={
                    "source": "splunk",
                    "search_name": doc_id,
                    "app": search_config.get("acl", {}).get("app", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                source="splunk",
            )
        except Exception as e:
            logger.error(f"Failed to load Splunk saved search {doc_id}: {e}")
            return None

    def load_folder(self, folder_path: str = "searches") -> List[LoadedDocument]:
        """Load Splunk resources.

        Args:
            folder_path: Resource type (searches, dashboards)
        """
        if folder_path == "searches":
            return self.load_saved_searches()
        elif folder_path == "dashboards":
            return self.load_dashboards()
        else:
            logger.warning(f"Unknown folder type: {folder_path}")
            return []

    def load_saved_searches(self, app: Optional[str] = None) -> List[LoadedDocument]:
        """Load all saved searches.

        Args:
            app: Filter by app (None = all apps)
        """
        self._ensure_authenticated()
        docs = []

        try:
            namespace = f"servicesNS/-/{app}" if app else "servicesNS/-/-"

            resp = self._session.get(
                f"{self.base_url}/{namespace}/saved/searches",
                params={"output_mode": "json", "count": 0},
            )
            resp.raise_for_status()
            searches = resp.json().get("entry", [])

            logger.info(f"Found {len(searches)} Splunk saved searches")

            for search in searches:
                name = search.get("name")
                if name:
                    content = self._format_saved_search(search)

                    docs.append(
                        LoadedDocument(
                            id=f"splunk://savedsearch/{name}",
                            content=content,
                            metadata={
                                "source": "splunk",
                                "search_name": name,
                                "app": search.get("acl", {}).get("app", ""),
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            source="splunk",
                        )
                    )

        except Exception as e:
            logger.error(f"Failed to load Splunk saved searches: {e}")

        return docs

    def load_dashboards(self, app: Optional[str] = None) -> List[LoadedDocument]:
        """Load all dashboards.

        Args:
            app: Filter by app (None = all apps)
        """
        self._ensure_authenticated()
        docs = []

        try:
            namespace = f"servicesNS/-/{app}" if app else "servicesNS/-/-"

            resp = self._session.get(
                f"{self.base_url}/{namespace}/data/ui/views",
                params={"output_mode": "json", "count": 0},
            )
            resp.raise_for_status()
            dashboards = resp.json().get("entry", [])

            logger.info(f"Found {len(dashboards)} Splunk dashboards")

            for dashboard in dashboards:
                name = dashboard.get("name")
                if name:
                    content = self._format_dashboard(dashboard)

                    docs.append(
                        LoadedDocument(
                            id=f"splunk://dashboard/{name}",
                            content=content,
                            metadata={
                                "source": "splunk",
                                "dashboard_name": name,
                                "app": dashboard.get("acl", {}).get("app", ""),
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            source="splunk",
                        )
                    )

        except Exception as e:
            logger.error(f"Failed to load Splunk dashboards: {e}")

        return docs

    def run_search(
        self,
        query: str,
        earliest_time: str = "-24h",
        latest_time: str = "now",
        max_results: int = 100,
    ) -> List[LoadedDocument]:
        """Run a Splunk search query.

        Args:
            query: SPL (Search Processing Language) query
            earliest_time: Start time (Splunk time format, e.g., "-24h", "2024-01-01")
            latest_time: End time (default: "now")
            max_results: Maximum results to return
        """
        self._ensure_authenticated()

        try:
            # Create search job
            resp = self._session.post(
                f"{self.base_url}/services/search/jobs",
                data={
                    "search": query,
                    "earliest_time": earliest_time,
                    "latest_time": latest_time,
                    "output_mode": "json",
                    "exec_mode": "blocking",  # Wait for results
                    "max_count": max_results,
                },
            )
            resp.raise_for_status()
            job_sid = resp.json().get("sid")

            logger.info(f"Created Splunk search job: {job_sid}")

            # Get results
            results_resp = self._session.get(
                f"{self.base_url}/services/search/jobs/{job_sid}/results",
                params={"output_mode": "json", "count": max_results},
            )
            results_resp.raise_for_status()
            results = results_resp.json().get("results", [])

            logger.info(f"Got {len(results)} results from Splunk")

            # Format as documents
            docs = []
            for idx, result in enumerate(results[:max_results]):
                content = self._format_search_result(query, result)

                docs.append(
                    LoadedDocument(
                        id=f"splunk://search/{job_sid}/{idx}",
                        content=content,
                        metadata={
                            "source": "splunk",
                            "query": query,
                            "job_sid": job_sid,
                            "index": result.get("index", ""),
                            "sourcetype": result.get("sourcetype", ""),
                            "host": result.get("host", ""),
                            "_time": result.get("_time", ""),
                        },
                        source="splunk",
                    )
                )

            return docs

        except Exception as e:
            logger.error(f"Failed to run Splunk search: {e}")
            return []

    def _format_saved_search(self, search: dict) -> str:
        """Format saved search as text."""
        content = search.get("content", {})
        name = search.get("name", "Unknown")

        return f"""# Splunk Saved Search: {name}

## Configuration
- **App**: {search.get('acl', {}).get('app', 'unknown')}
- **Owner**: {search.get('author', 'unknown')}
- **Enabled**: {content.get('disabled', '0') == '0'}

## Search Query
```spl
{content.get('search', 'No query')}
```

## Schedule
- **Cron**: {content.get('cron_schedule', 'Not scheduled')}
- **Earliest**: {content.get('dispatch.earliest_time', 'N/A')}
- **Latest**: {content.get('dispatch.latest_time', 'N/A')}

## Actions
- **Email**: {content.get('action.email', '0') == '1'}
- **Alert**: {content.get('alert_type', 'none')}
"""

    def _format_dashboard(self, dashboard: dict) -> str:
        """Format dashboard as text."""
        content = dashboard.get("content", {})
        name = dashboard.get("name", "Unknown")
        xml = content.get("eai:data", "")

        # Try to parse XML to extract panels
        panels = []
        try:
            root = ET.fromstring(xml)
            for panel in root.findall(".//panel"):
                title = panel.find("title")
                panels.append(title.text if title is not None else "Untitled")
        except Exception:
            pass

        panel_list = "\n".join(f"- {p}" for p in panels) if panels else "No panels"

        return f"""# Splunk Dashboard: {name}

## Configuration
- **App**: {dashboard.get('acl', {}).get('app', 'unknown')}
- **Owner**: {dashboard.get('author', 'unknown')}

## Panels
{panel_list}
"""

    def _format_search_result(self, query: str, result: dict) -> str:
        """Format search result as text."""
        # Get key fields
        time = result.get("_time", "Unknown")
        raw = result.get("_raw", "")

        # Get all fields except internal ones
        fields = {k: v for k, v in result.items() if not k.startswith("_")}

        fields_str = "\n".join(f"- **{k}**: {v}" for k, v in list(fields.items())[:20])

        return f"""# Splunk Search Result

## Query
```spl
{query}
```

## Event
- **Time**: {time}
- **Source**: {result.get('source', 'unknown')}
- **Sourcetype**: {result.get('sourcetype', 'unknown')}
- **Host**: {result.get('host', 'unknown')}

## Fields
{fields_str}

## Raw Event
```
{raw[:1000]}
```
"""
