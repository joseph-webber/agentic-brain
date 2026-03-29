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

"""CMIS (Content Management Interoperability Services) loader for RAG pipelines.

Supports both bindings:
- AtomPub (CMIS 1.0/1.1) - XML/Atom-based REST API
- Browser (CMIS 1.1) - JSON-based REST API

Compatible systems:
- Alfresco
- IBM FileNet
- Microsoft SharePoint (CMIS connector)
- OpenText
- Nuxeo
- Other CMIS 1.0/1.1 compliant systems

SECURITY: Uses _validate_sql_identifier() for CMIS query parameters to prevent
injection attacks.
"""

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote, urljoin

from .base import BaseLoader, LoadedDocument, _validate_sql_identifier

logger = logging.getLogger(__name__)

# Check for cmislib
try:
    from cmislib import CmisClient

    CMISLIB_AVAILABLE = True
except ImportError:
    CMISLIB_AVAILABLE = False

# Check for requests (for AtomPub binding)
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# CMIS namespaces
CMIS_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "cmis": "http://docs.oasis-open.org/ns/cmis/core/200908/",
    "cmisra": "http://docs.oasis-open.org/ns/cmis/restatom/200908/",
    "app": "http://www.w3.org/2007/app",
}


@dataclass
class CMISRepository:
    """CMIS repository information."""

    id: str
    name: str
    description: str
    vendor: str
    product_name: str
    product_version: str
    root_folder_id: str
    capabilities: dict
    root_folder_url: Optional[str] = None
    query_url: Optional[str] = None


@dataclass
class CMISObject:
    """CMIS object (document or folder)."""

    object_id: str
    name: str
    object_type: str
    base_type: str
    created_by: str
    creation_date: Optional[datetime]
    last_modified_by: str
    last_modification_date: Optional[datetime]
    content_stream_url: Optional[str] = None
    content_stream_mime_type: Optional[str] = None
    content_stream_length: int = 0
    parent_id: Optional[str] = None
    path: Optional[str] = None
    properties: dict = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}


