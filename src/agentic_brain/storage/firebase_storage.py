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

"""Firebase Storage helpers for uploads, downloads, and signed URLs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, storage

    FIREBASE_STORAGE_AVAILABLE = True
except ImportError:
    FIREBASE_STORAGE_AVAILABLE = False
    firebase_admin = None  # type: ignore[assignment]
    credentials = None  # type: ignore[assignment]
    storage = None  # type: ignore[assignment]


@dataclass(slots=True)
class StorageObject:
    """Metadata for a Firebase Storage object."""

    path: str
    bucket: str
    content_type: Optional[str] = None
    metadata: Optional[dict[str, str]] = None
    size_bytes: Optional[int] = None


class FirebaseStorageManager:
    """Manage Firebase Storage uploads and downloads."""

    def __init__(
        self,
        bucket_name: str,
        credentials_path: Optional[str] = None,
        app_name: str = "agentic-brain-storage",
    ):
        if not FIREBASE_STORAGE_AVAILABLE:
            raise ImportError(
                "firebase-admin not available. Install with: pip install firebase-admin"
            )
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self.app_name = app_name
        self._app: Any = None
        self._bucket: Any = None

    def connect(self) -> bool:
        if self._bucket is not None:
            return True
        try:
            try:
                self._app = firebase_admin.get_app(self.app_name)
            except ValueError:
                options = {"storageBucket": self.bucket_name}
                if self.credentials_path:
                    cred = credentials.Certificate(self.credentials_path)
                    self._app = firebase_admin.initialize_app(
                        cred, options=options, name=self.app_name
                    )
                else:
                    self._app = firebase_admin.initialize_app(
                        options=options, name=self.app_name
                    )
            self._bucket = storage.bucket(name=self.bucket_name, app=self._app)
            return True
        except Exception as exc:
            logger.error("Failed to connect to Firebase Storage: %s", exc)
            return False

    def _blob(self, path: str) -> Any:
        self.connect()
        return self._bucket.blob(path)

    def upload_file(
        self,
        source_path: str,
        destination_path: str,
        *,
        metadata: Optional[dict[str, str]] = None,
        content_type: Optional[str] = None,
    ) -> StorageObject:
        blob = self._blob(destination_path)
        if metadata:
            blob.metadata = metadata
        blob.upload_from_filename(source_path, content_type=content_type)
        size = Path(source_path).stat().st_size if Path(source_path).exists() else None
        return StorageObject(
            path=destination_path,
            bucket=self.bucket_name,
            content_type=content_type,
            metadata=metadata,
            size_bytes=size,
        )

    def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        *,
        metadata: Optional[dict[str, str]] = None,
        content_type: Optional[str] = None,
    ) -> StorageObject:
        blob = self._blob(destination_path)
        if metadata:
            blob.metadata = metadata
        blob.upload_from_string(data, content_type=content_type)
        return StorageObject(
            path=destination_path,
            bucket=self.bucket_name,
            content_type=content_type,
            metadata=metadata,
            size_bytes=len(data),
        )

    def download_file(self, source_path: str, destination_path: str) -> Path:
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._blob(source_path).download_to_filename(str(destination))
        return destination

    def create_resumable_upload(
        self, destination_path: str, chunk_size: int = 8 * 1024 * 1024
    ) -> Any:
        blob = self._blob(destination_path)
        blob.chunk_size = chunk_size
        return blob

    def upload_resumable(
        self,
        source_path: str,
        destination_path: str,
        *,
        metadata: Optional[dict[str, str]] = None,
        content_type: Optional[str] = None,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> StorageObject:
        blob = self.create_resumable_upload(destination_path, chunk_size=chunk_size)
        if metadata:
            blob.metadata = metadata
        blob.upload_from_filename(source_path, content_type=content_type)
        size = Path(source_path).stat().st_size if Path(source_path).exists() else None
        return StorageObject(
            path=destination_path,
            bucket=self.bucket_name,
            content_type=content_type,
            metadata=metadata,
            size_bytes=size,
        )

    def get_signed_url(
        self, source_path: str, *, expiration_seconds: int = 3600, method: str = "GET"
    ) -> str:
        return self._blob(source_path).generate_signed_url(
            expiration=timedelta(seconds=expiration_seconds), method=method
        )

    def process_image(
        self,
        source_path: str,
        destination_path: str,
        processor: Callable[[bytes], bytes],
        *,
        metadata: Optional[dict[str, str]] = None,
        content_type: str = "image/png",
    ) -> StorageObject:
        image_bytes = self._blob(source_path).download_as_bytes()
        processed = processor(image_bytes)
        return self.upload_bytes(
            processed, destination_path, metadata=metadata, content_type=content_type
        )
