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

"""Factory functions for creating document loaders."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Type, Union

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Registry of loader types
_LOADER_REGISTRY: Dict[str, Type[BaseLoader]] = {}


def _register_loaders():
    """Register all available loaders."""
    global _LOADER_REGISTRY

    # Import loaders lazily to avoid circular imports
    try:
        from .google_drive import GoogleDriveLoader

        _LOADER_REGISTRY["google_drive"] = GoogleDriveLoader
        _LOADER_REGISTRY["drive"] = GoogleDriveLoader
        _LOADER_REGISTRY["gdrive"] = GoogleDriveLoader
    except ImportError:
        pass

    try:
        from .email import GmailLoader, Microsoft365Loader

        _LOADER_REGISTRY["gmail"] = GmailLoader
        _LOADER_REGISTRY["email"] = GmailLoader
        _LOADER_REGISTRY["microsoft365"] = Microsoft365Loader
        _LOADER_REGISTRY["outlook"] = Microsoft365Loader
        _LOADER_REGISTRY["office365"] = Microsoft365Loader
    except ImportError:
        pass

    try:
        from .icloud import iCloudLoader

        _LOADER_REGISTRY["icloud"] = iCloudLoader
        _LOADER_REGISTRY["icloud_drive"] = iCloudLoader
    except ImportError:
        pass

    try:
        from .cloud import AzureBlobLoader, GCSLoader, MinIOLoader, S3Loader

        _LOADER_REGISTRY["s3"] = S3Loader
        _LOADER_REGISTRY["aws_s3"] = S3Loader
        _LOADER_REGISTRY["gcs"] = GCSLoader
        _LOADER_REGISTRY["google_cloud_storage"] = GCSLoader
        _LOADER_REGISTRY["azure_blob"] = AzureBlobLoader
        _LOADER_REGISTRY["azure"] = AzureBlobLoader
        _LOADER_REGISTRY["minio"] = MinIOLoader
    except ImportError:
        pass

    try:
        from .confluence import ConfluenceLoader

        _LOADER_REGISTRY["confluence"] = ConfluenceLoader
    except ImportError:
        pass

    try:
        from .social import NotionLoader, SlackLoader

        _LOADER_REGISTRY["slack"] = SlackLoader
        _LOADER_REGISTRY["notion"] = NotionLoader
    except ImportError:
        pass

    try:
        from .github import GitHubLoader

        _LOADER_REGISTRY["github"] = GitHubLoader
        _LOADER_REGISTRY["gh"] = GitHubLoader
    except ImportError:
        pass

    try:
        from .firestore import FirestoreLoader
        from .nosql import ElasticsearchLoader, MongoDBLoader, RedisLoader

        _LOADER_REGISTRY["mongodb"] = MongoDBLoader
        _LOADER_REGISTRY["mongo"] = MongoDBLoader
        _LOADER_REGISTRY["redis"] = RedisLoader
        _LOADER_REGISTRY["elasticsearch"] = ElasticsearchLoader
        _LOADER_REGISTRY["elastic"] = ElasticsearchLoader
        _LOADER_REGISTRY["firestore"] = FirestoreLoader
        _LOADER_REGISTRY["firebase"] = FirestoreLoader  # Alias
    except ImportError:
        pass

    try:
        from .database import MySQLLoader, OracleLoader, PostgreSQLLoader

        _LOADER_REGISTRY["postgresql"] = PostgreSQLLoader
        _LOADER_REGISTRY["postgres"] = PostgreSQLLoader
        _LOADER_REGISTRY["mysql"] = MySQLLoader
        _LOADER_REGISTRY["oracle"] = OracleLoader
    except ImportError:
        pass

    try:
        from .salesforce import SalesforceLoader

        _LOADER_REGISTRY["salesforce"] = SalesforceLoader
    except ImportError:
        pass

    try:
        from .wordpress import WordPressLoader

        _LOADER_REGISTRY["wordpress"] = WordPressLoader
        _LOADER_REGISTRY["wp"] = WordPressLoader
    except ImportError:
        pass


def create_loader(loader_type: str, **kwargs: Any) -> BaseLoader:
    """Create a document loader by type name.

    Args:
        loader_type: Type of loader (e.g., "gmail", "s3", "confluence")
        **kwargs: Arguments passed to loader constructor

    Returns:
        Configured loader instance

    Raises:
        ValueError: If loader type is unknown

    Example:
        loader = create_loader("gmail", credentials_path="creds.json")
        loader = create_loader("s3", bucket="my-bucket", region="us-east-1")
        loader = create_loader("confluence", url="https://wiki.example.com")
    """
    # Ensure loaders are registered
    if not _LOADER_REGISTRY:
        _register_loaders()

    loader_type = loader_type.lower().replace("-", "_")

    if loader_type not in _LOADER_REGISTRY:
        available = sorted(_LOADER_REGISTRY.keys())
        raise ValueError(
            f"Unknown loader type: {loader_type}. "
            f"Available types: {', '.join(available)}"
        )

    loader_class = _LOADER_REGISTRY[loader_type]
    return loader_class(**kwargs)


def load_from_multiple_sources(
    sources: List[Dict[str, Any]],
    parallel: bool = True,
    max_workers: int = 5,
) -> List[LoadedDocument]:
    """Load documents from multiple sources in parallel.

    Args:
        sources: List of source configurations, each containing:
            - type: Loader type (e.g., "gmail", "s3")
            - path: Path/folder to load (optional)
            - ... other loader-specific kwargs
        parallel: Whether to load in parallel (default True)
        max_workers: Max parallel workers (default 5)

    Returns:
        List of all loaded documents from all sources

    Example:
        sources = [
            {"type": "gmail", "credentials_path": "gmail_creds.json", "days": 7},
            {"type": "s3", "bucket": "docs", "prefix": "reports/"},
            {"type": "confluence", "url": "https://wiki.co", "space": "ENG"},
        ]
        all_docs = load_from_multiple_sources(sources)
    """
    all_documents: List[LoadedDocument] = []

    def load_source(source_config: Dict[str, Any]) -> List[LoadedDocument]:
        """Load from a single source."""
        config = source_config.copy()
        loader_type = config.pop("type")
        path = config.pop("path", None)

        try:
            loader = create_loader(loader_type, **config)
            loader.authenticate()

            if path:
                return loader.load_folder(path)
            elif hasattr(loader, "load_recent"):
                return loader.load_recent()
            else:
                return []

        except Exception as e:
            logger.error(f"Failed to load from {loader_type}: {e}")
            return []

    if parallel and len(sources) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(load_source, src): src for src in sources}
            for future in as_completed(futures):
                try:
                    docs = future.result()
                    all_documents.extend(docs)
                except Exception as e:
                    logger.error(f"Source loading failed: {e}")
    else:
        for source in sources:
            docs = load_source(source)
            all_documents.extend(docs)

    return all_documents


async def load_from_multiple_sources_async(
    sources: List[Dict[str, Any]],
    max_concurrent: int = 5,
) -> List[LoadedDocument]:
    """Async version of load_from_multiple_sources.

    Args:
        sources: List of source configurations
        max_concurrent: Max concurrent loads

    Returns:
        List of all loaded documents
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    all_documents: List[LoadedDocument] = []

    async def load_source_async(source_config: Dict[str, Any]) -> List[LoadedDocument]:
        async with semaphore:
            # Run sync code in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: _load_source_sync(source_config)
            )

    def _load_source_sync(source_config: Dict[str, Any]) -> List[LoadedDocument]:
        config = source_config.copy()
        loader_type = config.pop("type")
        path = config.pop("path", None)

        try:
            loader = create_loader(loader_type, **config)
            loader.authenticate()

            if path:
                return loader.load_folder(path)
            elif hasattr(loader, "load_recent"):
                return loader.load_recent()
            else:
                return []

        except Exception as e:
            logger.error(f"Failed to load from {loader_type}: {e}")
            return []

    tasks = [load_source_async(src) for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            all_documents.extend(result)
        elif isinstance(result, Exception):
            logger.error(f"Async load failed: {result}")

    return all_documents


def get_available_loaders() -> List[str]:
    """Get list of available loader types.

    Returns:
        Sorted list of loader type names
    """
    if not _LOADER_REGISTRY:
        _register_loaders()
    return sorted(_LOADER_REGISTRY.keys())
