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

"""Customer support and helpdesk loaders for RAG pipelines.

Supports:
- Zendesk (ticketing)
- Intercom (customer communication)
- Freshdesk (helpdesk)
- HubSpot (CRM + support)
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for Zendesk
try:
    from zenpy import Zenpy
    from zenpy.lib.exception import ZenpyException

    ZENDESK_AVAILABLE = True
except ImportError:
    ZENDESK_AVAILABLE = False

# Check for Intercom
try:
    from intercom import Client

    INTERCOM_AVAILABLE = True
except ImportError:
    INTERCOM_AVAILABLE = False

# Check for HubSpot
try:
    from hubspot import HubSpot

    HUBSPOT_AVAILABLE = True
except ImportError:
    HUBSPOT_AVAILABLE = False


class ZendeskLoader(BaseLoader):
    """Document loader for Zendesk support tickets.

    Load tickets and comments from Zendesk.

    Features:
    - Load tickets and comments
    - Search tickets
    - Load ticket attachments
    - Support for custom fields

    Requirements:
        pip install zenpy

    Environment variables:
        ZENDESK_EMAIL: Agent email
        ZENDESK_TOKEN: API token
        ZENDESK_SUBDOMAIN: Zendesk subdomain

    Example:
        loader = ZendeskLoader(email="x", token="y", subdomain="company")
        loader.authenticate()
        docs = loader.load_tickets(status="open")
    """

    def __init__(
        self,
        email: Optional[str] = None,
        token: Optional[str] = None,
        subdomain: Optional[str] = None,
        **kwargs,
    ):
        """Initialize Zendesk loader.

        Args:
            email: Agent email
            token: API token
            subdomain: Zendesk subdomain
        """
        if not ZENDESK_AVAILABLE:
            raise ImportError(
                "zenpy is required for ZendeskLoader. "
                "Install with: pip install zenpy"
            )

        self._email = email or os.environ.get("ZENDESK_EMAIL")
        self._token = token or os.environ.get("ZENDESK_TOKEN")
        self._subdomain = subdomain or os.environ.get("ZENDESK_SUBDOMAIN")
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "Zendesk"

    def authenticate(self) -> bool:
        """Authenticate with Zendesk API."""
        try:
            creds = {
                "email": self._email,
                "token": self._token,
                "subdomain": self._subdomain,
            }
            self._client = Zenpy(**creds)

            # Test connection
            self._client.users.me()
            self._authenticated = True
            logger.info("Zendesk authentication successful")
            return True

        except Exception as e:
            logger.error(f"Zendesk authentication failed: {e}")
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single ticket by ID.

        Args:
            doc_id: Ticket ID

        Returns:
            LoadedDocument or None
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            ticket = self._client.tickets(id=int(doc_id))

            # Build content
            content_parts = [
                f"# Ticket #{ticket.id}: {ticket.subject}",
                "",
                f"**Status:** {ticket.status}",
                f"**Priority:** {ticket.priority}",
                f"**Requester:** {ticket.requester.name if ticket.requester else 'Unknown'}",
                f"**Assignee:** {ticket.assignee.name if ticket.assignee else 'Unassigned'}",
                "",
                "## Description",
                ticket.description or "(No description)",
            ]

            # Add comments
            comments = list(self._client.tickets.comments(ticket_id=int(doc_id)))
            if len(comments) > 1:  # First comment is description
                content_parts.append("")
                content_parts.append("## Comments")
                for comment in comments[1:]:
                    content_parts.append(
                        f"\n**{comment.author.name if comment.author else 'Unknown'}**:"
                    )
                    content_parts.append(comment.body)

            content = "\n".join(content_parts)

            return LoadedDocument(
                content=content,
                source="zendesk",
                source_id=doc_id,
                filename=f"ticket_{doc_id}.md",
                created_at=ticket.created_at,
                modified_at=ticket.updated_at,
                metadata={
                    "id": ticket.id,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "type": ticket.type,
                },
            )

        except Exception as e:
            logger.error(f"Failed to load Zendesk ticket {doc_id}: {e}")
            return None

    def load_ticket(self, ticket_id: str) -> Optional[LoadedDocument]:
        """Alias for load_document."""
        return self.load_document(ticket_id)

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load tickets with a status filter.

        Args:
            folder_path: Status filter (open, pending, solved, all)
            recursive: Not used

        Returns:
            List of LoadedDocument
        """
        return self.load_tickets(status=folder_path if folder_path != "all" else None)

    def load_tickets(
        self, status: Optional[str] = None, max_results: int = 100
    ) -> list[LoadedDocument]:
        """Load tickets from Zendesk.

        Args:
            status: Filter by status (new, open, pending, hold, solved, closed)
            max_results: Maximum tickets to return

        Returns:
            List of LoadedDocument
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            if status:
                tickets = self._client.search(type="ticket", status=status)
            else:
                tickets = self._client.tickets()

            count = 0
            for ticket in tickets:
                if count >= max_results:
                    break

                doc = self.load_document(str(ticket.id))
                if doc:
                    docs.append(doc)
                    count += 1

        except Exception as e:
            logger.error(f"Failed to load Zendesk tickets: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for tickets.

        Args:
            query: Search text
            max_results: Maximum results

        Returns:
            List of LoadedDocument
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            results = self._client.search(query, type="ticket")

            count = 0
            for ticket in results:
                if count >= max_results:
                    break

                doc = self.load_document(str(ticket.id))
                if doc:
                    docs.append(doc)
                    count += 1

        except Exception as e:
            logger.error(f"Zendesk search failed: {e}")

        return docs

    async def load_async(self, doc_id: str) -> Optional[LoadedDocument]:
        """Async document loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.load_document, doc_id)

    async def load_folder_async(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Async folder loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.load_folder, folder_path, recursive
        )


