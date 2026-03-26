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

"""Cloud storage loaders for RAG pipelines.

Supports:
- Amazon S3
- Google Cloud Storage (GCS)
- Azure Blob Storage
- MinIO (S3-compatible, self-hosted)
"""

import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for boto3 (AWS SDK)
try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Check for Azure Blob
try:
    from azure.storage.blob import BlobServiceClient

    AZURE_BLOB_AVAILABLE = True
except ImportError:
    AZURE_BLOB_AVAILABLE = False

# Check for Google Cloud Storage
try:
    from google.cloud import storage as gcs_storage

    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False


class S3Loader(BaseLoader):
    """Load documents from Amazon S3 or MinIO (S3-compatible).

    Works with:
    - Amazon S3 (cloud)
    - MinIO (self-hosted, S3-compatible)
    - Any S3-compatible storage (Wasabi, DigitalOcean Spaces, etc.)

    Authentication options:
        1. AWS credentials file (~/.aws/credentials)
        2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        3. Explicit credentials in constructor
        4. IAM role (for EC2/Lambda)

    Example:
        # AWS S3
        loader = S3Loader(bucket="my-documents")
        docs = loader.load_folder("reports/2024/")

        # MinIO (self-hosted)
        loader = S3Loader(
            bucket="documents",
            endpoint_url="http://minio.local:9000",
            access_key="minioadmin",
            secret_key="minioadmin"
        )
        docs = loader.load_folder("project-docs/")
    """

    TEXT_EXTENSIONS = {
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".csv",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".html",
        ".htm",
        ".log",
        ".ini",
        ".cfg",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
    }

    def __init__(
        self,
        bucket: str,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "us-east-1",
        prefix: str = "",
        include_metadata: bool = True,
        **kwargs,
    ):
        """Initialize S3/MinIO loader.

        Args:
            bucket: S3 bucket name
            endpoint_url: Custom endpoint for MinIO/S3-compatible
            access_key: AWS access key ID (or MinIO access key)
            secret_key: AWS secret access key (or MinIO secret key)
            region: AWS region (default: us-east-1)
            prefix: Default prefix/folder to use
            include_metadata: Include S3 object metadata in documents
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 not available. Install with: pip install boto3")

        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._access_key = access_key or kwargs.get("aws_access_key_id")
        self._secret_key = secret_key or kwargs.get("aws_secret_access_key")
        self._region = region
        self._prefix = prefix.strip("/")
        self._include_metadata = include_metadata
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "s3"

    def authenticate(self) -> bool:
        """Initialize S3 client."""
        if self._authenticated and self._client is not None:
            return True

        try:
            client_kwargs = {
                "service_name": "s3",
                "region_name": self._region,
            }

            if self._endpoint_url:
                client_kwargs["endpoint_url"] = self._endpoint_url
                client_kwargs["config"] = BotoConfig(
                    signature_version="s3v4", s3={"addressing_style": "path"}
                )

            if self._access_key and self._secret_key:
                client_kwargs["aws_access_key_id"] = self._access_key
                client_kwargs["aws_secret_access_key"] = self._secret_key

            self._client = boto3.client(**client_kwargs)
            self._client.head_bucket(Bucket=self._bucket)

            self._authenticated = True
            endpoint = self._endpoint_url or "AWS S3"
            logger.info(f"S3 authenticated: {endpoint}, bucket: {self._bucket}")
            return True

        except NoCredentialsError:
            logger.error("S3 authentication failed: No credentials found")
            return False
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 authentication failed: {error_code}")
            return False
        except Exception as e:
            logger.error(f"S3 authentication failed: {e}")
            return False

    def _ensure_authenticated(self) -> None:
        if not self._authenticated and not self.authenticate():
            raise RuntimeError("S3 authentication required")

    def _get_object_content(self, key: str) -> Optional[tuple]:
        """Get object content and metadata."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            content_type = response.get("ContentType", "application/octet-stream")
            body = response["Body"].read()

            if content_type.startswith("text/") or self._is_text_file(key):
                try:
                    content = body.decode("utf-8")
                except UnicodeDecodeError:
                    content = body.decode("latin-1")
            elif content_type == "application/json":
                content = body.decode("utf-8")
            elif content_type == "application/pdf":
                content = self._extract_text_from_pdf(body)
            else:
                ext = Path(key).suffix.lower()
                if ext in self.TEXT_EXTENSIONS:
                    try:
                        content = body.decode("utf-8")
                    except UnicodeDecodeError:
                        logger.debug(f"Skipping binary file: {key}")
                        return None
                else:
                    logger.debug(f"Skipping non-text file: {key}")
                    return None

            metadata = {
                "content_type": content_type,
                "content_length": response.get("ContentLength", 0),
                "etag": response.get("ETag", "").strip('"'),
                "last_modified": response.get("LastModified"),
            }

            if self._include_metadata and "Metadata" in response:
                metadata["s3_metadata"] = response["Metadata"]

            return content, metadata

        except ClientError as e:
            logger.error(f"Failed to get object {key}: {e}")
            return None

    def _is_text_file(self, key: str) -> bool:
        ext = Path(key).suffix.lower()
        return ext in self.TEXT_EXTENSIONS

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by S3 key."""
        self._ensure_authenticated()

        try:
            result = self._get_object_content(doc_id)
            if result is None:
                return None

            content, metadata = result
            head = self._client.head_object(Bucket=self._bucket, Key=doc_id)

            return LoadedDocument(
                content=content,
                metadata={"bucket": self._bucket, "key": doc_id, **metadata},
                source="s3",
                source_id=f"s3://{self._bucket}/{doc_id}",
                filename=Path(doc_id).name,
                mime_type=metadata.get("content_type", "text/plain"),
                created_at=None,
                modified_at=head.get("LastModified"),
                size_bytes=metadata.get("content_length", 0),
            )

        except Exception as e:
            logger.error(f"Failed to load S3 document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from an S3 prefix (folder)."""
        self._ensure_authenticated()

        documents = []
        prefix = folder_path.strip("/")
        if prefix:
            prefix = f"{prefix}/"

        try:
            paginator = self._client.get_paginator("list_objects_v2")

            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]

                    if key.endswith("/"):
                        continue

                    if not recursive:
                        remaining = key[len(prefix) :]
                        if "/" in remaining:
                            continue

                    doc = self.load_document(key)
                    if doc:
                        documents.append(doc)

            logger.info(
                f"Loaded {len(documents)} documents from s3://{self._bucket}/{prefix}"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to load S3 folder {folder_path}: {e}")
            return []

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for documents by filename pattern."""
        self._ensure_authenticated()

        documents = []
        query_lower = query.lower()
        prefix = self._prefix + "/" if self._prefix else ""

        try:
            paginator = self._client.get_paginator("list_objects_v2")

            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]

                    if query_lower in key.lower():
                        doc = self.load_document(key)
                        if doc:
                            documents.append(doc)
                            if len(documents) >= max_results:
                                break

                if len(documents) >= max_results:
                    break

            logger.info(f"Found {len(documents)} documents matching '{query}'")
            return documents

        except Exception as e:
            logger.error(f"S3 search failed: {e}")
            return []

    def list_folders(self, prefix: str = "") -> list[dict[str, str]]:
        """List 'folders' (common prefixes) in a prefix."""
        self._ensure_authenticated()

        folders = []
        prefix = prefix.strip("/")
        if prefix:
            prefix = f"{prefix}/"

        try:
            response = self._client.list_objects_v2(
                Bucket=self._bucket, Prefix=prefix, Delimiter="/"
            )

            for cp in response.get("CommonPrefixes", []):
                folder_path = cp["Prefix"].rstrip("/")
                folder_name = folder_path.split("/")[-1]
                folders.append({"name": folder_name, "path": folder_path})

            return folders

        except Exception as e:
            logger.error(f"Failed to list S3 folders: {e}")
            return []

    def upload_document(
        self,
        key: str,
        content: str,
        content_type: str = "text/plain",
        metadata: Optional[dict[str, str]] = None,
    ) -> bool:
        """Upload a document to S3."""
        self._ensure_authenticated()

        try:
            put_kwargs = {
                "Bucket": self._bucket,
                "Key": key,
                "Body": content.encode("utf-8"),
                "ContentType": content_type,
            }

            if metadata:
                put_kwargs["Metadata"] = metadata

            self._client.put_object(**put_kwargs)
            logger.info(f"Uploaded document to s3://{self._bucket}/{key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return False

    def delete_document(self, key: str) -> bool:
        """Delete a document from S3."""
        self._ensure_authenticated()

        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            logger.info(f"Deleted s3://{self._bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete S3 object: {e}")
            return False


class GCSLoader(BaseLoader):
    """Load documents from Google Cloud Storage.

    Environment Variables:
        GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON

    Example:
        loader = GCSLoader(
            bucket="my-documents",
            credentials_path="service-account.json"
        )
        docs = loader.load_folder("reports/")
    """

    def __init__(
        self,
        bucket: str,
        credentials_path: Optional[str] = None,
        max_file_size_mb: int = 50,
    ):
        if not GCS_AVAILABLE:
            raise ImportError(
                "Google Cloud Storage SDK not installed. Run: pip install google-cloud-storage"
            )

        self.bucket_name = bucket
        self.credentials_path = credentials_path
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self._client = None
        self._bucket = None

    @property
    def source_name(self) -> str:
        return "gcs"

    def authenticate(self) -> bool:
        """Authenticate with Google Cloud Storage."""
        try:
            if self.credentials_path:
                self._client = gcs_storage.Client.from_service_account_json(
                    self.credentials_path
                )
            else:
                self._client = gcs_storage.Client()

            self._bucket = self._client.bucket(self.bucket_name)
            self._bucket.exists()
            logger.info(f"GCS authentication successful for {self.bucket_name}")
            return True
        except Exception as e:
            logger.error(f"GCS authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._bucket and not self.authenticate():
            raise RuntimeError("Failed to authenticate with GCS")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single object by path."""
        self._ensure_authenticated()
        try:
            blob = self._bucket.blob(doc_id)
            blob.reload()

            if blob.size > self.max_file_size:
                logger.warning(f"Skipping large object: {doc_id}")
                return None

            content_bytes = blob.download_as_bytes()
            mime_type = blob.content_type or "application/octet-stream"

            if mime_type == "application/pdf":
                content = self._extract_text_from_pdf(content_bytes)
            elif mime_type.startswith("text/") or mime_type == "application/json":
                content = content_bytes.decode("utf-8", errors="replace")
            else:
                logger.debug(f"Skipping unsupported type: {mime_type}")
                return None

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=Path(doc_id).name,
                mime_type=mime_type,
                created_at=blob.time_created,
                modified_at=blob.updated,
                size_bytes=blob.size,
                metadata={"bucket": self.bucket_name, "object_path": doc_id},
            )
        except Exception as e:
            logger.error(f"Failed to load object {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a prefix."""
        self._ensure_authenticated()
        docs = []
        prefix = folder_path.strip("/") + "/" if folder_path else ""
        delimiter = None if recursive else "/"

        try:
            blobs = self._client.list_blobs(
                self.bucket_name, prefix=prefix, delimiter=delimiter
            )
            for blob in blobs:
                doc = self.load_document(blob.name)
                if doc:
                    docs.append(doc)
        except Exception as e:
            logger.error(f"Failed to load folder {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search objects by name pattern."""
        self._ensure_authenticated()
        docs = []
        count = 0

        try:
            blobs = self._client.list_blobs(self.bucket_name)
            for blob in blobs:
                if query.lower() in blob.name.lower():
                    doc = self.load_document(blob.name)
                    if doc:
                        docs.append(doc)
                        count += 1
                        if count >= max_results:
                            break
        except Exception as e:
            logger.error(f"GCS search failed: {e}")

        return docs


class AzureBlobLoader(BaseLoader):
    """Load documents from Azure Blob Storage.

    Environment Variables:
        AZURE_STORAGE_CONNECTION_STRING: Full connection string
        AZURE_STORAGE_ACCOUNT_NAME: Account name (with AZURE_STORAGE_ACCOUNT_KEY)
        AZURE_STORAGE_ACCOUNT_KEY: Account key

    Example:
        loader = AzureBlobLoader(
            connection_string="DefaultEndpointsProtocol=https;AccountName=...",
            container="documents"
        )
        docs = loader.load_folder("reports/2024/")
    """

    def __init__(
        self,
        container: str,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
        max_file_size_mb: int = 50,
    ):
        if not AZURE_BLOB_AVAILABLE:
            raise ImportError(
                "Azure SDK not installed. Run: pip install azure-storage-blob"
            )

        self.container_name = container
        self.connection_string = connection_string or os.environ.get(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        self.account_name = account_name or os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
        self.account_key = account_key or os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self._client = None
        self._container_client = None

    @property
    def source_name(self) -> str:
        return "azure_blob"

    def authenticate(self) -> bool:
        """Authenticate with Azure Blob Storage."""
        try:
            if self.connection_string:
                self._client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            elif self.account_name and self.account_key:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self._client = BlobServiceClient(
                    account_url=account_url, credential=self.account_key
                )
            else:
                raise ValueError(
                    "Provide connection_string or account_name/account_key"
                )

            self._container_client = self._client.get_container_client(
                self.container_name
            )
            self._container_client.exists()
            logger.info(
                f"Azure Blob authentication successful for {self.container_name}"
            )
            return True
        except Exception as e:
            logger.error(f"Azure Blob authentication failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._container_client and not self.authenticate():
            raise RuntimeError("Failed to authenticate with Azure Blob Storage")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single blob by path."""
        self._ensure_authenticated()
        try:
            blob_client = self._container_client.get_blob_client(doc_id)
            props = blob_client.get_blob_properties()

            if props.size > self.max_file_size:
                logger.warning(f"Skipping large blob: {doc_id}")
                return None

            content_bytes = blob_client.download_blob().readall()
            mime_type, _ = mimetypes.guess_type(doc_id)
            mime_type = mime_type or "application/octet-stream"

            if mime_type == "application/pdf":
                content = self._extract_text_from_pdf(content_bytes)
            elif mime_type.startswith("text/") or mime_type == "application/json":
                content = content_bytes.decode("utf-8", errors="replace")
            else:
                logger.debug(f"Skipping unsupported type: {mime_type}")
                return None

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=Path(doc_id).name,
                mime_type=mime_type,
                created_at=props.creation_time,
                modified_at=props.last_modified,
                size_bytes=props.size,
                metadata={"container": self.container_name, "blob_path": doc_id},
            )
        except Exception as e:
            logger.error(f"Failed to load blob {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a blob prefix."""
        self._ensure_authenticated()
        docs = []
        prefix = folder_path.strip("/") + "/" if folder_path else ""

        try:
            blobs = self._container_client.list_blobs(name_starts_with=prefix)
            for blob in blobs:
                if not recursive and "/" in blob.name[len(prefix) :]:
                    continue
                doc = self.load_document(blob.name)
                if doc:
                    docs.append(doc)
        except Exception as e:
            logger.error(f"Failed to load folder {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search blobs by name pattern."""
        self._ensure_authenticated()
        docs = []
        count = 0

        try:
            blobs = self._container_client.list_blobs()
            for blob in blobs:
                if query.lower() in blob.name.lower():
                    doc = self.load_document(blob.name)
                    if doc:
                        docs.append(doc)
                        count += 1
                        if count >= max_results:
                            break
        except Exception as e:
            logger.error(f"Azure Blob search failed: {e}")

        return docs


class MinIOLoader(S3Loader):
    """Load documents from MinIO (self-hosted S3-compatible storage).

    Example:
        loader = MinIOLoader(
            bucket="documents",
            endpoint_url="http://minio.local:9000",
            access_key="minioadmin",
            secret_key="minioadmin"
        )
        docs = loader.load_folder("reports/")
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: str = "http://localhost:9000",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: bool = False,
        **kwargs,
    ):
        super().__init__(
            bucket=bucket,
            endpoint_url=endpoint_url,
            access_key=access_key or os.environ.get("MINIO_ACCESS_KEY"),
            secret_key=secret_key or os.environ.get("MINIO_SECRET_KEY"),
            **kwargs,
        )

    @property
    def source_name(self) -> str:
        return "minio"


__all__ = [
    "S3Loader",
    "GCSLoader",
    "AzureBlobLoader",
    "MinIOLoader",
]
