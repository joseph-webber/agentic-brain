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

"""ArgoCD loader for RAG pipelines.

Load applications, deployments, and sync status from ArgoCD.
Supports GitOps workflow documentation and deployment history.
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


class ArgoCDLoader(BaseLoader):
    """Load ArgoCD applications and deployment data.

    Features:
    - Application manifests
    - Sync status and history
    - Deployment events
    - Resource health status
    - Git repository connections

    Requirements:
        pip install requests

    Environment variables:
        ARGOCD_SERVER: ArgoCD server URL
        ARGOCD_TOKEN: ArgoCD auth token

    Example:
        loader = ArgoCDLoader(
            server="argocd.company.com",
            token="xxx"
        )
        loader.authenticate()
        docs = loader.load_applications()
    """

    def __init__(
        self,
        server: Optional[str] = None,
        token: Optional[str] = None,
        insecure: bool = False,
        **kwargs,
    ):
        """Initialize ArgoCD loader.

        Args:
            server: ArgoCD server URL (without https://)
            token: ArgoCD auth token
            insecure: Skip TLS verification (for self-signed certs)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required: pip install requests")

        self.server = server or os.environ.get("ARGOCD_SERVER")
        self.token = token or os.environ.get("ARGOCD_TOKEN")
        self.insecure = insecure
        self._session = None

        if not self.server:
            raise ValueError("ArgoCD server URL required")
        if not self.token:
            raise ValueError("ArgoCD auth token required")

    @property
    def source_name(self) -> str:
        return "argocd"

    def authenticate(self) -> bool:
        """Initialize ArgoCD API session."""
        try:
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
            )

            if self.insecure:
                self._session.verify = False
                import urllib3

                urllib3.disable_warnings()

            # Test connection
            resp = self._session.get(f"https://{self.server}/api/version")
            resp.raise_for_status()

            logger.info(f"ArgoCD authentication successful: {resp.json()}")
            return True
        except Exception as e:
            logger.error(f"ArgoCD authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with ArgoCD")

    @with_rate_limit(requests_per_minute=60)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single ArgoCD application.

        Args:
            doc_id: Application name
        """
        self._ensure_authenticated()
        try:
            resp = self._session.get(
                f"https://{self.server}/api/v1/applications/{doc_id}"
            )
            resp.raise_for_status()
            app = resp.json()

            # Get sync history
            history_resp = self._session.get(
                f"https://{self.server}/api/v1/applications/{doc_id}/synchistory"
            )
            history = history_resp.json() if history_resp.ok else []

            content = self._format_application(app, history)

            return LoadedDocument(
                source_id=f"argocd://{doc_id}",
                content=content,
                metadata={
                    "source": "argocd",
                    "application": doc_id,
                    "namespace": app.get("metadata", {}).get("namespace", ""),
                    "sync_status": app.get("status", {}).get("sync", {}).get("status"),
                    "health_status": app.get("status", {})
                    .get("health", {})
                    .get("status"),
                    "repo": app.get("spec", {}).get("source", {}).get("repoURL"),
                    "path": app.get("spec", {}).get("source", {}).get("path"),
                    "cluster": app.get("spec", {}).get("destination", {}).get("server"),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                source="argocd",
            )
        except Exception as e:
            logger.error(f"Failed to load ArgoCD application {doc_id}: {e}")
            return None

    def load_folder(self, folder_path: str = "") -> List[LoadedDocument]:
        """Load all applications, optionally filtered by project.

        Args:
            folder_path: Project name to filter (empty = all)
        """
        self._ensure_authenticated()
        docs = []

        try:
            # List applications
            params = {}
            if folder_path:
                params["project"] = folder_path

            resp = self._session.get(
                f"https://{self.server}/api/v1/applications", params=params
            )
            resp.raise_for_status()
            apps = resp.json().get("items", [])

            logger.info(f"Found {len(apps)} ArgoCD applications")

            for app in apps:
                app_name = app.get("metadata", {}).get("name")
                if app_name:
                    doc = self.load_document(app_name)
                    if doc:
                        docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load ArgoCD applications: {e}")

        return docs

    def load_applications(self, project: Optional[str] = None) -> List[LoadedDocument]:
        """Load all applications for a project.

        Args:
            project: Project name (None = all projects)
        """
        return self.load_folder(project or "")

    def _format_application(self, app: dict, history: list) -> str:
        """Format application data as text."""
        metadata = app.get("metadata", {})
        spec = app.get("spec", {})
        status = app.get("status", {})

        content_parts = [
            f"# ArgoCD Application: {metadata.get('name', 'Unknown')}",
            "",
            "## Overview",
            f"- **Namespace**: {metadata.get('namespace', 'default')}",
            f"- **Project**: {spec.get('project', 'default')}",
            f"- **Created**: {metadata.get('creationTimestamp', 'Unknown')}",
            "",
            "## Source",
            f"- **Repository**: {spec.get('source', {}).get('repoURL', 'Unknown')}",
            f"- **Path**: {spec.get('source', {}).get('path', '/')}",
            f"- **Target Revision**: {spec.get('source', {}).get('targetRevision', 'HEAD')}",
            "",
            "## Destination",
            f"- **Cluster**: {spec.get('destination', {}).get('server', 'Unknown')}",
            f"- **Namespace**: {spec.get('destination', {}).get('namespace', 'default')}",
            "",
            "## Status",
            f"- **Sync Status**: {status.get('sync', {}).get('status', 'Unknown')}",
            f"- **Health Status**: {status.get('health', {}).get('status', 'Unknown')}",
            f"- **Revision**: {status.get('sync', {}).get('revision', 'Unknown')[:8]}",
        ]

        # Add sync history
        if history:
            content_parts.append("")
            content_parts.append("## Recent Deployments")
            for deploy in history[:5]:
                started = deploy.get("deployStartedAt", "Unknown")
                revision = deploy.get("revision", "Unknown")[:8]
                status = deploy.get("status", "Unknown")
                content_parts.append(f"- **{started}**: {revision} - {status}")

        # Add resources
        resources = status.get("resources", [])
        if resources:
            content_parts.append("")
            content_parts.append("## Resources")
            for res in resources[:20]:  # Limit to 20
                kind = res.get("kind", "Unknown")
                name = res.get("name", "Unknown")
                health = res.get("health", {}).get("status", "Unknown")
                content_parts.append(f"- **{kind}** {name}: {health}")

        return "\n".join(content_parts)