# ============================================================================
# INTERCOM LOADER
# ============================================================================

# Check for intercom availability
try:
    import intercom
    from intercom.client import Client as IntercomClient

    INTERCOM_AVAILABLE = True
except ImportError:
    INTERCOM_AVAILABLE = False


class IntercomLoader(BaseLoader):
    """Document loader for Intercom conversations.

    Load conversations and messages from Intercom.

    Features:
    - Load conversations
    - Load conversation messages
    - Search conversations
    - Support for contacts

    Requirements:
        pip install python-intercom

    Environment variables:
        INTERCOM_ACCESS_TOKEN: Access token

    Example:
        loader = IntercomLoader(token="xxx")
        loader.authenticate()
        docs = loader.load_conversations()
    """

    def __init__(self, token: Optional[str] = None, **kwargs):
        """Initialize Intercom loader.

        Args:
            token: Intercom access token
        """
        if not INTERCOM_AVAILABLE:
            raise ImportError(
                "python-intercom is required for IntercomLoader. "
                "Install with: pip install python-intercom"
            )

        self._token = token or os.environ.get("INTERCOM_ACCESS_TOKEN")
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "Intercom"

    def authenticate(self) -> bool:
        """Authenticate with Intercom API."""
        try:
            self._client = IntercomClient(personal_access_token=self._token)

            # Test connection
            self._client.admins.all()
            self._authenticated = True
            logger.info("Intercom authentication successful")
            return True

        except Exception as e:
            logger.error(f"Intercom authentication failed: {e}")
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single conversation by ID.

        Args:
            doc_id: Conversation ID

        Returns:
            LoadedDocument or None
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            conversation = self._client.conversations.find(id=doc_id)

            # Build content from conversation parts
            content_parts = [f"# Conversation: {doc_id}", ""]

            # Add source (first message)
            if conversation.source:
                author = (
                    conversation.source.author.name
                    if hasattr(conversation.source.author, "name")
                    else "Unknown"
                )
                content_parts.append(f"**{author}:** {conversation.source.body}")

            # Add conversation parts
            for part in conversation.conversation_parts:
                author = part.author.name if hasattr(part.author, "name") else "Unknown"
                content_parts.append(f"\n**{author}:** {part.body}")

            content = "\n".join(content_parts)

            return LoadedDocument(
                content=content,
                source="intercom",
                source_id=doc_id,
                filename=f"conversation_{doc_id}.md",
                created_at=(
                    datetime.fromtimestamp(conversation.created_at)
                    if conversation.created_at
                    else None
                ),
                modified_at=(
                    datetime.fromtimestamp(conversation.updated_at)
                    if conversation.updated_at
                    else None
                ),
                metadata={
                    "id": doc_id,
                    "state": conversation.state,
                    "read": conversation.read,
                },
            )

        except Exception as e:
            logger.error(f"Failed to load Intercom conversation {doc_id}: {e}")
            return None

    def load_conversation(self, conversation_id: str) -> Optional[LoadedDocument]:
        """Alias for load_document."""
        return self.load_document(conversation_id)

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load conversations with a state filter.

        Args:
            folder_path: State filter (open, closed, all)
            recursive: Not used

        Returns:
            List of LoadedDocument
        """
        return self.load_conversations(
            state=folder_path if folder_path != "all" else None
        )

    def load_conversations(
        self, state: Optional[str] = None, max_results: int = 100
    ) -> list[LoadedDocument]:
        """Load conversations from Intercom.

        Args:
            state: Filter by state (open, closed)
            max_results: Maximum conversations to return

        Returns:
            List of LoadedDocument
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            conversations = self._client.conversations.all()

            count = 0
            for conv in conversations:
                if count >= max_results:
                    break

                if state and conv.state != state:
                    continue

                doc = self.load_document(conv.id)
                if doc:
                    docs.append(doc)
                    count += 1

        except Exception as e:
            logger.error(f"Failed to load Intercom conversations: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for conversations.

        Args:
            query: Search text
            max_results: Maximum results

        Returns:
            List of LoadedDocument
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Intercom API doesn't support conversation search directly
        # Load all and filter locally
        logger.warning("Intercom doesn't support conversation search, loading all")
        return self.load_conversations(max_results=max_results)

    async def load_async(self, doc_id: str) -> Optional[LoadedDocument]:
        """Async document loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.load_document, doc_id)

    async def load_folder_async(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Async folder loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.load_folder, folder_path, recursive
        )


# ============================================================================
# FRESHDESK LOADER
# ============================================================================

# Check for freshdesk availability
try:
    import requests

    FRESHDESK_AVAILABLE = True  # Uses requests directly
except ImportError:
    FRESHDESK_AVAILABLE = False


class FreshdeskLoader(BaseLoader):
    """Document loader for Freshdesk support tickets.

    Load tickets and conversations from Freshdesk.

    Features:
    - Load tickets and conversations
    - Search tickets
    - Load attachments
    - Support for custom fields

    Requirements:
        pip install requests

    Environment variables:
        FRESHDESK_DOMAIN: Freshdesk domain (company.freshdesk.com)
        FRESHDESK_API_KEY: API key

    Example:
        loader = FreshdeskLoader(domain="company", api_key="xxx")
        loader.authenticate()
        docs = loader.load_tickets(status="open")
    """

    def __init__(
        self,
        domain: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """Initialize Freshdesk loader.

        Args:
            domain: Freshdesk domain (without .freshdesk.com)
            api_key: API key
        """
        self._domain = domain or os.environ.get("FRESHDESK_DOMAIN")
        self._api_key = api_key or os.environ.get("FRESHDESK_API_KEY")
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "Freshdesk"

    def authenticate(self) -> bool:
        """Authenticate with Freshdesk API."""
        try:
            import requests

            response = requests.get(
                f"https://{self._domain}.freshdesk.com/api/v2/tickets",
                auth=(self._api_key, "X"),
                params={"per_page": 1},
            )

            if response.status_code == 200:
                self._authenticated = True
                logger.info("Freshdesk authentication successful")
                return True
            else:
                logger.error(f"Freshdesk auth failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Freshdesk authentication failed: {e}")
            return False

    def _make_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Optional[Any]:
        """Make authenticated request to Freshdesk API."""
        import requests

        response = requests.get(
            f"https://{self._domain}.freshdesk.com/api/v2{endpoint}",
            auth=(self._api_key, "X"),
            params=params,
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Freshdesk API error: {response.status_code}")
            return None

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single ticket by ID.

        Args:
            doc_id: Ticket ID

        Returns:
            LoadedDocument or None
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            ticket = self._make_request(f"/tickets/{doc_id}")
            if not ticket:
                return None

            # Status mapping
            status_map = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
            priority_map = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}

            # Build content
            content_parts = [
                f"# Ticket #{ticket['id']}: {ticket['subject']}",
                "",
                f"**Status:** {status_map.get(ticket['status'], 'Unknown')}",
                f"**Priority:** {priority_map.get(ticket['priority'], 'Unknown')}",
                "",
                "## Description",
                ticket.get(
                    "description_text", ticket.get("description", "(No description)")
                ),
            ]

            # Get conversations
            conversations = self._make_request(f"/tickets/{doc_id}/conversations")
            if conversations:
                content_parts.append("")
                content_parts.append("## Conversations")
                for conv in conversations:
                    content_parts.append("\n**Message:**")
                    content_parts.append(conv.get("body_text", conv.get("body", "")))

            content = "\n".join(content_parts)

            return LoadedDocument(
                content=content,
                source="freshdesk",
                source_id=doc_id,
                filename=f"ticket_{doc_id}.md",
                created_at=(
                    datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
                    if ticket.get("created_at")
                    else None
                ),
                modified_at=(
                    datetime.fromisoformat(ticket["updated_at"].replace("Z", "+00:00"))
                    if ticket.get("updated_at")
                    else None
                ),
                metadata={
                    "id": ticket["id"],
                    "status": status_map.get(ticket["status"], "Unknown"),
                    "priority": priority_map.get(ticket["priority"], "Unknown"),
                },
            )

        except Exception as e:
            logger.error(f"Failed to load Freshdesk ticket {doc_id}: {e}")
            return None

    def load_ticket(self, ticket_id: str) -> Optional[LoadedDocument]:
        """Alias for load_document."""
        return self.load_document(ticket_id)

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load tickets with a status filter.

        Args:
            folder_path: Status filter (open, pending, resolved, closed, all)
            recursive: Not used

        Returns:
            List of LoadedDocument
        """
        status_map = {"open": 2, "pending": 3, "resolved": 4, "closed": 5}
        status = (
            status_map.get(folder_path.lower())
            if folder_path.lower() != "all"
            else None
        )
        return self.load_tickets(status=status)

    def load_tickets(
        self, status: Optional[int] = None, max_results: int = 100
    ) -> list[LoadedDocument]:
        """Load tickets from Freshdesk.

        Args:
            status: Filter by status (2=Open, 3=Pending, 4=Resolved, 5=Closed)
            max_results: Maximum tickets to return

        Returns:
            List of LoadedDocument
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            params = {"per_page": min(max_results, 100)}
            if status:
                params["filter"] = f"status:{status}"

            tickets = self._make_request("/tickets", params=params)
            if not tickets:
                return docs

            for ticket in tickets[:max_results]:
                doc = self.load_document(str(ticket["id"]))
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load Freshdesk tickets: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for tickets.

        Args:
            query: Search text
            max_results: Maximum results

        Returns:
            List of LoadedDocument
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            # Freshdesk search endpoint
            results = self._make_request(
                "/search/tickets", params={"query": f'"{query}"'}
            )
            if not results or "results" not in results:
                return docs

            for ticket in results["results"][:max_results]:
                doc = self.load_document(str(ticket["id"]))
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Freshdesk search failed: {e}")

        return docs

    async def load_async(self, doc_id: str) -> Optional[LoadedDocument]:
        """Async document loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.load_document, doc_id)

    async def load_folder_async(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Async folder loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.load_folder, folder_path, recursive
        )