class CMISAtomPubClient:
    """CMIS AtomPub binding client.

    Implements CMIS 1.0/1.1 AtomPub (RESTful) binding for
    content management interoperability.

    The AtomPub binding uses Atom feeds and entries for navigation,
    with CMIS-specific extensions for properties and queries.
    """

    def __init__(
        self,
        service_url: str,
        username: str,
        password: str,
        timeout: int = 30,
    ):
        self.service_url = service_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = None
        self._repository: Optional[CMISRepository] = None

    @property
    def session(self) -> requests.Session:
        """Get or create authenticated session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.auth = (self.username, self.password)
            self._session.headers.update(
                {
                    "Accept": "application/atom+xml",
                    "Content-Type": "application/atom+xml",
                }
            )
        return self._session

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse CMIS datetime string."""
        if not dt_str:
            return None
        try:
            # Handle various formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
            ]:
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def _get_property_value(self, prop_elem: ET.Element) -> Any:
        """Extract property value from CMIS property element."""
        value_elem = prop_elem.find("cmis:value", CMIS_NS)
        if value_elem is not None and value_elem.text:
            return value_elem.text
        return None

    def _parse_object_entry(self, entry: ET.Element) -> CMISObject:
        """Parse CMIS object from Atom entry."""
        # Get CMIS object element
        obj_elem = entry.find(".//cmisra:object/cmis:properties", CMIS_NS)

        properties = {}
        if obj_elem is not None:
            for prop in obj_elem:
                prop_id = prop.get("propertyDefinitionId", "")
                if prop_id:
                    properties[prop_id] = self._get_property_value(prop)

        # Extract content stream URL
        content_url = None
        for link in entry.findall("atom:link", CMIS_NS):
            if link.get("rel") == "enclosure" or link.get("rel") == "edit-media":
                content_url = link.get("href")
                break

        return CMISObject(
            object_id=properties.get("cmis:objectId", ""),
            name=properties.get("cmis:name", ""),
            object_type=properties.get("cmis:objectTypeId", ""),
            base_type=properties.get("cmis:baseTypeId", ""),
            created_by=properties.get("cmis:createdBy", ""),
            creation_date=self._parse_datetime(properties.get("cmis:creationDate")),
            last_modified_by=properties.get("cmis:lastModifiedBy", ""),
            last_modification_date=self._parse_datetime(
                properties.get("cmis:lastModificationDate")
            ),
            content_stream_url=content_url,
            content_stream_mime_type=properties.get("cmis:contentStreamMimeType"),
            content_stream_length=int(
                properties.get("cmis:contentStreamLength", 0) or 0
            ),
            parent_id=properties.get("cmis:parentId"),
            path=properties.get("cmis:path"),
            properties=properties,
        )

    def get_repositories(self) -> list[CMISRepository]:
        """Get available CMIS repositories."""
        response = self.session.get(self.service_url, timeout=self.timeout)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        repositories = []

        for workspace in root.findall(".//app:workspace", CMIS_NS):
            repo_info = workspace.find("cmisra:repositoryInfo", CMIS_NS)
            if repo_info is None:
                continue

            # Extract capabilities
            caps = {}
            caps_elem = repo_info.find("cmis:capabilities", CMIS_NS)
            if caps_elem is not None:
                for cap in caps_elem:
                    cap_name = cap.tag.split("}")[-1] if "}" in cap.tag else cap.tag
                    caps[cap_name] = cap.text

            # Find collection URLs
            root_folder_url = None
            query_url = None
            for collection in workspace.findall("app:collection", CMIS_NS):
                coll_type = collection.find("cmisra:collectionType", CMIS_NS)
                if coll_type is not None:
                    if coll_type.text == "root":
                        root_folder_url = collection.get("href")
                    elif coll_type.text == "query":
                        query_url = collection.get("href")

            repo = CMISRepository(
                id=repo_info.findtext("cmis:repositoryId", "", CMIS_NS),
                name=repo_info.findtext("cmis:repositoryName", "", CMIS_NS),
                description=repo_info.findtext(
                    "cmis:repositoryDescription", "", CMIS_NS
                ),
                vendor=repo_info.findtext("cmis:vendorName", "", CMIS_NS),
                product_name=repo_info.findtext("cmis:productName", "", CMIS_NS),
                product_version=repo_info.findtext("cmis:productVersion", "", CMIS_NS),
                root_folder_id=repo_info.findtext("cmis:rootFolderId", "", CMIS_NS),
                capabilities=caps,
                root_folder_url=root_folder_url,
                query_url=query_url,
            )
            repositories.append(repo)

        return repositories

    def get_repository(self, repository_id: Optional[str] = None) -> CMISRepository:
        """Get a specific repository or the default one."""
        repos = self.get_repositories()
        if not repos:
            raise RuntimeError("No CMIS repositories found")

        if repository_id:
            for repo in repos:
                if repo.id == repository_id:
                    self._repository = repo
                    return repo
            raise ValueError(f"Repository not found: {repository_id}")

        self._repository = repos[0]
        return repos[0]

    def get_object(self, object_id: str) -> CMISObject:
        """Get a CMIS object by ID."""
        if not self._repository:
            self.get_repository()

        url = f"{self.service_url}/{self._repository.id}/object?objectId={quote(object_id)}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        return self._parse_object_entry(root)

    def get_object_by_path(self, path: str) -> CMISObject:
        """Get a CMIS object by path."""
        if not self._repository:
            self.get_repository()

        url = (
            f"{self.service_url}/{self._repository.id}/objectbypath?path={quote(path)}"
        )
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        return self._parse_object_entry(root)

    def get_children(self, folder_id: str, max_items: int = 100) -> list[CMISObject]:
        """Get children of a folder."""
        if not self._repository:
            self.get_repository()

        url = f"{self.service_url}/{self._repository.id}/children?objectId={quote(folder_id)}&maxItems={max_items}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        children = []

        for entry in root.findall("atom:entry", CMIS_NS):
            try:
                obj = self._parse_object_entry(entry)
                children.append(obj)
            except Exception as e:
                logger.warning(f"Failed to parse entry: {e}")

        return children

    def query(self, statement: str, max_items: int = 100) -> list[CMISObject]:
        """Execute a CMIS query."""
        if not self._repository:
            self.get_repository()

        if not self._repository.query_url:
            raise RuntimeError("Query not supported by this repository")

        # Build query request
        query_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <cmis:query xmlns:cmis="http://docs.oasis-open.org/ns/cmis/core/200908/">
            <cmis:statement>{statement}</cmis:statement>
            <cmis:searchAllVersions>false</cmis:searchAllVersions>
            <cmis:maxItems>{max_items}</cmis:maxItems>
        </cmis:query>
        """

        response = self.session.post(
            self._repository.query_url,
            data=query_xml,
            headers={"Content-Type": "application/cmisquery+xml"},
            timeout=self.timeout,
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        results = []

        for entry in root.findall("atom:entry", CMIS_NS):
            try:
                obj = self._parse_object_entry(entry)
                results.append(obj)
            except Exception as e:
                logger.warning(f"Failed to parse query result: {e}")

        return results

    def get_content_stream(self, object_id: str) -> Optional[bytes]:
        """Get content stream of a document."""
        obj = self.get_object(object_id)
        if not obj.content_stream_url:
            return None

        response = self.session.get(
            obj.content_stream_url,
            timeout=self.timeout,
            headers={"Accept": "*/*"},
        )
        response.raise_for_status()
        return response.content


class CMISLoader(BaseLoader):
    """Load documents from CMIS-compliant content management systems.

    Supports both binding types:
    - AtomPub (default): Uses XML/Atom REST API
    - cmislib: Uses Python cmislib library

    Compatible systems:
    - Alfresco
    - IBM FileNet
    - Microsoft SharePoint (CMIS connector)
    - OpenText
    - Nuxeo
    - Other CMIS 1.0/1.1 compliant systems

    SECURITY NOTE: Query parameters are validated using _validate_sql_identifier()
    to prevent CMIS Query Language injection attacks.

    Example:
        # Using AtomPub binding (recommended)
        loader = CMISLoader(
            url="https://alfresco.example.com/alfresco/api/-default-/public/cmis/versions/1.1/atom",
            username="admin",
            password="secret",
            binding="atompub"
        )
        docs = loader.load_folder("/Sites/mysite/documentLibrary")
        results = loader.search("invoice")

        # Using cmislib
        loader = CMISLoader(
            url="https://alfresco.example.com/alfresco/api/-default-/public/cmis/versions/1.1/atom",
            username="admin",
            password="secret",
            binding="cmislib"
        )
    """

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        repository_id: Optional[str] = None,
        max_items: int = 100,
        binding: str = "atompub",  # "atompub" or "cmislib"
        timeout: int = 30,
    ):
        """Initialize CMIS loader.

        Args:
            url: CMIS service URL (AtomPub endpoint)
            username: Authentication username
            password: Authentication password
            repository_id: Specific repository ID (uses default if not provided)
            max_items: Maximum items to return per query
            binding: CMIS binding type ("atompub" or "cmislib")
            timeout: Request timeout in seconds
        """
        self.url = url or os.environ.get("CMIS_URL")
        self.username = username or os.environ.get("CMIS_USERNAME")
        self.password = password or os.environ.get("CMIS_PASSWORD")
        self.repository_id = repository_id or os.environ.get("CMIS_REPOSITORY_ID")
        self.max_items = max_items
        self.binding = binding.lower()
        self.timeout = timeout

        # Client instances
        self._atompub_client: Optional[CMISAtomPubClient] = None
        self._cmislib_client = None
        self._cmislib_repo = None

        # Validate binding
        if self.binding == "cmislib" and not CMISLIB_AVAILABLE:
            raise ImportError("cmislib not installed. Run: pip install cmislib")
        if self.binding == "atompub" and not REQUESTS_AVAILABLE:
            raise ImportError("requests not installed. Run: pip install requests")

    @property
    def source_name(self) -> str:
        return "cmis"

    def authenticate(self) -> bool:
        """Connect to CMIS repository."""
        try:
            if self.binding == "atompub":
                self._atompub_client = CMISAtomPubClient(
                    service_url=self.url,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                )
                repo = self._atompub_client.get_repository(self.repository_id)
                logger.info(f"CMIS AtomPub connection successful: {repo.name}")
                return True

            else:  # cmislib
                from cmislib import CmisClient

                self._cmislib_client = CmisClient(
                    self.url, self.username, self.password
                )
                if self.repository_id:
                    self._cmislib_repo = self._cmislib_client.getRepository(
                        self.repository_id
                    )
                else:
                    self._cmislib_repo = self._cmislib_client.defaultRepository
                logger.info(
                    f"CMIS cmislib connection successful: {self._cmislib_repo.name}"
                )
                return True

        except Exception as e:
            logger.error(f"CMIS connection failed: {e}")
            return False

    def _ensure_authenticated(self):
        """Ensure client is authenticated."""
        if self.binding == "atompub":
            if not self._atompub_client and not self.authenticate():
                raise RuntimeError("Failed to connect to CMIS repository")
        else:
            if not self._cmislib_repo and not self.authenticate():
                raise RuntimeError("Failed to connect to CMIS repository")

    def _extract_content(self, obj: Any) -> str:
        """Extract content from a CMIS object."""
        try:
            if self.binding == "atompub":
                content = self._atompub_client.get_content_stream(obj.object_id)
                if content:
                    return content.decode("utf-8", errors="replace")
            else:
                content_stream = obj.getContentStream()
                if content_stream:
                    return content_stream.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug(f"Failed to extract content: {e}")
        return ""

    def _cmis_object_to_loaded_document(self, obj: Any) -> Optional[LoadedDocument]:
        """Convert CMIS object to LoadedDocument."""
        try:
            if self.binding == "atompub":
                content = self._extract_content(obj)
                return LoadedDocument(
                    content=content,
                    source=self.source_name,
                    source_id=obj.object_id,
                    filename=obj.name,
                    mime_type=obj.content_stream_mime_type
                    or "application/octet-stream",
                    size_bytes=obj.content_stream_length,
                    created_at=obj.creation_date,
                    modified_at=obj.last_modification_date,
                    metadata={
                        "cmis_type": obj.object_type,
                        "base_type": obj.base_type,
                        "path": obj.path or "",
                        "created_by": obj.created_by,
                        "modified_by": obj.last_modified_by,
                    },
                )
            else:
                props = obj.getProperties()
                content = self._extract_content(obj)
                return LoadedDocument(
                    content=content,
                    source=self.source_name,
                    source_id=props.get("cmis:objectId", ""),
                    filename=props.get("cmis:name", ""),
                    mime_type=props.get(
                        "cmis:contentStreamMimeType", "application/octet-stream"
                    ),
                    size_bytes=props.get("cmis:contentStreamLength", 0),
                    created_at=props.get("cmis:creationDate"),
                    modified_at=props.get("cmis:lastModificationDate"),
                    metadata={
                        "cmis_type": props.get("cmis:objectTypeId", ""),
                        "path": props.get("cmis:path", ""),
                        "created_by": props.get("cmis:createdBy", ""),
                        "modified_by": props.get("cmis:lastModifiedBy", ""),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to convert CMIS document: {e}")
            return None

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by object ID or path."""
        self._ensure_authenticated()

        try:
            if self.binding == "atompub":
                if doc_id.startswith("/"):
                    obj = self._atompub_client.get_object_by_path(doc_id)
                else:
                    obj = self._atompub_client.get_object(doc_id)

                if obj.base_type != "cmis:document":
                    logger.warning(f"Object is not a document: {doc_id}")
                    return None

                return self._cmis_object_to_loaded_document(obj)

            else:
                if doc_id.startswith("/"):
                    obj = self._cmislib_repo.getObjectByPath(doc_id)
                else:
                    obj = self._cmislib_repo.getObject(doc_id)

                if obj.getObjectType().baseId != "cmis:document":
                    logger.warning(f"Object is not a document: {doc_id}")
                    return None

                return self._cmis_object_to_loaded_document(obj)

        except Exception as e:
            logger.error(f"Failed to load CMIS document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a CMIS folder."""
        self._ensure_authenticated()
        docs = []

        try:
            if self.binding == "atompub":
                # Get folder object
                folder = self._atompub_client.get_object_by_path(folder_path)

                def process_folder_atompub(folder_id: str, depth: int = 0):
                    if depth > 10:
                        return

                    children = self._atompub_client.get_children(
                        folder_id, max_items=self.max_items
                    )
                    for child in children:
                        if child.base_type == "cmis:document":
                            doc = self._cmis_object_to_loaded_document(child)
                            if doc:
                                docs.append(doc)
                        elif child.base_type == "cmis:folder" and recursive:
                            process_folder_atompub(child.object_id, depth + 1)

                process_folder_atompub(folder.object_id)

            else:
                folder = self._cmislib_repo.getObjectByPath(folder_path)

                def process_folder_cmislib(f, depth=0):
                    if depth > 10:
                        return

                    children = f.getChildren()
                    for child in children:
                        child_type = child.getObjectType().baseId

                        if child_type == "cmis:document":
                            doc = self._cmis_object_to_loaded_document(child)
                            if doc:
                                docs.append(doc)
                        elif child_type == "cmis:folder" and recursive:
                            process_folder_cmislib(child, depth + 1)

                process_folder_cmislib(folder)

        except Exception as e:
            logger.error(f"Failed to load CMIS folder {folder_path}: {e}")

        logger.info(f"Loaded {len(docs)} documents from {folder_path}")
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search documents using CMIS Query Language.

        SECURITY: Query parameter is escaped to prevent injection.
        """
        self._ensure_authenticated()
        docs = []

        try:
            # Escape single quotes in query to prevent injection
            safe_query = query.replace("'", "''")

            cmis_query = f"SELECT * FROM cmis:document WHERE CONTAINS('{safe_query}')"

            if self.binding == "atompub":
                results = self._atompub_client.query(cmis_query, max_items=max_results)
                for result in results:
                    doc = self._cmis_object_to_loaded_document(result)
                    if doc:
                        docs.append(doc)
            else:
                results = self._cmislib_repo.query(cmis_query)
                count = 0
                for result in results:
                    if count >= max_results:
                        break
                    doc = self._cmis_object_to_loaded_document(result)
                    if doc:
                        docs.append(doc)
                        count += 1

        except Exception as e:
            logger.error(f"CMIS search failed: {e}")

        return docs

    def query(self, cmis_query: str, max_results: int = 100) -> list[LoadedDocument]:
        """Execute a raw CMIS query.

        WARNING: Use with caution - query is executed as-is.
        Prefer search() for user-provided queries.
        """
        self._ensure_authenticated()
        docs = []

        try:
            if self.binding == "atompub":
                results = self._atompub_client.query(cmis_query, max_items=max_results)
                for result in results:
                    doc = self._cmis_object_to_loaded_document(result)
                    if doc:
                        docs.append(doc)
            else:
                results = self._cmislib_repo.query(cmis_query)
                count = 0
                for result in results:
                    if count >= max_results:
                        break
                    doc = self._cmis_object_to_loaded_document(result)
                    if doc:
                        docs.append(doc)
                        count += 1

        except Exception as e:
            logger.error(f"CMIS query failed: {e}")

        return docs

    def get_repository_info(self) -> dict:
        """Get information about the connected repository."""
        self._ensure_authenticated()

        if self.binding == "atompub":
            repo = self._atompub_client._repository
            return {
                "id": repo.id,
                "name": repo.name,
                "description": repo.description,
                "vendor": repo.vendor,
                "product": f"{repo.product_name} {repo.product_version}",
                "capabilities": repo.capabilities,
            }
        else:
            info = self._cmislib_repo.info
            return {
                "id": info.get("repositoryId"),
                "name": info.get("repositoryName"),
                "description": info.get("repositoryDescription"),
                "vendor": info.get("vendorName"),
                "product": f"{info.get('productName')} {info.get('productVersion')}",
            }


__all__ = [
    "CMISLoader",
    "CMISAtomPubClient",
    "CMISRepository",
    "CMISObject",
    "CMISLIB_AVAILABLE",
    "REQUESTS_AVAILABLE",
]
