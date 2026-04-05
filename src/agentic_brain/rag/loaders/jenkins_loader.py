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

"""Jenkins loader for RAG pipelines.

Load Jenkins jobs, builds, and pipeline configurations.
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class JenkinsLoader(BaseLoader):
    """Load Jenkins CI/CD jobs and build data.

    Features:
    - Job configurations
    - Build history and logs
    - Pipeline definitions
    - Build artifacts metadata
    - Test results

    Requirements:
        pip install requests

    Environment variables:
        JENKINS_URL: Jenkins server URL
        JENKINS_USER: Jenkins username
        JENKINS_TOKEN: Jenkins API token

    Example:
        loader = JenkinsLoader(
            url="https://jenkins.company.com",
            username="user",
            token="xxx"
        )
        loader.authenticate()
        docs = loader.load_jobs()
    """

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        token: Optional[str] = None,
        **kwargs,
    ):
        """Initialize Jenkins loader.

        Args:
            url: Jenkins server URL
            username: Jenkins username
            token: Jenkins API token
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required: pip install requests")

        self.url = (url or os.environ.get("JENKINS_URL", "")).rstrip("/")
        self.username = username or os.environ.get("JENKINS_USER")
        self.token = token or os.environ.get("JENKINS_TOKEN")
        self._session = None

        if not self.url:
            raise ValueError("Jenkins URL required")

    @property
    def source_name(self) -> str:
        return "jenkins"

    def authenticate(self) -> bool:
        """Initialize Jenkins API session."""
        try:
            self._session = requests.Session()

            if self.username and self.token:
                self._session.auth = (self.username, self.token)

            # Test connection
            resp = self._session.get(f"{self.url}/api/json")
            resp.raise_for_status()

            logger.info("Jenkins authentication successful")
            return True
        except Exception as e:
            logger.error(f"Jenkins authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Jenkins")

    @with_rate_limit(requests_per_minute=60)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Jenkins job.

        Args:
            doc_id: Job name (format: "job/name" or "job/name/buildNumber")
        """
        self._ensure_authenticated()
        try:
            # Check if doc_id includes build number
            if "/builds/" in doc_id:
                job_path, build_num = doc_id.rsplit("/builds/", 1)
                return self._load_build(job_path, build_num)
            else:
                return self._load_job(doc_id)
        except Exception as e:
            logger.error(f"Failed to load Jenkins job {doc_id}: {e}")
            return None

    def _load_job(self, job_name: str) -> Optional[LoadedDocument]:
        """Load job configuration and recent builds."""
        resp = self._session.get(
            f"{self.url}/job/{job_name}/api/json",
            params={
                "tree": "name,description,url,builds[number,result,timestamp,duration]"
            },
        )
        resp.raise_for_status()
        job = resp.json()

        # Get config.xml for pipeline definition
        config_resp = self._session.get(f"{self.url}/job/{job_name}/config.xml")
        config_xml = config_resp.text if config_resp.ok else ""

        content = self._format_job(job, config_xml)

        return LoadedDocument(
            id=f"jenkins://job/{job_name}",
            content=content,
            metadata={
                "source": "jenkins",
                "job_name": job_name,
                "url": job.get("url", ""),
                "timestamp": datetime.utcnow().isoformat(),
            },
            source="jenkins",
        )

    def _load_build(self, job_name: str, build_number: str) -> Optional[LoadedDocument]:
        """Load specific build details."""
        resp = self._session.get(f"{self.url}/job/{job_name}/{build_number}/api/json")
        resp.raise_for_status()
        build = resp.json()

        # Get console log (truncated)
        log_resp = self._session.get(
            f"{self.url}/job/{job_name}/{build_number}/consoleText"
        )
        console_log = log_resp.text[-10000:] if log_resp.ok else ""  # Last 10KB

        content = self._format_build(job_name, build, console_log)

        return LoadedDocument(
            id=f"jenkins://job/{job_name}/builds/{build_number}",
            content=content,
            metadata={
                "source": "jenkins",
                "job_name": job_name,
                "build_number": int(build_number),
                "result": build.get("result", "UNKNOWN"),
                "duration_ms": build.get("duration", 0),
                "timestamp": datetime.fromtimestamp(
                    build.get("timestamp", 0) / 1000
                ).isoformat(),
            },
            source="jenkins",
        )

    def load_folder(self, folder_path: str = "") -> List[LoadedDocument]:
        """Load all jobs from Jenkins.

        Args:
            folder_path: Folder path (empty = root)
        """
        self._ensure_authenticated()
        docs = []

        try:
            url = f"{self.url}/api/json"
            if folder_path:
                url = f"{self.url}/job/{folder_path}/api/json"

            resp = self._session.get(url, params={"tree": "jobs[name,url]"})
            resp.raise_for_status()
            data = resp.json()

            jobs = data.get("jobs", [])
            logger.info(f"Found {len(jobs)} Jenkins jobs")

            for job in jobs:
                job_name = job.get("name")
                if job_name:
                    doc = self._load_job(job_name)
                    if doc:
                        docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load Jenkins jobs: {e}")

        return docs

    def load_jobs(self, folder: Optional[str] = None) -> List[LoadedDocument]:
        """Load all jobs.

        Args:
            folder: Folder name (None = root)
        """
        return self.load_folder(folder or "")

    def _format_job(self, job: dict, config_xml: str) -> str:
        """Format job data as text."""
        content_parts = [
            f"# Jenkins Job: {job.get('name', 'Unknown')}",
            "",
            "## Overview",
            f"- **URL**: {job.get('url', 'Unknown')}",
            f"- **Description**: {job.get('description', 'No description')}",
            "",
        ]

        # Add recent builds
        builds = job.get("builds", [])
        if builds:
            content_parts.append("## Recent Builds")
            for build in builds[:10]:
                num = build.get("number", "?")
                result = build.get("result", "UNKNOWN")
                timestamp = datetime.fromtimestamp(
                    build.get("timestamp", 0) / 1000
                ).strftime("%Y-%m-%d %H:%M")
                duration = build.get("duration", 0) // 1000  # seconds
                content_parts.append(
                    f"- **Build #{num}**: {result} ({duration}s) - {timestamp}"
                )
            content_parts.append("")

        # Add pipeline snippet if available
        if "pipeline" in config_xml.lower() or "jenkinsfile" in config_xml.lower():
            content_parts.append("## Pipeline Configuration")
            content_parts.append("```xml")
            content_parts.append(config_xml[:2000])  # First 2KB
            content_parts.append("```")

        return "\n".join(content_parts)

    def _format_build(self, job_name: str, build: dict, console_log: str) -> str:
        """Format build data as text."""
        timestamp = datetime.fromtimestamp(build.get("timestamp", 0) / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        duration_s = build.get("duration", 0) // 1000

        content_parts = [
            f"# Jenkins Build: {job_name} #{build.get('number', '?')}",
            "",
            "## Build Information",
            f"- **Result**: {build.get('result', 'UNKNOWN')}",
            f"- **Started**: {timestamp}",
            f"- **Duration**: {duration_s}s",
            f"- **URL**: {build.get('url', 'Unknown')}",
            "",
        ]

        # Add parameters if any
        actions = build.get("actions", [])
        for action in actions:
            if "parameters" in action:
                content_parts.append("## Parameters")
                for param in action["parameters"]:
                    name = param.get("name", "?")
                    value = param.get("value", "")
                    content_parts.append(f"- **{name}**: {value}")
                content_parts.append("")
                break

        # Add console log snippet
        if console_log:
            content_parts.append("## Console Output (Last 10KB)")
            content_parts.append("```")
            content_parts.append(console_log)
            content_parts.append("```")

        return "\n".join(content_parts)
