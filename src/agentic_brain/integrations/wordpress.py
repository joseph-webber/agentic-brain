# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
WordPress REST API integration.

Access WordPress through its REST API, not direct database access.
Permissions are controlled by WordPress user roles (subscriber, author, editor, administrator).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..security.api_access import (
    APIAccessController,
    APIEndpoint,
    APIScope,
    AuthType,
    SecurityViolation,
)
from ..security.roles import SecurityRole


class WordPressRole(Enum):
    """WordPress user roles with increasing privileges."""

    SUBSCRIBER = "subscriber"  # Can read, manage own profile
    CONTRIBUTOR = "contributor"  # Can write posts but not publish
    AUTHOR = "author"  # Can publish own posts
    EDITOR = "editor"  # Can publish and manage posts
    ADMINISTRATOR = "administrator"  # Full WordPress access
    CUSTOMER = "customer"  # WooCommerce customer role


@dataclass
class WordPressCapabilities:
    """WordPress capabilities based on role."""

    # Content
    can_read_posts: bool = True
    can_create_posts: bool = False
    can_edit_posts: bool = False
    can_edit_others_posts: bool = False
    can_publish_posts: bool = False
    can_delete_posts: bool = False

    # Media
    can_upload_files: bool = False
    can_edit_files: bool = False

    # Users
    can_list_users: bool = False
    can_create_users: bool = False
    can_edit_users: bool = False
    can_delete_users: bool = False

    # Settings
    can_manage_options: bool = False
    can_manage_categories: bool = False
    can_moderate_comments: bool = False

    @classmethod
    def from_role(cls, role: WordPressRole) -> WordPressCapabilities:
        """Get capabilities for a WordPress role."""

        if role == WordPressRole.SUBSCRIBER:
            return cls(
                can_read_posts=True,
            )

        elif role == WordPressRole.CONTRIBUTOR:
            return cls(
                can_read_posts=True,
                can_create_posts=True,
                can_edit_posts=True,  # Own posts only
            )

        elif role == WordPressRole.AUTHOR:
            return cls(
                can_read_posts=True,
                can_create_posts=True,
                can_edit_posts=True,
                can_publish_posts=True,
                can_delete_posts=True,  # Own posts only
                can_upload_files=True,
            )

        elif role == WordPressRole.EDITOR:
            return cls(
                can_read_posts=True,
                can_create_posts=True,
                can_edit_posts=True,
                can_edit_others_posts=True,
                can_publish_posts=True,
                can_delete_posts=True,
                can_upload_files=True,
                can_edit_files=True,
                can_manage_categories=True,
                can_moderate_comments=True,
            )

        elif role == WordPressRole.ADMINISTRATOR:
            return cls(
                can_read_posts=True,
                can_create_posts=True,
                can_edit_posts=True,
                can_edit_others_posts=True,
                can_publish_posts=True,
                can_delete_posts=True,
                can_upload_files=True,
                can_edit_files=True,
                can_list_users=True,
                can_create_users=True,
                can_edit_users=True,
                can_delete_users=True,
                can_manage_options=True,
                can_manage_categories=True,
                can_moderate_comments=True,
            )

        elif role == WordPressRole.CUSTOMER:
            # WooCommerce customer - can read and manage own orders
            return cls(
                can_read_posts=True,
            )

        return cls()


