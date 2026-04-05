# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Source connectors for external knowledge systems."""

from .base import (
    Connector,
    ConnectorRecord,
    ConnectorSchedule,
    ConnectorSyncCursor,
    ConnectorSyncPage,
    ConnectorSyncResult,
    parse_datetime,
)
from .confluence import ConfluenceConnector
from .github import GitHubConnector
from .google_drive import GoogleDriveConnector
from .notion import NotionConnector
from .slack import SlackConnector

__all__ = [
    "Connector",
    "ConnectorRecord",
    "ConnectorSchedule",
    "ConnectorSyncCursor",
    "ConnectorSyncPage",
    "ConnectorSyncResult",
    "parse_datetime",
    "ConfluenceConnector",
    "GitHubConnector",
    "GoogleDriveConnector",
    "NotionConnector",
    "SlackConnector",
]
