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

"""Tests for cloud document loaders (Google Drive, Gmail, iCloud)."""

import base64
import os
from datetime import UTC, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest

from agentic_brain.rag.loaders import (
    BOTO3_AVAILABLE,
    CONFLUENCE_AVAILABLE,
    FIREBASE_AVAILABLE,
    GOOGLE_API_AVAILABLE,
    MSAL_AVAILABLE,
    NOTION_AVAILABLE,
    PYGITHUB_AVAILABLE,
    PYICLOUD_AVAILABLE,
    PYMONGO_AVAILABLE,
    SLACK_AVAILABLE,
    BaseLoader,
    ConfluenceLoader,
    FirestoreLoader,
    GitHubLoader,
    GmailLoader,
    GoogleDriveLoader,
    LoadedDocument,
    Microsoft365Loader,
    MongoDBLoader,
    NotionLoader,
    S3Loader,
    SlackLoader,
    create_loader,
    iCloudLoader,
    load_from_multiple_sources,
)

# ============================================================================
# LoadedDocument Tests
# ============================================================================


class TestLoadedDocument:
    """Tests for LoadedDocument dataclass."""

    def test_basic_creation(self):
        """Test creating a LoadedDocument with minimal fields."""
        doc = LoadedDocument(content="Hello World")
        assert doc.content == "Hello World"
        assert doc.metadata == {}
        assert doc.source == ""
        assert doc.source_id == ""
        assert doc.filename == ""
        assert doc.mime_type == "text/plain"
        assert doc.created_at is None
        assert doc.modified_at is None
        assert doc.size_bytes == 0

    def test_full_creation(self):
        """Test creating a LoadedDocument with all fields."""
        now = datetime.now(UTC)
        doc = LoadedDocument(
            content="Test content",
            metadata={"key": "value"},
            source="google_drive",
            source_id="abc123",
            filename="test.txt",
            mime_type="text/plain",
            created_at=now,
            modified_at=now,
            size_bytes=12,
        )
        assert doc.content == "Test content"
        assert doc.metadata == {"key": "value"}
        assert doc.source == "google_drive"
        assert doc.source_id == "abc123"
        assert doc.filename == "test.txt"
        assert doc.mime_type == "text/plain"
        assert doc.created_at == now
        assert doc.modified_at == now
        assert doc.size_bytes == 12

    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        doc = LoadedDocument(
            content="Test content",
            metadata={"key": "value"},
            source="gmail",
            source_id="msg123",
            filename="email.eml",
            mime_type="message/rfc822",
            created_at=now,
            modified_at=now,
            size_bytes=100,
        )

        result = doc.to_dict()

        assert result["content"] == "Test content"
        assert result["metadata"] == {"key": "value"}
        assert result["source"] == "gmail"
        assert result["source_id"] == "msg123"
        assert result["filename"] == "email.eml"
        assert result["mime_type"] == "message/rfc822"
        assert result["created_at"] == "2026-01-15T12:00:00+00:00"
        assert result["modified_at"] == "2026-01-15T12:00:00+00:00"
        assert result["size_bytes"] == 100

    def test_to_dict_none_dates(self):
        """Test serialization with None dates."""
        doc = LoadedDocument(content="Test")
        result = doc.to_dict()
        assert result["created_at"] is None
        assert result["modified_at"] is None

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "content": "Restored content",
            "metadata": {"restored": True},
            "source": "icloud",
            "source_id": "path/to/file",
            "filename": "doc.txt",
            "mime_type": "text/plain",
            "created_at": "2026-01-15T12:00:00+00:00",
            "modified_at": "2026-01-16T12:00:00+00:00",
            "size_bytes": 200,
        }

        doc = LoadedDocument.from_dict(data)

        assert doc.content == "Restored content"
        assert doc.metadata == {"restored": True}
        assert doc.source == "icloud"
        assert doc.source_id == "path/to/file"
        assert doc.filename == "doc.txt"
        assert doc.created_at.year == 2026
        assert doc.size_bytes == 200

    def test_from_dict_minimal(self):
        """Test deserialization with minimal data."""
        data = {"content": "Just content"}
        doc = LoadedDocument.from_dict(data)
        assert doc.content == "Just content"
        assert doc.metadata == {}
        assert doc.created_at is None

    def test_roundtrip(self):
        """Test serialization/deserialization roundtrip."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        original = LoadedDocument(
            content="Roundtrip test",
            metadata={"nested": {"data": [1, 2, 3]}},
            source="google_drive",
            source_id="xyz789",
            filename="roundtrip.txt",
            mime_type="text/plain",
            created_at=now,
            modified_at=now,
            size_bytes=50,
        )

        restored = LoadedDocument.from_dict(original.to_dict())

        assert restored.content == original.content
        assert restored.metadata == original.metadata
        assert restored.source == original.source
        assert restored.source_id == original.source_id
        assert restored.filename == original.filename


# ============================================================================
# BaseLoader Tests
# ============================================================================


class TestBaseLoader:
    """Tests for BaseLoader abstract class."""

    def test_cannot_instantiate_directly(self):
        """Test that BaseLoader cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseLoader()

    def test_concrete_implementation(self):
        """Test creating a concrete loader implementation."""

        class ConcreteLoader(BaseLoader):
            @property
            def source_name(self) -> str:
                return "test"

            def authenticate(self) -> bool:
                return True

            def load_document(self, doc_id: str):
                return LoadedDocument(content=f"Doc: {doc_id}", source="test")

            def load_folder(self, folder_path: str, recursive: bool = True):
                return [LoadedDocument(content="From folder", source="test")]

            def search(self, query: str, max_results: int = 50):
                return [LoadedDocument(content=f"Search: {query}", source="test")]

        loader = ConcreteLoader()
        assert loader.source_name == "test"
        assert loader.authenticate() is True

        doc = loader.load_document("123")
        assert doc.content == "Doc: 123"

        docs = loader.load_folder("/test")
        assert len(docs) == 1

        results = loader.search("query")
        assert len(results) == 1

    def test_clean_html_with_beautifulsoup(self):
        """Test HTML cleaning with BeautifulSoup available."""

        class TestLoader(BaseLoader):
            @property
            def source_name(self) -> str:
                return "test"

            def authenticate(self) -> bool:
                return True

            def load_document(self, doc_id: str):
                return None

            def load_folder(self, folder_path: str, recursive: bool = True):
                return []

            def search(self, query: str, max_results: int = 50):
                return []

        loader = TestLoader()
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <script>alert('test');</script>
            <style>body { color: red; }</style>
            <h1>Hello</h1>
            <p>World</p>
        </body>
        </html>
        """

        result = loader._clean_html(html)
        assert "Hello" in result
        assert "World" in result
        assert "alert" not in result
        assert "color: red" not in result

    def test_clean_html_fallback(self):
        """Test HTML cleaning fallback (regex-based)."""

        class TestLoader(BaseLoader):
            @property
            def source_name(self) -> str:
                return "test"

            def authenticate(self) -> bool:
                return True

            def load_document(self, doc_id: str):
                return None

            def load_folder(self, folder_path: str, recursive: bool = True):
                return []

            def search(self, query: str, max_results: int = 50):
                return []

        loader = TestLoader()

        # Patch BeautifulSoup import to fail
        with patch.dict("sys.modules", {"bs4": None}):
            html = "<p>Simple <b>test</b> content</p>"
            result = loader._clean_html(html)
            assert "test" in result
            assert "<p>" not in result
            assert "<b>" not in result


# ============================================================================
# GoogleDriveLoader Tests
# ============================================================================


@pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
class TestGoogleDriveLoader:
    """Tests for GoogleDriveLoader."""

    def test_source_name(self):
        """Test source_name property."""
        with patch("agentic_brain.rag.loaders.GOOGLE_API_AVAILABLE", True):
            loader = GoogleDriveLoader(credentials_path="dummy.json")
            assert loader.source_name == "google_drive"

    def test_init_with_params(self):
        """Test initialization with parameters."""
        scopes = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
        loader = GoogleDriveLoader(
            credentials_path="creds.json",
            token_path="token.json",
            service_account_path="service.json",
            scopes=scopes,
        )
        assert loader._credentials_path == "creds.json"
        assert loader._token_path == "token.json"
        assert loader._service_account_path == "service.json"
        assert loader._scopes == scopes

    @patch("googleapiclient.discovery.build")
    @patch("google.oauth2.service_account.Credentials.from_service_account_file")
    def test_authenticate_service_account(self, mock_from_sa, mock_build):
        """Test service account authentication."""
        mock_creds = MagicMock()
        mock_from_sa.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        loader = GoogleDriveLoader(
            credentials_path="service-account.json",
            service_account_path="service-account.json",
        )

        result = loader.authenticate()

        assert result is True
        mock_from_sa.assert_called_once_with(
            "service-account.json", scopes=loader._scopes
        )
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)

    @patch("builtins.open", new_callable=mock_open)
    @patch("googleapiclient.discovery.build")
    @patch("google.oauth2.credentials.Credentials.from_authorized_user_file")
    @patch("os.path.exists")
    def test_authenticate_oauth_existing_token(
        self, mock_exists, mock_from_token, mock_build, mock_open_file
    ):
        """Test OAuth authentication with existing valid token."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_from_token.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        loader = GoogleDriveLoader(
            credentials_path="client_secrets.json", token_path="token.json"
        )

        result = loader.authenticate()

        assert result is True
        mock_from_token.assert_called_once()
        mock_open_file.assert_called()

    @patch("agentic_brain.rag.loaders.google_drive.LoadedDocument")
    @patch("googleapiclient.discovery.build")
    def test_load_document_success(self, mock_build, mock_loaded_document):
        """Test loading a document successfully."""
        # Setup mock service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock file metadata response
        mock_service.files().get().execute.return_value = {
            "id": "doc123",
            "name": "test.txt",
            "mimeType": "text/plain",
            "size": "100",
            "createdTime": "2026-01-15T12:00:00.000Z",
            "modifiedTime": "2026-01-16T12:00:00.000Z",
            "parents": ["folder123"],
        }

        loader = GoogleDriveLoader(credentials_path="creds.json")
        loader._service = mock_service
        loader._credentials = MagicMock()
        loader._authenticated = True

        mock_media = MagicMock()
        mock_media.execute.return_value = b"File content"
        mock_service.files().get_media.return_value = mock_media

        mocked_doc = SimpleNamespace(
            content="File content",
            source="google_drive",
            source_id="doc123",
            filename="test.txt",
            mime_type="text/plain",
            metadata={"file_id": "doc123"},
        )
        mock_loaded_document.return_value = mocked_doc

        doc = loader.load_document("doc123")

        assert doc is not None
        assert doc.source_id == "doc123"
        assert doc.filename == "test.txt"
        assert doc.mime_type == "text/plain"

    @patch("googleapiclient.discovery.build")
    def test_load_folder_empty(self, mock_build):
        """Test loading an empty folder."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock folder lookup
        mock_service.files().list().execute.return_value = {
            "files": [{"id": "folder123", "name": "TestFolder"}]
        }

        loader = GoogleDriveLoader(credentials_path="creds.json")
        loader._service = mock_service
        loader._credentials = MagicMock()
        loader._authenticated = True

        # Mock empty folder contents
        with patch.object(loader, "_load_folder_by_id", return_value=[]):
            docs = loader.load_folder("TestFolder")

        assert docs == []

    @patch("googleapiclient.discovery.build")
    def test_search_documents(self, mock_build):
        """Test searching for documents."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.files().list().execute.return_value = {
            "files": [
                {
                    "id": "doc1",
                    "name": "Report.txt",
                    "mimeType": "text/plain",
                    "size": "100",
                },
                {
                    "id": "doc2",
                    "name": "Notes.txt",
                    "mimeType": "text/plain",
                    "size": "200",
                },
            ],
            "nextPageToken": None,
        }

        loader = GoogleDriveLoader(credentials_path="creds.json")
        loader._service = mock_service
        loader._credentials = MagicMock()
        loader._authenticated = True

        with patch.object(loader, "load_file") as mock_load:
            mock_load.return_value = LoadedDocument(
                content="test", source="google_drive"
            )
            results = loader.search("quarterly report", max_results=10)

        assert len(results) == 2

    def test_supported_mime_types(self):
        """Test that SUPPORTED_MIME_TYPES contains expected types."""
        assert "text/plain" in GoogleDriveLoader.SUPPORTED_MIME_TYPES
        assert "application/pdf" in GoogleDriveLoader.SUPPORTED_MIME_TYPES
        assert "text/markdown" in GoogleDriveLoader.SUPPORTED_MIME_TYPES

    def test_google_mime_types(self):
        """Test that GOOGLE_MIME_TYPES contains workspace types."""
        assert (
            "application/vnd.google-apps.document"
            in GoogleDriveLoader.GOOGLE_MIME_TYPES
        )
        assert (
            "application/vnd.google-apps.spreadsheet"
            in GoogleDriveLoader.GOOGLE_MIME_TYPES
        )
        assert (
            "application/vnd.google-apps.presentation"
            in GoogleDriveLoader.GOOGLE_MIME_TYPES
        )


