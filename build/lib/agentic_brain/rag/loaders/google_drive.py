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

"""Google Drive loader for RAG pipelines."""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for Google API
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False


class GoogleDriveLoader(BaseLoader):
    """Load documents from Google Drive.

    Supports:
    - Text files (txt, md, etc.)
    - Google Docs (exported as text)
    - PDFs (with text extraction)
    - Spreadsheets (as CSV/text)

    Example:
        loader = GoogleDriveLoader(credentials_path="client_secrets.json")
        docs = loader.load_folder("My Documents")
    """

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    # Supported MIME types
    SUPPORTED_MIME_TYPES = [
        "text/plain",
        "text/markdown",
        "application/pdf",
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    # Google native MIME type mapping
    GOOGLE_MIME_TYPES = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        token_path: str = "drive_token.json",
        service_account_path: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ):
        """Initialize Google Drive loader.

        Args:
            credentials_path: Path to OAuth credentials JSON
            token_path: Path to store/load OAuth token
            service_account_path: Path to service account JSON (alternative auth)
            scopes: OAuth scopes (defaults to read-only)
        """
        super().__init__()
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._service_account_path = service_account_path
        self._scopes = scopes or self.SCOPES
        self._service = None
        self._creds = None

    @property
    def source_name(self) -> str:
        """Return source name."""
        return "google_drive"

    def authenticate(self) -> bool:
        """Authenticate with Google Drive API."""
        if not GOOGLE_DRIVE_AVAILABLE:
            raise ImportError(
                "Google API client not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )

        try:
            from google.oauth2 import service_account

            if self._service_account_path:
                self._creds = service_account.Credentials.from_service_account_file(
                    self._service_account_path, scopes=self._scopes
                )
            else:
                import os

                if os.path.exists(self._token_path):
                    self._creds = Credentials.from_authorized_user_file(
                        self._token_path, self._scopes
                    )

                if not self._creds or not self._creds.valid:
                    if (
                        self._creds
                        and self._creds.expired
                        and self._creds.refresh_token
                    ):
                        self._creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self._credentials_path, self._scopes
                        )
                        self._creds = flow.run_local_server(port=0)

                    with open(self._token_path, "w") as token:
                        token.write(self._creds.to_json())

            self._service = build("drive", "v3", credentials=self._creds)
            self._authenticated = True
            return True

        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            self._authenticated = False
            return False

    def load_file(self, file_id: str) -> LoadedDocument:
        """Load a single file by ID."""
        if not self._authenticated:
            self.authenticate()

        file_meta = (
            self._service.files()
            .get(fileId=file_id, fields="id,name,mimeType,modifiedTime")
            .execute()
        )

        mime_type = file_meta.get("mimeType", "")

        # Export Google Docs to plain text
        if mime_type in self.GOOGLE_MIME_TYPES:
            export_type = self.GOOGLE_MIME_TYPES[mime_type]
            content = (
                self._service.files()
                .export(fileId=file_id, mimeType=export_type)
                .execute()
            )
            if isinstance(content, bytes):
                content = content.decode("utf-8")
        else:
            content = self._service.files().get_media(fileId=file_id).execute()
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")

        return LoadedDocument(
            content=content,
            source=f"gdrive://{file_id}",
            title=file_meta.get("name", file_id),
            metadata={
                "file_id": file_id,
                "mime_type": mime_type,
                "modified_time": file_meta.get("modifiedTime"),
            },
        )

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> List[LoadedDocument]:
        """Load all documents from a folder."""
        if not self._authenticated:
            self.authenticate()

        # Find folder by name
        query = (
            f"name='{folder_path}' and mimeType='application/vnd.google-apps.folder'"
        )
        results = self._service.files().list(q=query, fields="files(id)").execute()
        folders = results.get("files", [])

        if not folders:
            logger.warning(f"Folder not found: {folder_path}")
            return []

        folder_id = folders[0]["id"]
        return self._load_folder_by_id(folder_id, recursive)

    def _load_folder_by_id(
        self, folder_id: str, recursive: bool = True
    ) -> List[LoadedDocument]:
        """Load folder contents by ID."""
        documents = []

        query = f"'{folder_id}' in parents and trashed=false"
        results = (
            self._service.files()
            .list(q=query, fields="files(id,name,mimeType)")
            .execute()
        )

        for item in results.get("files", []):
            mime_type = item.get("mimeType", "")

            if mime_type == "application/vnd.google-apps.folder":
                if recursive:
                    documents.extend(self._load_folder_by_id(item["id"], recursive))
            elif (
                mime_type in self.SUPPORTED_MIME_TYPES
                or mime_type in self.GOOGLE_MIME_TYPES
            ):
                try:
                    doc = self.load_file(item["id"])
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"Failed to load {item['name']}: {e}")

        return documents

    def search(self, query: str, max_results: int = 100) -> List[LoadedDocument]:
        """Search for files matching query."""
        if not self._authenticated:
            self.authenticate()

        results = (
            self._service.files()
            .list(
                q=f"fullText contains '{query}' and trashed=false",
                fields="files(id,name,mimeType)",
                pageSize=max_results,
            )
            .execute()
        )

        documents = []
        for item in results.get("files", []):
            try:
                doc = self.load_file(item["id"])
                documents.append(doc)
            except Exception as e:
                logger.warning(f"Failed to load search result {item['name']}: {e}")

        return documents