class WordPressAPI:
    """
    Access WordPress through REST API, not direct DB.

    This enforces WordPress's own permission system - we don't bypass it.
    The chatbot acts as a user with specific WordPress role privileges.
    """

    def __init__(
        self,
        site_url: str,
        username: str,
        app_password: str,
        wp_role: WordPressRole,
        api_controller: APIAccessController,
    ):
        """
        Initialize WordPress API client.

        Args:
            site_url: WordPress site URL (e.g., "https://example.com")
            username: WordPress username
            app_password: WordPress application password
            wp_role: WordPress role for this user
            api_controller: API access controller (enforces chatbot role)
        """
        self.site_url = site_url.rstrip("/")
        self.username = username
        self.wp_role = wp_role
        self.capabilities = WordPressCapabilities.from_role(wp_role)
        self.api_controller = api_controller

        # Determine allowed API scopes based on WordPress role
        scopes = [APIScope.READ]  # Everyone can read

        if self.capabilities.can_create_posts or self.capabilities.can_edit_posts:
            scopes.append(APIScope.WRITE)

        if self.capabilities.can_delete_posts:
            scopes.append(APIScope.DELETE)

        if wp_role == WordPressRole.ADMINISTRATOR:
            scopes.append(APIScope.ADMIN)

        # Register WordPress API
        endpoint = APIEndpoint(
            name="wordpress",
            base_url=f"{self.site_url}/wp-json/wp/v2",
            auth_type=AuthType.WORDPRESS_APP,
            allowed_scopes=scopes,
            rate_limit=60,  # 60 requests per minute
            api_role=wp_role.value,
            description=f"WordPress REST API ({wp_role.value} role)",
        )

        credentials = {
            "username": username,
            "password": app_password,
        }

        api_controller.register_api(endpoint, credentials)

    # --- Posts ---

    async def list_posts(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str = "publish",
        author: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List posts.

        Args:
            per_page: Posts per page
            page: Page number
            status: Post status (publish, draft, private)
            author: Filter by author ID

        Returns:
            List of posts
        """
        params = {
            "per_page": per_page,
            "page": page,
            "status": status,
        }

        if author:
            params["author"] = author

        response = await self.api_controller.call_api(
            "wordpress",
            "GET",
            "/posts",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_post(self, post_id: int) -> Dict[str, Any]:
        """Get a single post by ID."""
        response = await self.api_controller.call_api(
            "wordpress",
            "GET",
            f"/posts/{post_id}",
        )
        response.raise_for_status()
        return response.json()

    async def create_post(
        self, title: str, content: str, status: str = "draft", **kwargs
    ) -> Dict[str, Any]:
        """
        Create a new post.

        Args:
            title: Post title
            content: Post content (HTML)
            status: Post status (draft, publish, private)
            **kwargs: Additional post fields

        Returns:
            Created post data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_create_posts:
            raise SecurityViolation(
                f"WordPress role {self.wp_role.value} cannot create posts"
            )

        # Ensure non-authors can't publish directly
        if status == "publish" and not self.capabilities.can_publish_posts:
            status = "draft"

        data = {"title": title, "content": content, "status": status, **kwargs}

        response = await self.api_controller.call_api(
            "wordpress",
            "POST",
            "/posts",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    async def update_post(self, post_id: int, **fields) -> Dict[str, Any]:
        """
        Update a post.

        Args:
            post_id: Post ID to update
            **fields: Fields to update

        Returns:
            Updated post data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_edit_posts:
            raise SecurityViolation(
                f"WordPress role {self.wp_role.value} cannot edit posts"
            )

        response = await self.api_controller.call_api(
            "wordpress",
            "POST",
            f"/posts/{post_id}",
            json=fields,
        )
        response.raise_for_status()
        return response.json()

    async def delete_post(self, post_id: int, force: bool = False) -> Dict[str, Any]:
        """
        Delete a post.

        Args:
            post_id: Post ID to delete
            force: Bypass trash and force deletion

        Returns:
            Deleted post data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_delete_posts:
            raise SecurityViolation(
                f"WordPress role {self.wp_role.value} cannot delete posts"
            )

        params = {"force": force}

        response = await self.api_controller.call_api(
            "wordpress",
            "DELETE",
            f"/posts/{post_id}",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    # --- Users ---

    async def list_users(self) -> List[Dict[str, Any]]:
        """
        List users.

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_list_users:
            raise SecurityViolation(
                f"WordPress role {self.wp_role.value} cannot list users"
            )

        response = await self.api_controller.call_api(
            "wordpress",
            "GET",
            "/users",
        )
        response.raise_for_status()
        return response.json()

    async def get_current_user(self) -> Dict[str, Any]:
        """Get the current authenticated user."""
        response = await self.api_controller.call_api(
            "wordpress",
            "GET",
            "/users/me",
        )
        response.raise_for_status()
        return response.json()

    # --- Media ---

    async def upload_media(
        self,
        file_path: str,
        title: Optional[str] = None,
        alt_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a media file.

        Args:
            file_path: Path to file to upload
            title: Media title
            alt_text: Alt text for accessibility

        Returns:
            Uploaded media data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_upload_files:
            raise SecurityViolation(
                f"WordPress role {self.wp_role.value} cannot upload files"
            )

        # TODO: Implement multipart file upload
        raise NotImplementedError("Media upload not yet implemented")

    # --- Comments ---

    async def list_comments(
        self,
        post_id: Optional[int] = None,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """List comments, optionally filtered by post."""
        params = {"per_page": per_page}

        if post_id:
            params["post"] = post_id

        response = await self.api_controller.call_api(
            "wordpress",
            "GET",
            "/comments",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def create_comment(
        self,
        post_id: int,
        content: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a comment on a post."""
        data = {
            "post": post_id,
            "content": content,
        }

        if author_name:
            data["author_name"] = author_name
        if author_email:
            data["author_email"] = author_email

        response = await self.api_controller.call_api(
            "wordpress",
            "POST",
            "/comments",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    # --- Categories and Tags ---

    async def list_categories(self) -> List[Dict[str, Any]]:
        """List all categories."""
        response = await self.api_controller.call_api(
            "wordpress",
            "GET",
            "/categories",
        )
        response.raise_for_status()
        return response.json()

    async def list_tags(self) -> List[Dict[str, Any]]:
        """List all tags."""
        response = await self.api_controller.call_api(
            "wordpress",
            "GET",
            "/tags",
        )
        response.raise_for_status()
        return response.json()


# Helper function to create WordPress API client
def create_wordpress_client(
    site_url: str,
    username: str,
    app_password: str,
    wp_role: WordPressRole,
    chatbot_role: SecurityRole,
) -> WordPressAPI:
    """
    Create a WordPress API client.

    Args:
        site_url: WordPress site URL
        username: WordPress username
        app_password: WordPress application password
        wp_role: WordPress role for this user
        chatbot_role: Chatbot security role (ADMIN, USER, GUEST)

    Returns:
        Configured WordPressAPI client
    """
    from ..security.api_access import create_api_controller

    api_controller = create_api_controller(chatbot_role)

    return WordPressAPI(
        site_url=site_url,
        username=username,
        app_password=app_password,
        wp_role=wp_role,
        api_controller=api_controller,
    )