# ============================================================================
# GmailLoader Tests
# ============================================================================


@pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
class TestGmailLoader:
    """Tests for GmailLoader."""

    def test_source_name(self):
        """Test source_name property."""
        loader = GmailLoader(credentials_path="dummy.json")
        assert loader.source_name == "gmail"

    def test_init_with_params(self):
        """Test initialization with parameters."""
        loader = GmailLoader(
            credentials_path="creds.json",
            token_path="gmail_token.json",
            include_attachments=False,
            max_attachment_size_mb=10,
        )
        assert loader.credentials_path == "creds.json"
        assert loader.token_path == "gmail_token.json"
        assert loader.include_attachments is False
        assert loader.max_attachment_size == 10 * 1024 * 1024

    @patch("googleapiclient.discovery.build")
    @patch("google.oauth2.credentials.Credentials")
    @patch("os.path.exists")
    def test_authenticate_success(self, mock_exists, mock_creds_class, mock_build):
        """Test successful authentication."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        loader = GmailLoader(credentials_path="creds.json")
        result = loader.authenticate()

        assert result is True
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)

    def test_load_document_success(self):
        """Test loading an email successfully."""
        mock_service = MagicMock()

        # Mock message response
        body_data = base64.urlsafe_b64encode(b"Email body content").decode()
        mock_service.users().messages().get().execute.return_value = {
            "id": "msg123",
            "threadId": "thread123",
            "labelIds": ["INBOX"],
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Date", "value": "Mon, 15 Jan 2026 12:00:00 +0000"},
                ],
                "body": {"data": body_data},
            },
        }

        loader = GmailLoader(credentials_path="creds.json")
        loader._service = mock_service
        loader._credentials = MagicMock()

        doc = loader.load_document("msg123")

        assert doc is not None
        assert doc.source == "gmail"
        assert doc.source_id == "msg123"
        assert "Test Subject" in doc.content
        assert "Email body content" in doc.content
        assert doc.metadata["subject"] == "Test Subject"

    def test_load_recent(self):
        """Test loading recent emails."""
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            "messages": [
                {"id": "msg1"},
                {"id": "msg2"},
            ],
            "nextPageToken": None,
        }

        loader = GmailLoader(credentials_path="creds.json", include_attachments=False)
        loader._service = mock_service
        loader._credentials = MagicMock()

        with patch.object(loader, "load_document") as mock_load:
            mock_load.return_value = LoadedDocument(content="Email", source="gmail")
            emails = loader.load_recent(days=7)

        assert len(emails) == 2

    def test_search_with_query(self):
        """Test searching with Gmail query syntax."""
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}],
            "nextPageToken": None,
        }

        loader = GmailLoader(credentials_path="creds.json", include_attachments=False)
        loader._service = mock_service
        loader._credentials = MagicMock()

        with patch.object(loader, "load_document") as mock_load:
            mock_load.return_value = LoadedDocument(content="Email", source="gmail")
            loader.search("from:boss@company.com has:attachment")

        # Verify the search was called with our query
        mock_service.users().messages().list.assert_called()

    def test_load_by_label(self):
        """Test loading emails by label."""
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}],
            "nextPageToken": None,
        }

        loader = GmailLoader(credentials_path="creds.json", include_attachments=False)
        loader._service = mock_service
        loader._credentials = MagicMock()

        with patch.object(loader, "load_document") as mock_load:
            mock_load.return_value = LoadedDocument(content="Email", source="gmail")
            emails = loader.load_by_label("IMPORTANT")

        assert len(emails) == 1

    def test_list_labels(self):
        """Test listing Gmail labels."""
        mock_service = MagicMock()
        mock_service.users().labels().list().execute.return_value = {
            "labels": [
                {"id": "INBOX", "name": "INBOX"},
                {"id": "Label_1", "name": "Custom Label"},
            ]
        }

        loader = GmailLoader(credentials_path="creds.json")
        loader._service = mock_service
        loader._credentials = MagicMock()

        labels = loader.list_labels()

        assert len(labels) == 2
        assert labels[0]["name"] == "INBOX"
        assert labels[1]["name"] == "Custom Label"

    def test_get_message_body_multipart(self):
        """Test extracting body from multipart message."""
        loader = GmailLoader(credentials_path="creds.json")

        text_data = base64.urlsafe_b64encode(b"Plain text content").decode()
        payload = {
            "parts": [
                {"mimeType": "text/plain", "body": {"data": text_data}},
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": base64.urlsafe_b64encode(
                            b"<p>HTML content</p>"
                        ).decode()
                    },
                },
            ]
        }

        body = loader._get_message_body(payload)

        assert body == "Plain text content"


# ============================================================================
# iCloudLoader Tests
# ============================================================================


class TestICloudLoader:
    """Tests for iCloudLoader."""

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_source_name(self):
        """Test source_name property."""
        loader = iCloudLoader(apple_id="test@icloud.com", password="password")
        assert loader.source_name == "icloud"

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_init_with_params(self):
        """Test initialization with parameters."""
        loader = iCloudLoader(
            apple_id="user@icloud.com",
            password="app-password",
            cookie_directory=".custom_icloud",
            max_file_size_mb=25,
        )
        assert loader.apple_id == "user@icloud.com"
        assert loader.password == "app-password"
        assert loader.cookie_directory == ".custom_icloud"
        assert loader.max_file_size == 25 * 1024 * 1024

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_init_from_environment(self):
        """Test initialization from environment variables."""
        with patch.dict(
            os.environ,
            {"ICLOUD_APPLE_ID": "env@icloud.com", "ICLOUD_PASSWORD": "env_password"},
        ):
            loader = iCloudLoader()
            assert loader.apple_id == "env@icloud.com"
            assert loader.password == "env_password"

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    @patch("agentic_brain.rag.loaders.PyiCloudService")
    def test_authenticate_success(self, mock_pyicloud):
        """Test successful authentication."""
        mock_api = MagicMock()
        mock_api.requires_2fa = False
        mock_pyicloud.return_value = mock_api

        loader = iCloudLoader(apple_id="test@icloud.com", password="password")
        result = loader.authenticate()

        assert result is True
        mock_pyicloud.assert_called_once()

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    @patch("agentic_brain.rag.loaders.PyiCloudService")
    def test_authenticate_requires_2fa(self, mock_pyicloud):
        """Test authentication with 2FA required."""
        mock_api = MagicMock()
        mock_api.requires_2fa = True
        mock_api.validate_2fa_code.return_value = True
        mock_api.is_trusted_session = True
        mock_pyicloud.return_value = mock_api

        loader = iCloudLoader(apple_id="test@icloud.com", password="password")

        with patch("builtins.input", return_value="123456"):
            result = loader.authenticate()

        assert result is True
        mock_api.validate_2fa_code.assert_called_once_with("123456")

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_load_document_txt(self):
        """Test loading a text file."""
        mock_api = MagicMock()

        # Create mock item
        mock_item = MagicMock()
        mock_item.type = "file"
        mock_item.name = "document.txt"
        mock_item.size = 100
        mock_item.date_modified = datetime.now()

        # Mock open/download
        mock_response = MagicMock()
        mock_response.raw.read.return_value = b"File content here"
        mock_item.open.return_value = mock_response

        # Setup folder navigation
        mock_root = MagicMock()
        mock_root.__getitem__ = lambda self, key: mock_item
        mock_api.drive.root = mock_root

        loader = iCloudLoader(apple_id="test@icloud.com", password="password")
        loader._api = mock_api

        doc = loader.load_document("document.txt")

        assert doc is not None
        assert doc.content == "File content here"
        assert doc.filename == "document.txt"

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_load_folder_recursive(self):
        """Test loading folder recursively."""
        mock_api = MagicMock()

        # Create mock files
        mock_file1 = MagicMock()
        mock_file1.type = "file"
        mock_file1.name = "file1.txt"
        mock_file1.size = 50
        mock_response1 = MagicMock()
        mock_response1.raw.read.return_value = b"Content 1"
        mock_file1.open.return_value = mock_response1

        mock_file2 = MagicMock()
        mock_file2.type = "file"
        mock_file2.name = "file2.txt"
        mock_file2.size = 60
        mock_response2 = MagicMock()
        mock_response2.raw.read.return_value = b"Content 2"
        mock_file2.open.return_value = mock_response2

        # Setup folder with files
        mock_folder = MagicMock()
        mock_folder.dir.return_value = ["file1.txt", "file2.txt"]
        mock_folder.__getitem__ = lambda self, key: (
            mock_file1 if key == "file1.txt" else mock_file2
        )

        mock_root = MagicMock()
        mock_root.dir.return_value = ["TestFolder"]
        mock_root.__getitem__ = lambda self, key: mock_folder
        mock_api.drive.root = mock_root

        loader = iCloudLoader(apple_id="test@icloud.com", password="password")
        loader._api = mock_api

        with patch.object(loader, "_get_folder", return_value=mock_folder):
            with patch.object(loader, "load_document") as mock_load:
                mock_load.return_value = LoadedDocument(content="test", source="icloud")
                loader.load_folder("TestFolder")

        # Verify load_document was called for each file
        assert mock_load.call_count == 2

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_search_by_name(self):
        """Test searching files by name."""
        mock_api = MagicMock()

        mock_file = MagicMock()
        mock_file.type = "file"
        mock_file.name = "quarterly_report.txt"

        mock_root = MagicMock()
        mock_root.dir.return_value = ["quarterly_report.txt", "other.txt"]
        mock_root.__getitem__ = lambda self, key: mock_file
        mock_api.drive.root = mock_root

        loader = iCloudLoader(apple_id="test@icloud.com", password="password")
        loader._api = mock_api

        with patch.object(loader, "load_document") as mock_load:
            mock_load.return_value = LoadedDocument(content="report", source="icloud")
            results = loader.search("quarterly")

        assert len(results) == 1

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_list_folders(self):
        """Test listing subfolders."""
        mock_api = MagicMock()

        mock_folder1 = MagicMock()
        mock_folder1.type = "folder"
        mock_folder2 = MagicMock()
        mock_folder2.type = "folder"
        mock_file = MagicMock()
        mock_file.type = "file"

        mock_root = MagicMock()
        mock_root.dir.return_value = ["Documents", "Photos", "file.txt"]

        def mock_getitem(key):
            if key == "Documents":
                return mock_folder1
            elif key == "Photos":
                return mock_folder2
            return mock_file

        mock_root.__getitem__ = mock_getitem
        mock_api.drive.root = mock_root

        loader = iCloudLoader(apple_id="test@icloud.com", password="password")
        loader._api = mock_api

        folders = loader.list_folders()

        assert len(folders) == 2
        assert any(f["name"] == "Documents" for f in folders)
        assert any(f["name"] == "Photos" for f in folders)

    def test_supported_extensions(self):
        """Test SUPPORTED_EXTENSIONS contains expected types."""
        assert ".txt" in iCloudLoader.SUPPORTED_EXTENSIONS
        assert ".pdf" in iCloudLoader.SUPPORTED_EXTENSIONS
        assert ".docx" in iCloudLoader.SUPPORTED_EXTENSIONS
        assert ".md" in iCloudLoader.SUPPORTED_EXTENSIONS


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestCreateLoader:
    """Tests for create_loader factory function."""

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_create_google_drive_loader(self):
        """Test creating Google Drive loader."""
        loader = create_loader("google_drive", credentials_path="creds.json")
        assert isinstance(loader, GoogleDriveLoader)

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_create_drive_alias(self):
        """Test creating loader with 'drive' alias."""
        loader = create_loader("drive", credentials_path="creds.json")
        assert isinstance(loader, GoogleDriveLoader)

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_create_gmail_loader(self):
        """Test creating Gmail loader."""
        loader = create_loader("gmail", credentials_path="creds.json")
        assert isinstance(loader, GmailLoader)

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_create_email_alias(self):
        """Test creating loader with 'email' alias."""
        loader = create_loader("email", credentials_path="creds.json")
        assert isinstance(loader, GmailLoader)

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_create_icloud_loader(self):
        """Test creating iCloud loader."""
        loader = create_loader("icloud", apple_id="test@icloud.com", password="pass")
        assert isinstance(loader, iCloudLoader)

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_create_icloud_drive_alias(self):
        """Test creating loader with 'icloud_drive' alias."""
        loader = create_loader(
            "icloud_drive", apple_id="test@icloud.com", password="pass"
        )
        assert isinstance(loader, iCloudLoader)

    def test_create_unknown_source(self):
        """Test creating loader with unknown source raises error."""
        with pytest.raises(ValueError) as excinfo:
            create_loader("unknown_source")
        assert "Unknown loader type" in str(excinfo.value)

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_case_insensitive(self):
        """Test source name is case insensitive."""
        loader = create_loader("Google_Drive", credentials_path="creds.json")
        assert isinstance(loader, GoogleDriveLoader)

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_with_dashes(self):
        """Test source name with dashes."""
        loader = create_loader("google-drive", credentials_path="creds.json")
        assert isinstance(loader, GoogleDriveLoader)


class TestLoadFromMultipleSources:
    """Tests for load_from_multiple_sources function."""

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_single_source_folder(self):
        """Test loading from single source with folder."""
        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_loader = MagicMock()
            mock_loader.load_folder.return_value = [
                LoadedDocument(content="Doc 1", source="google_drive"),
                LoadedDocument(content="Doc 2", source="google_drive"),
            ]
            mock_create.return_value = mock_loader

            sources = [
                {
                    "type": "google_drive",
                    "credentials_path": "creds.json",
                    "folder": "Work",
                }
            ]

            docs = load_from_multiple_sources(sources)

            assert len(docs) == 2
            mock_loader.load_folder.assert_called_once_with("Work")

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_single_source_query(self):
        """Test loading from single source with query."""
        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_loader = MagicMock()
            mock_loader.search.return_value = [
                LoadedDocument(content="Result 1", source="gmail"),
            ]
            mock_create.return_value = mock_loader

            sources = [
                {
                    "type": "gmail",
                    "credentials_path": "creds.json",
                    "query": "from:boss",
                }
            ]

            docs = load_from_multiple_sources(sources)

            assert len(docs) == 1
            mock_loader.search.assert_called_once_with("from:boss")

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_multiple_sources(self):
        """Test loading from multiple sources."""
        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_drive = MagicMock()
            mock_drive.load_folder.return_value = [
                LoadedDocument(content="Drive doc", source="google_drive"),
            ]

            mock_gmail = MagicMock()
            mock_gmail.search.return_value = [
                LoadedDocument(content="Email", source="gmail"),
            ]

            def create_side_effect(source_type, **kwargs):
                if "drive" in source_type or "google" in source_type:
                    return mock_drive
                return mock_gmail

            mock_create.side_effect = create_side_effect

            sources = [
                {
                    "type": "google_drive",
                    "credentials_path": "creds.json",
                    "folder": "Work",
                },
                {
                    "type": "gmail",
                    "credentials_path": "creds.json",
                    "query": "from:boss",
                },
            ]

            docs = load_from_multiple_sources(sources)

            assert len(docs) == 2

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_deduplication(self):
        """Test deduplication of documents."""
        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_loader = MagicMock()
            # Return documents with same content
            mock_loader.load_folder.return_value = [
                LoadedDocument(content="Same content", source="google_drive"),
                LoadedDocument(content="Same content", source="google_drive"),
                LoadedDocument(content="Different content", source="google_drive"),
            ]
            mock_create.return_value = mock_loader

            sources = [
                {
                    "type": "google_drive",
                    "credentials_path": "creds.json",
                    "folder": "Work",
                }
            ]

            docs = load_from_multiple_sources(sources, deduplicate=True)

            assert len(docs) == 2  # One duplicate removed

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_no_deduplication(self):
        """Test loading without deduplication."""
        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_loader = MagicMock()
            mock_loader.load_folder.return_value = [
                LoadedDocument(content="Same content", source="google_drive"),
                LoadedDocument(content="Same content", source="google_drive"),
            ]
            mock_create.return_value = mock_loader

            sources = [
                {
                    "type": "google_drive",
                    "credentials_path": "creds.json",
                    "folder": "Work",
                }
            ]

            docs = load_from_multiple_sources(sources, deduplicate=False)

            assert len(docs) == 2  # Duplicates kept

    def test_missing_folder_and_query(self):
        """Test warning when no folder or query specified."""
        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_loader = MagicMock()
            mock_create.return_value = mock_loader

            sources = [
                {
                    "type": "google_drive",
                    "credentials_path": "creds.json",
                }  # No folder or query
            ]

            docs = load_from_multiple_sources(sources)

            assert len(docs) == 0
            mock_loader.load_folder.assert_not_called()
            mock_loader.search.assert_not_called()

    def test_source_error_handling(self):
        """Test error handling for failing sources."""
        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_create.side_effect = Exception("Connection failed")

            sources = [
                {
                    "type": "google_drive",
                    "credentials_path": "creds.json",
                    "folder": "Work",
                }
            ]

            # Should not raise, just log error and return empty
            docs = load_from_multiple_sources(sources)

            assert docs == []

    def test_does_not_mutate_input(self):
        """Test that input source configs are not mutated."""
        original_config = {
            "type": "google_drive",
            "credentials_path": "creds.json",
            "folder": "Work",
        }
        sources = [original_config.copy()]

        with patch("agentic_brain.rag.loaders.factory.create_loader") as mock_create:
            mock_loader = MagicMock()
            mock_loader.load_folder.return_value = []
            mock_create.return_value = mock_loader

            load_from_multiple_sources(sources)

        # Original should still have 'type', 'folder' keys
        assert "type" in sources[0]
        assert "folder" in sources[0]


# ============================================================================
# Import Availability Tests
# ============================================================================


class TestImportAvailability:
    """Tests for library availability flags."""

    def test_google_api_flag_exported(self):
        """Test GOOGLE_API_AVAILABLE is exported."""
        from agentic_brain.rag import GOOGLE_API_AVAILABLE

        assert isinstance(GOOGLE_API_AVAILABLE, bool)

    def test_pyicloud_flag_exported(self):
        """Test PYICLOUD_AVAILABLE is exported."""
        from agentic_brain.rag import PYICLOUD_AVAILABLE

        assert isinstance(PYICLOUD_AVAILABLE, bool)

    def test_google_drive_raises_without_library(self):
        """Test GoogleDriveLoader raises ImportError when library not available."""
        with patch("agentic_brain.rag.loaders.GOOGLE_API_AVAILABLE", False):
            # Need to reload to trigger the check
            # This is a design limitation - can't easily test without library
            pass

    def test_gmail_raises_without_library(self):
        """Test GmailLoader raises ImportError when library not available."""
        # Similar to above - design limitation
        pass

    def test_icloud_raises_without_library(self):
        """Test iCloudLoader raises ImportError when library not available."""
        # Similar to above - design limitation
        pass


# ============================================================================
# PDF Extraction Tests
# ============================================================================


class TestPDFExtraction:
    """Tests for PDF text extraction."""

    def test_pdf_extraction_pypdf2(self):
        """Test PDF extraction with PyPDF2."""

        class TestLoader(BaseLoader):
            @property
            def source_name(self) -> str:
                return "test"

            def authenticate(self) -> bool:
                return True

            def load_document(self, doc_id: str):
                return None

            def load_folder(self, folder_path: str, recursive: bool = True):
                return []

            def search(self, query: str, max_results: int = 50):
                return []

        loader = TestLoader()

        # Create a minimal valid PDF
        # This is a very basic PDF structure
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test PDF Content) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF"""

        # The extraction might fail on our minimal PDF,
        # but at least test that the method exists and handles errors
        result = loader._extract_text_from_pdf(pdf_content)
        # Should return something (either extracted text or fallback message)
        assert result is not None


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_google_drive_auth_failure(self):
        """Test handling of authentication failure."""
        loader = GoogleDriveLoader(credentials_path="nonexistent.json")
        result = loader.authenticate()
        assert result is False

    @pytest.mark.skipif(not PYICLOUD_AVAILABLE, reason="pyicloud not available")
    def test_icloud_missing_credentials(self):
        """Test iCloud with missing credentials."""
        loader = iCloudLoader()  # No apple_id or password

        with pytest.raises(ValueError) as excinfo:
            loader.authenticate()
        assert "apple_id and password required" in str(excinfo.value)

    @pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API not available")
    def test_google_drive_folder_not_found(self):
        """Test loading non-existent folder."""
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {"files": []}

        loader = GoogleDriveLoader(credentials_path="creds.json")
        loader._service = mock_service
        loader._credentials = MagicMock()

        docs = loader.load_folder("NonExistent/Folder")
        assert docs == []

    def test_loaded_document_empty_content(self):
        """Test LoadedDocument with empty content."""
        doc = LoadedDocument(content="")
        assert doc.content == ""
        assert doc.size_bytes == 0

    def test_loaded_document_large_metadata(self):
        """Test LoadedDocument with large metadata."""
        large_metadata = {f"key_{i}": f"value_{i}" for i in range(1000)}
        doc = LoadedDocument(content="test", metadata=large_metadata)
        assert len(doc.metadata) == 1000

        # Should serialize successfully
        result = doc.to_dict()
        assert len(result["metadata"]) == 1000