# ============================================================================
# CLOUD STORAGE LOADERS
# ============================================================================

# Azure Blob Storage
try:
    from azure.storage.blob import BlobServiceClient

    AZURE_BLOB_AVAILABLE = True
except ImportError:
    AZURE_BLOB_AVAILABLE = False


class HubSpotLoader(BaseLoader):
    """Document loader for HubSpot CRM.

    Load contacts, deals, and tickets from HubSpot.

    Features:
    - Load contacts, companies, deals
    - Load tickets
    - Search across CRM
    - Support for custom properties

    Requirements:
        pip install hubspot-api-client

    Environment variables:
        HUBSPOT_API_KEY: API key

    Example:
        loader = HubSpotLoader(api_key="xxx")
        loader.authenticate()
        docs = loader.load_contacts(max_results=100)
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize HubSpot loader.

        Args:
            api_key: HubSpot API key
        """
        if not HUBSPOT_AVAILABLE:
            raise ImportError(
                "hubspot-api-client is required for HubSpotLoader. "
                "Install with: pip install hubspot-api-client"
            )

        self._api_key = api_key or os.environ.get("HUBSPOT_API_KEY")
        self._client: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "HubSpot"

    def authenticate(self) -> bool:
        """Authenticate with HubSpot API."""
        try:
            self._client = HubSpot(api_key=self._api_key)

            # Test connection
            self._client.crm.contacts.basic_api.get_page(limit=1)
            self._authenticated = True
            logger.info("HubSpot authentication successful")
            return True

        except Exception as e:
            logger.error(f"HubSpot authentication failed: {e}")
            return False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single CRM object.

        Args:
            doc_id: Object ID in format "type:id" (e.g., "contact:123")

        Returns:
            LoadedDocument or None
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            obj_type, obj_id = doc_id.split(":", 1)

            if obj_type == "contact":
                obj = self._client.crm.contacts.basic_api.get_by_id(obj_id)
            elif obj_type == "company":
                obj = self._client.crm.companies.basic_api.get_by_id(obj_id)
            elif obj_type == "deal":
                obj = self._client.crm.deals.basic_api.get_by_id(obj_id)
            elif obj_type == "ticket":
                obj = self._client.crm.tickets.basic_api.get_by_id(obj_id)
            else:
                raise ValueError(f"Unknown object type: {obj_type}")

            # Format properties as content
            content_parts = [f"# {obj_type.title()}: {obj_id}", ""]
            for prop, value in obj.properties.items():
                if value:
                    content_parts.append(f"**{prop}:** {value}")

            content = "\n".join(content_parts)

            return LoadedDocument(
                content=content,
                source="hubspot",
                source_id=doc_id,
                filename=f"{obj_type}_{obj_id}.md",
                created_at=(
                    datetime.fromisoformat(obj.created_at.replace("Z", "+00:00"))
                    if hasattr(obj, "created_at") and obj.created_at
                    else None
                ),
                modified_at=(
                    datetime.fromisoformat(obj.updated_at.replace("Z", "+00:00"))
                    if hasattr(obj, "updated_at") and obj.updated_at
                    else None
                ),
                metadata={
                    "type": obj_type,
                    "id": obj_id,
                    "properties": list(obj.properties.keys()),
                },
            )

        except Exception as e:
            logger.error(f"Failed to load HubSpot object {doc_id}: {e}")
            return None

    def load_object(self, object_ref: str) -> Optional[LoadedDocument]:
        """Alias for load_document."""
        return self.load_document(object_ref)

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load objects of a type.

        Args:
            folder_path: Object type (contacts, companies, deals, tickets)
            recursive: Not used

        Returns:
            List of LoadedDocument
        """
        if folder_path == "contacts":
            return self.load_contacts()
        elif folder_path == "companies":
            return self.load_companies()
        elif folder_path == "deals":
            return self.load_deals()
        elif folder_path == "tickets":
            return self.load_tickets()
        else:
            logger.error(f"Unknown HubSpot object type: {folder_path}")
            return []

    def load_contacts(self, max_results: int = 100) -> list[LoadedDocument]:
        """Load contacts from HubSpot."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            response = self._client.crm.contacts.basic_api.get_page(limit=max_results)

            for contact in response.results:
                doc = self.load_document(f"contact:{contact.id}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load HubSpot contacts: {e}")

        return docs

    def load_companies(self, max_results: int = 100) -> list[LoadedDocument]:
        """Load companies from HubSpot."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            response = self._client.crm.companies.basic_api.get_page(limit=max_results)

            for company in response.results:
                doc = self.load_document(f"company:{company.id}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load HubSpot companies: {e}")

        return docs

    def load_deals(self, max_results: int = 100) -> list[LoadedDocument]:
        """Load deals from HubSpot."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            response = self._client.crm.deals.basic_api.get_page(limit=max_results)

            for deal in response.results:
                doc = self.load_document(f"deal:{deal.id}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load HubSpot deals: {e}")

        return docs

    def load_tickets(self, max_results: int = 100) -> list[LoadedDocument]:
        """Load tickets from HubSpot."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            response = self._client.crm.tickets.basic_api.get_page(limit=max_results)

            for ticket in response.results:
                doc = self.load_document(f"ticket:{ticket.id}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Failed to load HubSpot tickets: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search across HubSpot CRM."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        docs = []

        try:
            from hubspot.crm.contacts import PublicObjectSearchRequest

            search_request = PublicObjectSearchRequest(
                query=query,
                limit=max_results,
            )

            response = self._client.crm.contacts.search_api.do_search(search_request)

            for contact in response.results:
                doc = self.load_document(f"contact:{contact.id}")
                if doc:
                    docs.append(doc)

        except Exception as e:
            logger.error(f"HubSpot search failed: {e}")

        return docs

    async def load_async(self, doc_id: str) -> Optional[LoadedDocument]:
        """Async document loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.load_document, doc_id)

    async def load_folder_async(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Async folder loading."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.load_folder, folder_path, recursive
        )


# ============================================================================
# SALESFORCE LOADER
# ============================================================================

# Check for simple_salesforce availability
try:
    from simple_salesforce import Salesforce

    SALESFORCE_AVAILABLE = True
except ImportError:
    SALESFORCE_AVAILABLE = False


__all__ = [
    "ZendeskLoader",
    "IntercomLoader",
    "FreshdeskLoader",
    "HubSpotLoader",
    "ZENDESK_AVAILABLE",
    "INTERCOM_AVAILABLE",
    "HUBSPOT_AVAILABLE",
]
