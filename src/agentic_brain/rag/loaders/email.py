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

"""Email loaders for RAG pipelines.

Supports:
- Gmail (via Google API)
- Microsoft 365/Outlook (via Microsoft Graph API)
"""

import base64
import logging
import os
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for Google API
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# Check for MSAL (Microsoft)
try:
    import requests
    from msal import ConfidentialClientApplication, PublicClientApplication

    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False


class GmailLoader(BaseLoader):
    """Load emails from Gmail as documents.

    Supports:
    - Email body (plain text or HTML converted to text)
    - Attachments (text, PDF, Word docs)
    - Search with Gmail query syntax
    - Label-based filtering

    Example:
        loader = GmailLoader(credentials_path="client_secrets.json")

        # Load recent emails
        emails = loader.load_recent(days=7)

        # Search with Gmail syntax
        emails = loader.search("from:boss@company.com has:attachment")

        # Load by label
        emails = loader.load_by_label("IMPORTANT")
    """

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        token_path: str = "gmail_token.json",
        include_attachments: bool = True,
        max_attachment_size_mb: int = 25,
    ):
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. Run: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )

        self.credentials_path = credentials_path
        self.token_path = token_path
        self.include_attachments = include_attachments
        self.max_attachment_size = max_attachment_size_mb * 1024 * 1024
        self._service = None
        self._credentials = None

    @property
    def source_name(self) -> str:
        return "gmail"

    def authenticate(self) -> bool:
        """Authenticate with Gmail API."""
        try:
            if os.path.exists(self.token_path):
                self._credentials = Credentials.from_authorized_user_file(
                    self.token_path, self.SCOPES
                )

            if not self._credentials or not self._credentials.valid:
                if (
                    self._credentials
                    and self._credentials.expired
                    and self._credentials.refresh_token
                ):
                    self._credentials.refresh(Request())
                else:
                    if not self.credentials_path:
                        raise ValueError("credentials_path required for OAuth2 flow")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    self._credentials = flow.run_local_server(port=0)

                with open(self.token_path, "w") as token:
                    token.write(self._credentials.to_json())

            self._service = build("gmail", "v1", credentials=self._credentials)
            logger.info("Gmail authentication successful")
            return True

        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._service and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Gmail")

    def _get_message_body(self, payload: dict) -> str:
        """Extract message body from payload."""
        body = ""

        if "body" in payload and payload["body"].get("data"):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="replace"
            )

        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")

                if mime_type == "text/plain":
                    if part.get("body", {}).get("data"):
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                            "utf-8", errors="replace"
                        )
                        break
                elif mime_type == "text/html":
                    if part.get("body", {}).get("data"):
                        html = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                            "utf-8", errors="replace"
                        )
                        body = self._clean_html(html)
                elif mime_type.startswith("multipart/"):
                    body = self._get_message_body(part)
                    if body:
                        break

        return body

    def _get_attachments(self, message_id: str, payload: dict) -> list[LoadedDocument]:
        """Extract attachments from email."""
        attachments = []

        def process_parts(parts: list[dict]):
            for part in parts:
                filename = part.get("filename", "")
                if filename and part.get("body", {}).get("attachmentId"):
                    mime_type = part.get("mimeType", "")
                    size = int(part.get("body", {}).get("size", 0))

                    if size > self.max_attachment_size:
                        logger.debug(f"Skipping large attachment: {filename}")
                        continue

                    try:
                        attachment = (
                            self._service.users()
                            .messages()
                            .attachments()
                            .get(
                                userId="me",
                                messageId=message_id,
                                id=part["body"]["attachmentId"],
                            )
                            .execute()
                        )

                        data = base64.urlsafe_b64decode(attachment["data"])

                        content = None
                        if mime_type == "application/pdf":
                            content = self._extract_text_from_pdf(data)
                        elif mime_type.startswith("text/"):
                            content = data.decode("utf-8", errors="replace")

                        if content:
                            attachments.append(
                                LoadedDocument(
                                    content=content,
                                    source="gmail_attachment",
                                    source_id=f"{message_id}_{part['body']['attachmentId']}",
                                    filename=filename,
                                    mime_type=mime_type,
                                    size_bytes=size,
                                    metadata={
                                        "message_id": message_id,
                                        "attachment_filename": filename,
                                    },
                                )
                            )
                    except Exception as e:
                        logger.error(f"Failed to get attachment {filename}: {e}")

                if "parts" in part:
                    process_parts(part["parts"])

        if "parts" in payload:
            process_parts(payload["parts"])

        return attachments

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single email by message ID."""
        self._ensure_authenticated()

        try:
            message = (
                self._service.users()
                .messages()
                .get(userId="me", id=doc_id, format="full")
                .execute()
            )

            headers = {
                h["name"].lower(): h["value"]
                for h in message.get("payload", {}).get("headers", [])
            }

            subject = headers.get("subject", "(No Subject)")
            from_addr = headers.get("from", "")
            to_addr = headers.get("to", "")
            date_str = headers.get("date", "")

            created_at = None
            if date_str:
                try:
                    from email.utils import parsedate_to_datetime

                    created_at = parsedate_to_datetime(date_str)
                except Exception:
                    pass

            body = self._get_message_body(message.get("payload", {}))
            content = f"Subject: {subject}\nFrom: {from_addr}\nTo: {to_addr}\nDate: {date_str}\n\n{body}"

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"{subject}.eml",
                mime_type="message/rfc822",
                created_at=created_at,
                metadata={
                    "message_id": doc_id,
                    "subject": subject,
                    "from": from_addr,
                    "to": to_addr,
                    "labels": message.get("labelIds", []),
                    "thread_id": message.get("threadId", ""),
                },
            )

        except Exception as e:
            logger.error(f"Failed to load email {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load emails by label (folder)."""
        return self.load_by_label(folder_path)

    def load_by_label(self, label: str, max_results: int = 100) -> list[LoadedDocument]:
        """Load emails with a specific label."""
        self._ensure_authenticated()
        return self._search_messages(f"label:{label}", max_results)

    def load_recent(
        self, days: int = 7, max_results: int = 100
    ) -> list[LoadedDocument]:
        """Load recent emails from the last N days."""
        self._ensure_authenticated()
        return self._search_messages(f"newer_than:{days}d", max_results)

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search emails using Gmail query syntax."""
        self._ensure_authenticated()
        return self._search_messages(query, max_results)

    def _search_messages(self, query: str, max_results: int) -> list[LoadedDocument]:
        """Internal search implementation."""
        documents = []
        page_token = None

        while len(documents) < max_results:
            results = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=min(100, max_results - len(documents)),
                    pageToken=page_token,
                )
                .execute()
            )

            for msg in results.get("messages", []):
                doc = self.load_document(msg["id"])
                if doc:
                    documents.append(doc)

                    if self.include_attachments:
                        full_msg = (
                            self._service.users()
                            .messages()
                            .get(userId="me", id=msg["id"], format="full")
                            .execute()
                        )
                        attachments = self._get_attachments(
                            msg["id"], full_msg.get("payload", {})
                        )
                        documents.extend(attachments)

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Loaded {len(documents)} emails matching '{query}'")
        return documents

    def list_labels(self) -> list[dict[str, str]]:
        """List all Gmail labels."""
        self._ensure_authenticated()

        results = self._service.users().labels().list(userId="me").execute()
        return [{"id": l["id"], "name": l["name"]} for l in results.get("labels", [])]


class Microsoft365Loader(BaseLoader):
    """Load documents from Microsoft 365 (OneDrive, Outlook, SharePoint).

    Uses Microsoft Graph API to access all Microsoft 365 services.

    Authentication options:
        1. Client credentials (app-only, for automation)
        2. Device code flow (interactive, for users)
        3. Existing access token

    Example:
        loader = Microsoft365Loader(
            client_id="your-app-id",
            client_secret="your-secret",
            tenant_id="your-tenant-id"
        )

        # Load OneDrive files
        docs = loader.load_onedrive_folder("Documents/Projects")

        # Load recent emails
        emails = loader.load_outlook_emails(days=7, query="from:boss@company.com")
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    SCOPES_DELEGATED = [
        "Files.Read.All",
        "Mail.Read",
        "Sites.Read.All",
        "Notes.Read.All",
        "User.Read",
    ]

    SCOPES_APPLICATION = ["https://graph.microsoft.com/.default"]

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        access_token: Optional[str] = None,
        user_id: Optional[str] = None,
        use_device_flow: bool = False,
    ):
        if not MSAL_AVAILABLE:
            raise ImportError(
                "MSAL not available. Install with: pip install msal requests"
            )

        self._client_id = client_id or os.environ.get("MICROSOFT_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get("MICROSOFT_CLIENT_SECRET")
        self._tenant_id = tenant_id or os.environ.get("MICROSOFT_TENANT_ID")
        self._access_token = access_token
        self._user_id = user_id or "me"
        self._use_device_flow = use_device_flow

        self._app: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "microsoft365"

    def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph."""
        if self._authenticated and self._access_token:
            return True

        try:
            if self._access_token:
                self._authenticated = True
                return True

            if not self._client_id or not self._tenant_id:
                raise ValueError("client_id and tenant_id are required")

            authority = f"https://login.microsoftonline.com/{self._tenant_id}"

            if self._client_secret:
                self._app = ConfidentialClientApplication(
                    self._client_id,
                    authority=authority,
                    client_credential=self._client_secret,
                )

                result = self._app.acquire_token_for_client(
                    scopes=self.SCOPES_APPLICATION
                )

            elif self._use_device_flow:
                self._app = PublicClientApplication(
                    self._client_id, authority=authority
                )

                flow = self._app.initiate_device_flow(scopes=self.SCOPES_DELEGATED)

                if "user_code" not in flow:
                    raise ValueError(
                        f"Failed to create device flow: {flow.get('error_description')}"
                    )

                print(f"\nTo authenticate, visit: {flow['verification_uri']}")
                print(f"Enter code: {flow['user_code']}\n")

                result = self._app.acquire_token_by_device_flow(flow)
            else:
                raise ValueError(
                    "Either client_secret or use_device_flow must be provided"
                )

            if "access_token" in result:
                self._access_token = result["access_token"]
                self._authenticated = True
                logger.info("Microsoft 365 authenticated successfully")
                return True
            else:
                error = result.get(
                    "error_description", result.get("error", "Unknown error")
                )
                logger.error(f"Microsoft 365 authentication failed: {error}")
                return False

        except Exception as e:
            logger.error(f"Microsoft 365 authentication failed: {e}")
            return False

    def _ensure_authenticated(self) -> None:
        if not self._authenticated and not self.authenticate():
            raise RuntimeError("Microsoft 365 authentication required")

    def _graph_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Optional[dict]:
        """Make a request to Microsoft Graph API."""
        url = f"{self.GRAPH_BASE_URL}/{endpoint.lstrip('/')}"

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.request(
                method, url, headers=headers, params=params, json=data, timeout=30
            )
            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.HTTPError as e:
            logger.error(
                f"Graph API error: {e.response.status_code} - {e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"Graph API request failed: {e}")
            return None

    def _download_file_content(self, download_url: str) -> Optional[bytes]:
        """Download file content from OneDrive/SharePoint."""
        try:
            response = requests.get(
                download_url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=60,
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return None

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID."""
        self._ensure_authenticated()

        try:
            parts = doc_id.split(":")

            if parts[0] == "onedrive":
                item_id = parts[1]
                endpoint = f"/me/drive/items/{item_id}"
            elif parts[0] == "sharepoint":
                site_id, item_id = parts[1], parts[2]
                endpoint = f"/sites/{site_id}/drive/items/{item_id}"
            elif parts[0] == "outlook":
                message_id = parts[1]
                return self._load_outlook_message(message_id)
            else:
                raise ValueError(f"Invalid doc_id format: {doc_id}")

            item = self._graph_request(endpoint)
            if not item:
                return None

            download_url = item.get("@microsoft.graph.downloadUrl")
            if not download_url:
                return None

            content_bytes = self._download_file_content(download_url)
            if not content_bytes:
                return None

            mime_type = item.get("file", {}).get("mimeType", "application/octet-stream")
            filename = item.get("name", "")

            if mime_type == "application/pdf":
                content = self._extract_text_from_pdf(content_bytes)
            elif mime_type.startswith("text/"):
                content = content_bytes.decode("utf-8", errors="replace")
            else:
                logger.debug(f"Unsupported type: {mime_type}")
                return None

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=filename,
                mime_type=mime_type,
                created_at=(
                    datetime.fromisoformat(
                        item.get("createdDateTime", "").replace("Z", "+00:00")
                    )
                    if item.get("createdDateTime")
                    else None
                ),
                modified_at=(
                    datetime.fromisoformat(
                        item.get("lastModifiedDateTime", "").replace("Z", "+00:00")
                    )
                    if item.get("lastModifiedDateTime")
                    else None
                ),
                size_bytes=item.get("size", 0),
                metadata={"web_url": item.get("webUrl", ""), "id": item.get("id", "")},
            )

        except Exception as e:
            logger.error(f"Failed to load document {doc_id}: {e}")
            return None

    def _load_outlook_message(self, message_id: str) -> Optional[LoadedDocument]:
        """Load a single Outlook email."""
        message = self._graph_request(f"/me/messages/{message_id}")
        if not message:
            return None

        subject = message.get("subject", "(No Subject)")
        from_addr = message.get("from", {}).get("emailAddress", {}).get("address", "")
        to_addrs = [
            r.get("emailAddress", {}).get("address", "")
            for r in message.get("toRecipients", [])
        ]
        body = message.get("body", {}).get("content", "")

        if message.get("body", {}).get("contentType") == "html":
            body = self._clean_html(body)

        content = f"Subject: {subject}\nFrom: {from_addr}\nTo: {', '.join(to_addrs)}\n\n{body}"

        return LoadedDocument(
            content=content,
            source="outlook",
            source_id=f"outlook:{message_id}",
            filename=f"{subject}.eml",
            mime_type="message/rfc822",
            created_at=(
                datetime.fromisoformat(
                    message.get("createdDateTime", "").replace("Z", "+00:00")
                )
                if message.get("createdDateTime")
                else None
            ),
            metadata={
                "message_id": message_id,
                "subject": subject,
                "from": from_addr,
                "to": to_addrs,
                "is_read": message.get("isRead", False),
            },
        )

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load documents from OneDrive folder."""
        return self.load_onedrive_folder(folder_path, recursive)

    def load_onedrive_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all files from OneDrive folder."""
        self._ensure_authenticated()
        documents = []

        try:
            endpoint = (
                f"/me/drive/root:/{folder_path}:/children"
                if folder_path
                else "/me/drive/root/children"
            )
            result = self._graph_request(endpoint)

            if not result:
                return []

            for item in result.get("value", []):
                if "folder" in item and recursive:
                    subfolder = (
                        f"{folder_path}/{item['name']}" if folder_path else item["name"]
                    )
                    documents.extend(self.load_onedrive_folder(subfolder, recursive))
                elif "file" in item:
                    doc = self.load_document(f"onedrive:{item['id']}")
                    if doc:
                        documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Failed to load OneDrive folder: {e}")
            return []

    def load_outlook_emails(
        self, days: int = 7, query: Optional[str] = None, max_results: int = 100
    ) -> list[LoadedDocument]:
        """Load recent Outlook emails."""
        self._ensure_authenticated()
        documents = []

        try:
            params = {
                "$top": max_results,
                "$orderby": "receivedDateTime desc",
            }

            if days:
                since = datetime.now(UTC) - timedelta(days=days)
                params["$filter"] = f"receivedDateTime ge {since.isoformat()}Z"

            if query:
                params["$search"] = f'"{query}"'

            result = self._graph_request("/me/messages", params=params)

            if not result:
                return []

            for message in result.get("value", []):
                doc = self._load_outlook_message(message["id"])
                if doc:
                    documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Failed to load Outlook emails: {e}")
            return []

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search across OneDrive files."""
        self._ensure_authenticated()
        documents = []

        try:
            result = self._graph_request(
                f"/me/drive/root/search(q='{query}')",
                params={"$top": max_results},
            )

            if not result:
                return []

            for item in result.get("value", []):
                if "file" in item:
                    doc = self.load_document(f"onedrive:{item['id']}")
                    if doc:
                        documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []


# Alias for backwards compatibility
OutlookLoader = Microsoft365Loader

__all__ = [
    "GmailLoader",
    "Microsoft365Loader",
    "OutlookLoader",
]