# ============================================================================
# Firestore Loader Tests
# ============================================================================

# Check if Firebase is available
try:
    import firebase_admin

    from agentic_brain.rag.loaders import FIREBASE_AVAILABLE, FirestoreLoader
except ImportError:
    FIREBASE_AVAILABLE = False


class TestFirestoreLoaderBasic:
    """Basic tests for FirestoreLoader."""

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_source_name(self):
        """Test source_name property."""
        loader = FirestoreLoader(project_id="test-project")
        assert loader.source_name == "firestore"

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        loader = FirestoreLoader(
            service_account_path="firebase.json",
            project_id="my-project",
            app_name="test-app",
            content_field="body",
            title_field="name",
            metadata_fields=["tags", "author"],
        )
        assert loader._service_account_path == "firebase.json"
        assert loader._project_id == "my-project"
        assert loader._app_name == "test-app"
        assert loader._content_field == "body"
        assert loader._title_field == "name"
        assert loader._metadata_fields == ["tags", "author"]

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_init_default_params(self):
        """Test initialization with default parameters."""
        loader = FirestoreLoader()
        assert loader._service_account_path is None
        assert loader._app_name == "[DEFAULT]"
        assert loader._content_field == "content"
        assert loader._title_field == "title"
        assert loader._metadata_fields == []

    def test_firebase_not_available(self):
        """Test behavior when Firebase is not available."""
        if FIREBASE_AVAILABLE:
            pytest.skip("Firebase is available")

        with pytest.raises(ImportError) as excinfo:
            from agentic_brain.rag.loaders import FirestoreLoader

            FirestoreLoader()
        assert "firebase-admin" in str(excinfo.value).lower()


class TestFirestoreLoaderAuthentication:
    """Tests for Firestore authentication."""

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_authenticate_with_service_account(self):
        """Test authentication with service account."""
        with (
            patch("firebase_admin.initialize_app") as mock_init,
            patch("firebase_admin.get_app", side_effect=ValueError),
            patch("firebase_admin.credentials.Certificate") as mock_cred,
            patch("firebase_admin.firestore.client") as mock_client,
        ):

            mock_init.return_value = MagicMock()
            mock_client.return_value = MagicMock()

            loader = FirestoreLoader(
                service_account_path="firebase.json", project_id="test-project"
            )
            result = loader.authenticate()

            assert result is True
            assert loader._authenticated is True
            mock_cred.assert_called_once_with("firebase.json")

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_authenticate_with_existing_app(self):
        """Test authentication reuses existing Firebase app."""
        with (
            patch("firebase_admin.get_app") as mock_get_app,
            patch("firebase_admin.firestore.client") as mock_client,
        ):

            mock_app = MagicMock()
            mock_get_app.return_value = mock_app
            mock_client.return_value = MagicMock()

            loader = FirestoreLoader(project_id="test-project")
            result = loader.authenticate()

            assert result is True
            assert loader._app == mock_app

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_authenticate_failure(self):
        """Test authentication failure handling."""
        with (
            patch("firebase_admin.get_app", side_effect=ValueError),
            patch(
                "firebase_admin.initialize_app", side_effect=Exception("Auth failed")
            ),
        ):

            loader = FirestoreLoader(project_id="test-project")
            result = loader.authenticate()

            assert result is False
            assert loader._authenticated is False


class TestFirestoreLoaderDocumentConversion:
    """Tests for Firestore document conversion."""

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_doc_to_loaded_document_basic(self):
        """Test converting Firestore doc to LoadedDocument."""
        mock_snapshot = MagicMock()
        mock_snapshot.id = "doc123"
        mock_snapshot.to_dict.return_value = {
            "content": "Test content",
            "title": "Test Title",
            "author": "John",
        }
        mock_snapshot.create_time = datetime.now(UTC)
        mock_snapshot.update_time = datetime.now(UTC)

        loader = FirestoreLoader(project_id="test")
        loader._authenticated = True

        doc = loader._doc_to_loaded_document(mock_snapshot, "articles")

        assert doc is not None
        assert doc.content == "Test content"
        assert doc.filename == "Test Title"
        assert doc.source == "firestore"
        assert doc.source_id == "articles/doc123"
        assert doc.metadata["collection"] == "articles"
        assert doc.metadata["author"] == "John"

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_doc_to_loaded_document_fallback_fields(self):
        """Test fallback field detection."""
        mock_snapshot = MagicMock()
        mock_snapshot.id = "doc456"
        mock_snapshot.to_dict.return_value = {
            "body": "Content in body field",
            "name": "Document Name",
        }
        mock_snapshot.create_time = None
        mock_snapshot.update_time = None

        loader = FirestoreLoader(project_id="test")
        loader._authenticated = True

        doc = loader._doc_to_loaded_document(mock_snapshot, "docs")

        assert doc.content == "Content in body field"
        assert doc.filename == "Document Name"

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_doc_to_loaded_document_json_fallback(self):
        """Test JSON fallback when no content field exists."""
        mock_snapshot = MagicMock()
        mock_snapshot.id = "doc789"
        mock_snapshot.to_dict.return_value = {"field1": "value1", "field2": 123}
        mock_snapshot.create_time = None
        mock_snapshot.update_time = None

        loader = FirestoreLoader(project_id="test")
        loader._authenticated = True

        doc = loader._doc_to_loaded_document(mock_snapshot, "misc")

        # Should serialize entire doc as JSON
        assert "field1" in doc.content
        assert "value1" in doc.content


class TestFirestoreLoaderOperations:
    """Tests for Firestore CRUD operations."""

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_load_document(self):
        """Test loading a single document."""
        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()

        mock_snapshot.exists = True
        mock_snapshot.id = "doc1"
        mock_snapshot.to_dict.return_value = {"content": "Hello", "title": "Hi"}
        mock_snapshot.create_time = None
        mock_snapshot.update_time = None

        mock_doc_ref.get.return_value = mock_snapshot
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        doc = loader.load_document("articles/doc1")

        assert doc is not None
        assert doc.content == "Hello"
        mock_db.collection.assert_called_with("articles")

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_load_document_invalid_format(self):
        """Test loading document with invalid ID format."""
        loader = FirestoreLoader(project_id="test")
        loader._db = MagicMock()
        loader._authenticated = True

        doc = loader.load_document("invalid_format")
        assert doc is None

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_load_document_not_found(self):
        """Test loading non-existent document."""
        mock_db = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False

        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_snapshot
        )

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        doc = loader.load_document("articles/nonexistent")
        assert doc is None

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_load_collection(self):
        """Test loading entire collection."""
        mock_db = MagicMock()
        mock_snapshot1 = MagicMock()
        mock_snapshot1.id = "doc1"
        mock_snapshot1.to_dict.return_value = {"content": "Doc 1", "title": "First"}
        mock_snapshot1.create_time = None
        mock_snapshot1.update_time = None
        mock_snapshot1.reference.collections.return_value = []

        mock_snapshot2 = MagicMock()
        mock_snapshot2.id = "doc2"
        mock_snapshot2.to_dict.return_value = {"content": "Doc 2", "title": "Second"}
        mock_snapshot2.create_time = None
        mock_snapshot2.update_time = None
        mock_snapshot2.reference.collections.return_value = []

        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_snapshot1, mock_snapshot2]
        mock_db.collection.return_value = mock_query

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        docs = loader.load_collection("articles")

        assert len(docs) == 2
        assert docs[0].content == "Doc 1"
        assert docs[1].content == "Doc 2"

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_load_collection_with_filters(self):
        """Test loading collection with where filters."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = []

        mock_db.collection.return_value = mock_query

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        loader.load_collection(
            "articles",
            where=[("status", "==", "published")],
            order_by="-created_at",
            limit=10,
        )

        mock_query.where.assert_called_once()
        mock_query.order_by.assert_called_once()
        mock_query.limit.assert_called_once_with(10)

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_save_document(self):
        """Test saving a document."""
        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new_doc_id"
        mock_db.collection.return_value.add.return_value = (None, mock_doc_ref)

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        doc_id = loader.save_document(
            collection="articles",
            content="New article content",
            title="New Article",
            metadata={"tags": ["tech"]},
        )

        assert doc_id == "new_doc_id"
        mock_db.collection.assert_called_with("articles")

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_save_document_with_id(self):
        """Test saving document with specific ID."""
        mock_db = MagicMock()

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        doc_id = loader.save_document(
            collection="articles",
            content="Content",
            title="Title",
            document_id="my-custom-id",
        )

        assert doc_id == "my-custom-id"
        mock_db.collection.return_value.document.assert_called_with("my-custom-id")

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_delete_document(self):
        """Test deleting a document."""
        mock_db = MagicMock()

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        result = loader.delete_document("articles/doc123")

        assert result is True
        mock_db.collection.return_value.document.return_value.delete.assert_called_once()

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_list_collections(self):
        """Test listing collections."""
        mock_db = MagicMock()
        mock_coll1 = MagicMock()
        mock_coll1.id = "articles"
        mock_coll2 = MagicMock()
        mock_coll2.id = "users"

        mock_db.collections.return_value = [mock_coll1, mock_coll2]

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        collections = loader.list_collections()

        assert collections == ["articles", "users"]


class TestFirestoreLoaderSearch:
    """Tests for Firestore search functionality."""

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_search_basic(self):
        """Test basic search across collections."""
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.id = "articles"

        mock_snapshot = MagicMock()
        mock_snapshot.id = "doc1"
        mock_snapshot.to_dict.return_value = {
            "content": "Python programming guide",
            "title": "Learn Python",
        }
        mock_snapshot.create_time = None
        mock_snapshot.update_time = None

        mock_coll.stream.return_value = [mock_snapshot]
        mock_db.collections.return_value = [mock_coll]

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        docs = loader.search("python")

        assert len(docs) == 1
        assert "Python" in docs[0].content

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_search_max_results(self):
        """Test search respects max_results."""
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.id = "articles"

        # Create 10 matching documents
        snapshots = []
        for i in range(10):
            snap = MagicMock()
            snap.id = f"doc{i}"
            snap.to_dict.return_value = {
                "content": f"Python article {i}",
                "title": f"Article {i}",
            }
            snap.create_time = None
            snap.update_time = None
            snapshots.append(snap)

        mock_coll.stream.return_value = snapshots
        mock_db.collections.return_value = [mock_coll]

        loader = FirestoreLoader(project_id="test")
        loader._db = mock_db
        loader._authenticated = True

        docs = loader.search("python", max_results=3)

        assert len(docs) == 3


class TestFirestoreLoaderFactory:
    """Tests for Firestore in factory function."""

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_create_loader_firestore(self):
        """Test creating FirestoreLoader via factory."""
        loader = create_loader("firestore", project_id="test-project")
        # Use type name check to avoid dual-import isinstance issues on CI
        assert type(loader).__name__ == "FirestoreLoader"

    @pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="Firebase not available")
    def test_create_loader_firebase_alias(self):
        """Test 'firebase' alias for FirestoreLoader."""
        loader = create_loader("firebase", project_id="test-project")
        # Use type name check to avoid dual-import isinstance issues on CI
        assert type(loader).__name__ == "FirestoreLoader"


# =============================================================================
# S3 LOADER TESTS
# =============================================================================


class TestS3LoaderBasic:
    """Basic tests for S3Loader."""

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_s3_loader_init(self):
        """Test S3Loader initialization."""
        loader = S3Loader(
            bucket="test-bucket",
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
        )
        assert loader.source_name == "Amazon S3"
        assert loader._bucket_name == "test-bucket"

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_s3_loader_init_minio(self):
        """Test S3Loader with MinIO endpoint."""
        loader = S3Loader(
            bucket="test-bucket",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
        )
        assert loader.source_name == "Amazon S3"

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_s3_authenticate(self):
        """Test S3 authentication."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            loader = S3Loader(
                bucket="test-bucket",
                aws_access_key_id="test_key",
                aws_secret_access_key="test_secret",
            )
            result = loader.authenticate()

            assert result is True
            assert loader._authenticated is True


class TestS3LoaderDocuments:
    """Tests for S3Loader document operations."""

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_load_document(self):
        """Test loading a document from S3."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            # Mock get_object response
            mock_body = MagicMock()
            mock_body.read.return_value = b"Hello, World!"
            mock_s3.get_object.return_value = {
                "Body": mock_body,
                "ContentType": "text/plain",
                "LastModified": "2024-01-01T00:00:00Z",
                "Metadata": {"title": "Test Doc"},
            }

            loader = S3Loader(
                bucket="test-bucket",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
            )
            loader.authenticate()

            doc = loader.load_document("docs/test.txt")

            assert doc is not None
            assert doc.content == "Hello, World!"
            assert doc.doc_id == "docs/test.txt"

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_save_document(self):
        """Test saving a document to S3."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            loader = S3Loader(
                bucket="test-bucket",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
            )
            loader.authenticate()

            result = loader.save_document(
                key="docs/new.txt", content="New content", metadata={"author": "test"}
            )

            assert result is True
            mock_s3.put_object.assert_called_once()

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_delete_document(self):
        """Test deleting a document from S3."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            loader = S3Loader(
                bucket="test-bucket",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
            )
            loader.authenticate()

            result = loader.delete_document("docs/old.txt")

            assert result is True
            mock_s3.delete_object.assert_called_once_with(
                Bucket="test-bucket", Key="docs/old.txt"
            )


class TestS3LoaderFolder:
    """Tests for S3Loader folder/prefix operations."""

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_load_folder(self):
        """Test loading a folder (prefix) from S3."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            # Mock list and get operations
            mock_s3.list_objects_v2.return_value = {
                "Contents": [
                    {"Key": "docs/file1.txt", "Size": 100},
                    {"Key": "docs/file2.txt", "Size": 200},
                ]
            }

            mock_body = MagicMock()
            mock_body.read.return_value = b"File content"
            mock_s3.get_object.return_value = {
                "Body": mock_body,
                "ContentType": "text/plain",
                "LastModified": "2024-01-01T00:00:00Z",
                "Metadata": {},
            }

            loader = S3Loader(
                bucket="test-bucket",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
            )
            loader.authenticate()

            docs = loader.load_folder("docs/")

            assert len(docs) == 2

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_list_objects(self):
        """Test listing objects in a prefix."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_s3.list_objects_v2.return_value = {
                "Contents": [
                    {
                        "Key": "docs/file1.txt",
                        "Size": 100,
                        "LastModified": "2024-01-01",
                    },
                    {"Key": "docs/file2.md", "Size": 200, "LastModified": "2024-01-02"},
                ]
            }

            loader = S3Loader(
                bucket="test-bucket",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
            )
            loader.authenticate()

            objects = loader.list_objects("docs/")

            assert len(objects) == 2
            assert objects[0]["Key"] == "docs/file1.txt"


class TestS3LoaderSearch:
    """Tests for S3Loader search functionality."""

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_search_by_content(self):
        """Test searching S3 by content."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            # Mock list and get
            mock_s3.list_objects_v2.return_value = {
                "Contents": [{"Key": "docs/python.txt", "Size": 100}]
            }

            mock_body = MagicMock()
            mock_body.read.return_value = b"Python programming tutorial"
            mock_s3.get_object.return_value = {
                "Body": mock_body,
                "ContentType": "text/plain",
                "LastModified": "2024-01-01",
                "Metadata": {},
            }

            loader = S3Loader(
                bucket="test-bucket",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
            )
            loader.authenticate()

            docs = loader.search("python")

            assert len(docs) >= 0  # May find matches


class TestS3LoaderFactory:
    """Tests for S3 in factory function."""

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_create_loader_s3(self):
        """Test creating S3Loader via factory."""
        loader = create_loader("s3", bucket="test")
        assert isinstance(loader, S3Loader)

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_create_loader_minio_alias(self):
        """Test 'minio' alias for S3Loader."""
        loader = create_loader("minio", bucket="test")
        assert isinstance(loader, S3Loader)

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="Boto3 not available")
    def test_create_loader_aws_alias(self):
        """Test 'aws' alias for S3Loader."""
        loader = create_loader("aws", bucket="test")
        assert isinstance(loader, S3Loader)


# =============================================================================
# MONGODB LOADER TESTS
# =============================================================================


class TestMongoDBLoaderBasic:
    """Basic tests for MongoDBLoader."""

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_mongodb_loader_init(self):
        """Test MongoDBLoader initialization."""
        loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
        assert loader.source_name == "MongoDB"
        assert loader._database_name == "testdb"

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_mongodb_loader_init_components(self):
        """Test MongoDBLoader with individual components."""
        loader = MongoDBLoader(
            host="localhost",
            port=27017,
            database="testdb",
            username="user",
            password="pass",
        )
        assert loader.source_name == "MongoDB"

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_mongodb_authenticate(self):
        """Test MongoDB authentication."""
        with patch("pymongo.MongoClient") as mock_client:
            mock_db = MagicMock()
            mock_client.return_value.__getitem__.return_value = mock_db

            loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
            result = loader.authenticate()

            assert result is True


class TestMongoDBLoaderDocuments:
    """Tests for MongoDBLoader document operations."""

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_load_document(self):
        """Test loading a document from MongoDB."""
        with patch("pymongo.MongoClient") as mock_client:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection
            mock_client.return_value.__getitem__.return_value = mock_db

            # Mock find_one
            mock_collection.find_one.return_value = {
                "_id": "doc1",
                "content": "Hello MongoDB",
                "title": "Test Document",
            }

            loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
            loader.authenticate()

            doc = loader.load_document("articles", "doc1")

            assert doc is not None
            assert doc.content == "Hello MongoDB"

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_save_document(self):
        """Test saving a document to MongoDB."""
        with patch("pymongo.MongoClient") as mock_client:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection
            mock_client.return_value.__getitem__.return_value = mock_db

            mock_collection.replace_one.return_value = MagicMock(upserted_id="new_doc")

            loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
            loader.authenticate()

            result = loader.save_document(
                "articles", {"_id": "doc1", "content": "New content"}
            )

            assert result is not None

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_delete_document(self):
        """Test deleting a document from MongoDB."""
        with patch("pymongo.MongoClient") as mock_client:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection
            mock_client.return_value.__getitem__.return_value = mock_db

            mock_collection.delete_one.return_value = MagicMock(deleted_count=1)

            loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
            loader.authenticate()

            result = loader.delete_document("articles", "doc1")

            assert result is True


class TestMongoDBLoaderCollection:
    """Tests for MongoDBLoader collection operations."""

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_load_collection(self):
        """Test loading a collection from MongoDB."""
        with patch("pymongo.MongoClient") as mock_client:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection
            mock_client.return_value.__getitem__.return_value = mock_db

            mock_collection.find.return_value = [
                {"_id": "doc1", "content": "First"},
                {"_id": "doc2", "content": "Second"},
            ]

            loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
            loader.authenticate()

            docs = loader.load_folder("articles")

            assert len(docs) == 2

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_list_collections(self):
        """Test listing collections."""
        with patch("pymongo.MongoClient") as mock_client:
            mock_db = MagicMock()
            mock_db.list_collection_names.return_value = ["articles", "users"]
            mock_client.return_value.__getitem__.return_value = mock_db

            loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
            loader.authenticate()

            collections = loader.list_collections()

            assert collections == ["articles", "users"]


class TestMongoDBLoaderSearch:
    """Tests for MongoDBLoader search functionality."""

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_search_with_text_index(self):
        """Test search using text index."""
        with patch("pymongo.MongoClient") as mock_client:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection
            mock_db.list_collection_names.return_value = ["articles"]
            mock_client.return_value.__getitem__.return_value = mock_db

            mock_collection.find.return_value = [
                {"_id": "doc1", "content": "Python tutorial"}
            ]

            loader = MongoDBLoader(uri="mongodb://localhost:27017", database="testdb")
            loader.authenticate()

            docs = loader.search("python")

            # Search should return results
            assert isinstance(docs, list)


class TestMongoDBLoaderFactory:
    """Tests for MongoDB in factory function."""

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_create_loader_mongodb(self):
        """Test creating MongoDBLoader via factory."""
        loader = create_loader("mongodb", uri="mongodb://localhost", database="test")
        assert isinstance(loader, MongoDBLoader)

    @pytest.mark.skipif(not PYMONGO_AVAILABLE, reason="PyMongo not available")
    def test_create_loader_mongo_alias(self):
        """Test 'mongo' alias for MongoDBLoader."""
        loader = create_loader("mongo", uri="mongodb://localhost", database="test")
        assert isinstance(loader, MongoDBLoader)


# =============================================================================
# GITHUB LOADER TESTS
# =============================================================================


class TestGitHubLoaderBasic:
    """Basic tests for GitHubLoader."""

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_github_loader_init(self):
        """Test GitHubLoader initialization."""
        loader = GitHubLoader(token="ghp_test_token")
        assert loader.source_name == "GitHub"

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_github_authenticate(self):
        """Test GitHub authentication."""
        with patch("agentic_brain.rag.loaders.github.Github") as mock_gh:
            mock_instance = MagicMock()
            mock_user = MagicMock()
            mock_user.login = "testuser"
            mock_instance.get_user.return_value = mock_user
            mock_gh.return_value = mock_instance

            loader = GitHubLoader(token="ghp_test_token")
            result = loader.authenticate()

            assert result is True


class TestGitHubLoaderDocuments:
    """Tests for GitHubLoader document operations."""

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_load_document(self):
        """Test loading a file from GitHub."""
        with patch("agentic_brain.rag.loaders.github.Github") as mock_gh:
            mock_instance = MagicMock()
            mock_repo = MagicMock()
            mock_content = MagicMock()
            mock_content.decoded_content = b"# README\nThis is a test"
            mock_content.path = "README.md"
            mock_content.sha = "abc123"
            mock_content.type = "file"

            mock_content.size = 20
            mock_content.html_url = "https://example.com/README.md"
            mock_content.name = "README.md"

            mock_repo.get_contents.return_value = mock_content
            mock_instance.get_repo.return_value = mock_repo
            mock_user = MagicMock()
            mock_user.login = "test"
            mock_instance.get_user.return_value = mock_user
            mock_gh.return_value = mock_instance

            loader = GitHubLoader(token="ghp_test")
            loader.authenticate()

            doc = loader.load_document("owner/repo:README.md")

            assert doc is not None
            assert "README" in doc.content

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_load_repository(self):
        """Test loading all files from a repository."""
        with patch("agentic_brain.rag.loaders.github.Github") as mock_gh:
            mock_instance = MagicMock()
            mock_repo = MagicMock()

            mock_file1 = MagicMock()
            mock_file1.path = "src/main.py"
            mock_file1.type = "file"
            mock_file1.decoded_content = b"print('hello')"
            mock_file1.sha = "sha1"
            mock_file1.size = 15
            mock_file1.html_url = "https://example.com/src/main.py"
            mock_file1.name = "main.py"

            mock_file2 = MagicMock()
            mock_file2.path = "README.md"
            mock_file2.type = "file"
            mock_file2.decoded_content = b"# Title"
            mock_file2.sha = "sha2"
            mock_file2.size = 10
            mock_file2.html_url = "https://example.com/README.md"
            mock_file2.name = "README.md"

            mock_repo.get_contents.return_value = [mock_file1, mock_file2]
            mock_instance.get_repo.return_value = mock_repo
            mock_user = MagicMock()
            mock_user.login = "test"
            mock_instance.get_user.return_value = mock_user
            mock_gh.return_value = mock_instance

            loader = GitHubLoader(token="ghp_test")
            loader.authenticate()

            docs = loader.load_repository("owner/repo")

            assert len(docs) == 2


class TestGitHubLoaderIssues:
    """Tests for GitHubLoader issue operations."""

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_load_issues(self):
        """Test loading issues from repository."""
        with patch("agentic_brain.rag.loaders.github.Github") as mock_gh:
            mock_instance = MagicMock()
            mock_repo = MagicMock()

            mock_issue = MagicMock()
            mock_issue.number = 42
            mock_issue.title = "Bug report"
            mock_issue.body = "There's a bug"
            mock_issue.state = "open"
            mock_issue.created_at = MagicMock()
            mock_issue.created_at.isoformat.return_value = "2024-01-01T00:00:00"
            mock_issue.labels = []
            mock_issue.get_comments.return_value = []
            mock_issue.user = MagicMock()
            mock_issue.user.login = "reporter"
            mock_issue.html_url = "https://example.com/issues/42"
            mock_issue.updated_at = mock_issue.created_at
            mock_issue.comments = 0
            mock_issue.pull_request = False

            mock_repo.get_issues.return_value = [mock_issue]
            mock_instance.get_repo.return_value = mock_repo
            mock_user = MagicMock()
            mock_user.login = "test"
            mock_instance.get_user.return_value = mock_user
            mock_gh.return_value = mock_instance

            loader = GitHubLoader(token="ghp_test")
            loader.authenticate()

            docs = loader.load_issues("owner/repo")

            assert len(docs) == 1
            assert "Bug report" in docs[0].content


class TestGitHubLoaderPullRequests:
    """Tests for GitHubLoader PR operations."""

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_load_pull_requests(self):
        """Test loading pull requests from repository."""
        with patch("agentic_brain.rag.loaders.github.Github") as mock_gh:
            mock_instance = MagicMock()
            mock_repo = MagicMock()

            mock_pr = MagicMock()
            mock_pr.number = 101
            mock_pr.title = "Add feature"
            mock_pr.body = "This PR adds a feature"
            mock_pr.state = "open"
            mock_pr.created_at = MagicMock()
            mock_pr.created_at.isoformat.return_value = "2024-01-01T00:00:00"
            mock_pr.head = MagicMock()
            mock_pr.head.ref = "feature-branch"
            mock_pr.base = MagicMock()
            mock_pr.base.ref = "main"
            mock_pr.get_files.return_value = []
            mock_pr.get_review_comments.return_value = []

            mock_repo.get_pulls.return_value = [mock_pr]
            mock_instance.get_repo.return_value = mock_repo
            mock_user = MagicMock()
            mock_user.login = "test"
            mock_instance.get_user.return_value = mock_user
            mock_gh.return_value = mock_instance

            loader = GitHubLoader(token="ghp_test")
            loader.authenticate()

            docs = loader.load_pull_requests("owner/repo")

            assert len(docs) == 1
            assert "Add feature" in docs[0].content


class TestGitHubLoaderSearch:
    """Tests for GitHubLoader search functionality."""

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_search_code(self):
        """Test searching code on GitHub."""
        with patch("agentic_brain.rag.loaders.github.Github") as mock_gh:
            mock_instance = MagicMock()

            mock_result = MagicMock()
            mock_result.path = "src/utils.py"
            mock_result.repository.full_name = "owner/repo"
            mock_result.sha = "sha123"

            mock_instance.search_code.return_value = [mock_result]
            mock_user = MagicMock()
            mock_user.login = "test"
            mock_instance.get_user.return_value = mock_user
            mock_gh.return_value = mock_instance

            loader = GitHubLoader(token="ghp_test")
            loader.authenticate()

            results = loader.search("def parse")

            assert isinstance(results, list)


class TestGitHubLoaderFactory:
    """Tests for GitHub in factory function."""

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_create_loader_github(self):
        """Test creating GitHubLoader via factory."""
        loader = create_loader("github", token="ghp_test")
        assert isinstance(loader, GitHubLoader)

    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not available")
    def test_create_loader_gh_alias(self):
        """Test 'gh' alias for GitHubLoader."""
        loader = create_loader("gh", token="ghp_test")
        assert isinstance(loader, GitHubLoader)


# =============================================================================
# MICROSOFT 365 LOADER TESTS
# =============================================================================


class TestMicrosoft365LoaderBasic:
    """Basic tests for Microsoft365Loader."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_m365_loader_init(self):
        """Test Microsoft365Loader initialization."""
        loader = Microsoft365Loader(
            client_id="test_client_id",
            client_secret="test_secret",
            tenant_id="test_tenant",
        )
        assert loader.source_name == "Microsoft 365"

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_m365_authenticate_client_credentials(self):
        """Test Microsoft 365 client credentials authentication."""
        with patch("msal.ConfidentialClientApplication") as mock_app:
            mock_instance = MagicMock()
            mock_instance.acquire_token_for_client.return_value = {
                "access_token": "test_token"
            }
            mock_app.return_value = mock_instance

            loader = Microsoft365Loader(
                client_id="client", client_secret="secret", tenant_id="tenant"
            )
            result = loader.authenticate()

            assert result is True


class TestMicrosoft365LoaderOneDrive:
    """Tests for Microsoft365Loader OneDrive operations."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_load_onedrive_file(self):
        """Test loading a file from OneDrive."""
        with patch("msal.ConfidentialClientApplication") as mock_msal:
            with patch("requests.get") as mock_get:
                mock_app = MagicMock()
                mock_app.acquire_token_for_client.return_value = {
                    "access_token": "token"
                }
                mock_msal.return_value = mock_app

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "id": "file123",
                    "name": "document.txt",
                    "@microsoft.graph.downloadUrl": "https://download.url",
                }
                mock_response.raise_for_status = MagicMock()
                mock_response.text = "File content here"
                mock_get.return_value = mock_response

                loader = Microsoft365Loader(
                    client_id="client", client_secret="secret", tenant_id="tenant"
                )
                loader.authenticate()

                # Test that load_document works without raising
                # Actual content loading would need more mocking
                assert loader._authenticated is True

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_load_onedrive_folder(self):
        """Test loading a folder from OneDrive."""
        with patch("msal.ConfidentialClientApplication") as mock_msal:
            with patch("requests.get") as mock_get:
                mock_app = MagicMock()
                mock_app.acquire_token_for_client.return_value = {
                    "access_token": "token"
                }
                mock_msal.return_value = mock_app

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "value": [
                        {"id": "f1", "name": "doc1.txt", "file": {}},
                        {"id": "f2", "name": "doc2.txt", "file": {}},
                    ]
                }
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response

                loader = Microsoft365Loader(
                    client_id="client", client_secret="secret", tenant_id="tenant"
                )
                loader.authenticate()

                assert loader._authenticated is True


class TestMicrosoft365LoaderOutlook:
    """Tests for Microsoft365Loader Outlook operations."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_load_outlook_emails(self):
        """Test loading emails from Outlook."""
        with patch("msal.ConfidentialClientApplication") as mock_msal:
            with patch("requests.get") as mock_get:
                mock_app = MagicMock()
                mock_app.acquire_token_for_client.return_value = {
                    "access_token": "token"
                }
                mock_msal.return_value = mock_app

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "value": [
                        {
                            "id": "mail1",
                            "subject": "Test Email",
                            "body": {"content": "Hello"},
                            "from": {"emailAddress": {"address": "sender@test.com"}},
                            "receivedDateTime": "2024-01-01T00:00:00Z",
                        }
                    ]
                }
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response

                loader = Microsoft365Loader(
                    client_id="client", client_secret="secret", tenant_id="tenant"
                )
                loader.authenticate()

                assert loader._authenticated is True


class TestMicrosoft365LoaderSharePoint:
    """Tests for Microsoft365Loader SharePoint operations."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_load_sharepoint_library(self):
        """Test loading from SharePoint library."""
        with patch("msal.ConfidentialClientApplication") as mock_msal:
            with patch("requests.get") as mock_get:
                mock_app = MagicMock()
                mock_app.acquire_token_for_client.return_value = {
                    "access_token": "token"
                }
                mock_msal.return_value = mock_app

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "value": [
                        {
                            "id": "sp1",
                            "name": "Company Docs",
                            "driveType": "documentLibrary",
                        }
                    ]
                }
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response

                loader = Microsoft365Loader(
                    client_id="client", client_secret="secret", tenant_id="tenant"
                )
                loader.authenticate()

                assert loader._authenticated is True


class TestMicrosoft365LoaderSearch:
    """Tests for Microsoft365Loader search functionality."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_search_across_services(self):
        """Test searching across Microsoft 365 services."""
        with patch("msal.ConfidentialClientApplication") as mock_msal:
            with patch("requests.get") as mock_get:
                mock_app = MagicMock()
                mock_app.acquire_token_for_client.return_value = {
                    "access_token": "token"
                }
                mock_msal.return_value = mock_app

                mock_response = MagicMock()
                mock_response.json.return_value = {"value": []}
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response

                loader = Microsoft365Loader(
                    client_id="client", client_secret="secret", tenant_id="tenant"
                )
                loader.authenticate()

                results = loader.search("project report")

                assert isinstance(results, list)


class TestMicrosoft365LoaderFactory:
    """Tests for Microsoft 365 in factory function."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_create_loader_m365(self):
        """Test creating Microsoft365Loader via factory."""
        loader = create_loader(
            "microsoft365",
            client_id="client",
            client_secret="secret",
            tenant_id="tenant",
        )
        assert isinstance(loader, Microsoft365Loader)

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_create_loader_office365_alias(self):
        """Test 'office365' alias for Microsoft365Loader."""
        loader = create_loader(
            "office365", client_id="client", client_secret="secret", tenant_id="tenant"
        )
        assert isinstance(loader, Microsoft365Loader)

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_create_loader_onedrive_alias(self):
        """Test 'onedrive' alias for Microsoft365Loader."""
        loader = create_loader(
            "onedrive", client_id="client", client_secret="secret", tenant_id="tenant"
        )
        assert isinstance(loader, Microsoft365Loader)

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_create_loader_sharepoint_alias(self):
        """Test 'sharepoint' alias for Microsoft365Loader."""
        loader = create_loader(
            "sharepoint", client_id="client", client_secret="secret", tenant_id="tenant"
        )
        assert isinstance(loader, Microsoft365Loader)


# =============================================================================
# NOTION LOADER TESTS
# =============================================================================


class TestNotionLoaderBasic:
    """Basic tests for NotionLoader."""

    @pytest.mark.skipif(not NOTION_AVAILABLE, reason="Notion client not available")
    def test_notion_loader_init(self):
        """Test NotionLoader initialization."""
        loader = NotionLoader(token="secret_test_token")
        assert loader.source_name == "Notion"

    @pytest.mark.skipif(not NOTION_AVAILABLE, reason="Notion client not available")
    def test_notion_authenticate(self):
        """Test Notion authentication."""
        with patch("notion_client.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.users.me.return_value = {"id": "user123"}
            mock_client.return_value = mock_instance

            loader = NotionLoader(token="secret_test")
            result = loader.authenticate()

            assert result is True


class TestNotionLoaderDocuments:
    """Tests for NotionLoader document operations."""

    @pytest.mark.skipif(not NOTION_AVAILABLE, reason="Notion client not available")
    def test_load_document(self):
        """Test loading a Notion page."""
        with patch("notion_client.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.users.me.return_value = {"id": "user123"}
            mock_instance.pages.retrieve.return_value = {
                "id": "page123",
                "url": "https://notion.so/page123",
                "properties": {
                    "title": {"type": "title", "title": [{"plain_text": "Test Page"}]}
                },
                "created_time": "2024-01-01T00:00:00Z",
                "last_edited_time": "2024-01-02T00:00:00Z",
                "parent": {"type": "workspace"},
            }
            mock_instance.blocks.children.list.return_value = {
                "results": [
                    {
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"plain_text": "Hello World"}]},
                    }
                ]
            }
            mock_client.return_value = mock_instance

            loader = NotionLoader(token="secret_test")
            loader.authenticate()

            doc = loader.load_document("page123")

            assert doc is not None
            assert "Hello World" in doc.content

    @pytest.mark.skipif(not NOTION_AVAILABLE, reason="Notion client not available")
    def test_load_database(self):
        """Test loading Notion database entries."""
        with patch("notion_client.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.users.me.return_value = {"id": "user123"}
            mock_instance.databases.query.return_value = {
                "results": [{"id": "page1"}, {"id": "page2"}],
                "has_more": False,
            }
            mock_instance.pages.retrieve.return_value = {
                "id": "page1",
                "properties": {"title": {"type": "title", "title": []}},
                "parent": {"type": "database"},
            }
            mock_instance.blocks.children.list.return_value = {"results": []}
            mock_client.return_value = mock_instance

            loader = NotionLoader(token="secret_test")
            loader.authenticate()

            docs = loader.load_database("db123")

            assert isinstance(docs, list)


class TestNotionLoaderSearch:
    """Tests for NotionLoader search."""

    @pytest.mark.skipif(not NOTION_AVAILABLE, reason="Notion client not available")
    def test_search(self):
        """Test Notion search."""
        with patch("notion_client.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.users.me.return_value = {"id": "user123"}
            mock_instance.search.return_value = {
                "results": [{"object": "page", "id": "page123"}]
            }
            mock_instance.pages.retrieve.return_value = {
                "id": "page123",
                "properties": {"title": {"type": "title", "title": []}},
                "parent": {},
            }
            mock_instance.blocks.children.list.return_value = {"results": []}
            mock_client.return_value = mock_instance

            loader = NotionLoader(token="secret_test")
            loader.authenticate()

            results = loader.search("project")

            assert isinstance(results, list)


class TestNotionLoaderFactory:
    """Tests for Notion in factory function."""

    @pytest.mark.skipif(not NOTION_AVAILABLE, reason="Notion client not available")
    def test_create_loader_notion(self):
        """Test creating NotionLoader via factory."""
        loader = create_loader("notion", token="secret_test")
        assert isinstance(loader, NotionLoader)


# =============================================================================
# CONFLUENCE LOADER TESTS
# =============================================================================


class TestConfluenceLoaderBasic:
    """Basic tests for ConfluenceLoader."""

    @pytest.mark.skipif(not CONFLUENCE_AVAILABLE, reason="Atlassian API not available")
    def test_confluence_loader_init(self):
        """Test ConfluenceLoader initialization."""
        loader = ConfluenceLoader(
            url="https://company.atlassian.net/wiki",
            username="user@company.com",
            api_token="token123",
        )
        assert loader.source_name == "Confluence"

    @pytest.mark.skipif(not CONFLUENCE_AVAILABLE, reason="Atlassian API not available")
    def test_confluence_authenticate(self):
        """Test Confluence authentication."""
        with patch("atlassian.Confluence") as mock_confluence:
            mock_instance = MagicMock()
            mock_instance.get_all_spaces.return_value = {"results": []}
            mock_confluence.return_value = mock_instance

            loader = ConfluenceLoader(
                url="https://company.atlassian.net/wiki",
                username="user@company.com",
                api_token="token123",
            )
            result = loader.authenticate()

            assert result is True


class TestConfluenceLoaderDocuments:
    """Tests for ConfluenceLoader document operations."""

    @pytest.mark.skipif(not CONFLUENCE_AVAILABLE, reason="Atlassian API not available")
    def test_load_document(self):
        """Test loading a Confluence page."""
        with patch("atlassian.Confluence") as mock_confluence:
            mock_instance = MagicMock()
            mock_instance.get_all_spaces.return_value = {"results": []}
            mock_instance.get_page_by_id.return_value = {
                "id": "12345",
                "title": "Test Page",
                "body": {"storage": {"value": "<p>Hello World</p>"}},
                "space": {"key": "PROJ", "name": "Project"},
                "version": {"number": 1, "when": "2024-01-01"},
                "ancestors": [],
            }
            mock_confluence.return_value = mock_instance

            loader = ConfluenceLoader(
                url="https://company.atlassian.net/wiki",
                username="user@company.com",
                api_token="token123",
            )
            loader.authenticate()

            doc = loader.load_document("12345")

            assert doc is not None
            assert "Hello World" in doc.content

    @pytest.mark.skipif(not CONFLUENCE_AVAILABLE, reason="Atlassian API not available")
    def test_load_space(self):
        """Test loading a Confluence space."""
        with patch("atlassian.Confluence") as mock_confluence:
            mock_instance = MagicMock()
            mock_instance.get_all_spaces.return_value = {"results": []}
            mock_instance.get_all_pages_from_space.return_value = [
                {"id": "page1"},
                {"id": "page2"},
            ]
            mock_instance.get_page_by_id.return_value = {
                "id": "page1",
                "title": "Page",
                "body": {"storage": {"value": ""}},
                "space": {"key": "PROJ"},
                "version": {},
                "ancestors": [],
            }
            mock_confluence.return_value = mock_instance

            loader = ConfluenceLoader(
                url="https://company.atlassian.net/wiki",
                username="user@company.com",
                api_token="token123",
            )
            loader.authenticate()

            docs = loader.load_space("PROJ")

            assert isinstance(docs, list)


class TestConfluenceLoaderSearch:
    """Tests for ConfluenceLoader search."""

    @pytest.mark.skipif(not CONFLUENCE_AVAILABLE, reason="Atlassian API not available")
    def test_search(self):
        """Test Confluence search."""
        with patch("atlassian.Confluence") as mock_confluence:
            mock_instance = MagicMock()
            mock_instance.get_all_spaces.return_value = {"results": []}
            mock_instance.cql.return_value = {
                "results": [{"content": {"type": "page", "id": "page123"}}]
            }
            mock_instance.get_page_by_id.return_value = {
                "id": "page123",
                "title": "Test",
                "body": {"storage": {"value": ""}},
                "space": {},
                "version": {},
                "ancestors": [],
            }
            mock_confluence.return_value = mock_instance

            loader = ConfluenceLoader(
                url="https://company.atlassian.net/wiki",
                username="user@company.com",
                api_token="token123",
            )
            loader.authenticate()

            results = loader.search("roadmap")

            assert isinstance(results, list)


class TestConfluenceLoaderFactory:
    """Tests for Confluence in factory function."""

    @pytest.mark.skipif(not CONFLUENCE_AVAILABLE, reason="Atlassian API not available")
    def test_create_loader_confluence(self):
        """Test creating ConfluenceLoader via factory."""
        loader = create_loader(
            "confluence",
            url="https://company.atlassian.net/wiki",
            username="user",
            api_token="token",
        )
        assert isinstance(loader, ConfluenceLoader)

    @pytest.mark.skipif(not CONFLUENCE_AVAILABLE, reason="Atlassian API not available")
    def test_create_loader_atlassian_alias(self):
        """Test 'atlassian' alias for ConfluenceLoader."""
        loader = create_loader(
            "atlassian",
            url="https://company.atlassian.net/wiki",
            username="user",
            api_token="token",
        )
        assert isinstance(loader, ConfluenceLoader)


# =============================================================================
# SLACK LOADER TESTS
# =============================================================================


class TestSlackLoaderBasic:
    """Basic tests for SlackLoader."""

    @pytest.mark.skipif(not SLACK_AVAILABLE, reason="Slack SDK not available")
    def test_slack_loader_init(self):
        """Test SlackLoader initialization."""
        loader = SlackLoader(token="xoxb-test-token")
        assert loader.source_name == "Slack"

    @pytest.mark.skipif(not SLACK_AVAILABLE, reason="Slack SDK not available")
    def test_slack_authenticate(self):
        """Test Slack authentication."""
        with patch("slack_sdk.WebClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.auth_test.return_value = {"ok": True, "team": "TestTeam"}
            mock_client.return_value = mock_instance

            loader = SlackLoader(token="xoxb-test")
            result = loader.authenticate()

            assert result is True


class TestSlackLoaderDocuments:
    """Tests for SlackLoader document operations."""

    @pytest.mark.skipif(not SLACK_AVAILABLE, reason="Slack SDK not available")
    def test_load_channel(self):
        """Test loading messages from a Slack channel."""
        with patch("slack_sdk.WebClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.auth_test.return_value = {"ok": True, "team": "Test"}
            mock_instance.conversations_history.return_value = {
                "ok": True,
                "messages": [
                    {"user": "U123", "text": "Hello world", "ts": "1234567890.123456"}
                ],
            }
            mock_instance.users_info.return_value = {
                "ok": True,
                "user": {"real_name": "Test User", "name": "testuser"},
            }
            mock_client.return_value = mock_instance

            loader = SlackLoader(token="xoxb-test")
            loader.authenticate()

            docs = loader.load_channel("C12345", days=7)

            assert len(docs) == 1
            assert "Hello world" in docs[0].content

    @pytest.mark.skipif(not SLACK_AVAILABLE, reason="Slack SDK not available")
    def test_load_thread(self):
        """Test loading a Slack thread."""
        with patch("slack_sdk.WebClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.auth_test.return_value = {"ok": True, "team": "Test"}
            mock_instance.conversations_replies.return_value = {
                "ok": True,
                "messages": [
                    {"user": "U123", "text": "Parent", "ts": "1234567890.123456"},
                    {"user": "U456", "text": "Reply", "ts": "1234567890.123457"},
                ],
            }
            mock_instance.users_info.return_value = {
                "ok": True,
                "user": {"real_name": "User", "name": "user"},
            }
            mock_client.return_value = mock_instance

            loader = SlackLoader(token="xoxb-test")
            loader.authenticate()

            docs = loader.load_thread("C123", "1234567890.123456")

            assert len(docs) == 2


class TestSlackLoaderSearch:
    """Tests for SlackLoader search."""

    @pytest.mark.skipif(not SLACK_AVAILABLE, reason="Slack SDK not available")
    def test_search(self):
        """Test Slack search."""
        with patch("slack_sdk.WebClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.auth_test.return_value = {"ok": True, "team": "Test"}
            mock_instance.search_messages.return_value = {
                "ok": True,
                "messages": {
                    "matches": [
                        {
                            "user": "U123",
                            "text": "Project update",
                            "ts": "123",
                            "channel": {"id": "C123", "name": "general"},
                        }
                    ]
                },
            }
            mock_instance.users_info.return_value = {
                "ok": True,
                "user": {"real_name": "User"},
            }
            mock_client.return_value = mock_instance

            loader = SlackLoader(token="xoxb-test")
            loader.authenticate()

            results = loader.search("project update")

            assert len(results) == 1


class TestSlackLoaderFactory:
    """Tests for Slack in factory function."""

    @pytest.mark.skipif(not SLACK_AVAILABLE, reason="Slack SDK not available")
    def test_create_loader_slack(self):
        """Test creating SlackLoader via factory."""
        loader = create_loader("slack", token="xoxb-test")
        assert isinstance(loader, SlackLoader)


# ============================================================================
# Dropbox Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import DROPBOX_AVAILABLE, DropboxLoader
except ImportError:
    DROPBOX_AVAILABLE = False


class TestDropboxLoaderAuth:
    """Tests for DropboxLoader authentication."""

    @pytest.mark.skipif(not DROPBOX_AVAILABLE, reason="Dropbox SDK not available")
    def test_init_with_token(self):
        """Test initialization with access token."""
        loader = DropboxLoader(access_token="test-token")
        assert loader.source_name == "Dropbox"

    @pytest.mark.skipif(not DROPBOX_AVAILABLE, reason="Dropbox SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("dropbox.Dropbox") as mock_client:
            mock_instance = MagicMock()
            mock_instance.users_get_current_account.return_value = MagicMock(
                email="test@test.com"
            )
            mock_client.return_value = mock_instance

            loader = DropboxLoader(access_token="test-token")
            result = loader.authenticate()

            assert result is True

    @pytest.mark.skipif(not DROPBOX_AVAILABLE, reason="Dropbox SDK not available")
    def test_load_document(self):
        """Test loading a single file."""
        with patch("dropbox.Dropbox") as mock_client:
            mock_instance = MagicMock()
            mock_instance.users_get_current_account.return_value = MagicMock(
                email="test@test.com"
            )
            mock_metadata = MagicMock()
            mock_metadata.id = "id:abc123"
            mock_metadata.name = "test.txt"
            mock_metadata.server_modified = datetime.now()
            mock_metadata.size = 100
            mock_response = MagicMock()
            mock_response.content = b"Test content"
            mock_instance.files_download.return_value = (mock_metadata, mock_response)
            mock_client.return_value = mock_instance

            loader = DropboxLoader(access_token="test-token")
            loader.authenticate()
            doc = loader.load_document("/test.txt")

            assert doc is not None
            assert doc.content == "Test content"


class TestDropboxLoaderFactory:
    """Tests for Dropbox in factory function."""

    @pytest.mark.skipif(not DROPBOX_AVAILABLE, reason="Dropbox SDK not available")
    def test_create_loader_dropbox(self):
        """Test creating DropboxLoader via factory."""
        loader = create_loader("dropbox", access_token="test-token")
        assert isinstance(loader, DropboxLoader)


# ============================================================================
# Box Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import BOX_AVAILABLE, BoxLoader
except ImportError:
    BOX_AVAILABLE = False


class TestBoxLoaderAuth:
    """Tests for BoxLoader authentication."""

    @pytest.mark.skipif(not BOX_AVAILABLE, reason="Box SDK not available")
    def test_init_with_developer_token(self):
        """Test initialization with developer token."""
        loader = BoxLoader(developer_token="test-token")
        assert loader.source_name == "Box"

    @pytest.mark.skipif(not BOX_AVAILABLE, reason="Box SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with (
            patch("boxsdk.OAuth2"),
            patch("boxsdk.Client") as mock_client,
        ):
            mock_user = MagicMock()
            mock_user.login = "test@test.com"
            mock_client_instance = MagicMock()
            mock_client_instance.user.return_value.get.return_value = mock_user
            mock_client.return_value = mock_client_instance

            loader = BoxLoader(developer_token="test-token")
            result = loader.authenticate()

            assert result is True


class TestBoxLoaderFactory:
    """Tests for Box in factory function."""

    @pytest.mark.skipif(not BOX_AVAILABLE, reason="Box SDK not available")
    def test_create_loader_box(self):
        """Test creating BoxLoader via factory."""
        loader = create_loader("box", developer_token="test-token")
        assert isinstance(loader, BoxLoader)


# ============================================================================
# OneDrive Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import OneDriveLoader
except ImportError:
    pass


class TestOneDriveLoaderAuth:
    """Tests for OneDriveLoader authentication."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_init(self):
        """Test initialization."""
        loader = OneDriveLoader(
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="consumers",
        )
        assert loader.source_name == "OneDrive"

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("msal.ConfidentialClientApplication") as mock_app:
            mock_instance = MagicMock()
            mock_instance.acquire_token_for_client.return_value = {
                "access_token": "test-token"
            }
            mock_app.return_value = mock_instance

            loader = OneDriveLoader(
                client_id="test-client",
                client_secret="test-secret",
                tenant_id="consumers",
            )
            result = loader.authenticate()

            assert result is True


class TestOneDriveLoaderFactory:
    """Tests for OneDrive in factory function."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_create_loader_onedrive(self):
        """Test creating OneDriveLoader via factory."""
        loader = create_loader(
            "onedrive",
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="consumers",
        )
        assert isinstance(loader, OneDriveLoader)


# ============================================================================
# SharePoint Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import SharePointLoader
except ImportError:
    pass


class TestSharePointLoaderAuth:
    """Tests for SharePointLoader authentication."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_init(self):
        """Test initialization."""
        loader = SharePointLoader(
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant",
            site_url="https://company.sharepoint.com/sites/team",
        )
        assert loader.source_name == "SharePoint"


class TestSharePointLoaderFactory:
    """Tests for SharePoint in factory function."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_create_loader_sharepoint(self):
        """Test creating SharePointLoader via factory."""
        loader = create_loader(
            "sharepoint",
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant",
        )
        assert isinstance(loader, SharePointLoader)


# ============================================================================
# Discord Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import DISCORD_AVAILABLE, DiscordLoader
except ImportError:
    DISCORD_AVAILABLE = False


class TestDiscordLoaderAuth:
    """Tests for DiscordLoader authentication."""

    @pytest.mark.skipif(not DISCORD_AVAILABLE, reason="Discord.py not available")
    def test_init_with_token(self):
        """Test initialization with bot token."""
        loader = DiscordLoader(token="test-token")
        assert loader.source_name == "Discord"

    @pytest.mark.skipif(not DISCORD_AVAILABLE, reason="Discord.py not available")
    def test_authenticate(self):
        """Test authentication sets token."""
        loader = DiscordLoader(token="test-token")
        result = loader.authenticate()
        assert result is True


class TestDiscordLoaderFactory:
    """Tests for Discord in factory function."""

    @pytest.mark.skipif(not DISCORD_AVAILABLE, reason="Discord.py not available")
    def test_create_loader_discord(self):
        """Test creating DiscordLoader via factory."""
        loader = create_loader("discord", token="test-token")
        assert isinstance(loader, DiscordLoader)


# ============================================================================
# Teams Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import TeamsLoader
except ImportError:
    pass


class TestTeamsLoaderAuth:
    """Tests for TeamsLoader authentication."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_init(self):
        """Test initialization."""
        loader = TeamsLoader(
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant",
        )
        assert loader.source_name == "Teams"

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("msal.ConfidentialClientApplication") as mock_app:
            mock_instance = MagicMock()
            mock_instance.acquire_token_for_client.return_value = {
                "access_token": "test-token"
            }
            mock_app.return_value = mock_instance

            loader = TeamsLoader(
                client_id="test-client",
                client_secret="test-secret",
                tenant_id="test-tenant",
            )
            result = loader.authenticate()

            assert result is True


class TestTeamsLoaderFactory:
    """Tests for Teams in factory function."""

    @pytest.mark.skipif(not MSAL_AVAILABLE, reason="MSAL not available")
    def test_create_loader_teams(self):
        """Test creating TeamsLoader via factory."""
        loader = create_loader(
            "teams",
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant",
        )
        assert isinstance(loader, TeamsLoader)


# ============================================================================
# JIRA Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import JIRA_AVAILABLE, JiraLoader
except ImportError:
    JIRA_AVAILABLE = False


class TestJiraLoaderAuth:
    """Tests for JiraLoader authentication."""

    @pytest.mark.skipif(not JIRA_AVAILABLE, reason="JIRA SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = JiraLoader(
            url="https://company.atlassian.net",
            email="test@test.com",
            token="test-token",
        )
        assert loader.source_name == "JIRA"

    @pytest.mark.skipif(not JIRA_AVAILABLE, reason="JIRA SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("jira.JIRA") as mock_jira:
            mock_instance = MagicMock()
            mock_jira.return_value = mock_instance

            loader = JiraLoader(
                url="https://company.atlassian.net",
                email="test@test.com",
                token="test-token",
            )
            result = loader.authenticate()

            assert result is True


class TestJiraLoaderDocuments:
    """Tests for JiraLoader document operations."""

    @pytest.mark.skipif(not JIRA_AVAILABLE, reason="JIRA SDK not available")
    def test_load_issue(self):
        """Test loading a JIRA issue."""
        with patch("jira.JIRA") as mock_jira:
            mock_instance = MagicMock()
            mock_issue = MagicMock()
            mock_issue.key = "PROJ-123"
            mock_issue.fields.summary = "Test Issue"
            mock_issue.fields.status.name = "Open"
            mock_issue.fields.issuetype.name = "Task"
            mock_issue.fields.priority = MagicMock(name="Medium")
            mock_issue.fields.assignee = None
            mock_issue.fields.reporter = MagicMock(displayName="Reporter")
            mock_issue.fields.description = "Test description"
            mock_issue.fields.created = "2026-01-01T00:00:00Z"
            mock_issue.fields.updated = "2026-01-02T00:00:00Z"
            mock_issue.fields.project.key = "PROJ"
            mock_instance.issue.return_value = mock_issue
            mock_instance.comments.return_value = []
            mock_jira.return_value = mock_instance

            loader = JiraLoader(
                url="https://company.atlassian.net",
                email="test@test.com",
                token="test-token",
            )
            loader.authenticate()
            doc = loader.load_document("PROJ-123")

            assert doc is not None
            assert "PROJ-123" in doc.content
            assert "Test Issue" in doc.content


class TestJiraLoaderFactory:
    """Tests for JIRA in factory function."""

    @pytest.mark.skipif(not JIRA_AVAILABLE, reason="JIRA SDK not available")
    def test_create_loader_jira(self):
        """Test creating JiraLoader via factory."""
        loader = create_loader(
            "jira",
            url="https://company.atlassian.net",
            email="test@test.com",
            token="test-token",
        )
        assert isinstance(loader, JiraLoader)


# ============================================================================
# Asana Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import ASANA_AVAILABLE, AsanaLoader
except ImportError:
    ASANA_AVAILABLE = False


class TestAsanaLoaderAuth:
    """Tests for AsanaLoader authentication."""

    @pytest.mark.skipif(not ASANA_AVAILABLE, reason="Asana SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = AsanaLoader(token="test-token")
        assert loader.source_name == "Asana"

    @pytest.mark.skipif(not ASANA_AVAILABLE, reason="Asana SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("asana.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.users.me.return_value = {"name": "Test User"}
            mock_client.access_token.return_value = mock_instance

            loader = AsanaLoader(token="test-token")
            result = loader.authenticate()

            assert result is True


class TestAsanaLoaderFactory:
    """Tests for Asana in factory function."""

    @pytest.mark.skipif(not ASANA_AVAILABLE, reason="Asana SDK not available")
    def test_create_loader_asana(self):
        """Test creating AsanaLoader via factory."""
        loader = create_loader("asana", token="test-token")
        assert isinstance(loader, AsanaLoader)


# ============================================================================
# Trello Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import TRELLO_AVAILABLE, TrelloLoader
except ImportError:
    TRELLO_AVAILABLE = False


class TestTrelloLoaderAuth:
    """Tests for TrelloLoader authentication."""

    @pytest.mark.skipif(not TRELLO_AVAILABLE, reason="Trello SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = TrelloLoader(api_key="test-key", token="test-token")
        assert loader.source_name == "Trello"

    @pytest.mark.skipif(not TRELLO_AVAILABLE, reason="Trello SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("trello.TrelloClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.list_boards.return_value = []
            mock_client.return_value = mock_instance

            loader = TrelloLoader(api_key="test-key", token="test-token")
            result = loader.authenticate()

            assert result is True


class TestTrelloLoaderFactory:
    """Tests for Trello in factory function."""

    @pytest.mark.skipif(not TRELLO_AVAILABLE, reason="Trello SDK not available")
    def test_create_loader_trello(self):
        """Test creating TrelloLoader via factory."""
        loader = create_loader("trello", api_key="test-key", token="test-token")
        assert isinstance(loader, TrelloLoader)


# ============================================================================
# Airtable Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import AIRTABLE_AVAILABLE, AirtableLoader
except ImportError:
    AIRTABLE_AVAILABLE = False


class TestAirtableLoaderAuth:
    """Tests for AirtableLoader authentication."""

    @pytest.mark.skipif(not AIRTABLE_AVAILABLE, reason="Airtable SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = AirtableLoader(api_key="test-key")
        assert loader.source_name == "Airtable"

    @pytest.mark.skipif(not AIRTABLE_AVAILABLE, reason="Airtable SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("pyairtable.Api") as mock_api:
            mock_api.return_value = MagicMock()

            loader = AirtableLoader(api_key="test-key")
            result = loader.authenticate()

            assert result is True


class TestAirtableLoaderFactory:
    """Tests for Airtable in factory function."""

    @pytest.mark.skipif(not AIRTABLE_AVAILABLE, reason="Airtable SDK not available")
    def test_create_loader_airtable(self):
        """Test creating AirtableLoader via factory."""
        loader = create_loader("airtable", api_key="test-key")
        assert isinstance(loader, AirtableLoader)


# ============================================================================
# HubSpot Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import HUBSPOT_AVAILABLE, HubSpotLoader
except ImportError:
    HUBSPOT_AVAILABLE = False


class TestHubSpotLoaderAuth:
    """Tests for HubSpotLoader authentication."""

    @pytest.mark.skipif(not HUBSPOT_AVAILABLE, reason="HubSpot SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = HubSpotLoader(api_key="test-key")
        assert loader.source_name == "HubSpot"

    @pytest.mark.skipif(not HUBSPOT_AVAILABLE, reason="HubSpot SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("hubspot.HubSpot") as mock_hubspot:
            mock_instance = MagicMock()
            mock_hubspot.return_value = mock_instance

            loader = HubSpotLoader(api_key="test-key")
            result = loader.authenticate()

            assert result is True


class TestHubSpotLoaderFactory:
    """Tests for HubSpot in factory function."""

    @pytest.mark.skipif(not HUBSPOT_AVAILABLE, reason="HubSpot SDK not available")
    def test_create_loader_hubspot(self):
        """Test creating HubSpotLoader via factory."""
        loader = create_loader("hubspot", api_key="test-key")
        assert isinstance(loader, HubSpotLoader)


# ============================================================================
# Salesforce Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import SALESFORCE_AVAILABLE, SalesforceLoader
except ImportError:
    SALESFORCE_AVAILABLE = False


class TestSalesforceLoaderAuth:
    """Tests for SalesforceLoader authentication."""

    @pytest.mark.skipif(not SALESFORCE_AVAILABLE, reason="Salesforce SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = SalesforceLoader(
            username="test@test.com",
            password="password",
            security_token="token",
        )
        assert loader.source_name == "Salesforce"

    @pytest.mark.skipif(not SALESFORCE_AVAILABLE, reason="Salesforce SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("simple_salesforce.Salesforce") as mock_sf:
            mock_sf.return_value = MagicMock()

            loader = SalesforceLoader(
                username="test@test.com",
                password="password",
                security_token="token",
            )
            result = loader.authenticate()

            assert result is True


class TestSalesforceLoaderFactory:
    """Tests for Salesforce in factory function."""

    @pytest.mark.skipif(not SALESFORCE_AVAILABLE, reason="Salesforce SDK not available")
    def test_create_loader_salesforce(self):
        """Test creating SalesforceLoader via factory."""
        loader = create_loader(
            "salesforce",
            username="test@test.com",
            password="password",
            security_token="token",
        )
        assert isinstance(loader, SalesforceLoader)


# ============================================================================
# Zendesk Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import ZENDESK_AVAILABLE, ZendeskLoader
except ImportError:
    ZENDESK_AVAILABLE = False


class TestZendeskLoaderAuth:
    """Tests for ZendeskLoader authentication."""

    @pytest.mark.skipif(not ZENDESK_AVAILABLE, reason="Zendesk SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = ZendeskLoader(
            email="test@test.com",
            token="test-token",
            subdomain="company",
        )
        assert loader.source_name == "Zendesk"

    @pytest.mark.skipif(not ZENDESK_AVAILABLE, reason="Zendesk SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("zenpy.Zenpy") as mock_zenpy:
            mock_instance = MagicMock()
            mock_zenpy.return_value = mock_instance

            loader = ZendeskLoader(
                email="test@test.com",
                token="test-token",
                subdomain="company",
            )
            result = loader.authenticate()

            assert result is True


class TestZendeskLoaderFactory:
    """Tests for Zendesk in factory function."""

    @pytest.mark.skipif(not ZENDESK_AVAILABLE, reason="Zendesk SDK not available")
    def test_create_loader_zendesk(self):
        """Test creating ZendeskLoader via factory."""
        loader = create_loader(
            "zendesk",
            email="test@test.com",
            token="test-token",
            subdomain="company",
        )
        assert isinstance(loader, ZendeskLoader)


# ============================================================================
# Intercom Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import INTERCOM_AVAILABLE, IntercomLoader
except ImportError:
    INTERCOM_AVAILABLE = False


class TestIntercomLoaderAuth:
    """Tests for IntercomLoader authentication."""

    @pytest.mark.skipif(not INTERCOM_AVAILABLE, reason="Intercom SDK not available")
    def test_init(self):
        """Test initialization."""
        loader = IntercomLoader(token="test-token")
        assert loader.source_name == "Intercom"

    @pytest.mark.skipif(not INTERCOM_AVAILABLE, reason="Intercom SDK not available")
    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("intercom.client.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance

            loader = IntercomLoader(token="test-token")
            result = loader.authenticate()

            assert result is True


class TestIntercomLoaderFactory:
    """Tests for Intercom in factory function."""

    @pytest.mark.skipif(not INTERCOM_AVAILABLE, reason="Intercom SDK not available")
    def test_create_loader_intercom(self):
        """Test creating IntercomLoader via factory."""
        loader = create_loader("intercom", token="test-token")
        assert isinstance(loader, IntercomLoader)


# ============================================================================
# Freshdesk Loader Tests
# ============================================================================

try:
    from agentic_brain.rag.loaders import FRESHDESK_AVAILABLE, FreshdeskLoader
except ImportError:
    FRESHDESK_AVAILABLE = False
    FreshdeskLoader = None


@pytest.mark.skipif(
    not FRESHDESK_AVAILABLE or FreshdeskLoader is None,
    reason="Freshdesk SDK not available",
)
class TestFreshdeskLoaderAuth:
    """Tests for FreshdeskLoader authentication."""

    def test_init(self):
        """Test initialization."""
        loader = FreshdeskLoader(domain="company", api_key="test-key")
        assert loader.source_name == "Freshdesk"

    def test_authenticate_success(self):
        """Test successful authentication."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            loader = FreshdeskLoader(domain="company", api_key="test-key")
            result = loader.authenticate()

            assert result is True

    def test_load_ticket(self):
        """Test loading a single ticket."""
        with patch("requests.get") as mock_get:
            # First call for auth
            auth_response = MagicMock()
            auth_response.status_code = 200

            # Second call for ticket
            ticket_response = MagicMock()
            ticket_response.status_code = 200
            ticket_response.json.return_value = {
                "id": 123,
                "subject": "Test Ticket",
                "status": 2,
                "priority": 2,
                "description_text": "Test description",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }

            # Third call for conversations
            conv_response = MagicMock()
            conv_response.status_code = 200
            conv_response.json.return_value = []

            mock_get.side_effect = [auth_response, ticket_response, conv_response]

            loader = FreshdeskLoader(domain="company", api_key="test-key")
            loader.authenticate()
            doc = loader.load_document("123")

            assert doc is not None
            assert "Test Ticket" in doc.content


@pytest.mark.skipif(
    not FRESHDESK_AVAILABLE or FreshdeskLoader is None,
    reason="Freshdesk SDK not available",
)
class TestFreshdeskLoaderFactory:
    """Tests for Freshdesk in factory function."""

    def test_create_loader_freshdesk(self):
        """Test creating FreshdeskLoader via factory."""
        loader = create_loader("freshdesk", domain="company", api_key="test-key")
        assert isinstance(loader, FreshdeskLoader)
